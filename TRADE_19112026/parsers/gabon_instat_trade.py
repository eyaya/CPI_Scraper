"""Parser for INSTAT Gabon "Bulletin des statistiques du commerce extérieur"
(quarterly, 2020 Q1 - 2022 Q3 on new.instatgabon.org; data DGS and DGDDI).

Every table has three value columns -- the bulletin's quarter a year earlier,
the previous quarter and the bulletin's quarter -- followed by two variation
columns (%) that are not read. The PDF text layer gives each table as a label
line followed by its numbers, one per line; the three periods come from the
bulletin's quarter (file name), as the header prints ("3e Trim 2021 / 2e Trim
2022 / 3e Trim 2022"). Tables read (by caption):

  Tableau 1 "exportations par groupe de produits" (milliards de F.CFA):
      "Exportations" (all products) + the NSO's product groups (national)
  Tableau 2 the same in milliers de tonnes (net weight)
  Tableau 3 "exportations par continent de destination" (groups)
  Tableau 5 "importations des principaux produits par type de biens":
      "Importations" + types of goods and products (national)
  Tableau 6 "importations par continent" (groups)
Not read: the side-by-side top-20 client / supplier rankings, the partner
balances, structure (%) tables, and Tableau 8 whose row labels have no text
layer (its balance rows cannot be identified from the text).
"""
from __future__ import annotations

import os
import re

import fitz
import pandas as pd

from ._common import row, to_number, _fold
from ..schema import KEY

_NUM = re.compile(r"^-?\d{1,3}(?:[   ]\d{3})*(?:,\d+)?$|^-?\d+,\d+$|^[-_]$")
# "^-?\d+,\d+$": a figure printed without a thousands space ("1013,4", BULLETIN_3T2021
# Tableau 1) was taken for a row label, so the row above lost a cell and the
# numbers after it were filed under a label "1013,4" (row split repaired 2026-11-12).
_QW = {"1ER": 1, "2EME": 2, "3EME": 3, "4EME": 4}


def bulletin_quarter(path):
    b = os.path.basename(path).upper()
    m = re.search(r"([1-4])T(20\d\d)", b)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.search(r"(1ER|2EME|3EME|4EME)-TRIMESTRIEL-(20\d\d)", b)
    if m:
        return int(m.group(2)), _QW[m.group(1)]
    return None


def _periods(y, q):
    py, pq = (y, q - 1) if q > 1 else (y - 1, 4)
    return [f"{y - 1}-Q{q}", f"{py}-Q{pq}", f"{y}-Q{q}"]


def _table_kind(cap):
    t = _fold(cap)
    if "exportations par groupe de produits" in t:
        return "exp_products"
    if "exportations par continent" in t:
        return "exp_continent"
    if "importations des principaux produits" in t or "importations par type" in t \
            or "importations par groupe de produits" in t:
        return "imp_products"
    if "importations par continent" in t:
        return "imp_continent"
    if "importations par section" in t:
        return "imp_sh"
    if "exportations par zone economique" in t:
        return "exp_continent"
    if "importations par zone economique" in t:
        return "imp_continent"
    return None


