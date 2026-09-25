# -*- coding: utf-8 -*-
"""Runs the checks and assembles the report."""

import datetime

import re

from .checks import CHECKS, Context, NotChecked
from .model import ISTEKLE, Report

README_GEREKTIREN = ("install", "links", "badges", "web")


def vet(slug, client, only=None, skip=None, web_limit=40, ref=None):
    """Check one repository. Returns a Report.

    `ref` -- a branch, tag or commit -- is where the README and files are
    read. Without it they are read on the default branch. A pull request
    that breaks its README is only caught if the README being read is the
    pull request's.

    A check that cannot see what it needs is recorded as skipped rather than
    counted as passing: an audit that reports "clean" for something it never
    managed to look at is worse than no audit. That rule is why this function
    is mostly about what it refuses to do.
    """
    rapor = Report(slug)

    meta, bilinen = client.repo(slug)
    if meta is None:
        if getattr(client, "bad_credentials", False):
            rapor.skipped.append(
                ("*", "GitHub rejected the token (401 Bad credentials); check "
                      "--token, GITHUB_TOKEN or GH_TOKEN"))
        elif client.rate_limited:
            rapor.skipped.append(("*", _rate_limit_reason(client)))
        elif bilinen:
            rapor.skipped.append(("*", "no such repository, or not visible "
                                       "with this token"))
        else:
            rapor.skipped.append(("*", "GitHub could not be read"))
        return rapor

    dal = meta.get("default_branch")
    etiket = None
    if ref:
        # Resolved to one commit first, so the README, the tree and the
        # manifest all come from the same snapshot even if the branch moves
        # mid-run -- and so a mistyped ref is reported as one, instead of as
        # a repository with no README.
        sha = client.commit_sha(slug, ref)
        if sha is None:
            rapor.skipped.append(("*", "GitHub could not be read"
                                  + (" (rate limit)" if client.rate_limited else "")))
            return rapor
        if not sha:
            rapor.skipped.append(("*", "no such branch, tag or commit: %s" % ref))
            return rapor
        dal = sha
        etiket = ref[:12] if re.match(r"^[0-9a-f]{40}$", ref) else ref
    metin, readme_bilinen = client.readme(slug, dal)
    agac, kirpik = client.tree(slug, dal or "HEAD")
    ctx = Context(slug, client, meta=meta, text=metin or "", tree=agac,
                  tree_truncated=kirpik, ref=dal if ref else None,
                  ref_label=etiket)

    if metin is None:
        if not readme_bilinen or client.rate_limited:
            rapor.skipped.append(("readme", "the README could not be read"
                                  + (" (GitHub rate limit)" if client.rate_limited else "")))
        else:
            rapor.skipped.append(("readme", "the repository has no README"))

    for ad, fn in CHECKS:
        if only and ad not in only:
            continue
        if skip and ad in skip:
            rapor.skipped.append((ad, ISTEKLE))
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
        try:
            if ad == "web":
                bulgular = fn(ctx, limit=web_limit)
            else:
                bulgular = fn(ctx)
        except NotChecked as e:
            rapor.skipped.append((ad, str(e)))
            continue
        rapor.checked.append(ad)
        for b in bulgular:
            rapor.add(b)

    if client.rate_limited:
        rapor.skipped.append(("*", "a GitHub rate limit was hit during this "
                                   "run; some answers may be incomplete"))
    return rapor


def _rate_limit_reason(client):
    """Say which limit, and what would lift it.

    Without a token GitHub allows 60 requests an hour, which one link-heavy
    README can use up; the fix is a token. With a token the fix is waiting,
    and telling someone to pass the token they already passed is noise.
    """
    ne_zaman = ""
    reset = getattr(client, "rate_reset", None)
    if reset:
        ne_zaman = "; it resets at %s" % datetime.datetime.fromtimestamp(
            reset, datetime.timezone.utc).strftime("%H:%M UTC")
    if getattr(client, "token", None):
        return "GitHub rate limit reached for this token%s" % ne_zaman
    return ("GitHub rate limit reached (60 requests an hour without a "
            "token)%s; pass --token or set GITHUB_TOKEN" % ne_zaman)
