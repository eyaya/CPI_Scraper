"""Kenya -- monetary-poverty layout (KNBS, The Kenya Poverty Report 2022).

KCHS 2022 (Kenya Continuous Household Survey). Welfare = consumption per adult
equivalent; lines are monthly and differ by residence:

    overall  KSh 4,358 rural / 8,006 urban per adult equivalent per month
    food     KSh 2,668 rural / 3,520 urban

KNBS reports THREE headcounts from those two lines, and they are three line
concepts here:
    Overall poverty   total consumption < overall line  -> line_level overall
    Hardcore poverty  total consumption < FOOD line     -> line_level extreme
    Food poverty      FOOD consumption  < food line     -> line_level other
                      (a different welfare comparison, not a third line value)

Collected:
  4.3 / 4.4 / 4.5  national, rural, urban + 47 counties: P0, distribution of
       the poor, P1, P2 (food / overall / hardcore). The population and
       number-of-poor columns are in THOUSANDS -- skipped, the schema has no
       thousand-persons unit and values are never rescaled.
  4.2  trend 2015/16 (KIHBS), 2019, 2020, 2021 (KCHS): P0 by residence for
       the three measures, the distribution of the overall poor and the
       population distribution. 2022 is read from 4.3-4.5 (same values),
       except the population distribution, printed only here.
  5.1  household-level overall P0 and P1, household and poor-household
       distributions, by sex / education / marital status of the head,
       children in the household, household size, age of the head.
Not collected: 4.1 (repeats 4.3-4.5, counts in thousands), 4.6 (Gini --
inequality), 5.2-5.6 (child / youth / elderly poverty: printed ROTATED, the
text layer comes out reversed character by character).

CROSS-CHECK (verbatim): overall 39.8 / P1 10.1 / P2 3.8; food 31.7; hardcore
7.1; rural overall 42.9, urban 33.2; Turkana overall 82.7, Nairobi City 16.5;
2015/16 overall 36.1, 2020 42.9; households overall 33.5, female-headed 35.3.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T
from ._vocab import label_rows

_LINES = {
    "overall": {"line_level": "overall", "line_name": "Overall poverty line (KNBS)"},
    "hardcore": {"line_level": "extreme",
                 "line_name": "Hardcore poverty (total consumption below the food poverty line)"},
    "food": {"line_level": "other",
             "line_name": "Food poverty (food consumption below the food poverty line)"},
}

_COUNTY_COLS = [{"metric": "headcount"}, {"metric": "poor_share"}, {"metric": "gap"},
                {"metric": "severity"}, {"skip": True}, {"skip": True}]
_RESIDENCE = [
    {"match": r"^National(?=\s)"},
    {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
    {"match": r"^Urban(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urban"},
]


def _county_tables(caption: str, line: dict, dash_counties=()) -> list[dict]:
    # A county whose number of poor is printed "-" (hardcore: Kiambu 0.0 ...
    # 2,579 -) carries one number fewer, so the exact-count scan would drop it;
    # it gets its own row spec without the count column instead.
    extra = [{"match": rf"^{c}(?=\s)", "geography": c, "columns": _COUNTY_COLS[:5]}
             for c in dash_counties]
    return [
        {"page_contains": [caption, "by residence and county, 2022"],
         "defaults": line, "exact_numbers": True, "columns": _COUNTY_COLS,
         "rows": _RESIDENCE + extra},
        {"page_contains": [caption, "by residence and county, 2022"],
         "defaults": line, "join_wrapped_labels": True, "columns": _COUNTY_COLS,
         "row_scan": {"expect_rows": 47 - len(dash_counties),
                      "exclude_labels": ["National", "Rural", "Urban", *dash_counties],
                      "label_map": {"Elgeyo/ Marakwet": "Elgeyo/Marakwet"},
                      "defaults": {}}},
    ]


def _t51(start, topic, labels):
    loc = []
    for metric in ("headcount", "gap", "population_share", "poor_share"):
        for l, lab in (("rural", "Rural"), ("urban", "Urban"), ("all", "Total")):
            loc.append({"metric": metric, "locality": l, "locality_label": lab})
    return {"page_contains": ["table 5.1: poverty measures and socioeconomic characteristics"],
            "start": start, "end": r"^(?:Education level|Marital status|Child in household|"
                                  r"Household size|Age of household head|\*The number)",
            "join_wrapped_labels": True, "exact_numbers": True,
            "defaults": {**_LINES["overall"], "unit_of_analysis": "household"},
            "columns": loc, "rows": label_rows(topic, labels)}


LAYOUT = {
    "survey": "KCHS 2022", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "annual", "decimal": ".",
    "line_type": "national", **_LINES["overall"],
    "line_unit": "", "period": "2022", "reference_period": "2022",
    "tables": (
        _county_tables("table 4.3: food poverty rates", _LINES["food"])
        + _county_tables("table 4.4: overall poverty rates", _LINES["overall"])
        + _county_tables("table 4.5: hardcore poverty rates", _LINES["hardcore"], ("Kiambu",))
        + [
            {**_t51(None, "total", []), "start": None,
             # the national household row: rates and gaps only (its shares are 100)
             "rows": [{"match": r"^National(?=\s)",
                       "columns": _t51(None, "total", [])["columns"][:6] + [{"skip": True}] * 6}]},
            _t51(r"^Sex of Household", "sex_of_head", ["Male", "Female"]),
            _t51(r"^Education level of household head", "education_of_head",
                 ["None", "Primary", "Secondary", "Tertiary"]),
            _t51(r"^Marital status of household head", "marital_status_of_head",
                 ["Married monogamous", "Married poligamous", "Widower", "Widow",
                  "Never married", "Other"]),
            _t51(r"^Child in household", "household_type",
                 ["Household without children", "Household with children"]),
            _t51(r"^Household size", "household_size",
                 ["1-3 members", "4-6 members", "7+ members"]),
            _t51(r"^Age of household head", "age_of_head",
                 ["15-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70+"]),
        ]),
}
# A row label of 5.1 must keep its sex in `sex` too, like the other countries.
for _t in LAYOUT["tables"]:
    for _r in _t.get("rows", []):
        if _r.get("topic") == "sex_of_head":
            _r["sex"] = "male" if _r["characteristic"] == "Male" else "female"

_engine = T.make_parser(LAYOUT)

# Table 4.2: rounds as columns. Blocks of three residence rows (National,
# Rural, Urban) in print order; the block labels wrap around the rows
# ("Overall Poverty" / "Rate (%) Rural ..."), so rows are read by their
# residence word and assigned to blocks by position.
_ROUNDS = [("2015", "KIHBS 2015/16", "2015/16"), ("2019", "KCHS 2019", "2019"),
           ("2020", "KCHS 2020", "2020"), ("2021", "KCHS 2021", "2021"),
           ("2022", "KCHS 2022", "2022")]
_BLOCKS = [("headcount", "overall"), ("headcount", "food"), ("headcount", "hardcore"),
           ("poor_share", "overall"), (None, None),            # millions: skipped
           ("population_share", "overall")]
_ROW = re.compile(r"(National|Rural|Urban)\s+((?:-?\d+\.\d\s+){5}-?\d+\.\d)\s*$")


def _trend(pages: list[str]) -> list[dict]:
    page = next((p for p in pages if "Table 4.2: Trends in Poverty Incidence" in p
                 and "Indicator Place of" in p), None)
    if page is None:
        raise ValueError("Kenya Table 4.2 not found")
    hits = [m for m in (_ROW.search(l) for l in page.splitlines()) if m]
    if len(hits) != 18 or [h.group(1) for h in hits] != ["National", "Rural", "Urban"] * 6:
        raise ValueError(f"Kenya Table 4.2: expected 6 blocks of National/Rural/Urban, got "
                         f"{[h.group(1) for h in hits]}")
    rows = []
    for b, (metric, line) in enumerate(_BLOCKS):
        if metric is None:
            continue
        for h in hits[b * 3:(b + 1) * 3]:
            res = h.group(1)
            vals = C.numbers_in(h.group(2))[:5]          # the last column is a change
            if metric != "headcount" and res == "National":
                continue                                  # 100.0 by construction
            for (period, survey, ref), v in zip(_ROUNDS, vals):
                # 2019-2022 rates and the poor distribution come from each
                # year's own report (Tables 4.3-4.5 / the annexes) and are
                # identical there (all 33 checked, 2026-11-04); the trend table
                # adds only 2015/16 and the population distribution.
                if period != "2015" and metric != "population_share":
                    continue
                loc = {"National": {}, "Rural": {"topic": "locality", "locality": "rural",
                                                 "locality_label": "Rural"},
                       "Urban": {"topic": "locality", "locality": "urban",
                                 "locality_label": "Urban"}}[res]
                rows.append(C.row(metric=metric, value=v, survey=survey,
                                  welfare_aggregate="consumption", line_type="national",
                                  period=period, reference_period=ref, frequency="annual",
                                  **_LINES[line], **loc))
    return rows


def parse(path: str) -> pd.DataFrame:
    df = _engine(path)
    pages = T._pages(path, halves=False)["full"]
    return pd.concat([df, pd.DataFrame(_trend(pages))], ignore_index=True)


# ---- back years: the annexes of the 2019, 2020 and 2021 reports ------------
# Annex Tables A.1 / B.1 / C.1 (individuals) give, per residence and county,
# P0 P1 P2 and the contribution to each, every value followed by its standard
# error in brackets: "Turkana 80.6(1.97) 36.1(1.31) 20.0(0.97) 3.7(0.50) ...".
# The adult-equivalent (A.2) and household (A.3) annexes repeat the same rows
# for other units and are NOT read: the caption must say "(individuals)".
# The main-body tables are not used for these years because their count
# columns are glyph-split ("4 9,529 1 5,112"), which the bracketed annex
# layout avoids. Standard errors are not collected (no schema metric).
_NUM = r"(\d+\.\d+)\s?\(\s?\d+\.\d+\s?\)"
_AROW = re.compile(r"^([A-Z][A-Za-z'’/\- ]+?)\s+" + _NUM + r"\s+" + _NUM + r"\s+" + _NUM + r"\s+(.*)$")
_ACAP = re.compile(r"Annex\s+Table\s*[A-Z]\s*\.?\s*\d+\s*:\s*(Overall|Food|Hardcore(?:/extreme)?)\s+"
                   r"poverty\s+estimates\s*\((\w+)\)", re.I)
_FIX = {"Elgeyo / Marakwet": "Elgeyo/Marakwet", "Elgeyo /Marakwet": "Elgeyo/Marakwet",
        "Taita /Taveta": "Taita/Taveta", "Taita / Taveta": "Taita/Taveta", "Kirinyag’a": "Kirinyaga"}
_MEASURE = {"overall": "overall", "food": "food", "hardcore": "hardcore", "hardcore/extreme": "hardcore"}


def _annex(path: str, year: str) -> list[dict]:
    import pdfplumber
    found: dict[str, dict[str, tuple]] = {}
    cur = None
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            t = p.crop((0, 0, p.width, p.height)).extract_text() or ""
            m = _ACAP.search(t)
            if m:
                cur = _MEASURE[m.group(1).lower()] if m.group(2).lower().startswith("individual") else None
            elif re.search(r"Annex\s+Table", t):
                cur = None
            if not cur:
                continue
            for line in t.splitlines():
                r = _AROW.match(line.strip())
                if not r:
                    continue
                label = _FIX.get(r.group(1).strip(), r.group(1).strip())
                found.setdefault(cur, {}).setdefault(label, (r.groups()[1:4], r.group(5)))
    rows = []
    survey = f"KCHS {year}"
    for measure, by in found.items():
        counties = [k for k in by if k not in ("National", "Rural", "Urban")]
        if len(counties) != 47 or not {"National", "Rural", "Urban"} <= set(by):
            raise ValueError(f"Kenya {year} annex {measure}: {len(counties)} counties, "
                             f"rows {sorted(by)[:5]}...")
        for label, (fgt, rest) in by.items():
            geo = {"geography": label} if label in counties else {}
            loc = ({"topic": "locality", "locality": label.lower(), "locality_label": label}
                   if label in ("Rural", "Urban") else {})
            vals = list(zip(("headcount", "gap", "severity"), map(float, fgt)))
            if label != "National":
                ctr = re.findall(_NUM, rest)[:3]
                if len(ctr) != 3:
                    raise ValueError(f"Kenya {year} {measure} {label}: contributions unreadable")
                vals += list(zip(("poor_share", "gap_contribution", "severity_contribution"),
                                 map(float, ctr)))
            for metric, v in vals:
                rows.append(C.row(metric=metric, value=v, survey=survey,
                                  welfare_aggregate="consumption", line_type="national",
                                  period=year, reference_period=year, frequency="annual",
                                  **_LINES[measure], **geo, **loc))
    if set(found) != {"overall", "food", "hardcore"}:
        raise ValueError(f"Kenya {year} annex: measures found {sorted(found)}")
    return rows


_parse_2022 = parse


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:  # noqa: F811
    frames = [_parse_2022(path)]
    for ex in extras or []:
        y = re.search(r"Report-(20\d\d)\.pdf$", ex)
        if y and y.group(1) != "2022":
            frames.append(pd.DataFrame(_annex(ex, y.group(1))))
    return pd.concat(frames, ignore_index=True)
