# -*- coding: utf-8 -*-
"""Everything that reaches the network, behind one small interface.

Two reasons it is one class and not scattered `urlopen` calls: the tests
replace it with a dictionary, and a user can see in one place exactly which
hosts this tool talks to (api.github.com, pypi.org, registry.npmjs.org, and
whatever URLs your own README links to).

The distinction this module is built around is **absent** versus **could not
look**. A 404 from PyPI means the distribution is not published. A 403, a
rate limit or a timeout means nothing at all — and a checker that treats the
second like the first will eventually accuse a healthy project of shipping a
broken install command. Callers get `None` when the answer is unknown.
"""

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

GITHUB_API = "https://api.github.com"
PYPI = "https://pypi.org/pypi/%s/json"
NPM = "https://registry.npmjs.org/%s"

KULLANICI = "repo-vet"


# A GitHub API call that failed this way is asked once more. Not a rate limit
# (asking again makes it worse), not a 404 (that is an answer), and never an
# outbound link (a slow third-party host is that host's business).
YENIDEN = (500, 502, 503, 504)


class _YonlendirmedeJetonuBirak(urllib.request.HTTPRedirectHandler):
    """Follow redirects, but never carry the token to another origin.

    urllib copies every header of the original request onto the redirected
    one, `Authorization` included, whatever host the `Location` names. GitHub
    redirects a renamed repository to another path on api.github.com, which
    is fine; a redirect that leaves that origin -- another host, another
    port, or https downgraded to http -- gets the request without the token.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        yeni = urllib.request.HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, newurl)
        if yeni is not None and _koken(newurl) != _koken(req.full_url):
            yeni.remove_header("Authorization")
        return yeni


def _koken(url):
    parca = urllib.parse.urlsplit(url)
    return (parca.scheme.lower(), (parca.hostname or "").lower(),
            parca.port or {"http": 80, "https": 443}.get(parca.scheme.lower()))


def _varsayilan_acici():
    return urllib.request.build_opener(_YonlendirmedeJetonuBirak).open


class Client(object):
    """A thin, honest HTTP client. One retry for GitHub's own hiccups, no
    caching magic, no surprises."""

    def __init__(self, token=None, timeout=20, opener=None, workers=8,
                 sleep=None):
        self.token = token
        self.timeout = timeout
        self.workers = max(1, workers)
        self._opener = opener or _varsayilan_acici()
        self._sleep = sleep or time.sleep
        self._cache = {}
        self.rate_limited = False
        self.rate_reset = None          # epoch seconds, from X-RateLimit-Reset
        self.bad_credentials = False    # GitHub answered 401 to this token

    # -- low level ---------------------------------------------------------

    def _fetch(self, url, accept=None, auth=False, timeout=None):
        headers = {"User-Agent": KULLANICI}
        if accept:
            headers["Accept"] = accept
        if auth and self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(url, headers=headers)
        with self._opener(req, timeout=timeout or self.timeout) as r:
            return getattr(r, "status", 200), r.read(), dict(r.headers)

    def _get(self, url, accept=None, auth=False, timeout=None):
        """(status, bytes) — status None when the host could not be reached."""
        github = url.startswith(GITHUB_API + "/")
        kod, govde = self._get_once(url, accept, auth, timeout)
        if github and (kod is None or kod in YENIDEN):
            self._sleep(1)
            kod, govde = self._get_once(url, accept, auth, timeout)
        return kod, govde

    def _get_once(self, url, accept, auth, timeout):
        try:
            kod, govde, basliklar = self._fetch(url, accept, auth, timeout)
            return kod, govde
        except urllib.error.HTTPError as e:
            if url.startswith(GITHUB_API + "/"):
                self._github_error(e)
            return e.code, None
        except Exception:
            return None, None

    def _github_error(self, e):
        """Remember why GitHub said no, so the report can say it too."""
        basliklar = e.headers or {}
        if e.code == 401:
            self.bad_credentials = True
        elif e.code in (403, 429):
            # The primary limit (60/hour without a token, 5,000 with one)
            # says so with Remaining: 0; a secondary limit says Retry-After.
            # A plain 403 is neither and stays a plain 403. Remembering it
            # lets the report say "not checked" instead of inventing a clean
            # bill of health.
            if (basliklar.get("X-RateLimit-Remaining") == "0"
                    or basliklar.get("Retry-After") is not None):
                self.rate_limited = True
                try:
                    self.rate_reset = int(basliklar.get("X-RateLimit-Reset"))
                except (TypeError, ValueError):
                    pass

    def status(self, url, timeout=None):
        """HTTP status for a URL, or None when the host could not be reached."""
        if url in self._cache:
            return self._cache[url]
        kod, _ = self._get(url, timeout=timeout)
        self._cache[url] = kod
        return kod

    def statuses(self, urls, timeout=None):
        """Many URLs at once. Forty links checked one at a time is a coffee break."""
        urls = list(urls)
        if not urls:
            return {}
        with ThreadPoolExecutor(max_workers=self.workers) as havuz:
            sonuc = list(havuz.map(lambda u: self.status(u, timeout), urls))
        return dict(zip(urls, sonuc))

    def json(self, url, auth=False):
        """(data, known) — `known` is False when the answer could not be read.

        `(None, True)` means the resource is genuinely absent (404).
        """
        kod, govde = self._get(url, accept="application/vnd.github+json", auth=auth)
        if kod == 404:
            return None, True
        if kod != 200 or govde is None:
            return None, False
        try:
            return json.loads(govde.decode("utf-8")), True
        except Exception:
            return None, False

    # -- GitHub ------------------------------------------------------------

    def repo(self, slug):
        """(metadata, known). Absent and unreadable are not the same thing."""
        return self.json("%s/repos/%s" % (GITHUB_API, slug), auth=True)

    def tree(self, slug, ref):
        """(paths, truncated) — or (None, False) when the tree could not be read.

        `truncated` matters: GitHub caps a recursive tree, and torvalds/linux
        comes back with 71,638 of its entries and a flag saying so. Checking a
        link against a partial tree would report perfectly good files as
        missing.
        """
        veri, _ = self.json("%s/repos/%s/git/trees/%s?recursive=1"
                            % (GITHUB_API, slug, urllib.parse.quote(ref)), auth=True)
        if not veri:
            return None, False
        yollar = set(g.get("path", "") for g in veri.get("tree", []))
        return yollar, bool(veri.get("truncated"))

    def readme(self, slug, ref=None):
        """(text, known). `(None, True)`: there is no README. `(None, False)`:
        there may be one, but it could not be read."""
        url = "%s/repos/%s/readme" % (GITHUB_API, slug)
        if ref:
            url += "?ref=" + urllib.parse.quote(ref, safe="")
        return self._icerik(url)

    def file_text(self, slug, path, ref=None):
        """(text, known), with the same meaning as `readme`."""
        url = "%s/repos/%s/contents/%s" % (GITHUB_API, slug, urllib.parse.quote(path))
        if ref:
            url += "?ref=" + urllib.parse.quote(ref, safe="")
        return self._icerik(url)

    def _icerik(self, url):
        veri, bilinen = self.json(url, auth=True)
        if veri is None:
            return None, bilinen
        if not isinstance(veri, dict) or "content" not in veri:
            return None, True             # a directory or a submodule, not a file
        try:
            return base64.b64decode(veri["content"]).decode("utf-8", "replace"), True
        except (TypeError, ValueError):
            return None, False

    def commit_sha(self, slug, ref):
        """The commit `ref` names: its SHA, `""` when there is no such ref,
        `None` when GitHub could not be asked."""
        kod, govde = self._get("%s/repos/%s/commits/%s"
                               % (GITHUB_API, slug, urllib.parse.quote(ref, safe="")),
                               accept="application/vnd.github.sha", auth=True)
        if kod == 200 and govde:
            return govde.decode("ascii", "replace").strip()
        if kod in (404, 422):
            return ""
        return None

    def tags(self, slug):
        """Tag objects, `[]` when there are none, `None` when unknown."""
        return self._liste("%s/repos/%s/tags?per_page=100" % (GITHUB_API, slug))

    def releases(self, slug):
        """Release objects, `[]` when there are none, `None` when unknown."""
        return self._liste("%s/repos/%s/releases?per_page=100" % (GITHUB_API, slug))

    def _liste(self, url):
        veri, bilinen = self.json(url, auth=True)
        if veri is None:
            return [] if bilinen else None
        return veri

    def workflow_runs(self, slug, path):
        veri, _ = self.json("%s/repos/%s/actions/workflows/%s/runs?per_page=1"
                            % (GITHUB_API, slug, urllib.parse.quote(path)), auth=True)
        if not veri:
            return None
        return veri.get("total_count", 0)

    # -- package registries ------------------------------------------------

    def pypi_versions(self, name):
        """Released versions, `set()` when unpublished, `None` when unknown."""
        veri, bilinen = self.json(PYPI % urllib.parse.quote(name))
        if veri is None:
            return set() if bilinen else None
        return set(veri.get("releases") or {})

    def npm_versions(self, name):
        veri, bilinen = self.json(NPM % urllib.parse.quote(name, safe="@/"))
        if veri is None:
            return set() if bilinen else None
        return set(veri.get("versions") or {})
