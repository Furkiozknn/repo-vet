# -*- coding: utf-8 -*-
"""Reading a README the way a visitor reads it.

The distinction this module keeps is between what a README *says* and what
it *asks you to run*. A sentence that mentions `pip install thing` is
discussing it. A fenced code block containing the same line is asking you
to paste it into a terminal. Only the second one is a promise, and only
promises can be broken.
"""

import re
import urllib.parse

# A fence opens and closes at the start of a line, the way Markdown
# defines it. Without the anchor, three backticks written mid-sentence
# pair with the next real fence and swallow the prose in between --
# which is how this tool first accused its own README.
KOD_BLOGU = re.compile(r"^[ ]{0,3}```[^\n]*\n(.*?)^[ ]{0,3}```",
                       re.S | re.M)

BAGLANTI = re.compile(r"!?\[([^\]]*)\]\(\s*<?([^)>\s]+)>?(?:\s+\"[^\"]*\")?\s*\)")
IMG_ETIKET = re.compile(r"<img[^>]*\ssrc=[\"']([^\"']+)[\"']", re.I)

PIP = re.compile(
    r"(?:pip3?\s+install|pipx\s+install|uv\s+pip\s+install|uv\s+tool\s+install|uvx)"
    r"([^\n`]*)")
# Uzun secenek once: `i|install` siralamasi `install`in basini yer ve
# geriye "nstall left-pad" kalir. Bu bir kez oldu, test olarak duruyor.
NPM = re.compile(
    r"(?:npm\s+(?:install|exec|i)\b|npx\b|pnpm\s+(?:add|dlx)\b"
    r"|yarn\s+add\b|bunx\b|bun\s+add\b)"
    r"([^\n`]*)")
CARGO = re.compile(r"cargo\s+install\b([^\n`]*)")

# Cargo options that take a value before the crate name. `--git` and `--path`
# are handled separately because they install from a source, not crates.io.
CARGO_YUTAN = {"--vers", "--version", "--root", "--target", "--target-dir",
               "--index", "--registry", "--bin", "--example", "--features",
               "-F", "--jobs", "-j", "--profile", "--branch", "--tag",
               "--rev", "--git", "--path", "--config", "--message-format",
               "--color"}

# Flags that swallow the following word: what comes after is a file or a
# path, never a distribution name.
# `-D` and `--save-dev` are deliberately absent: they are npm switches that
# take no argument, and swallowing the next word would hide the package.
YUTAN = {"-r", "--requirement", "-e", "--editable", "-c", "--constraint",
         "-i", "--index-url", "--extra-index-url", "-f", "--find-links",
         "-p", "--python", "--with", "--index", "--prefix", "--target"}

# Characters no registry name contains.
AD_DISI = ("+", ":", "\\", "$", "<", ">", "=", '"', "'", "*", "|")
DOSYA_SONU = (".txt", ".py", ".toml", ".cfg", ".lock", ".json", ".yaml",
              ".yml", ".sh", ".tgz", ".whl")

# Workflow badges, both spellings GitHub hands you.
ROZET_SHIELDS = re.compile(
    r"img\.shields\.io/github/(?:actions/)?workflow/status/"
    r"([^/\s]+)/([^/\s]+)/([^/?\s\"')]+)")
ROZET_GITHUB = re.compile(
    r"github\.com/([^/\s]+)/([^/\s]+)/actions/workflows/([^/?\s\"')]+)/badge\.svg")


def code_blocks(text):
    """Only the text between ``` fences, joined."""
    return "\n".join(KOD_BLOGU.findall(text or ""))


def _distribution(tail, scoped_ok=False):
    """The distribution name an install command names, or None.

    `git+https://...`, `-e .`, `-r requirements.txt` and a bare path are not
    registry names. `uvx --from <dist> <command>` names its distribution
    after `--from`; the trailing word there is the command being run, and
    mistaking one for the other invents findings that are not real.
    """
    parts = tail.split()
    if "--from" in parts:
        return None
    i = 0
    while i < len(parts):
        p = parts[i]
        if p in YUTAN:
            i += 2
            continue
        if p.startswith("-"):
            i += 1
            continue
        aday = p.strip("`,;()\"'")
        # Strip a version pin: requests==2.0 is still "requests".
        for ayirac in ("==", ">=", "<=", "~=", "!=", "@", ">", "<"):
            if ayirac in aday and not (scoped_ok and aday.startswith("@")):
                aday = aday.split(ayirac)[0]
                break
        # Strip extras: what PyPI knows is the base name, and asking it
        # about `fastapi[all]` would invent a missing distribution.
        if "[" in aday:
            aday = aday.split("[")[0]
        if not aday or aday.startswith((".", "-", "/")):
            return None
        if any(k in aday for k in AD_DISI):
            return None
        if aday.lower().endswith(DOSYA_SONU):
            return None
        if "/" in aday and not (scoped_ok and aday.startswith("@")):
            return None
        return aday
    return None


