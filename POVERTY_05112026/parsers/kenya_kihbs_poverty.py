"""Kenya -- KIHBS rounds (2005/06, 2015/16): back-series beside the KCHS reports.

Two KNBS reports, each its own descriptor:

1. "Basic Report on Well-Being in Kenya" (KIHBS 2015/16, published 2018;
   `sources/kenya_kihbs_2015.yaml`):
     Tables 4.2 / 4.3 / 4.4 -- food / overall / hardcore poverty by residence
       (National, Rural, Peri-Urban, Core-Urban) and 47 counties: headcount,
       distribution of the poor, gap, severity (population and count columns
       skipped -- counts are in thousands).
     Table 4.5 -- trend 2005/06 vs 2015/16: the ORIGINAL KIHBS 2005/06 rates
       and the COMPARABLE 2005/06 rates (2015/16 basket revalued at 2005/06
       prices), each its own `survey`, for overall / food / hardcore poverty,
       distribution of the poor and population distribution. Its 2015/16
       column repeats Tables 4.2-4.4 and is not read.
   THE THREE-WAY RESIDENCE SPLIT IS NOT THE KCHS TWO-WAY ONE. The 2022 report
   republishes KIHBS 2015/16 as Rural 38.8 / Urban 29.4 (peri-urban folded in
   differently); this report prints Rural 40.1 / Peri-Urban 27.5 / Core-Urban
   29.4. So this report's Rural is filed with locality_label "Rural (three-way
   split)" and the others as strata -- otherwise two different published
   rural rates for one survey would share a merge key and an ID.
   Table 5.1 (household level) is printed ROTATED; its text layer is
   reversed, so it is not read. Published defect: Table 4.4's Nairobi City
   severity reads 9.8 against a headcount of 0.6 (P2 cannot exceed P0) -- that
   one cell is dropped, its other cells kept.

2. "Constituency Report on Well-being in Kenya" (KIHBS 2005/06, KNBS 2008;
   `sources/kenya_kihbs_2005_constituency.yaml`, Wayback `id_` of knbs.or.ke):
     Table 3 -- 8 provinces and 210 constituencies: number of poor, P0 2005/06,
       contribution to national poverty, and P0 1999.
     Appendix (pp. 70-71) -- Kenya, Rural, provinces and districts: poor
       individuals and poor households below the line (counts).
   The constituency figures are SMALL-AREA ESTIMATES (KIHBS consumption model
   applied to census populations; report ch. 1.3), filed under their own
   survey label; the 1999 column is the 1999-census small-area estimate on the
   1997 WMS-III lines (KSh 1,239 rural / 2,648 urban), as republished here.
   Places carry their level ("Makueni (constituency)", "Kitui (district)") so
   a constituency or a pre-2010 district never shares a place with a county.

CROSS-CHECK (verbatim): 2015/16 overall 36.1 / 10.4 / 4.5, food 32.0, hardcore
8.6; Turkana overall 79.4 (gap 46.0); 2005/06 overall 46.6 (comparable 46.8),
food 45.8, hardcore 19.5; Nairobi Province 22.0 (1999: 43.9); Turkana Central
96.9; Kajiado North 10.7; Kenya 16,562,550 poor individuals, 2,671,201 poor
households.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_LINES = {
    "overall": {"line_level": "overall", "line_name": "Overall poverty line (KNBS)"},
    "hardcore": {"line_level": "extreme",
                 "line_name": "Hardcore poverty (total consumption below the food poverty line)"},
    "food": {"line_level": "other",
             "line_name": "Food poverty (food consumption below the food poverty line)"},
}
_COLS = [{"metric": "headcount"}, {"metric": "poor_share"}, {"metric": "gap"},
         {"metric": "severity"}, {"skip": True}, {"skip": True}]
_RES = [
    {"match": r"^National(?=\s)"},
    {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural",
     "locality_label": "Rural (three-way split)"},
    {"match": r"^Peri-?\s?urban(?=\s)", "topic": "locality", "locality": "other",
     "locality_label": "Peri-Urban"},
    {"match": r"^Core-?\s?urban(?=\s)", "topic": "locality", "locality": "other",
     "locality_label": "Core-Urban"},
]
_COUNTY_MAP = {"samburu": "Samburu", "baringo": "Baringo", "bomet": "Bomet",
               "bungoma": "Bungoma", "busia": "Busia", "siaya": "Siaya",
               "homa bay": "Homa Bay", "Taita /Taveta": "Taita/Taveta",
               "Taita / Taveta": "Taita/Taveta", "Elgeyo / Marakwet": "Elgeyo/Marakwet",
               "Elgeyo /Marakwet": "Elgeyo/Marakwet", "Tharaka - Nithi": "Tharaka-Nithi",
               "Murang'a": "Murang'a", "Murang’a": "Murang'a",
               # "Tharaka - Nithi": the label pattern stops at the " - ".
               "Tharaka": "Tharaka-Nithi"}


def _county(caption: str, line: dict, nairobi_no_severity: bool = False) -> list[dict]:
    sel = [caption, "by residence and county, 2015/16"]
    extra = []
    if nairobi_no_severity:
        extra = [{"match": r"^Nairobi City(?=\s)", "geography": "Nairobi City",
                  "columns": _COLS[:3] + [{"skip": True}] * 3}]
    return [
        {"page_contains": sel, "defaults": line, "exact_numbers": True,
         "columns": _COLS, "rows": _RES + extra},
        {"page_contains": sel, "defaults": line, "columns": _COLS,
         "row_scan": {"expect_rows": 47 - len(extra),
                      "exclude_labels": ["National", "Rural", "Peri-Urban", "Peri-urban",
                                         "Core-Urban", "Core-urban",
                                         *(["Nairobi City"] if extra else [])],
                      "label_map": _COUNTY_MAP, "defaults": {}}},
    ]


LAYOUT = {
    "survey": "KIHBS 2015/16", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", **_LINES["overall"], "line_unit": "",
    "period": "2015", "reference_period": "2015/16",
    "tables": (_county("table 4.2: food poverty estimates", _LINES["food"])
               + _county("table 4.3: overall poverty estimates", _LINES["overall"])
               + _county("table 4.4: hardcore poverty estimates", _LINES["hardcore"],
                         nairobi_no_severity=True)),
}
_engine = T.make_parser(LAYOUT)

# Table 4.5: six blocks of four residence rows, in print order.
_T45_ROW = re.compile(r"(National|Rural|Peri-Urban|Core-Urban)\s+(n/a|-?[\d.]+)\s+(n/a|-?[\d.]+)"
                      r"\s+(n/a|-?[\d.]+)\s+(n/a|-?[\d.]+)\s*$")
_T45_BLOCKS = [("headcount", "overall"), ("headcount", "food"), ("headcount", "hardcore"),
               ("poor_share", "overall"), (None, None),              # millions of poor: skipped
               ("population_share", "overall")]
_T45_SURVEYS = [("KIHBS 2005/06", "2005/06"),
                ("KIHBS 2005/06 (comparable: 2015/16 basket revalued at 2005/06 prices)", "2005/06")]
_RES_ATTRS = {"National": {},
              "Rural": {"topic": "locality", "locality": "rural",
                        "locality_label": "Rural (three-way split)"},
              "Peri-Urban": {"topic": "locality", "locality": "other", "locality_label": "Peri-Urban"},
              "Core-Urban": {"topic": "locality", "locality": "other", "locality_label": "Core-Urban"}}


def _base(**kw) -> dict:
    d = dict(survey="KIHBS 2005/06", welfare_aggregate="consumption", unit_of_analysis="person",
             line_type="national", period="2005", reference_period="2005/06",
             frequency="ad_hoc", line_value="", line_unit="", **_LINES["overall"])
    d.update(kw)
    return d


def _trend(pages: list[str]) -> list[dict]:
    page = next((p for p in pages if "table 4.5: trends in poverty incidence" in p.lower()
                 and "comparable 2005/06" in p.lower()), None)
    if page is None:
        raise ValueError("Table 4.5 (trend 2005/06-2015/16) not found")
    hits = [m for m in (_T45_ROW.search(l.strip()) for l in page.splitlines()) if m]
    if len(hits) != 24:
        raise ValueError(f"Table 4.5: expected 24 residence rows (6 blocks x 4), got {len(hits)}")
    out = []
    for k, m in enumerate(hits):
        metric, line = _T45_BLOCKS[k // 4]
        if metric is None:
            continue
        res = m.group(1)
        for (survey, ref), cell in zip(_T45_SURVEYS, (m.group(2), m.group(3))):
            if cell == "n/a":
                continue
            # A residence's share of the whole is 100 for National: not a row.
            if metric != "headcount" and res == "National":
                continue
            out.append(C.row(metric=metric, value=float(cell),
                             **{k2: v for k2, v in _base(survey=survey, reference_period=ref,
                                                         **_LINES[line]).items()},
                             **_RES_ATTRS[res]))
    return out


def parse(path: str) -> pd.DataFrame:
    df = _engine(path)
    pages = T._pages(path, halves=False)["full"]
    return pd.concat([df, pd.DataFrame(_trend(pages))], ignore_index=True)


# ------------------------------------------------------------------ 2005/06 --
LAYOUT_CONSTITUENCY = {
    "survey": "KIHBS 2005/06", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", **_LINES["overall"],
    "line_value": "", "line_unit": "",
    "period": "2005", "reference_period": "2005/06", "tables": [],
}
_SAE_2005 = "KIHBS 2005/06 small-area estimates (constituency, census-based)"
_SAE_1999 = "Census 1999 small-area estimates (1997 WMS-III lines), as republished 2008"
_NUM = re.compile(r"^[+-]?[\d,]+(?:\.\d+)?$")


def _num(s: str) -> float:
    return float(s.replace(",", "").replace("+", ""))


def _tokens(doc, pages) -> list[str]:
    out = []
    for i in pages:
        out += [l.strip() for l in doc[i].get_text().split("\n") if l.strip()]
    return out


def parse_constituency(path: str) -> pd.DataFrame:
    import fitz
    doc = fitz.open(path)
    rows: list[dict] = []
    # Table 3 (pp. 46-50): "<code> <name> pop poor P0 rank contrib P0_1999 change"
    # and province totals "<X> Province pop poor P0 contrib P0_1999 change".
    tok = _tokens(doc, range(45, 50))
    i, consts, provs = 0, 0, 0
    while i < len(tok):
        t = tok[i]
        m = re.fullmatch(r"([A-Za-z.\- ]+?)\s+Province", t)
        if m and i + 6 < len(tok) and all(_NUM.match(x) for x in tok[i + 1:i + 7]):
            p0, contrib, p99 = _num(tok[i + 3]), _num(tok[i + 4]), _num(tok[i + 5])
            geo = re.sub(r"\s+", " ", m.group(1)).strip().replace("N. Eastern", "North Eastern") + " Province"
            b = dict(geography=geo)
            rows += [C.row(metric="poor_count", value=_num(tok[i + 2]), **_base(), **b),
                     C.row(metric="headcount", value=p0, **_base(), **b),
                     C.row(metric="poor_share", value=contrib, **_base(), **b),
                     C.row(metric="headcount", value=p99,
                           **_base(survey=_SAE_1999, period="1999", reference_period="1999"), **b)]
            provs += 1
            i += 7
            continue
        if re.fullmatch(r"\d{1,3}", t) and 1 <= int(t) <= 210 and i + 8 < len(tok):
            name_parts, j = [], i + 1
            while j < len(tok) and not _NUM.match(tok[j]) and len(name_parts) < 3:
                name_parts.append(tok[j])
                j += 1
            nums = tok[j:j + 7]
            if name_parts and len(nums) == 7 and all(_NUM.match(x) for x in nums):
                geo = re.sub(r"\s+", " ", " ".join(name_parts)).strip() + " (constituency)"
                b = dict(geography=geo)
                sae = _base(survey=_SAE_2005)
                rows += [C.row(metric="poor_count", value=_num(nums[1]), **sae, **b),
                         C.row(metric="headcount", value=_num(nums[2]), **sae, **b),
                         C.row(metric="poor_share", value=_num(nums[4]), **sae, **b),
                         C.row(metric="headcount", value=_num(nums[5]),
                               **_base(survey=_SAE_1999, period="1999", reference_period="1999"),
                               **b)]
                consts += 1
                i = j + 7
                continue
        i += 1
    if consts != 210 or provs != 8:
        raise ValueError(f"Table 3: expected 210 constituencies and 8 provinces, got {consts} / {provs}")

    # A constituency name printed TWICE in Table 3 with different figures
    # ("Turkana Central" 60.9 and 96.9) cannot be told apart: both are dropped.
    df = pd.DataFrame(rows)
    key = ["metric", "geography", "survey", "period"]
    twice = df[df.duplicated(key, keep=False)]["geography"].unique()
    if len(twice):
        print(f"[kenya_kihbs] constituency printed twice, dropped: {list(twice)}")
        df = df[~df["geography"].isin(twice)]
    rows = df.to_dict("records")

    # Appendix 5 (pp. 70-71): "<area> AE HH IND AE_poor HH_poor IND_poor",
    # Kenya, then a RURAL block (rural provinces and their districts), then an
    # URBAN block (Nairobi, Mombasa, Kisumu, Nakuru, Other Urban). A district
    # or province row is therefore the RURAL part of it, and an urban row the
    # city -- never the whole district.
    tok = _tokens(doc, range(69, 71))
    provinces = {"Central", "Coast", "Eastern", "North Eastern", "Nyanza", "Rift Valley", "Western"}
    seen, block, i = 0, None, 0
    while i < len(tok):
        t = tok[i]
        if not _NUM.match(t) and i + 6 < len(tok) and all(_NUM.match(x) for x in tok[i + 1:i + 7])                 and not re.search(r"\d", t):
            hh_poor, ind_poor = _num(tok[i + 5]), _num(tok[i + 6])
            if t == "Kenya":
                b = dict(geography="Total country")
            elif t in ("Rural", "Urban"):
                block = t
                b = dict(topic="locality", locality=t.lower(), locality_label=t)
            elif block == "Rural":
                geo = f"{t} Province" if t in provinces else f"{t} (district)"
                b = dict(geography=geo, topic="locality", locality="rural", locality_label="Rural")
            elif t == "Other Urban":
                b = dict(topic="locality", locality="other", locality_label="Other urban")
            else:
                b = dict(geography=f"{t} (city)", topic="locality", locality="urban",
                         locality_label="Urban")
            rows += [C.row(metric="poor_count", value=ind_poor, **_base(), **b),
                     C.row(metric="poor_count", value=hh_poor, unit="households",
                           **_base(unit_of_analysis="household"), **b)]
            seen += 1
            i += 7
            continue
        i += 1
    if seen < 70:
        raise ValueError(f"appendix 5: only {seen} areas read")
    return pd.DataFrame(rows)
