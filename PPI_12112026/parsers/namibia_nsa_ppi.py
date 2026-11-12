"""Namibia -- NSA Namibia Producer Price Index (NPPI), quarterly table workbooks.

parse  (June 2024=100; "PPI-Q<n>-<yyyy>-Tables.xlsx", current edition)
  Table 1  index by industry, 2023-Q1 .. latest (22 rows, labels only)
  Table 2  index by ISIC group/division/class with the 2022 product-share
           weights, 2016-Q1 .. (35 rows, ISIC codes)
  Table 3  % change on the previous quarter, 2016-Q1 ..
  Table 4  % change on a year earlier, 2017-Q1 ..
  TABLE 2 IS STALE AFTER 2024-Q2. In the Q2 2026 release it agrees with
  Table 1 to the last digit for 2023-Q1 .. 2024-Q2 but not afterwards
  (Production 2025-Q3: Table 2 112.36, Table 1 134.21), while Tables 1, 3 and
  4 agree with each other (2026-Q1 / 2025-Q4 = +1.757 %, Table 3 1.757). So
  index levels are read from Table 2 up to 2024-Q2 and from Table 1 from
  2024-Q3; every row is filed under Table 2's ISIC code and label. Tables 3
  and 4 run row for row with Table 2 (the parser checks the labels), Table 1
  is matched by value (its 2023 quarters equal Table 2's to the last digit).
  Table 2 repeats a label for a division and its only class (C22 / C2220,
  D35 / D3510, E36 / E3600); those rows carry their code in `industry`
  ("Water supply [E36]"), or the two would share a merge key. Table 1's placeholders for products
  introduced in June 2024 (0 in 2024-Q1, 33.33 = (0+0+100)/3 in 2024-Q2) are
  never read: those quarters come from Table 2, which leaves them empty.

parse_dec2015  (Dec 2015=100; last edition Q2 2024, "PPI-Q2-2024-Tables_Dissemination.xlsx")
  Table 1  index by ISIC section/class with weights, 2016-Q1 .. 2024-Q2
           (the Dec 2015 = 100 reference column is not a quarter: skipped)
  Table 2  captioned "Percentage Change Over Quarter" but it is the change on
           a YEAR earlier: it starts 2017-Q1, and Mining 2017-Q1 -12.09 =
           88.96 / 101.19 - 1 (index 2017-Q1 / 2016-Q1). Filed as
           inflation_yoy; the validator's y/y guard confirms it on every row.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

from . import _common as C

_NAME = "Namibia Producer Price Index (NPPI)"
_QCUT = "2024-Q2"          # last quarter read from the current edition's Table 2


def _rows(ws):
    return [r for r in ws.iter_rows(values_only=True) if any(v not in (None, "") for v in r)]


def _quarters(year_row, q_row, start: int) -> dict[int, str]:
    """column index -> 'YYYY-Qn', carrying the year forward across its quarters."""
    out, yr = {}, None
    for j, (y, q) in enumerate(zip(year_row, q_row)):
        if isinstance(y, (int, float)) and 1990 < y < 2100:
            yr = int(y)
        if j >= start and yr and isinstance(q, str) and re.fullmatch(r"Q[1-4]", q.strip()):
            out[j] = f"{yr}-{q.strip()}"
    return out


def _norm(label) -> str:
    return re.sub(r"[^a-z]+", " ", str(label or "").lower()).strip()


def _same(a, b) -> bool:
    """Table 2's 'Mining of uranium' and Table 3's 'Uranium' are one row: the
    shorter label's words must all occur in the longer one."""
    x, y = set(_norm(a).split()) - {"of", "and", "the"}, set(_norm(b).split()) - {"of", "and", "the"}
    return bool(x) and bool(y) and (x <= y or y <= x)


def _cell(v):
    return None if v is None else C.to_number(v)


