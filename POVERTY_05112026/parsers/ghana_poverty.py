"""Ghana -- monetary-poverty layout (GSS, "Poverty Trends in Ghana 2005-2017",
GLSS 7 poverty profile, 2018).

GLSS 5 (2005/06), GLSS 6 (2012/13) and GLSS 7 (2016/17) on ONE methodology:
consumption per adult equivalent in constant Greater Accra January 2017 prices;
upper line GH¢1,314, extreme line GH¢792.05 per adult equivalent per year.
The earlier rounds are re-estimated on that basis, so they are tagged with
their own survey but share the line.

Read:
  Appendix A1.1a/b, A1.2a/b  seven ecological strata and ten regions, both
        lines: population share, P0, P1, P2 and their contributions C0..C2.
        Each table prints THREE year blocks (2005/06, 2012/13, 2016/17) on one
        page; the page is split into one pseudo-page per block before reading.
  A1.3  sex of head x Urban / Rural / Ghana (upper line).
  A1.4/A1.5  employment status of head; A1.6/A1.7 education of head.
  Tables 3.1/3.2  Urban and Rural P0, C0, P1, C1, both lines, three years.

PUBLISHED DEFECTS, handled by explicit rule:
  * A1.3 2005/06 prints the URBAN P0/P1/P2/(P1/P0) cells again on the Rural row
    (12.4 3.7 1.6 29.5); its share and contributions are right (62.3, 85.3...).
    Rural 2005/06 P0/P1 come from Table 3.1 (43.7 / 15.4); its P2 is not taken.
  * Table 3.1/3.2 and Appendix A1.1a/A1.2a disagree for three 2016/17 strata
    (Accra 2.0 vs 0.8, Urban Coastal 8.3 vs 5.3, Rural Coastal 29.9 vs 25.8);
    the appendix (the full P0-P2 set) is read for the strata, Tables 3.1/3.2
    only for Urban and Rural, which the appendix does not print by line.
  * A1.7 2005/06 "Ghana" extreme P0 is 20.2 against 16.5 everywhere else --
    national rows are read only from A1.1a/A1.2a.
  * A1.1a 2005/06's text layer overprints "(GAMA)" on "Urban Coastal"
    ("(UGrAbaMn AC)o astal"); restored to "Urban Coastal" on that page only.
Not read: average welfare, P1/P0 (a ratio of published cells), Table 4.x
(Palma, decomposition -- inequality / derived), Appendices 2-8.

CROSS-CHECK (verbatim): P0 23.4 / 24.2 / 31.9 (2016/17, 2012/13, 2005/06);
extreme 8.2 / 8.4 / 16.5; P2 4.3 (2016/17); Upper West 70.9; Northern C0 26.1;
Rural Savannah 67.7; Greater Accra extreme 0.0; female-headed 17.6 (2016/17).
"""
from __future__ import annotations

import re

import pandas as pd

from . import poverty_tables as T
from ._vocab import label_rows

_YEARS = {"2005/06": ("2005", "GLSS 5 (2005/06)"),
          "2012/13": ("2012", "GLSS 6 (2012/13)"),
          "2016/17": ("2016", "GLSS 7 (2016/17)")}
_UP = {"line_level": "overall", "line_name": "Poverty line GH¢1,314",
       "line_value": 1314, "line_unit": "GHS per adult equivalent per year, Accra January 2017 prices"}
_EX = {"line_level": "extreme", "line_name": "Extreme poverty line GH¢792.05",
       "line_value": 792.05, "line_unit": "GHS per adult equivalent per year, Accra January 2017 prices"}

_S = {"skip": True}


