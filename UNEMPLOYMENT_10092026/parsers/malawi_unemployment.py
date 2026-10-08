"""Malawi — NSO Malawi Labour Force Survey (MLFS) 2024 report, plus the 2018
Population and Housing Census economic tables (Series D).

THE 2024 MLFS IS THE PRIMARY SOURCE. NSO lists it as publication "Malawi
Labour Force Survey 2024" with three files: a brochure and a factsheet (chart
panels, not used -- the brochure's figures are bar labels beside an axis) and
the full report, which prints every headline cut as a table. Base 15-64 (NSO's
working-age definition). Tables taken:

* Table 0.1   summary counts by sex: working-age population, employed,
              unemployed, outside the labour force, labour force.
* Table 4.2   participation rate (and its working-age population) by sex x
              residence / region / age group / education.
* Table 5.1   employment-to-population ratio, same groups.
* Table 6.1   unemployment rate, time-related underemployment rate, LU2, LU3
              and LU4 by sex / residence / region / age / education.
* Tables 10.3, 10.6  youth NEET rates (15-35 and 15-24) by sex x residence /
              region.
* Tables 5.2 [sic -- the district annex reuses the number], 12.4, 12.5, 12.12,
  12.14: participation, employment ratio, underutilisation and NEET by
  district (and the four cities) x sex.

THE UNEMPLOYMENT RATE IS NSO'S BROAD MEASURE, AND IS FILED AS SUCH. Table 0.1
defines the unemployed as persons "without work and currently available to
work -- broad definition used in the report". (Chapter 4's prose speaks of
"actively seeking", but the summary table states which definition the report's
figures use.) So `unemployment_rate` rows carry definition "broad", and so do
LU2, LU3 and LU4. There is no strict rate in the report to pair it with.

READ BY LABEL, CHECKED BY ARITHMETIC: Table 0.1's labour force = employed +
unemployed, and population = labour force + outside; 5.1's denominators must
equal 4.2's; every national/"Malawi" row of a supporting table must equal the
summary or its first appearance (it is emitted once). WRAPPED LABELS are
rejoined against a known list -- "Lilongwe" / "City" in Table 12.4 would
otherwise publish Lilongwe City's ratio under rural Lilongwe district.

2018 CENSUS (Series D workbook, the one `labour/` reads): Tables D1 (age x
sex) and D2 (urban/rural, region, district x sex) give the population 15-64,
labour force, employed, unemployed and inactive; D4 splits the unemployed into
"seeking work" and "not seeking work" by age x sex. COUNTS ONLY -- the census
prints no rates and none is computed here. NOTE the census "unemployed"
includes 907 912 persons NOT seeking work (of 1 224 602): it is not the ILO
strict count. The rows carry definition not_applicable (NSO does not name the
definition) and the printed labels; the docstring and descriptor say what they
contain.

NOT COLLECTED: country-of-birth and functional-difficulty rows (no schema
column); 6.1's "potential labour force" rate (no matching topic -- the topic is
a count); the chapter 4/7 percentage distributions of the labour force and of
those outside it (shares, not rates); D5/D6 reasons for inactivity.

CROSS-CHECK: 2024 working-age population 10 996 589; labour force 5 319 370;
LFPR 48,4 (urban 58,6); EPR 38,8; unemployment rate 19,7 (female 23,0; Blantyre
33,2); LU4 55,5; NEET 15-35 41,4; Lilongwe City EPR 48,0 (Lilongwe 45,0).
2018 census: labour force 6 614 065; unemployed 1 224 602 (seeking 316 690).
"""
from __future__ import annotations

import os
import re

import openpyxl
import pandas as pd
import pdfplumber

from . import _common as C

_NUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?"
_SEX3 = [{}, {"sex": "male"}, {"sex": "female"}]
_SECTIONS = {"Sex": "sex", "Residence": "locality", "Region": "geography",
             "Age group": "age_group", "Highest education level": "education",
             "Highest education": "education", "Country of birth": "skip",
             "Country of Birth": "skip", "District": "geography"}
# Wrapped ROW-label tails. ("level" is NOT one: it is the tail of the section
# heading "Highest education / level", and glued to the row above it would
# publish the 55-64 age row as "55-64 level".)
_CONT = {"Preschool", "tertiary", "City"}
_DISTRICTS = ["Chitipa", "Karonga", "Nkhatabay", "Rumphi", "Mzimba", "Likoma",
              "Mzuzu City", "Kasungu", "Nkhotakota", "Nthisi", "Dowa", "Salima",
              "Lilongwe", "Mchinji", "Dedza", "Ntcheu", "Lilongwe City",
              "Mangochi", "Machinga", "Zomba", "Chiradzulu", "Blantyre", "Mwanza",
              "Thyolo", "Mulanje", "Phalombe", "Chikwawa", "Nsanje", "Balaka",
              "Neno", "Zomba City", "Blantyre City"]


