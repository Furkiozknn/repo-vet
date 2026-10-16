# -*- coding: utf-8 -*-
"""The checks themselves.

Each one takes the repository context and returns findings. None of them
guess: a check either observes something concrete or stays quiet. Where a
check cannot see enough to be sure — an unreachable host, a rate limit, a
tree GitHub truncated — it says nothing rather than reporting a clean result
it did not earn.

Every rule here that looks oddly specific is there because a real repository
proved the general version wrong. Those repositories are named in the
comments, and in the tests.
"""

import json
import re

from .model import Finding, HATA, UYARI
from . import readme as md

SURUM_PYPROJECT = re.compile(r'^\s*version\s*=\s*"([^"]+)"', re.M)


class NotChecked(Exception):
    """Raised by a check that could not read what it needs.

    Returning no findings would put the check in the "ran" column and let the
    report call the repository clean on its behalf. Raising puts it in the
    "not checked" column with the reason, which is the truth.
    """


class Context(object):
    """What every check is allowed to look at."""

    def __init__(self, slug, client, meta=None, text=None, tree=None,
                 tree_truncated=False, ref=None, ref_label=None):
        self.slug = slug
        self.client = client
        self.meta = meta or {}
        self.text = text or ""
        self.tree = tree
        self.tree_truncated = tree_truncated
        self.ref = ref                    # what the files are read at
        self.ref_label = ref_label        # how that is shown in evidence
        self.owner, _, self.name = slug.partition("/")

    @property
    def branch(self):
        """The ref files are read at: `--ref` if one was given, otherwise
        the default branch."""
        return self.ref or self.meta.get("default_branch") or "main"

    @property
    def shown_ref(self):
        return self.ref_label or self.branch


# --------------------------------------------------------------------------


def check_install(ctx):
    """Does the install command in the README actually resolve?

    This is the first thing a visitor runs and the last thing an author
    re-runs. A distribution that was renamed, never published, or published
    under a different name leaves a README whose opening instruction fails.
    """
    out = []
    for ad in sorted(md.pypi_installs(ctx.text)):
        surumler = ctx.client.pypi_versions(ad)
        if surumler is None:
            continue                      # could not ask; silence beats a guess
        if not surumler:
            out.append(Finding(
                "install",
                "README tells you to install `%s` from PyPI, but no such "
                "distribution is published there." % ad,
                "pypi.org/project/%s -> 404" % ad))
    for ad in sorted(md.npm_installs(ctx.text)):
        surumler = ctx.client.npm_versions(ad)
        if surumler is None:
            continue
        if not surumler:
            out.append(Finding(
                "install",
                "README tells you to install `%s` from npm, but no such "
                "package is published there." % ad,
                "registry.npmjs.org/%s -> 404" % ad))
    for ad in sorted(md.cargo_installs(ctx.text)):
        surumler = ctx.client.cargo_versions(ad)
        if surumler is None:
            continue
        if not surumler:
            out.append(Finding(
                "install",
                "README tells you to install `%s` from crates.io, but no such "
                "crate is published there." % ad,
                "crates.io/crates/%s -> 404" % ad))
    return out


def check_links(ctx):
    """Do the README's relative links and images exist in the tree?

    A target with a file extension is a file: if it is not there, the link is
    broken and that is an error. A target like `tutorial/` is usually a route
    on a documentation site that shares this README — on GitHub it still
    404s, which is worth saying, but not worth failing a build over.
    (`tiangolo/fastapi` links to `tutorial/` exactly this way.)
    """
    if ctx.tree is None or ctx.tree_truncated:
        return []
    out = []
    for yol, dosya_gibi in sorted(md.local_targets(ctx.text)):
        if yol in ctx.tree or yol.rstrip("/") in ctx.tree:
            continue
        onek = yol.rstrip("/") + "/"
        if any(p.startswith(onek) for p in ctx.tree):
            continue
        if dosya_gibi:
            out.append(Finding(
                "links",
                "README links to `%s`, which is not in the repository." % yol,
                "%s@%s has no such path" % (ctx.slug, ctx.shown_ref)))
        else:
            out.append(Finding(
                "links",
                "README links to `%s`, which is not in the repository; on "
                "GitHub that link 404s. If it is a documentation-site route, "
                "an absolute URL would survive both places." % yol,
                "%s@%s has no such path" % (ctx.slug, ctx.shown_ref), UYARI))
    return out


