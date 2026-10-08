"""Senegal — ANSD: the quarterly ENES summary box, and the ERI-ESI 2017 tables.

TWO SOURCES, EACH FOR WHAT IT CAN BE TRUSTED WITH.

1. ENES (Enquête Nationale sur l'Emploi au Sénégal), QUARTERLY. Each release is
   a 6-10 page "note d'informations" with no `Tableau` at all -- the reason
   this country sat in `sources_blocked/` (README §4). What IS collectable is
   the front-page box "PRINCIPAUX INDICATEURS DU MARCHE DU TRAVAIL", printed on
   every release from 2025 Q1 on, whose figures are LABELLED and PROVE
   THEMSELVES:

       Population en âge de travailler (15ans et plus)   12 120 496
       Main-d'oeuvre (population active)                   6 779 717 (55,9%)
       Hors de la main-d'oeuvre                            5 340 779
       NEET (15-24 ans)                                    35,3%

   labour force + outside labour force must equal the working-age population,
   and the printed 55,9% must be labour force / working-age population to one
   decimal -- or the issue is refused. That is the same standard as Mali's
   summary box (`mali_pdf_bulletin`): only arithmetically self-verifying figures
   are taken from a note.

   NOT TAKEN FROM THE NOTE: the box's "Occupé / Chômage / 45,3% / 19,1%" pair,
   whose labels and values reach the text layer out of order -- and whose
   unlabelled "Chômage" is the ÉLARGI rate, not BIT (README §1: 5,4% vs 23,3%
   in T4 2025); the prose rates (phrasing varies by issue, and the BIT-strict
   rate is printed in only one of fifteen issues); and every Graphique.
   Releases before 2025 Q1 carry no box and are not read.

2. ERI-ESI 2017 final report -- the AFRISTAT template shared with Togo, read by
   `togo_unemployment.read_eriesi`: the recap "Principaux indicateurs de
   l'emploi" (BIT, SU2, SU4 by Dakar urbain / autres urbains / urbain / rural),
   Tableau 5.4 (SU1-SU4 and the labour force by sex, age, education, milieu and
   the 14 regions) and Tableau 5.10 (employment-to-population ratio, NEET,
   employed). The labels "Dakar" (5.4's milieu block) and "Urbain" (the recap)
   are mapped to the strata names 5.10 prints, so overlapping cells meet and
   are checked equal.

PUBLISHED DEFECTS: Tableau 5.4's national extended labour force prints
"44 915 351" for 4 915 352 (its two sexes); that column is not collected
(no topic holds it), and the labour force is checked against its sex split
instead. The recap drops the leading zero of small decimals (",9").

Base 15+ throughout. ENES periods are the quarter the note covers; ERI-ESI is
2017.

CROSS-CHECK: ENES 2026 Q2 -- working-age 12 120 496, labour force 6 779 717
(55,9%), NEET 15-24 35,3%. ERI-ESI 2017 -- chômage BIT 2,9 (Dakar urbain 4,7;
rural 1,6); SU2 12,6; SU3 20,5; SU4 28,4; main d'œuvre 4 024 678; ratio
emploi/population 45,0; actifs occupés 3 906 070.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C
from .togo_unemployment import Cells, read_eriesi, su_labels

_URB = {"locality": "urban"}
_DAKAR = {**_URB, "locality_label": "Dakar urbain"}
_AUTRES = {**_URB, "locality_label": "Autres urbains"}
_ENS_URB = {**_URB, "locality_label": "Ensemble urbain"}
_RURAL = {"locality": "rural", "locality_label": "Rural"}

ERIESI = {
    "where": "Senegal ERI-ESI 2017",
    "max_page": 100,
    "base": {"survey": "ERI-ESI -- Enquête Régionale Intégrée sur l'Emploi et "
                       "le Secteur Informel", "period": "2017",
             "reference_period": "ERI-ESI 2017", "frequency": "ad_hoc",
             "working_age_base": "15+"},
    "su": su_labels(),
    "country_label": "Sénégal",
    "recap_columns": [_DAKAR, _AUTRES, _ENS_URB, _RURAL, {}],
    "milieu": {"Dakar": _DAKAR, "Dakar urbain": _DAKAR,
               "Autres urbains": _AUTRES, "Ensemble urbain": _ENS_URB,
               "Rural": _RURAL},
    "su_caption": r"^Tableau 5\.4\s*:\s*Principales caractéristiques de la "
                  r"sous-utilisation",
    "su_code": "ERI-ESI T5.4",
    "lf_label": "Main d'œuvre (actifs occupés + chômeurs BIT)",
    "su_expect": {"sex": 2, "age": 7, "edu": 4, "loc": 4, "geo": 14,
                  "national": 1},
    "opp_caption": r"^Tableau 5\.10\s*:\s*Aperçu de quelques indicateurs des "
                   r"possibilités d.emploi",
    "opp_code": "ERI-ESI T5.10",
    "opp_min_rows": 27,
}

_ORD = {"premier": 1, "deuxième": 2, "troisième": 3, "quatrième": 4}
_ENES_SURVEY = "ENES -- Enquête Nationale sur l'Emploi au Sénégal"


def _enes_box(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages[:4]]
    flat = re.sub(r"\s+", " ", "\n".join(pages))
    q = re.search(r"\(ENES\)\s*(Premier|Deuxième|Troisième|Quatrième)\s+"
                  r"trimestre\s+(20\d\d)", flat, re.I)
    if not q:
        raise ValueError(f"ENES {path}: cannot date the note from its title")
    period = f"{q.group(2)}-Q{_ORD[q.group(1).lower()]}"
    where = f"ENES {period}"
    grab = {
        "wap": r"Population en âge de travailler \(15\s*ans et plus\)\s*"
               r"(\d{1,3}(?: \d{3})+)",
        "lf": r"Main-d.(?:oe|œ)uvre \(population active\)\s*(\d{1,3}(?: \d{3})+)"
              r"\s*\((\d+,\d)\s*%\)",
        "olf": r"Hors de la main-d.(?:oe|œ)uvre\s*(\d{1,3}(?: \d{3})+)",
        "neet": r"NEET \(15-24 ans\)\s*(\d+,\d)\s*%",
    }
    got = {k: re.search(p, flat) for k, p in grab.items()}
    missing = [k for k, m in got.items() if not m]
    if missing:
        raise ValueError(f"{where}: summary box lacks {missing} -- the note's "
                         f"front page changed; re-check before reading it")
    wap = float(got["wap"].group(1).replace(" ", ""))
    lf = float(got["lf"].group(1).replace(" ", ""))
    lfpr = float(got["lf"].group(2).replace(",", "."))
    olf = float(got["olf"].group(1).replace(" ", ""))
    neet = float(got["neet"].group(1).replace(",", "."))
    # The box proves itself, or it is refused.
    if abs(lf + olf - wap) > 1:
        raise ValueError(f"{where}: labour force + outside != working-age "
                         f"({lf + olf:,.0f} vs {wap:,.0f})")
    if abs(round(lf / wap * 100, 1) - lfpr) > 0.05:
        raise ValueError(f"{where}: printed participation {lfpr} is not "
                         f"labour force / working-age ({lf / wap * 100:.2f})")
    base = dict(survey=_ENES_SURVEY, period=period,
                reference_period=f"ENES {q.group(1).lower()} trimestre "
                                 f"{q.group(2)}",
                frequency="quarterly", working_age_base="15+",
                series_code="ENES principaux indicateurs")
    rows = [
        C.row(topic="working_age_population", value=wap,
              series_label="Population en âge de travailler (15 ans et plus)",
              **base),
        C.row(topic="labour_force", value=lf,
              series_label="Main-d'oeuvre (population active)", **base),
        C.row(topic="outside_labour_force", value=olf,
              series_label="Hors de la main-d'oeuvre", **base),
        C.row(topic="labour_force_participation_rate", value=lfpr,
              definition="strict",
              series_label="Main-d'oeuvre (population active), % de la "
                           "population en âge de travailler", **base),
        C.row(topic="neet_rate", value=neet, age_group="15-24",
              series_label="NEET (15-24 ans)", **base),
    ]
    return pd.DataFrame(rows)


def _kind(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        head = " ".join((p.extract_text() or "") for p in pdf.pages[:2])
    if re.search(r"Enquête nationale sur l.Emploi au Sénégal", head, re.I):
        return "enes"
    if re.search(r"Enquête r.gionale int.gr.e sur l.emploi", head, re.I):
        return "eriesi"
    raise ValueError(f"Senegal: {path} is neither an ENES note nor the ERI-ESI "
                     f"report")


def parse(path: str, extras=None) -> pd.DataFrame:
    frames = []
    for p in [path, *(extras or [])]:
        frames.append(_enes_box(p) if _kind(p) == "enes"
                      else read_eriesi(p, ERIESI))
    df = pd.concat(frames, ignore_index=True)
    key = ["topic", "definition", "series_label", "sex", "age_group",
           "education", "geography", "locality", "locality_label",
           "working_age_base", "period", "measure"]
    dup = df[df.duplicated(key, keep=False)]
    if len(dup):
        raise ValueError(f"Senegal: {len(dup)} rows share a merge key -- two "
                         f"files cover the same quarter")
    return df
