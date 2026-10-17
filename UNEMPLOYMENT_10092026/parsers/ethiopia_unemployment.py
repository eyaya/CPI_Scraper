"""Ethiopia — unemployment / labour-force layout and parser.

One module per country, as everywhere else in this repo. The layout is
declarative and read by `pdf_key_indicators.make_parser`; the comments beside
it record the report's actual column order and the cross-check values used to
prove the layout still holds.
"""
from __future__ import annotations

import re  # noqa: F401  -- some layouts build their rows with it

from ._vocab import *  # noqa: F401,F403
from .pdf_key_indicators import make_parser

LAYOUTS: dict[str, dict] = {}

# =========================================================================
# ETHIOPIA -- ESS, Labour Force and Migration Survey 2021.
# Summary Table 1A: rows are Region x Sex, columns are three indicators x four
# survey periods (Mar-99, Mar-05, Jun-13, Feb-21) = twelve numeric columns.
# Only the CURRENT period (Feb-21) is captured from each indicator block.
#
# WORKING-AGE BASE IS 10+, not 15+ -- confirmed by ST3's own caption,
# "(Age 10 years and above)". Ethiopian rates are not comparable with a 15+
# series without saying so, and the base travels on every row.
#
# TWO BLANK PATTERNS the parser must survive, and they sit at opposite ends of
# a row: TIGRAY is excluded from the 2021 round (its Feb-21 cells are blank at
# the row TAIL), and SIDAMA did not exist as a region before 2020 (its 1999,
# 2005 and 2013 cells are blank at the row HEAD). Reading from the end of the
# line handles Sidama; Tigray simply produces too few numbers and is skipped
# rather than misaligned -- which is the correct outcome, since Tigray has no
# 2021 estimate to report.
#
# Printed typos preserved: ST3's caption reads "Economically Activity Persons".
#
# CROSS-CHECK (Country Total, Feb-21): LFPR 64.7 (M 72.6 / F 56.8);
# EPR 59.5 (M 69.0 / F 50.2); unemployment 8.0 (M 5.0 / F 11.7).
# Addis Ababa unemployment 22.1; Dire Dawa 15.9; Sidama 5.5.
# ST3 country total: economically active 45,245,760; employed 41,637,071;
# unemployed 3,608,688; urban unemployment 17.9; rural 5.2.
# =========================================================================
_ET_CURRENT = [{"skip": True}] * 3 + [{}]      # keep only the 4th (Feb-2021)

_ET_REGIONS = [
    {"match": r"^Country[- ]?Total", "geography": "Total country"},
    {"match": r"^Afar\b", "geography": "Afar"},
    {"match": r"^Amhara\b", "geography": "Amhara"},
    {"match": r"^Oromia\b", "geography": "Oromia"},
    {"match": r"^Somali\b", "geography": "Somali"},
    {"match": r"^Benishangul", "geography": "Benishangul-Gumuz"},
    {"match": r"^SNNP\b", "geography": "SNNP"},
    {"match": r"^Sidama\b", "geography": "Sidama"},
    {"match": r"^Gambella\b", "geography": "Gambella"},
    {"match": r"^Harari\b", "geography": "Harari"},
    {"match": r"^Addis Ababa", "geography": "Addis Ababa"},
    {"match": r"^Dire Dawa", "geography": "Dire Dawa"},
]

