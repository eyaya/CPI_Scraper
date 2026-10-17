"""Stats SL -- "2015 Population and Housing Census, Thematic Report on
Population Projections", a SECOND Sierra Leone descriptor
(sierra_leone_projections.yaml) beside sierra_leone.yaml (the 2015 census and
the 2021 mid-term census).

Read:
* Table 2.1 "Total population and intercensal growth rate, 1901-2015" -- the
  national total at each census. The report says the 1901-1948 censuses
  covered the Western Area (the Colony) and ADDED ESTIMATES for the
  provinces, so 1901-1948 are series_type estimate; 1963-2004 census. 2015 is
  sierra_leone.yaml's census figure and is only checked (7 092 113).
* Table 2.2 "Percentage distribution of population by region, 1963-2015" --
  share (percent), regions as printed (Eastern, Northern, Southern, Western
  Area; census).
* Table 7.2 "Summary of projected population by sex, 2016-2030 - Medium
  variant" -- national Total / Male / Female (projection).
* Table 7.5 "Summary of projected population by region, 2016-2030" -- the
  four pre-2017 regions as printed (Eastern, Northern, Southern, Western),
  both sexes (projection).

NOT READ: intercensal growth rates (a rate over a period); High and Low
variants (7.1, 7.3); urban/rural (7.4, no locality column); broad age shares
(7.6); districts (7.7 -- pre-2017 districts); school ages (7.8).

Checks: 7.2 Male + Female = Total; 7.5 regions sum to "All regions" and that
equals 7.2's Total; 2.2 shares sum to 100.0 (within 0.2).
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_N = r"\d{1,3}(?:,\d{3})+"


def _n(s: str) -> float:
    return float(s.replace(",", ""))


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with fitz.open(local_path) as doc:
        pages = [" ".join(p.get_text().split()) for p in doc]
    text = " ".join(pages)

    def block(start: str, end: str, content: str = _N) -> str:
        hits = [m.start() for m in re.finditer(re.escape(start), text)]
        for h in hits:                                  # skip the list of tables
            b = text[h:h + 3000]
            e = b.find(end)
            if e > 0 and re.search(r"\d", b[:e]):
                body = b[:e]
                if re.search(content, body):
                    return body
        raise ValueError(f"Stats SL: block {start!r} not found")

    out = []

    def rec(st, sex, geo, year, measure, value, unit, code):
        out.append({"series_type": st, "sex": sex, "age_group": "Total",
                    "geography": geo, "period": year, "frequency": "annual",
                    "measure": measure, "value": value, "unit": unit,
                    "series_code": code})

    # ---- Table 2.1
    b = block("Table 2.1 Total population and intercensal growth rate", "Source:")
    t21 = dict(re.findall(rf"\b(19\d\d|20\d\d) ({_N})", b))
    years21 = ["1901", "1911", "1921", "1931", "1948", "1963", "1974", "1985", "2004", "2015"]
    if list(t21) != years21:
        raise ValueError(f"Stats SL Table 2.1: years {list(t21)}")
    if _n(t21["2015"]) != 7092113:
        raise ValueError(f"Stats SL Table 2.1: 2015 {t21['2015']} != census 7 092 113")
    for y in years21[:-1]:
        rec("estimate" if int(y) <= 1948 else "census", "total", "Total country", y,
            "count", _n(t21[y]), "persons", "SL_PHC2015_PROJ_T2.1")

    # ---- Table 2.2
    b = block("Table 2.2 Percentage distribution of population by region", "Source:",
              r"\d+\.\d")
    yrs = re.search(r"((?:(?:19|20)\d\d ){5})Percentage", b)
    if not yrs:
        raise ValueError("Stats SL Table 2.2: header")
    years22 = yrs.group(1).split()
    shares = {}
    for name in ("Eastern", "Northern", "Southern", "Western Area", "Total"):
        m = re.search(rf"{name} ((?:\d+\.\d ){{4}}\d+\.\d)", b)
        if not m:
            raise ValueError(f"Stats SL Table 2.2: row {name}")
        shares[name] = dict(zip(years22, map(float, m.group(1).split())))
    for y in years22:
        s = sum(shares[r][y] for r in ("Eastern", "Northern", "Southern", "Western Area"))
        if abs(s - 100.0) > 0.2 or shares["Total"][y] != 100.0:
            raise ValueError(f"Stats SL Table 2.2 {y}: shares sum {s}")
    for r in ("Eastern", "Northern", "Southern", "Western Area"):
        for y in years22:
            rec("census", "total", r, y, "share", shares[r][y], "percent", "SL_PHC2015_PROJ_T2.2")

    # ---- Table 7.2 (medium)
    b = block("Table 7.2 Summary of projected population by sex, 2016–2030 Medium variant", "Source:")
    t72 = {y: tuple(map(_n, v)) for y, *v in re.findall(rf"\b(20[123]\d) ({_N}) ({_N}) ({_N})", b)}
    if list(t72) != [str(y) for y in range(2016, 2031)]:
        raise ValueError(f"Stats SL Table 7.2: years {list(t72)}")
    for y, (t, m_, f) in t72.items():
        if m_ + f != t:
            raise ValueError(f"Stats SL Table 7.2 {y}: {m_} + {f} != {t}")
        for sex, v in (("total", t), ("male", m_), ("female", f)):
            rec("projection", sex, "Total country", y, "count", v, "persons", "SL_PHC2015_PROJ_T7.2_MEDIUM")

    # ---- Table 7.5
    b = block("Table 7.5 Summary of projected population by region, 2016–2030", "Source:")
    if "Year All regions Eastern Northern Southern Western" not in b:
        raise ValueError("Stats SL Table 7.5: header changed")
    t75 = {y: tuple(map(_n, v)) for y, *v in
           re.findall(rf"\b(20[123]\d) ({_N}) ({_N}) ({_N}) ({_N}) ({_N})", b)}
    if list(t75) != list(t72):
        raise ValueError(f"Stats SL Table 7.5: years {list(t75)}")
    for y, (allr, *regs) in t75.items():
        if sum(regs) != allr or allr != t72[y][0]:
            raise ValueError(f"Stats SL Table 7.5 {y}: regions {sum(regs)}, all {allr}, 7.2 {t72[y][0]}")
        for r, v in zip(("Eastern", "Northern", "Southern", "Western"), regs):
            rec("projection", "total", r, y, "count", v, "persons", "SL_PHC2015_PROJ_T7.5")
    return pd.DataFrame(out)
