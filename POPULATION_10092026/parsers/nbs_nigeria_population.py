"""Nigeria — NBS "Demographic Statistics Bulletin" annexes (projections by the
National Population Commission, 2006 census base), three editions.

WHERE THEY ARE. nigerianstat.gov.ng/elibrary lists the bulletins (2012-2022;
the 2023 and 2024 editions appear only in the release calendar, never
uploaded). The e-library's `download/<id>` route serves the file whose
Content-Disposition names it -- verified per id, because neighbouring ids
return unrelated reports (CPI, FAAC): 1241422 = DEMOGRAPHIC_BULLETIN_2022_FINAL,
1241207 = DEMOGRAPHIC BULETIN 2021, 1241121 = DEMOGRAPHIC BULLETIN 2020.

WHAT IS READ (all series_type `projection`, credited "National Population
Commission"):

* 2022 Annex 1  national population by sex, 2006-2022;
* 2022 Annex 3  national population by five-year age group x sex, 2018-2022;
* 2022 Annex 2  national population by single year of age 0..79, 80+ x sex,
                2018-2022 -- emitted only for years whose ages add up (below);
* 2021 Annex 3  population by state (36 + FCT), 2018-2020, total only;
* 2020 Annex 1  population by state, 2016-2019, total only -- read for 2016
                and 2017 (2018-2019 are taken from the newer 2021 edition and
                must agree with this one, state by state).

2021 Annex 2 (national age groups 2018-2020) repeats 2022 Annex 3's totals and
is a check, not emitted. State tables' TOTAL rows are not emitted (the
national series comes from 2022 Annex 1); states must sum to it.

CHECKS, every run: Male + Female = Total on every row (within 2); five-year
bands sum to Annex 1 for each year and sex; states sum to Annex 1; the two
editions' state figures agree where they overlap.

PUBLISHED DEFECTS, PINNED (each raises if it disappears, so a corrected
reissue is noticed):
* 2020 Annex 1 prints the 2018 TOTAL as 191,625,349 -- its own states sum to
  196,042,933, the figure every other table carries. The state rows are fine;
  the TOTAL row is not emitted anyway.
* 2020 Annex 1 splits a figure: "4,4 17,584" (Adamawa 2018) = 4,417,584,
  re-joined by digit grouping and confirmed by the 2021 edition.
* 2022 Annex 2 spans three pages, each ending in its own "Source:" line,
  so the table is read until Annex 3 opens, not until the first Source line.
  Its single-year ages are checked to sum to Annex 1's total
  for each year; a year that fails is withheld whole (reported), never
  partially emitted.

CROSS-CHECK: 2022 216,783,381 (108,350,410 M / 108,432,971 F); 2006
140,431,790; Kano 2020 14,655,311; 0-04 2022 33,596,028.
"""
from __future__ import annotations

import re
import sys

import pandas as pd
import pdfplumber

_NUM = re.compile(r"^\d{1,3}(?:,\d{3})+$|^\d{1,3}$")


def _numbers(tokens: list[str]) -> list[float]:
    """Rebuild comma-grouped numbers, re-joining a figure the text layer split
    ("4,4" + "17,584" -> 4,417,584): a token that is not a well-formed
    grouping is glued to the next one until it is."""
    out, buf = [], ""
    for t in tokens:
        buf += t
        if _NUM.match(buf):
            out.append(float(buf.replace(",", "")))
            buf = ""
    if buf:
        raise ValueError(f"NBS: cannot rebuild a number from {buf!r}")
    return out


