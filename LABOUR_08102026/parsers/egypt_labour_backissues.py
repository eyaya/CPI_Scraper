"""CAPMAS Egypt quarterly LFS -- employment composition, current bulletin PLUS
back issues.

The descriptor's primary is the current quarter's PDF bulletin, read by
`egypt_labour` (Tables 16 and 17, national block). Back issues come in as
`extra_urls`, one workbook per quarter named `egypt_lfs_<YYYY>Q<n>.xlsx`
(2021 Q1 onward; earlier issues are PDF-only image scans -- no OCR).

THE WORKBOOK'S TABLES 16 AND 17 are the same two tables as the bulletin's:

    Table 16  employed persons 15+ by MAIN OCCUPATION (10 groups)
    Table 17  employed persons 15+ by ECONOMIC ACTIVITY (22 sections)

each a percentage distribution per row, one row per sex within each
geographical block, closing on a "%" column of 100 and a count column. Read
here as published:

* EVERY CATEGORY COLUMN, including the two the bulletin reader does not carry
  ("Individuals can't be classified"; "Activities incompletely described").
  The count ("No.,") and "Column %" columns are not shares of the row and are
  not read.
* EVERY GEOGRAPHICAL BLOCK. In the bulletin the region name is printed once
  per three-row block and is not safely placed, so only the national block is
  read there; the workbook writes the region in its own English column on
  each block's first row, so the regions are read too. `geography` keeps the
  published stratum, `locality` its urban/rural half.
* LABELS VERBATIM from the workbook's English header row (whitespace runs
  collapsed). They differ from the bulletin's in places ("Professionals" /
  "proficinals") and are never mapped onto them.
* FULL PRECISION. The workbook stores the unrounded shares (3.6896...); the
  bulletin prints one decimal. Each is kept as its edition publishes it.

CHECK: each row's category shares must sum to its published "%" total (100)
within 0.5 -- a shifted column fails it.

PDF BACK ISSUES (2015-2020): only the issues whose Tables 16-17 parse with
the current layout and sum to 100 are listed (2018 Q1); the others' tables
changed shape or are image scans (no OCR).

DATING: from the filename the descriptor gives (`save_as`, set from CAPMAS's
API year/quarter), checked against the workbook's own cover text. Two
workbooks carry the previous quarter's cover over the stated quarter's data
(2025 Q3 -> "Second Quarter 2025", 2026 Q1 -> "Fourth Quarter 2025"); both
were verified against the same quarter's PDF bulletin and are pinned. See
`indicators/unemployment/parsers/egypt_lfs_backissues.py`.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from . import egypt_labour

_NAME = re.compile(r"egypt_lfs_(20\d{2})Q([1-4])\.xlsx$", re.I)
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_COVER = re.compile(
    r"(?:The\s+(First|Second|Third|Fourth)\s+Quarter\s+(20\d{2}))"
    r"|(?:(20\d{2})\s+The\s+(First|Second|Third|Fourth)\s+Quarter)", re.I)
_STALE_COVER = {(2026, 1): (2025, 4), (2025, 3): (2025, 2)}

# PUBLISHED, PINNED: rows whose printed shares miss their printed 100 by
# more than rounding -- (period, table, region, sex, published sum). Kept as
# published; a row that starts or stops missing is a change to look at.
KNOWN_SUM_GAPS: set = {
    # A blank cell ("not printed"), so the printed shares fall short:
    ("2021-Q1", "LFS T16", "Total Egypt", "female", 95.8),
    ("2021-Q1", "LFS T16", "Total Egypt", "total", 95.1),
    ("2021-Q4", "LFS T17", "Urban Upper Egypt", "male", 88.3),
    # Shares as printed that miss 100 beyond rounding:
    ("2021-Q1", "LFS T16", "Rural Frontier Gov.", "female", 98.4),
    ("2021-Q2", "LFS T16", "Rural Frontier Gov.", "female", 98.4),
    ("2021-Q1", "LFS T17", "Urban Governorates", "total", 97.7),
    ("2021-Q1", "LFS T17", "Urban Upper Egypt", "male", 98.8),
    ("2021-Q1", "LFS T17", "Urban Upper Egypt", "total", 98.4),
    ("2021-Q1", "LFS T17", "Urban Frontier Gov.", "male", 97.5),
    ("2021-Q1", "LFS T17", "Urban Frontier Gov.", "total", 97.6),
    ("2021-Q1", "LFS T17", "Rural Frontier Gov.", "female", 98.4),
    ("2021-Q1", "LFS T17", "Total Urban", "male", 98.6),
    ("2021-Q1", "LFS T17", "Total Urban", "total", 98.4),
    ("2022-Q1", "LFS T17", "Rural Frontier Gov.", "female", 101.3),
}

# Rows shifted against their header and therefore NOT read, counted per
# (period, table). A count that changes is a workbook that changed.
KNOWN_MISALIGNED = {("2025-Q2", "LFS T16"): 3, ("2025-Q2", "LFS T17"): 30,
                    ("2025-Q3", "LFS T17"): 30, ("2026-Q1", "LFS T17"): 30}
MISALIGNED_SEEN: list = []

_SURVEY = "Labour Force Survey quarterly bulletin"
_TABLES = {"جدول 16 Table": ("occupation", "LFS T16"),
           "جدول 17 Table": ("industry", "LFS T17")}
_SEX = {"male": "male", "female": "female", "total": "total"}
_LOCALITY = {"urban governorates": "urban", "urban lower egypt": "urban",
             "rural lower egypt": "rural", "urban upper egypt": "urban",
             "rural upper egypt": "rural", "urban frontier governorates": "urban",
             "rural frontier governorates": "rural"}


def _clean(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if isinstance(v, str) else ""


def _num(v):
    t = str(v).replace(",", "").strip()
    if not t or t.lower() == "nan":
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _cover_quarter(xl: pd.ExcelFile) -> set[tuple[int, int]]:
    found = set()
    for sh in xl.sheet_names:
        d = xl.parse(sh, header=None, dtype=str)
        for v in d.values.ravel():
            if not isinstance(v, str):
                continue
            for m in _COVER.finditer(v):
                if m.group(1):
                    found.add((int(m.group(2)), _ORD[m.group(1).lower()]))
                else:
                    found.add((int(m.group(3)), _ORD[m.group(4).lower()]))
    return found


def _sheet(xl: pd.ExcelFile, sheet: str, topic: str, code: str,
           period: str, reference: str) -> list[dict]:
    d = xl.parse(sheet, header=None, dtype=str)
    # The English header row: the first row with an ASCII label in the
    # second column and the "No.," count header further right.
    hdr = next(i for i in range(len(d))
               if any(_clean(v).lower().startswith("no.") for v in d.iloc[i]))
    header = [_clean(v) for v in d.iloc[hdr]]
    first = 1                                   # column 0 = Arabic region label
    count_col = next(j for j, h in enumerate(header) if h.lower().startswith("no."))
    # The Arabic header sits on the row above the English one. Where the
    # English cell is not a label (the 2021 Q3 workbook prints "%" over
    # Technicians in Table 16 and over Manufacturing in Table 17), the same
    # file's Arabic header names the column and is used verbatim -- never a
    # label borrowed from another quarter.
    arabic = [_clean(v) for v in d.iloc[hdr - 1]]
    cats = []
    for j in range(first, count_col):
        name = header[j]
        if name and not re.search(r"[A-Za-z]", name):
            name = arabic[j] if j < len(arabic) else ""
        if name:
            cats.append((j, name))
    if not cats:
        raise ValueError(f"{sheet}: no category headers")
    # The "%" (row total) column: the first column after the categories whose
    # national Total row reads 100. In Table 16 it precedes the count; in
    # Table 17 it follows it.
    rows, geo = [], None
    for i in range(hdr + 1, len(d)):
        r = list(d.iloc[i])
        tail = [_clean(v) for v in r if _clean(v)]
        # English labels sit at the right: [..., sex, (region)].
        eng = [t for t in tail if re.match(r"^[A-Za-z]", t)]
        if not eng:
            continue
        sex = _SEX.get(eng[0].lower())
        if sex is None:
            continue
        if len(eng) > 1:
            geo = eng[1]
        # A BLANK CELL IS "NOT PRINTED", not zero: CAPMAS leaves the
        # "Individuals can't be classified" cell empty in many rows. It is
        # skipped, never filled.
        vals = [(_num(r[j]), name) for j, name in cats if j < len(r)]
        vals = [(v, name) for v, name in vals if v is not None]
        if not vals:
            continue
        # Each share is rounded (one decimal in the 2021-2023 workbooks), so
        # the row may miss 100 by up to half a unit in the last place per
        # category. Not tested against a "%" cell: in Table 17 that column is
        # the block's share of national employment, not the row total.
        # A ROW SHIFTED AGAINST ITS HEADER. In some workbooks a row carries
        # one category fewer than the header and its row total (100) lands in
        # a category slot (2025 Q2 Table 16, national block: nine shares, then
        # 100 under "Individuals can't be classified"). Which category dropped
        # out cannot be read from the file, so the row is not read at all.
        if len(vals) > 1 and any(abs(v - 100) < 1e-6 for v, _ in vals):
            MISALIGNED_SEEN.append((period, code, geo or "Total Egypt", sex))
            continue
        s = sum(v for v, _ in vals)
        if abs(s - 100) > 0.05 * len(vals) + 0.05:
            key = (period, code, geo or "Total Egypt", sex, round(s, 1))
            if key not in KNOWN_SUM_GAPS:
                raise ValueError(f"{sheet} row {i} ({geo}, {sex}): shares sum to "
                                 f"{s:.2f}, not the published 100 -- unpinned {key}")
        national = geo is None or geo.lower() == "total egypt"
        low = (geo or "").lower()
        for v, name in vals:
            rows.append({
                "survey": _SURVEY, "topic": topic, "characteristic": name,
                "classification": "National", "sex": sex,
                "age_group": "Total", "education": "Total",
                "geography": "Total country" if national else geo,
                "locality": "all" if national else _LOCALITY.get(low, "other"),
                "locality_label": "Total" if national else geo,
                "working_age_base": "15+", "period": period,
                "reference_period": reference, "frequency": "quarterly",
                "measure": "share", "value": v, "unit": "percent",
                "series_code": code,
            })
    return rows


def _back_issue(path: str) -> list[dict]:
    m = _NAME.search(os.path.basename(path))
    if not m:
        raise ValueError(f"Egypt LFS back issue {path!r}: name must be "
                         f"egypt_lfs_<YYYY>Q<n>.xlsx (set by the descriptor)")
    y, q = int(m.group(1)), int(m.group(2))
    xl = pd.ExcelFile(path)
    cover = _cover_quarter(xl)
    if cover != {(y, q)} and cover != {_STALE_COVER.get((y, q))}:
        raise ValueError(f"{os.path.basename(path)}: filed as {y} Q{q} but the "
                         f"workbook names {sorted(cover) or 'no quarter'}")
    period, reference = f"{y}-Q{q}", f"Q{q} {y}"
    rows = []
    for sheet, (topic, code) in _TABLES.items():
        MISALIGNED_SEEN.clear()
        got = _sheet(xl, sheet, topic, code, period, reference)
        want = KNOWN_MISALIGNED.get((period, code), 0)
        if len(MISALIGNED_SEEN) != want:
            raise ValueError(f"{os.path.basename(path)} {code}: {len(MISALIGNED_SEEN)} "
                             f"row(s) shifted against the header, {want} pinned")
        if not got and not want:
            raise ValueError(f"{os.path.basename(path)}: {sheet} read no rows")
        rows += got
    return rows


def _pdf_back_issue(path: str) -> pd.DataFrame:
    """A 2015-2020 PDF issue, read by the current bulletin layout with the
    quarter checked against the issue's own text. Each sex's shares in each
    table must sum to 100 within rounding, or the issue is refused."""
    from indicators.unemployment.parsers import egypt_lfs_pdf_period
    from .pdf_tables_labour import make_parser
    df = make_parser(egypt_lfs_pdf_period.fixed_layout(egypt_labour.LAYOUT, path))(path)
    tbl = df["series_code"].str.extract(r"(T1[67])")[0]
    sums = df.groupby([tbl, df["sex"]])["value"].sum()
    if len(sums) != 6 or ((sums - 100).abs() > 0.5).any():
        raise ValueError(f"{os.path.basename(path)}: Tables 16/17 shares by sex sum "
                         f"to {sums.round(1).to_dict()} -- not a clean read")
    return df


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    cur = egypt_labour.parse(path)
    current = set(cur["period"].astype(str))
    rows, frames = [], [cur]
    for p in extras or []:
        if p.lower().endswith(".pdf"):
            d = _pdf_back_issue(p)
            frames.append(d[~d["period"].astype(str).isin(current)])
        else:
            rows += [r for r in _back_issue(p) if r["period"] not in current]
    return pd.concat(frames + [pd.DataFrame(rows)], ignore_index=True)
