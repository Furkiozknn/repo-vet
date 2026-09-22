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
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

GITHUB_API = "https://api.github.com"
PYPI = "https://pypi.org/pypi/%s/json"
NPM = "https://registry.npmjs.org/%s"

KULLANICI = "repo-vet"


class Client(object):
    """A thin, honest HTTP client. No retries, no caching magic, no surprises."""

    def __init__(self, token=None, timeout=20, opener=None, workers=8):
        self.token = token
        self.timeout = timeout
        self.workers = max(1, workers)
        self._opener = opener or urllib.request.urlopen
        self._cache = {}
        self.rate_limited = False

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
        try:
            kod, govde, basliklar = self._fetch(url, accept, auth, timeout)
            return kod, govde
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and "api.github.com" in url:
                # Secondary rate limits and the unauthenticated 60/hour ceiling
                # both land here. Remembering it lets the report say "not
                # checked" instead of inventing a clean bill of health.
                if (e.headers or {}).get("X-RateLimit-Remaining") == "0":
                    self.rate_limited = True
            return e.code, None
        except Exception:
            return None, None

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

    def _veri(self, url, auth=False, varsayilan=None):
        veri, _ = self.json(url, auth=auth)
        return varsayilan if veri is None else veri

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
        url = "%s/repos/%s/readme" % (GITHUB_API, slug)
        if ref:
            url += "?ref=" + urllib.parse.quote(ref)
        veri, _ = self.json(url, auth=True)
        if not veri or "content" not in veri:
            return None
        return base64.b64decode(veri["content"]).decode("utf-8", "replace")

    def file_text(self, slug, path, ref=None):
        url = "%s/repos/%s/contents/%s" % (GITHUB_API, slug, urllib.parse.quote(path))
        if ref:
            url += "?ref=" + urllib.parse.quote(ref)
        veri, _ = self.json(url, auth=True)
        if not veri or "content" not in veri:
            return None
        return base64.b64decode(veri["content"]).decode("utf-8", "replace")

    def tags(self, slug):
        return self._veri("%s/repos/%s/tags?per_page=100" % (GITHUB_API, slug),
                          auth=True, varsayilan=[])

    def releases(self, slug):
        return self._veri("%s/repos/%s/releases?per_page=100" % (GITHUB_API, slug),
                          auth=True, varsayilan=[])

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
