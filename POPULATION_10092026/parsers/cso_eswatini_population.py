"""Eswatini — CSO "2017-2038 Population Projection, based on the 2017 Eswatini
Population and Housing Census" (August 2020), via a Wayback `id_` copy.

WHY THE WAYBACK MACHINE. The CSO's files are hosted on gov.sz, which times out
on connect (and eswatinistats.org.sz never answers) -- the same reason the GDP
descriptor reads the CSO's national accounts through the archive. The `id_`
capture returns the original bytes of the CSO's own PDF
(gov.sz/images/Final-2017_2038-POPULATION-PROJECTIONS-1-1.pdf); nothing is
re-hosted or re-estimated.

WHAT IS READ:

* Table 2.1  the 2017 census ENUMERATED population by region and sex (Hhohho,
             Manzini, Shiselweni, Lubombo, and Eswatini) -> `census`, 2017.
             The table's other half ("Base Population, adjusted and moved to
             1 July 2017") is the projection base and is the 2017 column of
             Table 5.2; it is not emitted twice. The Urban / Rural rows have
             no home (no residence column).
* Table 5.2  national population by five-year age group 0-4 .. 80+ and Total,
             by sex, medium variant, 2017-2038 -> `projection`.

THE NUMBERS USE SPACE THOUSANDS SEPARATORS, so "538 957 567 494 1 106 451"
reads more than one way. Each row is split under its own arithmetic: every
reading is enumerated (a number is a 1-3 digit head plus 3-digit groups) and
the one where Male + Female = Both Sexes for every year is taken; a row with
no such reading, or more than one, raises. Each year's bands must then sum to
its Total.

NOT YET READ, with the reason:
* Table 5.6 (regions by five-year age group x sex) -- its pages are ROTATED
  and the text layer comes out character-reversed ("latoT", "initawsE");
  readable with PyMuPDF word positions, not yet laid out.
* Table 5.5 (regions by sex, 2017-2038) -- carries published defects: Manzini
  2018 prints Both sexes "65 822" (its Male + Female = 365 822), and the 2033
  column breaks trend for Manzini and Shiselweni. Needs cell-level pinning.
* The full census report (gov.sz/images/planningministry/census2017.pdf,
  20 MB, also archived) -- age x sex by region, not yet laid out.

CROSS-CHECK: census 2017 enumerated 1 093 238 (531 111 M / 562 127 F),
Manzini 355 945; projection 2017 1 106 451, 2038 1 432 235.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber


def _readings(tokens: list[str], n: int) -> list[list[int]]:
    """Every way to read `tokens` as `n` space-grouped numbers."""
    out = []

    def go(i, acc):
        if len(acc) == n:
            if i == len(tokens):
                out.append(acc)
            return
        if i >= len(tokens) or not re.fullmatch(r"\d{1,3}", tokens[i]):
            return
        val = tokens[i]
        go(i + 1, acc + [int(val)])
        j = i + 1
        while j < len(tokens) and re.fullmatch(r"\d{3}", tokens[j]) and j - i < 3:
            val += tokens[j]
            go(j + 1, acc + [int(val)])
            j += 1
    go(0, [])
    return out


def _split_triples(tokens: list[str], years: int, where: str) -> list[tuple[int, int, int]]:
    good = [r for r in _readings(tokens, 3 * years)
            # within 2: the ADJUSTED base rounds independently (Lubombo
            # 105 954 + 109 151 = 215 105, printed 215 106); the reading must
            # still be unique, so tolerance cannot admit a wrong split silently.
            if all(abs(r[3 * k] + r[3 * k + 1] - r[3 * k + 2]) <= 2
                   for k in range(years))]
    if len(good) != 1:
        raise ValueError(f"CSO Eswatini {where}: {len(good)} readings satisfy "
                         f"M + F = T for {' '.join(tokens)!r}")
    r = good[0]
    return [tuple(r[3 * k:3 * k + 3]) for k in range(years)]


def _table_2_1(pages: list[str]) -> list[dict]:
    text = next(t for t in pages if "Table 2.1 Enumerated and adjusted" in t)
    body = text[text.index("Table 2.1 Enumerated and adjusted"):]
    rows = []
    for ln in body.splitlines():
        m = re.match(r"^(Eswatini|Hhohho|Manzini|Shiselweni|Lubombo)\s+([\d ]+)$",
                     ln.strip())
        if not m:
            continue
        (enum, base) = _split_triples(m.group(2).split(), 2, f"T2.1 {m.group(1)}")
        rows.append({"geo": m.group(1), "enum": enum, "base": base})
    if [r["geo"] for r in rows] != ["Eswatini", "Hhohho", "Manzini",
                                     "Shiselweni", "Lubombo"]:
        raise ValueError(f"CSO Eswatini T2.1: rows {[r['geo'] for r in rows]}")
    nat = rows[0]["enum"]
    for i in range(3):
        if sum(r["enum"][i] for r in rows[1:]) != nat[i]:
            raise ValueError("CSO Eswatini T2.1: regions do not sum to Eswatini")
    return rows


def _table_5_2(pages: list[str]) -> dict:
    out, years = {}, None
    on = False
    for text in pages:
        if "Table 5.2: Projected National Population by Five-Year" in text:
            on = True
        elif on and re.search(r"Table 5\.3:", text):
            break
        if not on or "...." in text:
            continue
        for ln in text.splitlines():
            s = ln.strip()
            # "2017 2018 2019", or "Age 2026 2027 2028" on one block
            if re.fullmatch(r"(?:Age\s+)?(?:20\d\d\s*){1,3}", s):
                years = re.findall(r"20\d\d", s)
                continue
            # bands print with a hyphen or, in the 2029-2031 block, an EN DASH ("0 - 4")
            m = re.match(r"^(\d{1,2}\s*[-–]\s*\d{1,2}|80\+|Total)\s+([\d ]+)$", s)
            if m and years:
                band = re.sub(r"\s+", "", m.group(1)).replace("–", "-")
                for y, trip in zip(years, _split_triples(m.group(2).split(),
                                                          len(years), f"T5.2 {band}")):
                    out[(band, y)] = trip
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with pdfplumber.open(local_path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    t21 = _table_2_1(pages)
    t52 = _table_5_2(pages)
    years = sorted({y for _, y in t52})
    if years != [str(y) for y in range(2017, 2039)]:
        raise ValueError(f"CSO Eswatini T5.2: years {years}")
    for y in years:
        bands = [b for b, yy in t52 if yy == y and b != "Total"]
        if len(bands) != 17:
            raise ValueError(f"CSO Eswatini T5.2 {y}: {len(bands)} bands")
        for i in range(3):
            if sum(t52[(b, y)][i] for b in bands) != t52[("Total", y)][i]:
                raise ValueError(f"CSO Eswatini T5.2 {y}: bands != Total")
    # Table 2.1's base population is Table 5.2's 2017 column
    if t21[0]["base"] != t52[("Total", "2017")]:
        raise ValueError("CSO Eswatini: T2.1 base != T5.2 2017")

    out = []

    def emit(trip, age, geo, year, series, code):
        for sex, v in zip(("male", "female", "total"), trip):
            out.append({"series_type": series, "sex": sex, "age_group": age,
                        "geography": geo, "period": year, "frequency": "annual",
                        "measure": "count", "value": float(v), "unit": "persons",
                        "series_code": code})

    for r in t21:
        emit(r["enum"], "Total", "Total country" if r["geo"] == "Eswatini"
             else r["geo"], "2017", "census", "CSO Projections 2017-2038 T2.1 (enumerated)")
    for (band, y), trip in t52.items():
        emit(trip, band, "Total country", y, "projection",
             "CSO Projections 2017-2038 T5.2")
    return pd.DataFrame(out)
