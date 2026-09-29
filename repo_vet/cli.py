# -*- coding: utf-8 -*-
"""Command line: repo-vet owner/name [owner/name ...]"""

import argparse
import os
import re
import sys

from . import __version__
from .checks import CHECK_NAMES
from .report import as_markdown, as_text
from .runner import vet
from .sources import Client


EPILOG = """\
examples:
  repo-vet OWNER/NAME                       check one repository (no token needed for a public one)
  repo-vet psf/requests --skip web          skip the slow outbound-link pass
  repo-vet OWNER/NAME --only install,links  just those checks
  repo-vet --from-file corpus.txt           many repositories, one slug per line
  repo-vet OWNER/NAME --json                machine-readable output

repo-vet reads a repository over the GitHub API. It does not clone anything and
does not scan a local folder.

exit codes:
  0  nothing to report (warnings alone never fail a run; --fail-on any changes that)
  1  findings, as --fail-on defines them
  2  bad usage: an unknown check, a malformed slug or ref, an unreadable --from-file
  3  a repository could not be read at all (mistyped slug, missing ref, rate limit,
     rejected token, no network). Nothing was looked at, which is not the same as clean
"""

EXAMPLE = "repo-vet Furkiozknn/repo-vet"


def _parser():
    p = argparse.ArgumentParser(
        prog="repo-vet",
        description="Check what a GitHub repository claims against what is there: "
                    "install commands, links, badges, releases and published sites.",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repos", nargs="*", metavar="OWNER/NAME")
    p.add_argument("--from-file", dest="from_file", default=None, metavar="PATH",
                   help="read OWNER/NAME slugs from a file, one per line; "
                        "blank lines and lines after a # are ignored")
    p.add_argument("--token", default=None,
                   help="GitHub token. Optional for public repositories; "
                        "raises the rate limit and reaches private ones. "
                        "Falls back to GITHUB_TOKEN or GH_TOKEN.")
    p.add_argument("--ref", default=None, metavar="REF",
                   help="read the README and files at this branch, tag or "
                        "commit instead of the default branch")
    p.add_argument("--only", default=None,
                   help="run only these checks (comma separated): " + ", ".join(CHECK_NAMES))
    p.add_argument("--skip", default=None, help="skip these checks (comma separated)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--json-out", dest="json_out", default=None, metavar="PATH",
                   help="also write the machine-readable report to this file, "
                        "whatever the console output is")
    p.add_argument("--markdown", action="store_true",
                   help="GitHub step-summary output")
    p.add_argument("--web-limit", type=int, default=40,
                   help="how many outbound links to try (default 40)")
    p.add_argument("--fail-on", choices=("error", "any", "none"), default="error",
                   help="what makes the exit code non-zero (default: error). "
                        "Exit codes: 0 clean, 1 findings, 2 bad usage, "
                        "3 a repository could not be read at all")
    p.add_argument("--timeout", type=int, default=20,
                   help="seconds to wait for each GitHub request (default 20)")
    p.add_argument("--version", action="version", version="repo-vet " + __version__)
    return p


# What GitHub allows in an owner or repository name. Anything else -- a
# space, `?`, `#`, `%`, or a `..` segment -- would change which API URL gets
# requested (with the token attached) instead of naming a repository.
SLUG_PARCA = re.compile(r"^[A-Za-z0-9._-]+$")
# A branch, tag or commit: git's own characters, minus the ones git forbids
# in a ref name and the `..` that would walk up an API path.
REF = re.compile(r"^[A-Za-z0-9._/+@-]+$")


def slug_ok(slug):
    parcalar = slug.split("/")
    return (len(parcalar) == 2
            and all(SLUG_PARCA.match(p) and p not in (".", "..") for p in parcalar))


def ref_ok(ref):
    return bool(REF.match(ref)) and ".." not in ref and "@{" not in ref \
        and not ref.startswith(("/", "-")) and not ref.endswith("/")


def slug_hint(slug):
    """One line saying what to type instead of a slug that is not OWNER/NAME.

    The likeliest first mistakes are a pasted URL, a clone URL, a bare name or
    a folder: each gets the command that would have worked.
    """
    m = re.match(r"^(?:https?://(?:www\.)?github\.com/|git@github\.com:)"
                 r"([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?(?:[/#?].*)?$", slug)
    if m:
        return "repo-vet %s/%s" % (m.group(1), m.group(2))
    if slug in (".", "..") or "\\" in slug or slug.startswith(("./", "../", "~")):
        return ("repo-vet reads a repository over the GitHub API and does not scan "
                "a local folder; name the repository as OWNER/NAME, e.g. " + EXAMPLE)
    if slug.endswith("/") and slug_ok(slug.rstrip("/")):
        return "repo-vet " + slug.rstrip("/")
    return "a repository is OWNER/NAME, e.g. " + EXAMPLE


def _liste(deger):
    if not deger:
        return None
    return set(x.strip() for x in deger.split(",") if x.strip())


def main(argv=None):
    args = _parser().parse_args(argv)

    bilinmeyen = (_liste(args.only) or set()) | (_liste(args.skip) or set())
    hatali = sorted(bilinmeyen - set(CHECK_NAMES))
    if hatali:
        sys.stderr.write("unknown check(s): %s\nknown: %s\n"
                         % (", ".join(hatali), ", ".join(CHECK_NAMES)))
        return 2

    slugs = list(args.repos)
    if args.from_file:
        try:
            with open(args.from_file, encoding="utf-8") as f:
                for satir in f:
                    satir = satir.split("#")[0].strip()
                    if satir:
                        slugs.append(satir)
        except OSError as e:
            sys.stderr.write("cannot read %s: %s\n" % (args.from_file, e))
            return 2
    if not slugs:
        sys.stderr.write("nothing to check: pass OWNER/NAME or --from-file\n"
                         "try: %s\n(repo-vet --help lists every option)\n" % EXAMPLE)
        return 2

    # Every slug is checked before any network work: a typo on line 30 of a
    # --from-file list should not cost twenty-nine scans and then no report.
    for slug in slugs:
        if not slug_ok(slug):
            sys.stderr.write("not an OWNER/NAME slug: %s\nhint: %s\n"
                             % (slug, slug_hint(slug)))
            return 2
    if args.ref is not None and not ref_ok(args.ref):
        sys.stderr.write("not a branch, tag or commit: %s\n" % args.ref)
        return 2

    token = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    client = Client(token=token, timeout=args.timeout)

    raporlar = []
    for slug in slugs:
        raporlar.append(vet(slug, client, only=_liste(args.only),
                            skip=_liste(args.skip), web_limit=args.web_limit,
                            ref=args.ref))

    # One scan, one truth. Writing the machine-readable report to a file
    # alongside whatever the console gets means a caller no longer has to run
    # the tool three times to get JSON, a summary and an exit code - and three
    # runs against a flaky network could disagree with each other, which is a
    # worse failure than being slow.
    if args.json_out:
        import json
        try:
            with open(args.json_out, "w", encoding="utf-8") as f:
                json.dump([r.as_dict() for r in raporlar], f, indent=2,
                          ensure_ascii=False)
                f.write("\n")
        except OSError as e:
            sys.stderr.write("cannot write %s: %s\n" % (args.json_out, e))
            return 2

    if args.json:
        import json
        print(json.dumps([r.as_dict() for r in raporlar], indent=2,
                         ensure_ascii=False))
    elif args.markdown:
        print("\n".join(as_markdown(r) for r in raporlar))
    else:
        renkli = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
        print("\n\n".join(as_text(r, renkli) for r in raporlar))

    if args.fail_on == "none":
        return 0
    if args.fail_on == "any":
        if any(r.findings for r in raporlar):
            return 1
    elif any(r.errors for r in raporlar):
        return 1
    # A repository that could not be read at all - a mistyped slug, a rate
    # limit, a rejected token - has no findings because nobody looked. Exiting
    # 0 would hand CI a green tick for an audit that never happened.
    if any(r.unreadable for r in raporlar):
        return 3
    return 0


if __name__ == "__main__":                                # pragma: no cover
    raise SystemExit(main())
