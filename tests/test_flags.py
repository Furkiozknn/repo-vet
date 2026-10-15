# -*- coding: utf-8 -*-
"""The flags check: options a README passes to the project's own command
must be options that command defines."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fakes import FakeClient                                  # noqa: E402
from repo_vet import checks, readme                           # noqa: E402
from repo_vet.model import HATA, UYARI                        # noqa: E402
from repo_vet.runner import vet                               # noqa: E402

PYPROJECT = '[project]\nname = "tool"\n\n[project.scripts]\ntool = "tool.cli:main"\n'
ARGPARSE = (
    "import argparse\n"
    "p = argparse.ArgumentParser(prog='tool')\n"
    "p.add_argument('--json', action='store_true')\n"
    "p.add_argument(\"--json-out\", dest='json_out')\n"
    "p.add_argument('--fail-on', choices=('error', 'none'))\n"
)


def blok(*satirlar):
    return "```bash\n" + "\n".join(satirlar) + "\n```"


def ctx(text, files=None, tree=None):
    dosyalar = {"pyproject.toml": PYPROJECT, "tool/cli.py": ARGPARSE}
    dosyalar.update(files or {})
    agac = set(tree) if tree is not None else {"pyproject.toml", "tool/cli.py", "README.md"}
    return checks.Context("o/r", FakeClient(files=dosyalar), meta={"default_branch": "main"},
                          text=text, tree=agac)


class ReadmeFlags(unittest.TestCase):
    def test_options_after_the_command_are_read(self):
        t = blok("tool o/r --json", "$ tool o/r --json-out=r.json --fail-on none")
        self.assertEqual(readme.cli_flags(t, "tool"), {"--json", "--json-out", "--fail-on"})

    def test_a_runner_may_start_the_command(self):
        t = blok("uvx --from git+https://github.com/o/tool tool --json")
        self.assertEqual(readme.cli_flags(t, "tool"), {"--json"})

    def test_installing_the_command_is_not_running_it(self):
        t = blok("pip install tool --upgrade", "pipx install tool --force",
                 "uv tool install git+https://github.com/o/tool")
        self.assertEqual(readme.cli_flags(t, "tool"), set())

    def test_another_program_in_the_same_line_keeps_its_own_options(self):
        t = blok("tool o/r --json | jq --raw-output .", "cd x && git clone --depth 1 y")
        self.assertEqual(readme.cli_flags(t, "tool"), {"--json"})

    def test_prose_and_other_commands_are_ignored(self):
        t = "Run `tool --nope` in prose.\n" + blok("python -m tool --x", "git --version")
        self.assertEqual(readme.cli_flags(t, "tool"), set())


class CheckFlags(unittest.TestCase):
    def test_defined_options_are_quiet(self):
        c = ctx(blok("tool o/r --json --fail-on none", "tool o/r --json-out r.json"))
        self.assertEqual(checks.check_flags(c), [])

    def test_a_renamed_option_is_an_error(self):
        c = ctx(blok("tool o/r --output r.json"))
        (f,) = checks.check_flags(c)
        self.assertEqual((f.check, f.level), ("flags", HATA))
        self.assertIn("--output", f.message)
        self.assertIn("tool/cli.py", f.evidence)

    def test_an_argparse_prefix_is_accepted(self):
        # argparse takes an unambiguous prefix unless allow_abbrev=False.
        self.assertEqual(checks.check_flags(ctx(blok("tool --fail none"))), [])
        strict = ARGPARSE.replace("ArgumentParser(prog='tool')",
                                  "ArgumentParser(prog='tool', allow_abbrev=False)")
        (f,) = checks.check_flags(ctx(blok("tool --fail none"), files={"tool/cli.py": strict}))
        self.assertIn("--fail", f.message)

    def test_help_is_always_there(self):
        self.assertEqual(checks.check_flags(ctx(blok("tool --help"))), [])

    def test_subcommands_wired_elsewhere_make_it_a_warning(self):
        kaynak = ARGPARSE + "sub = p.add_subparsers()\nfrom .commands import add_all\n"
        (f,) = checks.check_flags(ctx(blok("tool run --watch"), files={"tool/cli.py": kaynak}))
        self.assertEqual(f.level, UYARI)

    def test_options_not_spelled_out_in_the_entry_file_are_not_checked(self):
        # typer derives options from parameter names; nothing to read.
        typer = "import typer\napp = typer.Typer()\n@app.command()\ndef main(json: bool = False): ...\n"
        c = ctx(blok("tool --json"), files={"tool/cli.py": typer})
        with self.assertRaises(checks.NotChecked):
            checks.check_flags(c)

    def test_a_package_layout_under_src_is_found(self):
        c = ctx(blok("tool --nope"), files={"src/tool/cli.py": ARGPARSE},
                tree={"pyproject.toml", "src/tool/cli.py"})
        (f,) = checks.check_flags(c)
        self.assertIn("src/tool/cli.py", f.message)

    def test_the_dotted_scripts_key_is_read(self):
        # pypa/pipx: `scripts.pipx = "pipx.__main__:cli"` inside [project].
        proje = '[project]\nname = "tool"\nscripts.tool = "tool.__main__:cli"\n'
        c = ctx(blok("tool --nope"), files={"pyproject.toml": proje, "tool/__main__.py": ARGPARSE},
                tree={"pyproject.toml", "tool/__main__.py"})
        (f,) = checks.check_flags(c)
        self.assertIn("tool/__main__.py", f.message)

    def test_npm_bin_with_commander(self):
        paket = json.dumps({"name": "@scope/tool", "bin": "./bin/tool.js"})
        js = ("const { Command } = require('commander');\nconst program = new Command();\n"
              "program.option('-d, --debug').option('--shout/--no-shout');\n")
        c = ctx(blok("npx tool --debug --no-shout", "npx tool --verbose"),
                files={"pyproject.toml": None, "package.json": paket, "bin/tool.js": js},
                tree={"package.json", "bin/tool.js"})
        (f,) = checks.check_flags(c)
        self.assertIn("--verbose", f.message)

    def test_a_readme_without_the_command_is_quiet_and_reads_nothing_more(self):
        c = ctx(blok("pip install tool"))
        self.assertEqual(checks.check_flags(c), [])
        self.assertNotIn("file:tool/cli.py@main", c.client.asked)

    def test_runs_in_a_full_vet_and_needs_the_tree(self):
        kw = dict(repo={"default_branch": "main"}, readme=blok("tool --output x"),
                  files={"pyproject.toml": PYPROJECT, "tool/cli.py": ARGPARSE})
        r = vet("o/r", FakeClient(tree={"pyproject.toml", "tool/cli.py"}, **kw), only={"flags"})
        self.assertEqual([f.check for f in r.errors], ["flags"])
        r = vet("o/r", FakeClient(tree=None, **kw), only={"flags"})
        self.assertIn(("flags", "the file tree could not be read"), r.skipped)


if __name__ == "__main__":
    unittest.main()
