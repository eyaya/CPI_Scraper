"""Tunisia -- INS back-series and sub-national depth (adds to tunisia_poverty).

1. "Mesure de la pauvreté, des inégalités et de la polarisation en Tunisie
   2000-2010" (INS, with AfDB and World Bank, 2012; on ins.tn). P0 for 2000,
   2005, 2010 on INS's high and low lines, by stratum (grandes villes /
   moyennes communes / zones non communales) and by the seven regions
   (Tableaux 7-8); P1 and P2 likewise (Annex A17 a/b, A18 a/b -- the
   "Consommation annuelle" columns, the welfare measure the report retains);
   for 2010, population share, absolute and relative contribution by region
   (Tableaux 9-10) and by education of the head (Tableaux 14-15).
   THIS IS INS'S 2012 METHODOLOGY. Its 2010 rate is 15,5 where the 2021 Volume
   A re-estimates 2010 at 20,5 (2005: 23,3 vs 23,1; 2000: 32,4 vs the web
   table's 25,4). The rows therefore carry their own lines, line_level OTHER --
   "Seuil haut / Seuil bas (série INS 2000-2010)" -- so they get their own
   series ids and never compete with the current series. Standard errors
   (in brackets), the 'priority' ratio (derived) and the 'Dépense totale'
   welfare variant are not collected; CSP tables 12-13 are not read (labels
   wrap around their numbers on both sides).

2. "Carte de la pauvreté en Tunisie, Septembre 2020" (INS / World Bank small
   area estimation, RGPH 2014 x EBCNV 2015). Tableau A2: for 24 gouvernorats,
   the EBCNV 2015 SURVEY P0 (filed under the survey: geography-level detail
   Volume A does not print) and the census-based map estimate; Tableau 4: the
   map estimate for the seven regions; Tableau A3: the map estimate for every
   délégation. Map rows carry the survey label "Carte de la pauvreté 2020
   (RGPH 2014 x EBCNV 2015)", period 2014 (the census the map predicts on).
   Tableau 4's survey column repeats Volume A's 2015 regional rates and is not
   read twice. Standard errors not collected.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_HAUT = "Seuil haut (série INS 2000-2010)"
_BAS = "Seuil bas (série INS 2000-2010)"
_BASE = dict(welfare_aggregate="consumption", unit_of_analysis="person",
             line_type="national", frequency="ad_hoc")
LAYOUT = {"survey": "ENBCNV 2000-2010 (mesure INS 2012)", **_BASE, "line_level": "other",
          "line_name": _HAUT, "period_patterns": [r"(20\d\d)"], "tables": []}
LAYOUT_CARTE = {"survey": "Carte de la pauvreté 2020 (RGPH 2014 x EBCNV 2015)", **_BASE,
                "line_level": "overall", "line_name": "Seuil de pauvreté", "period": "2014", "tables": []}

_STRATA = {
    "Tunisie": {},
    "Grandes villes": dict(topic="locality", characteristic="Grandes villes", locality="other",
                           locality_label="Grandes villes"),
    "Moyennes communes": dict(topic="locality", characteristic="Moyennes communes", locality="other",
                              locality_label="Moyennes communes"),
    "Petites et moyennes communes": dict(topic="locality", characteristic="Moyennes communes", locality="other",
                                         locality_label="Moyennes communes"),
    "Zones non communales": dict(topic="locality", characteristic="Zones non communales", locality="rural",
                                 locality_label="Zones non communales"),
    "Non communal": dict(topic="locality", characteristic="Zones non communales", locality="rural",
                         locality_label="Zones non communales"),
}
_REGIONS = ["Grand Tunis", "Nord Est", "Nord Ouest", "Centre Est", "Centre Ouest", "Sud Est", "Sud Ouest"]
_YEARS = ["2000", "2005", "2010"]


def _row(**kw):
    return C.row(**{**_BASE, **kw})


def _num(tok):
    return float(tok.replace(",", "."))


def _rows_of(text: str, n: int):
    """[(label, [n numbers])] for a block whose rows print the numbers BEFORE
    (or around) the label and standard errors in brackets on their own line.
    Brackets are dropped; numbers accumulate until n are read, the words that
    follow are the label."""
    text = re.sub(r"\(\d+[,.]\d+\)", " ", text)
    out, nums, words = [], [], []
    for tok in text.split():
        if re.fullmatch(r"\d+[,.]\d+|\d+", tok):
            if len(nums) == n and words:
                out.append((" ".join(words), nums))
                nums, words = [], []
            if len(nums) < n:
                nums.append(_num(tok))
            continue
        if len(nums) == n:
            words.append(tok)
    if len(nums) == n and words:
        out.append((" ".join(words), nums))
    return out


def _between(t: str, start: str, end: str | None) -> str:
    i = t.find(start)
    if i < 0:
        raise ValueError(f"'{start}' not found")
    j = t.find(end, i + len(start)) if end else -1
    return t[i + len(start): j if j > 0 else None]


def _attrs(label: str):
    # A label can carry trailing page furniture ("Sud Ouest I n s t i t u t
    # ...", "Non communal Niveau Régional ...") or a sub-heading ("Tunisie Par
    # strate"): match the known stratum / region names by PREFIX, longest first.
    lab = re.sub(r"^(Région|Milieu)\s+", "", label).strip()
    for key in sorted(_STRATA, key=len, reverse=True):
        if lab == key or lab.startswith(key + " "):
            return _STRATA[key]
    for key in _REGIONS:
        if lab == key or lab.startswith(key + " "):
            return dict(geography=key)
    return None


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        P = {i + 1: (p.extract_text() or "") for i, p in enumerate(pdf.pages)}
    out = []

    def emit(metric, value, year, line, unit="percent", **a):
        out.append(_row(metric=metric, value=value, unit=unit, survey=f"ENBCNV {year}",
                        period=year, reference_period=year, line_level="other", line_name=line, **a))

    # Tableaux 7 and 8 -- P0, high line 2000/2005/2010 then low line
    blocks = [_between(P[15], "Tableau 7", "Les valeurs entre"), _between(P[16], "Tableau 8", "Figure 1")]
    for b in blocks:
        b = b.split("2010", 2)[-1] if b.count("2010") >= 2 else b
        for label, v in _rows_of(b, 6):
            a = _attrs(label)
            if a is None:
                continue
            for k, y in enumerate(_YEARS):
                emit("headcount", v[k], y, _HAUT, **a)
                emit("headcount", v[3 + k], y, _BAS, **a)
    # Annex A17 / A18 -- P1, P2 (last three columns = consommation annuelle)
    for pages, metric, tab in (((41, 42), "gap", "A17"), ((43, 44), "severity", "A18")):
        # A..a (low line) runs from p.41/43 onto the top of p.42/44, where
        # A..b (high line) begins at its own caption.
        both = P[pages[0]] + "\n" + P[pages[1]]
        cut = both.find(f"Tableau {tab} b")
        if cut < 0:
            raise ValueError(f"Tableau {tab} b not found")
        for t, line in ((both[:cut], _BAS), (both[cut:], _HAUT)):
            # Read only what follows each column header: the page's running
            # title ("Tu n i s i e 2 0 0 0 - 2 0 1 0"), the prose and the
            # formula above the table would otherwise feed stray digits into
            # the first row. Footers end each segment.
            segs = re.split(r"2000 2005 2010 2000 2005 2010", t)[1:]
            t = "\n".join(re.split(r"I n s t i t u t|Niveau Régional|Tableau A1", s)[0] for s in segs)
            for label, v in _rows_of(t, 6):
                a = _attrs(label)
                if a is None:
                    continue
                for k, y in enumerate(_YEARS):
                    # PUBLISHED DEFECT: A18 a (low line) prints 2005/2010
                    # severity ABOVE the low-line gap (national 2,43 / 1,45
                    # against P1 1,66 / 0,99 -- impossible, P2 <= P1), while
                    # A18 b's 2005/2010 cells (0,14 / 0,04 ...) are of
                    # low-line size: the two tables' 2005-2010 columns look
                    # exchanged in print. Not repaired: severity is kept for
                    # 2000 only, where both tables are consistent.
                    if metric == "severity" and y != "2000":
                        continue
                    emit(metric, v[3 + k], y, line, **a)
    # Tableaux 9/10 (regions) and 14/15 (education of head), 2010
    for pg, cap, end, line, topic in ((18, "Tableau 9", "Ensemble", _BAS, "region"),
                                      (19, "Tableau 10", "Ensemble", _HAUT, "region"),
                                      (21, "Tableau 14", "Ensemble", _BAS, "education_of_head"),
                                      (21, "Tableau 15", "Ensemble", _HAUT, "education_of_head")):
        b = _between(P[pg], cap, end)
        b = b.split("\n", 1)[1]                  # the caption ends "... en 2010"
        b = b[b.find("(%)") + 3:] if "(%)" in b else b
        for label, v in _rows_of(b, 5):
            if topic == "region":
                if label not in _REGIONS:
                    continue
                a = dict(geography=label)
            else:
                if not label.startswith(("Sans niveau", "Niveau")):
                    continue
                a = dict(topic="education_of_head", characteristic=label)
                emit("headcount", v[0], "2010", line, **a)
            emit("population_share", v[1], "2010", line, **a)
            emit("absolute_contribution", v[2], "2010", line, unit="percentage_points", **a)
            emit("poor_share", v[3], "2010", line, **a)
    df = pd.DataFrame(out)
    k = [c for c in df.columns if c not in ("value",)]
    if df.duplicated(k).any():
        raise ValueError(f"duplicate cells: {df[df.duplicated(k, keep=False)].head()}")
    if len(df) != 228:
        raise ValueError(f"{path}: only {len(df)} values")
    return df


def parse_carte2020(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        P = {i + 1: (p.extract_text() or "") for i, p in enumerate(pdf.pages)}
    MAP = dict(survey=LAYOUT_CARTE["survey"], period="2014", reference_period="2014")
    SUR = dict(survey="ENBCNV 2015", period="2015", reference_period="2015")
    out = []

    def emit(v, geo, s):
        out.append(_row(metric="headcount", value=v, unit="percent", geography=geo,
                        line_level="overall", line_name="Seuil de pauvreté", **s))

    t4 = _between(P[18], "Tableau 4", "Source")
    for line in t4.splitlines():
        m = re.match(r"^([A-Z][\w\- ]+?)\s+(\d+,\d)\s+\S+\s+\S+\s+\S+\s+(\d+,\d)\s+\S+\s+\S+$", line.strip())
        if m and m.group(1) != "Tunisie":
            emit(_num(m.group(3)), m.group(1).replace("-", " "), MAP)
    if len(out) != 7:
        raise ValueError(f"{path}: {len(out)} regions read from Tableau 4, expected 7")
    a2 = _between(P[93], "Tableau A2", None)
    for line in a2.splitlines():
        m = re.match(r"^([A-Z][A-Z ]+?)\s+(\d+,\d)\s+\S+\s+\S+\s+\S+\s+(\d+,\d)\s+\S+\s+\S+$", line.strip())
        if m:
            g = m.group(1).strip().title()
            emit(_num(m.group(2)), g + " (gouvernorat)", SUR)
            emit(_num(m.group(3)), g + " (gouvernorat)", MAP)
    deleg = []
    for pg in range(94, 101):
        for line in P[pg].splitlines():
            m = re.match(r"^(.+?)\s+(\d{4})\s+(\d+)\s+(\d+(?:\.\d+)?)\s+(0\.\d+)$", line.strip())
            if m:
                deleg.append((m.group(1).strip(), m.group(2), float(m.group(4))))
    names = pd.Series([d[0] for d in deleg])
    dup = set(names[names.duplicated(keep=False)])
    for name, code, v in deleg:
        emit(v, f"{name} ({code})" if name in dup else name, MAP)
    if len(deleg) < 250:
        raise ValueError(f"{path}: only {len(deleg)} délégations")
    return pd.DataFrame(out)
LAYOUT_CARTE2020 = LAYOUT_CARTE  # tunisia_carte2020_poverty -> parse_carte2020


# ------------------------------------- 3. ENBCNV 2015, Volume A (Arabic) ---
# The Arabic text layer prints labels in VISUAL (reversed) order but numbers
# in the column order of the header, which reads left to right as the page
# shows it. Rows are therefore identified by POSITION, the order every INS
# table uses -- and confirmed by value: the 2005-2015 columns of Tableau 13
# equal Volume A 2021's Tableau 13 exactly (Centre Ouest 49,7 / 42,3 / 30,8).
_R7 = ["Grand Tunis", "Nord Est", "Nord Ouest", "Centre Est", "Centre Ouest", "Sud Est", "Sud Ouest"]
_EDU15 = ["Néant (لاشيء)", "Primaire (ابتدائي)", "Secondaire (ثانوي)", "Supérieur (عالي)"]
_CSP15 = ["Cadres et professions libérales supérieurs", "Cadres et professions libérales moyens",
          "Autres employés", "Patrons dans l'industrie, le commerce et les services",
          "Indépendants dans l'industrie, le commerce et les services", "Ouvriers non agricoles",
          "Exploitants agricoles", "Ouvriers agricoles", "Chômeurs", "Retraités", "Autres inactifs"]
LAYOUT_VOL2015 = {**LAYOUT, "survey": "ENBCNV 2015", "line_level": "overall",
                  "line_name": "Seuil de pauvreté", "period": "2015"}


def _nums_line(line):
    return [float(x.replace(",", ".").replace("٫", ".")) for x in re.findall(r"\d+[.,٫]\d+", line)]


def parse_vol2015(path: str) -> pd.DataFrame:
    """Tableau 13 -- poverty and extreme poverty by the 7 regions, 2000-2015:
    only the 2000 columns are read (2005-2015 = Volume A 2021). Tableaux 14/15
    -- P0 and population share by education and socio-professional category of
    the head, 2015 (weighted P0 reproduces the national 15,2). Tableau 11
    (milieu) repeats the web table; Tableau 12 counts the poor in THOUSANDS
    (no unit for that, not rescaled)."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        t28 = pdf.pages[27].extract_text() or ""
        t33 = pdf.pages[32].extract_text() or ""
    base = dict(line_level="overall", line_name="Seuil de pauvreté")
    out = []
    i = t28.find(":13 لودجلا")
    if i < 0:
        raise ValueError(f"{path}: Tableau 13 not on p. 28")
    rows = [l for l in t28[i:].splitlines() if len(_nums_line(l)) == 8]
    if len(rows) != 7:
        raise ValueError(f"{path}: Tableau 13 has {len(rows)} data rows, expected 7")
    for reg, l in zip(_R7, rows):
        v = _nums_line(l)        # extreme 2015 2010 2005 2000 | poverty 2015 2010 2005 2000
        for val, lvl, name in ((v[3], "extreme", "Seuil de pauvreté extrême"), (v[7], "overall", "Seuil de pauvreté")):
            out.append(_row(metric="headcount", value=val, unit="percent", survey="ENBCNV 2000",
                            period="2000", reference_period="2000", geography=reg,
                            line_level=lvl, line_name=name))
    for cap, labels, topic in ((": 14 لودج", _EDU15, "education_of_head"), (":15 لودج", _CSP15, "employment_of_head")):
        j = t33.find(cap)
        if j < 0:
            raise ValueError(f"{path}: {cap} not on p. 33")
        rows = []
        for l in t33[j:].splitlines()[1:]:
            v = _nums_line(l)
            if len(v) == 2:
                rows.append(v)
                if v[0] == 100.0:
                    break
        tot = rows[-1]
        rows = rows[:-1]
        if len(rows) != len(labels) or tot[1] != 15.2:
            raise ValueError(f"{path}: {cap} read {len(rows)} rows (want {len(labels)}), total {tot}")
        w = sum(s * p for s, p in rows) / 100
        if abs(w - 15.2) > 0.4:
            raise ValueError(f"{path}: {cap} weighted P0 {w:.2f} != 15,2 -- column order?")
        for lab, (share, p0) in zip(labels, rows):
            for metric, val in (("headcount", p0), ("population_share", share)):
                out.append(_row(metric=metric, value=val, unit="percent", survey="ENBCNV 2015",
                                period="2015", reference_period="2015", topic=topic,
                                characteristic=lab, **base))
    return pd.DataFrame(out)
LAYOUT_VOL2015_ALIAS = LAYOUT_VOL2015  # tunisia_vol2015_poverty -> parse_vol2015
