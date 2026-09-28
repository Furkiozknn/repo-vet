# -*- coding: utf-8 -*-
"""Not checked is not clean — at the exit code, not only in the prose.

Before these tests, a repository that could not be read at all (a typo in the
slug, a rate limit, a rejected token, GitHub being down) printed
"clean (0 checks)" and exited 0. In CI that is a green tick for an audit that
never happened, which is the one failure this tool exists to avoid.
"""

import contextlib
import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakes import FakeClient                                  # noqa: E402
from repo_vet import checks, cli                              # noqa: E402
from repo_vet.model import Report                             # noqa: E402
from repo_vet.report import as_markdown, as_text              # noqa: E402
from repo_vet.runner import vet                               # noqa: E402
from repo_vet.sources import Client                           # noqa: E402

REPO = {"default_branch": "main", "homepage": ""}


def _okunamayan():
    return Report("o/r", skipped=[("*", "GitHub could not be read")])


def _kos(rapor, argv):
    eski_client, eski_vet = cli.Client, cli.vet
    cli.Client = lambda *a, **kw: None
    cli.vet = lambda slug, client, **kw: rapor
    cikti, hata = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(cikti), contextlib.redirect_stderr(hata):
            kod = cli.main(argv)
    finally:
        cli.Client, cli.vet = eski_client, eski_vet
    return kod, cikti.getvalue(), hata.getvalue()


class ExitCode(unittest.TestCase):
    def test_unreadable_repository_does_not_exit_zero(self):
        kod, _, _ = _kos(_okunamayan(), ["o/r"])
        self.assertEqual(kod, 3)

    def test_fail_on_none_still_exits_zero(self):
        kod, _, _ = _kos(_okunamayan(), ["o/r", "--fail-on", "none"])
        self.assertEqual(kod, 0)

    def test_fail_on_any_also_refuses_a_green_tick(self):
        kod, _, _ = _kos(_okunamayan(), ["o/r", "--fail-on", "any"])
        self.assertEqual(kod, 3)

    def test_errors_still_win_over_unchecked(self):
        # One repository with a real error, one unreadable: the concrete
        # finding decides the exit code.
        hatali = Report("o/r", checked=["install"])
        from repo_vet.model import Finding
        hatali.add(Finding("install", "missing", "404"))
        raporlar = iter([hatali, _okunamayan()])
        eski_client, eski_vet = cli.Client, cli.vet
        cli.Client = lambda *a, **kw: None
        cli.vet = lambda slug, client, **kw: next(raporlar)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                kod = cli.main(["o/r", "o/s"])
        finally:
            cli.Client, cli.vet = eski_client, eski_vet
        self.assertEqual(kod, 1)

    def test_skipping_every_check_on_request_is_not_unreadable(self):
        r = Report("o/r", skipped=[("install", "skipped on request")])
        self.assertEqual(_kos(r, ["o/r"])[0], 0)

    def test_bad_slug_is_rejected_before_any_scan(self):
        taranan = []
        eski_client, eski_vet = cli.Client, cli.vet
        cli.Client = lambda *a, **kw: None
        cli.vet = lambda slug, client, **kw: taranan.append(slug) or Report(slug)
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                kod = cli.main(["o/r", "not-a-slug"])
        finally:
            cli.Client, cli.vet = eski_client, eski_vet
        self.assertEqual(kod, 2)
        self.assertEqual(taranan, [])


class Wording(unittest.TestCase):
    def test_text_does_not_say_clean(self):
        m = as_text(_okunamayan())
        self.assertNotIn("clean", m)
        self.assertIn("not checked", m)
        self.assertIn("GitHub could not be read", m)

    def test_markdown_does_not_say_clean(self):
        m = as_markdown(_okunamayan())
        self.assertNotIn("Clean", m)
        self.assertIn("Not checked", m)

    def test_json_keeps_its_shape(self):
        d = json.loads(_okunamayan().as_json())
        self.assertEqual(sorted(d), ["checks_run", "checks_skipped",
                                     "error_count", "finding_count",
                                     "findings", "repository"])
        self.assertEqual(d["checks_run"], [])
        self.assertEqual(d["checks_skipped"][0]["check"], "*")


