"""Burkina Faso -- INSD ENB-ESI 2023 note PLUS the semester bulletins of the
Enquête Nationale Semestrielle sur l'Emploi (ENSE).

The primary (ENB-ESI 2023 synthesis note) is read by `burkina_faso_pdf`.
INSD now runs a semester labour survey and publishes a bulletin per round on
the same page (/fr/statistiques-sociales/statistiques-sur-le-travail-et-
l-emploi):

    Bulletin N°002 -- Edition du 1er Semestre 2025   (ENSE2, Sept 2025)
    Bulletin N°003 -- Edition du 2e Semestre 2025    (ENSE3, Jan 2026)

Each is an `extra_urls` entry. Bulletin N°001 (2nd semester 2024, which
ENSE2 cites at 3.5% unemployment) is not on INSD's page and is not read.

WHAT IS READ: only page 3, "Résumé du marché du travail", which prints the
three headline rates as a panel --

    TAUX DE PARTICIPATION (%)   TAUX D'EMPLOI (%)   TAUX DE CHÔMAGE (%)
    64,4                        59,7                7,2          (S1 2025)

national, both sexes, population aged 16+ (the base the bulletins and the
ENB-ESI 2023 share). The breakdowns by sex, milieu and age exist only as
chart data labels and narrative text, whose order cannot be tied to a
category without guessing, so they are not read.

DATING: the semester is taken from the bulletin's own cover ("Edition du 1er
Semestre 2025" -> 2025-H1, "2e Semestre" -> 2025-H2), frequency semiannual.

CROSS-CHECK: ENSE2 page 6 text repeats "64,4% de main d'œuvre ... 7,2% sont
au chômage"; ENSE3 page 6 "la main- d'œuvre représente 73,7% avec 6,5%".
"""
from __future__ import annotations

import re

import pandas as pd

from . import burkina_faso_unemployment

_SURVEY = "ENSE -- Enquête Nationale Semestrielle sur l'Emploi"
_COVER = re.compile(r"Edition\s+du\s+(1er|2e|2ème|deuxième|premier)\s+Semestre\s+(20\d{2})", re.I)
_TOPICS = [
    ("labour_force_participation_rate", "strict", "Taux de participation (%)"),
    ("employment_to_population_ratio", "not_applicable", "Taux d'emploi (%)"),
    ("unemployment_rate", "strict", "Taux de chômage (%)"),
]


def _bulletin(path: str) -> pd.DataFrame:
    import fitz
    doc = fitz.open(path)
    cover = " ".join(doc[i].get_text() for i in range(min(2, len(doc))))
    m = _COVER.search(cover)
    if not m:
        raise ValueError(f"{path}: no 'Edition du <n> Semestre <year>' on the cover")
    half = "H1" if m.group(1).lower() in {"1er", "premier"} else "H2"
    period = f"{m.group(2)}-{half}"
    page = next((p.get_text() for p in doc if "Résumé du marché du travail" in p.get_text()), None)
    if page is None:
        raise ValueError(f"{path}: no 'Résumé du marché du travail' panel")
    if not re.search(r"TAUX DE\s+PARTICIPA", page) or "CHÔMAGE" not in page:
        raise ValueError(f"{path}: the summary panel's headings have changed")
    nums = [float(x.replace(",", ".")) for x in re.findall(r"\b\d{1,2},\d\b", page)]
    if len(nums) != 3:
        raise ValueError(f"{path}: summary panel holds {len(nums)} rates, expected 3")
    lfpr, epr, ur = nums
    # Arithmetic of the three published rates: EPR = LFPR x (1 - UR).
    if abs(lfpr * (1 - ur / 100) - epr) > 0.2:
        raise ValueError(f"{path}: panel rates {nums} are not LFPR/EPR/UR in that order")
    rows = []
    for (topic, definition, label), v in zip(_TOPICS, nums):
        rows.append({
            "survey": _SURVEY, "topic": topic, "definition": definition,
            "series_label": label, "sex": "total", "age_group": "Total",
            "education": "Total", "geography": "Total country",
            "locality": "all", "locality_label": "Total",
            "working_age_base": "16+", "period": period,
            "reference_period": m.group(0), "frequency": "semiannual",
            "measure": "rate", "value": v, "unit": "percent",
            "series_code": "INSD ENSE résumé",
        })
    return pd.DataFrame(rows)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = [burkina_faso_unemployment.parse(path)]
    frames += [_bulletin(p) for p in extras or []]
    return pd.concat(frames, ignore_index=True)
