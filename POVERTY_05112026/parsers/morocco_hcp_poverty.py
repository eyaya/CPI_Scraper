"""Morocco -- HCP's monetary-poverty back-series (time depth for morocco_poverty).

Every file is HCP's own, from hcp.ma/downloads/?tag=Pauvreté+et+vulnérabilité
or the indicator pages under "Revenu & conditions de vie > Pauvreté".

1. "Les Indices de la pauvreté 1984-1985 / 1990-1991 / 1998-1999 / 2000-2001"
   (four 4-5 page PDFs, one per survey round: ENCDM 1984/85, ENNVM 1990/91,
   ENNVM 1998/99, ENCDM 2000/01). One layout for all four:
       Variables | Taux de pauvreté | Vulnérabilité | Indice volumétrique |
       Indice de sévérité | Gini | part 10% pauvres | part 10% aisés
   P0 in %, P1 and P2 as 0-1 INDICES (0,055), so unit "index" -- never
   rescaled. Rows: milieu; the 16 regions of the time, each with Urbain and
   Rural sub-rows; sex, marital status and age of the head; household size;
   activity, sector and socio-professional category of the head; schooling and
   diploma of the head. Not collected: vulnerability (a band above the line,
   no metric), Gini and decile shares (inequality), "Nombre d'enfants de
   moins de 15 ans" (no topic). Text repairs: digits letter-spaced
   ("1 4 , 4" -> "14,4"); a "- Rural" label printed on the line ABOVE its
   numbers is re-joined. Rows with a malformed cell ("0,04,8", "0,10,2" in
   1984/85) are dropped whole, never repaired.

2. HCP indicator workbooks (Google Sheets exports linked from hcp.ma):
   "Taux de pauvreté absolue" (Tableau 11: milieu, 2001-2022), "Indices de
   pauvreté selon la région" (12 regions, 2001/2014/2022) and "Taux de
   pauvreté relative" (50% of median income, 2020). The 2001 milieu values
   repeat source 1 exactly and are not read twice. The year HCP labels "2020"
   is the ENSR 2019 survey (HCP's 2024 note: "1,7% en 2019") -- dated 2019.

3. The poverty MAPS (small-area estimates, census x survey): 2014 (RGPH 2014 x
   ENCDM 2014; xls by region, province and commune, each Ensemble / Urbain /
   Rural), 2007 (RGPH 2004 x ENNVM 2007; regions and provinces by milieu from
   the 2007 report) and 2004 (RGPH 2004 x ENCDM 2000/01; provinces). P1/P2 are
   printed in PERCENT here. A map's national figure is a model total (2007:
   9,5 against ENNVM 2007's 8,9), so every map row carries its own survey
   label and never replaces a survey estimate. The 2004/2007 COMMUNE tables
   are not read: province and commune names wrap across lines in both columns
   ("Charf-Mghogha" above "Tanger-Assilah (AR)"), so which words belong to
   which column cannot be told from the text layer.
"""
from __future__ import annotations

import os
import re
import unicodedata

import pandas as pd

from . import _common as C

_LINE = "Seuil national de pauvreté (HCP)"
_BASE = dict(welfare_aggregate="consumption", unit_of_analysis="person",
             line_type="national", line_level="overall", line_name=_LINE,
             frequency="ad_hoc")
LAYOUT = {"survey": "HCP, Indices de la pauvreté", **_BASE,
          "period_patterns": [r"(19\d{2}|20\d{2})"], "tables": []}
LAYOUT_SERIES = {**LAYOUT, "survey": "HCP, indicateurs de pauvreté"}
LAYOUT_CARTE = {**LAYOUT, "survey": "HCP, Carte de la pauvreté"}

_ROUNDS = {"1984_1985": ("ENCDM 1984/85", "1985", "1984/85"),
           "1990_1991": ("ENNVM 1990/91", "1991", "1990/91"),
           "1998_1999": ("ENNVM 1998/99", "1999", "1998/99"),
           "2000_2001": ("ENCDM 2000/01", "2001", "2000/01")}


def _row(**kw):
    kw = {**_BASE, **kw}
    return C.row(**kw)