def _pages(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def _region(pages: list[str], caption: str, stop: str) -> list[str]:
    """Lines from `caption` until a line matching `stop`, across pages."""
    lines, on = [], False
    for text in pages:
        for ln in text.splitlines():
            s = ln.strip()
            if not on and caption in s and "...." not in s:
                on = True
                continue
            if on:
                if re.search(stop, s):
                    return lines
                lines.append(s)
    if not on:
        raise ValueError(f"NBS: {caption!r} not found")
    return lines


def _annex1(pages):
    rows = {}
    for s in _region(pages, "Annex 1: Nigeria Total Projected Population", r"^Source"):
        m = re.match(r"^(20\d\d)\s+(.+)$", s)
        if m:
            male, female, total = _numbers(m.group(2).split())
            if abs(male + female - total) > 2:
                raise ValueError(f"NBS Annex 1 {m.group(1)}: M+F != T")
            rows[m.group(1)] = (male, female, total)
    if sorted(rows) != [str(y) for y in range(2006, 2023)]:
        raise ValueError(f"NBS Annex 1: years {sorted(rows)}")
    return rows


def _by_age(pages, caption, stop, label_re, years_expected):
    years, out = None, {}
    for s in _region(pages, caption, stop):
        ys = re.findall(r"\b(20\d\d)\b", s)
        if len(ys) == len(years_expected) and not re.search(r"\d,\d", s):
            years = ys
            continue
        m = re.match(label_re, s)
        if not m or not years:
            continue
        vals = _numbers(m.group(2).split())
        if len(vals) != 3 * len(years):
            raise ValueError(f"NBS {caption[:20]}: {len(vals)} values in {s!r}")
        label = m.group(1)
        for i, y in enumerate(years):
            male, female, total = vals[3 * i:3 * i + 3]
            if abs(male + female - total) > 2:
                raise ValueError(f"NBS {caption[:20]} {label} {y}: M+F != T")
            out[(label, y)] = (male, female, total)
    return out


def _states(pages, caption, stop):
    years, out = None, {}
    for s in _region(pages, caption, stop):
        ys = re.findall(r"\b(20\d\d)\b", s)
        if ys and re.match(r"^(STATE|NIGERIA)\b", s):
            years = ys
            continue
        m = re.match(r"^([A-Z][A-Z ]+?)\s+([\d, ]+)$", s)
        if not m or not years:
            continue
        vals = _numbers(m.group(2).split())
        if len(vals) != len(years):
            raise ValueError(f"NBS {caption[:24]}: {len(vals)} values in {s!r}")
        for y, v in zip(years, vals):
            out[(m.group(1).strip(), y)] = v
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    books = {}
    for p in [local_path, *(extras or [])]:
        pages = _pages(p)
        # The edition is the first year on the COVER, whose title may be
        # letter-split ("Demographi c Statistics | Bulletin | 2022") or printed
        # after the year ("2021 | National Bureau of Statistics | DEMOGRAPHIC").
        cover = pages[0]
        ed = re.search(r"\b(20\d\d)\b", cover)
        if "demographicstatistic" not in re.sub(r"\s", "", cover).lower() or not ed:
            raise ValueError(f"NBS: {p} is not a Demographic Statistics Bulletin")
        books[ed.group(1)] = pages
    if not {"2022", "2021", "2020"} <= set(books):
        raise ValueError(f"NBS: editions {sorted(books)}")

    nat = _annex1(books["2022"])
    groups = _by_age(books["2022"], "Annex 3: Nigeria Projected Population by Age Group",
                     r"^(Source|Annex 4)", r"^(\d{1,2}-\d{2}|80\+|Total)\s+([\d, ]+)$",
                     ["2018", "2019", "2020", "2021", "2022"])
    singles = _by_age(books["2022"], "Annex 2: Nigeria Projected Population by Single Age",
                      r"^Annex 3", r"^(\d{1,2}|80\+)\s+([\d, ]+)$",
                      ["2018", "2019", "2020", "2021", "2022"])
    st21 = _states(books["2021"], "Annex 3: National Projected Population by State",
                   r"^(Source|SOURCE)")
    st20 = _states(books["2020"], "NIGERIAN PROJECTED POPULATION BY STATE",
                   r"^(Source|SOURCE)")

    out = []

    def emit(sex_vals, age, geo, year, code):
        for sex, v in zip(("male", "female", "total"), sex_vals):
            if v is None:
                continue
            out.append({"series_type": "projection", "sex": sex, "age_group": age,
                        "geography": geo, "period": year, "frequency": "annual",
                        "measure": "count", "value": v, "unit": "persons",
                        "series_code": code})

    for y, v in nat.items():
        emit(v, "Total", "Total country", y, "NBS DSB 2022 Annex 1")

    # five-year bands: must sum to Annex 1 for each year and sex
    bands = sorted({a for a, _ in groups if a != "Total"})
    for y in ["2018", "2019", "2020", "2021", "2022"]:
        for i in range(3):
            s = sum(groups[(a, y)][i] for a in bands)
            if abs(s - nat[y][i]) > 20:
                raise ValueError(f"NBS Annex 3 {y}: bands sum {s} != Annex 1 {nat[y][i]}")
        for a in bands:
            emit(groups[(a, y)], a, "Total country", y, "NBS DSB 2022 Annex 3")

    # single years: a year is emitted only if its ages add up
    ages = sorted({a for a, _ in singles}, key=lambda a: (a == "80+", int(a.rstrip("+"))))
    for y in ["2018", "2019", "2020", "2021", "2022"]:
        if len(ages) != 81 or any((a, y) not in singles for a in ages):
            raise ValueError(f"NBS Annex 2 {y}: {len(ages)} ages read")
        sums = [sum(singles[(a, y)][i] for a in ages) for i in range(3)]
        if any(abs(sums[i] - nat[y][i]) > 50 for i in range(3)):
            print(f"[nigeria] Annex 2 {y}: single ages sum to {sums[2]:,.0f}, "
                  f"Annex 1 says {nat[y][2]:,.0f} -- year withheld", file=sys.stderr)
            continue
        for a in ages:
            # 80+ is printed by BOTH annexes; it is emitted once (from Annex 3)
            # and the two printings must agree.
            if a == "80+":
                if singles[(a, y)] != groups[(a, y)]:
                    raise ValueError(f"NBS {y}: 80+ differs between Annex 2 "
                                     f"{singles[(a, y)]} and Annex 3 {groups[(a, y)]}")
                continue
            emit(singles[(a, y)], a, "Total country", y, "NBS DSB 2022 Annex 2")

    # states: 2021 edition for 2018-2020, 2020 edition for 2016-2017
    states = sorted({s for s, _ in st21 if s != "TOTAL"})
    if len(states) != 37:
        raise ValueError(f"NBS states: {len(states)} read")
    for (s, y), v in st20.items():
        if s != "TOTAL" and y in ("2018", "2019") and st21.get((s, y)) != v:
            raise ValueError(f"NBS states: {s} {y} 2020 edition {v} != 2021 edition "
                             f"{st21.get((s, y))}")
    # the pinned defect: 2020 edition's 2018 TOTAL row
    if st20.get(("TOTAL", "2018")) != 191625349.0:
        raise ValueError("NBS 2020 Annex 1: the 2018 TOTAL is no longer 191,625,349 "
                         "-- remove the pin")
    rows = {**{k: v for k, v in st20.items() if k[1] in ("2016", "2017")}, **st21}
    for y in ["2016", "2017", "2018", "2019", "2020"]:
        s = sum(rows[(st, y)] for st in states)
        if abs(s - nat[y][2]) > 50:
            raise ValueError(f"NBS states {y}: sum {s} != Annex 1 {nat[y][2]}")
        for st in states:
            ed = "2021" if y >= "2018" else "2020"
            emit((None, None, rows[(st, y)]), "Total", st.title() if st != "FCT" else "FCT",
                 y, f"NBS DSB {ed} state annex")
    return pd.DataFrame(out)
