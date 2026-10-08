"""Republic of Congo — CNSEE (now INS) household surveys, read from the
Wayback Machine's copies of CNSEE's own files.

WHY THE WAYBACK MACHINE. INS's rebuilt site (ins-congo.cg) lists 135
publications and none is a household employment report: the yearbooks' labour
chapters (2005, 2007, 2010, 2012, 2014, 2018) are civil-service, job-seeker
and "secteur moderne" registers -- administrative, the Kenya trap. The
household reports lived on the old CNSEE site (cnsee.org, now dead), and the
Wayback Machine holds them. The `id_` URL returns the ORIGINAL BYTES of
CNSEE's file -- no banner, no rewriting -- so this is the NSO's publication
unchanged, as for DR Congo's Enquête 1-2-3. Two documents:

* ECOM 2005, "Profil de pauvreté au Congo en 2005" (national household survey,
  collected June-August 2005), chapter 4.1.3:
    Tableau 4.1.2  branche d'activité (4 groups)  -> industry
    Tableau 4.1.3  CSP (6 categories)             -> employment_status
  Each prints Pauvre / Non pauvre / Ensemble for the 10-14, the 15+ and all
  employed. Only the two ENSEMBLE columns are taken -- 15+ (base "15+") and
  all employed (base "10+"); poverty status is not a dimension this schema
  carries, and the 10-14 column (children) sits below the survey's 15+ line.
  Each Ensemble must lie between its own Pauvre and Non pauvre values.

* EESIC 2009 (Enquête sur l'Emploi et le Secteur Informel, November 2009),
  "Tableau récapitulatif des principaux indicateurs du marché du travail",
  the phase-1 (household) indicator sheet -- the full phase-1 report
  (Phase1_09.pdf) survives only as a truncated file in every capture:
    secteur institutionnel (Public et para public / Privé formel / Informel
                            agricole / Informel non agricole) -> formality
                            (the Cameroon precedent)
    catégorie socioprofessionnelle (5)                        -> employment_status
    secteur d'activité (4)                                    -> industry
  by Brazzaville, Pointe-Noire and "Urbain Congo". EESIC 2009 covered the two
  cities ONLY, so "Urbain Congo" is their union -- carried as locality urban,
  never as the country. It must be a weighted average of the two cities with
  ONE weight for every row (fitted: Brazzaville ~0,62 of the employed), which
  is what keeps a mis-paired row from passing.

NOT COLLECTED: ECOM Tableau 4.1.1 (institutional sector) -- every column is a
stratum x poverty-status cell, with no all-employed column to take; EESIC's
rates (informalité, salarisation, ...) belong to `unemployment`; EESIC 2012
"Tableaux Emploi et Chômage en milieu urbain" (rates and job-seekers only);
"Pauvreté et travail" (ECOM, urban zone) -- an author's calculation
("calcul de l'auteur") with fractional counts, not a CNSEE table; RGPH 2007
volumes on cnsee.org (demographic only); the 1984 census (empty download).

Categories are CNSEE's own -> National. Periods 2005 and 2009.

CROSS-CHECK: ECOM 15+ agriculture 35,4, propre compte 71,1; all employed
agriculture 36,1, propre compte 70,1. EESIC urban public 23,9, informel non
agricole 70,2, cadres 22,3, services hors commerce 51,3; Brazzaville public
30,8.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber

from . import _common as C

_P = {"measure": "share", "unit": "percent"}
_DEC = r"\d{1,3},\d"

# --- ECOM 2005 -------------------------------------------------------------
_ECOM = "Enquête Congolaise auprès des Ménages (ECOM) 2005"
_ECOM_TABLES = [
    (r"Tableau 4\.1\.2 : Structure par branche d'activit", "industry",
     ["Agriculture", "Industrie, Mines et BTP", "Commerce", "Services",
      "Ensemble"], "ECOM T4.1.2"),
    (r"Tableau 4\.1\.3 : Structure par CSP", "employment_status",
     ["Cadres", "Employés", "Manœuvres", "Autres travailleurs dépendants",
      "Patrons, employeurs", "Travailleurs pour propre compte", "Ensemble"],
     "ECOM T4.1.3"),
]


def _ecom(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(pdf.pages[i].extract_text() or "" for i in range(70, 90))
    out = []
    for caption, topic, labels, code in _ECOM_TABLES:
        m = re.search(caption, text)
        if not m:
            raise ValueError(f"{code}: caption not found")
        rows, pending = [], ""
        for ln in text[m.end():].splitlines()[1:]:
            ln = ln.strip()
            if ln.startswith("Source"):
                break
            nm = re.fullmatch(rf"(.*?)\s*((?:{_DEC}\s+){{8}}{_DEC})", ln)
            if not nm:
                # a wrapped label head ("Autres travailleurs") or header text
                pending = ln if not re.search(r"\d|Pauvre|Actifs|Ensemble$", ln) else ""
                continue
            label = f"{pending} {nm.group(1)}".strip() if pending else nm.group(1)
            pending = ""
            vals = [float(v.replace(",", ".")) for v in nm.group(2).split()]
            rows.append((label, vals))
        if [r[0] for r in rows] != labels:
            raise ValueError(f"{code}: read {[r[0] for r in rows]}")
        for label, v in rows:
            for poor, rich, ens in ((3, 4, 5), (6, 7, 8)):
                if not min(v[poor], v[rich]) - 0.05 <= v[ens] <= max(v[poor], v[rich]) + 0.05:
                    raise ValueError(f"{code}: {label} Ensemble {v[ens]} outside "
                                     f"{v[poor]} / {v[rich]}")
        for j, base in ((5, "15+"), (8, "10+")):
            s = sum(v[j] for lab, v in rows if lab != "Ensemble")
            if abs(s - 100) > 0.2:
                raise ValueError(f"{code}: column {j} sums to {s}")
            for label, v in rows:
                out.append(C.row(topic=topic,
                                 characteristic="Total" if label == "Ensemble" else label,
                                 classification="National", value=v[j],
                                 survey=_ECOM, period="2005",
                                 reference_period="ECOM, June-August 2005",
                                 frequency="ad_hoc", working_age_base=base,
                                 series_code=code, **_P))
    return out


# --- EESIC 2009 indicator sheet -------------------------------------------
_EESIC = ("Enquête sur l'Emploi et le Secteur Informel au Congo (EESIC) 2009, "
          "phase 1 -- Brazzaville and Pointe-Noire only")
_EESIC_BLOCKS = [
    (r"R.partition des emplois par secteur institutionnel", "formality",
     "Not applicable",
     ["Public et para public", "Secteur privé formel", "Secteur informel agricole",
      "Secteur informel non agricole"]),
    (r"R.partition des emplois par cat.gorie socioprofessionnelle",
     "employment_status", "National",
     ["Cadres", "Employés, ouvriers", "Manœuvres", "Travailleurs indépendants",
      "Aides familiaux"]),
    (r"R.partition des emplois par secteur d.activit", "industry", "National",
     ["Secteur primaire", "Industrie", "Commerce", "Services hors commerce"]),
]
_EESIC_COLS = [{"geography": "Brazzaville"}, {"geography": "Pointe-Noire"},
               {"locality": "urban", "locality_label": "Urbain Congo"}]
_FURNITURE = {"Brazzaville", "Pointe Noire", "Urbain Congo"}


def _eesic(path: str) -> list[dict]:
    # PyMuPDF gives one cell per line: label, then its three values.
    with fitz.open(path) as doc:
        if not re.search(r"SECTEUR INFORMEL AU CONGO\s*\(Novembre 2009\)",
                         doc[0].get_text()):
            raise ValueError("EESIC: not the November 2009 indicator sheet")
        lines = [ln.strip() for p in doc for ln in p.get_text().splitlines()
                 if ln.strip() and ln.strip() not in _FURNITURE]
    blocks = []
    for heading, topic, scheme, labels in _EESIC_BLOCKS:
        i = next((k for k, ln in enumerate(lines) if re.search(heading, ln)), None)
        if i is None:
            raise ValueError(f"EESIC: block {heading!r} not found")
        vals = {}
        k = i + 1
        for lab in labels:
            if lines[k] != lab:
                raise ValueError(f"EESIC: expected {lab!r}, read {lines[k]!r}")
            nums = lines[k + 1:k + 4]
            if not all(re.fullmatch(_DEC, n) for n in nums):
                raise ValueError(f"EESIC: {lab!r} values {nums}")
            vals[lab] = [float(n.replace(",", ".")) for n in nums]
            k += 4
        for j in range(3):
            s = sum(v[j] for v in vals.values())
            if abs(s - 100) > 0.2:
                raise ValueError(f"EESIC {topic}: column {j} sums to {s}")
        blocks.append((topic, scheme, vals))

    # "Urbain Congo" = the two cities pooled: one weight must reproduce
    # every row (least squares over rows where the cities differ).
    pairs = [(v[0], v[1], v[2]) for _, _, vals in blocks for v in vals.values()]
    num = sum((u - p) * (b - p) for b, p, u in pairs)
    den = sum((b - p) ** 2 for b, p, u in pairs)
    w = num / den
    for b, p, u in pairs:
        if abs(w * b + (1 - w) * p - u) > 0.25:
            raise ValueError(f"EESIC: Urbain Congo {u} is not the pooled "
                             f"Brazzaville {b} / Pointe-Noire {p} (w={w:.3f})")

    out = []
    for topic, scheme, vals in blocks:
        for lab, v in vals.items():
            for ctx, val in zip(_EESIC_COLS, v):
                out.append(C.row(topic=topic, characteristic=lab,
                                 classification=scheme, value=val,
                                 survey=_EESIC, period="2009",
                                 reference_period="EESIC, novembre 2009",
                                 frequency="ad_hoc", working_age_base="15+",
                                 series_code="EESIC 2009 indicateurs",
                                 **_P, **ctx))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path, *(extras or [])]:
        with fitz.open(p) as doc:
            head = doc[0].get_text()
        if "Profil de pauvreté au Congo en 2005" in head:
            rows += _ecom(p)
        elif "SECTEUR INFORMEL AU CONGO" in head:
            rows += _eesic(p)
        else:
            raise ValueError(f"Congo: unrecognised document {p!r}")
    return pd.DataFrame(rows)
