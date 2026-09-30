# -*- coding: utf-8 -*-
"""What a first-time user sees: a wrong first command names the right one,
--help carries examples and the exit codes, and every command the README
shows is accepted by the parser."""

import contextlib
import io
import os
import re
import shlex
import unittest

from repo_vet import cli
from repo_vet.model import Report
from repo_vet.report import as_text
from repo_vet.runner import vet

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORNEK = "repo-vet Furkiozknn/repo-vet"


def _calistir(argv):
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        try:
            kod = cli.main(argv)
        except SystemExit as e:
            kod = e.code
    return kod, out.getvalue(), err.getvalue()


class SlugHint(unittest.TestCase):
    def test_pasted_url_becomes_the_command_that_works(self):
        self.assertEqual(cli.slug_hint("https://github.com/Furkiozknn/repo-vet"), ORNEK)
        self.assertEqual(cli.slug_hint("https://github.com/Furkiozknn/repo-vet/tree/main"), ORNEK)
        self.assertEqual(cli.slug_hint("https://github.com/Furkiozknn/repo-vet#readme"), ORNEK)

    def test_clone_urls_become_the_command_that_works(self):
        self.assertEqual(cli.slug_hint("https://github.com/Furkiozknn/repo-vet.git"), ORNEK)
        self.assertEqual(cli.slug_hint("git@github.com:Furkiozknn/repo-vet.git"), ORNEK)

    def test_a_folder_is_told_this_tool_does_not_scan_folders(self):
        for yol in (".", "..", "./repo-vet", "../x", "C:\\work\\repo"):
            self.assertIn("does not scan a local folder", cli.slug_hint(yol), yol)

    def test_trailing_slash_is_dropped(self):
        self.assertEqual(cli.slug_hint("Furkiozknn/repo-vet/"), ORNEK)

    def test_a_bare_name_gets_the_owner_name_shape(self):
        self.assertIn("OWNER/NAME", cli.slug_hint("repo-vet"))
        self.assertIn(ORNEK, cli.slug_hint("repo-vet"))

    def test_every_hint_that_is_a_command_is_itself_a_valid_slug(self):
        for kotu in ("https://github.com/o/r", "git@github.com:o/r.git", "o/r/"):
            komut = cli.slug_hint(kotu)
            self.assertTrue(komut.startswith("repo-vet "))
            self.assertTrue(cli.slug_ok(komut.split(" ", 1)[1]), komut)


class FirstRunMessages(unittest.TestCase):
    def test_bad_slug_exits_2_names_the_slug_and_a_hint(self):
        kod, out, err = _calistir(["https://github.com/o/r"])
        self.assertEqual(kod, 2)
        self.assertIn("not an OWNER/NAME slug: https://github.com/o/r", err)
        self.assertIn("hint: repo-vet o/r", err)
        self.assertEqual(out, "")

    def test_no_arguments_shows_an_example_and_points_at_help(self):
        kod, _, err = _calistir([])
        self.assertEqual(kod, 2)
        self.assertIn("nothing to check", err)
        self.assertIn(ORNEK, err)
        self.assertIn("--help", err)

    def test_help_has_examples_and_every_exit_code(self):
        kod, out, _ = _calistir(["--help"])
        self.assertEqual(kod, 0)
        self.assertIn("examples:", out)
        self.assertIn(ORNEK.replace("Furkiozknn/repo-vet", "OWNER/NAME"), out)
        for kodu in ("0  ", "1  ", "2  ", "3  "):
            self.assertIn("\n  " + kodu, out)
        self.assertIn("does not scan a local folder", out)
        self.assertIn("seconds to wait", out)          # --timeout is described


class _Istemci(object):
    """Just enough of Client for `vet` to stop at the first question."""

    rate_limited = False
    bad_credentials = False
    token = None

    def __init__(self, bilinen):
        self._bilinen = bilinen

    def repo(self, slug):
        return None, self._bilinen


class UnreadableRepository(unittest.TestCase):
    def test_missing_repository_says_what_to_check(self):
        r = vet("o/r", _Istemci(True))
        neden = r.skipped[0][1]
        self.assertIn("no such repository", neden)
        self.assertIn("--token", neden)

    def test_no_answer_at_all_names_the_likely_causes(self):
        r = vet("o/r", _Istemci(False))
        neden = r.skipped[0][1]
        self.assertIn("GitHub could not be read", neden)
        self.assertIn("no network", neden)

    def test_unreadable_output_says_nothing_was_looked_at(self):
        r = vet("o/r", _Istemci(True))
        metin = as_text(r)
        self.assertIn("o/r  not checked", metin)
        self.assertIn("nothing was looked at: no such repository", metin)
        self.assertNotIn("skipped (", metin)

    def test_a_skipped_check_keeps_its_old_wording(self):
        r = Report("o/r", checked=["links"], skipped=[("web", "skipped on request")])
        self.assertIn("- web: skipped (skipped on request)", as_text(r))

    def test_a_rate_limit_hit_mid_run_is_not_called_unreadable(self):
        r = Report("o/r", checked=["links"],
                   skipped=[("*", "a GitHub rate limit was hit during this run")])
        self.assertIn("- *: skipped (", as_text(r))
        self.assertNotIn("nothing was looked at", as_text(r))


class ReadmeCommands(unittest.TestCase):
    """A command the README shows must be one the parser accepts."""

    def _komutlar(self):
        with open(os.path.join(KOK, "README.md"), encoding="utf-8") as f:
            metin = f.read()
        bulunan = []
        for blok in re.findall(r"```(?:bash|console|sh)\n(.*?)```", metin, re.S):
            for satir in blok.splitlines():
                satir = satir.strip()
                if satir.startswith("$ "):
                    satir = satir[2:]
                satir = satir.split("  #")[0].strip()
                if satir.startswith("repo-vet ") and "[" not in satir:
                    bulunan.append(satir.replace("OWNER/NAME", "o/r"))
        return bulunan

    def test_the_readme_shows_commands(self):
        self.assertGreaterEqual(len(self._komutlar()), 6)

    def test_every_readme_command_parses(self):
        for komut in self._komutlar():
            argv = shlex.split(komut)[1:]
            hatali = io.StringIO()
            with contextlib.redirect_stderr(hatali):
                try:
                    cli._parser().parse_args(argv)
                except SystemExit:
                    self.fail("README command rejected by the parser: %s\n%s"
                              % (komut, hatali.getvalue()))
            slugs = [a for a in argv if "/" in a and not a.startswith("-")
                     and not a.endswith((".txt", ".json"))]
            for slug in slugs:
                self.assertTrue(cli.slug_ok(slug), "%s in: %s" % (slug, komut))


if __name__ == "__main__":                                # pragma: no cover
    unittest.main(verbosity=2)
