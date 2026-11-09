"""Côte d'Ivoire -- INS "Enquête sur le Niveau de Vie des ménages" (ENV)
reports, Wayback `id_` copies of INS's own files (ins.ci/ENV/, ins.ci/n/
templates/docss/). INS (now ANStat) measures poverty against the 1985 line
of 75 000 FCFA carried forward by inflation ("seuil relatif ... soit 101 340
Francs CFA en 1993, 144 800 en 1995, 162 800 en 1998 et 183 450 en 2002").

parse_2008 -- "ENV 2008" (ENV2008.pdf):
    Tableau 1.2  P0 by Abidjan / urbain hors Abidjan / urbain / rural /
                 ensemble for 1985 1993 1995 1998 2002 2008 -- the series as
                 republished in this report (survey "ENV <year> (série ENV
                 2008)"; 2008 itself is "ENV 2008").
    Tableau 2.3  P0 P1 P2 by the 11 regions of the time (Centre, Centre Est,
                 ... Abidjan); 2.4 the same split urban / rural (Abidjan has
                 one column). 2.11 / 2.12 the same for EXTREME poverty, with
                 the national row.
parse_2002 -- "ENV 2002" (ENV2002.pdf):
    Tableau 2.1.1 P0 by strata (Abidjan, autres villes, forêt rurale est /
                 ouest, savane rurale) 1985-2002 with each year's line;
    Tableau 2.1.2 the same for the extreme line (63 375 / 86 760 / 95 700 /
                 94 280 FCFA); 3.1.1 P0 by region x milieu, 2002.
    Years before 2002 carry "(série ENV 2002)".
parse_2011 -- "ENV 2011" (ENV2011.pdf): a ZONAL survey (Abidjan's Abobo and
    Yopougon communes, and the West, urban / rural) -- not national.
    Tableau 4: P0 P1 P2 per zone for 2002, 2008 and 2011.

ENV 1993-1995 (ENV1993-1995.pdf, P0 printed as 0-1 proportions): collected by
cote_divoire_env1993_poverty, as the original estimates.

CROSS-CHECK (verbatim): 2008 48,9 / extreme 10,0; Nord 77,3 / 36,1 / 20,6;
Abidjan 21,0; 2002 38,4; Ouest 64,4 (2002); 1985 10,0; ENV 2011 total Ouest
57,4 / 24,6 / 13,6.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

LINE = "Seuil de pauvreté relatif (75 000 FCFA de 1985, actualisé)"
LINE_EXT = "Seuil d'extrême pauvreté (ENV)"
LAYOUT = {"survey": "ENV 2008", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "line_type": "national", "line_level": "overall", "line_name": LINE,
          "period": "2008", "frequency": "ad_hoc", "decimal": ",", "tables": []}
_LOC = {"Abidjan": dict(topic="locality", locality="other", locality_label="Abidjan"),
        "Milieu urbain hors Abidjan": dict(topic="locality", locality="other", locality_label="Urbain hors Abidjan"),
        "Autres Villes": dict(topic="locality", locality="other", locality_label="Urbain hors Abidjan"),
        "Total milieu urbain": dict(topic="locality", locality="urban", locality_label="Urbain"),
        "Total urbain": dict(topic="locality", locality="urban", locality_label="Urbain"),
        "Total milieu rural": dict(topic="locality", locality="rural", locality_label="Rural"),
        "Total rural": dict(topic="locality", locality="rural", locality_label="Rural"),
        "Forêt Rurale Est": dict(topic="locality", locality="other", locality_label="Forêt rurale Est"),
        "Forêt Rurale Ouest": dict(topic="locality", locality="other", locality_label="Forêt rurale Ouest"),
        "Savane Rurale": dict(topic="locality", locality="other", locality_label="Savane rurale"),
        "Ensemble CI": {}, "Ensemble": {}}


def _r(metric, value, survey, period, extreme=False, line_value="", **kw):
    if kw.get("topic") == "locality":
        kw.setdefault("characteristic", kw["locality_label"])
    return C.row(metric=metric, value=value, survey=survey, welfare_aggregate="consumption",
                 line_type="national", line_level="extreme" if extreme else "overall",
                 line_name=LINE_EXT if extreme else LINE, line_value=line_value,
                 line_unit="XOF per person per year" if line_value != "" else "",
                 period=period, reference_period=period, frequency="ad_hoc", **kw)


def _text(pages, caption):
    for t in pages:
        if "...." in t:
            continue
        m = re.search(caption, t)
        if m:
            body = t[m.end():]
            k = re.search(r"^(?:Source|Tableau ?\d)", body, re.M)
            return (body[:k.start()] if k else body).replace("‐", "-")
    raise ValueError(f"caption not found: {caption}")


def _line(text, label, n, plain=False):
    """`plain`: every whitespace-separated token is one cell -- ENV 2015 has no
    thousands, and "8 100" (P2 then contribution) must not fuse into 8100."""
    # The label must be followed by its numbers: "Centre" must not read the
    # "Centre Nord" row, nor "Nord" the "Nord Est" row.
    m = re.search(rf"^{re.escape(label)}\s+(?=[-\d,])(.*)$", text, re.M)
    if plain and m:
        nums = [C.to_number(x, ",") for x in re.findall(r"-?\d+(?:,\d+)?(?=%?(?:\s|$))", m.group(1))]
    else:
        nums = C.numbers_in(m.group(1), decimal=",") if m else []
    if len(nums) != n:
        raise ValueError(f"{label!r}: {nums} (expected {n})")
    return nums


_REG08 = ["Centre Est", "Centre Nord", "Centre Ouest", "Centre", "Nord Est", "Nord Ouest", "Nord",
          "Ouest", "Sud Ouest", "Sud", "Abidjan"]


def _reg_line(text, reg):
    # Region rows carry the chef-lieu and current region names before the
    # numbers ("Nord Korhogo Savanes 77,3 36,1 20,6"); read the last 3 numbers
    # of the line that starts with the region name followed by a capital word.
    for ln in text.splitlines():
        s = ln.strip()
        if re.match(rf"^{reg} [A-Z]", s) and not re.match(rf"^{reg} (?:Est|Nord|Ouest)\b", s):
            nums = C.numbers_in(s, decimal=",")
            return nums[-3:]
    raise ValueError(f"region {reg!r} not found")


def parse_2008(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    rows = []
    t = _text(pages, r"Tableau 1\.2 : Evolution et variation par milieu")
    t = t.split("2. Variation")[0]
    years = ["1985", "1993", "1995", "1998", "2002", "2008"]
    for lab in ("Abidjan", "Milieu urbain hors Abidjan", "Total milieu urbain", "Total milieu rural", "Ensemble CI"):
        for yr, v in zip(years, _line(t, lab, 6)):
            sv = "ENV 2008" if yr == "2008" else f"ENV {yr} (série ENV 2008)"
            rows.append(_r("headcount", v, sv, yr, **_LOC[lab]))
    for cap, ext in ((r"Tableau 2\.3 : Distribution de la pauvreté par région", False),
                     (r"Tableau 2\.11 : Distribution de l’extrême pauvreté par région", True)):
        t = _text(pages, cap)
        for reg in _REG08:
            for m, v in zip(("headcount", "gap", "severity"), _reg_line(t, reg)):
                rows.append(_r(m, v, "ENV 2008", "2008", ext, geography=reg))
        if ext:
            for m, v in zip(("headcount", "gap", "severity"), _line(t, "Ensemble Côte d’Ivoire", 3)):
                rows.append(_r(m, v, "ENV 2008", "2008", ext))
    for cap, ext in ((r"Tableau 2\.4 : Distribution des indicateurs de pauvreté par strate", False),
                     (r"Tableau 2\.12 : Distribution des indicateurs d'extrême pauvreté par strate", True)):
        t = _text(pages, cap)
        for reg in [r for r in _REG08 if r != "Abidjan"]:
            nums = _line(t, reg, 6)
            for k, m in enumerate(("headcount", "gap", "severity")):
                rows.append(_r(m, nums[2 * k], "ENV 2008", "2008", ext, geography=reg, topic="locality",
                               locality="urban", locality_label="Urbain"))
                rows.append(_r(m, nums[2 * k + 1], "ENV 2008", "2008", ext, geography=reg, topic="locality",
                               locality="rural", locality_label="Rural"))
        if ext:
            nums = _line(t, "Ensemble", 6)
            for k, m in enumerate(("headcount", "gap", "severity")):
                rows.append(_r(m, nums[2 * k], "ENV 2008", "2008", ext, **_LOC["Total urbain"]))
                rows.append(_r(m, nums[2 * k + 1], "ENV 2008", "2008", ext, **_LOC["Total rural"]))
    return _dedupe(pd.DataFrame.from_records(rows))


def parse_2002(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    rows = []
    years = ["1985", "1993", "1995", "1998", "2002"]
    lines = {"1985": 75000, "1993": 101340, "1995": 144800, "1998": 162800, "2002": 183450}
    lines_x = {"1993": 63375, "1995": 86760, "1998": 95700, "2002": 94280}
    for cap, ext, labels, n in (
            (r"Tableau 2\.1\.1 : Ratio de pauvreté P", False,
             ["Abidjan", "Autres Villes", "Total urbain", "Forêt Rurale Est", "Forêt Rurale Ouest",
              "Savane Rurale", "Total rural", "Ensemble CI"], 11),
            (r"Tableau 2\.1\.2 : Ratio d’extrême pauvreté", True,
             ["Abidjan", "Autres Villes", "Forêt Rurale Est", "Forêt Rurale Ouest", "Savane Rurale",
              "Ensemble"], 10)):
        t = _text(pages, cap)
        for lab in labels:
            nums = _line(t, lab, n)
            for j, yr in enumerate(years):
                if ext and yr == "1985":
                    continue          # 1985 has no extreme line: the column repeats the overall P0
                sv = "ENV 2002" if yr == "2002" else f"ENV {yr} (série ENV 2002)"
                lv = (lines_x if ext else lines).get(yr, "")
                rows.append(_r("headcount", nums[2 * j + 1], sv, yr, ext, lv, **_LOC[lab]))
    t = _text(pages, r"Tableau 3\.1\.1 : Répartition des individus de l'échantillon et ratio")
    reg = [("Centre-Est", "Centre Est"), ("Centre-Nord", "Centre Nord"), ("Centre-Ouest", "Centre Ouest"),
           ("Centre", "Centre"), ("Nord-Est", "Nord Est"), ("Nord-Ouest", "Nord Ouest"), ("Nord", "Nord"),
           ("Ouest", "Ouest"), ("Sud (hors Abidjan-ville)", "Sud (hors Abidjan-ville)"),
           ("Sud-Ouest", "Sud Ouest"), ("Abidjan-ville", "Abidjan")]
    for raw, geo in reg:
        m = re.search(rf"^{re.escape(raw)} [A-Z][^\d]*\s(\d.*)$", t, re.M)
        if not m:
            raise ValueError(f"3.1.1 {raw!r}")
        s = m.group(1).replace(" - - ", " ")
        nums = C.numbers_in(s, decimal=",")
        if raw == "Abidjan-ville":
            vals = [("urban", nums[2]), ("all", nums[3])]
        else:
            vals = [("rural", nums[2]), ("urban", nums[4]), ("all", nums[5])]
        for loc, v in vals:
            att = {} if loc == "all" else dict(topic="locality", locality=loc,
                                               locality_label="Rural" if loc == "rural" else "Urbain")
            rows.append(_r("headcount", v, "ENV 2002", "2002", False, 183450, geography=geo, **att))
    return _dedupe(pd.DataFrame.from_records(rows))


def parse_2011(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    t = _text(pages, r"Tableau 4: Indices de pauvreté P , P et P par zone")
    zones = {"ABOBO": dict(geography="Abobo (Abidjan)"), "YOPOUGON": dict(geography="Yopougon (Abidjan)"),
             "OUEST URBAIN": dict(geography="Ouest", topic="locality", locality="urban", locality_label="Urbain"),
             "OUEST RURAL": dict(geography="Ouest", topic="locality", locality="rural", locality_label="Rural"),
             "TOTAL OUEST": dict(geography="Ouest")}
    rows = []
    for lab, att in zones.items():
        nums = _line(t, lab, 9)
        for j, yr in enumerate(("2002", "2008", "2011")):
            sv = "ENV 2011 (enquête zonale)" if yr == "2011" else f"ENV {yr} (série ENV 2011, zones)"
            for k, m in enumerate(("headcount", "gap", "severity")):
                rows.append(_r(m, nums[3 * j + k], sv, yr, **att))
    return pd.DataFrame.from_records(rows)


def _dedupe(df):
    key = [c for c in df.columns if c != "value"]
    bad = df[df.duplicated(key, keep=False)].groupby(key)["value"].nunique()
    if (bad > 1).any():
        raise ValueError(f"conflicting duplicates: {bad[bad > 1]}")
    return df.drop_duplicates(key)


parse = parse_2008
LAYOUT_2002 = LAYOUT_2011 = LAYOUT


# --- ENV 2015 ---------------------------------------------------------------
# "ENV 2015 : Profil de pauvreté" (env2015.pdf). Line 269 075 FCFA per person
# per year (the 2008 line 241 145 indexed by the CPI); extreme line 122 385
# (top of the poorest decile, as INS defines it).
#   Tableau 3.1  Urbain / Rural / Ensemble: P0 P1 P2 and their contributions.
#   Tableau 3.3  33 regions + the Abidjan district: same columns (names as
#                printed, upper case; "BOUKANI" is INS's spelling).
#   Tableau 3.4  EXTREME P0 by region x Urbain / Rural / Ensemble (Abidjan
#                prints urban and ensemble only).
#   Tableau 3.5  P0 only (its population-share and contribution columns are
#                misaligned in places -- e.g. "Couple sans enfant" CTR 37,7 vs
#                "Couples avec enfant" 0,5) for Abidjan / Autre urbain / Rural /
#                Ensemble by household size, sex, age, marital status and
#                literacy of the head.
# NOT COLLECTED: Tableau 3.2 (2002 / 2008 / 2015 by former regions): its 2008
# Centre P1 prints "0,2" against 20,3 in the ENV 2008 report itself.
# CROSS-CHECK: 46,3 / 16,3 / 8; extreme 10,0; rural 56,8; Abidjan 22,7;
# Kabadougou 71,7; Bagoué extreme 30,8.
_LINE15, _LINE15X = 269075, 122385
_REG15 = ["VILLE D'ABIDJAN", "HAUT SASSANDRA", "PORO", "GBEKE", "INDENIE-DJUABLIN", "TONKPI",
          "DISTRICT DE YAMOUSSOUKRO", "GONTOUGO", "SAN-PEDRO", "KABADOUGOU", "N'ZI", "MARAHOUE",
          "SUD-COMOE", "WORODOUGOU", "LÔH-DJIBOUA", "AGNEBY-TIASSA", "GÔH", "CAVALLY", "BAFING", "BAGOUE",
          "BELIER", "BERE", "BOUKANI", "FOLON", "GBÔKLE", "GRANDS-PONTS", "GUEMON", "HAMBOL", "IFFOU",
          "LA ME", "NAWA", "TCHOLOGO", "MORONOU"]
_SIX = ("headcount", "poor_share", "gap", "gap_contribution", "severity", "severity_contribution")


def parse_2015(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    sv, rows = "ENV 2015", []
    t = _text(pages, r"Tableau 3\. 1 : Indices et contributions de pauvreté en 2015")
    for lab, att in (("Urbain", _LOC["Total urbain"]), ("Rural", _LOC["Total rural"]), ("Ensemble", {})):
        for m, v in zip(_SIX, _line(t, lab, 6, True)):
            rows.append(_r(m, v, sv, "2015", False, _LINE15, **att))
    t = _text(pages, r"Tableau 3\. 3 : Indices de pauvreté par région en 2015")
    for reg in _REG15:
        for m, v in zip(_SIX, _line(t, reg, 6, True)):
            rows.append(_r(m, v, sv, "2015", False, _LINE15, geography=reg))
    t = _text(pages, r"Tableau 3\. 4 : Ratio d'extrême pauvreté par région")
    for reg in _REG15 + ["Ensemble"]:
        nums = _line(t, reg, 2 if reg == "VILLE D'ABIDJAN" else 3, True)
        locs = [("urban", "Urbain"), ("all", None)] if len(nums) == 2 else [("urban", "Urbain"), ("rural", "Rural"), ("all", None)]
        for (loc, lab), v in zip(locs, nums):
            geo = {} if reg == "Ensemble" else {"geography": reg}
            att = {} if loc == "all" else dict(topic="locality", locality=loc, locality_label=lab)
            rows.append(_r("headcount", v, sv, "2015", True, _LINE15X, **geo, **att))
    t = _text(pages, r"Tableau 3\. 5 : Taux de pauvreté selon les caractéristiques du ménage")
    blocks = [("household_size", [("Moins de 3", "Moins de 3 personnes"), ("Entre 4 et 6", "4 à 6 personnes"),
                                  ("Plus de 6", "Plus de 6 personnes")]),
              ("sex_of_head", [("Masculin", "Masculin"), ("Féminin", "Féminin")]),
              ("age_of_head", [("Moins de 25", "Moins de 25 ans"), ("entre 26 et 35", "26 à 35 ans"),
                               ("entre 36 et 45", "36 à 45 ans"), ("entre 46 et 55", "46 à 55 ans"),
                               ("Plus de 56", "Plus de 56 ans")]),
              ("marital_status_of_head", [("Jamais marié", "Jamais marié"), ("Marié", "Marié"),
                                          ("Divorcé/Séparé", "Divorcé/Séparé"), ("Veuf/ve", "Veuf/ve")]),
              ("literacy_of_head", [("Non", "Non"), ("Oui", "Oui")])]
    mil = [dict(topic=None, locality="other", locality_label="Abidjan"),
           dict(topic=None, locality="other", locality_label="Autre urbain"),
           dict(topic=None, locality="rural", locality_label="Rural"), dict(topic=None, locality="all", locality_label="Total")]
    for topic, labels in blocks:
        for raw, char in labels:
            nums = _line(t, raw, 12, True)
            for j, att in enumerate(mil):
                kw = {k: v for k, v in att.items() if k != "topic"}
                if topic == "sex_of_head":
                    kw["sex"] = "male" if char == "Masculin" else "female"
                rows.append(_r("headcount", nums[3 * j + 1], sv, "2015", False, _LINE15, topic=topic,
                               characteristic=char, **kw))
    return _dedupe(pd.DataFrame.from_records(rows))


LAYOUT_2015 = LAYOUT
