"""Benin — INSAE (now INStaD), "Transition des jeunes femmes et des jeunes hommes
de l'école vers la vie active au Bénin", Rapport final 2014 (ETVA-2014, the
ILO school-to-work transition survey), chapter 6 "Les jeunes ayant un emploi".

REACHED THROUGH THE WAYBACK MACHINE. instad.bj -- and the old insae-bj.org,
which now serves the same page -- answers HTTP 503 "Maintenance en cours, une
nouvelle plateforme arrive prochainement" to every client (seen 2026-09-29,
rechecked 2026-10-01 with plain requests and three browser fingerprints). The
Wayback Machine holds an unchanged capture of INSAE's OWN file
(insae-bj.org .../Autres publications/rapport_analyse_etva2-Benin-2014_final.pdf,
captured 2017-06-06), fetched in its `id_` form, which returns the original
bytes: an archive of the NSO's publication, not an aggregator -- the DR Congo
and Côte d'Ivoire precedent.

A HOUSEHOLD SURVEY OF YOUTH ONLY: ETVA interviewed persons aged 15-29 in a
three-stage sample drawn from the RGPH-4 frame (4 305 youths). Every row is
therefore the composition of YOUTH employment -- `age_group` "15-29 ans" and
`working_age_base` "15-29" on every row, so it can never be read as a
national all-ages distribution.

Three tables of the employed youth (584 985), each counts and % by sex:

* Tableau 6.1  statut dans l'emploi (7 categories)          -> employment_status
* Tableau 6.2  branche d'activité, header "CITI Révision 4" -> industry, ISIC Rev.4
* Tableau 6.3  activité professionnelle, header "CITP-08"   -> occupation, ISCO-08

The schemes are NAMED against the tables (in their column header), so they are
recorded; 6.1's categories carry no scheme name -> National.

UNIVERSE CHECKED: 584 985 is the employed-youth total the report repeats in
every chapter-4/6 table that covers the employed (pp. 24, 26, 32-35, 40-41,
56), and each table's categories sum to it (to within 1, rounding). Tableau
6.4's 470 574 is a SUBSET (three statuses only, despite the prose calling it
"les jeunes occupés") and is not collected; Tableau 3.5's 484 050 counts only
youths no longer in school.

A MISPRINTED THOUSANDS SPACE, READ AS PRINTED DIGITS: Tableau 6.3 prints
"Professions élémentaires 9 6178 16,4". The digits are 96178; only the space is
misplaced. Read as 96 178 because (a) the occupation counts then sum to the
Ensemble EXACTLY (584 985) and (b) 96 178 / 584 985 = 16,4%, the printed share.
Whitelisted in `_MISPRINTS`, checked on every run -- any other malformed
number raises.

"*" MARKS AN ESTIMATE ON FEWER THAN 30 UNWEIGHTED OBSERVATIONS -- the report's
own reliability flag. The values are published and collected; the flag is not
a column in this schema, so it is recorded here: most cells of 6.2 outside
agriculture, manufacturing, construction, commerce, other services and
education carry it.

NOT COLLECTED: Graphique 6.1 (aggregated sectors, a chart that repeats 6.2);
6.4 (a subset, above); 6.5 (benefits -- its "effectifs" exceed the youth
population and are not counts of persons); the Ensemble effectif as a level is
kept only as the Total of each distribution.

PERIOD 2014.

CROSS-CHECK: travailleur indépendant 204 421 (34,9%); travailleurs familiaux
non rémunérés 26,1%; commerce 199 384 (34,1%; femmes 45,5%); agriculture 15,7%;
services directs aux particuliers, commerçants et vendeurs 24,5%; professions
élémentaires 96 178 (16,4%).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = ("Enquête sur la transition des jeunes vers la vie active (ETVA) "
           "2014 -- youth aged 15-29 only")
_PCT = re.compile(r"^\d{1,3},\d$")
_COUNT = re.compile(r"^\d{1,3}(?: \d{3})*$")
# (as printed, -> value), each proven by the table's own arithmetic.
_MISPRINTS = {"9 6178": 96178.0}
_COLS = [{}, {"sex": "male"}, {"sex": "female"}]

_T61 = ["Employé (travail pour une tierce personne contre rémunération)",
        "Employeur", "Travailleur indépendant",
        "Membre d’une coopérative de producteurs",
        "Travailleurs familiaux non-rémunérés", "Autre", "Non Applicable",
        "Ensemble"]
_T62 = ["Agriculture, sylviculture et pêche", "Activités extractives",
        "Activités de fabrication",
        "Production et distribution d’électricité, de gaz, de vapeur et climatisation",
        "Distribution d’eau ; réseau d’assainissement ; gestion des déchets et "
        "activités de remise en état",
        "Construction",
        "Commerce de gros et de détail, réparations de véhicules automobiles et "
        "de motocycles",
        "Transport et entreposage", "Activités d’hébergement et de restauration",
        "Information et communication", "Activités financières et d’assurances",
        "Activités immobilières",
        "Activités professionnelles, scientifiques et techniques",
        "Activités de services administratifs et d’appui",
        "Administration publique et défense ; sécurité sociale obligatoire",
        "Education", "Santé et activités d’action sociale",
        "Arts, spectacles et loisirs", "Autres activités de services",
        "Activités des ménages privés employant du personnel domestique",
        "Activités des organisations et organismes extraterritoriaux",
        "Non Applicable", "Ensemble"]
_T63 = ["Directeurs, cadres de direction et gérants",
        "Professions intellectuelles et scientifiques",
        "Professions intermédiaires", "Employés de type administratif",
        "Personnel des services directs aux particuliers, commerçants et vendeurs",
        "Agriculteurs et ouvriers qualifiés de l’agriculture, de la sylviculture "
        "et de la pêche",
        "Métiers qualifiés de l’industrie et de l’artisanat",
        "Conducteurs d’installations et de machines, et ouvriers de l’assemblage",
        "Professions élémentaires", "Professions militaires", "Non Applicable",
        "Ensemble"]
_TABLES = [
    (r"^Tableau 6\.1\. R.partition des jeunes travailleurs par statut",
     "employment_status", "National", _T61, "ETVA2014 T6.1"),
    (r"^Tableau 6\.2\. R.partition des jeunes occup.s par secteur",
     "industry", "ISIC Rev.4", _T62, "ETVA2014 T6.2"),
    (r"^Tableau 6\.3\. R.partition des jeunes employ.s par activit.",
     "occupation", "ISCO-08", _T63, "ETVA2014 T6.3"),
]


def _split_values(tail: str, where: str) -> list[float] | None:
    """'1 660* 0,3 1 660* 0,6 0* 0,0' -> six numbers. Each share closes the
    count before it, so space-grouped counts split one way only."""
    toks, out, cur = tail.replace("*", "").split(), [], []
    for t in toks:
        if _PCT.match(t):
            if not cur:
                return None
            raw = " ".join(cur)
            if _COUNT.match(raw):
                out.append(float(raw.replace(" ", "")))
            elif raw in _MISPRINTS:
                out.append(_MISPRINTS[raw])
            else:
                raise ValueError(f"{where}: malformed count {raw!r}")
            out.append(float(t.replace(",", ".")))
            cur = []
        elif re.fullmatch(r"\d+", t):
            cur.append(t)
        else:
            return None
    return out if len(out) == 6 and not cur else None


def _read(lines: list[str], caption: str, labels: list[str], where: str):
    start = next((i for i, ln in enumerate(lines) if re.search(caption, ln)), None)
    if start is None:
        raise ValueError(f"{where}: caption not found")
    rows, text = [], []
    for ln in lines[start + 1:]:
        if ln.startswith("Source"):
            break
        m = re.search(r"(?:^|\s)((?:\d[\d ]*\*?\s+\d{1,3},\d\s*){3})$", ln)
        vals = _split_values(m.group(1), where) if m else None
        if vals is not None:
            rows.append(vals)
            ln = ln[:m.start()].strip()
        if ln and not re.match(r"^(Ensemble Hommes Femmes|Effectif % Effectif|"
                               r"Statut dans|CITI R|Activit. professionnelle)", ln):
            text.append(ln)
    if len(rows) != len(labels):
        raise ValueError(f"{where}: {len(rows)} value rows for {len(labels)} labels")
    flat, pos = " ".join(text), 0
    for lab in labels:
        for word in lab.split():
            k = flat.find(word, pos)
            if k < 0:
                raise ValueError(f"{where}: label {lab!r} not in order")
            pos = k + len(word)
    *cats, total = rows
    for j in (0, 2, 4):                      # counts sum to the Ensemble
        s = sum(r[j] for r in cats)
        if abs(s - total[j]) > 2:
            raise ValueError(f"{where}: column {j} counts sum to {s}, Ensemble {total[j]}")
    for j in (1, 3, 5):
        s = sum(r[j] for r in cats)
        if abs(s - 100) > 0.4 or total[j] != 100.0:
            raise ValueError(f"{where}: column {j} shares sum to {s:.1f}")
    return list(zip(labels, rows))


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        lines = [ln.strip() for p in pdf.pages[30:37]
                 for ln in (p.extract_text() or "").splitlines()]
    out = []
    for caption, topic, scheme, labels, code in _TABLES:
        for lab, vals in _read(lines, caption, labels, code):
            lab = "Total" if lab == "Ensemble" else lab
            for k, ctx in enumerate(_COLS):
                for val, meas, unit in ((vals[2 * k], "count", "persons"),
                                        (vals[2 * k + 1], "share", "percent")):
                    out.append(C.row(topic=topic, characteristic=lab,
                                     classification=scheme, value=val,
                                     survey=_SURVEY, period="2014",
                                     reference_period="ETVA-2014",
                                     frequency="ad_hoc", measure=meas,
                                     unit=unit, age_group="15-29 ans",
                                     working_age_base="15-29",
                                     series_code=code, **ctx))
    return pd.DataFrame(out)
