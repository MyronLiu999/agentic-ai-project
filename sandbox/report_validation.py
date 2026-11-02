"""Neutral parsers for report facts and explicit business claims.

No agent decision, task file, or expected answer is consulted here. Callers supply
independently obtained facts and decide which named fields their contract requires.
"""
from __future__ import annotations

import csv
import io
import math
import re


def number(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def named_number_problems(figures: dict, name: str, truth: float, tolerance: float = .01) -> list[str]:
    value = number(figures.get(name))
    if value is None:
        return [f"figures have no finite {name}"]
    if abs(value - truth) > tolerance:
        return [f"{name} is {value:,.2f}, not {truth:,.2f}"]
    return []


def upload_units(text: str) -> int | None:
    """Read the actual upload's recognized units column, without guessing cells."""
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        rows = list(csv.reader(io.StringIO(text), dialect))
        columns = [c.strip().lower() for c in rows[0]]
        index = next(columns.index(c) for c in ("units", "units_sold", "qty", "quantity", "menge") if c in columns)
        values = [number(row[index].strip()) for row in rows[1:] if row and any(row)]
    except (csv.Error, IndexError, StopIteration):
        return None
    if not values or any(v is None or v < 0 or not v.is_integer() for v in values):
        return None
    return int(sum(values))


_PERIOD = re.compile(r"\b(?:(\d{4})\s*)?Q([1-4])\b", re.I)
_REVENUE = re.compile(r"\b(?:revenue|sales(?:\s+total)?|turnover)\b", re.I)
_AMOUNT = re.compile(r"(?<![\w.,])(?:[-+]?\d[\d.,]*\d|\d|[-+]?(?:NaN|Infinity|Inf))(?!\w)", re.I)
_UP = re.compile(r"\b(?:increas\w*|grew|grown|rose|risen|higher)\b|\b(?:went|was|is|are|were)\s+up\b|\bup\s+(?:from|by|on)\b|\brevenue\s+up\b", re.I)
_DOWN = re.compile(r"\b(?:decreas\w*|fell|fallen|declin\w*|dropped|lower)\b|\b(?:went|was|is|are|were)\s+down\b|\bdown\s+(?:from|by|on)\b|\brevenue\s+down\b", re.I)
_FLAT = re.compile(r"\b(?:unchanged|flat|stable)\b|\b(?:no change|the same)\b", re.I)


def comparison_requested(text: str, period: str | None = None) -> bool:
    return (bool(re.search(r"\b(?:compar\w*|last quarter|previous quarter|prior quarter|versus|vs|(?:change from|against|from|than) Q[1-4])\b", text or "", re.I))
            or bool(period and any(p != period for p in _periods(text or "", period))))


def _clauses(text):
    return re.split(r"(?<=[.!?])\s+|[;\n]|\b(?:but|whereas)\b|,?\s+and\s+(?=(?:units|revenue|sales)\b)", text or "", flags=re.I)


def _periods(text, current):
    return [f"{m[1] or current[:4]}Q{m[2]}" for m in _PERIOD.finditer(text)]


def _amount(text):
    # Strip quarter labels before scanning; their year is not a revenue amount.
    text = _PERIOD.sub("", text)
    match = _AMOUNT.search(text)
    if not match:
        return None, False
    raw = match[0].rstrip(".,")
    tail = text[match.end():]
    if re.match(r"\s*(?:%|units\b)", tail, re.I):
        return None, False
    if re.fullmatch(r"[-+]?\d{1,3}(?:\.\d{3})*,\d{2}", raw):
        raw = raw.replace(".", "").replace(",", ".")
    return number(raw), True


def wrong_direction_claims(text: str, now: float, before: float, period: str) -> list[str]:
    """Interpret direction only in the local revenue clause, never 'follow up'."""
    wrong = []
    true_direction = (now > before) - (now < before)
    for clause in _clauses(text):
        if not _REVENUE.search(clause):
            continue
        # Courtesy tails are separate from the revenue assertion they follow.
        revenue_clause = re.split(r",\s*(?:so|please|let)\b|\band\s+(?:I|we|you|please|let)\b",
                                  clause, flags=re.I)[0]
        revenue_clause = re.split(r"\b(?:units|follow up)\b", revenue_clause, flags=re.I)[0]
        # Questions, wishes and negated revenue claims are not positive assertions.
        if "?" in revenue_clause or re.search(r"\b(?:not|never|whether|if)\b", revenue_clause, re.I):
            continue
        noun = _REVENUE.search(revenue_clause)
        if noun is None:
            continue
        directions = [m.start() for p in (_UP, _DOWN, _FLAT) if (m := p.search(revenue_clause))]
        # A period attached to the amount before 'higher/lower' describes the
        # subject just as a period before the revenue noun does.
        subject = revenue_clause[:min(directions) if directions else noun.end()]
        expected = true_direction
        subject_periods = _periods(subject, period)
        if (re.search(r"\b(?:previous|prior|last)\b", subject, re.I)
                or (subject_periods and subject_periods[-1] != period)
                or re.search(r"\b(?:was|were)\b.*\b(?:last|previous|prior) quarter\b", clause, re.I)):
            expected = -expected
        for pattern, direction in ((_UP, 1), (_DOWN, -1), (_FLAT, 0)):
            if pattern.search(revenue_clause) and direction != expected:
                wrong.append(clause.strip())
                break
    return wrong


def revenue_problems(text: str, truth: float, period: str, before: float | None = None,
                     previous_period: str | None = None, *, require_current: bool = False) -> list[str]:
    """Validate explicit revenue totals and their period; a reference number is not a total.

    Accept ordinary prose and comparisons, including 'from X to Y'. Numeric changes
    and percentages are not interpreted as headline revenue totals.
    """
    problems, current_stated = [], False
    for clause in _clauses(text):
        nouns = list(_REVENUE.finditer(clause))
        tags = _periods(clause, period)
        # Two explicitly labelled quarters can place the labels before or after
        # their totals, including 'Q2 and Q3 revenue: X versus Y'.
        unlabelled = _PERIOD.sub("", clause)
        amounts = []
        for match in _AMOUNT.finditer(unlabelled):
            value, stated = _amount(unlabelled[match.start():])
            if stated:
                amounts.append(value)
        if nouns and len(tags) == 2 and len(amounts) == 2:
            for tag, value in zip(tags, amounts):
                expected = truth if tag == period else before if tag == previous_period else None
                if expected is None or value is None or abs(value - expected) > .01:
                    problems.append(f"revenue assertion for {tag} does not match the database")
                elif tag == period:
                    current_stated = True
            continue
        for i, noun in enumerate(nouns):
            prefix = clause[nouns[i - 1].end() if i else 0:noun.start()]
            suffix = clause[noun.end():nouns[i + 1].start() if i + 1 < len(nouns) else len(clause)]
            # A following quarter before another revenue noun belongs to that noun.
            if i + 1 < len(nouns):
                suffix = re.split(r"\b(?:compared|versus|vs\.?|while|and)\b", suffix, flags=re.I)[0]
            tags = _periods(prefix, period) or _periods(suffix.split(" from ")[0], period)
            prior = bool(re.search(r"\b(?:previous|prior|last)\b", prefix + suffix[:20], re.I))
            claimed_period = tags[-1] if tags else previous_period if prior else period
            expected = before if claimed_period == previous_period else truth if claimed_period == period else None
            # A change has its own quantity, rather than being a revenue total.
            if re.match(r"\s*(?:change|increas\w*|decreas\w*|grew|rose|fell|declin\w*|dropped)\b", suffix, re.I):
                # Endpoint markers identify totals regardless of word order. A
                # 'by' amount is a delta and must not stand in for a total.
                endpoints = re.finditer(r"\b(from|to)\s+(.+?)(?=\b(?:from|to)\s|$)", suffix, re.I)
                for endpoint in endpoints:
                    value, stated = _amount(endpoint[2])
                    if not stated:
                        continue  # e.g. 'from Q2' identifies a period, not an amount
                    destination = endpoint[1].lower() == "to"
                    endpoint_truth = expected if destination else before
                    if endpoint_truth is None or value is None or abs(value - endpoint_truth) > .01:
                        problems.append("revenue comparison amounts do not match the database")
                    elif destination and claimed_period == period:
                        current_stated = True
                continue
            value, stated = _amount(suffix)
            if not stated:
                # Also accept '51,264.85 in revenue'.
                value, stated = _amount(re.sub(r"\bin\s*$", "", prefix))
            if stated:
                if expected is None or value is None or abs(value - expected) > .01:
                    problems.append(f"revenue assertion for {claimed_period or 'previous period'} does not match the database")
                elif claimed_period == period:
                    current_stated = True
    # Subject/report headings can also contradict the request, even with an unlabelled body total.
    for line in (text or "").splitlines():
        if re.search(r"\breport\b", line, re.I) and not _REVENUE.search(line):
            if any(p != period for p in _periods(line, period)) and not comparison_requested(line):
                problems.append("report prose names the wrong period")
    if before is not None and wrong_direction_claims(text, truth, before, period):
        problems.append("revenue direction contradicts the database")
    if require_current and not current_stated:
        problems.append(f"does not state the total revenue {truth:,.2f} for {period}")
    return problems
