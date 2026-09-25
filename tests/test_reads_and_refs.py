# -*- coding: utf-8 -*-
"""What was read, where it was read, and who got the token.

Four gaps these tests close, each of which let the tool say more than it saw:

- A README or manifest that timed out was reported as absent, and a release
  check that could not read the tags still counted as a check that ran.
- The README was always read on the default branch, so the Action run on a
  pull request vetted main, not the pull request.
- A slug such as `o/..` or `o/r?x=1` went into an API URL with the token.
- urllib forwards `Authorization` on a redirect to any host.
"""

import contextlib
import http.server
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakes import FakeClient                                  # noqa: E402
from repo_vet import cli                                      # noqa: E402
from repo_vet.model import Report                             # noqa: E402
from repo_vet.report import as_text                           # noqa: E402
from repo_vet.runner import vet                               # noqa: E402
from repo_vet.sources import Client                           # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = {"default_branch": "main", "homepage": ""}
SHA = "0123456789abcdef0123456789abcdef01234567"


def _http(kod):
    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, kod, "x", {}, None)
    return opener


def _skipped(rapor):
    return dict(rapor.skipped)


# -- unknown is not absent -------------------------------------------------


class UnreadableIsNotAbsent(unittest.TestCase):
    def test_readme_that_timed_out_is_not_a_missing_readme(self):
        c = FakeClient(repo=REPO, readme=None, tree=set())
        c.readme_known = False
        sebep = _skipped(vet("o/r", c))["readme"]
        self.assertIn("could not be read", sebep)
        self.assertNotIn("no README", sebep)

    def test_a_readme_that_is_really_absent_is_still_said_so(self):
        c = FakeClient(repo=REPO, readme=None, tree=set())
        self.assertIn("has no README", _skipped(vet("o/r", c))["readme"])

    def test_unreadable_manifest_moves_release_to_not_checked(self):
        c = FakeClient(repo=REPO, readme="x", tree={"README.md"})
        c.unknown_files = ("pyproject.toml",)
        r = vet("o/r", c, only={"release"})
        self.assertNotIn("release", r.checked)
        self.assertEqual(_skipped(r)["release"], "pyproject.toml could not be read")
        # Nothing that was asked for could be looked at: not clean, exit 3.
        self.assertNotIn("clean", as_text(r))
        self.assertTrue(r.unreadable)

    def test_unreadable_tags_move_release_to_not_checked(self):
        c = FakeClient(repo=REPO, readme="x", tree={"README.md"},
                       files={"pyproject.toml": 'version = "1.0.0"\n'})
        c._tags = None
        r = vet("o/r", c)
        self.assertNotIn("release", r.checked)
        self.assertIn("tag list could not be read", _skipped(r)["release"])
        # The other checks still ran and still count.
        self.assertIn("links", r.checked)

    def test_client_readme_tells_absent_from_unknown(self):
        self.assertEqual(Client(opener=_http(404)).readme("o/r"), (None, True))
        self.assertEqual(Client(opener=_http(503), sleep=lambda s: None)
                         .readme("o/r"), (None, False))

    def test_client_file_text_tells_absent_from_unknown(self):
        self.assertEqual(Client(opener=_http(404)).file_text("o/r", "p"), (None, True))
        self.assertEqual(Client(opener=_http(500), sleep=lambda s: None)
                         .file_text("o/r", "p"), (None, False))


# -- --ref -------------------------------------------------------------------