# ----------------------------------------------------------- 1. indices ---
_BLOCKS = [  # heading regex -> (topic, characteristic prefix)
    (r"^Milieu de r[ée]sidence", ("milieu", "")),
    (r"^R[ée]gion\s*:", ("region", "")),
    (r"^Sexe du chef", ("sex_of_head", "")),
    (r"^Etat matrimonial", ("marital_status_of_head", "")),
    (r"^Groupes d.[âa]ge", ("age_of_head", "")),
    (r"^Nombre d.enfants", (None, "")),
    (r"^Taille du m[ée]nage", ("household_size", "")),
    (r"^Type d.activit[ée]", ("employment_of_head", "Type d'activité: ")),
    (r"^Secteur d.activit[ée]", ("employment_of_head", "Secteur d'activité: ")),
    (r"^Cat[ée]gorie socio", ("employment_of_head", "CSP: ")),
    (r"^Niveau scolaire", ("education_of_head", "Niveau scolaire: ")),
    (r"^Dipl[ôo]me", ("education_of_head", "Diplôme: ")),
    (r"^Caract[ée]ristiques", ("skip", "")),
]
_NUM = re.compile(r"^\d+(?:,\d+)?$")


def _fix(text: str) -> str:
    # "1 4 , 4" / "8 , 1" -> "14,4" / "8,1" (letter-spaced cells)
    text = re.sub(r"(?<![\d,])(\d) (\d) , (\d)", r"\1\2,\3", text)
    text = re.sub(r"(?<![\d,])(\d) , (\d)", r"\1,\2", text)
    return text


def _lines(path: str) -> list[str]:
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            out += [l.strip() for l in _fix(p.extract_text() or "").splitlines() if l.strip()]
    # "- Rural" alone, numbers on the next line -> one line
    joined = []
    for l in out:
        if joined and re.fullmatch(r"-\s*\w[\w ]*", joined[-1]) and re.match(r"^\d", l):
            joined[-1] = joined[-1] + " " + l
        else:
            joined.append(l)
    return joined


def parse_indices(path: str) -> pd.DataFrame:
    key = next((k for k in _ROUNDS if k in os.path.basename(path)), None)
    if key is None:
        raise ValueError(f"{path}: not one of the four HCP 'Indices de la pauvreté' files")
    survey, period, ref = _ROUNDS[key]
    rows, dropped = [], []
    topic, prefix, region = None, "", None
    prev = None
    for line in _lines(path):
        for pat, (t, p) in _BLOCKS:
            if re.search(pat, line):
                if t != "skip":
                    topic, prefix = t, p
                    region = None
                break
        m = re.match(r"^-\s*(.+?)\s*:?\s+((?:\S+\s+){6}\S+)$", line)
        if not m:
            # a wrapped CSP label tail ("libérales") continues the row above
            if prev is not None and topic == "employment_of_head" and re.fullmatch(r"[a-zà-ÿ][\w ’'-]*", line):
                for r in prev:
                    r["characteristic"] = r["characteristic"] + " " + line
            prev = None
            continue
        label, cells = m.group(1).strip(), m.group(2).split()
        prev = None
        if not all(_NUM.match(c) for c in cells):
            dropped.append(line)
            continue
        v = [float(c.replace(",", ".")) for c in cells]
        p0, p1, p2 = v[0], v[2], v[3]
        if topic is None:
            continue
        if topic == "milieu":
            if label.lower().startswith("national"):
                attrs = {}
            elif label.lower().startswith("urbain"):
                attrs = dict(topic="locality", characteristic="Urbain", locality="urban", locality_label="Urbain")
            elif label.lower().startswith("rural"):
                attrs = dict(topic="locality", characteristic="Rural", locality="rural", locality_label="Rural")
            else:
                continue
        elif topic == "region":
            if label.lower() in ("urbain", "rural"):
                if region is None:
                    continue
                lab = label.capitalize()
                attrs = dict(topic="locality", characteristic=lab, geography=region,
                             locality=lab.lower().replace("urbain", "urban"), locality_label=lab)
            else:
                region = label.rstrip(" :")
                attrs = dict(geography=region)
        else:
            if label.lower() == "ensemble":
                continue
            attrs = dict(topic=topic, characteristic=prefix + label)
            if topic == "sex_of_head":
                attrs["sex"] = "male" if label.lower().startswith("masc") else "female"
        made = []
        for metric, val, unit in (("headcount", p0, "percent"), ("gap", p1, "index"),
                                  ("severity", p2, "index")):
            r = _row(metric=metric, value=val, unit=unit, survey=survey, period=period,
                     reference_period=ref, **attrs)
            rows.append(r)
            made.append(r)
        prev = made
    if dropped:
        print(f"[morocco_hcp] {os.path.basename(path)}: {len(dropped)} row(s) with a malformed "
              f"cell dropped: {dropped}")
    if len(rows) < 150:
        raise ValueError(f"{path}: only {len(rows)} values read -- layout changed?")
    return pd.DataFrame(rows)


