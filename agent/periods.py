from __future__ import annotations

import re

_MONTHS = {
    "january": "jan",
    "jan": "jan",
    "february": "feb",
    "feb": "feb",
    "march": "mar",
    "mar": "mar",
    "april": "apr",
    "apr": "apr",
    "may": "may",
    "june": "jun",
    "jun": "jun",
    "july": "jul",
    "jul": "jul",
    "august": "aug",
    "aug": "aug",
    "september": "sep",
    "sept": "sep",
    "sep": "sep",
    "october": "oct",
    "oct": "oct",
    "november": "nov",
    "nov": "nov",
    "december": "dec",
    "dec": "dec",
    "christmas": "dec",
    "xmas": "dec",
}

_QUARTERS = {
    "q1": {"jan", "feb", "mar"},
    "q2": {"apr", "may", "jun"},
    "q3": {"jul", "aug", "sep"},
    "q4": {"oct", "nov", "dec"},
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_QUARTER_RE = re.compile(r"\bq([1-4])\b")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def task_markers(task: str) -> set[str]:
    toks = _tokens(task)
    marks: set[str] = set()
    for tok in toks:
        if tok in _MONTHS:
            marks.add(_MONTHS[tok])
    for match in _QUARTER_RE.findall(task.lower()):
        marks |= _QUARTERS[f"q{match}"]
    return marks


def evidence_months(evidence: str) -> set[str]:
    toks = _tokens(evidence)
    months: set[str] = set()
    for tok in toks:
        if tok in _MONTHS:
            months.add(_MONTHS[tok])
    return months


def period_compatible(task: str, evidence: str) -> tuple[bool, str]:
    marks = task_markers(task)
    if not marks:
        return True, "no explicit period in task"
    months = evidence_months(evidence)
    if marks & months:
        return True, "period overlaps"
    wanted = ", ".join(sorted(marks))
    return False, (
        f"task asks for period {wanted} "
        "but source evidence shows no overlap; "
        "do not post another period instead"
    )
