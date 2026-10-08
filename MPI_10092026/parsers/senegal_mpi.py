"""Senegal — ANSD / OPCV, "La pauvreté multidimensionnelle au Sénégal. Rapport
national de présentation de l'Indice de Pauvreté Multidimensionnelle (IPM)"
(version provisoire, 25 septembre 2018), from the ESPS-II 2011 survey.

A NATIONAL MPI, NSO-HOSTED AND NSO-LED. The report sits on ansd.sn
(/sites/default/files/2022-11/Rapport_IPM 2011_VSF.pdf). It is the
Observatoire de la Pauvreté et des Conditions de Vie's national presentation
report; the OPCV's bureau is chaired by ANSD's Director-General (named as
"Coordonnateur général"), the measure was set by a multisectoral national
committee with regional consultations, and OPHI is credited only for technical
accompaniment. It was recorded in PENDING.md as "adopted national MPI or ANSD
analytical study?" -- it is the former in form (a "rapport national" of a
national IPM), with one caveat carried on every row's survey label: the cover
says VERSION PROVISOIRE.

METHODOLOGY (Chapter 3): Alkire-Foster; 5 dimensions -- Éducation (4
indicators), Santé (5), Conditions de vie (9), Emploi (5), Gouvernance et
institutions (2) -- 25 indicators; poverty cutoff k = 32% ("la valeur du seuil
de pauvreté globale a été fixée à 32%"). The identification unit is the
HOUSEHOLD ("le choix de l'unité d'identification (ménage)"), but every
published figure is a share of PERSONS ("plus de six personnes sur dix"), so
`unit_of_analysis` is person, as for the other countries that identify at the
household and report over people.

TAKEN
* Annexe 14 -- H, A and M0, each with its 95% confidence interval, for the 14
  regions and Sénégal. Preferred over Annexe 12, which prints the SAME figures
  rounded (19,7% vs 19,73%) and would collide on the merge key.
* Tableaux 4.1 / 4.2 -- H and A with their intervals by stratum (Dakar urbain,
  Autres villes, Rural). Their "Sénégal" column repeats Annexe 14 exactly and
  is not emitted twice. M0 by stratum is printed (2 decimals) in the Ensemble
  row of Tableaux 4.3-4.7; it is taken once, from Tableau 4.3.
* Tableaux 4.3 (sexe du CM), 4.4 (âge du CM), 4.6 (instruction du CM) -- H, A
  and M0 nationally, and H and M0 for each stratum, by the household head's
  characteristic.

NOT TAKEN
* Tableau 4.5 (statut matrimonial) -- no topic for marital status, and the
  table is defective: its "Ensemble" row (61,31% / 36,29% / 0,22) contradicts
  every other table's national figures (60,92% / 42,50% / 0,26), and its
  "Concubinage" stratum cells print 0 and 1.
* Tableau 4.7 (occupation du CM) -- no topic for activity status.
* Annexe 14's "Part dans les ménages / dans la population" -- population
  shares, not MPI metrics. Regional maps and charts (Figure 4.1/4.2).
* Dimension contributions -- printed only in charts.

PUBLISHED ZEROS KEPT: Tableau 4.6 prints "0 0" for H and M0 of Dakar urbain
heads with higher education (no poor person in that cell of the sample); they
are collected as the published 0, not treated as missing.

CROSS-CHECK (read off the opened report): national H 60,92% (58,93-62,91),
A 42,50%, M0 0,26; Dakar urbain H 19,27%, Rural 83,86%; Kolda H 86,37%,
Dakar region H 19,73% / M0 0,08; head without schooling H 72,16%, higher
education 7,15%.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_M = dict(mpi_type="national", measure_name="IPM Sénégal (OPCV/ANSD)",
          survey="ESPS-II 2011 (rapport national IPM, version provisoire 2018)",
          k_cutoff=32, n_dimensions=5, n_indicators=25,
          unit_of_analysis="person", period="2011",
          reference_period="ESPS-II 2011", frequency="ad_hoc")
_NUM = r"(\d{1,3},\d{1,2})%?"
_REGIONS = ["Dakar", "Ziguinchor", "Diourbel", "Saint-Louis", "Tambacounda",
            "Kaolack", "Thiès", "Louga", "Fatick", "Kolda", "Matam", "Kaffrine",
            "Kédougou", "Sédhiou", "Sénégal"]
_STRATA = [("Dakar urbain", "urban"), ("Autres villes", "urban"),
           ("Rural", "rural")]


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def _page(pages: list[str], caption: str) -> str:
    """The page carrying `caption` as a table title, not a list-of-tables line."""
    for t in pages:
        for m in re.finditer(caption, t):
            line = t[m.start():t.find("\n", m.start())]
            if not re.search(r"\.{5}", line):
                return t[m.start():]
    raise ValueError(f"ANSD IPM: {caption!r} not found")


def _row(**kw) -> dict:
    return C.row(**{**_M, **kw})


def _annexe14(pages) -> list[dict]:
    t = _page(pages, r"Annexe 14 : Intervalles de confiance")
    out = []
    for reg in _REGIONS:
        # The two population shares print "100%" on the national row.
        share = r"(\d{1,3}(?:,\d{1,2})?)%"
        m = re.search(rf"^{re.escape(reg)} {share} {share} "
                      + r" ".join([_NUM] * 9) + r"\s*$", t, re.M)
        if not m:
            raise ValueError(f"ANSD IPM Annexe 14: no row for {reg}")
        v = [_f(x) for x in m.groups()][2:]          # drop the two shares
        geo = {} if reg == "Sénégal" else {"geography": reg}
        for i, (met, lo, hi) in enumerate(
                (("incidence_H", "incidence_H_ci_low", "incidence_H_ci_high"),
                 ("intensity_A", "intensity_A_ci_low", "intensity_A_ci_high"),
                 ("index_M0", "index_M0_ci_low", "index_M0_ci_high"))):
            for metric, val in zip((met, lo, hi), v[3 * i:3 * i + 3]):
                out.append(_row(metric=metric, value=val,
                                series_code="ANSD IPM Annexe 14", **geo))
    # The national row must match Tableaux 4.1/4.2 and every head table.
    nat = {r["metric"]: r["value"] for r in out if r["geography"] == "Total country"}
    if (nat["incidence_H"], nat["intensity_A"], nat["index_M0"]) != (60.92, 42.5, 0.26):
        raise ValueError(f"ANSD IPM: national row reads {nat}")
    return out


def _strata(pages) -> list[dict]:
    out = []
    for cap, metric, lo, hi in (
            (r"Tableau 4\.1 : Incidence", "incidence_H", "incidence_H_ci_low",
             "incidence_H_ci_high"),
            (r"Tableau 4\.2 : Intensit", "intensity_A", "intensity_A_ci_low",
             "intensity_A_ci_high")):
        t = _page(pages, cap)
        lines = [ln for ln in t.splitlines()[:8] if re.search(r"\d+,\d+%", ln)]
        if len(lines) != 3:
            raise ValueError(f"ANSD IPM {cap}: {len(lines)} value lines")
        for line, met in zip(lines, (metric, lo, hi)):
            vals = [_f(x) for x in re.findall(_NUM, line)]
            if len(vals) != 4:
                raise ValueError(f"ANSD IPM {cap}: {line!r}")
            for (label, loc), v in zip(_STRATA, vals[:3]):   # 4th = Sénégal
                out.append(_row(metric=met, value=v, topic="locality",
                                characteristic=label, locality=loc,
                                locality_label=label,
                                series_code=f"ANSD IPM {cap[8:20].strip()}"))
    return out


_HEAD_TABLES = [
    (r"Tableau 4\.3 : Pauvreté multidimensionnelle selon le sexe",
     "sex_of_head", ["Masculin", "Féminin"], "ANSD IPM Tableau 4.3"),
    (r"Tableau 4\.4 : Pauvreté multidimensionnelle selon le groupe",
     "age", ["Moins de 35 ans", "35 - 60 ans", "Plus de 60 ans"],
     "ANSD IPM Tableau 4.4"),
    (r"Tableau 4\.6 : Pauvreté multidimensionnelle selon le niveau",
     "education", ["Sans instruction", "Primaire", "Moyen", "Secondaire",
                   "Supérieur"], "ANSD IPM Tableau 4.6"),
]
# Sénégal H A M0 | Dakar urbain H M0 | Autres villes H M0 | Rural H M0
_HEAD_COLS = ([("incidence_H", None), ("intensity_A", None), ("index_M0", None)]
              + [(m, s) for s in _STRATA for m in ("incidence_H", "index_M0")])
_CELL = r"(\d{1,3},\d{1,2}%|\d,\d{2}|0|1)"


def _head(pages) -> list[dict]:
    out = []
    for cap, topic, labels, code in _HEAD_TABLES:
        t = _page(pages, cap)
        for lab in labels + ["Ensemble"]:
            m = re.search(rf"^{re.escape(lab)} " + " ".join([_CELL] * 9) + r"\s*$",
                          t, re.M)
            if not m:
                raise ValueError(f"{code}: no row {lab!r}")
            vals = [_f(x.rstrip("%")) for x in m.groups()]
            if lab == "Ensemble":
                if vals[:3] != [60.92, 42.5, 0.26]:
                    raise ValueError(f"{code}: Ensemble reads {vals[:3]}")
                if topic == "sex_of_head":     # M0 by stratum, taken once
                    for i, (label, loc) in enumerate(_STRATA):
                        out.append(_row(metric="index_M0", value=vals[4 + 2 * i],
                                        topic="locality", characteristic=label,
                                        locality=loc, locality_label=label,
                                        series_code=code))
                continue
            for (metric, stratum), v in zip(_HEAD_COLS, vals):
                kw = dict(metric=metric, value=v, topic=topic,
                          characteristic=lab, series_code=code)
                if stratum:
                    kw.update(locality=stratum[1], locality_label=stratum[0])
                out.append(_row(**kw))
    return out


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    rows = _annexe14(pages) + _strata(pages) + _head(pages)
    return pd.DataFrame(rows)


# The methodology as a LAYOUT, so `parsers.LAYOUTS` and tests/check_registry
# can verify it like every table-driven country's. This parser is bespoke, so
# there are no table specs; the dict is the same one every row is built from.
LAYOUT = {**_M, "tables": []}
