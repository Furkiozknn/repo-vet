# -*- coding: utf-8 -*-
"""Each check, against a client that answers from a dictionary."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakes import FakeClient                                  # noqa: E402
from repo_vet import checks                                   # noqa: E402
from repo_vet.model import HATA, UYARI                        # noqa: E402


def blok(*satirlar):
    return "```bash\n" + "\n".join(satirlar) + "\n```"


def ctx(text="", tree=None, meta=None, **kw):
    return checks.Context("o/r", FakeClient(**kw), meta=meta or {},
                          text=text, tree=tree)


class Install(unittest.TestCase):
    def test_missing_distribution_is_an_error(self):
        c = ctx(blok("pip install ghost-pkg"), pypi={})
        (f,) = checks.check_install(c)
        self.assertEqual(f.check, "install")
        self.assertEqual(f.level, HATA)
        self.assertIn("ghost-pkg", f.message)
        self.assertIn("not found", f.evidence)

    def test_published_distribution_is_quiet(self):
        c = ctx(blok("pip install real-pkg"), pypi={"real-pkg": ["1.0"]})
        self.assertEqual(checks.check_install(c), [])

    def test_npm_side(self):
        c = ctx(blok("npm install ghost"), npm={})
        (f,) = checks.check_install(c)
        self.assertIn("npm", f.message)

    def test_nothing_to_install_is_quiet(self):
        self.assertEqual(checks.check_install(ctx("no code here")), [])


class Links(unittest.TestCase):
    def test_missing_file(self):
        c = ctx("[guide](docs/guide.md)", tree={"README.md"})
        (f,) = checks.check_links(c)
        self.assertIn("docs/guide.md", f.message)

    def test_present_file(self):
        c = ctx("[guide](docs/guide.md)", tree={"docs/guide.md"})
        self.assertEqual(checks.check_links(c), [])

    def test_directory_link_counts_if_anything_is_under_it(self):
        c = ctx("[dir](examples/)", tree={"examples/a.yaml"})
        self.assertEqual(checks.check_links(c), [])

    def test_no_tree_means_no_opinion(self):
        c = ctx("[guide](docs/guide.md)", tree=None)
        self.assertEqual(checks.check_links(c), [])


class Badges(unittest.TestCase):
    ROZET = ("![CI](https://github.com/o/r/actions/workflows/%s/badge.svg)")

    def test_badge_for_missing_workflow(self):
        c = ctx(self.ROZET % "ci.yml", tree={"README.md"})
        (f,) = checks.check_badges(c)
        self.assertEqual(f.level, HATA)
        self.assertIn("ci.yml", f.message)

    def test_badge_for_workflow_that_never_ran(self):
        c = ctx(self.ROZET % "ci.yml", tree={".github/workflows/ci.yml"},
                runs={"ci.yml": 0})
        (f,) = checks.check_badges(c)
        self.assertEqual(f.level, UYARI)
        self.assertIn("no status", f.message)

    def test_healthy_badge(self):
        c = ctx(self.ROZET % "ci.yml", tree={".github/workflows/ci.yml"},
                runs={"ci.yml": 12})
        self.assertEqual(checks.check_badges(c), [])

    def test_badge_pointing_at_another_repository(self):
        metin = "![x](https://github.com/someone/else/actions/workflows/ci.yml/badge.svg)"
        c = ctx(metin, tree={"README.md"})
        self.assertEqual(checks.check_badges(c), [])


class Release(unittest.TestCase):
    def test_newest_tag_without_release(self):
        c = ctx(tags=[{"name": "v2.0"}, {"name": "v1.0"}],
                releases=[{"tag_name": "v1.0"}])
        bulgular = checks.check_release(c)
        self.assertTrue(any("v2.0" in f.message for f in bulgular))

    def test_older_tags_without_releases_are_not_reported(self):
        c = ctx(tags=[{"name": "v2.0"}, {"name": "v1.0"}],
                releases=[{"tag_name": "v2.0"}])
        self.assertEqual(checks.check_release(c), [])

    def test_draft_release_does_not_count(self):
        c = ctx(tags=[{"name": "v1.0"}],
                releases=[{"tag_name": "v1.0", "draft": True}])
        self.assertTrue(checks.check_release(c))

    def test_declared_version_without_any_tag(self):
        c = ctx(files={"pyproject.toml": '[project]\nversion = "0.3.0"\n'})
        bulgular = checks.check_release(c)
        self.assertTrue(any("0.3.0" in f.message for f in bulgular))

    def test_package_json_placeholder_is_not_a_declaration(self):
        c = ctx(files={"package.json": '{"version": "0.0.0"}'})
        self.assertEqual(checks.check_release(c), [])


class Web(unittest.TestCase):
    def test_404_is_reported(self):
        c = ctx("[x](https://example.com/gone)",
                statuses={"https://example.com/gone": 404})
        (f,) = checks.check_web(c)
        self.assertIn("404", f.evidence)

    def test_403_is_a_closed_door_not_a_dead_link(self):
        c = ctx("[x](https://example.com/robot)",
                statuses={"https://example.com/robot": 403})
        self.assertEqual(checks.check_web(c), [])

    def test_unreachable_is_not_reported(self):
        c = ctx("[x](https://example.com/x)", statuses={})
        self.assertEqual(checks.check_web(c), [])

    def test_limit_is_respected(self):
        metin = " ".join("[l](https://example.com/%d)" % i for i in range(10))
        c = ctx(metin, statuses=dict(("https://example.com/%d" % i, 404)
                                     for i in range(10)))
        self.assertEqual(len(checks.check_web(c, limit=3)), 3)


class Pages(unittest.TestCase):
    def test_dead_homepage(self):
        c = ctx(meta={"homepage": "https://x.test/"},
                statuses={"https://x.test/": 404})
        (f,) = checks.check_pages(c)
        self.assertEqual(f.level, HATA)

    def test_live_homepage_is_quiet(self):
        c = ctx(meta={"homepage": "https://x.test/"},
                statuses={"https://x.test/": 200})
        self.assertEqual(checks.check_pages(c), [])

    def test_unadvertised_site(self):
        c = ctx(meta={}, statuses={"https://o.github.io/r/": 200})
        (f,) = checks.check_pages(c)
        self.assertEqual(f.level, UYARI)
        self.assertIn("no homepage", f.message)

    def test_no_site_no_finding(self):
        c = ctx(meta={}, statuses={"https://o.github.io/r/": 404})
        self.assertEqual(checks.check_pages(c), [])


if __name__ == "__main__":                                # pragma: no cover
    unittest.main(verbosity=2)