def check_badges(ctx):
    """Does each workflow badge point at a workflow that exists and has run?

    A badge whose workflow was renamed does not go red. It renders the words
    "no status", which reads like a build nobody looks after. `axios/axios`
    shows a badge for `ci.yml` while its workflow is called `run-ci.yml`.
    """
    out = []
    if ctx.tree_truncated:
        return out
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


def declared_version(ctx):
    """The version the project declares, and where it says it.

    Raises NotChecked when a manifest may exist but could not be read: "no
    declared version" is a statement about the repository, and a timeout is
    not evidence for it.
    """
    metin, bilinen = ctx.client.file_text(ctx.slug, "pyproject.toml", ctx.branch)
    if not bilinen:
        raise NotChecked("pyproject.toml could not be read")
    if metin:
        m = SURUM_PYPROJECT.search(metin)
        if m:
            return m.group(1), "pyproject.toml"
    metin, bilinen = ctx.client.file_text(ctx.slug, "package.json", ctx.branch)
    if not bilinen:
        raise NotChecked("package.json could not be read")
    if metin:
        m = re.search(r'"version"\s*:\s*"([^"]+)"', metin)
        if m and m.group(1) != "0.0.0":
            return m.group(1), "package.json"
    return None, None


# A finished version number and nothing else: 1.2.0, 5.53.12, 0.1.0.
# Anything with a suffix -- 3.2.0.dev, 3.10.0-dev, 2.0.0rc1, 1.0.0-beta.2 --
# is a version being worked towards, and saying so every day would be noise.
# Listing what a pre-release looks like is a losing game; listing what a
# finished one looks like is one line.
SON_SURUM = re.compile(r"^\d+(\.\d+)*$")


def _tag_matches(surum, adlar):
    """Tag names that plausibly carry this version, without guessing an order."""
    aday = {surum, "v" + surum}
    return sorted(a for a in adlar
                  if a in aday or a.endswith("@" + surum) or a.endswith("-" + surum))


def check_release(ctx):
    """Has this project ever finished a release, and did the last one land?

    Two earlier versions of this check were wrong in instructive ways, and
    both are in the tests.

    The first looked at "the newest tag". The tags API promises no order, and
    it duly announced `v0.1.16` as the newest tag of `tiangolo/fastapi` and
    `wincolor-0.1.6` as `ripgrep`'s.

    The second compared the declared version to the tag list. But a healthy
    repository between releases declares the version it is *working towards*:
    `pallets/flask` says `3.2.0.dev`, `astral-sh/ruff` says `0.16.8`,
    `prettier` says `3.10.0-dev`. None of those are broken; they are Tuesday.

    What is left is narrow and defensible: a project that declares a real
    version and has never tagged anything has never shipped, and a tag that
    carries the declared version while every other tag got a Release was
    probably forgotten halfway.
    """
    out = []
    surum, kaynak = declared_version(ctx)
    if not surum or not SON_SURUM.match(surum):
        return out                        # mid-development; nothing to say
    etiketler = ctx.client.tags(ctx.slug)
    if etiketler is None:
        # Could not ask. Not "never tagged" -- and not a clean pass either.
        raise NotChecked("the tag list could not be read")
    adlar = [t.get("name", "") for t in etiketler]
    if not adlar:
        out.append(Finding(
            "release",
            "`%s` declares version %s, but the repository has never been "
            "tagged." % (kaynak, surum),
            "%s -> %s, tags -> none" % (kaynak, surum), UYARI))
        return out
    eslesen = _tag_matches(surum, adlar)
    if not eslesen:
        return out                        # between releases: normal
    yayinlar = ctx.client.releases(ctx.slug)
    if yayinlar is None:
        raise NotChecked("the release list could not be read")
    yayinda = set(r.get("tag_name", "") for r in yayinlar if not r.get("draft"))
    if yayinda and not any(e in yayinda for e in eslesen):
        out.append(Finding(
            "release",
            "Tag `%s` carries the declared version %s but has no GitHub "
            "Release, while other tags here do." % (eslesen[0], surum),
            "tag %s, releases exist for %d other tags" % (eslesen[0], len(yayinda)),
            UYARI))
    return out


