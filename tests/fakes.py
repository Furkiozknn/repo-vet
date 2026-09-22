# -*- coding: utf-8 -*-
"""A client that answers from dictionaries, so no test touches the network.

Every test in this suite is offline. A test that depended on pypi.org would
fail on a train, and a linter you cannot run on a train is a linter you stop
running.

The fake mirrors the real client's two-valued answers on purpose: `repo`
returns (metadata, known) and the registries return `None` for "could not
ask". Those are exactly the paths where a careless checker invents findings,
so the fake must be able to reproduce them.
"""


class FakeClient(object):
    def __init__(self, repo=None, repo_known=True, readme=None, tree=None,
                 tree_truncated=False, files=None, tags=None, releases=None,
                 runs=None, statuses=None, pypi=None, npm=None,
                 rate_limited=False):
        self._repo = repo
        self._repo_known = repo_known
        self._readme = readme
        self._tree = tree
        self._tree_truncated = tree_truncated
        self._files = files or {}
        self._tags = tags or []
        self._releases = releases or []
        self._runs = runs or {}
        self._statuses = statuses or {}
        self._pypi = pypi if pypi is not None else {}
        self._npm = npm if npm is not None else {}
        self.rate_limited = rate_limited
        self.asked = []

    def repo(self, slug):
        return self._repo, self._repo_known

    def readme(self, slug, ref=None):
        return self._readme

    def tree(self, slug, ref):
        return self._tree, self._tree_truncated

    def file_text(self, slug, path, ref=None):
        return self._files.get(path)

    def tags(self, slug):
        return self._tags

    def releases(self, slug):
        return self._releases

    def workflow_runs(self, slug, path):
        return self._runs.get(path)

    def status(self, url, timeout=None):
        self.asked.append(url)
        return self._statuses.get(url)

    def statuses(self, urls, timeout=None):
        return dict((u, self.status(u)) for u in urls)

    def pypi_versions(self, name):
        self.asked.append("pypi:" + name)
        if self._pypi is None:
            return None                      # "could not ask"
        deger = self._pypi.get(name, [])
        return None if deger is None else set(deger)

    def npm_versions(self, name):
        self.asked.append("npm:" + name)
        if self._npm is None:
            return None
        deger = self._npm.get(name, [])
        return None if deger is None else set(deger)
