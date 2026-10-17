"""KNBS Kenya -- 2019 KPHC Analytical Report on Population Projections,
Appendix 5 "Projected Population by Age, Sex and County, 2020-2045".

Added 2026-10-13 as a SECOND Kenya descriptor (kenya_projections.yaml) beside
the 2019 census volumes.

For Kenya and each of the 47 counties, three pages:
* A -- "Base and Projected Age Distributions, 2020-2045": 2020, 2025, ...,
  2045 by five-year age group (0-4 .. 80+, All Ages) x Male/Female/Total,
  then two sex-ratio columns (2020, 2045; not read);
* C -- "Base and Projected Age Distributions", annual: 2020-2025 and
  2026-2030 on one page, 2030-2035 on the next.
(One county prints "B:" for "C:" -- the parser goes by the year header, not
the letter.) So 2020-2035 annually plus 2040 and 2045.

A year printed in two tables (2025, 2030, 2035 in A and C, 2030 in both C
blocks) must agree to the unit, and is emitted once.

Each row is bound to the nearest year header ABOVE it; the header line also
names the geography ("Kenya" -> "Total country"; "Elgeyo-" wraps onto the line
above "Marakwet"). Column order is read from the "Age Male Female Total ..."
line under each header. Checks: bands sum to "All Ages" (published as "All
Ages", filed as age_group "Total"), Male + Female = Total on every row, and
the 47 counties sum to Kenya every year.

County names are as printed in THIS report ("Taita-Taveta", "Trans-Nzoia",
"Elgeyo-Marakwet"); the census volumes print "Taita/Taveta", "Trans Nzoia",
"Elgeyo/Marakwet". Never sum counties with "Total country".

Part B (components of change by five-year period: births, deaths, CBR, CDR)
is deferred: its periods are ranges ("2020-25"), not years.

series_type = projection.
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_SC = "KNBS_KPHC2019_PROJ_APP5"
_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
          "75-79", "80+"]
_YEAR = re.compile(r"^20[2-4]\d$")
_NUM = re.compile(r"^\d{1,3}(,\d{3})*$")
_SEX = {"Male": "male", "Female": "female", "Total": "total"}


def _lines(page):
    ws = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    out = []
    for x0, y0, x1, y1, w, *_ in ws:
        y = (y0 + y1) / 2
        if out and y - out[-1][0] <= 2.5:
            out[-1][1].append((x0, w))
        else:
            out.append([y, [(x0, w)]])
    return [(y, [w for _, w in sorted(ws)]) for y, ws in out]


def _geo(name: str) -> str:
    return "Total country" if name == "Kenya" else name


def parse(local_path: str) -> pd.DataFrame:
    seen: dict[tuple[str, str, str, str], list] = {}    # (geo, year, age, sex)
    with fitz.open(local_path) as doc:
        for page in doc:
            lines = _lines(page)
            block = None          # (geo, years, sexes)
            for k, (y, words) in enumerate(lines):
                yrs = [w for w in words if _YEAR.match(w)]
                if len(yrs) >= 2 and not _YEAR.match(words[0]):
                    name = " ".join(words[:words.index(yrs[0])])
                    # the A header ends with the sex-ratio years "2020 2045"
                    if len(set(yrs)) < len(yrs):
                        yrs = yrs[:yrs.index(yrs[0], 1)]
                    if k and len(lines[k - 1][1]) == 1 and lines[k - 1][1][0].endswith("-"):
                        name = lines[k - 1][1][0] + name
                    block = [_geo(name), yrs, None]
                    continue
                if block is None:
                    continue
                if words[0] == "Age" and block[2] is None:
                    sexes = [_SEX[w] for w in words[1:]]
                    if sexes[:3] != ["male", "female", "total"]:
                        raise ValueError(f"KNBS projection p{page.number+1}: "
                                         f"sex columns {words[1:4]}")
                    block[2] = sexes
                    continue
                label = []
                for w in words:
                    if _NUM.match(w) and label and label != ["All"]:
                        break
                    label.append(w)
                lab = " ".join(label)
                if lab == "All Ages":
                    lab = "Total"
                # Kiambu's 2026-2030 block labels its open band "80-84"; the
                # report has no 80-84/85+ split anywhere, the bands then sum
                # to All Ages, and 2030 matches the A table's 80+ (checked).
                if lab == "80-84":
                    lab = "80+"
                if lab not in _BANDS and lab != "Total":
                    continue
                geo, yrs, sexes = block
                nums = words[len(label):]
                if sexes is None or len(sexes) != 3 * len(yrs):
                    raise ValueError(f"KNBS projection p{page.number+1}: "
                                     f"{geo} header unread")
                # the A table appends two sex-ratio columns
                if len(nums) not in (len(sexes), len(sexes) + 2) or \
                        not all(_NUM.match(n) for n in nums):
                    raise ValueError(f"KNBS projection p{page.number+1} {geo} "
                                     f"{lab}: figures {nums}")
                for j, n in enumerate(nums[:len(sexes)]):
                    key = (geo, yrs[j // 3], lab, sexes[j])
                    v = float(n.replace(",", ""))
                    seen.setdefault(key, []).append(v)
    vals = {}
    for key, vs in seen.items():
        # A year printed in several tables must agree. ONE published conflict:
        # Busia 2030 80+ Female is 5,799 in the A table and the 2026-2030 C
        # block (Male 3,916 + 5,799 = Total 9,714) but 3,120 in the 2030-2035
        # block -- the majority (and identity-consistent) figure is kept.
        best = max(set(vs), key=vs.count)
        if vs.count(best) * 2 <= len(vs):
            raise ValueError(f"KNBS projection {key}: tables disagree {vs}")
        if len(set(vs)) > 1 and key != ("Busia", "2030", "80+", "female"):
            raise ValueError(f"KNBS projection {key}: tables disagree {vs}")
        vals[key] = best
    geos = sorted({k[0] for k in vals})
    if "Total country" not in geos or len(geos) != 48:
        raise ValueError(f"KNBS projection: {len(geos)} geographies")
    years = [str(y) for y in range(2020, 2036)] + ["2040", "2045"]
    out = []
    county_sum: dict[str, float] = {}
    for g in geos:
        for yr in years:
            for sex in ("male", "female", "total"):
                missing = [a for a in _BANDS + ["Total"] if (g, yr, a, sex) not in vals]
                if missing:
                    raise ValueError(f"KNBS projection {g} {yr} {sex}: missing {missing}")
                s = sum(vals[(g, yr, a, sex)] for a in _BANDS)
                if abs(s - vals[(g, yr, "Total", sex)]) > 20:
                    raise ValueError(f"KNBS projection {g} {yr} {sex}: bands "
                                     f"{s} != All Ages {vals[(g, yr, 'Total', sex)]}")
            for a in _BANDS + ["Total"]:
                m, f, t = (vals[(g, yr, a, s)] for s in ("male", "female", "total"))
                if abs(m + f - t) > 3:
                    raise ValueError(f"KNBS projection {g} {yr} {a}: {m} + {f} != {t}")
            if g != "Total country":
                county_sum[yr] = county_sum.get(yr, 0) + vals[(g, yr, "Total", "total")]
    for yr, s in county_sum.items():
        nat = vals[("Total country", yr, "Total", "total")]
        if abs(s - nat) > 100:
            raise ValueError(f"KNBS projection {yr}: counties {s} != Kenya {nat}")
    for (g, yr, a, sex), v in sorted(vals.items()):
        if yr not in years:
            raise ValueError(f"KNBS projection: unexpected year {yr}")
        out.append({"series_type": "projection", "sex": sex, "age_group": a,
                    "geography": g, "period": yr, "frequency": "annual",
                    "measure": "count", "value": v, "unit": "persons",
                    "series_code": _SC})
    return pd.DataFrame(out)
