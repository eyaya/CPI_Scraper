"""Chad — INSEED ECOSIT4 (Quatrième Enquête sur la Consommation des Ménages
et le Secteur Informel), Rapport général, chapter 7 "Emploi".

A HOUSEHOLD survey, not a labour force survey -- ECOSIT4 is Chad's
consumption/poverty survey with an employment section -- so the universe is
the right one (persons in households, informal and agricultural work included)
even though the instrument is not a dedicated LFS. Base 15+ ("les personnes
actives occupées de 15 ans et plus"). National figures only.

Three distributions of the "emplois principaux":

* Tableau 7.06  catégorie socioprofessionnelle (7 categories) -> employment_status;
* Tableau 7.07  secteur d'activité (11 branches)             -> industry;
* Tableau 7.08  branche institutionnelle (5 units), counts and % -> sector.

CSP IS FILED AS STATUS, AND IT IS A HYBRID. Patron / travailleur indépendant /
aide familial-apprenti are statuses in employment; cadre supérieur / cadre
moyen / employé-ouvrier / manœuvre subdivide EMPLOYEES by skill. The seven
together partition the employed (they sum to 100), which is what a status
distribution is, and INSEED's own caption calls it the CSP -- hence National,
never ICSE.

"% FEMMES" IS NOT COLLECTED. Each table's second column is the share of women
WITHIN the category (row percentage), which this indicator does not collect
(README: "Row percentages are not collected"). Tableau 7.08's "années
d'études réussies" is a mean, with no topic here.

TABLEAU 7.08 IS READ FROM THE TEXT LAYER, not by the engine. Two of its labels
wrap, and INSEED's layout splits the ROW'S VALUES across the wrap:

    Entreprise publique ou parapublique/organisme
    0,5 20,6
    international 27 609 10,4

-- the percentage and % femmes on the middle line, the count and years of
study on the last. No line reader can put those back without being told the
shape, so `_table_7_08` states it: every row must yield exactly one count and
one percentage, the five units must sum to the printed Ensemble (5 674 675,
100,0), and the labels must be the five printed ones, in order.

NOT COLLECTED: Tableau 7.10 (hours by enterprise type / CSP / residence / sex)
is ROW percentages -- and visibly defective: its "Masculin" row repeats
"Ensemble urbain" digit for digit (53,5 6,6 16,4 23,5), "Féminin" repeats
"Rural", "Patron" repeats "Ménage comme employeur", and "Maître communautaire"
sums to 51,1. Tableaux 7.01-7.05 and 7.11-7.25 are rates belonging to
`unemployment`.

NO NOMENCLATURE IS NAMED -- CITI, CITP, NAEMA and "nomenclature" appear
nowhere in the report -- so every category is National.

PERIOD 2019, reference "2018-2019": collection ran in two waves, July-September
2018 and January-April 2019 (section 2.4.3), and multi-year rounds are dated
to their final year as Liberia's 2016-17 LFS is.

CROSS-CHECK (% of emplois principaux, 15+): travailleur indépendant 58,1;
aide familial/apprenti 34,7; agriculture 72,1; commerce 8,1; entreprise
privée 5 471 217 (96,4); administration 122 625 (2,2); ensemble 5 674 675.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C
from .pdf_tables_labour import make_parser

_P = {"measure": "share", "unit": "percent"}

LAYOUT = {
    "survey": "Quatrième Enquête sur la Consommation des Ménages et le "
              "Secteur Informel au Tchad (ECOSIT4)",
    "frequency": "ad_hoc", "working_age_base": "15+",
    "period": "2019", "reference_period": "2018-2019",
    "decimal": ",",
    "tables": [
        {"caption": r"^Tableau 7\.06 : R.partition des emplois principaux par "
                    r"cat.gorie socioprofessionnelle",
         "topic": "employment_status", "classification": "National",
         # distribution | % femmes (a row percentage -- skipped)
         "columns": [_P, {"skip": True}],
         "series_code": "ECOSIT4 T7.06",
         # Prose follows each table on the same page with no caption between,
         # and carries paired figures ("(96,4%) ... (2,2%)"): close on the
         # table's own Ensemble row.
         "end_after": r"^Ensemble\s+100\b",
         "label_map": {"Ensemble": "Total"},
         "row_scan": {"expect_rows": 8}},
        {"caption": r"^Tableau 7\.07 : R.partition des emplois principaux par "
                    r"secteur d.activit",
         "topic": "industry", "classification": "National",
         "columns": [_P, {"skip": True}],
         "series_code": "ECOSIT4 T7.07",
         "end_after": r"^Ensemble\s+100\b",
         "label_map": {"Ensemble": "Total"},
         "row_scan": {"expect_rows": 12}},
    ],
}

_engine = make_parser(LAYOUT)

# The caption also opens a line of the list of tables, ended by dot leaders.
_T708 = re.compile(r"^Tableau 7\.08 : Caract.ristiques des emplois principaux "
                   r"par branche institutionnelle(?![^\n]*\.{4})", re.M)
_UNITS = ["Administration",
          "Entreprise publique ou parapublique/organisme international",
          "Entreprise privée", "Entreprise associative",
          "Ménage comme employeur de personnel domestique", "Ensemble"]
_COUNT = r"\d{1,3}(?: \d{3})+|\d{1,3}"
_DEC = r"\d{1,3},\d"


def _table_7_08(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = next(t for t in (p.extract_text() or "" for p in pdf.pages)
                    if _T708.search(t))
    lines = [ln.strip() for ln in text[_T708.search(text).end():].splitlines()]
    rows, label, dec_line = [], [], None
    for s in lines:
        # "0,5 20,6" -- a wrapped row's percentage and % femmes, alone.
        if re.fullmatch(rf"{_DEC} {_DEC}", s):
            dec_line = s
            continue
        # label? count  [pct  %femmes]  years
        m = re.fullmatch(rf"(.*?)\s*({_COUNT})\s+((?:{_DEC}|100,0)(?: {_DEC})*)", s)
        if m and re.search(r"[A-Za-zé]", s):
            label.append(m.group(1))
            decs = m.group(3).split()
            if len(decs) == 3:            # count  pct  %femmes  years
                pct = decs[0]
            elif len(decs) == 1 and dec_line:   # count  years (wrapped row)
                pct = dec_line.split()[0]
            else:
                raise ValueError(f"ECOSIT4 T7.08: cannot read {s!r}")
            rows.append((" ".join(w for w in label if w).strip(),
                         float(m.group(2).replace(" ", "")),
                         float(pct.replace(",", "."))))
            label, dec_line = [], None
            if rows[-1][0] == "Ensemble":
                break
        elif rows or label or s.startswith(("Administration", "Entreprise",
                                            "Ménage")):
            label.append(s)
    got = [r[0] for r in rows]
    if got != _UNITS:
        raise ValueError(f"ECOSIT4 T7.08: read {got}")
    *units, (_, total_n, total_p) = rows
    if sum(r[1] for r in units) != total_n:
        raise ValueError("ECOSIT4 T7.08: counts do not sum to the Ensemble")
    if abs(sum(r[2] for r in units) - total_p) > 0.2:
        raise ValueError("ECOSIT4 T7.08: shares do not sum to the Ensemble")
    out = []
    for lab, n, pct in rows:
        lab = "Total" if lab == "Ensemble" else lab
        for val, meas, unit in ((n, "count", "persons"), (pct, "share", "percent")):
            out.append(C.row(topic="sector", characteristic=lab,
                             classification="Not applicable", value=val,
                             survey=LAYOUT["survey"], period=LAYOUT["period"],
                             reference_period=LAYOUT["reference_period"],
                             frequency=LAYOUT["frequency"], measure=meas,
                             unit=unit, working_age_base="15+",
                             series_code="ECOSIT4 T7.08"))
    return out


def parse(path: str) -> pd.DataFrame:
    return pd.concat([_engine(path), pd.DataFrame(_table_7_08(path))],
                     ignore_index=True)
