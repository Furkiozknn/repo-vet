# -*- coding: utf-8 -*-
"""Running the checks, and saying what happened."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakes import FakeClient                                  # noqa: E402
from repo_vet.model import Finding, Report, HATA, UYARI       # noqa: E402
from repo_vet.report import as_markdown, as_text              # noqa: E402
from repo_vet.runner import vet                               # noqa: E402

REPO = {"default_branch": "main", "homepage": ""}


class Runner(unittest.TestCase):
    def test_missing_repository_reports_nothing_as_clean(self):
        # The failure mode worth guarding: an audit that says "clean"
        # about something it could not see.
        r = vet("o/r", FakeClient(repo=None))
        self.assertEqual(r.findings, [])
        self.assertEqual(r.checked, [])
        self.assertEqual(r.skipped[0][0], "*")

    def test_no_readme_skips_the_readme_checks(self):
        r = vet("o/r", FakeClient(repo=REPO, readme=None, tree=set()))
        atlanan = dict(r.skipped)
        for ad in ("install", "links", "badges", "web"):
            self.assertIn(ad, atlanan)
        self.assertIn("release", r.checked)

    def test_only_and_skip(self):
        c = FakeClient(repo=REPO, readme="x", tree=set())
        self.assertEqual(vet("o/r", c, only={"release"}).checked, ["release"])
        r = vet("o/r", c, skip={"web"})
        self.assertNotIn("web", r.checked)
        self.assertIn(("web", "skipped on request"), r.skipped)

    def test_a_real_finding_flows_through(self):
        c = FakeClient(repo=REPO, readme="```bash\npip install ghost\n```",
                       tree=set(), pypi={})
        r = vet("o/r", c, only={"install"})
        self.assertEqual(len(r.errors), 1)
        self.assertEqual(r.as_dict()["error_count"], 1)


class Output(unittest.TestCase):
    def _rapor(self):
        r = Report("o/r", checked=["install", "links"])
        r.add(Finding("install", "thing is missing", "pypi -> not found"))
        r.add(Finding("pages", "site is quiet", "HTTP 200", UYARI))
        return r

    def test_text_names_repo_and_counts(self):
        m = as_text(self._rapor())
        self.assertIn("o/r", m)
        self.assertIn("2 findings", m)
        self.assertIn("thing is missing", m)
        self.assertIn("pypi -> not found", m)

    def test_text_when_clean(self):
        m = as_text(Report("o/r", checked=["install"]))
        self.assertIn("clean", m)

    def test_markdown_is_a_table(self):
        m = as_markdown(self._rapor())
        self.assertIn("| error |", m)
        self.assertIn("| warn |", m)
        self.assertIn("`pypi -> not found`", m)

    def test_markdown_when_clean_is_one_line(self):
        m = as_markdown(Report("o/r", checked=["install", "links"]))
        self.assertIn("Clean.", m)
        self.assertNotIn("|---|", m)

    def test_pipes_in_evidence_do_not_break_the_table(self):
        r = Report("o/r")
        r.add(Finding("web", "a | b", "x | y"))
        self.assertNotIn("| a | b |", as_markdown(r))

    def test_json_round_trips(self):
        d = json.loads(self._rapor().as_json())
        self.assertEqual(d["repository"], "o/r")
        self.assertEqual(d["finding_count"], 2)
        self.assertEqual(d["error_count"], 1)
        self.assertEqual(d["findings"][0]["level"], HATA)


if __name__ == "__main__":                                # pragma: no cover
    unittest.main(verbosity=2)
