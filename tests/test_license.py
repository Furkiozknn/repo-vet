# -*- coding: utf-8 -*-
"""The licence check: manifest, README badge and LICENSE file must agree.

The check compares licence *families*, so the many spellings of one licence
("Apache-2.0", "Apache 2.0", "Apache Software License") never disagree with
each other, and only claims that actually contradict one another are raised.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakes import FakeClient                                  # noqa: E402
from repo_vet import checks, readme                           # noqa: E402
from repo_vet.model import HATA, UYARI                        # noqa: E402
from repo_vet.runner import vet                               # noqa: E402

MIT = {"key": "mit", "spdx_id": "MIT", "name": "MIT License"}
APACHE = {"key": "apache-2.0", "spdx_id": "Apache-2.0", "name": "Apache License 2.0"}
BELIRSIZ = {"key": "other", "spdx_id": "NOASSERTION", "name": "Other"}


def pyproject(license_line="", classifiers=()):
    siniflar = "".join('  "License :: OSI Approved :: %s",\n' % c for c in classifiers)
    return ('[project]\nname = "x"\nversion = "1.0"\n%s\nclassifiers = [\n%s]\n'
            % (license_line, siniflar))


def ctx(license=MIT, files=None, text="", tree=("LICENSE", "README.md")):
    meta = {"default_branch": "main", "license": license}
    return checks.Context("o/r", FakeClient(files=files or {}), meta=meta, text=text,
                          tree=set(tree) if tree is not None else None)


class Families(unittest.TestCase):
    def test_spellings_of_one_licence_are_one_family(self):
        for ad in ("Apache-2.0", "Apache 2.0", "Apache Software License",
                   "Apache License, Version 2.0"):
            self.assertEqual(checks.licence_family(ad), "apache", ad)
        self.assertEqual(checks.licence_family("MIT License"), "mit")
        self.assertEqual(checks.licence_family("BSD-3-Clause"), "bsd")

    def test_lgpl_and_agpl_are_not_gpl(self):
        self.assertEqual(checks.licence_family("LGPL-3.0-or-later"), "lgpl")
        self.assertEqual(checks.licence_family("GNU Lesser General Public License v3"), "lgpl")
        self.assertEqual(checks.licence_family("AGPL-3.0"), "agpl")
        self.assertEqual(checks.licence_family("GNU General Public License v3 (GPLv3)"), "gpl")

    def test_unknown_names_are_not_judged(self):
        for ad in ("NOASSERTION", "LicenseRef-Proprietary", "Other/Proprietary License",
                   "Public Domain", "", None):
            self.assertIsNone(checks.licence_family(ad), ad)

    def test_an_expression_allows_each_of_its_families(self):
        self.assertEqual(checks.licence_families("MIT OR Apache-2.0"), {"mit", "apache"})
        self.assertEqual(checks.licence_families("(MIT OR Apache-2.0)"), {"mit", "apache"})
        self.assertEqual(checks.licence_families("Apache-2.0 WITH LLVM-exception"), {"apache"})
        self.assertEqual(checks.licence_families("MIT/Apache-2.0"), {"mit", "apache"})
        self.assertIsNone(checks.licence_families("MIT OR LicenseRef-Mine"))


class Badges(unittest.TestCase):
    def test_static_licence_badges_are_read(self):
        t = ("[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) "
             "![l](https://img.shields.io/badge/License-Apache%202.0-blue.svg) "
             "![d](https://img.shields.io/badge/licence-MIT%20OR%20Apache--2.0-blue)")
        self.assertEqual(readme.licence_badges(t),
                         {"MIT", "Apache 2.0", "MIT OR Apache-2.0"})

    def test_other_badges_and_dynamic_licence_badges_are_ignored(self):
        t = ("![py](https://img.shields.io/badge/python-3.9%2B-blue) "
             "![l](https://img.shields.io/github/license/o/r)")
        self.assertEqual(readme.licence_badges(t), set())


class CheckLicense(unittest.TestCase):
    def test_agreeing_claims_are_quiet(self):
        # This repository's own shape: MIT file, MIT in pyproject (table form
        # and classifier), MIT badge.
        c = ctx(MIT, files={"pyproject.toml": pyproject('license = { text = "MIT" }',
                                                        ["MIT License"])},
                text="![l](https://img.shields.io/badge/license-MIT-green)")
        self.assertEqual(checks.check_license(c), [])

    def test_manifest_naming_another_family_is_an_error(self):
        c = ctx(APACHE, files={"pyproject.toml": pyproject('license = "MIT"')})
        (f,) = checks.check_license(c)
        self.assertEqual((f.check, f.level), ("license", HATA))
        self.assertIn("pyproject.toml", f.message)
        self.assertIn("Apache-2.0", f.evidence)

    def test_classifier_naming_another_family_is_an_error(self):
        c = ctx(MIT, files={"pyproject.toml": pyproject(classifiers=["Apache Software License"])})
        (f,) = checks.check_license(c)
        self.assertIn("classifier", f.message)

    def test_package_json_and_cargo_toml_are_read(self):
        c = ctx(MIT, files={
            "package.json": json.dumps({"name": "x", "license": "ISC"}),
            "Cargo.toml": '[package]\nname = "x"\nlicense = "GPL-3.0-only"\n',
        })
        kaynaklar = sorted(f.message.split("`")[1] for f in checks.check_license(c))
        self.assertEqual(kaynaklar, ["Cargo.toml", "package.json"])

    def test_dual_licence_with_one_detected_file_is_quiet(self):
        c = ctx(APACHE, files={"Cargo.toml": '[package]\nlicense = "MIT OR Apache-2.0"\n'})
        self.assertEqual(checks.check_license(c), [])

    def test_a_licence_github_cannot_identify_is_not_judged(self):
        # Two LICENSE files, or an edited text: GitHub says NOASSERTION.
        c = ctx(BELIRSIZ, files={"pyproject.toml": pyproject('license = "MIT"')},
                text="![l](https://img.shields.io/badge/license-GPL-red)")
        self.assertEqual(checks.check_license(c), [])

    def test_badge_naming_another_family_is_an_error(self):
        c = ctx(MIT, text="![l](https://img.shields.io/badge/license-Apache%202.0-blue)")
        (f,) = checks.check_license(c)
        self.assertIn("badge", f.message)
        self.assertEqual(f.level, HATA)

    def test_dual_licence_badges_and_files_are_quiet(self):
        # clap-rs/clap: one badge and one LICENSE file per licence, and GitHub
        # detects only Apache-2.0. Judging each badge on its own called the
        # MIT badge wrong; this is the corpus run that showed it.
        c = ctx(APACHE, tree=("LICENSE-APACHE", "LICENSE-MIT", "README.md"),
                files={"Cargo.toml": '[package]\nlicense = "MIT"\n'},
                text="![l](https://img.shields.io/badge/license-Apache%202.0-blue) "
                     "![l](https://img.shields.io/badge/license-MIT-blue)")
        self.assertEqual(checks.check_license(c), [])

    def test_a_licence_file_named_for_another_licence_does_not_excuse_a_mismatch(self):
        c = ctx(APACHE, tree=("LICENSE-APACHE", "README.md"),
                files={"Cargo.toml": '[package]\nlicense = "MIT"\n'})
        (f,) = checks.check_license(c)
        self.assertIn("Cargo.toml", f.message)

    def test_declared_licence_without_any_licence_file_is_a_warning(self):
        c = ctx(None, files={"pyproject.toml": pyproject('license = "MIT"')},
                tree=("README.md", "src/x.py"))
        (f,) = checks.check_license(c)
        self.assertEqual(f.level, UYARI)
        self.assertIn("no licence file", f.message)

    def test_a_licence_file_github_did_not_recognise_still_counts_as_a_file(self):
        c = ctx(None, files={"pyproject.toml": pyproject('license = "MIT"')},
                tree=("LICENSE.md", "README.md"))
        self.assertEqual(checks.check_license(c), [])

    def test_an_unreadable_tree_never_claims_the_file_is_missing(self):
        c = ctx(None, files={"pyproject.toml": pyproject('license = "MIT"')}, tree=None)
        self.assertEqual(checks.check_license(c), [])

    def test_a_licence_field_outside_the_project_table_is_not_the_projects(self):
        metin = '[project]\nname = "x"\n\n[tool.other]\nlicense = "GPL-3.0"\n'
        c = ctx(MIT, files={"pyproject.toml": metin})
        self.assertEqual(checks.check_license(c), [])

    def test_missing_licence_field_in_metadata_is_not_checked(self):
        c = checks.Context("o/r", FakeClient(), meta={"default_branch": "main"})
        with self.assertRaises(checks.NotChecked):
            checks.check_license(c)

    def test_runs_as_part_of_a_full_vet(self):
        c = FakeClient(repo={"default_branch": "main", "license": APACHE},
                       readme="# x\n", tree={"LICENSE", "README.md"},
                       files={"pyproject.toml": pyproject('license = "MIT"')})
        r = vet("o/r", c, only={"license"})
        self.assertEqual(r.checked, ["license"])
        self.assertEqual([f.check for f in r.errors], ["license"])


if __name__ == "__main__":
    unittest.main()