class ReadAtRef(unittest.TestCase):
    def _client(self):
        c = FakeClient(repo=REPO, readme="[x](docs/gone.md)", tree={"README.md"},
                       files={"pyproject.toml": 'version = "1.0.0"\n'},
                       tags=[{"name": "v1.0.0"}])
        c.refs = {"feature/x": SHA, SHA: SHA}
        return c

    def test_everything_is_read_at_the_resolved_commit(self):
        c = self._client()
        vet("o/r", c, ref="feature/x")
        self.assertIn("readme@" + SHA, c.asked)
        self.assertIn("tree@" + SHA, c.asked)
        self.assertIn("file:pyproject.toml@" + SHA, c.asked)
        self.assertFalse([a for a in c.asked if a.endswith("@main")])

    def test_evidence_names_the_ref_that_was_read(self):
        (f,) = vet("o/r", self._client(), ref="feature/x", only={"links"}).findings
        self.assertEqual(f.evidence, "o/r@feature/x has no such path")

    def test_a_commit_is_shown_short(self):
        (f,) = vet("o/r", self._client(), ref=SHA, only={"links"}).findings
        self.assertEqual(f.evidence, "o/r@%s has no such path" % SHA[:12])

    def test_without_ref_the_default_branch_is_read(self):
        c = self._client()
        vet("o/r", c)
        self.assertIn("readme@main", c.asked)

    def test_a_missing_ref_is_unreadable_not_a_repository_without_readme(self):
        r = vet("o/r", self._client(), ref="no-such-branch")
        self.assertTrue(r.unreadable)
        self.assertIn("no such branch, tag or commit: no-such-branch",
                      _skipped(r)["*"])

    def test_ref_that_could_not_be_resolved_is_unreadable(self):
        c = self._client()
        c.refs = None
        self.assertTrue(vet("o/r", c, ref="main").unreadable)

    def test_client_commit_sha(self):
        class Yanit(object):
            status = 200
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return (SHA + "\n").encode()

        istek = []

        def opener(req, timeout):
            istek.append(req)
            return Yanit()

        self.assertEqual(Client(opener=opener).commit_sha("o/r", "feature/x"), SHA)
        self.assertTrue(istek[0].full_url.endswith("/repos/o/r/commits/feature%2Fx"))
        self.assertEqual(istek[0].get_header("Accept"), "application/vnd.github.sha")
        self.assertEqual(Client(opener=_http(404)).commit_sha("o/r", "x"), "")
        self.assertEqual(Client(opener=_http(422)).commit_sha("o/r", "x"), "")
        self.assertIsNone(Client(opener=_http(503), sleep=lambda s: None)
                          .commit_sha("o/r", "x"))


# -- the command line refuses what would change the URL --------------------


def _kos(argv):
    goren = []
    eski_client, eski_vet = cli.Client, cli.vet
    cli.Client = lambda *a, **kw: None
    cli.vet = lambda slug, client, **kw: goren.append((slug, kw)) or Report(
        slug, checked=["links"])
    hata = io.StringIO()
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(hata):
            kod = cli.main(argv)
    finally:
        cli.Client, cli.vet = eski_client, eski_vet
    return kod, goren, hata.getvalue()


class Validation(unittest.TestCase):
    def test_slugs_that_would_rewrite_the_api_url_are_refused(self):
        for slug in ("o/..", "../r", "./r", "o/r?per_page=1", "o/r#x",
                     "o/r x", "o/%2e%2e", "o/r/contents", "/r", "o/"):
            kod, goren, hata = _kos([slug])
            self.assertEqual(kod, 2, slug)
            self.assertEqual(goren, [], slug)
            self.assertIn("not an OWNER/NAME slug", hata)

    def test_real_slugs_pass(self):
        for slug in ("psf/requests", "Furkiozknn/repo-vet", "a-b/c.d_e",
                     "sindresorhus/awesome", "o/.github"):
            self.assertEqual(_kos([slug])[0], 0, slug)

    def test_bad_refs_are_refused_before_any_scan(self):
        for ref in ("../x", "a..b", "a b", "-x", "/x", "x/", "a@{1}",
                    "a?b", "a#b", "a~1", "a^", "a:b", ""):
            kod, goren, _ = _kos(["o/r", "--ref=" + ref])
            self.assertEqual(kod, 2, ref)
            self.assertEqual(goren, [], ref)

    def test_good_refs_reach_the_scan(self):
        for ref in ("main", "feature/x", "v1.2.0", SHA, "release-1.x",
                    "dependabot/pip/foo-1.2"):
            kod, goren, _ = _kos(["o/r", "--ref=" + ref])
            self.assertEqual(kod, 0, ref)
            self.assertEqual(goren[0][1]["ref"], ref)

    def test_no_ref_means_none(self):
        self.assertIsNone(_kos(["o/r"])[1][0][1]["ref"])