def parse_bulletin(path: str) -> pd.DataFrame:
    yq = bulletin_quarter(path)
    if yq is None:
        return pd.DataFrame()
    pers = _periods(*yq)
    doc = fitz.open(path)
    try:
        lines = [l.strip() for p in doc for l in p.get_text().split("\n")]
    finally:
        doc.close()
    out = []
    i = 0
    while i < len(lines):
        m = re.match(r"^tableau\s*(\d+)\s*:\s*(.*)$", lines[i], re.I)
        if not m or "...." in lines[i]:
            i += 1
            continue
        cap = lines[i]
        kind = _table_kind(cap)
        j = i + 1
        block = []
        while j < len(lines) and not lines[j].lower().startswith(("source", "tableau")):
            block.append(lines[j])
            j += 1
        i = j
        if kind is None:
            continue
        head = " ".join(block[:8])
        ft = _fold(cap + " " + head)
        # The periods come from the file name, so a page whose header names another
        # quarter is not read: BULLETIN_3T2021's Tableau 5 "(suite)" page at "2e
        # Trim.2021 / 1er Trim.2021 / 2e Trim.2020" is a page of the previous issue,
        # and its figures would be filed one quarter late. (Repaired 2026-11-12.)
        seen_q = {(int(y), int(q)) for q, y in re.findall(r"\b([1-4])\s*(?:er|e|eme)?\s*trim\.?\s*(20\d\d)", ft)}
        if seen_q and yq not in seen_q:
            continue
        if "milliers de tonnes" in ft:
            measure, unit, mult = "net_weight", "tonnes", 1e3
        elif re.search(r"milliards?\s+(?:de\s+)?(?:f\.?\s*cfa|francs?\s+cfa|fcfa)", ft):
            measure, unit, mult = "value", "XAF", 1e9
        else:
            continue
        flow = "export" if kind.startswith("exp") else "import"
        # label line, then its numbers
        k = 0
        prev_bare = None        # a label line directly followed by another label line
        while k < len(block):
            lab = block[k]
            if _NUM.match(lab) or not lab or re.search(r"trim|variation|^en milli|^valeur|^part", _fold(lab)):
                k += 1
                prev_bare = None
                continue
            # A label wrapped over two lines ("Produits alimentaires (y compris" /
            # "boissons alcoolisées)"): the second line starts in lower case or closes
            # a parenthesis it did not open. It is joined to the line above when that
            # line carried no figures (some HS chapter names are printed in lower
            # case, "fruits comestibles; ...", and stand alone after a row of figures).
            cont = lab[:1].islower() or lab.startswith("(") or lab.count(")") > lab.count("(")
            if cont and prev_bare is not None:
                lab = prev_bare + " " + lab
            prev_bare = None
            nums = []
            k += 1
            while k < len(block) and (_NUM.match(block[k]) or not block[k]):
                if block[k]:
                    nums.append(block[k])
                k += 1
            if not nums:
                prev_bare = lab
                continue
            # values, then two variation columns: 3 values (Q-4, Q-1, Q) or, in
            # the 2020-2021 import tables, the five quarters Q-4 ... Q
            nval = len(nums) - 2
            if nval == 3:
                rowpers = pers
            elif nval == 5:
                y, q = yq
                rowpers = []
                for b in range(4, -1, -1):
                    yy, qq = y, q - b
                    while qq < 1:
                        yy, qq = yy - 1, qq + 4
                    rowpers.append(f"{yy}-Q{qq}")
            else:
                continue
            fl = _fold(lab)
            if fl in ("exportations", "importations"):
                kw = dict(commodity=None, partner=None)
            elif kind.endswith("continent"):
                if fl.startswith("total"):
                    continue        # "Total général" is the all-partner total, not a group
                kw = dict(partner=lab, partner_type="group")
            else:
                kw = dict(commodity=lab.rstrip(" ."), commodity_classification="national")
            for per, tok in zip(rowpers, nums[:nval]):
                v = None if tok in ("-", "_") else to_number(tok, decimal=",")
                if v is None or v < 0:
                    continue
                out.append(row(tradeflow=flow, period=per, frequency="quarterly", value=v, unit=unit,
                               unit_multiplier=mult, measure=measure, series_code=f"T{m.group(1)}", **kw))
    df = pd.DataFrame.from_records(out)
    if df.empty:
        return df
    return df.drop_duplicates([c for c in KEY if c in df.columns]).reset_index(drop=True)


def parse(path: str, extras=None) -> pd.DataFrame:
    files = sorted({path, *(extras or [])}, key=lambda f: bulletin_quarter(f) or (0, 0))
    df = pd.concat([parse_bulletin(f) for f in files], ignore_index=True)
    return df.drop_duplicates([c for c in KEY if c in df.columns], keep="last").reset_index(drop=True)
