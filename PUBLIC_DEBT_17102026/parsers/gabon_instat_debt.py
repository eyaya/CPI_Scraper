"""Gabon — INSTAT "Annuaire statistique du Gabon 2016-2020", chapter V.1.2
"Dette publique" (source: DGD, Direction Générale de la Dette).

THE ROUTE. The Ministry's hosts (economie.gouv.ga, dgd.ga) do not resolve and
BEAC's Gabon series is a joint compilation of ratios (sources_blocked
evidence, 2026-10-08/12). INSTAT's yearbook reprints the DGD's own tables,
credited "Source : DGD", so the publisher is INSTAT and the figures the DGD's.
(An earlier pass searched this yearbook for GDP only and recorded "GDP per head
only"; its debt chapter was not looked at.)

COLLECTED (2016-2020, FCFA milliards):
* Tableau V.1.2.1 "Encours de la dette publique directe et garantie": external
  and domestic debt, each split direct / guaranteed, and the total. The
  repeated sub-labels are qualified by their block ("Dette extérieure: dette
  directe").
* Tableau V.1.2.5, the "Encours de la dette / PIB" row -> share_of_gdp.

NOT COLLECTED: V.1.2.2-V.1.2.4 (debt service, interest, repayments -- flows)
and the other V.1.2.5 ratios (service, exports, current expenditure).

PUBLISHED ROUNDING KEPT: external + domestic = total to within 0,01 in
2016/2017/2019, but 2018 prints 5 259,70 against 5 259,80 and 2020 6 277,73
against 6 277,93. Pinned in `_KNOWN_GAPS`; any other gap raises.

CROSS-CHECK: total 2020 6 277,73 (69,80 % of GDP); 2016 4 092,80 (49,3 %);
external direct 2020 4 029,14.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_T1 = re.compile(r"Tableau V\.1\.2\.1 : Encours de la dette Publique directe et garantie")
_T5 = re.compile(r"Tableau V\.1\.2\.5 : Ratios d.endettement")
_NUM = r"\d{1,3}(?: \d{3})*,\d{1,2}"
_KNOWN_GAPS = {"2018": -0.10, "2020": -0.20}   # printed total - (external + domestic)


def _f(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _block(text: str, cap: re.Pattern, n: int):
    m = cap.search(text)
    lines = text[m.end():].splitlines()
    head = next(ln for ln in lines if re.fullmatch(r"(?:20\d\d\s*){3,}", ln.strip()))
    years = head.split()
    rows = []
    for ln in lines[lines.index(head) + 1:]:
        if ln.startswith("Source"):
            break
        r = re.fullmatch(rf"(.+?)\s+((?:(?:{_NUM}|\.\.)\s*){{{len(years)}}})", ln.strip())
        if r:
            # NOT .split(): "3 107,00" is ONE value with a space thousands
            # separator.
            rows.append((r.group(1).strip(), re.findall(rf"{_NUM}|\.\.", r.group(2))))
    return years, rows


def parse(path: str, extras=None) -> pd.DataFrame:
    # Each table on its own page (V.1.2.1 and V.1.2.5 sit on consecutive
    # pages); the table of contents carries both captions with dot leaders.
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]

    def page_of(cap):
        t = next((t for t in pages if cap.search(t) and "Source : DGD" in t
                  and "....." not in t), None)
        if t is None:
            raise ValueError(f"INSTAT Gabon: {cap.pattern!r} not found")
        return t

    years, rows = _block(page_of(_T1), _T1, 7)
    if [r[0] for r in rows] != ["Dette extérieure", "Dette directe", "Dette garantie",
                                "Dette intérieure", "Dette directe", "Dette garantie",
                                "Total Encours"]:
        raise ValueError(f"INSTAT Gabon V.1.2.1: rows {[r[0] for r in rows]}")
    out, parent, vals = [], "", {}
    for lab, cells in rows:
        if lab in ("Dette extérieure", "Dette intérieure", "Total Encours"):
            parent, comp = lab, lab
        else:
            comp = f"{parent}: {lab.lower()}"
        vals[comp] = [_f(c) for c in cells]
        for y, v in zip(years, vals[comp]):
            out.append({"component": comp, "period": y, "frequency": "annual",
                        "measure": "stock", "value": v, "unit": "FCFA milliards",
                        "series_code": "INSTAT Annuaire T V.1.2.1 (DGD)"})
    for j, y in enumerate(years):
        ext, dom, tot = (vals[k][j] for k in ("Dette extérieure", "Dette intérieure",
                                               "Total Encours"))
        sub_e = vals["Dette extérieure: dette directe"][j] + vals["Dette extérieure: dette garantie"][j]
        if abs(sub_e - ext) > 0.015:
            raise ValueError(f"INSTAT Gabon {y}: external direct + guaranteed != external")
        gap = round(tot - ext - dom, 2)
        if abs(gap - _KNOWN_GAPS.get(y, 0.0)) > 0.015:
            raise ValueError(f"INSTAT Gabon {y}: total - (external + domestic) = {gap}")

    y5, ratios = _block(page_of(_T5), _T5, 5)
    row = next((c for lab, c in ratios if lab.startswith("Encours de la dette / PIB")), None)
    if row is None or y5 != years:
        raise ValueError("INSTAT Gabon V.1.2.5: debt/GDP row not found")
    for y, c in zip(y5, row):
        if c != "..":
            out.append({"component": "Total Encours", "period": y, "frequency": "annual",
                        "measure": "share_of_gdp", "value": _f(c), "unit": "percent",
                        "series_code": "INSTAT Annuaire T V.1.2.5 (DGD)"})
    return pd.DataFrame(out)
