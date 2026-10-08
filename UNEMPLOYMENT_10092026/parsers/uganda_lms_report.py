"""Uganda — UBOS Labour Market Survey 2025, MAIN REPORT (247 pages): the
headline series by location, education, age and the 14 sub-regions.

THE DECK `uganda_unemployment` READS GIVES EIGHT NATIONAL FIGURES; THE REPORT
TABULATES THEM. `labour/` already retains the main report for its composition
tables, and its rate tables are read here:

    15+ (ILO), annual        Table 3.1 EPR, 4.1 LU1, 4.3 LU2, 4.5 LU3, 4.7 LU4,
                             5.2 LFPR
    15-24 youth, annual      Table 6.3 EPR, 6.4 LU1, 6.7 LFPR
    14-64 (National          Annex A4.5 EPR, A4.6 LFPR, A4.10 LU1, A4.12 LU2,
    Employment Policy)       A4.14 LU3, A4.16 LU4 -- "Overall" columns
    18-30 youth (national)   Annex A6.1 EPR, A6.2 LU1, A6.3 LFPR -- "Overall"

TWO WORKING-AGE DEFINITIONS, NEVER MIXED: UBOS publishes the same indicators
on the ILO 15+ and the national 14-64 base, each with its own youth band
(15-24, 18-30). `working_age_base` and `age_group` carry which; 12.2% and
12.4% are both "the" unemployment rate.

THE TWO SURVEY WAVES ARE NOT COLLECTED. The annexes print March-May and
June-August 2025 beside the Overall; those windows straddle quarter boundaries
and fit no period this schema has (the same call `labour/` made for A4.7).
Annex A3 (15+) prints ONLY the waves, so the 15+ series comes from the
chapter tables, which give the annual figure.

ROWS: Location (-> locality), Education level attained (-> education), Age
groups (-> age_group), Sub regions (-> geography), National. Disability status
has no column here and is not collected. In the youth tables an Age-groups
section (15-19, 20-24) repeats the 15+ table's rows for those bands; it is
checked equal and not emitted twice.

NOT DUPLICATED WITH THE DECK: four national values -- LU1 15+ 12.2, LU1 14-64
12.4, youth 15-24 17.9, youth 18-30 16.2 -- are already collected from the
deck under its own labels. The report's National rows for those are checked
EQUAL to the deck's and not emitted; a disagreement raises.

TOPICS as elsewhere: LU1 -> unemployment_rate (strict; youth band ->
youth_unemployment_rate); LU2-LU4 -> labour_underutilisation_rate (broad); EPR
(not_applicable), LFPR (strict). Table 4.4 (rate of potential labour force)
has no topic and is not collected.

GUARDS: each table must yield its National row, at least 12 sub-regions and
both locations; every row must carry exactly 3 (chapter) or 9 (annex) values;
male and female must bracket the total in every row.

CROSS-CHECK: EPR 15+ 44.7 (male 53.1); LU2 15+ 19.9; LU4 15+ 41.6; LFPR 15+
50.9; youth 15-24 EPR 29.6, LFPR 36.0; LU1 15+ Bukedi 23.7, Bunyoro 4.5;
14-64 LU1 Overall Kampala 15.0; 18-30 LFPR 53.8.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_SURVEY = "Labour Market Survey 2025"
_SPECS = [
    # caption regex, topic, definition, series_label, base, age, ncols
    (r"^Table 3\.1: Employment-to-Population Ratio \(15 years and above\)",
     "employment_to_population_ratio", "not_applicable",
     "Employment-to-Population Ratio", "15+", "Total", 3),
    (r"^Table 4\.1: Unemployment Rate \(LU1\) among persons aged 15 and above",
     "unemployment_rate", "strict", "Unemployment Rate (LU1)", "15+", "Total", 3),
    (r"^Table 4\.3: Combined Rate of Unemployment and Time Related Underemployment",
     "labour_underutilisation_rate", "broad",
     "Combined Rate of Unemployment and Time Related Underemployment (LU2)",
     "15+", "Total", 3),
    (r"^Table 4\.5: Combined Rate of Unemployment and Potential Labour Force",
     "labour_underutilisation_rate", "broad",
     "Combined Rate of Unemployment and Potential Labour Force (LU3)",
     "15+", "Total", 3),
    (r"^Table 4\.7: The Composite measure of Labour underutilization",
     "labour_underutilisation_rate", "broad",
     "Composite measure of Labour underutilization (LU4)", "15+", "Total", 3),
    (r"^Table 5\.2: Labour Force Participation Rate \(15 years and above\)",
     "labour_force_participation_rate", "strict",
     "Labour Force Participation Rate", "15+", "Total", 3),
    (r"^Table 6\.3: Youth Employment-to-Population Ratio",
     "employment_to_population_ratio", "not_applicable",
     "Youth Employment-to-Population Ratio", "15+", "15-24", 3),
    (r"^Table 6\.4: Youth Unemployment Rate \(LU1\) among persons aged 15-24",
     "youth_unemployment_rate", "strict", "Youth Unemployment Rate (LU1)",
     "15+", "15-24", 3),
    (r"^Table 6\.7: Youth \(15-24 years\) Labour Force Participation Rate",
     "labour_force_participation_rate", "strict",
     "Youth Labour Force Participation Rate", "15+", "15-24", 3),
    (r"^Table A4\.5: Employment-to-Population Ratio \(14-64 years\)",
     "employment_to_population_ratio", "not_applicable",
     "Employment-to-Population Ratio", "14-64", "Total", 9),
    (r"^Table A4\.6: Labour Force Participation Rate \(14- ?64 years\)",
     "labour_force_participation_rate", "strict",
     "Labour Force Participation Rate", "14-64", "Total", 9),
    (r"^Table A4\.10: Unemployment Rate \(LU1\) by Selected Characteristics \(14-64",
     "unemployment_rate", "strict", "Unemployment Rate (LU1)", "14-64", "Total", 9),
    (r"^Table A4\.12: Combined Rate of Unemployment and Time Related Underemployment",
     "labour_underutilisation_rate", "broad",
     "Combined Rate of Unemployment and Time Related Underemployment (LU2)",
     "14-64", "Total", 9),
    (r"^Table A4\.14: Combined Rate of Unemployment and Potential Labour Force",
     "labour_underutilisation_rate", "broad",
     "Combined Rate of Unemployment and Potential Labour Force (LU3)",
     "14-64", "Total", 9),
    (r"^Table A4\.16: The Composite measure of Labour underutilization",
     "labour_underutilisation_rate", "broad",
     "Composite measure of Labour underutilization (LU4)", "14-64", "Total", 9),
    (r"^Table A6\.1: Youth Employment-to-Population Ratio",
     "employment_to_population_ratio", "not_applicable",
     "Youth Employment-to-Population Ratio", "14-64", "18-30", 9),
    (r"^Table A6\.2: Youth Unemployment Rate \(LU1\)",
     "youth_unemployment_rate", "strict", "Youth Unemployment Rate (LU1)",
     "14-64", "18-30", 9),
    (r"^Table A6\.3: Youth Labour Force Participation Rate",
     "labour_force_participation_rate", "strict",
     "Youth Labour Force Participation Rate", "14-64", "18-30", 9),
]
# National values the deck already carries: (topic, base, age) -> value.
_DECK = {("unemployment_rate", "15+", "Total"): 12.2,
         ("unemployment_rate", "14-64", "Total"): 12.4,
         ("youth_unemployment_rate", "15+", "15-24"): 17.9,
         ("youth_unemployment_rate", "14-64", "18-30"): 16.2}
_SECTIONS = {"location": "locality", "education level attained": "education",
             "disability status": "skip", "age groups": "age",
             "sub regions": "geography", "sub region": "geography"}
_NUM = r"(?:\d{1,3}(?:\.\d)?|-)"
_FURNITURE = re.compile(r"^(?:LMS 2025 Report|Characteristics?\b|Male Female|"
                        r"March-May|\(?%\)?$)")


def _lines(path: str) -> list[str]:
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[20:]:             # past the lists of tables
            out += [ln.strip() for ln in (page.extract_text() or "").splitlines()]
    return out


def _region(lines, caption, ncols, where):
    """Rows (section, label, values) from the first caption occurrence whose
    body reaches a National row -- a caption at a page foot opens nothing."""
    row_re = re.compile(rf"^(.*?)\s*((?:{_NUM}\s+){{{ncols - 1}}}{_NUM})$")
    for start in [i for i, ln in enumerate(lines) if re.search(caption, ln)]:
        section, rows, pending = None, [], ""
        for ln in lines[start + 1:start + 120]:
            if re.match(r"^Table [A-Z]?\d", ln):
                break
            if not ln or _FURNITURE.match(ln):
                continue
            key = ln.lower().rstrip(":")
            if key in _SECTIONS:
                section, pending = _SECTIONS[key], ""
                continue
            m = row_re.match(ln)
            if m:
                label = f"{pending} {m.group(1)}".strip()
                vals = [None if v == "-" else float(v) for v in m.group(2).split()]
                pending = ""
                if label == "National":
                    rows.append((None, label, vals))
                    return rows
                rows.append((section, label, vals))
            elif re.match(r"^[a-z(]", ln) and rows:
                s_, l_, v_ = rows[-1]               # "above" -- a label's tail
                rows[-1] = (s_, f"{l_} {ln}", v_)
            elif not re.search(r"\d", ln):
                pending = f"{pending} {ln}".strip()  # a label's head
        # no National row: try the next occurrence
    raise ValueError(f"{where}: no table body ending in a National row")


def _age(label: str) -> str:
    return label.replace("–", "-").replace(" ", "")


def _tid(caption: str) -> str:
    """The table id of a caption regex, e.g. "A4.10"."""
    m = re.search(r"Table ([A-Z]?\d+)\\.(\d+)", caption)
    return f"{m.group(1)}.{m.group(2)}"


def parse_report(path: str) -> list[dict]:
    lines = _lines(path)
    out, seen_age = [], {}
    for caption, topic, definition, slabel, base, age, ncols in _SPECS:
        where = f"UBOS LMS 2025 T{_tid(caption)}"
        rows = _region(lines, caption, ncols, where)
        geos = [r for r in rows if r[0] == "geography"]
        locs = {r[1] for r in rows if r[0] == "locality"}
        if len(geos) < 12 or not {"Rural", "Urban"} <= locs:
            raise ValueError(f"{where}: {len(geos)} sub-regions, locations {locs}")
        for section, label, vals in rows:
            m, f, t = vals[-3:]                  # chapter: M F T; annex: Overall
            if section == "skip":
                continue
            if None not in (m, f, t) and not min(m, f) - 0.15 <= t <= max(m, f) + 0.15:
                raise ValueError(f"{where} {label!r}: total {t} outside {m}/{f}")
            ctx = {"age_group": age}
            if section == "locality":
                ctx.update(locality=label.lower(), locality_label=label)
            elif section == "education":
                ctx["education"] = label
            elif section == "geography":
                ctx["geography"] = label
            elif section == "age":
                band = _age(label)
                key = (topic.replace("youth_", ""), base, band)
                if age != "Total":
                    # A youth table's age rows repeat the 15+ table's.
                    if key in seen_age and seen_age[key] != (m, f, t):
                        raise ValueError(f"{where}: {band} differs from the 15+ table")
                    continue
                seen_age[(topic, base, band)] = (m, f, t)
                ctx["age_group"] = band
            elif section is None:
                deck = _DECK.get((topic, base, age))
                if deck is not None:
                    if abs(deck - t) > 0.05:
                        raise ValueError(f"{where}: National {t} != deck {deck}")
                    vals = [m, f, None]          # the total is the deck's row
            for sex, v in zip(("male", "female", "total"), vals[-3:]):
                if v is None:
                    continue
                out.append({
                    "topic": topic, "definition": definition,
                    "series_label": slabel, "sex": sex,
                    "age_group": ctx.get("age_group", "Total"),
                    "education": ctx.get("education", "Total"),
                    "geography": ctx.get("geography", "Total country"),
                    "locality": ctx.get("locality", "all"),
                    "locality_label": ctx.get("locality_label", "Total"),
                    "working_age_base": base, "period": "2025",
                    "reference_period": "2025" if ncols == 3 else "2025 (Overall)",
                    "frequency": "ad_hoc", "measure": "rate", "value": float(v),
                    "unit": "percent", "survey": _SURVEY,
                    "series_code": f"UBOS LMS T{_tid(caption)}",
                })
    return out
