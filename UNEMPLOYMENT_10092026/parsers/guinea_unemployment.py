"""Guinea — INS Guinée, ENESIG 2018/2019 (Enquête Nationale sur l'Emploi et le
Secteur Informel en Guinée), rapport global, chapters 5-6.

A household LFS, 15+, collected 28 January - 3 March 2019 (dated 2019-Q1). NOT
the quarterly BTSMT bulletin, which is AGUIPE/CNSS registry data with no
unemployment rate (README §4).

Four tables share one shape -- nine columns, (Urbain | Rural | Ensemble) x
(Masculin | Féminin | Total), rows by région administrative and age band:

* Tableau 5.2   taux de participation à la main d'œuvre
* Tableau 6.1   taux d'emploi (employment-to-population ratio)
* Tableau 6.12  taux de chômage (BIT, strict)
* Tableau 6.15  taux de chômage des jeunes (15-35 ans) -> youth_unemployment_rate

Conakry has no rural stratum and prints "-" there; those cells are empty, never
0. The "Statut de handicap" and "Statut migratoire" rows have no column in this
schema and are not collected.

THE SU TABLE (6.21) IS REFUSED. Its 15-24 row prints SU-4 = 20,8 against SU-2 =
37,4, but SU-4 contains SU-2's population by definition, and its regional SU-2
counts (Boké 86 462 at 64,0%) do not agree with the regions' labour force. A
table that contradicts its own definitions is not collected; SU-1 is the same
figure as 6.12 anyway.

CROSS-CHECK (Ensemble/Total): participation 54,2; taux d'emploi 51,6; chômage
4,8 (urbain 9,5, rural 2,2; Conakry 14,1); jeunes 15-35 7,2 (Conakry 20,2).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_BASE = dict(survey="ENESIG 2018/2019 -- Enquête Nationale sur l'Emploi et le "
                    "Secteur Informel en Guinée", period="2019-Q1",
             reference_period="28 janvier - 3 mars 2019", frequency="ad_hoc",
             working_age_base="15+")
_LOCS = [{"locality": "urban", "locality_label": "Urbain"},
         {"locality": "rural", "locality_label": "Rural"}, {}]
_SEXES = ["male", "female", "total"]
_TABLES = [
    (r"Tableau 5\. ?2\s*:\s*Taux de participation à la main",
     {"topic": "labour_force_participation_rate", "definition": "strict",
      "series_label": "Taux de participation à la main d'œuvre"}, "T5.2"),
    (r"Tableau 6\. ?1\s*:\s*Taux d.emploi \(%\) par région",
     {"topic": "employment_to_population_ratio",
      "series_label": "Taux d'emploi"}, "T6.1"),
    (r"Tableau 6\. ?12\s*:\s*Taux de chômage par région",
     {"topic": "unemployment_rate", "definition": "strict",
      "series_label": "Taux de chômage"}, "T6.12"),
    (r"Tableau 6\. ?15\s*:\s*Taux de chômage des jeunes",
     {"topic": "youth_unemployment_rate", "definition": "strict",
      "series_label": "Taux de chômage des jeunes (15-35 ans)",
      "age_group": "15-35"}, "T6.15"),
]
_CELL = r"(\d+,\d|-)"
_ROW = re.compile(rf"^(.+?)\s+{_CELL}(?:\s+{_CELL}){{8}}$")
_REGIONS = {"Boké", "Conakry", "Faranah", "Kankan", "Kindia", "Labé", "Mamou",
            "N'Zérékoré"}


def _table(pages: list[str], caption: str, spec: dict, code: str) -> list[dict]:
    text = next((t for t in pages if re.search(caption, t)
                 and "...." not in t[re.search(caption, t).start():][:300]), None)
    if text is None:
        raise ValueError(f"ENESIG {code}: caption not found")
    lines = text[re.search(caption, text).end():].splitlines()
    out, section, regions = [], None, set()
    for ln in (s.strip() for s in lines):
        if ln.startswith("Source"):
            break
        if re.match(r"^Région", ln):
            section = "geo"
            continue
        if re.match(r"^(Classe|Groupe) d.âge", ln):
            section = "age"
            continue
        if re.match(r"^Statut", ln):
            section = "skip"
            continue
        m = _ROW.match(ln)
        # Conakry has no rural stratum. 6.1/6.12/6.15 print "-" there; 5.2
        # prints only the six urban + total cells. Map that shape explicitly,
        # and only for Conakry, whose urban and total must then be identical.
        c6 = re.match(rf"^(Conakry)\s+((?:\d+,\d\s+){{5}}\d+,\d)$", ln)
        if c6:
            v = c6.group(2).split()
            if v[:3] != v[3:]:
                raise ValueError(f"ENESIG {code}: Conakry urban != total")
            cells = v[:3] + ["-"] * 3 + v[3:]
            label = "Conakry"
        elif not m:
            continue
        else:
            label = m.group(1).strip()
            cells = ln[len(m.group(1)):].split()
        if label in ("Ensemble", "Total"):
            ctx = {}
        elif section == "geo" and label in _REGIONS:
            ctx = {"geography": label}
            regions.add(label)
        elif section == "age":
            ctx = {"age_group": re.sub(r"\s*ans$", "", label)}
        elif section == "skip":
            continue
        else:
            raise ValueError(f"ENESIG {code}: unexpected row {label!r}")
        for i, tok in enumerate(cells):
            if tok == "-":
                continue
            out.append(C.row(**_BASE, **spec, **_LOCS[i // 3], **ctx,
                             sex=_SEXES[i % 3], value=float(tok.replace(",", ".")),
                             series_code=f"ENESIG {code}"))
        if label in ("Ensemble", "Total"):
            break
    if regions != _REGIONS:
        raise ValueError(f"ENESIG {code}: regions read {sorted(regions)}")
    return out


def parse(path: str, extras=None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages[78:106]]
    rows = []
    for caption, spec, code in _TABLES:
        rows += _table(pages, caption, spec, code)
    return pd.DataFrame(rows)