def check_web(ctx, limit=40):
    """Do the README's outbound links still answer?

    404 and 410 are reported. 401/403/429 are not: they mean a host declined
    to talk to a script, which says nothing about whether a human can open
    the page. Neither is a timeout.
    """
    baglantilar = sorted(md.external_links(ctx.text))[:limit]
    if not baglantilar:
        return []
    durumlar = ctx.client.statuses(baglantilar)
    out = []
    for url in baglantilar:
        kod = durumlar.get(url)
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
        if kod is not None and kod >= 400 and kod not in (401, 403, 429):
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


# --------------------------------------------------------------------------
# licence
# --------------------------------------------------------------------------

# Licences are compared by family, not by exact SPDX id. "Apache 2.0" in a
# badge, "Apache-2.0" in a manifest and "Apache Software License" in a
# classifier are the same promise; telling them apart would be pedantry, and
# a pedantic check is one people switch off. Families are what can actually
# contradict each other: a manifest saying MIT over an Apache-2.0 LICENSE.
# Longer prefixes first, so "lgpl" is not read as "gpl".
LISANS_AILELERI = (
    ("agpl", "agpl"), ("gnuaffero", "agpl"),
    ("lgpl", "lgpl"), ("gnulesser", "lgpl"), ("gnulibrary", "lgpl"),
    ("gpl", "gpl"), ("gnugeneralpublic", "gpl"), ("gnugpl", "gpl"),
    ("apache", "apache"), ("mit", "mit"), ("0bsd", "bsd"), ("bsd", "bsd"),
    ("mpl", "mpl"), ("mozilla", "mpl"), ("isc", "isc"),
    ("unlicense", "unlicense"), ("theunlicense", "unlicense"),
    ("cc0", "cc0"), ("epl", "epl"), ("eclipse", "epl"),
    ("bsl", "bsl"), ("boost", "bsl"), ("zlib", "zlib"), ("wtfpl", "wtfpl"),
)

LISANS_DOSYASI = re.compile(r"^(?:un)?licen[cs]e|^copying", re.I)


def licence_family(name):
    """The family a licence name belongs to, or None when it is not known.

    None is an answer that silences the check: an unknown name is not
    evidence of a mismatch.
    """
    s = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    if not s or s.startswith(("licenseref", "noassertion", "other", "see")):
        return None
    for onek, aile in LISANS_AILELERI:
        if s.startswith(onek):
            return aile
    return None


def licence_families(expression):
    """Families an SPDX expression allows: "MIT OR Apache-2.0" -> {mit, apache}.

    None if any part is unknown, so a `LicenseRef-...` or a typo is not judged.
    """
    ifade = re.sub(r"\s+WITH\s+[^\s()]+", " ", expression or "", flags=re.I)
    parcalar = [p for p in re.split(r"\s+(?:OR|AND)\s+|[()/,]", ifade, flags=re.I)
                if p.strip()]
    aileler = set()
    for p in parcalar:
        aile = licence_family(p)
        if aile is None:
            return None
        aileler.add(aile)
    return aileler or None


def _toml_table(metin, ad):
    """The text of one `[table]` in a TOML file, up to the next header."""
    m = re.search(r"^\[%s\]\s*$(.*?)(?=^\[|\Z)" % re.escape(ad), metin, re.M | re.S)
    return m.group(1) if m else ""


