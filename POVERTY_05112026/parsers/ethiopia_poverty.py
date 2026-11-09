"""Ethiopia -- consumption poverty from the HICES rounds 1995/96-2015/16.

ESS (formerly CSA) runs the HICES but publishes consumption tables only; its
HCES 2015/16 report says the poverty profile "is produced by the NPC". So the
OFFICIAL COMPILER is the planning ministry (MoFED -> NPC -> PDC), the case the
source policy allows when the NSO itself publishes no poverty report. Both
reports are Wayback `id_` copies of the ministry's own files.

* `parse` -- NPC, "Ethiopia's Progress Towards Eradicating Poverty: An Interim
  Report on 2015/16 Poverty Analysis Study" (2017):
    Table 6   poverty lines (Birr per adult per year, at each round's prices)
    Table 10  P0 P1 P2, national / rural / urban, 1995/96, 1999/00, 2004/05,
              2010/11, 2015/16 (absolute line)
    Table 11  the same for FOOD POVERTY (food consumption below the food line;
              filed line_level other -- it is higher than absolute poverty,
              e.g. 24.8 vs 23.5, so it is not an extreme line)
    Table 13  P0 by region x rural/urban/total, 1999/00-2015/16
    Table 14  food-poverty P0 by region x national/rural/urban, 2010/11, 2015/16
  "-" cells are empty (no rural Addis Ababa; Gambella 2004/05 not covered).
* `parse_zones` -- MoFED, "Development and Poverty in Ethiopia 1995/96-
  2010/11" (2013), Annex Table A5.6b: P0 P1 P2 IN PERCENT by ZONE for
  1995/96, 1999/00 and 2004/05. Places are "<zone> zone, <region>" -- "NORTH
  SHOA" is a zone of both Amhara and Oromiya.
  The same function also reads the report's 0-1 TABLES (unit "index", kept as
  printed), filed as "HICES <round> (MoFED 2013 profile)" so they never share
  a merge key with the NPC report's percent re-statement of the same rounds:
    A5.1 / A5.2   P0 P1 P2 national / rural / urban, 1995/96-2010/11 (total
                  and food poverty)
    A5.3 / A5.4   regional P0 x rural / urban / total, four rounds (food: the
                  two 1995/96 urban zeros where A5.3 prints "-" are not read)
    5.5 / 5.6     regional P1, P2 2010/11 (their P0 repeats A5.3 / A5.4)
    A5.5 / A5.6a  towns, other-urban remainders and Addis Ababa sub-cities,
                  2010/11 (total + food) and 2004/05 (region-wide strata repeat
                  A5.3; calorie-intake poverty not read)
    5.10          number of poor by region, four rounds
    A6.1 / A6.5   sex / literacy of head x residence, four rounds
    A6.4 / 6.4    household size, four rounds (6.4: 2010/11 rural, urban)
    6.6 6.7 6.8 6.11 6.12  2010/11 schooling, industry ("Industry: ...") and
                  occupation ("Occupation: ...", plus 2004/05 from MoFED 2008),
                  age and marital status of head.
  Not read: SEs, % changes, Gini, 6.9 activity status, 6.10 ecological zone
  (rows lost in the text layer), 6.13 religion (no topic for them).
  Table 5.10's regions do not sum to its national total in 1995/96 (25.08 vs
  25.65 million printed); both are kept as printed.

Period = the START year of the Ethiopian round (1995, 1999, 2004, 2010, 2015),
as for Kenya and the EHCVM countries.

CROSS-CHECK (verbatim): MoFED A5.1 0.455 0.442 0.387 0.296 (= NPC Table 10);
Lideta 2010/11 0.538 / 0.182 / 0.083; Bole 2004/05 0.153; female-headed urban
1999/2000 0.492; Oromiya poor 2010/11 8 981 694; NPC P0 45.5 / 44.2 / 38.7 / 29.6 / 23.5; 2015/16 P1 6.7,
P2 2.8, rural 25.6, urban 14.8; food poverty 49.5 -> 24.8; Tigray 2015/16 27.0;
Harari 7.1; zone KONSO SPECIAL 1995/96 89.8.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_ABS = {"line_level": "overall", "line_name": "Absolute (total) poverty line (MoFED/NPC)"}
_FOOD = {"line_level": "other",
         "line_name": "Food poverty (food consumption below the food poverty line, MoFED/NPC)"}
_ROUNDS = {"1995": ("HICES 1995/96", "1995/96"), "1999": ("HICES 1999/00", "1999/00"),
           "2004": ("HICES 2004/05", "2004/05"), "2010": ("HICES 2010/11", "2010/11"),
           "2015": ("HICES 2015/16", "2015/16")}
_REGION = {"Tigray": "Tigray", "Afar": "Afar", "Amhara": "Amhara", "Oromia": "Oromia",
           "Oromiya": "Oromia", "Somale": "Somali", "Somali": "Somali", "B.G": "Benishangul-Gumuz",
           "SNNP": "SNNP", "Gamb.": "Gambella", "Gambella": "Gambella", "Harari": "Harari",
           "AA": "Addis Ababa", "A.A": "Addis Ababa", "DD": "Dire Dawa", "Dire Dawa": "Dire Dawa"}

LAYOUT = {"survey": "HICES 2015/16", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "frequency": "ad_hoc", "decimal": ".", "line_type": "national", **_ABS,
          "period": "2015", "reference_period": "2015/16", "tables": []}
LAYOUT_ZONES = {**LAYOUT, "survey": "HICES 2004/05", "period": "2004", "reference_period": "2004/05"}


def _base(year, line, lv=None, **kw):
    survey, ref = _ROUNDS[year]
    d = dict(survey=survey, welfare_aggregate="consumption", unit_of_analysis="person",
             line_type="national", period=year, reference_period=ref, frequency="ad_hoc",
             line_value=lv or "", line_unit="Birr per adult equivalent per year" if lv else "", **line)
    d.update(kw)
    return d


_LOC = {"Rural": dict(topic="locality", locality="rural", locality_label="Rural"),
        "Urban": dict(topic="locality", locality="urban", locality_label="Urban"),
        "National": {}, "Total": {}}


def _page(P, pat):
    """The LAST page carrying the caption: the list of tables comes first."""
    hits = [p for p in P if re.search(pat, p)]
    if not hits:
        raise ValueError(f"not found: {pat!r}")
    return hits[-1]


def parse(path: str) -> pd.DataFrame:
    P = T._pages(path, halves=False)["full"]
    out = []
    t6 = _page(P, r"Table 6: Total \(absolute\) and food poverty line in Birr")
    lines6 = {}
    for l in t6.splitlines():
        m = re.match(r"^(Food|Absolute) poverty line \(Birr\)\s+(\d+)\s+(\d+)\s+(\d+)\s*$", l)
        if m:
            lines6[m.group(1)] = dict(zip(("1995", "2010", "2015"), map(float, m.group(2, 3, 4))))
    if set(lines6) != {"Food", "Absolute"}:
        raise ValueError("Table 6 not read")
    years5 = ["1995", "1999", "2004", "2010", "2015"]
    for cap, line, lv in ((r"Table 10: Trends of national and rural/urban poverty", _ABS, lines6["Absolute"]),
                          (r"Table 11: Trends of national and rural/urban food poverty", _FOOD, None)):
        pg = _page(P, cap)
        body = pg[re.search(cap, pg).end():].splitlines()
        block, n = None, 0
        for l in body:
            s = l.strip()
            if s.startswith("Source"):
                break
            if re.match(r"^(National|Rural|Urban)\b", s) and not re.search(r"index", s):
                block = s.split()[0]
                continue
            m = re.match(r"^(Head count|Poverty gap|Poverty severity) index\s+((?:-?[\d.]+\s+){4}-?[\d.]+)", s)
            if m and block:
                metric = {"Head count": "headcount", "Poverty gap": "gap",
                          "Poverty severity": "severity"}[m.group(1)]
                for y, v in zip(years5, m.group(2).split()):
                    out.append(C.row(metric=metric, value=float(v),
                                     **_base(y, line, (lv or {}).get(y), **_LOC[block])))
                n += 1
        if n != 9:
            raise ValueError(f"{cap}: expected 9 rows, got {n}")
    # Table 13 -- regional P0, 4 rounds x Rural / Urban / Total
    t13 = _page(P, r"Table 13: Trends in regional poverty headcount indices")
    years4 = ["1999", "2004", "2010", "2015"]
    n = 0
    for l in t13[t13.index("Table 13"):].splitlines():
        tok = l.split()
        if not tok or tok[0] not in _REGION and tok[0] != "Total":
            continue
        cells = tok[1:]
        if len(cells) != 12:
            continue
        geo = {} if tok[0] == "Total" else {"geography": _REGION[tok[0]]}
        for k, y in enumerate(years4):
            for j, loc in enumerate(("Rural", "Urban", "Total")):
                v = cells[3 * k + j]
                if v in ("-", "--", "…", "na", "Na"):
                    continue
                if tok[0] == "Total":
                    continue                       # national rows come from Table 10
                out.append(C.row(metric="headcount", value=float(v),
                                 **_base(y, _ABS, lines6["Absolute"].get(y), **geo, **_LOC[loc])))
        n += 1
    if n != 12:
        raise ValueError(f"Table 13: expected 12 rows, got {n}")
    # Table 14 -- regional food P0, National/Rural/Urban x 2010/11, 2015/16
    t14 = _page(P, r"Table 14: Trends in regional food poverty headcount indices")
    n = 0
    for l in t14[t14.index("Table 14"):].splitlines():
        m = re.match(r"^(Tigray|Afar|Amhara|Oromia|Somali|B\.G|SNNP|Gambella|Harari|A\.A|Dire Dawa)\s+(.*)$",
                     l.strip())
        if not m:
            continue
        v = [float(x) for x in m.group(2).split()]
        geo = {"geography": _REGION[m.group(1)]}
        if len(v) == 6:
            cuts = [("National", "2010", v[0]), ("National", "2015", v[1]), ("Rural", "2010", v[2]),
                    ("Rural", "2015", v[3]), ("Urban", "2010", v[4]), ("Urban", "2015", v[5])]
        elif len(v) == 4 and m.group(1) == "A.A":
            # Addis Ababa has no rural stratum: national pair, then urban pair.
            cuts = [("National", "2010", v[0]), ("National", "2015", v[1]),
                    ("Urban", "2010", v[2]), ("Urban", "2015", v[3])]
        else:
            continue
        for loc, y, x in cuts:
            out.append(C.row(metric="headcount", value=x, **_base(y, _FOOD, None, **geo, **_LOC[loc])))
        n += 1
    if n != 11:
        raise ValueError(f"Table 14: expected 11 rows, got {n}")
    return pd.DataFrame(out)


# Zones of Annex A5.6b, in print order, with the region each block belongs to.
_ZONE_REGION = [("WESTERN TIGRAY", "Tigray"), ("AFAR_ZONE ONE", "Afar"), ("NORTH GONDAR", "Amhara"),
                ("WEST WELLEGA", "Oromia"), ("SHINILE", "Somali"), ("METEKEL", "Benishangul-Gumuz"),
                ("GURAGHIE", "SNNP"), ("HARARI", "Harari"), ("AA_WOREDA 3_ 4_", "Addis Ababa"),
                ("DIRE DAWA", "Dire Dawa")]


def parse_zones(path: str) -> pd.DataFrame:
    P = T._pages(path, halves=False)["full"]
    pg = _page(P, r"Table A5\.6b: Poverty headcount, poverty gap, and severity indices, in percent")
    out, region, seen = [], None, set()
    starts = dict(_ZONE_REGION)
    for l in pg.splitlines():
        m = re.match(r"^(.+?)\s+((?:\d+\.\d\s+){8}\d+\.\d)\s*$", l.strip())
        if not m:
            continue
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        region = starts.get(name, region)
        if region is None:
            continue
        geo = f"{name} zone, {region}"
        if geo in seen:
            raise ValueError(f"zone twice: {geo}")
        seen.add(geo)
        v = [float(x) for x in m.group(2).split()]
        for k, y in enumerate(("2004", "1999", "1995")):
            for metric, x in zip(("headcount", "gap", "severity"), v[3 * k:3 * k + 3]):
                out.append(C.row(metric=metric, value=x, **_base(y, _ABS, None, geography=geo)))
    # The table prints 58 zones (Tigray 5, Afar 3, Amhara 10, Oromia 12, Somali 3,
    # Benishangul-Gumuz 3, SNNP 15, Harari, 6 Addis Ababa woreda groups, Dire Dawa).
    if len(seen) != 58:
        raise ValueError(f"A5.6b: expected 58 zones, got {len(seen)}")
    out += _mofed2013(P)
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# MoFED 2013 profile: the tables printed on a 0-1 scale (unit "index", kept as
# printed). Filed under "HICES <round> (MoFED 2013 profile)" so they never
# share a merge key with the NPC 2017 report's percent tables for the same
# rounds (the newer report is preferred where series IDs coincide).

_M13 = "MoFED 2013 profile"
_NA = {"-", "--", "---", "----", "na", "Na", "NA", "�", "…", "."}
_NUMV = re.compile(r"^-?\d*\.\d+$|^\d+$")
_REG13 = {**_REGION, "B.B.G": "Benishangul-Gumuz", "BG": "Benishangul-Gumuz",
          "Gambela": "Gambella", "S.N.N.P": "SNNP", "Somale": "Somali"}
_LOCS = {"Rural": dict(topic="locality", locality="rural", locality_label="Rural"),
         "Urban": dict(topic="locality", locality="urban", locality_label="Urban"),
         "Total": {}, "National": {}}
_YR = {"1995/96": "1995", "1995/1996": "1995", "1999/2000": "1999", "1999/00": "1999",
       "2004/05": "2004", "2004/2005": "2004", "2010/11": "2010", "2010/2011": "2010"}
_M3 = ("headcount", "gap", "severity")
_Y4 = ["1995", "1999", "2004", "2010"]


def _b13(year, line, **kw):
    survey, ref = _ROUNDS[year]
    d = dict(survey=f"{survey} ({_M13})", welfare_aggregate="consumption",
             unit_of_analysis="person", line_type="national", period=year,
             reference_period=ref, frequency="ad_hoc", **line)
    d.update(kw)
    return d


def _split(line, n):
    """(label, last n cells) when the line ends in exactly n value-or-blank
    cells after a non-numeric label."""
    tok = line.split()
    if len(tok) < n + 1:
        return None
    vals = tok[-n:]
    if not all(_NUMV.match(v) or v in _NA for v in vals):
        return None
    lab = " ".join(tok[:-n])
    # A label is words ("Eight to 11", ">= 12" may end in a number); a
    # numeric "label" means the line has more cells than the table.
    if not re.search(r"[A-Za-z]|>=|^\d{4}/\d{2,4}$", lab):
        return None
    return lab, [None if v in _NA else float(v) for v in vals]


def _body(P, cap, end=None):
    pg = _page(P, cap)
    s = pg[re.search(cap, pg).end():]
    if end:
        m = re.search(end, s)
        s = s[:m.start()] if m else s
    return s.splitlines()


def _idx(metric, value, **b):
    return C.row(metric=metric, value=value, unit="index", **b)


def _cut(topic, label):
    d = dict(topic=topic, characteristic=label)
    if topic == "sex_of_head":
        d["sex"] = "female" if label.lower().startswith("female") else "male"
    return d


def _loc_cut(cut, loc):
    """A cut crossed with a residence column: the cut keeps its topic, the
    column sets the locality."""
    d = dict(cut)
    if loc in ("Rural", "Urban"):
        d.update(locality=loc.lower(), locality_label=loc)
    return d


def _mofed2013(P) -> list[dict]:
    out = []
    # A5.1 / A5.2 -- national, rural, urban x P0 P1 P2, four rounds
    for cap, end, line in ((r"Table A5\.1: Trends of national and rural/urban poverty", r"Percent Change", _ABS),
                           (r"Table A5\.2: Trends of national and rural/urban food poverty", r"% Change", _FOOD)):
        n = 0
        for l in _body(P, cap, end):
            got = _split(l, 9)
            if not got or got[0] not in _YR:
                continue
            for j, loc in enumerate(("National", "Rural", "Urban")):
                for k, metric in enumerate(_M3):
                    out.append(_idx(metric, got[1][3 * j + k], **_b13(_YR[got[0]], line, **_LOCS[loc])))
            n += 1
        if n != 4:
            raise ValueError(f"{cap}: expected 4 rounds, got {n}")
    # A5.3 / A5.4 -- regional P0, four rounds x rural / urban / total. The
    # Total row repeats A5.1 / A5.2 and is not read. A5.4 prints 0 for urban
    # Afar and Somali in 1995/96 where A5.3 prints "-" (no urban estimate):
    # those two cells cannot be told from missing ones and are not read.
    for cap, line in ((r"Table A5\.3: Trends of regional consumption poverty headcount indices", _ABS),
                      (r"Table A5\.4: Trends of regional food consumption poverty headcount indices", _FOOD)):
        n = 0
        for l in _body(P, cap, r"Source"):
            got = _split(l, 12)
            if not got or got[0] not in _REG13:
                continue
            geo = _REG13[got[0]]
            for k, y in enumerate(_Y4):
                for j, loc in enumerate(("Rural", "Urban", "Total")):
                    v = got[1][3 * k + j]
                    if v is None or (v == 0 and y == "1995" and loc == "Urban"):
                        continue
                    out.append(_idx("headcount", v, **_b13(y, line, geography=geo, **_LOCS[loc])))
            n += 1
        if n != 11:
            raise ValueError(f"{cap}: expected 11 regions, got {n}")
    # 5.5 / 5.6 -- regional P1 and P2, 2010/11 (their P0 repeats A5.3 / A5.4)
    for cap, end, line in ((r"Table 5\.5 Consumption poverty indices in 2010/11", r"Table 5\.6", _ABS),
                           (r"Table 5\.6 Food consumption poverty indices in 2010/11", r"The poverty results", _FOOD)):
        n = 0
        for l in _body(P, cap, end):
            tok = l.split()
            lab = " ".join(t for t in tok if not (_NUMV.match(t) or t in _NA))
            vals = [float(t) for t in tok if _NUMV.match(t)]
            if lab not in _REG13:
                continue
            geo = _REG13[lab]
            if len(vals) == 9:
                cells = {(m, loc): vals[3 * i + j] for i, m in enumerate(_M3)
                         for j, loc in enumerate(("Total", "Urban", "Rural"))}
            elif len(vals) == 6 and geo == "Addis Ababa":       # no rural stratum
                cells = {(m, loc): vals[2 * i + j] for i, m in enumerate(_M3)
                         for j, loc in enumerate(("Total", "Urban"))}
            else:
                raise ValueError(f"{cap}: {l!r}")
            for (m, loc), v in cells.items():
                if m != "headcount":
                    out.append(_idx(m, v, **_b13("2010", line, geography=geo, **_LOCS[loc])))
            n += 1
        if n != 11:
            raise ValueError(f"{cap}: expected 11 regions, got {n}")
    out += _reporting_levels(P)
    # 5.10 -- number of poor people by region, four rounds (the population
    # columns are not read)
    n = 0
    for l in _body(P, r"Table 5\.10 The number of poor people in 1995/96", r"Source"):
        got = _split(l, 8)
        if not got or (got[0] not in _REG13 and got[0] != "Total"):
            continue
        geo = {} if got[0] == "Total" else {"geography": _REG13[got[0]]}
        for y, v in zip(_Y4, got[1][4:]):
            if v is not None:
                out.append(C.row(metric="poor_count", value=v, **_b13(y, _ABS, **geo)))
        n += 1
    if n != 12:
        raise ValueError(f"Table 5.10: expected 12 rows, got {n}")
    out += _chapter6(P)
    return out


# A5.5 (2010/11) / A5.6a (2004/05) reporting levels below the region. Region-
# wide strata ("Tigray Rural", "Harari Urban", "Addis Ababa rural") repeat
# A5.3 and are not read; the towns, the other-urban remainder of each region
# and the Addis Ababa sub-cities are.
_TOWN_REGION = {
    "Mekele": "Tigray", "Mekelle": "Tigray", "Asayta Town": "Afar", "Bahir Dar": "Amhara",
    "Gonder": "Amhara", "Dessie": "Amhara", "DebreZeite": "Oromia", "Jimma": "Oromia",
    "Adama": "Oromia", "Jijjga": "Somali", "Jigjga": "Somali", "Assosa": "Benishangul-Gumuz",
    "Awassa": "SNNP", "Gambella": "Gambella"}
_SUBCITY = {"Arada", "Addis Ketema", "Lideta", "Kirkos", "Yeka", "Bole", "AkakiKaliti",
            "Nefas Silk Lafto", "KolfeKeranyo", "Gulele"}
_OTHER_URBAN = re.compile(r"^Other (\S+?)(?:-Gumuz)? urban$", re.I)
_OTHER_REG = {"Tigray": "Tigray", "Afar": "Afar", "Amhara": "Amhara", "Oromia": "Oromia",
              "Oromiya": "Oromia", "Somali": "Somali", "Somale": "Somali",
              "Benshangul": "Benishangul-Gumuz", "Benishangul": "Benishangul-Gumuz",
              "SNNP": "SNNP", "Gambella": "Gambella"}


def _level_geo(name):
    if name in _SUBCITY:
        return f"{name} sub-city, Addis Ababa"
    if name in _TOWN_REGION:
        return f"{name} town, {_TOWN_REGION[name]}"
    m = _OTHER_URBAN.match(name)
    if m and m.group(1) in _OTHER_REG:
        return f"Other urban areas, {_OTHER_REG[m.group(1)]}"
    return None


def _reporting_levels(P) -> list[dict]:
    out, seen = [], 0
    for l in _body(P, r"Table A5\.5\. Poverty indices by reporting level in 2010/11", r"Note:"):
        got = _split(l, 9)
        if not got:
            continue
        geo = _level_geo(got[0])
        if geo is None:
            if not re.search(r"\b(rural|urban)$", got[0], re.I):
                raise ValueError(f"A5.5: unplaced level {got[0]!r}")
            continue
        # consumption P0 P1 P2, food P0 P1 P2 (calorie-intake poverty not read)
        for k, m in enumerate(_M3):
            out.append(_idx(m, got[1][k], **_b13("2010", _ABS, geography=geo)))
            out.append(_idx(m, got[1][3 + k], **_b13("2010", _FOOD, geography=geo)))
        seen += 1
    if seen != 30:
        raise ValueError(f"A5.5: expected 30 towns / other-urban / sub-cities, got {seen}")
    seen = 0
    for l in _body(P, r"Table A5\.6a: Poverty headcount, poverty gap, and poverty severity indices, by reporting level",
                   r"Note:"):
        m_ = re.match(r"^\d{1,2}\s+(.+)$", l.strip())
        got = _split(m_.group(1), 3) if m_ else None
        if not got:
            continue
        geo = _level_geo(got[0])
        if geo is None:
            if not re.search(r"\b(rural|urban)$", got[0], re.I):
                raise ValueError(f"A5.6a: unplaced level {got[0]!r}")
            continue
        for k, m in enumerate(_M3):
            out.append(_idx(m, got[1][k], **_b13("2004", _ABS, geography=geo)))
        seen += 1
    if seen != 28:
        raise ValueError(f"A5.6a: expected 28 towns / other-urban / sub-cities, got {seen}")
    return out


def _chapter6(P) -> list[dict]:
    out = []
    MET = {"P0": "headcount", "P1": "gap", "P2": "severity"}
    # A6.1 sex of head / A6.5 literacy of head (the text: "households where
    # the head is illiterate"): round x P0-P2 x three residence columns, each
    # an (index, SE) pair; the SE is not read.
    for cap, end, topic, cols, labels in (
            (r"Table A6\.1: Poverty in male and female-headed households", r"Note:", "sex_of_head",
             ("National", "Rural", "Urban"), ("Male-headed", "Female-headed")),
            (r"Table A6\.5: Poverty, by literacy, sex of head", r"% change", "literacy_of_head",
             ("Rural", "Urban", "National"), ("Literate", "Illiterate"))):
        year = metric = None
        n = 0
        for l in _body(P, cap, end):
            tok = l.split()
            if tok and tok[0] in _YR:
                year, tok = _YR[tok[0]], tok[1:]
            if tok and tok[0] in MET:
                metric, tok = MET[tok[0]], tok[1:]
            if len(tok) != 7 or tok[0] not in labels or not (year and metric):
                continue
            v = [float(x) for x in tok[1:]]
            for j, loc in enumerate(cols):
                out.append(_idx(metric, v[2 * j], **_b13(year, _ABS, **_loc_cut(_cut(topic, tok[0]), loc))))
            n += 1
        if n != 24:
            raise ValueError(f"{cap}: expected 24 rows, got {n}")
    # A6.4 household size, four rounds, national. The last band prints a
    # Symbol-font ">=" (U+F0B3) that Table 6.4 prints as ">=12".
    n = 0
    for l in _body(P, r"Table A6\.4: Poverty, by household size and survey year", r"P = headcount"):
        got = _split(l.replace("", ">="), 12)
        if not got:
            continue
        lab = got[0].replace(">= ", ">=")
        for k, y in enumerate(_Y4):
            for i, m in enumerate(_M3):
                out.append(_idx(m, got[1][3 * k + i], **_b13(y, _ABS, **_cut("household_size", lab))))
        n += 1
    if n != 9:
        raise ValueError(f"A6.4: expected 9 sizes, got {n}")
    # 2010/11 by rural / urban / total: 6.4 household size (rural and urban
    # only -- its total repeats A6.4), 6.11 age of head, 6.12 marital status of
    # the head ("divorce or separation of families"). Total rows repeat A5.1.
    for cap, end, topic, cols, nexp in (
            (r"Table 6\.4 Poverty, by household size and place of residence in 2010/11", r"P = headcount",
             "household_size", ("Rural", "Urban", None), 9),
            (r"Table 6\.11\.Poverty by the age of HH head", r"Source", "age_of_head", ("Rural", "Urban", "Total"), 4),
            (r"Table 6\.12Poverty by divorce or separation of families", r"Source", "marital_status_of_head",
             ("Rural", "Urban", "Total"), 3)):
        n = 0
        for l in _body(P, cap, end):
            got = _split(l, 9)
            if not got or got[0] == "Total":
                continue
            for j, loc in enumerate(cols):
                if loc is None:
                    continue
                for i, m in enumerate(_M3):
                    out.append(_idx(m, got[1][3 * j + i], **_b13("2010", _ABS, **_loc_cut(_cut(topic, got[0]), loc))))
            n += 1
        if n != nexp:
            raise ValueError(f"{cap}: expected {nexp} rows, got {n}")
    # 6.6 schooling of the head, 2010/11, national P0-P2
    n = 0
    for l in _body(P, r"Table 6\.6 Poverty and schooling of the household head in 2010/11", r"Notes:"):
        got = _split(l, 3)
        if not got:
            continue
        for i, m in enumerate(_M3):
            out.append(_idx(m, got[1][i], **_b13("2010", _ABS, **_cut("education_of_head", got[0]))))
        n += 1
    if n != 10:
        raise ValueError(f"Table 6.6: expected 10 levels, got {n}")
    # 6.7 industry and 6.8 main occupation of the head ("households headed by
    # individuals who engage in ..."): P0 by rural / urban / total, 2010/11
    # and 2004/05 blocks (the 2004/05 values are MoFED 2008's, republished).
    for cap, prefix, nexp in (
            (r"Table 6\.7 Headcount poverty, by type of employment and place of residence", "Industry: ", 31),
            (r"Table 6\.8 Poverty headcount index, by household head's main occupation in 2010/11", "Occupation: ", 18)):
        year, n = "2010", 0
        for l in _body(P, cap, r"Source"):
            s = l.strip()
            if s.endswith("2010/11") and len(s.split()) <= 2:
                year = "2010"
                continue
            if s == "2004/05":
                year = "2004"
                continue
            got = _split(s, 3)
            if not got or got[0] == "Total":
                continue
            for loc, v in zip(("Rural", "Urban", "Total"), got[1]):
                if v is not None:
                    out.append(_idx("headcount", v, **_b13(year, _ABS, **_loc_cut(
                        _cut("employment_of_head", prefix + got[0]), loc))))
            n += 1
        if n != nexp:
            raise ValueError(f"{cap}: expected {nexp} rows, got {n}")
    return out
