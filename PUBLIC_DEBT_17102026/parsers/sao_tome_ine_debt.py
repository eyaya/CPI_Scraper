"""São Tomé and Príncipe — INE "São Tomé e Príncipe em Números" (bilingual
pocket yearbook), table 17.1 "Composição da dívida pública por fontes de
financiamento", USD million (source: the government's "Relatório anual sobre
Gestão e Seguimento da Dívida Pública").

THE ROUTE. financas.gov.st answers 403 and the central bank (BCSTP) publishes
debt SERVICE flows and prose stock figures only (sources_blocked evidence,
2026-10-12). INE's yearbook reprints the debt-management report's stock table,
credited, so the publisher is INE and the figures are the Ministry's.

COLLECTED: multilateral, bilateral, suppliers ("fornecedores"), Treasury bills
and the total, 2013-2017. Labels are kept in the Portuguese half of the
bilingual stub ("Multilateral / Multilatéral" -> "Multilateral").

CHECK: the four sources must sum to TOTAL in every year (they do exactly:
2017 = 44,5 + 235,3 + 13,3 + 17,0 = 310,1).

CROSS-CHECK: total 2013 232,4; 2017 310,1; bilateral 2017 235,3.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_CAPTION = re.compile(r"17\.1\. COMPOSIÇÃO DA DÍVIDA PÚBLICA POR FONTES DE FINANCIAMENTO")
_NUM = r"\d{1,3}(?:\.\d{3})*,\d"


def _f(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def parse(path: str, extras=None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        text = next((p.extract_text() or "" for p in pdf.pages
                     if _CAPTION.search(p.extract_text() or "")), None)
    if text is None:
        raise ValueError("INE STP: table 17.1 not found")
    lines = text[_CAPTION.search(text).end():].splitlines()
    head = next(ln for ln in lines if "Fontes de Financiamento" in ln)
    years = re.findall(r"20\d\d", head)
    if len(years) < 3:
        raise ValueError(f"INE STP: header {head!r}")
    rows = []
    for ln in lines[lines.index(head) + 1:]:
        if ln.startswith("Fonte"):
            break
        m = re.fullmatch(rf"(.+?)\s+((?:{_NUM}\s*){{{len(years)}}})", ln.strip())
        if not m:
            continue
        label = m.group(1).split(" / ")[0].strip()
        rows.append((label, [_f(v) for v in m.group(2).split()]))
    labels = [r[0] for r in rows]
    if not rows or labels[-1] != "TOTAL" or len(rows) < 4:
        raise ValueError(f"INE STP: rows {labels}")
    *parts, (_, total) = rows
    for j, y in enumerate(years):
        if abs(sum(v[j] for _, v in parts) - total[j]) > 0.15:
            raise ValueError(f"INE STP {y}: sources do not sum to TOTAL")
    return pd.DataFrame([{"component": "Total" if lab == "TOTAL" else lab,
                          "period": y, "frequency": "annual", "measure": "stock",
                          "value": v, "unit": "USD million",
                          "series_code": "INE STP em Números T17.1"}
                         for lab, vals in rows for y, v in zip(years, vals)])
