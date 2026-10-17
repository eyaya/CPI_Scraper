"""Côte d'Ivoire — Bulletin statistique de la dette publique (Ministère des
Finances et du Budget / Direction Générale des Financements, DGF), quarterly,
posted on the Treasury site tresor.gouv.ci.

PUBLISHER AND COVERAGE. The bulletin's own section A "Champs de couverture des
données": the public debt it reports is the debt of the ADMINISTRATION
CENTRALE, domestic and external, EXCLUDING the debt eligible for the C2D
(France) and PCD (Spain) debt-conversion programmes, which Tableau 2 reports
separately. State-guaranteed debt is shown apart (section IV / Tableau 11).

WHAT IS READ, from each bulletin:

* Tableau 1 "Encours, Tirages / Emissions et Service de la dette de
  l'Administration centrale" -- the three STOCK rows only: Dette Totale, Dette
  Extérieure, Dette Intérieure, each printed twice per period, in "Millions
  USD" and in "Milliards F CFA". Both units are collected as printed (two
  series_codes); nothing is converted. Drawings and debt service are flows,
  which this schema does not hold.
* Tableau 3 "Principaux ratios": "Dette de l'Administration Centrale en % du
  PIB" -> share_of_gdp.

Each bulletin recalls the four previous year-ends and the current quarter-end
(e.g. 2021, 2022, 2023, 2024, Septembre_2025). A year column is ANNUAL (end of
year); a "<mois>_<YYYY>" column is the QUARTER ending that month. Several
issues are read in one run; where two issues print the same period, the
NEWEST ISSUE WINS (the Dec-2024 bulletin's 2024 USD total 50 171,7 is revised
to 50 171,8 in the Sept-2025 one).

NOT READ, with the reason:
* Tableaux 4 and 7 (by maturity / instrument / currency; by institutional
  holder): their text layer DROPS GLYPHS -- "20 26 ,8" for 20 269,8,
  "24   4,4" for 24 774,4 -- so a value cannot be read with certainty.
* Tableau 11 (guaranteed debt): its stock column carries no unit on the page.
* Flows (Tableaux 5, 6, 8, 9, 10): drawings, service, projections, auctions.

TRAPS: values use SPACE thousands and a decimal COMMA, and every value carries
one decimal, so "34 929,9 20 269,8" splits unambiguously at each ",d".
Checked every run: Totale = Extérieure + Intérieure (to 0,2) in every column.

CROSS-CHECK (Sept 2025 issue): Dette Totale Sept 2025 = 34 016,3 milliards
FCFA = 53 970,2 millions USD; Extérieure 20 875,8; Intérieure 13 140,5;
Dette/PIB 59,3 % (2021: 50,2 %).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_VAL = re.compile(r"\d{1,3}(?: \d{3})*,\d")
_MONTH_Q = {"mars": 1, "juin": 2, "septembre": 3, "sept": 3, "décembre": 4,
            "decembre": 4}
_STOCK_ROWS = ("Dette Totale", "Dette Extérieure", "Dette Intérieure")
_ISSUE = re.compile(r"au\s+(\d{1,2})\s+([a-zéû]+)\s+(\d{4})", re.I)
_MONTH_NUM = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
              "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
              "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
              "decembre": 12}


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _periods(header: str) -> list[tuple[str, str]]:
    out = []
    for tok in header.split():
        m = re.fullmatch(r"(\d{4})(?:_Prov)?", tok)
        if m:
            out.append((m.group(1), "annual"))
            continue
        m = re.fullmatch(r"([A-Za-zéû]+)_(\d{4})", tok)
        if m and m.group(1).lower() in _MONTH_Q:
            q = _MONTH_Q[m.group(1).lower()]
            out.append((f"{m.group(2)}-Q{q}", "quarterly"))
    return out


def _read_issue(path: str) -> tuple[tuple[int, int], list[dict]]:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    m = _ISSUE.search(pages[0].replace("\n", " "))
    if not m or m.group(2).lower() not in _MONTH_NUM:
        raise ValueError(f"DGF CIV: cannot date the issue from its cover ({path})")
    issue = (int(m.group(3)), _MONTH_NUM[m.group(2).lower()])

    text = next((t for t in pages if "Tableau 1 : Encours" in t and "Dette Totale" in t), None)
    if text is None:
        raise ValueError(f"DGF CIV {issue}: Tableau 1 not found")
    lines = text.splitlines()
    i_tot = next(i for i, ln in enumerate(lines) if ln.startswith("Dette Totale"))
    header = next(ln for ln in reversed(lines[:i_tot]) if re.search(r"\b20\d\d\b", ln))
    periods = _periods(header)
    if len(periods) < 3:
        raise ValueError(f"DGF CIV {issue}: header {header!r}")

    # The first line after the header that STARTS WITH each stock label and
    # carries values. Older issues insert rows ("Dont arriérés") between them.
    rows, table = [], {}
    for lab in _STOCK_ROWS:
        ln = next((ln for ln in lines[i_tot:] if re.match(rf"{lab}\s+\d", ln)), None)
        vals = _VAL.findall(ln[len(lab):]) if ln else []
        if len(vals) != 2 * len(periods):
            raise ValueError(f"DGF CIV {issue}: Tableau 1 row {lab!r} gives "
                             f"{len(vals)} values for {len(periods)} periods")
        table[lab] = [_num(v) for v in vals]
    for j in range(2 * len(periods)):
        t, e, d = (table[r][j] for r in _STOCK_ROWS)
        if abs(t - (e + d)) > 0.2:
            raise ValueError(f"DGF CIV {issue}: Totale {t} != Ext {e} + Int {d}")
    for lab, vals in table.items():
        for k, (period, freq) in enumerate(periods):
            for v, unit, code in ((vals[2 * k], "USD million", "DGF BSDP T1 USD"),
                                  (vals[2 * k + 1], "FCFA milliards", "DGF BSDP T1 FCFA")):
                rows.append({"component": lab, "period": period, "frequency": freq,
                             "measure": "stock", "value": v, "unit": unit,
                             "series_code": code})

    ratio_line = next((ln for t in pages for ln in t.splitlines()
                       if ln.startswith("Dette de l'Administration Centrale en % du PIB")
                       or ln.startswith("Dette de l’Administration Centrale en % du PIB")), None)
    if ratio_line is None:
        raise ValueError(f"DGF CIV {issue}: Tableau 3 debt/GDP row not found")
    pcts = re.findall(r"(\d{1,3},\d)%", ratio_line)[:len(periods)]
    if len(pcts) != len(periods):
        raise ValueError(f"DGF CIV {issue}: debt/GDP row {ratio_line!r}")
    for (period, freq), p in zip(periods, pcts):
        rows.append({"component": "Dette de l'Administration Centrale en % du PIB",
                     "period": period, "frequency": freq, "measure": "share_of_gdp",
                     "value": _num(p), "unit": "percent", "series_code": "DGF BSDP T3"})
    return issue, rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    issues = sorted((_read_issue(p) for p in [path, *(extras or [])]),
                    key=lambda x: x[0])
    keep: dict[tuple, dict] = {}
    for _issue, rows in issues:               # oldest first: the newest wins
        for r in rows:
            keep[(r["component"], r["period"], r["unit"], r["series_code"])] = r
    return pd.DataFrame(list(keep.values()))