class Messages(unittest.TestCase):
    def test_rate_limit_without_a_token_asks_for_one(self):
        c = FakeClient(repo=None, repo_known=False, rate_limited=True)
        (sebep,) = [s for a, s in vet("o/r", c).skipped if a == "*"][:1]
        self.assertIn("rate limit", sebep)
        self.assertIn("GITHUB_TOKEN", sebep)

    def test_rate_limit_with_a_token_does_not_ask_for_one(self):
        c = FakeClient(repo=None, repo_known=False, rate_limited=True)
        c.token = "t"
        c.rate_reset = 1790330605              # 2026-09-25 10:03:25 UTC
        sebep = vet("o/r", c).skipped[0][1]
        self.assertIn("this token", sebep)
        self.assertIn("10:03 UTC", sebep)
        self.assertNotIn("pass a token", sebep)

    def test_rejected_token_is_named(self):
        c = FakeClient(repo=None, repo_known=False)
        c.token = "t"
        c.bad_credentials = True
        sebep = vet("o/r", c).skipped[0][1]
        self.assertIn("rejected the token", sebep)

    def test_readme_hidden_by_a_rate_limit_is_not_absent(self):
        c = FakeClient(repo=REPO, readme=None, tree=set(), rate_limited=True)
        c.readme_known = False
        sebepler = dict(vet("o/r", c).skipped)
        self.assertNotIn("has no README", sebepler.get("readme", ""))
        self.assertIn("could not be read", sebepler["readme"])


class ReleaseWhenTagsAreUnknown(unittest.TestCase):
    def test_unreadable_tags_are_not_never_tagged(self):
        # tags() used to fold "could not ask" into [], and the release check
        # then announced that a project had never been tagged.
        fc = FakeClient(files={"pyproject.toml": '[project]\nversion = "1.2.0"\n'})
        fc._tags = None
        c = checks.Context("o/r", fc, meta={}, text="", tree=None)
        with self.assertRaises(checks.NotChecked):
            checks.check_release(c)

    def test_unreadable_releases_do_not_crash(self):
        fc = FakeClient(files={"pyproject.toml": '[project]\nversion = "1.2.0"\n'},
                        tags=[{"name": "v1.2.0"}])
        fc._releases = None
        c = checks.Context("o/r", fc, meta={}, text="", tree=None)
        with self.assertRaises(checks.NotChecked):
            checks.check_release(c)


class _Yanit(object):
    status = 200
    headers = {}

    def __init__(self, govde):
        self.govde = govde

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.govde


def _http(kod, basliklar=None):
    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, kod, "x", basliklar or {}, None)
    return opener


class ClientSignals(unittest.TestCase):
    def test_primary_rate_limit_is_remembered_with_its_reset(self):
        c = Client(opener=_http(403, {"X-RateLimit-Remaining": "0",
                                      "X-RateLimit-Reset": "1790330605"}))
        self.assertEqual(c.repo("o/r"), (None, False))
        self.assertTrue(c.rate_limited)
        self.assertEqual(c.rate_reset, 1790330605)

    def test_secondary_rate_limit_is_remembered(self):
        c = Client(opener=_http(403, {"Retry-After": "60"}))
        c.repo("o/r")
        self.assertTrue(c.rate_limited)

    def test_plain_403_is_not_a_rate_limit(self):
        c = Client(opener=_http(403))
        c.repo("o/r")
        self.assertFalse(c.rate_limited)

    def test_401_marks_the_token_as_rejected(self):
        c = Client(token="bad", opener=_http(401))
        self.assertEqual(c.repo("o/r"), (None, False))
        self.assertTrue(c.bad_credentials)

    def test_tags_unknown_is_none_absent_is_empty(self):
        self.assertIsNone(Client(opener=_http(503), sleep=lambda s: None).tags("o/r"))
        self.assertEqual(Client(opener=_http(404)).tags("o/r"), [])

    def test_one_retry_on_a_transient_github_failure(self):
        cagri = []

        def opener(req, timeout):
            cagri.append(req.full_url)
            if len(cagri) == 1:
                raise urllib.error.HTTPError(req.full_url, 502, "x", {}, None)
            return _Yanit(b'{"default_branch": "main"}')

        c = Client(opener=opener, sleep=lambda s: None)
        self.assertEqual(c.repo("o/r"), ({"default_branch": "main"}, True))
        self.assertEqual(len(cagri), 2)

    def test_timeouts_are_retried_once_then_unknown(self):
        cagri = []

        def opener(req, timeout):
            cagri.append(1)
            raise TimeoutError("slow")

        c = Client(opener=opener, sleep=lambda s: None)
        self.assertEqual(c.repo("o/r"), (None, False))
        self.assertEqual(len(cagri), 2)

    def test_outbound_links_are_not_retried(self):
        cagri = []

        def opener(req, timeout):
            cagri.append(1)
            raise TimeoutError("slow")

        c = Client(opener=opener, sleep=lambda s: None)
        self.assertIsNone(c.status("https://example.com/x"))
        self.assertEqual(len(cagri), 1)

    def test_a_404_is_not_retried(self):
        cagri = []

        def opener(req, timeout):
            cagri.append(1)
            raise urllib.error.HTTPError(req.full_url, 404, "x", {}, None)

        Client(opener=opener, sleep=lambda s: None).repo("o/r")
        self.assertEqual(len(cagri), 1)


if __name__ == "__main__":                                # pragma: no cover
    unittest.main(verbosity=2)
