"""Niger — INS Niger, ERI-ESI 2017 (Enquête Régionale Intégrée sur l'Emploi et
le Secteur Informel), rapport final, chapter 5 "Emploi".

THE EMPLOYMENT PART, NOT THE INFORMAL-SECTOR MODULE. Niger was swept as empty
because every branch and status table in this report sits in the informal-
sector (UPI) chapters -- chapter 9's "Répartition des emplois des actifs
occupés" tables (9.7, 9.8) included, which despite their titles distribute
the jobs OF INFORMAL PRODUCTION UNITS ("43,6% des travailleurs du secteur
informel exercent dans le secondaire"). Those remain excluded: the Kenya trap.
Chapter 5 is the household employment survey, and two of its tables describe
all the employed:

* Tableau 5.30 "Principaux acteurs de l'offre d'emploi" -- the employed by
  institutional sector, by sex, stratum (Niamey urbain / autres urbains /
  ensemble urbain / rural), the eight regions, and Niger -> `sector`;
* Tableau 5.12 "Bilan de l'emploi" -- its overall block: the employed count by
  institutional sector (public / privé / ménages) -> `sector`, and the formal /
  informal split of all employment (8,1 / 91,9) -> `formality`.

THE UNIVERSE IS THE REPORT'S OWN EMPLOYED POPULATION, and that was checked
rather than assumed: 5.12's total, 2 182 207, is 99,3% of the "Actif occupé /
Niger" effectif printed with the age tables (2 197 369), the remainder being
employed with no sector recorded; and 5.30's national shares reproduce 5.12's
counts (public 8,4% vs 182 709 / 2 182 207 = 8,37%; ménage 1,4% vs 1,34%).

5.30 IS HIERARCHICAL: "Secteur privé" = Initiative privée + Autres acteurs, and
"Secteur public" = APU + EPP (checked in every column). Only the leaves and the
Total are collected, so the topic's categories partition the employed; the
two subtotals are verified sums, not new figures.

NOT COLLECTED from 5.12: the non-agricultural and agricultural blocks
(formal/informal WITHIN a sector crossed with agriculture -- a row percentage
over two dimensions no single category column holds) and the Ménages row of
the agricultural block, printed "0,0 0,0 0,0".

Categories are INS Niger's own -> National (sector), Not applicable
(formality). Base 15+. Period 2017.

CROSS-CHECK (Niger): initiative privée 68,5; APU 7,2; EPP 1,2; ménage employeur
1,4; secteur privé 1 970 235 employed; informal employment 91,9%.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = ("Enquête Régionale Intégrée sur l'Emploi et le Secteur Informel "
           "(ERI-ESI) 2017")
_BASE = dict(survey=_SURVEY, period="2017", reference_period="ERI-ESI 2017",
             frequency="ad_hoc", working_age_base="15+")

# Tableau 5.30's fifteen columns, in printed order.
_COLS_530 = (
    [{"sex": "male"}, {"sex": "female"},
     {"locality": "urban", "locality_label": "Niamey urbain"},
     {"locality": "urban", "locality_label": "Autres urbains"},
     {"locality": "urban", "locality_label": "Ensemble urbain"},
     {"locality": "rural", "locality_label": "Rural"}]
    + [{"geography": g} for g in ("Agadez", "Diffa", "Dosso", "Maradi",
                                  "Tahoua", "Tillabéri", "Zinder", "Niamey")]
    + [{}])
_ROWS_530 = ["Initiative privée", "Autres acteurs", "Secteur privé", "APU",
             "EPP", "Secteur public", "Ménage employeur", "Total"]
_LEAVES = ["Initiative privée", "Autres acteurs", "APU", "EPP",
           "Ménage employeur", "Total"]


def _page_lines(path: str, caption: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[55:95]:
            text = page.extract_text() or ""
            m = re.search(caption, text)
            if m:
                return [ln.strip() for ln in text[m.end():].splitlines()]
    raise ValueError(f"ERI-ESI: {caption!r} not found")


def _table_530(path: str) -> list[dict]:
    lines = _page_lines(path, r"Tableau 5\.30\s*:\s*Principaux acteurs de "
                              r"l.offre d.emploi")
    rows, pending = {}, ""
    for ln in lines:
        if ln.startswith("Source"):
            break
        m = re.fullmatch(r"(.*?)\s*((?:\d{1,3}(?:,\d{2})?\s+){14}\d{1,3}(?:,\d{2})?)", ln)
        if not m:
            pending = f"{pending} {ln}".strip()
            continue
        label = (m.group(1) or pending).strip()
        vals = [float(v.replace(",", ".")) for v in m.group(2).split()]
        pending = ""
        rows[label] = vals
    # "Ménage" / numbers / "employeur": the tail line after the numbers.
    if "" in rows or "Ménage" in rows:
        rows["Ménage employeur"] = rows.pop("Ménage", None) or rows.pop("")
    got = [r for r in _ROWS_530 if r in rows]
    if got != _ROWS_530:
        raise ValueError(f"ERI-ESI T5.30: rows {list(rows)}")
    for j in range(15):
        col = {k: v[j] for k, v in rows.items()}
        for total, parts in (("Secteur privé", ("Initiative privée", "Autres acteurs")),
                             ("Secteur public", ("APU", "EPP"))):
            if abs(col[total] - sum(col[p] for p in parts)) > 0.15:
                raise ValueError(f"ERI-ESI T5.30 col {j}: {total} is not the sum "
                                 f"of {parts}")
        s = sum(col[k] for k in _LEAVES if k != "Total")
        if abs(s - 100) > 0.3 or col["Total"] != 100:
            raise ValueError(f"ERI-ESI T5.30 col {j}: leaves sum to {s}")
    out = []
    for lab in _LEAVES:
        for ctx, v in zip(_COLS_530, rows[lab]):
            out.append(C.row(topic="sector", characteristic=lab,
                             classification="National", value=v,
                             measure="share", unit="percent",
                             series_code="ERI-ESI T5.30", **_BASE, **ctx))
    return out


def _table_512(path: str) -> list[dict]:
    lines = _page_lines(path, r"Tableau 5\.12\s*:\s*Bilan de l.emploi")
    # The overall block opens with "Total Secteur public ..." and is the last
    # four rows before the Source line.
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Total Secteur public"))
    block = []
    for ln in lines[start:start + 4]:
        m = re.fullmatch(r"(?:Total\s+)?(Secteur public|Secteur privé|Ménages|Total)\s+"
                         r"(\d{1,3},\d)\s+(\d{1,3},\d)\s+100,0\s+(\d+)", ln)
        if not m:
            raise ValueError(f"ERI-ESI T5.12: cannot read {ln!r}")
        block.append((m.group(1), float(m.group(2).replace(",", ".")),
                      float(m.group(3).replace(",", ".")), float(m.group(4))))
    labels = [b[0] for b in block]
    if labels != ["Secteur public", "Secteur privé", "Ménages", "Total"]:
        raise ValueError(f"ERI-ESI T5.12: rows {labels}")
    *parts, total = block
    if sum(p[3] for p in parts) != total[3]:
        raise ValueError("ERI-ESI T5.12: sector counts do not sum to the Total")
    out = []
    for lab, _, _, n in block:
        out.append(C.row(topic="sector", characteristic=lab,
                         classification="National", value=n, measure="count",
                         unit="persons", series_code="ERI-ESI T5.12", **_BASE))
    for lab, v in (("Emplois formels", total[1]), ("Emplois informels", total[2])):
        out.append(C.row(topic="formality", characteristic=lab,
                         classification="Not applicable", value=v,
                         measure="share", unit="percent",
                         series_code="ERI-ESI T5.12", **_BASE))
    return out


def parse(path: str) -> pd.DataFrame:
    return pd.DataFrame(_table_530(path) + _table_512(path))