def parse(path: str) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    t1, t2, t3, t4 = (_rows(wb[n]) for n in ("Table 1", "Table 2", "Table 3", "Table 4"))
    base = re.search(r"-\s*(.+?=\s*100)", str(t2[0][1] or t2[0][0])).group(1).strip()   # "June 2024=100"
    q2 = _quarters(t2[1], t2[2], 3)
    q3 = _quarters(t3[1], t3[2], 1)
    q4 = _quarters(t4[0], t4[1], 1)
    hdr1 = t1[2]
    q1 = {j: h.strip() for j, h in enumerate(hdr1) if isinstance(h, str) and re.fullmatch(r"\d{4}-Q[1-4]", h.strip())}
    body2, body3, body4 = t2[3:], t3[3:], t4[2:]
    if not (len(body2) == len(body3) == len(body4)):
        raise ValueError(f"tables 2/3/4 differ in length: {len(body2)} {len(body3)} {len(body4)}")
    out = []
    labels = []
    dup = pd.Series([_norm(r[1]) for r in body2]).value_counts().to_dict()
    section = {str(r[0]).strip(): str(r[1]) for r in body2 if re.fullmatch(r"[A-U]", str(r[0] or "").strip())}
    for r2, r3, r4 in zip(body2, body3, body4):
        code, label = str(r2[0] or "").strip(), str(r2[1]).strip()
        for other in (r3[0], r4[0]):
            # Tables 3/4 label D35 / D3510 by their section's name.
            if not _same(label, other) and not (code == "" and "production" in _norm(other))                     and not (code[:1] in section and _same(section[code[:1]], other)):
                raise ValueError(f"row mismatch: Table 2 {label!r} vs {other!r}")
        industry = "Production (B+C+D+E)" if code == "" else label
        if dup.get(_norm(label), 0) > 1:      # C22/C2220, D35/D3510, E36/E3600 share a label
            industry = f"{label} [{code}]"
        labels.append((industry, code, _norm(r3[0])))
        kw = dict(index_name=_NAME, industry=industry, industry_code_nso=code,
                  frequency="quarterly", base_period=base)
        if r2[2] is not None:
            out.append(C.row(**kw, period="2022", measure="weight", value=float(r2[2]),
                             unit="percent", series_code="weight 2022 (adjusted product share)")
                       | {"frequency": "annual"})
        for j, p in q2.items():
            v = _cell(r2[j])
            if v is not None and p <= _QCUT:
                out.append(C.row(**kw, period=p, measure="index", value=v))
        for j, p in q3.items():
            v = _cell(r3[j])
            if v is not None:
                out.append(C.row(**kw, period=p, measure="inflation_qoq", value=v))
        for j, p in q4.items():
            v = _cell(r4[j])
            if v is not None:
                out.append(C.row(**kw, period=p, measure="inflation_yoy", value=v))
    # Table 1 -> Table 2 rows by VALUE: a Table 1 row is the Table 2 row whose
    # 2023 quarters it equals to the last digit (Table 1's labels repeat:
    # two "Electricity ..." and two "Water ..." rows). Rows with no 2023
    # values (products introduced in June 2024) are matched by label through
    # Table 3's wording. Every overlap cell before the cut must agree.
    lvl = {}
    for x in out:
        if x["measure"] == "index":
            lvl.setdefault(x["industry"], {})[x["period"]] = x["value"]
    used, check = set(), 0
    for r1 in t1[3:]:
        mine = {p: _cell(r1[j]) for j, p in q1.items()}
        y23 = {p: v for p, v in mine.items() if p.startswith("2023") and v is not None}
        cands = [i for i, (ind, _, _) in enumerate(labels) if i not in used and y23
                 and all(abs(lvl.get(ind, {}).get(p, -1) - v) <= 1e-6 for p, v in y23.items())]
        if not y23:
            cands = [i for i, (_, _, l3) in enumerate(labels) if i not in used and l3 == _norm(r1[0])]
        if not cands:
            raise ValueError(f"Table 1 row {r1[0]!r} matches no Table 2 row")
        # identical series (a section and its only division): the first is the section
        i = cands[0]
        used.add(i)
        industry, code, _ = labels[i]
        for p, v in mine.items():
            if v is None:
                continue
            if p > _QCUT:
                out.append(C.row(index_name=_NAME, industry=industry, industry_code_nso=code,
                                 frequency="quarterly", base_period=base, period=p,
                                 measure="index", value=v))
            elif p < "2024-Q1" and p in lvl.get(industry, {}):
                check += 1
                if abs(lvl[industry][p] - v) > 1e-6:
                    raise ValueError(f"Table 1 / Table 2 disagree before the cut: {industry} {p} {v} vs {lvl[industry][p]}")
    if check < 20:
        raise ValueError(f"only {check} Table 1 / Table 2 overlap cells compared")
    return pd.DataFrame(out)


def parse_dec2015(path: str) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    t1, t2 = _rows(wb["Table 1"]), _rows(wb["Table 2"])
    base = re.search(r"\((.+?=\s*100)\)", str(t1[0][0])).group(1).strip()   # "Dec 2015 = 100"
    q1 = _quarters(t1[1], t1[2], 4)
    q2 = _quarters(t2[1], t2[2], 3)
    out = []
    for r1 in t1[3:]:
        code, label = str(r1[0]).strip(), str(r1[1]).strip()
        kw = dict(index_name=_NAME, industry=label, industry_code_nso=code,
                  frequency="quarterly", base_period=base)
        if r1[2] is not None:
            out.append(C.row(**kw, period="2015", measure="weight", value=float(r1[2]), unit="percent",
                             series_code="weight (Dec 2015 base)") | {"frequency": "annual"})
        for j, p in q1.items():
            v = _cell(r1[j])
            if v is not None:
                out.append(C.row(**kw, period=p, measure="index", value=v))
    for r2 in t2[3:]:
        code, label = str(r2[0]).strip(), str(r2[1]).strip()
        for j, p in q2.items():
            v = _cell(r2[j])
            if v is not None:
                out.append(C.row(index_name=_NAME, industry=label, industry_code_nso=code,
                                 frequency="quarterly", base_period=base, period=p,
                                 measure="inflation_yoy", value=v))
    return pd.DataFrame(out)
