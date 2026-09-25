# -*- coding: utf-8 -*-
"""What a finding is, and what a report is.

Every finding carries the thing that was observed, not just an opinion
about it. "The first install command fails" is an opinion; "`pip install
ptm-cli` is in a code block and PyPI has no such distribution" is an
observation someone else can repeat.
"""

import json

HATA = "error"
UYARI = "warning"


class Finding(object):
    """One checked claim that did not hold.

    check    - which check produced it, e.g. "install"
    message  - one sentence, in the repository's own terms
    evidence - what was actually observed (a command, a URL, a status code)
    level    - error or warning; warnings never fail a run on their own
    """

    __slots__ = ("check", "message", "evidence", "level")

    def __init__(self, check, message, evidence="", level=HATA):
        self.check = check
        self.message = message
        self.evidence = evidence
        self.level = level

    def __repr__(self):                                   # pragma: no cover
        return "Finding(%r, %r, %r, %r)" % (
            self.check, self.message, self.evidence, self.level)

    def __eq__(self, other):
        return (isinstance(other, Finding)
                and self.as_dict() == other.as_dict())

    def __hash__(self):
        return hash((self.check, self.message, self.evidence, self.level))

    def as_dict(self):
        return {"check": self.check, "message": self.message,
                "evidence": self.evidence, "level": self.level}


class Report(object):
    """Everything one run learned about one repository."""

    def __init__(self, repo, findings=None, checked=None, skipped=None):
        self.repo = repo
        self.findings = list(findings or [])
        self.checked = list(checked or [])      # checks that actually ran
        self.skipped = list(skipped or [])      # (check, reason) pairs

    @property
    def errors(self):
        return [f for f in self.findings if f.level == HATA]

    @property
    def warnings(self):
        return [f for f in self.findings if f.level == UYARI]

    @property
    def unreadable(self):
        """True when not a single check ran because the repository itself
        could not be read. Such a report has no findings, and it is not
        clean: nothing was looked at."""
        return not self.checked and any(c == "*" for c, _ in self.skipped)

    def add(self, finding):
        self.findings.append(finding)

    def as_dict(self):
        return {
            "repository": self.repo,
            "checks_run": self.checked,
            "checks_skipped": [{"check": c, "reason": r} for c, r in self.skipped],
            "finding_count": len(self.findings),
            "error_count": len(self.errors),
            "findings": [f.as_dict() for f in self.findings],
        }

    def as_json(self):
        return json.dumps(self.as_dict(), indent=2, ensure_ascii=False)