def _f(x: str) -> float:
    return float(x.replace(",", ""))


def _table_text(pages: list[str], caption: str) -> list[str]:
    rx = re.compile(caption, re.M)
    for t in reversed(pages):          # last occurrence: not the list of tables
        m = rx.search(t)
        if m:
            body = t[m.end():]
            s = re.search(r"^Source:", body, re.M)
            return [ln.strip() for ln in (body[:s.start()] if s else body).splitlines()]
    raise ValueError(f"MLFS 2024: caption {caption!r} not found")


def _grouped(lines: list[str], n: int) -> list[tuple[str, str, list[float]]]:
    """(section, label, n numbers) for a table of sectioned rows; wrapped
    label tails are rejoined to the row above."""
    out, section = [], None
    for ln in lines:
        m = re.fullmatch(rf"(.*?)\s*((?:(?:{_NUM})\s*){{{n}}})", ln)
        if m and m.group(2).split() and len(m.group(2).split()) == n:
            out.append([section, m.group(1).strip(), [_f(x) for x in m.group(2).split()]])
            continue
        if ln in _SECTIONS:
            section = _SECTIONS[ln]
        elif ln == "Highest":
            section = "education"
        elif ln == "level":
            continue
        elif ln in _CONT and out:
            out[-1][1] = f"{out[-1][1]} {ln}".strip()
    return [tuple(r) for r in out]


def _ctx(section: str | None, label: str) -> dict | None:
    if label == "Malawi" or section is None:
        return {}
    if section == "skip":
        return None
    if section == "sex":
        return {"sex": C.normalise_sex(label)}
    if section == "locality":
        return {"locality": label.lower(), "locality_label": label}
    return {section: label}


class _Rows:
    def __init__(self):
        self.kw = dict(survey="Malawi Labour Force Survey (MLFS) 2024",
                       period="2024", reference_period="MLFS 2024",
                       frequency="ad_hoc", working_age_base="15-64")
        self.rows: list[dict] = []

    def add(self, topic, value, label, code, definition="not_applicable", **ctx):
        self.rows.append(C.row(topic=topic, value=value, series_label=label,
                               definition=definition, series_code=code,
                               **self.kw, **ctx))


