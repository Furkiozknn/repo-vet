# -*- coding: utf-8 -*-
"""Reading a README: what it asks you to run, and what it merely mentions."""

import unittest

from repo_vet import readme as md


def blok(*satirlar):
    return "```bash\n" + "\n".join(satirlar) + "\n```"


class CodeBlocks(unittest.TestCase):
    def test_only_fenced_text(self):
        metin = "before\n" + blok("echo hi") + "\nafter"
        self.assertIn("echo hi", md.code_blocks(metin))
        self.assertNotIn("before", md.code_blocks(metin))
        self.assertNotIn("after", md.code_blocks(metin))

    def test_language_tag_is_not_content(self):
        self.assertEqual(md.code_blocks("```python\nx = 1\n```").strip(), "x = 1")

    def test_several_blocks(self):
        metin = blok("a") + "\ntext\n" + blok("b")
        self.assertIn("a", md.code_blocks(metin))
        self.assertIn("b", md.code_blocks(metin))

    def test_empty(self):
        self.assertEqual(md.code_blocks(""), "")
        self.assertEqual(md.code_blocks(None), "")


class PypiInstalls(unittest.TestCase):
    def test_plain_forms(self):
        self.assertEqual(md.pypi_installs(blok("pip install requests")), {"requests"})
        self.assertEqual(md.pypi_installs(blok("pipx install black")), {"black"})
        self.assertEqual(md.pypi_installs(blok("uv tool install ptm-cli")), {"ptm-cli"})
        self.assertEqual(md.pypi_installs(blok("uvx cowsay")), {"cowsay"})

    def test_prose_is_not_an_instruction(self):
        # The distinction the whole tool rests on: a sentence discussing a
        # command is not the same as a block asking you to run it.
        prose = "Once published, `pip install thing` will be the short route."
        self.assertEqual(md.pypi_installs(prose), set())
        self.assertEqual(md.pypi_installs(prose + "\n" + blok("pip install real")),
                         {"real"})

    def test_git_url_is_not_a_distribution(self):
        self.assertEqual(md.pypi_installs(
            blok("uv tool install git+https://github.com/o/r")), set())

    def test_from_form_names_its_distribution_elsewhere(self):
        self.assertEqual(md.pypi_installs(
            blok("uvx --from git+https://github.com/o/r cmd --help")), set())

    def test_local_installs_are_not_registry_names(self):
        self.assertEqual(md.pypi_installs(blok("pip install -e .")), set())
        self.assertEqual(md.pypi_installs(blok("pip install -r requirements.txt")),
                         set())
        self.assertEqual(md.pypi_installs(blok("pip install ./dist/x.whl")), set())

    def test_flags_are_not_packages(self):
        self.assertEqual(md.pypi_installs(blok("uv pip install --system pyyaml")),
                         {"pyyaml"})
        self.assertEqual(md.pypi_installs(blok("pip install --upgrade httpx")),
                         {"httpx"})

    def test_version_pin_keeps_the_name(self):
        self.assertEqual(md.pypi_installs(blok("pip install requests==2.31.0")),
                         {"requests"})
        self.assertEqual(md.pypi_installs(blok("pip install 'ruff>=0.5'")), {"ruff"})

    def test_extras_resolve_to_the_base_name(self):
        # PyPI knows `fastapi`, not `fastapi[all]`. Asking it about the
        # bracketed form would invent a missing distribution.
        self.assertEqual(md.pypi_installs(blok("pip install fastapi[all]")),
                         {"fastapi"})


class NpmInstalls(unittest.TestCase):
    def test_plain_forms(self):
        self.assertEqual(md.npm_installs(blok("npm install left-pad")), {"left-pad"})
        self.assertEqual(md.npm_installs(blok("npx serve")), {"serve"})
        self.assertEqual(md.npm_installs(blok("pnpm add vite")), {"vite"})
        self.assertEqual(md.npm_installs(blok("yarn add typescript")), {"typescript"})

    def test_scoped_package(self):
        self.assertEqual(md.npm_installs(blok("npm i @scope/pkg")), {"@scope/pkg"})

    def test_flags_and_paths(self):
        self.assertEqual(md.npm_installs(blok("npm install -D eslint")), {"eslint"})
        self.assertEqual(md.npm_installs(blok("npm install ./local")), set())


class LocalTargets(unittest.TestCase):
    def test_relative_links_and_images(self):
        metin = ("[docs](docs/guide.md) ![shot](assets/a.png) "
                 '<img src="assets/b.svg"> [ext](https://example.com)')
        self.assertEqual(md.local_targets(metin),
                         {"docs/guide.md", "assets/a.png", "assets/b.svg"})

    def test_anchors_and_queries_are_stripped(self):
        self.assertEqual(md.local_targets("[x](README.md#usage)"), {"README.md"})
        self.assertEqual(md.local_targets("[x](a/b.md?plain=1)"), {"a/b.md"})

    def test_in_page_anchor_is_not_a_file(self):
        self.assertEqual(md.local_targets("[x](#quickstart)"), set())

    def test_leading_dot_slash_is_normalised(self):
        self.assertEqual(md.local_targets("[x](./LICENSE)"), {"LICENSE"})

    def test_absolute_paths_are_left_alone(self):
        self.assertEqual(md.local_targets("[x](/etc/passwd)"), set())


class ExternalLinks(unittest.TestCase):
    def test_found(self):
        metin = "[a](https://example.com/x) ![b](http://img.test/y.png)"
        self.assertEqual(md.external_links(metin),
                         {"https://example.com/x", "http://img.test/y.png"})

    def test_relative_links_are_not_external(self):
        self.assertEqual(md.external_links("[a](docs/x.md)"), set())


class WorkflowBadges(unittest.TestCase):
    def test_shields_form(self):
        metin = ("![CI](https://img.shields.io/github/actions/workflow/status/"
                 "o/r/ci.yml?branch=main)")
        self.assertEqual(md.workflow_badges(metin), {("o", "r", "ci.yml")})

    def test_github_form(self):
        metin = "![CI](https://github.com/o/r/actions/workflows/tests.yml/badge.svg)"
        self.assertEqual(md.workflow_badges(metin), {("o", "r", "tests.yml")})

    def test_other_badges_are_ignored(self):
        self.assertEqual(
            md.workflow_badges("![lic](https://img.shields.io/badge/license-MIT-green)"),
            set())


if __name__ == "__main__":                                # pragma: no cover
    unittest.main(verbosity=2)
