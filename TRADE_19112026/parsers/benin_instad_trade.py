"""Parser for INStaD Benin "Grands traits du commerce extérieur du Bénin en <année>" (Tier 3 PDF).

Annexes read (decimal POINT, thousands space):
* Annexe 1 "Evolution des exportations et des importations par produit, niveau
  chapitre ... (SH2)": per chapter (label only), exports 3 years, imports 3 years
  (millions of FCFA), the latest year's "Solde commercial" and 4 percentage columns
  (skipped) -> 11 cells per row; a row with any other count is dropped.
* Annexe 2 "Liste des indicateurs du commerce international": "Exportations totales
  des biens (en milliards de FCFA)" and "Importations totales des biens" for every
  year 2005..latest. Its "Solde de la balance commerciale des biens" is
  ((2) - alpha x (3)) -- imports brought to FOB with an official freight rate -- not
  exports - imports, so it is not collected.
"""
from __future__ import annotations

import re

import pandas as pd

from ._common import row, to_number

_NUM = re.compile(r"^-?\d{1,3}(?:[   ]\d{3})*(?:\.\d+)?$|^-?\d+(?:\.\d+)?$")


def _n(s):
    return to_number(s.replace(",", "").replace(".", ","), decimal=",")


def _lines(doc):
    return [ln.strip() for p in doc for ln in p.get_text().split("\n") if ln.strip()]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    import fitz
    doc = fitz.open(path)
    try:
        lines = _lines(doc)
    finally:
        doc.close()
    out = []
    text = "\n".join(lines)
    # ---- Annexe 2: annual exports / imports of goods
    i = next((k for k, ln in enumerate(lines) if ln.startswith("Annexe 2") and "indicateurs" in ln.lower()), None)
    if i is not None:
        years = []
        k = i + 1
        while k < len(lines) and not re.fullmatch(r"(19|20)\d{2}", lines[k]):
            k += 1
        while k < len(lines) and re.fullmatch(r"(19|20)\d{2}", lines[k]):
            years.append(lines[k])
            k += 1
        for lab, flow in (("Exportations totales des", "export"), ("Importations totales des", "import")):
            j = next((m for m in range(k, len(lines)) if lines[m].startswith(lab)), None)
            if j is None:
                continue
            hdr = " ".join(lines[j:j + 3]).lower()
            if "milliards de fcfa" not in hdr:
                continue
            m = j
            while m < len(lines) and not _NUM.match(lines[m]):
                m += 1
            cells = []
            while m < len(lines) and len(cells) < len(years):
                s = lines[m]
                parts = re.split(r"\s(?=\d{1,3}(?:\s\d{3})*\.\d)", s) if not _NUM.match(s) else [s]
                if not all(_NUM.match(p) for p in parts):
                    break
                cells += parts
                m += 1
            if len(cells) != len(years):
                continue
            for y, c in zip(years, cells):
                v = _n(c)
                if v is not None:
                    out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit="XOF",
                                   unit_multiplier=1e9, price_basis="fob" if flow == "export" else "cif",
                                   series_code="Annexe 2"))
    # ---- Annexe 1: HS chapters
    i = next((k for k, ln in enumerate(lines) if ln.startswith("Annexe 1")), None)
    if i is not None:
        k = i
        years = []
        while k < len(lines) and len(years) < 3:
            if re.fullmatch(r"(19|20)\d{2}", lines[k]):
                years.append(lines[k])
            k += 1
        if len(years) == 3 and "millions fcfa" in " ".join(lines[i:k]).lower():
            # skip the rest of the column header
            while k < len(lines) and not re.search(r"[a-z]{3}", lines[k]):
                k += 1
            lab, cells = None, []
            for s in lines[k:]:
                if s.startswith("Annexe 2") or s.startswith("Source"):
                    break
                if _NUM.match(s):
                    if lab:
                        cells.append(s)
                    continue
                if lab and cells:
                    _hs_row(out, lab, cells, years)
                    lab, cells = None, []
                if re.match(r"^Grands traits", s) or re.fullmatch(r"\d{1,3}", s):
                    continue
                lab = f"{lab} {s}" if (lab and not cells) else s
            if lab and cells:
                _hs_row(out, lab, cells, years)
    return pd.DataFrame(out)


def _hs_row(out, lab, cells, years):
    if len(cells) != 11:
        return
    lab = re.sub(r"\s+", " ", lab).strip()
    total = lab.lower().startswith("total")
    for flow, off in (("export", 0), ("import", 3)):
        for k, y in enumerate(years):
            v = _n(cells[off + k])
            if v is None:
                continue
            out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit="XOF", unit_multiplier=1e6,
                           commodity=None if total else lab, commodity_classification="" if total else "hs2",
                           price_basis="fob" if flow == "export" else "cif", series_code="Annexe 1"))
    # cells[6], the "Solde commercial", is exports - alpha x imports (imports at FOB with the
    # official freight rate): -501,4 for "Animaux vivants" against 44,7 - 617,1. Not collected.
