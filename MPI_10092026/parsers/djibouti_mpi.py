"""Djibouti — INSTAD, RGPH-3 (2024 census), Thématique 16 "Mesure et
cartographie de la pauvreté non monétaire" (November 2025), section 3.3,
"Indice de pauvreté non monétaire multidimensionnel de la population".

A NATIONAL MEASURE, AND AN UNUSUAL ONE -- read this before using it.

* Methodology (Tableau n°1 and étapes 1-4, pp. 13-14): Alkire-Foster, THREE
  dimensions -- Éducation (niveau d'instruction: "aucun niveau d'instruction"),
  Santé (espérance de vie à la naissance below a mean of 40,07 ans), Conditions
  de vie (the household's standard of living is "pauvre" or "très pauvre") --
  one indicator each, equal weights of 1/3, k = 1/3 ("fixé à 33%"). The unit
  is the PERSON: "la population vivant dans des ménages identifiés comme
  pauvres". n_indicators is recorded as 3, from Tableau n°1, the table that
  defines the index. A definitions paragraph on p.15 says instead that a
  household is poor if deprived in "au moins 33,33% des 9 dimensions"; the
  report never lists nine, and the one table that enumerates them has three.
  That contradiction is the report's, and is recorded here rather than settled.
* WITH ONE INDICATOR PER DIMENSION AND k = 1/3, A PERSON IS POOR IF DEPRIVED IN
  ANY ONE OF THE THREE. That is why every age group up to 15-19 prints 100% and
  "Sans niveau" prints 100%: the education indicator is the person's own
  attainment, so every young child is deprived in it. The figures are as INSTAD
  published them; they are not comparable with any other country's MPI, nor
  with the global MPI.
* ONLY THE HEADCOUNT IS PUBLISHED. Each table splits the population into
  "Aucune pauvreté (%)" and "Pauvreté maximale (%)", summing to 100. The text
  equates the second with being multidimensionally poor ("86,2% de la
  population résidente vit dans une situation de pauvreté multidimensionnelle")
  -- so it is collected as `incidence_H`, and the complement is not. Intensity
  A and the index M0 are defined in the methodology but never printed, and
  nothing is computed in their place.

TABLES READ: n°21 (national; the six régions; milieu urbain/rural; groupes
d'âges) and n°20 (the 29 préfectures / sous-préfectures / arrondissements).
NOT READ: n°21's sex, nationality, migration and refugee rows and n°22
(education): the person's own sex and education have no topic in this schema
(`sex_of_head` and `education` mean the household head's), and nationality
and migration have no column. The section's other indices (Tableaux 10-19:
incidence/profondeur/sévérité de la pauvreté non monétaire) are a different,
household-standard-of-living measure and are not an MPI.

CROSS-CHECK: Ensemble 86,2; Djibouti-ville 83; Ali-Sabieh 96; Rural 98,7;
Urbain 83,9; 25-29 ans 68,7; Plateau Arrondissement 74,3; Adayllou 99,9.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_BASE = dict(
    mpi_type="national", measure_name="IPM Djibouti (RGPH-3)",
    survey="RGPH-3 2024 census, Thématique 16", k_cutoff=33.33,
    n_dimensions=3, n_indicators=3, unit_of_analysis="person",
    period="2024", reference_period="RGPH-3 (2024)", frequency="ad_hoc",
)
# "label  aucune  maximale  100  effectif" -- aucune may print "-" (none).
_ROW = re.compile(r"^(?P<label>.*?)\s*(?P<a>-|\d{1,3}(?:,\d+)?)\s+"
                  r"(?P<m>\d{1,3}(?:,\d+)?)\s+100\s+(?P<n>\d{1,3}(?:\s\d{3})*|\d+)$")
_SECTIONS = {"Région": "region", "Milieu de résidence": "locality",
             "Sexe": None, "Groupe d'âges": "age", "Nationalité": None,
             "Statut migratoire": None, "Statut de réfugié": None}
_REGIONS = ["Djibouti-ville", "Ali-Sabieh", "Dikhil", "Tadjourah", "Obock", "Arta"]


def _num(s: str) -> float | None:
    return None if s == "-" else float(s.replace(",", "."))


def _rows(lines: list[str]) -> list[tuple[str | None, str, float | None, float]]:
    """(section, label, aucune, maximale) per data row. A label that wraps
    around its numbers ("Cinquième" / "15,9 84,1 100 229 208" /
    "Arrondissement") is rebuilt from the line above and the line below."""
    out, section, pending = [], None, ""
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        i += 1
        if not s:
            continue
        key = s.replace("’", "'")
        if key in _SECTIONS:
            section, pending = key, ""
            continue
        m = _ROW.match(s)
        if not m:
            pending = s if not re.search(r"\d", s) else ""
            continue
        label = m.group("label").strip()
        if not label:
            label = pending
            nxt = lines[i].strip() if i < len(lines) else ""
            if nxt and not re.search(r"\d", nxt) and nxt.replace("’", "'") not in _SECTIONS:
                label = f"{label} {nxt}".strip()
                i += 1
        pending = ""
        a, mx = _num(m.group("a")), _num(m.group("m"))
        if (a or 0.0) + mx - 100 > 0.15 or (a or 0.0) + mx - 100 < -0.15:
            raise ValueError(f"INSTAD IPM: {label!r} {a} + {mx} != 100")
        out.append((section, label, a, mx))
    return out


def _table_lines(pdf, caption: str, until: str) -> list[str]:
    """Lines from the page carrying `caption` (not its list-of-tables entry)
    up to the line matching `until`, across a page break."""
    lines, on = [], False
    for page in pdf.pages:
        text = page.extract_text() or ""
        # The list of tables WRAPS each caption, so its dot leaders land on the
        # next line, not the caption's: skip contents pages as a whole.
        if not on and len(re.findall(r"\.{6,}", text)) >= 3:
            continue
        for ln in text.splitlines():
            if not on and caption in ln:
                on = True
                continue
            if on:
                if re.match(until, ln.strip()):
                    return lines
                lines.append(ln)
    raise ValueError(f"INSTAD IPM: {caption!r} not found")


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        t21 = _rows(_table_lines(pdf, "Tableau n°21.", r"^Source\s*:"))
        t20 = _rows(_table_lines(pdf, "Tableau n°20.", r"^Source\s*:"))

    rows = []
    regions = [r for r in t21 if r[0] == "Région"]
    if [r[1] for r in regions] != _REGIONS:
        raise ValueError(f"INSTAD IPM Tableau 21: regions {[r[1] for r in regions]}")
    nat = [r for r in t21 if r[1] == "Ensemble"]
    if len(nat) != 1 or nat[0][3] != 86.2:
        raise ValueError(f"INSTAD IPM Tableau 21: national row {nat}")
    rows.append(C.row(metric="incidence_H", value=nat[0][3], **_BASE,
                      series_code="RGPH-3 T16 Tab.21"))
    for _, label, _, mx in regions:
        rows.append(C.row(metric="incidence_H", value=mx, geography=label,
                          **_BASE, series_code="RGPH-3 T16 Tab.21"))
    for section, label, _, mx in t21:
        if section == "Milieu de résidence":
            loc = C.normalise_locality(label)
            rows.append(C.row(metric="incidence_H", value=mx, topic="locality",
                              characteristic=label, locality=loc,
                              locality_label=label, **_BASE,
                              series_code="RGPH-3 T16 Tab.21"))
        elif section == "Groupe d'âges":
            rows.append(C.row(metric="incidence_H", value=mx, topic="age",
                              characteristic=label, age_group=label, **_BASE,
                              series_code="RGPH-3 T16 Tab.21"))
    ages = [r for r in t21 if r[0] == "Groupe d'âges"]
    if len(ages) != 20:
        raise ValueError(f"INSTAD IPM Tableau 21: {len(ages)} age groups, want 20")

    units = [r for r in t20 if r[1] != "Ensemble"]
    if len(units) != 29:
        raise ValueError(f"INSTAD IPM Tableau 20: {len(units)} units, want 29: "
                         f"{[u[1] for u in units]}")
    if [r[3] for r in t20 if r[1] == "Ensemble"] != [86.2]:
        raise ValueError("INSTAD IPM Tableau 20: Ensemble is not Tableau 21's 86,2")
    for _, label, _, mx in units:
        rows.append(C.row(metric="incidence_H", value=mx, geography=label,
                          **_BASE, series_code="RGPH-3 T16 Tab.20"))
    return pd.DataFrame(rows)


# The methodology as a LAYOUT, so `parsers.LAYOUTS` and tests/check_registry
# can verify it like every table-driven country's. This parser is bespoke, so
# there are no table specs; the dict is the same one every row is built from.
LAYOUT = {**_BASE, "tables": []}
