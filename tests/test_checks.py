# -*- coding: utf-8 -*-
"""Each check, against a client that answers from a dictionary.

Several of these encode a repository that proved an earlier, more general
rule wrong. Those are named where they appear.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakes import FakeClient                                  # noqa: E402
from repo_vet import checks                                   # noqa: E402
from repo_vet.model import HATA, UYARI                        # noqa: E402


def blok(*satirlar):
    return "```bash\n" + "\n".join(satirlar) + "\n```"


def ctx(text="", tree=None, meta=None, truncated=False, **kw):
    return checks.Context("o/r", FakeClient(**kw), meta=meta or {},
                          text=text, tree=tree, tree_truncated=truncated)


class Install(unittest.TestCase):
    def test_missing_distribution_is_an_error(self):
        c = ctx(blok("pip install ghost-pkg"), pypi={})
        (f,) = checks.check_install(c)
        self.assertEqual(f.check, "install")
        self.assertEqual(f.level, HATA)
        self.assertIn("ghost-pkg", f.message)
        self.assertIn("404", f.evidence)

    def test_published_distribution_is_quiet(self):
        c = ctx(blok("pip install real-pkg"), pypi={"real-pkg": ["1.0"]})
        self.assertEqual(checks.check_install(c), [])

    def test_unanswerable_registry_says_nothing(self):
        # A rate limit or a network blip must not look like "unpublished".
        # This is the difference between a linter people trust and one they
        # switch off after the first false accusation.
        c = ctx(blok("pip install real-pkg"), pypi={"real-pkg": None})
        self.assertEqual(checks.check_install(c), [])

    def test_npm_side(self):
        c = ctx(blok("npm install ghost"), npm={})
        (f,) = checks.check_install(c)
        self.assertIn("npm", f.message)

    def test_npm_unanswerable(self):
        c = ctx(blok("npm install x"), npm={"x": None})
        self.assertEqual(checks.check_install(c), [])

    def test_unpublished_cargo_crate_is_an_error(self):
        c = ctx(blok("cargo install ghost-crate"), cargo={})
        (f,) = checks.check_install(c)
        self.assertEqual(f.check, "install")
        self.assertEqual(f.level, HATA)
        self.assertIn("ghost-crate", f.message)
        self.assertIn("crates.io", f.evidence)

    def test_published_cargo_crate_is_quiet(self):
        c = ctx(blok("cargo install serde"), cargo={"serde": ["1.0.0"]})
        self.assertEqual(checks.check_install(c), [])

    def test_unanswerable_cargo_registry_is_not_missing(self):
        c = ctx(blok("cargo install serde"), cargo={"serde": None})
        self.assertEqual(checks.check_install(c), [])

    def test_git_and_path_installs_are_not_checked_against_crates_io(self):
        c = ctx(blok(
            "cargo install --git https://github.com/o/r unpublished",
            "cargo install --path ./local-crate"), cargo={})
        self.assertEqual(checks.check_install(c), [])

    def test_nothing_to_install_is_quiet(self):
        self.assertEqual(checks.check_install(ctx("no code here")), [])


class Links(unittest.TestCase):
    def test_missing_file_is_an_error(self):
        c = ctx("[guide](docs/guide.md)", tree={"README.md"})
        (f,) = checks.check_links(c)
        self.assertEqual(f.level, HATA)
        self.assertIn("docs/guide.md", f.message)

    def test_missing_route_is_only_a_warning(self):
        # tiangolo/fastapi links to `tutorial/`, a route on its documentation
        # site. On GitHub it 404s, which is worth saying — and not worth
        # failing anyone's build over.
        c = ctx("[installation guide](tutorial/#install)", tree={"README.md"})
        (f,) = checks.check_links(c)
        self.assertEqual(f.level, UYARI)
        self.assertIn("tutorial/", f.message)

    def test_present_file(self):
        c = ctx("[guide](docs/guide.md)", tree={"docs/guide.md"})
        self.assertEqual(checks.check_links(c), [])

    def test_directory_link_counts_if_anything_is_under_it(self):
        c = ctx("[dir](examples/)", tree={"examples/a.yaml"})
        self.assertEqual(checks.check_links(c), [])

    def test_percent_encoded_target(self):
        c = ctx("[x](docs/my%20guide.md)", tree={"docs/my guide.md"})
        self.assertEqual(checks.check_links(c), [])

    def test_parent_directory_is_out_of_scope(self):
        c = ctx("[x](../other/file.md)", tree={"README.md"})
        self.assertEqual(checks.check_links(c), [])

    def test_links_inside_code_blocks_are_examples(self):
        c = ctx(blok("[see](docs/never-existed.md)"), tree={"README.md"})
        self.assertEqual(checks.check_links(c), [])

    def test_truncated_tree_means_no_opinion(self):
        # torvalds/linux: GitHub returns 71,638 paths and a flag saying there
        # are more. Judging links against a partial tree invents findings.
        c = ctx("[x](docs/guide.md)", tree={"README.md"}, truncated=True)
        self.assertEqual(checks.check_links(c), [])

    def test_no_tree_means_no_opinion(self):
        c = ctx("[guide](docs/guide.md)", tree=None)
        self.assertEqual(checks.check_links(c), [])


class Badges(unittest.TestCase):
    ROZET = "![CI](https://github.com/o/r/actions/workflows/%s/badge.svg)"

    def test_badge_for_missing_workflow(self):
        # axios/axios shows a badge for `ci.yml`; the workflow is `run-ci.yml`.
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

    def test_truncated_tree_means_no_opinion(self):
        c = ctx(self.ROZET % "ci.yml", tree={"README.md"}, truncated=True)
        self.assertEqual(checks.check_badges(c), [])


class Release(unittest.TestCase):
    PY = '[project]\nversion = "1.2.0"\n'

    def test_never_tagged_means_never_shipped(self):
        c = ctx(files={"pyproject.toml": self.PY})
        (f,) = checks.check_release(c)
        self.assertIn("1.2.0", f.message)
        self.assertIn("never been tagged", f.message)

    def test_between_releases_is_not_a_finding(self):
        # pallets/flask says 3.2.0.dev, astral-sh/ruff says 0.16.8,
        # prettier says 3.10.0-dev. A repository declaring the version it is
        # working towards is not broken; it is Tuesday. An earlier version
        # of this check reported all three.
        for surum in ("3.2.0.dev", "3.10.0-dev", "2.0.0rc1", "1.0.0-beta.2"):
            c = ctx(files={"pyproject.toml": '[project]\nversion = "%s"\n' % surum})
            self.assertEqual(checks.check_release(c), [], surum)

    def test_declared_version_not_yet_tagged_is_not_a_finding(self):
        c = ctx(files={"pyproject.toml": self.PY},
                tags=[{"name": "v1.1.0"}, {"name": "v1.0.0"}])
        self.assertEqual(checks.check_release(c), [])

    def test_matching_tag_with_release_is_quiet(self):
        c = ctx(files={"pyproject.toml": self.PY}, tags=[{"name": "v1.2.0"}],
                releases=[{"tag_name": "v1.2.0"}])
        self.assertEqual(checks.check_release(c), [])

    def test_matching_tag_without_release_while_others_have_one(self):
        c = ctx(files={"pyproject.toml": self.PY},
                tags=[{"name": "v1.2.0"}, {"name": "v1.1.0"}],
                releases=[{"tag_name": "v1.1.0"}])
        (f,) = checks.check_release(c)
        self.assertIn("v1.2.0", f.message)
        self.assertEqual(f.level, UYARI)

    def test_project_that_never_uses_releases_is_left_alone(self):
        # A repository that tags but publishes no Releases has made a choice.
        # torvalds/linux is the obvious one.
        c = ctx(files={"pyproject.toml": self.PY}, tags=[{"name": "v1.2.0"}],
                releases=[])
        self.assertEqual(checks.check_release(c), [])

    def test_monorepo_style_tag_counts(self):
        # sveltejs/svelte tags `svelte@5.53.12`; matching on the bare version
        # alone would have missed it.
        c = ctx(files={"package.json": '{"version": "5.53.12"}'},
                tags=[{"name": "svelte@5.53.12"}],
                releases=[{"tag_name": "svelte@5.53.12"}])
        self.assertEqual(checks.check_release(c), [])

    def test_no_declared_version_no_opinion(self):
        c = ctx(tags=[{"name": "v7.3-rc4"}], releases=[])
        self.assertEqual(checks.check_release(c), [])

    def test_package_json_placeholder_is_not_a_declaration(self):
        c = ctx(files={"package.json": '{"version": "0.0.0"}'})
        self.assertEqual(checks.check_release(c), [])

    def test_draft_release_does_not_count(self):
        c = ctx(files={"pyproject.toml": self.PY},
                tags=[{"name": "v1.2.0"}, {"name": "v1.1.0"}],
                releases=[{"tag_name": "v1.2.0", "draft": True},
                          {"tag_name": "v1.1.0"}])
        self.assertTrue(checks.check_release(c))


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

    def test_links_in_code_blocks_are_not_probed(self):
        c = ctx(blok("[x](https://example.com/sample)"),
                statuses={"https://example.com/sample": 404})
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

    def test_homepage_behind_a_login_is_not_dead(self):
        c = ctx(meta={"homepage": "https://x.test/"},
                statuses={"https://x.test/": 403})
        self.assertEqual(checks.check_pages(c), [])

    def test_live_homepage_is_quiet(self):
        c = ctx(meta={"homepage": "https://x.test/"},
                statuses={"https://x.test/": 200})
        self.assertEqual(checks.check_pages(c), [])

    def test_unadvertised_site(self):
        # sindresorhus/awesome: the Pages site is live, the homepage field
        # is empty, and nobody landing on the repository is told.
        c = ctx(meta={}, statuses={"https://o.github.io/r/": 200})
        (f,) = checks.check_pages(c)
        self.assertEqual(f.level, UYARI)
        self.assertIn("no homepage", f.message)

    def test_no_site_no_finding(self):
        c = ctx(meta={}, statuses={"https://o.github.io/r/": 404})
        self.assertEqual(checks.check_pages(c), [])


if __name__ == "__main__":                                # pragma: no cover
    unittest.main(verbosity=2)