def pypi_installs(text):
    """Distribution names a README's code blocks tell you to install from PyPI."""
    out = set()
    for tail in PIP.findall(code_blocks(text)):
        ad = _distribution(tail)
        if ad:
            out.add(ad)
    return out


def npm_installs(text):
    """Package names a README's code blocks tell you to install from npm."""
    out = set()
    for tail in NPM.findall(code_blocks(text)):
        ad = _distribution(tail, scoped_ok=True)
        if ad and ad not in ("install", "add", "dlx", "exec"):
            out.add(ad)
    return out


def cargo_installs(text):
    """Crate names a README's code blocks tell you to install from crates.io."""
    out = set()
    for tail in CARGO.findall(code_blocks(text)):
        parts = tail.split()
        # A git or local path source is not looked up on crates.io, even if a
        # package name follows the source option.
        source_options = {part.split("=", 1)[0] for part in parts}
        if "--git" in source_options or "--path" in source_options:
            continue
        registry = None
        index = None
        for i, part in enumerate(parts):
            option, separator, value = part.partition("=")
            if option == "--registry":
                registry = value if separator else (parts[i + 1]
                                                     if i + 1 < len(parts) else None)
            elif option == "--index":
                index = value if separator else (parts[i + 1]
                                                  if i + 1 < len(parts) else None)
        if registry is not None and registry != "crates-io":
            continue
        if index is not None and index not in (
                "sparse+https://index.crates.io/",
                "https://github.com/rust-lang/crates.io-index"):
            continue
        i = 0
        while i < len(parts):
            part = parts[i]
            if part.startswith("-"):
                if part.split("=", 1)[0] in CARGO_YUTAN and "=" not in part:
                    i += 2
                else:
                    i += 1
                continue
            name = _distribution(part)
            if name:
                out.add(name)
            i += 1
    return out


def _prose(text):
    """The README with its code blocks removed.

    A markdown link written inside a fence is an example of markdown, not a
    link anyone can click. Probing it would report a documented sample as a
    broken promise.
    """
    return KOD_BLOGU.sub("\n", text or "")


def local_targets(text):
    """Relative link and image targets — the ones that must exist in the tree.

    Returns (path, looks_like_a_file) pairs. The second half matters: a
    target with a file extension is a file that should be in the tree, while
    `tutorial/` or `getting-started` is usually a route on a documentation
    site that happens to share this README. Both are worth saying; only the
    first is worth failing a build over.
    """
    metin = _prose(text)
    out = set()
    for _, hedef in BAGLANTI.findall(metin):
        out.add(hedef)
    for hedef in IMG_ETIKET.findall(metin):
        out.add(hedef)
    yerel = set()
    for h in out:
        if h.startswith(("http://", "https://", "//", "#", "mailto:", "data:",
                         "tel:", "ftp:")):
            continue
        yol = h.split("#")[0].split("?")[0].strip()
        if not yol or yol.startswith("/"):
            continue
        yol = urllib.parse.unquote(yol)
        if yol.startswith("../"):
            # Escapes the repository root; nothing here can confirm it.
            continue
        yol = yol.lstrip("./")
        if not yol:
            continue
        taban = yol.rstrip("/").rsplit("/", 1)[-1]
        dosya_gibi = "." in taban and not yol.endswith("/")
        yerel.add((yol, dosya_gibi))
    return yerel


def external_links(text):
    """Absolute http(s) targets a reader can click (examples in fences excluded)."""
    text = _prose(text)
    out = set()
    for _, hedef in BAGLANTI.findall(text or ""):
        if hedef.startswith(("http://", "https://")):
            out.add(hedef.rstrip(").,"))
    for hedef in IMG_ETIKET.findall(text or ""):
        if hedef.startswith(("http://", "https://")):
            out.add(hedef.rstrip(").,"))
    return out


def workflow_badges(text):
    """(owner, repo, workflow-file) for every workflow-status badge."""
    out = set()
    for o, r, w in ROZET_SHIELDS.findall(text or ""):
        out.add((o, r, w.split("?")[0]))
    for o, r, w in ROZET_GITHUB.findall(text or ""):
        out.add((o, r, w.split("?")[0]))
    return out