# -- the token stays on its origin -----------------------------------------


class _Kaydeden(http.server.BaseHTTPRequestHandler):
    goruldu = None       # set per server
    hedef = None

    def do_GET(self):
        self.goruldu.append((self.path, self.headers.get("Authorization")))
        if self.path.startswith("/start") and self.hedef:
            self.send_response(302)
            self.send_header("Location", self.hedef)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


def _sunucu(goruldu, hedef=None):
    sinif = type("H", (_Kaydeden,), {"goruldu": goruldu, "hedef": hedef})
    s = http.server.HTTPServer(("127.0.0.1", 0), sinif)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


class TokenOnRedirect(unittest.TestCase):
    def _takip(self, ayni_koken):
        uzak = []
        yerel = []
        hedef_sunucu = _sunucu(uzak)
        self.addCleanup(hedef_sunucu.server_close)
        self.addCleanup(hedef_sunucu.shutdown)
        hedef_port = hedef_sunucu.server_address[1]
        if ayni_koken:
            kaynak = _sunucu(yerel)
            kaynak.RequestHandlerClass.hedef = "/landed"
        else:
            kaynak = _sunucu(yerel, "http://127.0.0.1:%d/landed" % hedef_port)
        self.addCleanup(kaynak.server_close)
        self.addCleanup(kaynak.shutdown)
        # No proxy for this: the request must reach 127.0.0.1 itself.
        with mock.patch.dict(os.environ, {"no_proxy": "*", "NO_PROXY": "*"}):
            c = Client(token="s3cret")
        c._fetch("http://127.0.0.1:%d/start" % kaynak.server_address[1], auth=True)
        return yerel, uzak

    def test_token_is_not_carried_to_another_origin(self):
        yerel, uzak = self._takip(ayni_koken=False)
        self.assertEqual(yerel, [("/start", "Bearer s3cret")])
        self.assertEqual(uzak, [("/landed", None)])

    def test_token_follows_a_redirect_on_the_same_origin(self):
        # A renamed repository redirects to another path on api.github.com;
        # that request still needs the token.
        yerel, _ = self._takip(ayni_koken=True)
        self.assertEqual(yerel, [("/start", "Bearer s3cret"),
                                 ("/landed", "Bearer s3cret")])


class Wording(unittest.TestCase):
    def test_one_check_is_singular(self):
        from repo_vet.report import as_markdown
        r = Report("o/r", checked=["links"])
        self.assertIn("clean (1 check)", as_text(r))
        self.assertIn("Clean. 1 check ran: links.", as_markdown(r))
        self.assertIn("clean (2 checks)", as_text(Report("o/r", checked=["a", "b"])))


# -- the Action's shell step --------------------------------------------------


def _action_yml():
    with open(os.path.join(KOK, "action.yml"), encoding="utf-8") as f:
        return f.read()


def _vet_betigi():
    """The `run:` block of the action's Vet step, as the runner would see it."""
    metin = _action_yml()
    blok = metin.split("- name: Vet", 1)[1].split("      run: |\n", 1)[1]
    satirlar = []
    for satir in blok.splitlines():
        if satir.strip() and not satir.startswith("        "):
            break
        satirlar.append(satir[8:])
    return "\n".join(satirlar) + "\n"


