# -*- coding: utf-8 -*-
"""A client that answers from dictionaries, so no test touches the network.

Every test in this suite is offline. A test that depended on pypi.org would
fail on a train, and a linter you cannot run on a train is a linter you stop
running.
"""


class FakeClient(object):
    def __init__(self, repo=None, readme=None, tree=None, files=None,
                 tags=None, releases=None, runs=None, statuses=None,
                 pypi=None, npm=None):
        self._repo = repo
        self._readme = readme
        self._tree = tree
        self._files = files or {}
        self._tags = tags or []
        self._releases = releases or []
        self._runs = runs or {}
        self._statuses = statuses or {}
        self._pypi = pypi or {}
        self._npm = npm or {}
        self.asked = []

    def repo(self, slug):
        return self._repo

    def readme(self, slug, ref=None):
        return self._readme

    def tree(self, slug, ref):
        return self._tree

    def file_text(self, slug, path, ref=None):
        return self._files.get(path)

    def tags(self, slug):
        return self._tags

    def releases(self, slug):
        return self._releases

    def workflow_runs(self, slug, path):
        return self._runs.get(path)

    def status(self, url):
        self.asked.append(url)
        return self._statuses.get(url)

    def pypi_versions(self, name):
        self.asked.append("pypi:" + name)
        return set(self._pypi.get(name, []))

    def npm_versions(self, name):
        self.asked.append("npm:" + name)
        return set(self._npm.get(name, []))
