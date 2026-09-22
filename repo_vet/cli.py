# -*- coding: utf-8 -*-
"""Command line: repo-vet owner/name [owner/name ...]"""

import argparse
import os
import sys

from . import __version__
from .checks import CHECK_NAMES
from .report import as_markdown, as_text
from .runner import vet
from .sources import Client


def _parser():
    p = argparse.ArgumentParser(
        prog="repo-vet",
        description="Check what a GitHub repository claims against what is there.")
    p.add_argument("repos", nargs="+", metavar="OWNER/NAME")
    p.add_argument("--token", default=None,
                   help="GitHub token. Optional for public repositories; "
                        "raises the rate limit and reaches private ones. "
                        "Falls back to GITHUB_TOKEN or GH_TOKEN.")
    p.add_argument("--only", default=None,
                   help="run only these checks (comma separated): " + ", ".join(CHECK_NAMES))
    p.add_argument("--skip", default=None, help="skip these checks (comma separated)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--markdown", action="store_true",
                   help="GitHub step-summary output")
    p.add_argument("--web-limit", type=int, default=40,
                   help="how many outbound links to try (default 40)")
    p.add_argument("--fail-on", choices=("error", "any", "none"), default="error",
                   help="what makes the exit code non-zero (default: error)")
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--version", action="version", version="repo-vet " + __version__)
    return p


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

    token = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    client = Client(token=token, timeout=args.timeout)

    raporlar = []
    for slug in args.repos:
        if slug.count("/") != 1 or not all(slug.split("/")):
            sys.stderr.write("not an OWNER/NAME slug: %s\n" % slug)
            return 2
        raporlar.append(vet(slug, client, only=_liste(args.only),
                            skip=_liste(args.skip), web_limit=args.web_limit))

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
        return 1 if any(r.findings for r in raporlar) else 0
    return 1 if any(r.errors for r in raporlar) else 0


if __name__ == "__main__":                                # pragma: no cover
    raise SystemExit(main())
