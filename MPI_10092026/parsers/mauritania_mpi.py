"""Mauritania — ANSADE, IPM-M (Indice de Pauvreté Multidimensionnelle de la
Mauritanie), EPCV 2019, as published in ANSADE's own Annuaire des Statistiques
Sociodémographiques 2024, chapter 6, Tableaux 6.7-6.9.

WHY THE YEARBOOK AND NOT THE POLICY BRIEF. ANSADE's "Pauvreté
Multidimensionnelle en Mauritanie" brief (November 2022, with UNICEF and OPHI)
has no text layer, and this collector does not OCR. The same measure's figures
are reprinted with a text layer, by ANSADE, in its sociodemographic yearbook:
national / urban / rural (6.7) and the 13 wilayas (6.8), each with H, A and the
IPM and their 95% confidence intervals, and two child age groups (6.9). Every
value collected here is read from that text layer.

METHODOLOGY -- read off ANSADE's own brief (page 6, "Structure de l'IPM-M",
Figure 2), by eye from the rendered page, because the yearbook states only
k = 38% (Tableaux 6.10/6.11): Alkire-Foster; 4 dimensions (Éducation,
Santé, Conditions de vie, Emploi), each weighted 1/4; 19 indicators; poverty
cutoff k = 38% ("être privé dans plus d'une dimension et demie"); the
individual is the unit ("chaque individu"). Only these four parameters come
from the brief; no figure does.

THE IPM IS PRINTED TWO WAYS. Tableau 6.7 prints it as a PERCENTAGE (national
32,0%, urban 17,9%) and Tableau 6.8 as a 0-1 index (Guidimagha 0,577); each is
collected in the unit its table prints (`percent` vs `index`), never rescaled,
as for Guinea and Morocco.

EDITION. The 2024 yearbook is pinned. The 2025 edition drops Tableaux 6.7-6.9
and its wilaya table (6.14) prints A and the IPM as "0.5 0.5", "0.4 0.4" --
rounded to one decimal and identical -- so it cannot be read.

NOT TAKEN: Tableau 6.13 (the wilayas again, rounded -- 6.8 is the same data
to more decimals and would collide on the merge key); 6.10/6.11 (cross-tabs of
monetary x multidimensional poverty: shares of a two-way table, not MPI
metrics); population shares; the key-indicators line "Pauvreté
multidimensionnelle 33,90% 2022", which has no table, no breakdown and no
stated source.

NAMES: the text layer maps the capital I to a lower-case l ("lnchiri", "lPM");
the wilaya is recorded as Inchiri. Other names are kept as printed in 6.8
("Hodh Gharbi", "Nouadhibou").

CROSS-CHECK (read off the page): national H 56,9% (53,6-60,2), A 56,3%, IPM
32,0%; urban H 35,4%, rural 77,1%; Guidimagha IPM 0,577, H 90,2%; Tiris
Zemmour H 25,2%; 0-4 ans H 63,8%.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_M = dict(mpi_type="national", measure_name="IPM-M (ANSADE)",
          survey="EPCV 2019 (Annuaire des Statistiques Sociodémographiques 2024)",
          k_cutoff=38, n_dimensions=4, n_indicators=19,
          unit_of_analysis="person", period="2019",
          reference_period="EPCV 2019", frequency="ad_hoc")
_P = r"(\d{1,3},\d)%"           # a printed percentage, one decimal
_I = r"(\d,\d{3})"              # a printed 0-1 index, three decimals
_WILAYAS = ["Guidimagha", "Gorgol", "Hodh Chargui", "Hodh Gharbi", "Assaba",
            "Tagant", "Brakna", "Adrar", "Trarza", "Nouakchott", "lnchiri",
            "Nouadhibou", "Tiris Zemmour"]
_TRIPLES = (("incidence_H", "incidence_H_ci_low", "incidence_H_ci_high"),
            ("intensity_A", "intensity_A_ci_low", "intensity_A_ci_high"))
_M0 = ("index_M0", "index_M0_ci_low", "index_M0_ci_high")


def _f(s: str) -> float:
    return float(s.replace(",", "."))


def _page(pages: list[str], caption: str) -> str:
    for t in pages:
        m = re.search(caption, t)
        if m and not re.search(r"\.{5}", t[m.start():t.find("\n", m.start())]):
            return t[m.start():]
    raise ValueError(f"ANSADE IPM-M: {caption!r} not found")


def _emit(vals: list[float], m0_unit: str, **kw) -> list[dict]:
    """vals = IPM, lo, hi, H, lo, hi, A, lo, hi -- the yearbook's order."""
    out = []
    for metric, v in zip(_M0, vals[0:3]):
        out.append(C.row(**_M, metric=metric, value=v, unit=m0_unit, **kw))
    for triple, chunk in zip(_TRIPLES, (vals[3:6], vals[6:9])):
        for metric, v in zip(triple, chunk):
            out.append(C.row(**_M, metric=metric, value=v, **kw))
    return out


