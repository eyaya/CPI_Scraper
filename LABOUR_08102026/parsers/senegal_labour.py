"""Senegal — ANSD, two household surveys that print composition as TABLES:

1. ERI-ESI 2017 (Enquête Régionale Intégrée sur l'Emploi et le Secteur
   Informel), rapport final -- the primary file:
   * Tableau 5.21 "Principaux acteurs de l'offre d'emploi" -- the employed by
     institutional sector, by sex, milieu (Dakar / autres urbains / ensemble
     urbain / rural), the 14 regions and Sénégal -> `sector`;
   * Tableau 5.8 "Bilan de l'emploi", its Total block -- employed COUNTS by
     institutional sector, and the formal / informal split of all employment
     (3,6 / 96,4) -> `sector`, `formality`;
   * Tableau 7.5 -- employed by CITP major group, counts and shares ->
     `occupation`.
2. EHCVM 2018/2019 (Enquête Harmonisée sur les Conditions de Vie des Ménages),
   rapport final, chapter VII.4 -- an extra file:
   * VII-2 / VII-4  secteur institutionnel by milieu / by education -> `sector`
   * VII-5 / VII-7  statut dans l'emploi by milieu / by education
                    -> `employment_status`
   * VII-8 / VII-10 branche d'activité (5 groups) by milieu / by education
                    -> `industry`

WHY SENEGAL WAS BLOCKED, AND WHY IT ISN'T. ANSD's QUARTERLY ENES notes (the
live labour series, listed at /Indicateur/enquete-emploi) draw every
composition cut as a `Graphique` whose labels reach the text layer as scattered
fragments -- that refusal stands, for those notes. The ERI-ESI and EHCVM
reports, listed on ANSD's own /enquete-et-etude/ pages, print the same cuts as
tables. Exactly the Niger/Togo lesson: the employment chapter of an ERI-ESI
report holds household tables, separate from its excluded informal-sector
(UPI) chapters 9-14 -- 9.2-9.7 ("Effectif des emplois", "Répartition des
emplois des actifs occupés") are UPI tables and are NOT read.

THE ERI-ESI UNIVERSE IS THE REPORT'S OWN EMPLOYED POPULATION, checked: "La
population active occupée est estimée à 3 906 070 en 2017" (p.122), which is
both 5.8's Ensemble and 7.5's Sénégal row; 5.21's national shares reproduce
7.5's sector columns (public 4,8 / privé 90,2 / ménages 5,0 vs 4,9).
(Contrast Togo, whose "Bilan de l'emploi" covered 22% of its employed and was
refused.)

PRINTED SUBTOTALS ARE VERIFIED, NOT EMITTED (the Niger/Togo precedent):
5.21's "Secteur privé (3=1+2)" and "Secteur public (6=4+5)", and 7.5's four
skill levels ("Hautement qualifiés non manuels" = groups 1-3, etc.), so each
topic's categories partition the employed. 7.5's remaining columns (age,
income, years of study, formality and sector WITHIN each group) are row
attributes, not composition.

EHCVM's "Ensemble"/"Total" column of the by-education tables repeats the
by-milieu table's national column; it is CHECKED equal and not emitted twice.
The quintile tables (VII-3, VII-6, VII-9 -- the last captioned "statut" but
holding branches) are not read: welfare quintile is not a column here.

BASES: ERI-ESI 15+; EHCVM 15-59 ("la population en âge de travailler
constitue les individus de la tranche d'âge 15-59 ans"). CITP is named
against 7.5 without a revision, the EHCVM groupings are ANSD's own -> National.
EHCVM statut mixes status with employer sector (salarié public / privé) --
filed as employment_status, a hybrid like Chad's and Cameroon's CSP.

PERIODS: ERI-ESI 2017; EHCVM 2019 (two waves, October-December 2018 and
April-July 2019), reference "EHCVM 2018/2019".

CROSS-CHECK: ERI-ESI -- initiative privée 54,8; ménage employeur femmes 10,6;
secteur privé 3 524 192 employed; informal 96,4%; professions élémentaires
968 977 (24,8%). EHCVM -- salarié public 4,8; compte propre rural 52,5;
agriculture 27,4 (rural 50,3); public, supérieur 35,4.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_ERI = dict(survey="Enquête Régionale Intégrée sur l'Emploi et le Secteur "
                   "Informel (ERI-ESI) 2017",
            period="2017", reference_period="ERI-ESI 2017",
            frequency="ad_hoc", working_age_base="15+")
_EH = dict(survey="Enquête Harmonisée sur les Conditions de Vie des Ménages "
                  "(EHCVM) 2018/2019",
           period="2019", reference_period="EHCVM 2018/2019",
           frequency="ad_hoc", working_age_base="15-59")
_P = dict(measure="share", unit="percent")
_N = dict(measure="count", unit="persons")

_COUNT = r"\d{1,3}(?: \d{3})*"
_DEC = r"\d{1,3},\d"


def _f(v: str) -> float:
    return float(v.replace(" ", "").replace(",", "."))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


def _lines_after(path: str, caption: str, pages: range) -> list[str]:
    with pdfplumber.open(path) as pdf:
        for i in pages:
            if i >= len(pdf.pages):
                break
            text = pdf.pages[i].extract_text() or ""
            m = re.search(caption, text)
            if m:
                return [ln.strip() for ln in text[m.end():].splitlines()]
    raise ValueError(f"ANSD: {caption!r} not found")


def _check_between(where, nat, a, b, tol=0.15):
    if not (min(a, b) - tol <= nat <= max(a, b) + tol):
        raise ValueError(f"{where}: national {nat} outside {a} / {b}")


# --------------------------------------------------------------------------
# ERI-ESI 2017
# --------------------------------------------------------------------------

_LEAVES_521 = ["Initiative privée", "Autres acteurs", "Administration publique",
               "Entreprise publique et parapublique", "Ménage employeur", "Total"]
_REGIONS = ["Dakar", "Diourbel", "Fatick", "Kaffrine", "Kaolack", "Kédougou",
            "Kolda", "Louga", "Matam", "Saint-Louis", "Sédhiou", "Tambacounda",
            "Thiès", "Ziguinchor"]
_MILIEU = {"Dakar": ("urban", "Dakar"), "Autres urbains": ("urban", "Autres urbains"),
           "Ens. urbain": ("urban", "Ensemble urbain"), "Rural": ("rural", "Rural")}


def _eri_521(path: str) -> list[dict]:
    lines = _lines_after(path, r"Tableau 5\.21 : Principaux acteurs de l.offre "
                               r"d.emploi selon la r.gion", range(85, 115))
    section, got = None, []
    for ln in lines:
        if ln.startswith("Source"):
            break
        if ln in ("Sexe", "Région"):
            section = ln
            continue
        if ln.startswith("Milieu de"):
            section = "Milieu"
            continue
        m = re.fullmatch(rf"(.+?)\s+((?:{_DEC}\s+){{7}}{_DEC})", ln)
        if not m or section is None:
            continue
        vals = [_f(v) for v in m.group(2).split()]
        got.append((section, m.group(1).strip(), vals))
    labels = [(s, l) for s, l, _ in got]
    want = ([("Sexe", "Homme"), ("Sexe", "Femme")]
            + [("Milieu", k) for k in _MILIEU]
            + [("Région", r) for r in _REGIONS] + [("Région", "Sénégal")])
    if labels != want:
        raise ValueError(f"ERI-ESI T5.21: rows {labels}")
    out = []
    for section, lab, v in got:
        ip, aa, priv, adm, epp, pub, men, tot = v
        where = f"ERI-ESI T5.21 {lab}"
        if abs(priv - (ip + aa)) > 0.15 or abs(pub - (adm + epp)) > 0.15:
            raise ValueError(f"{where}: printed subtotals are not their sums")
        if tot != 100.0 or abs(ip + aa + adm + epp + men - 100) > 0.3:
            raise ValueError(f"{where}: leaves do not sum to 100")
        if section == "Sexe":
            ctx = {"sex": C.normalise_sex(lab)}
        elif section == "Milieu":
            loc, lbl = _MILIEU[lab]
            ctx = {"locality": loc, "locality_label": lbl}
        elif lab == "Sénégal":
            ctx = {}
        else:
            ctx = {"geography": lab}
        for cat, val in zip(_LEAVES_521, (ip, aa, adm, epp, men, tot)):
            out.append(C.row(topic="sector", characteristic=cat,
                             classification="National", value=val,
                             series_code="ERI-ESI T5.21", **_P, **_ERI, **ctx))
    return out


def _eri_58(path: str) -> list[dict]:
    lines = _lines_after(path, r"Tableau 5\.8 : Bilan de l.emploi par secteur "
                               r"institutionnel", range(70, 95))
    start = lines.index("Total")
    rows = []
    for ln in lines[start + 1:start + 6]:
        m = re.fullmatch(rf"(Secteur public|Secteur privé|Ménages|Organisation "
                         rf"internationale|Ensemble)\s+({_DEC})\s+({_DEC})\s+100\s+"
                         rf"({_COUNT})", ln)
        if not m:
            raise ValueError(f"ERI-ESI T5.8: cannot read {ln!r}")
        rows.append((m.group(1), _f(m.group(2)), _f(m.group(3)), _f(m.group(4))))
    *parts, total = rows
    if total[0] != "Ensemble" or sum(p[3] for p in parts) != total[3]:
        raise ValueError("ERI-ESI T5.8: sector counts do not sum to the Ensemble")
    if total[3] != 3906070:
        raise ValueError(f"ERI-ESI T5.8: total {total[3]} is not the report's "
                         f"employed population 3 906 070")
    out = [C.row(topic="sector", characteristic="Total" if lab == "Ensemble" else lab,
                 classification="National", value=n, series_code="ERI-ESI T5.8",
                 **_N, **_ERI) for lab, _, _, n in rows]
    for lab, v in (("Emplois formels", total[1]), ("Emplois informels", total[2])):
        out.append(C.row(topic="formality", characteristic=lab,
                         classification="Not applicable", value=v,
                         series_code="ERI-ESI T5.8", **_P, **_ERI))
    return out


_CITP = ["Directeurs, cadres de direction et gérants",
         "Professions intellectuelles et scientifiques",
         "Professions intermédiaires",
         "Employés de type administratif",
         "Personnel des services directs aux particuliers, commerçants et vendeurs",
         "Agriculteurs et ouvriers qualifiés de l'agriculture, de la sylviculture "
         "et de la pêche",
         "Métiers qualifiés de l'industrie et de l'artisanat",
         "Conducteurs d'installations et de machines, et ouvriers de l'assemblage",
         "Professions élémentaires", "Autres professions"]
_SKILL = {"Hautement qualifiés non manuels": [0, 1, 2],
          "Peu qualifiés non manuels": [3, 4],
          "Qualifiés manuels": [5, 6, 7],
          "Non qualifiés": [8, 9]}


def _eri_75(path: str) -> list[dict]:
    lines = _lines_after(path, r"Tableau 7\.5 : Principales caract.ristiques des "
                               r"actifs occup.s selon les grands groupes de la CITP",
                         range(110, 135))
    rows = []                     # [label, count, share]
    for ln in lines:
        if ln.startswith("Source"):
            break
        m = re.match(rf"(.+?)\s+({_COUNT})\s+({_DEC})\s", ln + " ")
        if m and re.search(r"[A-Za-zé]", m.group(1)) and not ln.startswith("Grands groupes"):
            rows.append([_norm(m.group(1)), _f(m.group(2)), _f(m.group(3))])
        elif rows and re.match(r"^[a-zl']", ln):       # wrapped label tail
            rows[-1][0] = _norm(f"{rows[-1][0]} {ln}")
    byname = {r[0]: r for r in rows}
    want = [_norm(x) for x in _CITP] + list(_SKILL) + ["Sénégal"]
    if sorted(byname) != sorted(want):
        raise ValueError(f"ERI-ESI T7.5: rows {list(byname)}")
    leaves = [byname[_norm(x)] for x in _CITP]
    for sub, idx in _SKILL.items():
        if abs(byname[sub][1] - sum(leaves[i][1] for i in idx)) > 2:
            raise ValueError(f"ERI-ESI T7.5: {sub} is not the sum of its groups")
    total = byname["Sénégal"]
    if total[1] != 3906070 or abs(sum(r[1] for r in leaves) - total[1]) > 2:
        raise ValueError("ERI-ESI T7.5: groups do not sum to the employed total")
    out = []
    for lab, n, pct in leaves + [["Total", total[1], total[2]]]:
        for val, meas in ((n, _N), (pct, _P)):
            out.append(C.row(topic="occupation", characteristic=lab,
                             classification="National", value=val,
                             series_code="ERI-ESI T7.5", **meas, **_ERI))
    return out


# --------------------------------------------------------------------------
# EHCVM 2018/2019
# --------------------------------------------------------------------------

_EDU = ["Sans instruction", "Primaire", "Secondaire 1", "Secondaire 2", "Supérieur"]
_EH_TABLES = [  # (by milieu, by education, topic, rows, code)
    ("VII-2", "VII-4", "sector",
     ["Emploi secteur public", "Emploi secteur privé", "Total"]),
    ("VII-5", "VII-7", "employment_status",
     ["salarié public", "salarié privé", "patron", "travailleur compte propre",
      "aide familiale/apprenti", "Total"]),
    ("VII-8", "VII-10", "industry",
     ["Agriculture", "Industrie", "Commerce", "Transports", "Autres Services",
      "Total"]),
]


def _eh_read(path: str, code: str, labels: list[str], ncols: int):
    lines = _lines_after(path, rf"Tableau {code} :", range(80, 96))
    got = {}
    for ln in lines:
        if ln.startswith("Source"):
            break
        m = re.fullmatch(rf"(.+?)\s+((?:(?:{_DEC}|100)\s+){{{ncols - 1}}}(?:{_DEC}|100))", ln)
        if m and m.group(1) in labels:
            got[m.group(1)] = [_f(v) for v in m.group(2).split()]
    if list(got) != labels:
        raise ValueError(f"EHCVM {code}: rows {list(got)}")
    for j in range(ncols):
        s = sum(v[j] for k, v in got.items() if k != "Total")
        if abs(s - 100) > 0.3 or got["Total"][j] != 100:
            raise ValueError(f"EHCVM {code}: column {j} sums to {s:.1f}")
    return got


def _ehcvm(path: str) -> list[dict]:
    out = []
    for by_mil, by_edu, topic, labels in _EH_TABLES:
        mil = _eh_read(path, by_mil, labels, 3)        # Urbain Rural Total
        edu = _eh_read(path, by_edu, labels, 6)        # 5 levels + Ensemble
        for lab in labels:
            u, r, nat = mil[lab]
            if lab != "Total":
                _check_between(f"EHCVM {by_mil} {lab}", nat, u, r)
            if abs(edu[lab][-1] - nat) > 0.05:
                raise ValueError(f"EHCVM {by_edu} {lab}: Ensemble {edu[lab][-1]} "
                                 f"is not {by_mil}'s national {nat}")
            for ctx, v in (({"locality": "urban", "locality_label": "Urbain"}, u),
                           ({"locality": "rural", "locality_label": "Rural"}, r),
                           ({}, nat)):
                out.append(C.row(topic=topic, characteristic=lab,
                                 classification="National", value=v,
                                 series_code=f"EHCVM {by_mil}", **_P, **_EH, **ctx))
            for level, v in zip(_EDU, edu[lab][:5]):
                out.append(C.row(topic=topic, characteristic=lab,
                                 classification="National", value=v,
                                 education=level, series_code=f"EHCVM {by_edu}",
                                 **_P, **_EH))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _eri_521(path) + _eri_58(path) + _eri_75(path)
    ehcvm = [p for p in (extras or []) if "ehcvm" in p.lower()]
    if len(ehcvm) != 1:
        raise ValueError(f"EHCVM report not among the extras: {extras}")
    rows += _ehcvm(ehcvm[0])
    return pd.DataFrame(rows)