def _mlfs_2024(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    o = _Rows()

    # Table 0.1 -- counts by sex. Labels wrap; each value line follows its
    # indicator's opening words.
    lines = _table_text(pages, r"^Table 0\.1: Summary of 2024 Labour Force Indicators")
    want = {"Working population": "working_age_population",
            "Employed persons": "employed", "Unemployed persons": "unemployed",
            "Outside labour force": "outside_labour_force",
            "Labour force": "labour_force"}
    t01 = {}
    for ln in lines:
        m = re.match(r"\d\s+(Working population|Employed persons|Unemployed persons|"
                     r"Outside labour force|Labour force)\b.*?"
                     rf"((?:{_NUM})\s+(?:{_NUM})\s+(?:{_NUM}))$", ln)
        if m:
            t01[m.group(1)] = [_f(x) for x in m.group(2).split()]
    if set(t01) != set(want):
        raise ValueError(f"MLFS T0.1: read {sorted(t01)}")
    for c in range(3):
        if abs(t01["Labour force"][c] - t01["Employed persons"][c]
               - t01["Unemployed persons"][c]) > 2:
            raise ValueError("MLFS T0.1: labour force != employed + unemployed")
        if abs(t01["Working population"][c] - t01["Labour force"][c]
               - t01["Outside labour force"][c]) > 2:
            raise ValueError("MLFS T0.1: population != labour force + outside")
    for lab, topic in want.items():
        for ctx, v in zip(_SEX3, t01[lab]):
            o.add(topic, v, lab, "MLFS2024 T0.1", **ctx)
    wap = t01["Working population"]

    def sexed(caption, topic, code, label, seen_pop=None, emit_pop=False,
              age=None, sections=None, expect=None):
        rows = _grouped(_table_text(pages, caption), 6)
        if expect and len(rows) != expect:
            raise ValueError(f"MLFS {code}: {len(rows)} rows, expected {expect}")
        pops = {}
        for section, lab, vals in rows:
            ctx = _ctx(section, lab)
            if ctx is None:
                continue
            if sections and section not in sections and lab != "Malawi":
                raise ValueError(f"MLFS {code}: unexpected row {section}/{lab}")
            for g, sx in enumerate(_SEX3):
                rate, pop = vals[2 * g], vals[2 * g + 1]
                pops[(lab, g)] = pop
                if lab == "Malawi" and topic in ("labour_force_participation_rate",
                                                 "employment_to_population_ratio"):
                    if pop != wap[g]:
                        raise ValueError(f"MLFS {code}: Malawi population {pop} != T0.1")
                c = {**ctx, **sx}
                if age:
                    c["age_group"] = age
                if lab == "Malawi" and seen_pop is not None and (lab, g) in seen_pop:
                    pass
                o.add(topic, rate, label, code, **c)
                if emit_pop and lab != "Malawi":
                    o.add("working_age_population", pop, "Number of individuals", code, **c)
        return rows, pops

    # 4.2 -- LFPR and its denominators; 5.1 -- EPR (denominators must agree).
    r42, p42 = sexed(r"^Table 4\.2: Labour force participation rates by sex, age",
                     "labour_force_participation_rate", "MLFS2024 T4.2",
                     "Labour force participation rate", emit_pop=True)
    r51, p51 = sexed(r"^Table 5\.1: Employment to population ratio by sex",
                     "employment_to_population_ratio", "MLFS2024 T5.1",
                     "Employment to population ratio")
    if p42 != p51:
        raise ValueError("MLFS: Table 5.1's populations differ from Table 4.2's")

    # 6.1 -- underutilisation, both sexes per row (sex is a section).
    cols61 = [("unemployment_rate", "broad", "Unemployment rate"),
              ("underemployment_rate", "not_applicable", "Time-related underemployment rate"),
              None,   # potential labour force (a rate; no matching topic)
              ("labour_underutilisation_rate", "broad",
               "Combined rate of time-related underemployment and unemployment"),
              ("labour_underutilisation_rate", "broad",
               "Combined rate of unemployment and potential labour force"),
              ("labour_underutilisation_rate", "broad",
               "Aggregate measure of labour underutilization")]

    def lu(caption, code, expect):
        rows = _grouped(_table_text(pages, caption), 6)
        if len(rows) != expect:
            raise ValueError(f"MLFS {code}: {len(rows)} rows, expected {expect}")
        out = {}
        for section, lab, vals in rows:
            ctx = _ctx(section, lab)
            if ctx is None:
                continue
            out[lab] = vals
            for spec, v in zip(cols61, vals):
                if spec:
                    o.add(spec[0], v, spec[2], code, spec[1], **ctx)
        return out

    lu61 = lu(r"^Table 6\.1: Labour Underutilization", "MLFS2024 T6.1", 19)

    # 10.3 / 10.6 -- NEET.
    sexed(r"^Table 10\.3: Youth \(15 to 35\) Not in Employment", "neet_rate",
          "MLFS2024 T10.3", "NEET", age="15-35")
    sexed(r"^Table 10\.6: Youth \(15 to 24\) Not in Employment", "neet_rate",
          "MLFS2024 T10.6", "NEET", age="15-24")

    # District annex: its "Malawi" rows repeat the national tables -- checked,
    # not re-emitted.
    def district(caption, topic, code, label, age=None, national=None):
        rows = _grouped(_table_text(pages, caption), 6)
        got = [lab for _, lab, _ in rows]
        if got != ["Malawi"] + _DISTRICTS:
            raise ValueError(f"MLFS {code}: districts read {got}")
        for _, lab, vals in rows:
            if lab == "Malawi":
                if national is not None and [vals[0], vals[2], vals[4]] != national:
                    raise ValueError(f"MLFS {code}: Malawi row != national table")
                continue
            for g, sx in enumerate(_SEX3):
                c = {"geography": lab, **sx}
                if age:
                    c["age_group"] = age
                o.add(topic, vals[2 * g], label, code, **c)

    def nat(rows):
        return next([v[0], v[2], v[4]] for s, lab, v in rows if lab == "Malawi")

    district(r"^Table 5\.2: Labour force participation rates by district",
             "labour_force_participation_rate", "MLFS2024 T5.2 (district annex)",
             "Labour force participation rate", national=nat(r42))
    district(r"^Table 12\.4: Employment to population ratio by district",
             "employment_to_population_ratio", "MLFS2024 T12.4",
             "Employment to population ratio", national=nat(r51))
    district(r"^Table 12\.12: Youth \(15 to 35\) Not in Employment", "neet_rate",
             "MLFS2024 T12.12", "NEET", age="15-35")
    district(r"^Table 12\.14: Youth \(15 to 24\) Not in Employment", "neet_rate",
             "MLFS2024 T12.14", "NEET", age="15-24")

    rows = _grouped(_table_text(pages, r"^Table 12\.5: Labour Underutilization"), 6)
    got = [lab for _, lab, _ in rows]
    if got != ["Malawi"] + _DISTRICTS:
        raise ValueError(f"MLFS T12.5: districts read {got}")
    for _, lab, vals in rows:
        if lab == "Malawi":
            if vals != lu61["Malawi"]:
                raise ValueError("MLFS T12.5: Malawi row != Table 6.1")
            continue
        for spec, v in zip(cols61, vals):
            if spec:
                o.add(spec[0], v, spec[2], "MLFS2024 T12.5", spec[1], geography=lab)
    return o.rows


# ---------------------------------------------------------------------------
# 2018 census, Series D workbook
# ---------------------------------------------------------------------------

def _census_2018(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    kw = dict(survey="2018 Malawi Population and Housing Census (Series D)",
              period="2018", reference_period="2018 MPHC", frequency="ad_hoc",
              working_age_base="15-64")
    out = []

    def add(topic, v, label, code, **ctx):
        out.append(C.row(topic=topic, value=v, series_label=label,
                         definition="not_applicable", series_code=code, **kw, **ctx))

    blocks = [("working_age_population", "Population", 1),
              ("labour_force", "Economically Active (Labour Force)", 4),
              ("employed", "Employed", 7), ("unemployed", "Unemployed", 10)]

    def rows_of(sheet):
        # Data rows are the ones with a label and a number; header depth
        # differs by sheet (D4 has one header row fewer than D1/D2).
        return [r for r in wb[sheet].iter_rows(min_row=2, values_only=True)
                if r[0] is not None and isinstance(r[1], (int, float))]

    nat = None
    for sheet, code in (("D1", "MPHC2018 D1"), ("D2", "MPHC2018 D2")):
        for r in rows_of(sheet):
            lab = str(r[0]).strip()
            vals = list(r[1:14])
            for i in (0, 3, 6, 9):
                if vals[i] != vals[i + 1] + vals[i + 2]:
                    raise ValueError(f"{code} {lab}: male + female != total")
            if vals[3] != vals[6] + vals[9]:
                raise ValueError(f"{code} {lab}: labour force != employed + unemployed")
            if vals[0] != vals[3] + vals[12]:
                raise ValueError(f"{code} {lab}: population != active + inactive")
            if lab == "Malawi":
                if nat is not None:
                    if vals != nat:
                        raise ValueError(f"{code}: Malawi row differs from D1")
                    continue
                nat, ctx = vals, {}
            elif sheet == "D1":
                ctx = {"age_group": re.sub(r"\s+", "", lab)}
            elif lab in ("Urban", "Rural"):
                ctx = {"locality": lab.lower(), "locality_label": lab}
            else:
                ctx = {"geography": lab}
            for topic, label, j in blocks:
                for k, sx in enumerate(_SEX3):
                    add(topic, vals[j - 1 + k], label, code, **ctx, **sx)
            add("outside_labour_force", vals[12], "Economically Inactive", code, **ctx)

    # D4: unemployed seeking / not seeking work, by age within each sex block.
    sex = {}
    d4 = rows_of("D4")
    if [str(r[0]).strip() for r in d4].count("Total") != 1:
        raise ValueError("MPHC2018 D4: national Total row not read")
    for r in d4:
        lab = str(r[0]).strip()
        if lab in ("Total", "Male", "Females"):
            sex = {"Total": {}, "Male": {"sex": "male"}, "Females": {"sex": "female"}}[lab]
            ctx = dict(sex)
        else:
            ctx = {**sex, "age_group": re.sub(r"\s+", "", lab)}
        lf, unemp, seek, noseek = r[1:5]
        if unemp != seek + noseek:
            raise ValueError(f"MPHC2018 D4 {lab}: seeking + not seeking != unemployed")
        add("unemployed", seek, "Unemployed - Seeking Work", "MPHC2018 D4", **ctx)
        add("unemployed", noseek, "Unemployed - Not Seeking Work", "MPHC2018 D4", **ctx)
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        if p.lower().endswith(".xlsx"):
            rows += _census_2018(p)
        else:
            rows += _mlfs_2024(p)
    return pd.DataFrame(rows)
