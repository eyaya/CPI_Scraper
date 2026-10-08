"""Madagascar — INSTAT: ENEMPSI 2012 Tome 1 workbook (primary), the RGPH-3
(2018) "Caractéristiques économiques de la population" volume and the EPM
2021-2022 report (extras). The first two are the files `labour/` reads for
composition; the EPM is INSTAT's most recent household survey with a labour
chapter (its listing: /statistiques/enquetes-et-recensements/item/enquete-
periodique-aupres-des-menages-epm). Each file is recognised by its content.

ENEMPSI 2012 (Enquête Nationale sur l'Emploi et le Secteur Informel), sheets
"taux activite", "chômage" and "horaire sous-emploi":

    Tableaux 1-7    taux d'activité by milieu x région, sexe x milieu,
                    région x sexe, âge x milieu, âge x sexe (three age
                    groupings)                       -> labour_force_participation_rate
    Tableaux 18-19  taux d'occupation by milieu, région
                                                     -> employment_to_population_ratio
    Tableaux 131-136  taux de chômage STRICT and ÉLARGI by milieu, région,
                    sexe, âge (two groupings), niveau d'éducation
                                                     -> unemployment_rate strict / broad
    Tableaux 249-254  taux de sous-emploi lié à la durée du travail by milieu,
                    région, sexe, âge (two groupings), niveau d'éducation
                                                     -> underemployment_rate

  `definition` comes from INSTAT's own column headings ("Taux de chômage
  strict" / "Taux de chômage élargi"). The national strict rate is 1,23%,
  the broad 8,03%.

  WORKING-AGE BASE 5+: ENEMPSI covers everyone aged 5 and over -- the activity
  tables print a "5 à 9 ans" row (9,41% active) and the national activity rate
  (63,24) is on that base. The unemployment tables' age rows start at "10 à 14
  ans", but their "Ensemble" (1,23 / 8,03) is the same 5+ active population.

  ONE FIGURE, ONE ROW: the tables cross the same margins repeatedly (the
  "Ensemble" row of Tableau 1 is Tableau 2's; every unemployment table repeats
  1,23 / 8,03). Each value is keyed on the merge key and a repeat is dropped
  only if it agrees (to 0,005); a disagreement raises.

  NOT TAKEN: taux de situation d'emploi inadéquat and taux de sous-emploi
  global (Tableaux 258-272 -- AFRISTAT composites that fold in income-based
  "invisible" underemployment, which no topic here holds); rates by
  previous CSP / institutional sector / branch (no column); the chômeurs'
  characteristics, long-term unemployment shares by group (row splits).

RGPH-3 2018 (census, base 15-59 as every table states), read from PyMuPDF's
one-cell-per-line text because the tables' cells come out in reading order
there:

    Tableaux 3.5-3.7  taux NET d'activité by région / âge / niveau
                      d'instruction, each by milieu x sexe
                                                     -> labour_force_participation_rate
    Tableaux 4.6-4.8  taux de chômage by région / âge / niveau d'instruction,
                      each by milieu x sexe          -> unemployment_rate (and
                      the printed "Jeunes 15 à 30 ans" row -> youth_unemployment_rate)

  NOT TAKEN: the "taux BRUT d'activité" columns (they exceed 100 -- 103,5 in
  Vakinankaratra -- because their numerator is not confined to the 15-59
  denominator); the "taux net d'emploi spécifique" (Tableau 5.4: ~94%, the
  employed as a share of the ACTIVE, not of the population); marital-status
  and welfare-quintile rows (no column holds them).

EPM 2021-2022 (household survey, base 15+, chapter 4, one-column tables):
    Tableaux 4.2/4.3  taux de participation by sexe, milieu, the 23 régions,
                      âge, niveau d'éducation    -> labour_force_participation_rate
    Tableau 4.8       sous-emploi visible        -> underemployment_rate
    Tableau 4.9       taux de chômage            -> unemployment_rate
    Tableau 4.12      chômage des jeunes (15-24) -> youth_unemployment_rate
    Tableau 4.13      NEET (15-24)               -> neet_rate
    Tableau 4.15      emploi informel, total and hors agriculture
                                                 -> informal_employment_share
  NOT TAKEN: 4.14 (share of the informal SECTOR -- composition) and 4.16
  (informal jobs inside the formal sector -- a sub-population). TRAPS: a whole
  number prints without ",0" ("AMORON I MANIA 40"), and Tableau 4.2 breaks
  across a page whose footer "MARS 2024 89" reads as a region worth 89 --
  page furniture is excluded and the 23 regions are asserted.

CROSS-CHECK: ENEMPSI -- activity 63,24 (urban 56,32); occupation 62,5;
unemployment strict 1,23 / broad 8,03 (urban 3,33 / 15,26); underemployment
10,62. RGPH-3 -- unemployment 4,2 (urban 8,7, rural 3,2; Diana 6,7; 15-19 ans
10,9; supérieur 9,1); net activity 73,0 (Analamanga 70,6). EPM 2021-22 -- participation 58,8
(Itasy 74,5); unemployment 6,6; youth 11,2 (universitaire 30,6); NEET 43,4;
informal employment 95,2.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber
import xlrd

from . import _common as C

_KEY = ("topic", "definition", "series_label", "sex", "age_group", "education",
        "geography", "locality", "locality_label", "working_age_base", "period",
        "measure")


class _Rows:
    def __init__(self, tol: float):
        self.rows, self.tol = {}, tol

    def add(self, r, where):
        k = tuple(r[c] for c in _KEY)
        if k in self.rows:
            if abs(self.rows[k]["value"] - r["value"]) > self.tol:
                raise ValueError(f"{where}: {k} printed as {self.rows[k]['value']} "
                                 f"and {r['value']}")
            return
        self.rows[k] = r


# ----------------------------------------------------------------- ENEMPSI
_EN = dict(survey="Enquête Nationale sur l'Emploi et le Secteur Informel (ENEMPSI) 2012",
           period="2012", reference_period="ENEMPSI 2012", frequency="ad_hoc",
           working_age_base="5+")
# table number -> (sheet, topic, series_label)
_EN_TABLES = {
    **{n: ("taux activite", "labour_force_participation_rate", "Taux d'activité")
       for n in range(1, 8)},
    18: ("taux activite", "employment_to_population_ratio", "Taux d'occupation"),
    19: ("taux activite", "employment_to_population_ratio", "Taux d'occupation"),
    **{n: ("chômage", "unemployment_rate", "Taux de chômage") for n in range(131, 137)},
    **{n: ("horaire sous-emploi", "underemployment_rate",
           "Taux de sous-emploi lié à la durée du travail") for n in range(249, 255)},
}
_ROW_DIM = {"région": "geography", "milieu": "locality", "milieu de résidence": "locality",
            "sexe": "sex", "âge": "age", "groupe d'âge": "age",
            "niveau d'éducation": "education"}


def _en_dims(dim, label):
    lab = str(label).strip()
    if lab == "Ensemble":
        return {}
    if dim == "geography":
        return {"geography": lab}
    if dim == "locality":
        return {"locality": C.normalise_locality(lab), "locality_label": lab}
    if dim == "sex":
        sex = C.normalise_sex(lab)
        if sex == "total":
            raise ValueError(f"ENEMPSI: sex {lab!r}")
        return {"sex": sex}
    if dim == "age":
        return {"age_group": lab}
    return {"education": lab}


def _en_col(head):
    h = str(head).strip()
    if h in ("Urbain", "Rural"):
        return {"locality": C.normalise_locality(h), "locality_label": h}
    if h in ("Masculin", "Féminin", "Hommes", "Femmes"):
        return {"sex": C.normalise_sex(h)}
    if h == "Ensemble":
        return {}
    if re.search(r"chômage strict", h):
        return {"definition": "strict"}
    if re.search(r"chômage élargi", h):
        return {"definition": "broad"}
    if re.match(r"(Taux d'occupation|Taux de sous-emploi lié)", h):
        return {}
    raise ValueError(f"ENEMPSI: unknown column {h!r}")


def _enempsi(path, out: _Rows):
    book = xlrd.open_workbook(path)
    found = set()
    for sheet in {s for s, _, _ in _EN_TABLES.values()}:
        sh = book.sheet_by_name(sheet)
        r = 0
        while r < sh.nrows:
            first = str(sh.cell_value(r, 0)).strip()
            m = re.match(r"Tableau (\d+)\s*:", first)
            if not m or int(m.group(1)) not in _EN_TABLES:
                r += 1
                continue
            num = int(m.group(1))
            _, topic, label = _EN_TABLES[num]
            # The header row names the row dimension in column A; the
            # "Unité : %" line above it has column A empty.
            hr = next(i for i in range(r + 1, r + 4)
                      if str(sh.cell_value(i, 0)).strip()
                      and str(sh.cell_value(i, 1)).strip())
            dim_name = str(sh.cell_value(hr, 0)).strip().lower()
            dim = _ROW_DIM.get(dim_name)
            if dim is None:
                raise ValueError(f"ENEMPSI T{num}: row dimension {dim_name!r}")
            cols = [(c, _en_col(sh.cell_value(hr, c))) for c in range(1, sh.ncols)
                    if str(sh.cell_value(hr, c)).strip()]
            n = 0
            for i in range(hr + 1, sh.nrows):
                lab = sh.cell_value(i, 0)
                if not str(lab).strip():
                    break
                d = _en_dims(dim, lab)
                for c, cd in cols:
                    v = sh.cell_value(i, c)
                    if not isinstance(v, float):
                        raise ValueError(f"ENEMPSI T{num}: non-numeric {v!r}")
                    definition = cd.get("definition", "strict" if topic in (
                        "labour_force_participation_rate",) else "not_applicable")
                    dims = {k: v2 for k, v2 in {**d, **cd}.items() if k != "definition"}
                    if set(d) & set(cd) - {"definition"}:
                        raise ValueError(f"ENEMPSI T{num}: dimension clash")
                    out.add(C.row(topic=topic, value=round(v, 9), definition=definition,
                                  series_label=label + (" strict" if definition == "strict"
                                                        and topic == "unemployment_rate"
                                                        else " élargi" if definition == "broad"
                                                        else ""),
                                  series_code=f"ENEMPSI2012 T{num}", **_EN, **dims),
                            f"ENEMPSI T{num}")
                n += 1
            if n < 3:
                raise ValueError(f"ENEMPSI T{num}: {n} rows")
            found.add(num)
            r = i
    missing = set(_EN_TABLES) - found
    if missing:
        raise ValueError(f"ENEMPSI: tables {sorted(missing)} not found")


# ------------------------------------------------------------------ RGPH-3
_RG = dict(survey="Troisième Recensement Général de la Population et de l'Habitation "
                  "(RGPH-3) 2018",
           period="2018", reference_period="RGPH-3 2018", frequency="ad_hoc",
           working_age_base="15-59")
_COLS9 = [({"locality": "urban", "locality_label": "Urbain"}, s) for s in
          ("male", "female", "total")] + \
         [({"locality": "rural", "locality_label": "Rural"}, s) for s in
          ("male", "female", "total")] + [({}, s) for s in ("male", "female", "total")]
_REGIONS = {"Analamanga", "Vakinankaratra", "Itasy", "Bongolava", "Haute Matsiatra",
            "Amoron’i Mania", "Vatovavy Fitovinany", "Ihorombe", "Atsimo Atsinanana",
            "Atsinanana", "Analanjirofo", "Alaotra Mangoro", "Boeny", "Sofia",
            "Betsiboka", "Melaky", "Atsimo Andrefana", "Androy", "Anosy", "Menabe",
            "Diana", "Sava"}
_EDU = {"Sans instruction", "Primaire", "Secondaire 1", "Secondaire 2", "Supérieur"}
_NUM = re.compile(r"^\d{1,3}(?:,\d+)?$")


def _streams(doc, pages):
    """(label, [values]) runs: a label token followed by numeric tokens."""
    toks = []
    for p in pages:
        toks += [t.strip() for t in doc[p].get_text().split("\n") if t.strip()]
    i, out = 0, []
    while i < len(toks):
        if _NUM.match(toks[i]):
            i += 1
            continue
        lab = toks[i]
        # "Jeunes  15 à" / "30 ans": a label split over two tokens.
        if lab.startswith("Jeunes") and i + 1 < len(toks) and toks[i + 1] == "30 ans":
            lab, i = "Jeunes 15 à 30 ans", i + 1
        j = i + 1
        vals = []
        while j < len(toks) and _NUM.match(toks[j]):
            vals.append(float(toks[j].replace(",", ".")))
            j += 1
        out.append((re.sub(r"\s+", " ", lab), vals))
        i = j
    return out


def _rg_dims(lab):
    if lab in _REGIONS:
        return {"geography": lab}
    if lab in _EDU:
        return {"education": lab}
    if re.match(r"^\d{2}-\d{2} ans$", lab):
        return {"age_group": lab}
    if lab in ("MADAGASCAR", "ENSEMBLE"):
        return {}
    return None


def _rgph3(path, out: _Rows):
    doc = fitz.open(path)
    # Activity: Tableaux 3.5-3.7, printed pages 38-42 (PDF 70-74). 18 values
    # per row: taux NET (U H/F/E, R H/F/E, T H/F/E) then taux BRUT -- net only.
    n_act = 0
    for lab, vals in _streams(doc, range(69, 75)):
        if len(vals) != 18:
            continue
        d = _rg_dims(lab)
        topic = "labour_force_participation_rate"
        if lab == "Jeunes 15 à 30 ans":
            d = {"age_group": "15 à 30 ans"}
        if d is None:
            continue                              # marital status, quintiles
        net = vals[:9]
        if max(net) > 100:
            raise ValueError(f"RGPH-3 activity {lab}: net rate over 100")
        for (ld, sex), v in zip(_COLS9, net):
            out.add(C.row(topic=topic, value=v, definition="strict",
                          series_label="Taux net d'activité", sex=sex,
                          series_code="RGPH3 T3.5-3.7", **_RG, **ld, **d),
                    f"RGPH-3 activity {lab}")
        n_act += 1
    # Unemployment: Tableaux 4.6-4.8, printed pages 50-51 (PDF 82-83); 9 values.
    n_un = 0
    for lab, vals in _streams(doc, range(81, 83)):
        if len(vals) != 9:
            continue
        if lab == "Jeunes 15 à 30 ans":
            topic, d = "youth_unemployment_rate", {"age_group": "15 à 30 ans"}
        else:
            topic, d = "unemployment_rate", _rg_dims(lab)
        if d is None:
            continue                              # welfare quintiles
        for (ld, sex), v in zip(_COLS9, vals):
            out.add(C.row(topic=topic, value=v, definition="strict",
                          series_label="Taux de chômage", sex=sex,
                          series_code="RGPH3 T4.6-4.8", **_RG, **ld, **d),
                    f"RGPH-3 unemployment {lab}")
        n_un += 1
    # 22 regions + MADAGASCAR, 9 age groups + Jeunes, 5 education levels, and
    # the ENSEMBLE row printed under both 4.8 and 4.9 (equal; emitted once).
    if n_un != 40:
        raise ValueError(f"RGPH-3 unemployment: {n_un} rows, expected 40")
    if n_act < 30:
        raise ValueError(f"RGPH-3 activity: only {n_act} rows")


# ---------------------------------------------------------------- EPM 21-22
_EP = dict(survey="Enquête Permanente auprès des Ménages (EPM) 2021-2022",
           period="2022", reference_period="EPM 2021-2022", frequency="ad_hoc",
           working_age_base="15+")
# (caption, topic, series_label per value column, definition, fixed age, code)
_EP_TABLES = [
    (r"Tableau 4\.2 : Taux de participation", "labour_force_participation_rate",
     ["Taux de participation de la main d'œuvre"], "strict", None, "T4.2"),
    (r"Tableau 4\.3 : Taux de participation", "labour_force_participation_rate",
     ["Taux de participation de la main d'œuvre"], "strict", None, "T4.3"),
    (r"Tableau 4\.8 : Sous-emploi lié", "underemployment_rate",
     ["Sous-emploi visible (lié à la durée du travail)"], "not_applicable", None, "T4.8"),
    (r"Tableau 4\.9 : Taux de chômage par sexe", "unemployment_rate",
     ["Taux de chômage"], "strict", None, "T4.9"),
    (r"Tableau 4\.12 : Taux de chômage des jeunes", "youth_unemployment_rate",
     ["Taux de chômage des jeunes"], "strict", "15-24", "T4.12"),
    (r"Tableau 4\.13 : Proportion des jeunes ni en emploi", "neet_rate",
     ["Proportion des NEET"], "not_applicable", "15-24", "T4.13"),
    (r"Tableau 4\.15 : Part de l’emploi informel", "informal_employment_share",
     ["Emploi informel", "Emploi informel hors agriculture"], "not_applicable", None,
     "T4.15"),
]
_EP_SECTIONS = {"sexe": "sex", "milieu": "loc", "région": "geo", "age": "age",
                "groupe d’âge (ans)": "age", "niveau d’éducation": "edu",
                "sexe/milieu/age": "sex"}


def _f(s):
    return float(s.replace(",", "."))


def _epm(path, out: _Rows):
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages[115:155])
    for caption, topic, labels, definition, fixed_age, code in _EP_TABLES:
        m = re.search(caption, text)
        if not m:
            raise ValueError(f"EPM {code}: caption not found")
        body = text[m.end():text.index("Source : INSTAT", m.end())]
        # "AMORON I MANIA 40": a whole number prints without its ",0".
        rx = re.compile(rf"^(.+?)((?:\s+\d{{1,3}}(?:,\d)?){{{len(labels)}}})$")
        section, n, national = None, 0, False
        for ln in body.splitlines():
            ln = ln.strip()
            # PAGE FURNITURE: Tableau 4.2 breaks across pages, and the footer
            # "MARS 2024 89" is a label followed by a number -- read naively it
            # is a region whose participation rate is 89.
            if re.match(r"^(MARS 20\d\d|\d+ MARS 20\d\d|RAPPORT EPM|INSTAT-DSCVM)", ln):
                continue
            head = re.match(r"^(Sexe(?:/Milieu/Age)?|Milieu|Région|Age|"
                            r"Groupe d’âge \(ans\)|Niveau d’éducation)\b", ln)
            if head and not rx.match(ln):
                section = _EP_SECTIONS[head.group(1).lower()]
                continue
            mm = rx.match(ln)
            if not mm or section is None:
                continue
            lab = mm.group(1).strip()
            vals = [_f(v) for v in mm.group(2).split()]
            if lab == "National":
                d, national = {}, True
            elif section == "sex" and lab in ("Homme", "Femme"):
                d = {"sex": "male" if lab == "Homme" else "female"}
            elif section in ("sex", "loc") and lab in ("Urbain", "Rural"):
                d = {"locality": C.normalise_locality(lab), "locality_label": lab}
            elif section == "geo":
                d = {"geography": lab}
            elif section in ("age", "sex") and re.match(r"^\d{2}(-\d{2})?( ans|\+)?$", lab):
                d = {"age_group": lab}
            elif section == "edu":
                d = {"education": lab}
            else:
                raise ValueError(f"EPM {code}: row {lab!r} in section {section!r}")
            if fixed_age:
                d = {**d, "age_group": fixed_age}
            for label, v in zip(labels, vals):
                out.add(C.row(topic=topic, value=v, definition=definition,
                              series_label=label, series_code=f"EPM2021-22 {code}",
                              **_EP, **d), f"EPM {code}")
            n += 1
        if not national or n < 4:
            raise ValueError(f"EPM {code}: {n} rows, national row read: {national}")
        if code == "T4.2" and n != 2 + 2 + 23 + 1:
            raise ValueError(f"EPM T4.2: {n} rows, expected 2 sexes, 2 milieux, "
                             f"23 regions and National")


def _kind(path: str) -> str:
    """Each file is recognised by its own content, never by its name."""
    if path.lower().endswith(".xls"):
        return "enempsi"
    with fitz.open(path) as doc:
        head = " ".join(doc[i].get_text() for i in range(min(20, len(doc))))
    if re.search(r"EPM\s*2021\s*-\s*2022", head):
        return "epm"
    if re.search(r"CARACTERISTIQUES ECONOMIQUES DE LA POPULATION", head):
        return "rgph3"
    raise ValueError(f"Madagascar: unrecognised document {path!r}")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    out = {"enempsi": _Rows(0.005), "rgph3": _Rows(0.05), "epm": _Rows(0.05)}
    read = {"enempsi": _enempsi, "rgph3": _rgph3, "epm": _epm}
    for p in [path, *(extras or [])]:
        k = _kind(p)
        read[k](p, out[k])
    return pd.DataFrame([r for o in out.values() for r in o.rows.values()])
