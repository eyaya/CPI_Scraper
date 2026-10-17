"""CAPMAS Egypt quarterly LFS -- the current bulletin PLUS its back issues.

The descriptor's primary is the current quarter's PDF bulletin (read by
`egypt_unemployment`, the `egypt_pdf` layout). Back issues come in as
`extra_urls`, one workbook per quarter, named `egypt_lfs_<YYYY>Q<n>.xlsx`, and
are read by `egypt_excel_lfs` -- the same three tables (participation,
employment-to-population, unemployment rates by age, education and region,
by sex).

WHERE THE BACK ISSUES ARE. CAPMAS's API lists every quarter it holds:
`/api/Publication/PublicationPeriods?publicationId=11` (2006 Q1 onward) and
`/api/Publication/SearchPublicationDetail?PublicationId=11&Year=Y&Quarter=Q`
for each issue's files. Workbooks exist from 2021 Q1; before that the issues
are PDF only, and most of those are image scans with no text layer -- not read
(no OCR).

DATING A WORKBOOK. `egypt_excel_lfs` dates the CURRENT workbook from the API,
which says nothing about a back issue. Here the quarter comes from the
filename the descriptor gives it (`save_as`, set from the API's year/quarter
for that file) and is then CHECKED against the workbook's own cover text --
"The First Quarter 2021" / "2021 The Second Quarter" -- so a mislabelled file
cannot be filed under the wrong quarter. A workbook that names no quarter, or
a different one, is refused.

LABELS ARE THE WORKBOOK'S, NOT THE BULLETIN'S. CAPMAS words the categories
differently in the two editions ("University & post graduate" in the
workbook, "University & Higher" in the PDF; "Technical intermediate" /
"Technical Secondary"; "Urban Lower Egypt" / "Urban lower Egypt"), and the
workbook adds a 65+ age band. Each is kept as published -- never mapped onto
the other -- so a series that runs from the workbook quarters into the PDF
quarter changes label at that point. Only runs of whitespace are collapsed
("Rural Upper  Egypt" appears with a doubled space on one sheet of the 2021 Q2
workbook and a single one on the others).

STALE COVERS, PINNED. Two workbooks carry the PREVIOUS quarter's cover text
over data that is the stated quarter's: the 2026 Q1 workbook says "Fourth
Quarter 2025" and the 2025 Q3 one says "Second Quarter 2025". Each was
checked against CAPMAS's PDF bulletin for the same quarter, which dates
itself on every page -- 2026 Q1: national 6.0 (M 3.6, F 14.3), 20-24 16.2;
2025 Q3: national 6.4 (M 4.0, F 15.0), 20-24 17.9 (F 46.0) -- identical in
workbook and bulletin; and neither workbook repeats its neighbour's figures (2025
Q2 6.1, Q3 6.4, Q4 6.2). Those two, and only those two, are accepted with the
stale cover; any other mismatch is refused.

PDF BACK ISSUES, 2015-2020 (added 2026-10-14). Before 2021 CAPMAS published
PDF only; most of those issues are image scans (not read -- no OCR). The
ones with a text layer are read by the current-bulletin layout, dated from
`save_as` and checked against the bulletin's own month ranges
(`egypt_lfs_pdf_period`). Each must read completely (198 rows) and pass a
column-order check; only issues that do are listed in the descriptor.

COINCIDENCE, NOT DUPLICATION: 2021 Q1 and Q2 print the same headline rates
(7.4 / male 5.6 / female 15.9). The two workbooks are different files with
different covers, and 140 of their 204 figures differ -- so both are kept.
"""
from __future__ import annotations

import json
import os
import re

import pandas as pd

from . import egypt_excel_lfs
from . import egypt_unemployment

_NAME = re.compile(r"egypt_lfs_(20\d{2})Q([1-4])\.xlsx$", re.I)
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_COVER = re.compile(
    r"(?:The\s+(First|Second|Third|Fourth)\s+Quarter\s+(20\d{2}))"
    r"|(?:(20\d{2})\s+The\s+(First|Second|Third|Fourth)\s+Quarter)", re.I)