def _app_cols(share: bool = True):
    """Appendix A1: share | welfare | P0 P1 P2 | P1/P0 | C0 C1 C2."""
    return [{"metric": "population_share"} if share else _S, _S,
            {"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}, _S,
            {"metric": "poor_share"}, {"metric": "gap_contribution"},
            {"metric": "severity_contribution"}]


def _yr(y):
    p, s = _YEARS[y]
    return {"period": p, "survey": s, "reference_period": y}


def _t31_cols():
    """Tables 3.1/3.2: 2016/17 | 2012/13 | 2005/06, each P0 C0 P1 C1."""
    out = []
    for y in ("2016/17", "2012/13", "2005/06"):
        out += [{"metric": m, **_yr(y)} for m in ("headcount", "poor_share", "gap", "gap_contribution")]
    return out


_STRATA = ["Accra (GAMA)", "Urban Coastal", "Urban Forest", "Urban Savannah",
           "Rural Coastal", "Rural Forest", "Rural Savannah"]
_REGIONS = ["Western", "Central", "Greater Accra", "Volta", "Eastern", "Ashanti",
            "Brong Ahafo", "Northern", "Upper East", "Upper West"]
_EMP = ["Public Employee", "Private Employee", "Self-employed (non-agric)",
        "Self-employed (agric)", "Unemployed", "Retired", "Other Inactive"]
_EDU = ["None", "BECE", "MSLC", "SSS/Secondary", "Voc/Tech/Teacher", "Tertiary"]


def _strata_rows():
    rows = []
    for s in _STRATA:
        pat = r"^Accra(?: \(GAMA\))?(?=\s+\d)" if s.startswith("Accra") else r"^" + re.escape(s) + r"(?=\s+\d)"
        rows.append({"match": pat, "topic": "locality", "locality": "other", "locality_label": s})
    rows.append({"match": r"^Ghana(?=\s+\d)"})
    return rows


def _region_rows():
    return [{"match": r"^" + re.escape(r) + r"(?=\s+\d)", "geography": r} for r in _REGIONS]


def _tables():
    tabs = []
    for y in _YEARS:
        key = f"<<{y}>>"
        d = _yr(y)
        tabs += [
            {"page_contains": ["table a1.1a", key], "defaults": {**d, **_UP}, "take": "trailing",
             "exact_numbers": True, "join_wrapped_labels": True,
             "columns": _app_cols(), "rows": _strata_rows()},
            {"page_contains": ["table a1.2a", key], "defaults": {**d, **_EX}, "take": "trailing",
             "exact_numbers": True, "join_wrapped_labels": True,
             "columns": _app_cols(share=False), "rows": _strata_rows()},
            {"page_contains": ["table a1.1b", key], "defaults": {**d, **_UP},
             "columns": _app_cols(), "rows": _region_rows()},
            {"page_contains": ["table a1.2b", key], "defaults": {**d, **_EX},
             "columns": _app_cols(share=False), "rows": _region_rows()},
            {"page_contains": ["table a1.4", key], "defaults": {**d, **_UP},
             "columns": _app_cols(), "rows": _emp_rows()},
            {"page_contains": ["table a1.5", key], "defaults": {**d, **_EX},
             "columns": _app_cols(share=False), "rows": _emp_rows()},
            {"page_contains": ["table a1.6", key], "defaults": {**d, **_UP},
             "columns": _app_cols(), "rows": label_rows("education_of_head", _EDU)},
            {"page_contains": ["table a1.7", key], "defaults": {**d, **_EX},
             "columns": _app_cols(share=False), "rows": label_rows("education_of_head", _EDU)},
        ]
        # A1.3 -- sex of head within Urban / Rural / Ghana
        for start, end, loc in ((r"^Urban\b", r"^Rural\b", ("urban", "Urban")),
                                (r"^Rural\b", r"^Ghana\b", ("rural", "Rural")),
                                (r"^Ghana\b", None, ("all", "Total"))):
            tabs.append({
                "page_contains": ["table a1.3", key], "start": start, "end": end,
                "defaults": {**d, **_UP, "locality": loc[0], "locality_label": loc[1]},
                "columns": _app_cols(),
                "rows": [{"match": r"^Male(?=\s+\d)", "topic": "sex_of_head",
                          "characteristic": "Male", "sex": "male"},
                         {"match": r"^Female(?=\s+\d)", "topic": "sex_of_head",
                          "characteristic": "Female", "sex": "female"}]})
        # A1.3 -- Urban / Rural rows themselves: share, P2, C2 only (P0/P1 and
        # C0/C1 come from Table 3.1). 2005/06 Rural: share and C2 only (copied cells).
        rural_cols = ([{"metric": "population_share"}] + [_S] * 7 + [{"metric": "severity_contribution"}]
                      if y == "2005/06" else
                      [{"metric": "population_share"}, _S, _S, _S, {"metric": "severity"},
                       _S, _S, _S, {"metric": "severity_contribution"}])
        tabs.append({
            "page_contains": ["table a1.3", key], "defaults": {**d, **_UP, "topic": "locality"},
            "columns": [{"metric": "population_share"}, _S, _S, _S, {"metric": "severity"},
                        _S, _S, _S, {"metric": "severity_contribution"}],
            "rows": [{"match": r"^Urban(?=\s+\d)", "locality": "urban", "locality_label": "Urban"},
                     {"match": r"^Rural(?=\s+\d)", "locality": "rural", "locality_label": "Rural",
                      "columns": rural_cols}]})
    # Tables 3.1 / 3.2 -- Urban and Rural, three years in one row
    for cap, line in (("table 3.1: poverty incidence and poverty gap by locality", _UP),
                      ("table 3.2: extreme poverty incidence and poverty gap by locality", _EX)):
        tabs.append({
            "page_contains": [cap, "all ghana"], "defaults": {**line, "topic": "locality"},
            "exact_numbers": True, "columns": _t31_cols(),
            "rows": [{"match": r"^Urban(?=\s+\d)", "locality": "urban", "locality_label": "Urban"},
                     {"match": r"^Rural(?=\s+\d)", "locality": "rural", "locality_label": "Rural"}]})
    return tabs


def _emp_rows():
    rows = label_rows("employment_of_head", [e for e in _EMP if "non-agric" not in e])
    rows.insert(2, {"match": r"^Self-employed ?\(non-agric\)(?=\s+\d)",
                    "topic": "employment_of_head", "characteristic": "Self-employed (non-agric)"})
    return rows


LAYOUT = {
    "survey": "GLSS 7 (2016/17)", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", **_UP,
    "period": "2016", "reference_period": "2016/17",
    "tables": _tables(),
}

_YEAR_LINE = re.compile(r"^(2005/06|2012/13|2016/17)$", re.M)


def _fix(text: str) -> str:
    text = text.replace("(UGrAbaMn AC)o astal", "Urban Coastal")
    # 2016/17 blocks wrap "Urban" / "Savannah 6.8 ..." the other way round.
    return re.sub(r"^(Urban|Rural)\n(Savannah \d)", r"\1 \2", text, flags=re.M)


def _block_pages(pages: list[str]) -> list[str]:
    """Split an appendix page into one pseudo-page per year block, each
    starting with its caption and a <<year>> marker the layout selects on."""
    out = []
    for text in pages:
        text = _fix(text)
        cap = next((l for l in text.splitlines() if re.match(r"Table A1\.\d", l)), None)
        marks = list(_YEAR_LINE.finditer(text))
        if not cap or not marks:
            out.append(text)
            continue
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
            out.append(f"{cap}\n<<{m.group(1)}>>\n{text[m.end():end]}")
    return out


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)
    pages["full"] = _block_pages(pages["full"])
    rows, misses = [], []
    for t, tbl in enumerate(LAYOUT["tables"]):
        got, matched = T._parse_table(pages, LAYOUT, tbl, LAYOUT["period"], LAYOUT["reference_period"])
        rows.extend(got)
        misses += [f"table[{t}]{tbl['page_contains']}.{r['match']!r}"
                   for ri, r in enumerate(tbl.get("rows", [])) if ri not in matched]
    if misses:
        raise ValueError(f"{len(misses)} Ghana row spec(s) matched nothing: {misses[:6]}")
    return pd.DataFrame.from_records(rows)
