# -*- coding: utf-8 -*-
"""The command line: what it accepts, and what it exits with."""

import contextlib
import io
import json
import unittest

from repo_vet import cli
from repo_vet.model import Finding, Report


class FakeClientFactory(object):
    """Replaces Client so the CLI tests stay offline."""

    def __init__(self, *a, **kw):
        pass


def _yamalali(rapor, argv):
    """Run the CLI with the network replaced by a fixed report."""
    eski_client, eski_vet = cli.Client, cli.vet
    cli.Client = FakeClientFactory
    cli.vet = lambda slug, client, **kw: rapor
    cikti = io.StringIO()
    try:
        with contextlib.redirect_stdout(cikti):
            kod = cli.main(argv)
    finally:
        cli.Client, cli.vet = eski_client, eski_vet
    return kod, cikti.getvalue()


def _hatali(rapor=None):
    r = rapor or Report("o/r", checked=["install"])
    r.add(Finding("install", "missing", "not found"))
    return r


class Arguments(unittest.TestCase):
    def test_bad_slug_is_a_usage_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            kod = cli.main(["not-a-slug"])
        self.assertEqual(kod, 2)
        self.assertIn("OWNER/NAME", err.getvalue())

    def test_unknown_check_is_a_usage_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            kod = cli.main(["o/r", "--only", "teleport"])
        self.assertEqual(kod, 2)
        self.assertIn("unknown check", err.getvalue())

    def test_known_checks_are_listed_when_rejecting(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            cli.main(["o/r", "--skip", "nope"])
        self.assertIn("install", err.getvalue())


class ExitCodes(unittest.TestCase):
    def test_clean_repository_exits_zero(self):
        kod, _ = _yamalali(Report("o/r", checked=["install"]), ["o/r"])
        self.assertEqual(kod, 0)

    def test_error_exits_one(self):
        kod, _ = _yamalali(_hatali(), ["o/r"])
        self.assertEqual(kod, 1)

    def test_fail_on_none_always_exits_zero(self):
        kod, _ = _yamalali(_hatali(), ["o/r", "--fail-on", "none"])
        self.assertEqual(kod, 0)

    def test_warning_only_does_not_fail_by_default(self):
        r = Report("o/r", checked=["pages"])
        r.add(Finding("pages", "quiet site", "HTTP 200", "warning"))
        self.assertEqual(_yamalali(r, ["o/r"])[0], 0)
        self.assertEqual(_yamalali(r, ["o/r", "--fail-on", "any"])[0], 1)


class OutputFormats(unittest.TestCase):
    def test_json_is_a_list(self):
        _, cikti = _yamalali(_hatali(), ["o/r", "--json"])
        veri = json.loads(cikti)
        self.assertEqual(len(veri), 1)
        self.assertEqual(veri[0]["repository"], "o/r")

    def test_markdown_has_a_heading(self):
        _, cikti = _yamalali(_hatali(), ["o/r", "--markdown"])
        self.assertIn("### repo-vet", cikti)

    def test_text_is_the_default(self):
        _, cikti = _yamalali(_hatali(), ["o/r"])
        self.assertIn("Install command", cikti)


if __name__ == "__main__":                                # pragma: no cover
    unittest.main(verbosity=2)
