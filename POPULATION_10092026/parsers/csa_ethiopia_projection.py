"""CSA Ethiopia -- "Population Projections for Ethiopia 2007-2037" (Addis
Ababa, July 2013), MEDIUM VARIANT, a SECOND Ethiopia descriptor
(ethiopia_projections.yaml) beside ethiopia.yaml (ESS projections for July
2023 and 2025 by region, zone and wereda).

Annex tables "Projected Total, Urban and Rural Population Size (in thousands)
by Region and Sex, in Single Year, Medium Variant: 2008-2037": the country
total and each of the eleven regions / city administrations, Total / Male /
Female, every year 2008-2037. Only the "Urban + Rural" columns are read (the
schema has no locality column). Values are in THOUSANDS as printed.

WHICH PAGES. The annex numbers do not match the table of contents (the page
headed "Table A 7.3.1" is the Medium variant; the contents list A7.3.1 as
Low), so the country table is found by its own "Medium Variant" heading plus
"Country Total (in Thousands)", and regional tables by "<Region> (in
Thousands)". Low and High variants are not read.

NOT FILED: 2023 and 2025 -- ESS's own later projections for those years are
collected by ethiopia.yaml and supersede this 2013 vintage. Region labels are
the report's own (Tigray, Afar, ..., "Benshangul Gumz", SNNP); the 2007 base
population (Table A7.1) and age tables are not read.

Checks: Male + Female = Total within 1 (thousand, rounding).

PUBLISHED, NOT RECONCILED: the country table is projected on its own and the
eleven regions sum BELOW it every year, by 100 thousand in 2008 rising to 177
thousand in 2037 (Total; Male 53-95, Female 44-83) -- about 0.13-0.17 %. The
parser requires the regions to fall short by 0-0.3 %, so a misread region
still fails.
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_REGIONS = ["Tigray", "Afar", "Amhara", "Oromia", "Somali", "Benshangul Gumz",
            "SNNP", "Gambella", "Harari", "Addis Ababa", "Dire Dawa"]
_YEARS = [str(y) for y in range(2008, 2038)]
_SKIP = {"2023", "2025"}            # ethiopia.yaml holds ESS's newer projections


def _n(s: str) -> float:
    return float(s.replace(",", ""))


def _series(text: str, after: str) -> dict[str, tuple[float, float, float]]:
    i = text.find(after)
    toks = text[i + len(after):].split()
    out, k = {}, 0
    for y in _YEARS:
        while k < len(toks) and toks[k] != y:
            k += 1
        if k + 3 >= len(toks):
            raise ValueError(f"CSA Ethiopia {after!r}: year {y} not found")
        vals = toks[k + 1:k + 4]
        if not all(re.fullmatch(r"\d{1,3}(,\d{3})*", v) for v in vals):
            raise ValueError(f"CSA Ethiopia {after!r} {y}: {vals}")
        out[y] = tuple(map(_n, vals))
        k += 4
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    tables: dict[str, dict] = {}
    with fitz.open(local_path) as doc:
        for page in doc:
            t = " ".join(page.get_text().split())
            if "Projected Total, Urban and Rural Population Size (in thousands)" not in t \
                    or "Year Urban + Rural" not in t:
                continue                                   # contents pages
            if "Country Total (in Thousands)" in t:
                if "Medium Variant" in t.split("Year Urban")[0]:
                    if "Total country" in tables:
                        raise ValueError("CSA Ethiopia: two Medium-variant country tables")
                    tables["Total country"] = _series(t, "Country Total (in Thousands)")
                continue
            names = [r for r in _REGIONS if f"{r} (in Thousands)" in t]
            if len(names) != 1 or "Medium Variant" not in t:
                continue
            name = names[0]
            if name in tables:
                raise ValueError(f"CSA Ethiopia: unexpected region table {name!r}")
            tables[name] = _series(t, f"{name} (in Thousands)")
    if set(tables) != set(_REGIONS) | {"Total country"}:
        raise ValueError(f"CSA Ethiopia: tables {sorted(tables)}")

    for g, ser in tables.items():
        for y, (t, m_, f) in ser.items():
            if abs(m_ + f - t) > 1:
                raise ValueError(f"CSA Ethiopia {g} {y}: {m_} + {f} != {t}")
    for y in _YEARS:
        for k in range(3):
            s = sum(tables[r][y][k] for r in _REGIONS)
            c = tables["Total country"][y][k]
            # the country is projected on its own: the regions fall short of
            # it by a steady 0.13-0.17 % (as printed, never reconciled)
            if not (0 <= c - s <= 0.003 * c):
                raise ValueError(f"CSA Ethiopia {y} col {k}: regions {s} vs country {c}")

    out = []
    for g, ser in tables.items():
        for y, vals in ser.items():
            if y in _SKIP:
                continue
            for sex, v in zip(("total", "male", "female"), vals):
                out.append({"series_type": "projection", "sex": sex, "age_group": "Total",
                            "geography": g, "period": y, "frequency": "annual",
                            "measure": "count", "value": v, "unit": "thousand_persons",
                            "series_code": "ET_CSA_PROJ_2007_2037_MEDIUM"})
    return pd.DataFrame(out)
