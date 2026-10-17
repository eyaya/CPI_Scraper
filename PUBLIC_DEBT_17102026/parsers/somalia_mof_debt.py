"""Somalia — Ministry of Finance, Federal Government of Somalia (FGS), Debt
Management Department: Quarterly Public Debt Bulletin, Table 1 "Somalia Stock
of debt at the end of Q<n>, <year>" (Millions of US Dollars).

PUBLISHER: Ministry of Finance, FGS (an accepted official compiler); the table
is credited "Source: DMD, Ministry of Finance, FGS".

COVERAGE AS PUBLISHED: the federal government's EXTERNAL public debt, by
creditor. Somalia's post-HIPC debt is almost entirely external; the bulletin
prints no domestic-debt stock.

WHAT IS READ: every creditor row, every creditor-category SUBTOTAL and the
GRAND TOTAL, each with its four columns -- Face Value, Interest Arrears, Other
Fee Arrears, Total Debt Stock. Components are "<category>: <creditor>: <column>"
(e.g. "Non-Paris Club: Government Of Iraq: Total debt stock"); subtotals are
"<category>: <column>"; the grand total is "Total external debt: <column>".
A "-" cell is nil in the source and is NOT emitted (never read as 0).

FOOTNOTES 1/ and 2/ (kept in the label as printed, "Government Of Iraq 1/"
-> stripped of the marker): the Iraqi and Libyan penalty-interest arrears are
"subject to reconciliation" and the stocks "provisional" per MoF. Collected as
published.

DATING: the caption's quarter ("end of Q 2, 2026", "QII, 2025") -> "2026-Q2", quarterly.
Each new bulletin adds a quarter by merge-on-write.

NOT READ: Table 2 (arrears by category) repeats Table 1's arrears columns and
its text layer is letter-spaced; debt service (Tables 3-4, 6) are flows; the
risk indicators (Table 5) have no measure here.

CHECKS: for every row, face value + interest arrears + other fee arrears =
total (within 0.02); each category's creditors sum to its SUBTOTAL, and the
subtotals to the GRAND TOTAL (within 0.05).

CROSS-CHECK (Q2 2026 bulletin): grand total 1,479.81 (face value 1,104.61,
interest arrears 259.93, other fee arrears 115.27); Non-Paris Club 800.44;
Arab Monetary Fund 201.84.
"""
from __future__ import annotations

import re

import pdfplumber
import pandas as pd

_UNIT = "USD million"
_FACE, _PRIN, _INT, _FEE, _TOT = ("Face value", "Principal arrears", "Interest arrears",
                                  "Other fee arrears", "Total debt stock")
_CATS = {"Commercial", "Multilateral", "Non-Paris Club", "Paris Club"}
_CELL = r"(?:\d{1,3}(?:,\d{3})*\.\d{2}|-)"
_QTAG = re.compile(r"(\d{4})\s*-\s*Q([1-4])(?!\d)")


def _v(s: str):
    return None if s == "-" else float(s.replace(",", ""))


def _table_page(path: str) -> str | None:
    """Table 1's page: it prints the GRAND TOTAL row under the 'Creditor
    Category / Creditor Name' header (the caption sits on the previous page
    in some 2023 issues, so it is not required)."""
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            if "GRAND TOTAL" in t and "Creditor Category / Creditor Name" in t                     and "Face" in t:
                return t
    return None


