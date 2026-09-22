# -*- coding: utf-8 -*-
"""Runs the checks and assembles the report."""

from .checks import CHECKS, Context
from .model import Report

README_GEREKTIREN = ("install", "links", "badges", "web")


def vet(slug, client, only=None, skip=None, web_limit=40):
    """Check one repository. Returns a Report.

    A check that cannot see what it needs is recorded as skipped rather than
    counted as passing: an audit that reports "clean" for something it never
    managed to look at is worse than no audit. That rule is why this function
    is mostly about what it refuses to do.
    """
    rapor = Report(slug)

    meta, bilinen = client.repo(slug)
    if meta is None:
        if client.rate_limited:
            rapor.skipped.append(
                ("*", "GitHub rate limit reached; pass a token with --token "
                      "or GITHUB_TOKEN"))
        elif bilinen:
            rapor.skipped.append(("*", "no such repository, or not visible "
                                       "with this token"))
        else:
            rapor.skipped.append(("*", "GitHub could not be read"))
        return rapor

    dal = meta.get("default_branch")
    metin = client.readme(slug, dal)
    agac, kirpik = client.tree(slug, dal or "HEAD")
    ctx = Context(slug, client, meta=meta, text=metin or "", tree=agac,
                  tree_truncated=kirpik)

    if metin is None:
        rapor.skipped.append(("readme", "the repository has no README"))

    for ad, fn in CHECKS:
        if only and ad not in only:
            continue
        if skip and ad in skip:
            rapor.skipped.append((ad, "skipped on request"))
            continue
        if metin is None and ad in README_GEREKTIREN:
            rapor.skipped.append((ad, "needs a README"))
            continue
        if ad in ("links", "badges"):
            if agac is None:
                rapor.skipped.append((ad, "the file tree could not be read"))
                continue
            if kirpik:
                # GitHub caps a recursive tree. torvalds/linux comes back with
                # 71,638 entries and a flag saying there are more; checking a
                # link against a partial tree reports good files as missing.
                rapor.skipped.append(
                    (ad, "the file tree is too large for GitHub to return whole"))
                continue
        if ad == "web":
            bulgular = fn(ctx, limit=web_limit)
        else:
            bulgular = fn(ctx)
        rapor.checked.append(ad)
        for b in bulgular:
            rapor.add(b)

    if client.rate_limited:
        rapor.skipped.append(("*", "a GitHub rate limit was hit during this "
                                   "run; some answers may be incomplete"))
    return rapor
