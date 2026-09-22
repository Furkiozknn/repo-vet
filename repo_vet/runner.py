# -*- coding: utf-8 -*-
"""Runs the checks and assembles the report."""

from .checks import CHECKS, Context
from .model import Report


def vet(slug, client, only=None, skip=None, web_limit=40):
    """Check one repository. Returns a Report.

    A check that cannot see what it needs is recorded as skipped rather than
    counted as passing: an audit that reports "clean" for something it never
    managed to look at is worse than no audit.
    """
    rapor = Report(slug)

    meta = client.repo(slug)
    if meta is None:
        rapor.skipped.append(("*", "repository not found, or not visible with "
                                   "this token"))
        return rapor

    metin = client.readme(slug, meta.get("default_branch"))
    agac = client.tree(slug, meta.get("default_branch") or "HEAD")
    ctx = Context(slug, client, meta=meta, text=metin or "", tree=agac)

    if metin is None:
        rapor.skipped.append(("readme", "the repository has no README"))

    for ad, fn in CHECKS:
        if only and ad not in only:
            continue
        if skip and ad in skip:
            rapor.skipped.append((ad, "skipped on request"))
            continue
        if metin is None and ad in ("install", "links", "badges", "web"):
            rapor.skipped.append((ad, "needs a README"))
            continue
        if agac is None and ad in ("links",):
            rapor.skipped.append((ad, "the file tree could not be read"))
            continue
        if ad == "web":
            bulgular = fn(ctx, limit=web_limit)
        else:
            bulgular = fn(ctx)
        rapor.checked.append(ad)
        for b in bulgular:
            rapor.add(b)
    return rapor
