# -*- coding: utf-8 -*-
"""The command line: what it accepts, and what it exits with."""

import contextlib
import io
import json
import os
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


class FromFile(unittest.TestCase):
    def _dosya(self, icerik):
        import tempfile
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                        encoding="utf-8")
        f.write(icerik)
        f.close()
        self.addCleanup(lambda: os.unlink(f.name))
        return f.name

    def test_slugs_are_read_and_comments_ignored(self):
        yol = self._dosya("# a note\n\no/one\no/two   # trailing\n")
        gorulen = []
        rapor = Report("o/one", checked=["install"])
        eski_client, eski_vet = cli.Client, cli.vet
        cli.Client = FakeClientFactory
        cli.vet = lambda slug, client, **kw: (gorulen.append(slug) or rapor)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                kod = cli.main(["--from-file", yol])
        finally:
            cli.Client, cli.vet = eski_client, eski_vet
        self.assertEqual(kod, 0)
        self.assertEqual(gorulen, ["o/one", "o/two"])

    def test_missing_file_is_a_usage_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            kod = cli.main(["--from-file", "no-such-file.txt"])
        self.assertEqual(kod, 2)
        self.assertIn("cannot read", err.getvalue())

    def test_nothing_to_check_is_a_usage_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            kod = cli.main([])
        self.assertEqual(kod, 2)
        self.assertIn("nothing to check", err.getvalue())


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


class JsonOutTestleri(unittest.TestCase):
    """`--json-out`: bir tarama, tek gerçek.

    Bu bayrak eklenmeden önce GitHub Action aynı taramayı üç kez koşuyordu --
    bir kez JSON için, bir kez adım özeti için, bir kez de çıkış kodu için.
    Üç koşu ağ üzerinden bağlantı denetimi yaptığı için birbiriyle
    çelişebiliyordu: rapor "0 bulgu" derken üçüncü koşu kırmızı yanabilirdi.
    Yavaş olması ikincil; asıl sorun üç farklı cevabın mümkün olmasıydı.
    """

    def setUp(self):
        import tempfile
        self.dizin = tempfile.mkdtemp()
        self.yol = os.path.join(self.dizin, "rapor.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def test_dosyaya_yazarken_konsola_metin_basiyor(self):
        kod, cikti = _yamalali(_hatali(), ["o/r", "--json-out", self.yol])
        self.assertEqual(kod, 1)
        self.assertNotIn("{", cikti.split("\n")[0])
        with open(self.yol, encoding="utf-8") as f:
            veri = json.load(f)
        self.assertEqual(veri[0]["repository"], "o/r")
        self.assertEqual(veri[0]["finding_count"], 1)

    def test_markdown_ile_birlikte_calisiyor(self):
        kod, cikti = _yamalali(_hatali(), ["o/r", "--json-out", self.yol, "--markdown"])
        self.assertEqual(kod, 1)
        self.assertIn("#", cikti)
        with open(self.yol, encoding="utf-8") as f:
            self.assertEqual(json.load(f)[0]["finding_count"], 1)

    def test_cikis_kodu_ayni_taramadan_geliyor(self):
        """Dosyadaki sayı ile çıkış kodu aynı koşudan çıkmalı."""
        kod, _ = _yamalali(_hatali(), ["o/r", "--json-out", self.yol, "--fail-on", "none"])
        self.assertEqual(kod, 0)
        with open(self.yol, encoding="utf-8") as f:
            self.assertEqual(json.load(f)[0]["finding_count"], 1)

    def test_temiz_depoda_da_dosya_yaziliyor(self):
        r = Report("o/r", checked=["install"])
        kod, _ = _yamalali(r, ["o/r", "--json-out", self.yol])
        self.assertEqual(kod, 0)
        with open(self.yol, encoding="utf-8") as f:
            veri = json.load(f)
        self.assertEqual(veri[0]["finding_count"], 0)

    def test_yazilamayan_yol_sessizce_gecmiyor(self):
        hedef = os.path.join(self.dizin, "olmayan-klasor", "rapor.json")
        eski = io.StringIO()
        with contextlib.redirect_stderr(eski):
            kod, _ = _yamalali(_hatali(), ["o/r", "--json-out", hedef])
        self.assertEqual(kod, 2)
        self.assertIn("cannot write", eski.getvalue())

    def test_bayrak_verilmezse_hicbir_dosya_yazilmiyor(self):
        kod, _ = _yamalali(_hatali(), ["o/r"])
        self.assertEqual(kod, 1)
        self.assertFalse(os.path.exists(self.yol))