@unittest.skipUnless(shutil.which("bash"), "needs bash, as the Action does")
class ActionStep(unittest.TestCase):
    """Runs the Vet step under `bash -e`, as Actions does, with repo-vet
    replaced by a stub that records its arguments and exits with a chosen
    code."""

    def _kos(self, kod, **env):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        stub = os.path.join(d, "py")
        with open(stub, "w") as f:
            f.write('#!/usr/bin/env bash\n'
                    'if [ "$1" = "-c" ]; then exec %s "$@"; fi\n'
                    'printf "%%s\\n" "$@" > "$RUNNER_TEMP/args"\n'
                    'while [ $# -gt 0 ]; do\n'
                    '  if [ "$1" = "--json-out" ]; then\n'
                    '    echo \'[{"finding_count": 2}]\' > "$2"; fi\n'
                    '  shift; done\n'
                    'echo "### summary"\n'
                    'exit %d\n' % (sys.executable, kod))
        os.chmod(stub, 0o755)
        ortam = {"PATH": os.environ.get("PATH", ""), "RUNNER_TEMP": d,
                 "GITHUB_OUTPUT": os.path.join(d, "out"),
                 "GITHUB_STEP_SUMMARY": os.path.join(d, "summary"),
                 "RV_PY": stub, "RV_REPOSITORY": "o/r", "RV_ONLY": "",
                 "RV_SKIP": "", "RV_WEB_LIMIT": "40", "RV_FAIL_ON": "error",
                 "RV_REF": "", "GITHUB_REPOSITORY": "o/r", "GITHUB_SHA": SHA}
        ortam.update(env)
        p = subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail",
                            "-c", _vet_betigi()], env=ortam,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def oku(ad):
            yol = os.path.join(d, ad)
            if not os.path.exists(yol):
                return ""
            with open(yol) as f:
                return f.read()
        return p.returncode, oku("out"), oku("args").splitlines(), d

    def test_exit_code_passes_through_and_findings_are_written(self):
        for kod in (0, 1, 3):
            donen, cikti, _, d = self._kos(kod)
            self.assertEqual(donen, kod)
            self.assertIn("findings=2", cikti)
            self.assertIn("report=%s/repo-vet.json" % d, cikti)

    def test_own_repository_is_read_at_the_commit_under_test(self):
        _, _, args, _ = self._kos(0)
        self.assertEqual(args[args.index("--ref") + 1], SHA)

    def test_another_repository_is_read_on_its_default_branch(self):
        _, _, args, _ = self._kos(0, RV_REPOSITORY="other/repo")
        self.assertNotIn("--ref", args)

    def test_explicit_ref_wins(self):
        _, _, args, _ = self._kos(0, RV_REF="v1.0.0")
        self.assertEqual(args[args.index("--ref") + 1], "v1.0.0")

    def test_inputs_are_arguments_not_shell_code(self):
        _, _, args, d = self._kos(0, RV_SKIP='web"; touch pwned; echo "')
        self.assertIn('web"; touch pwned; echo "', args)
        self.assertFalse(os.path.exists(os.path.join(d, "pwned")))
        self.assertFalse(os.path.exists("pwned"))

    def test_no_report_means_no_count(self):
        # Bad usage (exit 2) writes no file: the step fails and invents no count.
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        stub = os.path.join(d, "py")
        with open(stub, "w") as f:
            f.write("#!/usr/bin/env bash\nexit 2\n")
        os.chmod(stub, 0o755)
        donen, cikti, _, _ = self._kos(2, RV_PY=stub)
        self.assertEqual(donen, 2)
        self.assertNotIn("findings=", cikti)

    def test_no_input_is_substituted_into_a_script(self):
        # `${{ inputs.x }}` inside `run:` is pasted into the script as code.
        metin = _action_yml()
        for blok in re.findall(r"run: \|\n((?:        .*\n|\n)+)", metin):
            self.assertNotIn("${{", blok)


if __name__ == "__main__":                                # pragma: no cover
    unittest.main(verbosity=2)