def declared_licences(ctx):
    """(where, what) for every licence a manifest declares.

    A manifest that cannot be read is left out rather than guessed at.
    """
    out = []
    metin, _ = ctx.client.file_text(ctx.slug, "pyproject.toml", ctx.branch)
    if metin:
        proje = _toml_table(metin, "project")
        m = (re.search(r'^\s*license\s*=\s*"([^"]+)"', proje, re.M)
             or re.search(r'^\s*license\s*=\s*\{[^}\n]*\btext\s*=\s*"([^"]+)"', proje, re.M))
        if m:
            out.append(("pyproject.toml", m.group(1)))
        for sinif in re.findall(r'"License :: (?:OSI Approved :: )?([^"]+)"', proje):
            out.append(("pyproject.toml classifier", sinif))
    metin, _ = ctx.client.file_text(ctx.slug, "package.json", ctx.branch)
    if metin:
        try:
            veri = json.loads(metin)
        except ValueError:
            veri = None
        if isinstance(veri, dict) and isinstance(veri.get("license"), str):
            out.append(("package.json", veri["license"]))
    metin, _ = ctx.client.file_text(ctx.slug, "Cargo.toml", ctx.branch)
    if metin:
        m = re.search(r'^\s*license\s*=\s*"([^"]+)"', _toml_table(metin, "package"), re.M)
        if m:
            out.append(("Cargo.toml", m.group(1)))
    return out


def check_license(ctx):
    """Do the licence claims agree with the licence file?

    Three places promise a licence: the LICENSE file (which is what GitHub
    detects and what actually grants the rights), the package manifest (which
    is what PyPI, npm and crates.io show), and a README badge. When they name
    different licence families, a user cannot tell which one applies.

    Quiet by construction: a licence GitHub cannot identify (`NOASSERTION`,
    two LICENSE files for a dual licence), an unknown name, or a dynamic
    `shields.io/github/license/...` badge are never judged.
    """
    if "license" not in ctx.meta:
        raise NotChecked("GitHub did not report the repository's licence")
    lisans = ctx.meta.get("license") or {}
    spdx = lisans.get("spdx_id") or "" if isinstance(lisans, dict) else ""
    tespit = licence_family(spdx)
    kok_dosyalar = [p for p in (ctx.tree or ()) if "/" not in p and LISANS_DOSYASI.match(p)]
    dosya_yok = (not lisans and ctx.tree is not None and not ctx.tree_truncated
                 and not kok_dosyalar)
    # A dual licence ships one file per licence (clap-rs/clap: LICENSE-APACHE
    # and LICENSE-MIT) and GitHub detects only one of them. Each file's name
    # counts as a licence the repository grants.
    izinli = set([tespit]) if tespit else set()
    for ad in kok_dosyalar:
        aile = licence_family(re.sub(r"^(?:un)?licen[cs]e|^copying", "", ad, flags=re.I))
        if aile:
            izinli.add(aile)
    out = []
    for kaynak, ifade in declared_licences(ctx):
        aileler = licence_families(ifade)
        if not aileler:
            continue
        if tespit and not (aileler & izinli):
            out.append(Finding(
                "license",
                "`%s` declares the licence %s, but the licence file GitHub "
                "detects is %s." % (kaynak, ifade, spdx),
                "%s -> %s; GitHub license -> %s" % (kaynak, ifade, spdx)))
        elif dosya_yok:
            out.append(Finding(
                "license",
                "`%s` declares the licence %s, but the repository has no "
                "licence file, so the licence text is not shipped with the "
                "code." % (kaynak, ifade),
                "%s -> %s; no LICENSE or COPYING at the root" % (kaynak, ifade),
                UYARI))
    # Badges are read together: two badges, one per licence, are how a dual
    # licence is usually shown (clap-rs/clap again).
    rozetler = sorted(md.licence_badges(ctx.text))
    aileler = set()
    for metin in rozetler:
        a = licence_families(metin)
        if a is None:
            aileler = set()
            break
        aileler |= a
    if aileler:
        soylenen = " and ".join(rozetler)
        if tespit and not (aileler & izinli):
            out.append(Finding(
                "license",
                "README's licence badge says %s, but the licence file GitHub "
                "detects is %s." % (soylenen, spdx),
                "badge -> %s; GitHub license -> %s" % (soylenen, spdx)))
        elif dosya_yok:
            out.append(Finding(
                "license",
                "README's licence badge says %s, but the repository has no "
                "licence file." % soylenen,
                "badge -> %s; no LICENSE or COPYING at the root" % soylenen, UYARI))
    return out


CHECKS = [
    ("install", check_install),
    ("links", check_links),
    ("badges", check_badges),
    ("release", check_release),
    ("license", check_license),
    ("web", check_web),
    ("pages", check_pages),
]

CHECK_NAMES = [ad for ad, _ in CHECKS]