def _table_67(pages) -> list[dict]:
    t = _page(pages, r"Tableau 6\.7 : Statistiques de pauvret")
    out = []
    # The first column ("Urbain", "National") wraps inside its cell, so only
    # its first letters share the line with the values.
    for prefix, kw in (("Urbai", dict(topic="locality", characteristic="Urbain",
                                      locality="urban", locality_label="Urbain")),
                       ("Rural", dict(topic="locality", characteristic="Rural",
                                      locality="rural", locality_label="Rural")),
                       ("Natio", {})):
        m = re.search(rf"^{prefix} {_P} " + " ".join([_P] * 9), t, re.M)
        if not m:
            raise ValueError(f"ANSADE 6.7: no {prefix} row")
        vals = [_f(x) for x in m.groups()][1:]      # drop the population share
        out += _emit(vals, "percent", series_code="ANSADE Annuaire 2024 T6.7", **kw)
    nat = [r["value"] for r in out if r["geography"] == "Total country"
           and r["topic"] == "total"]
    if nat[3] != 56.9 or nat[0] != 32.0:
        raise ValueError(f"ANSADE 6.7: national row reads {nat}")
    return out


def _table_68(pages) -> list[dict]:
    t = _page(pages, r"Tableau 6\.8 : Statistiques de pauvret")
    t = t[:t.find("Source")]
    out = []
    for w in _WILAYAS:
        m = re.search(rf"^{w} {_I} {_I} {_I} " + " ".join([_P] * 6), t, re.M)
        if not m:
            raise ValueError(f"ANSADE 6.8: no row for {w}")
        geo = "Inchiri" if w == "lnchiri" else w
        out += _emit([_f(x) for x in m.groups()], "index", geography=geo,
                     series_code="ANSADE Annuaire 2024 T6.8")
    return out


def _table_69(pages) -> list[dict]:
    t = _page(pages, r"Tableau 6\.9 : Statistiques de pauvret")
    t = t[:t.find("Source")]
    out = []
    for label in ("0 - 4 ans", "5-17 ans"):
        m = re.search(rf"^{re.escape(label)} {_P} {_I} {_I} {_I} "
                      + " ".join([_P] * 6), t, re.M)
        if not m:
            raise ValueError(f"ANSADE 6.9: no row {label!r}")
        vals = [_f(x) for x in m.groups()][1:]
        out += _emit(vals, "index", topic="age", characteristic=label,
                     age_group=label, series_code="ANSADE Annuaire 2024 T6.9")
    return out


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages[15:35]]
    return pd.DataFrame(_table_67(pages) + _table_68(pages) + _table_69(pages))


# The methodology as a LAYOUT, so `parsers.LAYOUTS` and tests/check_registry
# can verify it like every table-driven country's. This parser is bespoke, so
# there are no table specs; the dict is the same one every row is built from.
LAYOUT = {**_M, "tables": []}
