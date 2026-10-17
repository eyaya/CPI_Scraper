"""NSA Namibia -- "Namibia National Population Projections 2023-2053" (2023
census based, posted September 2026), section 3.9, Tables 3.14-3.44:
"Namibia population projection by five years age group and sex: <year>",
MEDIUM variant, one table per year 2023 (base year) to 2053.

Added 2026-10-13 as a SECOND Namibia descriptor (namibia_projections.yaml)
beside the 2023 census workbook.

ONE VARIANT: section 3.9 is the Medium variant; the Low/High totals of Table
3.1 are not read (the merge key has no variant column). The 2023 base-year
population (2,978,967) is the projection's adjusted base, NOT the census count
(3,022,401) -- it is filed under series_type projection, beside the census.

Tables print two-across. Each line is cut into segments at each age label
(the left table's labels sit at x~43, the right's at x~330), and a segment's
three figures (Both Sexes, Male, Female -- header order checked) go to the
table whose caption year is on that side. Caption years are read from the
"... and sex: <year>" lines. Checks: bands sum to Total, Male + Female =
Both Sexes, 31 consecutive years.

series_type = projection.
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_SC = "NSA_PROJ_2023_2053_MEDIUM"
_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
          "75-79", "80-84", "85-89", "90-94", "95+"]
_LABELS = set(_BANDS) | {"Total"}
_NUM = re.compile(r"^\d{1,3}(,\d{3})*$")
_MID = 250


def _lines(page):
    ws = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    out = []
    for x0, y0, x1, y1, w, *_ in ws:
        y = (y0 + y1) / 2
        if out and y - out[-1][0] <= 2.5:
            out[-1][1].append((x0, w))
        else:
            out.append([y, [(x0, w)]])
    return [(y, sorted(ws)) for y, ws in out]


def parse(local_path: str) -> pd.DataFrame:
    tables: dict[str, dict[str, list]] = {}
    with fitz.open(local_path) as doc:
        for page in doc:
            text = page.get_text("text")
            if not re.search(r"projection by five\s+years|base year population by five", text):
                continue
            if "......" in text or "��" in text:
                continue                        # list of tables
            lines = _lines(page)
            side_year: dict[bool, str] = {}
            for _, ws in lines:
                toks = [w for _, w in ws]
                if "sex:" in toks:
                    for x0, w in ws:
                        if re.fullmatch(r"20[2-5]\d", w):
                            side = x0 >= _MID
                            if side in side_year:
                                raise ValueError(f"NSA projection p{page.number+1}: "
                                                 f"two captions on one side")
                            side_year[side] = w
                if "Both" in toks:
                    order = [w for w in toks if w in ("Both", "Male", "Female")]
                    if order not in (["Both", "Male", "Female"],
                                     ["Both", "Male", "Female"] * 2):
                        raise ValueError(f"NSA projection p{page.number+1}: header {toks}")
            if not side_year:
                continue
            if len(side_year) == 1:
                # one table on the page (2053): its caption runs full width
                only = next(iter(side_year.values()))
                side_year = {False: only, True: only}
            for _, ws in lines:
                segs: list[list] = []
                for x0, w in ws:
                    if w in _LABELS:
                        segs.append([x0, w, []])
                    elif segs and _NUM.match(w):
                        segs[-1][2].append(float(w.replace(",", "")))
                for x0, lab, vals in segs:
                    year = side_year.get(x0 >= _MID)
                    if year is None:
                        raise ValueError(f"NSA projection p{page.number+1}: {lab} "
                                         f"with no caption on its side")
                    if len(vals) != 3:
                        raise ValueError(f"NSA projection {year} {lab}: {vals}")
                    t = tables.setdefault(year, {})
                    if lab in t:
                        raise ValueError(f"NSA projection {year} {lab}: read twice")
                    t[lab] = vals
    years = [str(y) for y in range(2023, 2054)]
    if sorted(tables) != years:
        raise ValueError(f"NSA projection: years {sorted(tables)}")
    out = []
    for y in years:
        t = tables[y]
        if set(t) != _LABELS:
            raise ValueError(f"NSA projection {y}: rows {sorted(_LABELS ^ set(t))}")
        for k in range(3):
            s = sum(t[b][k] for b in _BANDS)
            if abs(s - t["Total"][k]) > 20:
                raise ValueError(f"NSA projection {y}: bands {s} != Total {t['Total'][k]}")
        for lab, (b, m, f) in t.items():
            if abs(m + f - b) > 2:
                raise ValueError(f"NSA projection {y} {lab}: {m} + {f} != {b}")
            for sex, v in (("total", b), ("male", m), ("female", f)):
                out.append({"series_type": "projection", "sex": sex,
                            "age_group": lab, "geography": "Total country",
                            "period": y, "frequency": "annual", "measure": "count",
                            "value": v, "unit": "persons", "series_code": _SC})
    return pd.DataFrame(out)
