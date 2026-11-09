"""Benin -- INSAE, "Enquête Modulaire Intégrée sur les Conditions de Vie des
ménages (EMICoV) 2006 : Rapport d'analyse" (fieldwork August-November 2006;
Wayback `id_` copy of insae-bj.org).

A RELATIVE LINE. Chapter 2 sets every poverty line "aux deux premiers
quintiles de la distribution de l'indicateur de niveau de vie" -- for monetary
poverty, consumption per head -- so the monetary headcount is measured
against the 40th percentile, not the EMICoV 2009+ absolute line: line_type
relative. P0 is printed as a FRACTION (0,430): unit index, kept as printed.

    Tableau 2.1  monetary P0 ("PM") by the 12 departments (the PNM / PCV /
                 PA / PS columns are non-monetary and subjective: not taken).
    Tableau 2.7  monetary P0 by the 77 communes, two communes per line:
                 Commune | Proportion | Ecart-type | Rang (standard error and
                 rank not taken).
NOT COLLECTED: the national (37,4 %) and urban / rural values, printed only
as chart labels (Graphiques 2.1, 2.2: the bar-to-label order is not
recoverable for 2.2). PUBLISHED ODDITY KEPT: the prose quotes commune rates
that differ from Tableau 2.7 (Adjarra 22,17 % vs 0,220, Cotonou 30,38 % vs
0,310, Parakou 37,21 % vs 0,384); the table's values are kept.

CROSS-CHECK (verbatim): Alibori 0,430; Littoral 0,304; Couffo 0,406; Adjarra
0,220; Banikoara 0,563; Cotonou 0,310.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

LINE = "Deux premiers quintiles de la dépense par tête (EMICoV 2006)"
_DEPTS = ["Alibori", "Atacora", "Atlantique", "Borgou", "Collines", "Couffo", "Donga",
          "Littoral", "Mono", "Ouémé", "Plateau", "Zou"]
_BASE = dict(survey="EMICoV 2006", welfare_aggregate="consumption", unit_of_analysis="person",
             line_type="relative", line_level="overall", line_name=LINE, period="2006",
             reference_period="2006 (août-novembre)", frequency="ad_hoc", unit="index")
_COMMUNE = re.compile(r"([A-Z][A-Z'\- ]*?)\s+(\d,\d{3})\s+(\d,\d{3})\s+(\d{1,2})(?=\s|$)")


def _page(pdf, caption):
    for pg in pdf.pages:
        t = pg.extract_text() or ""
        if caption in t and "...." not in t:
            return t
    raise ValueError(f"{caption!r} not found")


def parse(path: str) -> pd.DataFrame:
    out = []
    with pdfplumber.open(path) as pdf:
        t = _page(pdf, "Tableau 2.1 : Différentes formes de pauvreté selon les départements")
        body = t.split("Tableau 2.1 :")[1].split("Source")[0]
        for dep in _DEPTS:
            m = re.search(rf"^{dep}\s+(\d,\d{{3}})\s", body, re.M)
            if not m:
                raise ValueError(f"Tableau 2.1: {dep} not found")
            out.append(C.row(metric="headcount", value=C.to_number(m.group(1), ","),
                             geography=dep, **_BASE))
        t = _page(pdf, "Tableau 2.7 : Pauvreté monétaire suivant les communes")
        body = t.split("Tableau 2.7 :")[1].split("Source")[0]
        ranks = set()
        for m in _COMMUNE.finditer(body):
            name, p0, _, rank = m.groups()
            ranks.add(int(rank))
            out.append(C.row(metric="headcount", value=C.to_number(p0, ","),
                             geography=name.strip(), **_BASE))
        if ranks != set(range(1, 78)):
            raise ValueError(f"Tableau 2.7: ranks read {len(ranks)} of 77")
    return pd.DataFrame(out)


LAYOUT = {k: v for k, v in _BASE.items() if k != "unit"} | {"tables": []}
