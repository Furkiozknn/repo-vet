# -*- coding: utf-8 -*-
"""Everything that reaches the network, behind one small interface.

Two reasons it is one class and not scattered `urlopen` calls: the tests
replace it with a dictionary, and a user can see in one place exactly which
hosts this tool talks to (api.github.com, pypi.org, registry.npmjs.org, and
whatever URLs your own README links to).
"""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

GITHUB_API = "https://api.github.com"
PYPI = "https://pypi.org/pypi/%s/json"
NPM = "https://registry.npmjs.org/%s"

KULLANICI = "repo-vet"


class Client(object):
    """A thin, honest HTTP client. No retries, no caching magic, no surprises."""

    def __init__(self, token=None, timeout=20, opener=None):
        self.token = token
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen
        self._cache = {}

    # -- low level ---------------------------------------------------------

    def _fetch(self, url, accept=None, auth=False, method="GET"):
        headers = {"User-Agent": KULLANICI}
        if accept:
            headers["Accept"] = accept
        if auth and self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(url, headers=headers, method=method)
        with self._opener(req, timeout=self.timeout) as r:
            return getattr(r, "status", 200), r.read()

    def status(self, url):
        """HTTP status for a URL, or None when the host could not be reached.

        None matters: unreachable is not the same as broken, and reporting a
        flaky network as a dead link would make the whole tool untrustworthy.
        """
        if url in self._cache:
            return self._cache[url]
        kod = None
        try:
            kod, _ = self._fetch(url)
        except urllib.error.HTTPError as e:
            kod = e.code
        except Exception:
            kod = None
        self._cache[url] = kod
        return kod

    def json(self, url, auth=False):
        """Parsed JSON, or None for 404 / unreachable."""
        try:
            _, ham = self._fetch(url, accept="application/vnd.github+json", auth=auth)
            return json.loads(ham.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 451):
                return None
            raise
        except Exception:
            return None

    # -- GitHub ------------------------------------------------------------

    def repo(self, slug):
        return self.json("%s/repos/%s" % (GITHUB_API, slug), auth=True)

    def tree(self, slug, ref):
        """Every path in the repository at `ref`, as a set."""
        veri = self.json("%s/repos/%s/git/trees/%s?recursive=1"
                         % (GITHUB_API, slug, urllib.parse.quote(ref)), auth=True)
        if not veri:
            return None
        return set(g.get("path", "") for g in veri.get("tree", []))

    def readme(self, slug, ref=None):
        url = "%s/repos/%s/readme" % (GITHUB_API, slug)
        if ref:
            url += "?ref=" + urllib.parse.quote(ref)
        veri = self.json(url, auth=True)
        if not veri or "content" not in veri:
            return None
        return base64.b64decode(veri["content"]).decode("utf-8", "replace")

    def file_text(self, slug, path, ref=None):
        url = "%s/repos/%s/contents/%s" % (GITHUB_API, slug, urllib.parse.quote(path))
        if ref:
            url += "?ref=" + urllib.parse.quote(ref)
        veri = self.json(url, auth=True)
        if not veri or "content" not in veri:
            return None
        return base64.b64decode(veri["content"]).decode("utf-8", "replace")

    def tags(self, slug):
        return self.json("%s/repos/%s/tags?per_page=20" % (GITHUB_API, slug),
                         auth=True) or []

    def releases(self, slug):
        return self.json("%s/repos/%s/releases?per_page=30" % (GITHUB_API, slug),
                         auth=True) or []

    def workflow_runs(self, slug, path):
        veri = self.json("%s/repos/%s/actions/workflows/%s/runs?per_page=1"
                         % (GITHUB_API, slug, urllib.parse.quote(path)), auth=True)
        if not veri:
            return None
        return veri.get("total_count", 0)

    # -- package registries ------------------------------------------------

    def pypi_versions(self, name):
        """Released versions on PyPI; empty set when the name is unused."""
        veri = self.json(PYPI % urllib.parse.quote(name))
        if veri is None:
            return set()
        return set(veri.get("releases") or {})

    def npm_versions(self, name):
        veri = self.json(NPM % urllib.parse.quote(name, safe="@/"))
        if veri is None:
            return set()
        return set(veri.get("versions") or {})
