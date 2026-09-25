# -*- coding: utf-8 -*-
"""Turning a report into something a person or a CI log can read."""

from .model import HATA

BASLIK = {
    "install": "Install command",
    "links": "Link into the repository",
    "badges": "Status badge",
    "release": "Release chain",
    "web": "Outbound link",
    "pages": "Published site",
}


def _grupla(findings):
    gruplar = {}
    for f in findings:
        gruplar.setdefault(f.check, []).append(f)
    return gruplar


def as_text(rapor, renkli=False):
    kalin = (lambda s: "\033[1m%s\033[0m" % s) if renkli else (lambda s: s)
    satir = ["%s  %s" % (kalin(rapor.repo), _ozet(rapor))]
    if not rapor.findings:
        for ad, sebep in rapor.skipped:
            satir.append("  - %s: skipped (%s)" % (ad, sebep))
        return "\n".join(satir)
    for ad, bulgular in sorted(_grupla(rapor.findings).items()):
        satir.append("")
        satir.append("%s" % kalin(BASLIK.get(ad, ad)))
        for f in bulgular:
            isaret = "x" if f.level == HATA else "!"
            satir.append("  %s %s" % (isaret, f.message))
            if f.evidence:
                satir.append("      %s" % f.evidence)
    if rapor.skipped:
        satir.append("")
        satir.append("Not checked: " + ", ".join(
            "%s (%s)" % (a, s) for a, s in rapor.skipped))
    return "\n".join(satir)


def _kontrol(n):
    return "%d check%s" % (n, "" if n == 1 else "s")


def _ozet(rapor):
    if rapor.unreadable:
        return "not checked"
    if not rapor.findings:
        return "clean (%s)" % _kontrol(len(rapor.checked))
    return "%d finding%s, %d of them errors" % (
        len(rapor.findings), "" if len(rapor.findings) == 1 else "s",
        len(rapor.errors))


def as_markdown(rapor):
    """A GitHub step summary: short when clean, specific when not."""
    satir = ["### repo-vet: `%s`" % rapor.repo, ""]
    if rapor.unreadable:
        satir.append("**Not checked:** %s. Nothing about this repository was "
                     "looked at, so nothing here is clean either."
                     % "; ".join(s for _, s in rapor.skipped))
        return "\n".join(satir) + "\n"
    if not rapor.findings:
        satir.append("Clean. %s ran: %s."
                     % (_kontrol(len(rapor.checked)), ", ".join(rapor.checked)))
        return "\n".join(satir) + "\n"
    satir.append("**%s**" % _ozet(rapor))
    satir.append("")
    satir.append("| | Check | What was found | Observed |")
    satir.append("|---|---|---|---|")
    for f in rapor.findings:
        satir.append("| %s | %s | %s | `%s` |" % (
            "error" if f.level == HATA else "warn",
            BASLIK.get(f.check, f.check),
            f.message.replace("|", "\\|"),
            f.evidence.replace("|", "\\|") or "-"))
    if rapor.skipped:
        satir.append("")
        satir.append("<sub>Not checked: %s</sub>" % ", ".join(
            "%s (%s)" % (a, s) for a, s in rapor.skipped))
    return "\n".join(satir) + "\n"