LAYOUTS["ethiopia"] = {
    "survey": "Labour Force and Migration Survey (LMS)",
    "frequency": "ad_hoc",
    "working_age_base": "10+",
    "decimal": ".",
    "period": "2021",
    "reference_period": "February 2021",
    "tables": [{
        # Summary Table 3: economically active / employed / unemployed counts
        # plus the unemployment rate, by region and by urban/rural.
        "page_contains": ["economically activity persons of regions"],
        "take": "trailing",
        "columns": [
            {"topic": "labour_force", "sex": "total"},
            {"topic": "labour_force", "sex": "male"},
            {"topic": "labour_force", "sex": "female"},
            {"topic": "employed", "sex": "total"},
            {"topic": "employed", "sex": "male"},
            {"topic": "employed", "sex": "female"},
            {"topic": "unemployed", "sex": "total"},
            {"topic": "unemployed", "sex": "male"},
            {"topic": "unemployed", "sex": "female"},
            {"topic": "unemployment_rate", "definition": "strict", "sex": "total"},
            {"topic": "unemployment_rate", "definition": "strict", "sex": "male"},
            {"topic": "unemployment_rate", "definition": "strict", "sex": "female"},
        ],
        "defaults": {"label": "Economically active / employed / unemployed"},
        "rows": _ET_REGIONS + [
            {"match": r"^Urban\b", "locality": "urban", "locality_label": "Urban"},
            {"match": r"^Rural\b", "locality": "rural", "locality_label": "Rural"},
        ],
    }],
}


LAYOUT = LAYOUTS['ethiopia']
_engine = make_parser(LAYOUT)


# =========================================================================
# EARLIER ROUNDS -- Summary Tables 1A (national), 1B (urban), 1C (rural).
# Added 2026-10-12. The same annex prints, for every region x sex, the
# participation rate, employment-to-population ratio and unemployment rate for
# FOUR survey rounds side by side: the national LFS/LMS rounds March 1999,
# March 2005, June 2013, February 2021 (1A, 1C), and the urban UEUS rounds
# April 2016, June 2018, January 2020 plus February 2021 (1B). Those are the
# NSO's own published estimates for each round, so each column is dated to its
# own round -- not interpolated.
#
# Base 10+, as for ST3. "-" is a missing cell (Tigray absent from 2021; Sidama
# created in 2020) and is never read as 0.
#
# NOT DOUBLE-COUNTED: ST3 above already emits the 2021 unemployment rate for
# some regions by sex. A 1A/1B/1C 2021 rate for the same region x sex x
# locality is skipped (the figures agree; only the label would differ).
#
# CROSS-CHECK (Country Total): 1A unemployment 8.0 / 5.0 / 4.5 / 8.0
# (1999/2005/2013/2021); LFPR 1999 75.1; 1B urban unemployment 2016 16.9,
# 2018 19.1, 2020 18.7; Addis Ababa urban 2016 21.0.
# =========================================================================
import pdfplumber as _pdfplumber
import pandas as _pd

_ST1 = {
    "1A": ("all", "Total", [("1999", "March 1999"), ("2005", "March 2005"),
                            ("2013", "June 2013"), ("2021", "February 2021")]),
    "1B": ("urban", "Urban", [("2016", "April 2016"), ("2018", "June 2018"),
                              ("2020", "January 2020"), ("2021", "February 2021")]),
    "1C": ("rural", "Rural", [("1999", "March 1999"), ("2005", "March 2005"),
                              ("2013", "June 2013"), ("2021", "February 2021")]),
}
_ST1_REGION = {
    "country": "Total country", "tigray": "Tigray", "afar": "Afar",
    "amhara": "Amhara", "oromia": "Oromia", "somali": "Somali",
    "beni - gumuz": "Benishangul-Gumuz", "benishangul - gumuz": "Benishangul-Gumuz",
    "snnp": "SNNP", "snnp -": "SNNP", "sidama": "Sidama", "gambella": "Gambella",
    "harari": "Harari", "addis ababa city admin.": "Addis Ababa",
    "dire dawa admin.": "Dire Dawa",
}
_ST1_TOPICS = [("labour_force_participation_rate", "not_applicable",
                "Activity rate / labour force participation rate"),
               ("employment_to_population_ratio", "not_applicable",
                "Employment to population ratio"),
               ("unemployment_rate", "strict", "Unemployment rate")]