# (filed year, quarter) -> the stale quarter its cover names. Verified
# against the same quarter's PDF bulletin; see the module docstring.
_STALE_COVER = {(2026, 1): (2025, 4), (2025, 3): (2025, 2)}
_LABELS = ("series_label", "education", "geography", "locality_label", "age_group")


def _cover_quarter(path: str) -> set[tuple[int, int]]:
    found = set()
    xl = pd.ExcelFile(path)
    for sh in xl.sheet_names:
        d = pd.read_excel(path, sheet_name=sh, header=None, dtype=str)
        for v in d.values.ravel():
            if not isinstance(v, str):
                continue
            for m in _COVER.finditer(v):
                if m.group(1):
                    found.add((int(m.group(2)), _ORD[m.group(1).lower()]))
                else:
                    found.add((int(m.group(3)), _ORD[m.group(4).lower()]))
    return found


def _back_issue(path: str) -> pd.DataFrame:
    m = _NAME.search(os.path.basename(path))
    if not m:
        raise ValueError(f"Egypt LFS back issue {path!r}: name must be "
                         f"egypt_lfs_<YYYY>Q<n>.xlsx (set by the descriptor)")
    y, q = int(m.group(1)), int(m.group(2))
    cover = _cover_quarter(path)
    if cover != {(y, q)} and cover != {_STALE_COVER.get((y, q))}:
        raise ValueError(f"{os.path.basename(path)}: filed as {y} Q{q} but the "
                         f"workbook names {sorted(cover) or 'no quarter'}")
    # egypt_excel_lfs reads its period from a sidecar when one exists.
    side = os.path.splitext(path)[0] + ".period.json"
    with open(side, "w", encoding="utf-8") as fh:
        json.dump({"period": f"{y}-Q{q}", "reference_period": f"Q{q} {y}"}, fh)
    return egypt_excel_lfs.parse(path)


# A complete PDF issue: three tables x (Total + 7 age bands + 7 education
# levels + 7 regions) x three sexes. Issues reading fewer rows lost part of a
# table and are refused rather than half-filed.
_PDF_ROWS = 198
# Which sex is largest is the one thing the bulletin's arithmetic does not
# check and a reversed column order would break (see egypt_unemployment): in
# every row, total lies between male and female; nationally, women's
# unemployment exceeds men's and men's participation and employment exceed
# women's.
_ORDER = {"unemployment_rate": "female", "labour_force_participation_rate": "male",
          "employment_to_population_ratio": "male"}


def _pdf_back_issue(path: str) -> pd.DataFrame:
    from .pdf_key_indicators import make_parser
    from . import egypt_lfs_pdf_period
    df = make_parser(egypt_lfs_pdf_period.fixed_layout(egypt_unemployment.LAYOUT, path))(path)
    name = os.path.basename(path)
    if len(df) != _PDF_ROWS:
        raise ValueError(f"{name}: read {len(df)} rows of {_PDF_ROWS} -- a table "
                         f"was only partly read; drop this issue from extra_urls")
    piv = df.pivot_table(index=["topic", "series_label"], columns="sex", values="value")
    lo = piv[["male", "female"]].min(axis=1) - 0.15
    hi = piv[["male", "female"]].max(axis=1) + 0.15
    if ((piv["total"] < lo) | (piv["total"] > hi)).any():
        raise ValueError(f"{name}: a total lies outside its male/female pair -- "
                         f"the column order differs in this issue")
    for topic, big in _ORDER.items():
        r = piv.loc[(topic, "Total")]
        other = "male" if big == "female" else "female"
        if not r[big] > r[other]:
            raise ValueError(f"{name}: national {topic} has {big} <= {other} -- "
                             f"columns reversed in this issue")
    return df


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = [egypt_unemployment.parse(path)]
    current = set(frames[0]["period"].astype(str))
    for p in extras or []:
        df = _pdf_back_issue(p) if p.lower().endswith(".pdf") else _back_issue(p)
        # The current quarter is the bulletin's; a workbook for the same
        # quarter is not read twice.
        df = df[~df["period"].astype(str).isin(current)]
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    for c in _LABELS:
        if c in out.columns:
            out[c] = out[c].map(
                lambda v: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v)
    return out