# ------------------------------------------------- 2. indicator workbooks ---
_MILIEU = {"Urbain": dict(topic="locality", characteristic="Urbain", locality="urban", locality_label="Urbain"),
           "Rural": dict(topic="locality", characteristic="Rural", locality="rural", locality_label="Rural"),
           "Ensemble": {}}
_SERIES = {2007: ("ENNVM 2007", "2007", "2007"), 2014: ("ENCDM 2013/14", "2014", "2013/14"),
           2019: ("ENSR 2019", "2019", "2019 (HCP labels the year 2020)"),
           2022: ("ENNVM 2022/23", "2022", "2022/23")}


def _sheet_rows(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    return [r for ws in wb for r in ws.iter_rows(values_only=True)]


def _year_milieu_table(path):
    rows = _sheet_rows(path)
    hdr = next(i for i, r in enumerate(rows) if any(str(x).strip() in ("Année", "Annee") for x in r if x))
    cols = {str(v).strip(): j for j, v in enumerate(rows[hdr]) if v is not None}
    for r in rows[hdr + 1:]:
        y = r[cols.get("Année", cols.get("Annee"))]
        if isinstance(y, (int, float)):
            yield int(y), {k: r[cols[k]] for k in _MILIEU if k in cols}


def parse_series(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    out = []
    for year, vals in _year_milieu_table(path):
        if year == 2001:
            continue                      # = Indices de la pauvreté 2000-2001
        if year == 2020:
            year = 2019
        survey, period, ref = _SERIES[year]
        for k, v in vals.items():
            if v is not None:
                out.append(_row(metric="headcount", value=float(v), survey=survey, period=period,
                                reference_period=ref, **_MILIEU[k]))
    if len(out) != 12:
        raise ValueError(f"{path}: expected 4 years x 3 milieux, got {len(out)}")
    for ex in extras or []:
        name = os.path.basename(ex)
        if "region" in name:
            rows = _sheet_rows(ex)
            hdr = next(i for i, r in enumerate(rows) if any(str(x).strip() == "Région" for x in r if x))
            cols = [str(v).strip() if v is not None else "" for v in rows[hdr]]
            years = {j: int(re.search(r"(20\d\d)", c).group(1)) for j, c in enumerate(cols) if re.search(r"20\d\d", c)}
            rcol = cols.index("Région")
            for r in rows[hdr + 1:]:
                reg = str(r[rcol] or "").strip()
                if not reg or reg == "Total":
                    continue
                for j, y in years.items():
                    if r[j] is None:
                        continue
                    survey, period, ref = {2001: ("ENCDM 2000/01", "2001", "2000/01")}.get(y) or _SERIES[y]
                    # THE 12 REGIONS OF 2015, NOT THE 16 OF THE INDICES FILES.
                    # Two names coincide ("Oriental"; "Grand Casablanca", which
                    # here is Casablanca-Settat: 6,9 in 2001 against the old
                    # region's 2,2), so these rows carry their own survey label
                    # and can never overwrite the old-region estimates.
                    survey = f"{survey} (12 régions, découpage 2015)"
                    out.append(_row(metric="headcount", value=float(r[j]), survey=survey,
                                    period=period, reference_period=ref, geography=reg))
        elif "relative" in name:
            for year, vals in _year_milieu_table(ex):
                if year == 2020:
                    year = 2019
                for k, v in vals.items():
                    if v is None:
                        continue
                    out.append(_row(metric="headcount", value=float(v), survey="ENSR 2019",
                                    period=str(year), reference_period="2019 (HCP labels the year 2020)",
                                    welfare_aggregate="income", line_type="relative", line_level="other",
                                    line_name="Pauvreté relative: 50% de la médiane du revenu", **_MILIEU[k]))
    return pd.DataFrame(out)


# ------------------------------------------------------------- 3. maps ---
def _deacc(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn").lower()


_LOC = {"ensemble": {}, "urbain": dict(topic="locality", characteristic="Urbain", locality="urban", locality_label="Urbain"),
        "rural": dict(topic="locality", characteristic="Rural", locality="rural", locality_label="Rural")}


def parse_carte2014(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Communes (primary xls, sheet 'Ensemble'), plus region and province xls."""
    S = dict(survey="Carte de la pauvreté 2014 (RGPH 2014 x ENCDM 2014)", period="2014",
             reference_period="2014")
    out = []

    skipped = []

    def emit(geo, p0, p1, p2, attrs):
        # "PM" (pour mémoire) marks a commune HCP gives no estimate for: no row.
        vals = [pd.to_numeric(str(v).strip(), errors="coerce") for v in (p0, p1, p2)]
        if any(pd.isna(v) for v in vals):
            skipped.append(geo)
            return
        for metric, v in zip(("headcount", "gap", "severity"), vals):
            out.append(_row(metric=metric, value=round(float(v), 4), unit="percent", geography=geo, **S, **attrs))

    x = pd.read_excel(path, sheet_name="Ensemble")
    x.columns = [str(c).strip() for c in x.columns]
    x = x.dropna(subset=["Commune"])
    sp = lambda s: s.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)  # noqa: E731
    geo = sp(x["Commune"]) + " (" + sp(x["Province"]) + ")"
    if geo.duplicated().any():
        raise ValueError(f"duplicate commune labels: {list(geo[geo.duplicated()])[:5]}")
    for g, (_, r) in zip(geo, x.iterrows()):
        emit(g, r["Taux de pauvreté (en%)"], r["Indice volumétrique (en%)"], r["Indice de sévérité (en%)"], {})
    n_comm = len(x)
    for ex in extras or []:
        sheets = pd.read_excel(ex, sheet_name=None)
        for sname, d in sheets.items():
            attrs = _LOC[_deacc(sname).strip()]
            d.columns = [str(c).strip() for c in d.columns]
            pcol = next(c for c in d.columns if c.startswith("Taux de pauvret"))
            if "libellé de la province" in d.columns:
                names = d["libellé de la province"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True) + " (province)"
            else:
                names = d["region_12postes"].astype(str).str.strip()
            for g, (_, r) in zip(names, d.iterrows()):
                if pd.isna(r[pcol]):
                    continue
                emit(g, r[pcol], r["Indice volumétrique"], r["Indice de sévérité"], attrs)
    if skipped:
        print(f"[morocco_hcp] carte 2014: {len(skipped)} unit(s) printed 'PM' (no estimate) skipped: {skipped[:5]}")
    if n_comm < 1500:
        raise ValueError(f"only {n_comm} communes read")
    return pd.DataFrame(out)


def _pdf_tables(path, pages):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        for i in pages:
            yield i, (pdf.pages[i - 1].extract_text() or "")


def parse_carte2007(path: str) -> pd.DataFrame:
    """Annexe 2, Tableaux 1 (regions) and 2 / 1 (provinces), Ensemble / Urbain / Rural."""
    S = dict(survey="Carte de la pauvreté 2007 (RGPH 2004 x ENNVM 2007)", period="2007", reference_period="2007")
    out = []
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        texts = [(i + 1, p.extract_text() or "") for i, p in enumerate(pdf.pages[:27])]
    level = milieu = None
    for i, t in texts:
        low = _deacc(t)
        if "indicateurs regionaux de la pauvrete" in low:
            level = "region"
        elif "indicateurs provinciaux de la pauvrete" in low or "par province (milieu" in low:
            level = "province"
        elif level == "province" and "tableau" not in low:
            # The national provincial table runs onto p.22 with NO caption and
            # no header: it inherits the previous page's table.
            pass
        else:
            level = None
            continue
        if "tableau" in low:
            m = re.search(r"\((niveau national|milieu urbain|milieu rural|milieu\s*\n?\s*(?:urbain|rural))", low)
            milieu = "ensemble" if (m is None or "national" in m.group(1)) else ("urbain" if "urbain" in m.group(1) else "rural")
        for line in t.splitlines():
            mm = re.match(r"^(\D+?)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)$", line.strip())
            if not mm:
                continue
            name = re.sub(r"\s+", " ", mm.group(1)).strip()
            if name.lower() in ("total",):
                continue
            geo = name if level == "region" else f"{name} (province)"
            for metric, v in (("headcount", mm.group(2)), ("gap", mm.group(3)), ("severity", mm.group(4))):
                out.append(_row(metric=metric, value=float(v), unit="percent", geography=geo, **S, **_LOC[milieu]))
    df = pd.DataFrame(out)
    if len(df) < 600:
        raise ValueError(f"{path}: only {len(df)} values")
    return df


def parse_carte2004(path: str) -> pd.DataFrame:
    """Annexe 2, Tableau 1: provinces -- P0 and P2 (no P1 printed); vulnerability,
    IDH and IDS not read."""
    S = dict(survey="Carte de la pauvreté 2004 (RGPH 2004 x ENCDM 2000/01)", period="2004",
             reference_period="2004")
    out = []
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        lines = []
        for p in pdf.pages[13:15]:
            lines += [l.strip() for l in (p.extract_text() or "").splitlines() if l.strip()]
    pending = ""
    for l in lines:
        mm = re.match(r"^(\D*?)\s*(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?|-)$", l)
        if mm:
            name = re.sub(r"\s+", " ", (pending + " " + mm.group(1)).strip())
            pending = ""
            name = {"Azila l": "Azilal"}.get(name, name)
            if not name:
                continue
            for metric, v in (("headcount", mm.group(2)), ("severity", mm.group(4))):
                out.append(_row(metric=metric, value=float(v.replace(",", ".")), unit="percent",
                                geography=f"{name} (province)", **S))
        elif re.fullmatch(r"[A-ZÀ-Ý][\w’'éèêâîôûç .-]*", l) and len(l) < 30 and not re.search(
                r"(?i)province|pauvret|indice|taux|humain|social|tableau|notation|vuln", l):
            pending = l
        else:
            pending = ""
    df = pd.DataFrame(out)
    if df["geography"].nunique() < 60:
        raise ValueError(f"{path}: only {df['geography'].nunique()} provinces")
    return df


# Registry entry points. `morocco_hcp_poverty` (this module's parse/LAYOUT) is
# the four "Indices de la pauvreté" descriptors; the others are extra keys:
#   morocco_series_poverty    -> parse_series,    LAYOUT_SERIES
#   morocco_carte2014_poverty -> parse_carte2014, LAYOUT_CARTE
#   morocco_carte2007_poverty -> parse_carte2007, LAYOUT_CARTE
#   morocco_carte2004_poverty -> parse_carte2004, LAYOUT_CARTE
parse = parse_indices


# ----------------------------------------- 4. Dynamique de la pauvreté ---
_DYN_SURVEY = {"1985": ("ENCDM 1984/85", "1984/85"), "1991": ("ENNVM 1990/91", "1990/91"),
               "2001": ("ENCDM 2000/01", "2000/01"), "2007": ("ENNVM 2007", "2007")}


def parse_dynamique(path: str) -> pd.DataFrame:
    """'Dynamique de la pauvreté 1985-2007' (HCP), two tables.

    p.19 Tableau 1 -- by milieu, for 1985/1991/2001/2007: "Valeurs Pa" (P0, P1,
    P2 in %), "Contribution absolue" and "Contribution relative". Taken: the
    RELATIVE contributions of urban and rural to P0, P1 and P2 (poor_share /
    gap_contribution / severity_contribution), the absolute contributions to P0
    (absolute_contribution), and the 2007 P1 and P2 values -- the only values
    not already collected from the indices files (whose 1985-2001 P1/P2 are the
    same figures as 0-1 indices) and from Tableau 11 (2007 P0; this table prints
    urban 4,8 where Tableau 11 prints 4,9, so 2007 P0 is not read twice).
    Absolute contributions to P1/P2 have no metric; Ensemble rows (100 / = P)
    are trivial.
    p.52 Tableau 1 -- national P0 of the 1994 and 2004 poverty MAPS (16,5 and
    14,2). Its survey years repeat other files and are not read (its 1985 is
    21,1 against the indices file's 21,0; 1999 16,3 against 16,2).
    """
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        t19 = pdf.pages[18].extract_text() or ""
        t52 = pdf.pages[51].extract_text() or ""
    if "Contribution du milieu de résidence" not in t19:
        raise ValueError(f"{path}: p.19 is no longer Tableau 1 (contributions)")
    years = ["1985", "1991", "2001", "2007"]
    out = []
    block = None
    for line in t19.splitlines():
        s = line.strip()
        if s.startswith("Taux de pauvreté"):
            block = "P0"
        elif s.startswith("Profondeur"):
            block = "P1"
        elif s.startswith("Sévérité") or s.startswith("Severite"):
            block = "P2"
        m = re.match(r"^(Urbain|Rural|Ensemble)\s+((?:\d+(?:,\d+)?\s+){11}\d+(?:,\d+)?)$", s)
        if not m or block is None:
            continue
        lab = m.group(1)
        v = [float(x.replace(",", ".")) for x in m.group(2).split()]
        vals, absc, rel = v[0:4], v[4:8], v[8:12]
        attrs = {} if lab == "Ensemble" else dict(_MILIEU[lab])
        metric = {"P0": "headcount", "P1": "gap", "P2": "severity"}[block]
        relm = {"P0": "poor_share", "P1": "gap_contribution", "P2": "severity_contribution"}[block]
        for y, val, a, r in zip(years, vals, absc, rel):
            survey, ref = _DYN_SURVEY[y]
            base = dict(survey=survey, period=y, reference_period=ref, **attrs)
            if y == "2007" and block != "P0":
                out.append(_row(metric=metric, value=val, unit="percent", **base))
            if lab == "Ensemble":
                continue
            out.append(_row(metric=relm, value=r, unit="percent", **base))
            if block == "P0":
                out.append(_row(metric="absolute_contribution", value=a, unit="percentage_points", **base))
    hdr = re.search(r"Indicateurs\s+((?:\d{4}\s+){6}\d{4})", t52)
    row = re.search(r"Taux de pauvreté en %\s+((?:\d+(?:,\d+)?\s+){6}\d+(?:,\d+)?)", t52)
    if not (hdr and row):
        raise ValueError(f"{path}: p.52 Tableau 1 not found")
    for y, v in zip(hdr.group(1).split(), row.group(1).split()):
        if y in ("1994", "2004"):
            survey = {"1994": "Carte de la pauvreté 1994",
                      "2004": "Carte de la pauvreté 2004 (RGPH 2004 x ENCDM 2000/01)"}[y]
            out.append(_row(metric="headcount", value=float(v.replace(",", ".")), survey=survey,
                            period=y, reference_period=y))
    if len(out) != 4 * 2 * 4 + 2 * 3 + 2:   # 32 contributions + 6 values + 2 maps
        raise ValueError(f"{path}: {len(out)} values, expected 40")
    return pd.DataFrame(out)
LAYOUT_DYN = LAYOUT  # morocco_dynamique_poverty -> parse_dynamique


# --------------------------- 5. Pauvreté et prospérité partagée 2001-2014 ---
_PP_BLOCKS = [
    (r"^Taux de pauvreté par groupe d'âge du CM", ("age_of_head", "headcount", {})),
    (r"^Taux de pauvreté par groupe d'âge$", ("age", "headcount", {})),
    (r"^Répartition des pauvres par sexe du chef", ("sex_of_head", "poor_share", {})),
    (r"^Taux de pauvreté par niveau scolaire du chef", ("education_of_head", "headcount", {})),
    (r"^Taux de pauvreté selon l.alphabétisation du chef", ("literacy_of_head", "headcount", {})),
]


def parse_prosperite(path: str) -> pd.DataFrame:
    """'Pauvreté et prospérité partagée au Maroc du troisième millénaire,
    2001-2014' (HCP/World Bank joint study, on hcp.ma). Annexe E (pp. 77-78):
    P0 by age group of the head, age of the person, schooling and literacy of
    the head, and the share of the poor by sex of the head -- 2007 and 2014,
    each Urbain / Rural / National. Tableau 5 (p. 48): P0 by sex of the head.
    Its 'National' rows repeat the survey totals and are skipped; structure /
    average-size / enrolment blocks are not poverty measures.
    """
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        lines = []
        for i in (76, 77):
            lines += [l.strip() for l in (pdf.pages[i].extract_text() or "").splitlines()]
        t48 = pdf.pages[47].extract_text() or ""
    if "Annexe E" not in "\n".join(lines):
        raise ValueError(f"{path}: Annexe E not on pp. 77-78")
    cols = [("2007", "urban"), ("2007", "rural"), ("2007", "all"),
            ("2014", "urban"), ("2014", "rural"), ("2014", "all")]
    surv = {"2007": ("ENNVM 2007", "2007"), "2014": ("ENCDM 2013/14", "2013/14")}
    loc = {"urban": dict(locality="urban", locality_label="Urbain"),
           "rural": dict(locality="rural", locality_label="Rural"), "all": {}}
    out, cur = [], None
    for s in lines:
        hit = next((b for pat, b in _PP_BLOCKS if re.search(pat, s)), None)
        if hit:
            cur = hit
            continue
        m = re.match(r"^(.+?)\s+((?:\d+,\d+\s+){5}\d+,\d+)$", s)
        if not m:
            # Any other block heading ends the block -- but not the page
            # number at the foot of p. 77, where the literacy block continues.
            if s and not s.isdigit() and not s.startswith(("Urbain", "Caract")):
                cur = None
            continue
        if cur is None:
            continue
        lab = re.sub(r"\s+", " ", m.group(1)).replace("–", "-").strip()
        if lab == "National":
            continue
        topic, metric, extra = cur
        v = [float(x.replace(",", ".")) for x in m.group(2).split()]
        attrs = dict(topic=topic, characteristic=lab)
        if topic == "sex_of_head":
            attrs["sex"] = "male" if lab == "Homme" else "female"
        if topic == "age":
            attrs["age_group"] = lab
        for (y, l), val in zip(cols, v):
            survey, ref = surv[y]
            out.append(_row(metric=metric, value=val, survey=survey, period=y,
                            reference_period=ref, **attrs, **loc[l]))
    m = re.search(r"Taux de pauvreté\s+((?:\d+,\d\s+){5}\d+,\d)", t48)
    if not m or "Masculin Féminin Ensemble" not in t48:
        raise ValueError(f"{path}: Tableau 5 (p. 48) not found")
    v = [float(x.replace(",", ".")) for x in m.group(1).split()]
    for (y, lab, sx), val in zip([("2007", "Masculin", "male"), ("2007", "Féminin", "female"), ("2007", None, None),
                                  ("2014", "Masculin", "male"), ("2014", "Féminin", "female"), ("2014", None, None)], v):
        if lab is None:
            continue
        survey, ref = surv[y]
        out.append(_row(metric="headcount", value=val, survey=survey, period=y, reference_period=ref,
                        topic="sex_of_head", characteristic=lab, sex=sx))
    if len(out) != 76:
        raise ValueError(f"{path}: only {len(out)} values")
    return pd.DataFrame(out)


LAYOUT_PP = LAYOUT  # morocco_prosperite_poverty -> parse_prosperite