_ST1_ROW = re.compile(r"^(Total|Male|Female)\s+((?:[\d.]+|-)(?:\s+(?:[\d.]+|-)){11})\s*$")
_ST1_SKIP = re.compile(r"^(Activity|Region|Participation|Sex|Unemployment|"
                       r"KEY FINDINGS|\d{4} LABOUR|Febru|and Sex|Population|TOTAL$|URBAN$|RURAL$)", re.I)


def _st1_sections(path: str) -> dict:
    with _pdfplumber.open(path) as pdf:
        text = "\n".join((pg.extract_text() or "") for pg in pdf.pages[23:30])
    out, cur = {}, None
    for ln in text.splitlines():
        m = re.match(r"^Summary Table (\w+)\s*:", ln.strip())
        if m:
            cur = m.group(1) if m.group(1) in _ST1 else None
            if cur:
                out[cur] = []
            continue
        if cur:
            out[cur].append(ln.strip())
    missing = [k for k in _ST1 if k not in out]
    if missing:
        raise ValueError(f"Ethiopia LMS: Summary Table(s) {missing} not found")
    return out


def _st1_rows(path: str) -> list:
    rows = []
    for key, lines in _st1_sections(path).items():
        locality, loc_label, rounds = _ST1[key]
        head = " ".join(lines[:14])
        for y, _ in rounds:
            if y not in head:
                raise ValueError(f"Ethiopia ST{key}: header lacks round {y}")
        region, pending, seen = None, [], 0
        for ln in lines:
            m = _ST1_ROW.match(ln)
            if not m:
                if (ln and not re.search(r"\d", ln) and not _ST1_SKIP.match(ln)
                        and not re.fullmatch(r"(March|June|April|January|"
                                             r"February|[A-Za-z ]+Rate)[A-Za-z ]*", ln)):
                    pending.append(ln)
                    # a region name is the last line, or the last two joined
                    # ("Addis Ababa" / "City Admin."); header debris before it
                    # (the tail of a wrapped "Febru-ary") is dropped.
                    for cand in (pending[-1], " ".join(pending[-2:])):
                        if cand.lower().strip() in _ST1_REGION:
                            region, pending = _ST1_REGION[cand.lower().strip()], []
                            break
                    if len(pending) > 3:
                        raise ValueError(f"Ethiopia ST{key}: unknown region {pending!r}")
                continue
            if region is None or pending:
                raise ValueError(f"Ethiopia ST{key}: data row before a known "
                                 f"region ({pending!r}): {ln!r}")
            sex = m.group(1).lower()
            cells = m.group(2).split()
            seen += 1
            for t, (topic, definition, label) in enumerate(_ST1_TOPICS):
                for r, (period, ref) in enumerate(rounds):
                    v = cells[4 * t + r]
                    if v == "-":
                        continue
                    rows.append({
                        "survey": LAYOUT["survey"],
                        "topic": topic, "definition": definition,
                        "series_label": f"{label} (Summary Table {key})",
                        "sex": sex, "age_group": "Total", "education": "Total",
                        "geography": region, "locality": locality,
                        "locality_label": loc_label, "working_age_base": "10+",
                        "period": period, "reference_period": ref,
                        "frequency": "ad_hoc", "measure": "rate",
                        "value": float(v), "unit": "percent",
                        "series_code": f"LMS 2021 ST{key}"})
        if seen < 30:
            raise ValueError(f"Ethiopia ST{key}: only {seen} region x sex rows read")
    return rows


def parse(path: str) -> _pd.DataFrame:
    base = _engine(path)
    extra = _pd.DataFrame(_st1_rows(path))
    ur = base[base.topic == "unemployment_rate"]
    have = set(zip(ur.geography, ur.sex, ur.locality))
    dup = (extra.topic == "unemployment_rate") & (extra.period == "2021") & _pd.Series(
        [(g, s, l) in have for g, s, l in zip(extra.geography, extra.sex, extra.locality)],
        index=extra.index)
    return _pd.concat([base, extra[~dup]], ignore_index=True)