def _parse_one(path: str) -> list[dict]:
    text = _table_page(path)
    if text is None:
        raise ValueError("MoF Somalia: Table 1 not found")
    head = text.split("GRAND TOTAL", 1)[0]
    # DATING. The column header carries "YYYY - Qn" per period block; the
    # 2023 issues print TWO blocks (previous quarter, then the bulletin's own),
    # and only the bulletin's OWN quarter -- the last block -- is read: the
    # comparison column is a later printing of a quarter that has its own
    # bulletin, sometimes revised (Q4 2022: 4,439.79 in its own issue, 3,868.98
    # in the Q1 2023 issue), and is never filed in its place. Older issues
    # name the quarter only in the caption ("end of Q 2, 2026", "QII, 2025").
    tags = _QTAG.findall(head)
    if tags:
        year, qn = tags[-1]
        nblocks = len(tags)
    else:
        q = re.search(r"Stock of debt at the end of Q\s*([1-4]|IV|III|II|I)\s*,\s*(\d{4})",
                      text)
        if not q:
            raise ValueError("MoF Somalia: cannot date Table 1")
        qn = {"I": "1", "II": "2", "III": "3", "IV": "4"}.get(q.group(1), q.group(1))
        year, nblocks = q.group(2), 1
    period = f"{year}-Q{qn}"
    # COLUMNS. Q2 2025 adds 'Principal Arrears' after Face Value; it is a part
    # OF face value (face + interest + other fees = total, as in every issue).
    cols = [_FACE, _PRIN, _INT, _FEE, _TOT] if "Principal Arrears" in head         else [_FACE, _INT, _FEE, _TOT]
    n = len(cols)
    row_rx = re.compile(rf"^(.*?)((?:\s+{_CELL}){{{n * nblocks}}})$")
    ix = {c: k for k, c in enumerate(cols)}

    cat, rows, subs, grand = None, {}, {}, None
    for ln in (l.strip() for l in text.splitlines()):
        bare = re.sub(r"\s+-$", "", ln)
        if bare in _CATS:            # a category heading with no figures
            cat = bare
            continue
        m = row_rx.match(ln)
        if not m:
            continue
        label = re.sub(r"\s*\d/$", "", m.group(1)).strip()
        vals = [_v(x) for x in m.group(2).split()][-n:]
        parts = [vals[ix[_FACE]], vals[ix[_INT]], vals[ix[_FEE]]]
        if any(v is not None for v in parts):
            s = sum(v or 0 for v in parts)
            if vals[ix[_TOT]] is None or abs(s - vals[ix[_TOT]]) > 0.02:
                raise ValueError(f"MoF Somalia {label}: columns sum {s} != {vals[ix[_TOT]]}")
        if label == "GRAND TOTAL":
            grand = vals
        elif label == "SUBTOTAL":
            if cat is None:
                raise ValueError("MoF Somalia: SUBTOTAL outside a category")
            subs[cat] = vals
        elif label in _CATS:         # 2023-25 layout: subtotal on the category line
            cat = label
            subs[cat] = vals
        elif cat is not None:
            rows[(cat, label)] = vals
    if grand is None or set(subs) != {c for c, _ in rows} or not subs:
        raise ValueError(f"MoF Somalia: categories {sorted(subs)}, grand {grand}")
    for c in subs:
        for k in range(n):
            s = sum(v[k] or 0 for (cc, _), v in rows.items() if cc == c)
            if abs(s - (subs[c][k] or 0)) > 0.05:
                raise ValueError(f"MoF Somalia {c} {cols[k]}: creditors {s} != subtotal")
    for k in range(n):
        if abs(sum(subs[c][k] or 0 for c in subs) - (grand[k] or 0)) > 0.05:
            raise ValueError(f"MoF Somalia {cols[k]}: subtotals != grand total")

    out = []

    def emit(comp, vals):
        for col, v in zip(cols, vals):
            if v is None:
                continue
            out.append({"component": f"{comp}: {col}", "period": period,
                        "frequency": "quarterly", "measure": "stock",
                        "value": v, "unit": _UNIT,
                        "series_code": "MoF FGS QPDB Table 1"})
    for (c, lab), vals in rows.items():
        emit(f"{c}: {lab}", vals)
    for c, vals in subs.items():
        emit(c, vals)
    emit("Total external debt", grand)
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The newest bulletin must parse; a BACK ISSUE whose Table 1 fails its own
    checks is skipped with a message, never misread. Three layouts read:
    category headings + SUBTOTAL lines (Q3 2025, Q2 2026); subtotals printed
    on the category line, grand total first (2023 Q1-Q3, 2024, Q1 2025 --
    the 2023 issues in two quarter blocks, own quarter read); and Q2 2025's
    extra 'Principal Arrears' column (part of face value). Q4 2023, Q4 2025
    and Q1 2026 are letter-spaced with labels detached from their numbers;
    2020-2022 issues use other layouts (comma decimals, split cells)."""
    rows = _parse_one(path)
    for p in extras or []:
        try:
            rows += _parse_one(p)
        except ValueError as e:
            print(f"  [somalia] back issue skipped ({p.rsplit(chr(92), 1)[-1]}): {e}")
    return pd.DataFrame(rows).drop_duplicates(
        ["component", "period", "measure", "unit"], keep="first")
