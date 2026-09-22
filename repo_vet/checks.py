# -*- coding: utf-8 -*-
"""The checks themselves.

Each one takes the repository context and returns findings. None of them
guess: a check either observes something concrete or stays quiet. Where a
check cannot see enough to be sure (an unreachable host, a private
registry, a rate limit), it says it was skipped rather than reporting a
clean result it did not earn.
"""

import re

from .model import Finding, HATA, UYARI
from . import readme as md

SURUM_PYPROJECT = re.compile(r'^\s*version\s*=\s*"([^"]+)"', re.M)


class Context(object):
    """What every check is allowed to look at."""

    def __init__(self, slug, client, meta=None, text=None, tree=None):
        self.slug = slug
        self.client = client
        self.meta = meta or {}
        self.text = text or ""
        self.tree = tree
        self.owner, _, self.name = slug.partition("/")

    @property
    def branch(self):
        return self.meta.get("default_branch") or "main"


# --------------------------------------------------------------------------


def check_install(ctx):
    """Does the install command in the README actually resolve?

    This is the first thing a visitor runs and the last thing an author
    re-runs. A distribution that was renamed, never published, or published
    under a different name leaves a README whose opening instruction fails.
    """
    out = []
    for ad in sorted(md.pypi_installs(ctx.text)):
        if not ctx.client.pypi_versions(ad):
            out.append(Finding(
                "install",
                "README tells you to install `%s` from PyPI, but no such "
                "distribution is published there." % ad,
                "pypi.org/project/%s -> not found" % ad))
    for ad in sorted(md.npm_installs(ctx.text)):
        if not ctx.client.npm_versions(ad):
            out.append(Finding(
                "install",
                "README tells you to install `%s` from npm, but no such "
                "package is published there." % ad,
                "registry.npmjs.org/%s -> not found" % ad))
    return out


def check_links(ctx):
    """Do the README's relative links and images exist in the tree?"""
    if ctx.tree is None:
        return []
    out = []
    for yol in sorted(md.local_targets(ctx.text)):
        if yol in ctx.tree:
            continue
        # A link to a directory is fine if anything lives under it.
        onek = yol.rstrip("/") + "/"
        if any(p.startswith(onek) for p in ctx.tree):
            continue
        out.append(Finding(
            "links",
            "README links to `%s`, which is not in the repository." % yol,
            "%s@%s has no such path" % (ctx.slug, ctx.branch)))
    return out


def check_badges(ctx):
    """Does each workflow badge point at a workflow that exists and has run?

    A badge whose workflow was renamed does not go red. It renders the words
    "no status", which reads like a build nobody looks after.
    """
    out = []
    for owner, name, dosya in sorted(md.workflow_badges(ctx.text)):
        if "%s/%s" % (owner, name) != ctx.slug:
            continue                      # a badge for somebody else's repo
        yol = ".github/workflows/" + dosya
        if ctx.tree is not None and yol not in ctx.tree:
            out.append(Finding(
                "badges",
                "README shows a status badge for `%s`, which is not in "
                ".github/workflows/." % dosya,
                "badge -> %s (missing)" % yol))
            continue
        sayi = ctx.client.workflow_runs(ctx.slug, dosya)
        if sayi == 0:
            out.append(Finding(
                "badges",
                "The badge for `%s` has never had a run, so it renders "
                "\"no status\"." % dosya,
                "workflow runs: 0", UYARI))
    return out


def _declared_version(ctx):
    metin = ctx.client.file_text(ctx.slug, "pyproject.toml", ctx.branch)
    if metin:
        m = SURUM_PYPROJECT.search(metin)
        if m:
            return m.group(1), "pyproject.toml"
    metin = ctx.client.file_text(ctx.slug, "package.json", ctx.branch)
    if metin:
        m = re.search(r'"version"\s*:\s*"([^"]+)"', metin)
        if m and m.group(1) != "0.0.0":
            return m.group(1), "package.json"
    return None, None


def check_release(ctx):
    """Is the release chain finished, or did it stop halfway?

    Two half-finished shapes, both silent: a tag with no release behind it,
    and a version the project declares but never tagged.
    """
    out = []
    etiketler = ctx.client.tags(ctx.slug)
    adlar = [t.get("name", "") for t in etiketler]
    yayinda = set(r.get("tag_name", "") for r in ctx.client.releases(ctx.slug)
                  if not r.get("draft"))
    if adlar and adlar[0] not in yayinda:
        out.append(Finding(
            "release",
            "The newest tag `%s` has no GitHub Release." % adlar[0],
            "tags: %s / releases: %s" % (adlar[0], ", ".join(sorted(yayinda)) or "none"),
            UYARI))
    surum, kaynak = _declared_version(ctx)
    if surum and not adlar:
        out.append(Finding(
            "release",
            "`%s` declares version %s, but the repository has no tags."
            % (kaynak, surum),
            "%s -> %s, tags -> none" % (kaynak, surum), UYARI))
    return out


def check_web(ctx, limit=40):
    """Do the README's outbound links still answer?

    404 and 410 are reported. 401/403/429 are not: they mean a host declined
    to talk to a script, which says nothing about whether a human can open
    the page.
    """
    out = []
    baglantilar = sorted(md.external_links(ctx.text))[:limit]
    for url in baglantilar:
        kod = ctx.client.status(url)
        if kod is None:
            continue                      # unreachable != broken
        if kod in (404, 410):
            out.append(Finding(
                "web", "README links to %s, which returns %d." % (url, kod),
                "HTTP %d" % kod))
    return out


def check_pages(ctx):
    """Is the advertised site alive, and is a live site advertised?"""
    out = []
    ev = (ctx.meta.get("homepage") or "").strip()
    if ev:
        kod = ctx.client.status(ev)
        if kod is not None and kod >= 400:
            out.append(Finding(
                "pages",
                "The repository's homepage %s returns %d." % (ev, kod),
                "HTTP %d" % kod))
        return out
    tahmin = "https://%s.github.io/%s/" % (ctx.owner.lower(), ctx.name)
    if ctx.client.status(tahmin) == 200:
        out.append(Finding(
            "pages",
            "%s is live, but the repository has no homepage set, so nobody "
            "arriving here is told about it." % tahmin,
            "HTTP 200, homepage field empty", UYARI))
    return out


CHECKS = [
    ("install", check_install),
    ("links", check_links),
    ("badges", check_badges),
    ("release", check_release),
    ("web", check_web),
    ("pages", check_pages),
]

CHECK_NAMES = [ad for ad, _ in CHECKS]
