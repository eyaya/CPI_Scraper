"""Togo — Bulletin statistique de la dette de l'Administration centrale du Togo,
Direction de la Dette Publique et du Financement (DDPF), Direction Générale du
Trésor et de la Comptabilité Publique, Ministère de l'Economie et des Finances,
on finances.gouv.tg (/documentation/ file browser).

COVERAGE, as the bulletin states it ("I. Couverture"): the domestic and
external debt of the CENTRAL ADMINISTRATION only -- decentralised
administrations and public enterprises are not covered.

THE ONLY ISSUE ON THE MINISTRY'S SITE is the first edition: 2017, with annual
data 2013-2017. No later bulletin is posted there (checked 2026-10-12: the
documentation browser, the site search, the WordPress media API returns HTTP
500; ddpf.finances.gouv.tg and dette.gouv.tg do not answer).

WHAT IS READ:
  * Tableau 1 -- "Dette Totale", "Dette Extérieure", "Dette Intérieure", year-end
    stocks in USD million AND XOF million (two columns per year);
  * Tableau 21 -- "Dette extérieure / PIB" and "Dette de l'Administration
    Centrale/ PIB", percent, as printed (never recomputed).
Flows (tirages, service) are not stocks and are not read. Space-grouped
figures print with inconsistent gaps ("1146 600,62", "291220,75"), so values
are split at each ",dd" decimal, and every year is held to
total = extérieure + intérieure in both currencies (to 0,02).

CROSS-CHECK: Dette Totale 2017 2 017 948,83 XOF m = 3 685,58 USD m; 2013
1 146 600,62; debt/GDP 2017 73,66 %; external/GDP 2013 14,95 %.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_VAL = re.compile(r"\d[\d ]*?,\d{2}")
_YEARS = ["2013", "2014", "2015", "2016", "2017"]
_T1 = {"Dette Totale": "Dette totale de l'Administration centrale",
       "Dette Extérieure": "Dette extérieure de l'Administration centrale",
       "Dette Intérieure": "Dette intérieure de l'Administration centrale"}
_T21 = {"Dette extérieure / PIB": "Dette extérieure / PIB",
        "Dette de l'Administration Centrale/ PIB": "Dette de l'Administration centrale / PIB"}


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _page(pdf, caption: str) -> str:
    for p in pdf.pages:
        t = p.extract_text() or ""
        if re.search(caption, t):
            return t
    raise ValueError(f"DDPF TG: {caption!r} not found")


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(path) as pdf:
        t1 = _page(pdf, r"Tableau 1: Encours de la dette de l'Administration centrale")
        t21 = _page(pdf, r"Tableau 21: Principaux indicateurs")
    if not re.search(r"\b2013 2014 2015 2016 2017\b", t1):
        raise ValueError("DDPF TG T1: header is no longer 2013..2017")
    got = {}
    for ln in t1.splitlines():
        for lab in _T1:
            # The FIRST occurrence is the stock block; "Dette Extérieure" /
            # "Dette Intérieure" recur under Tirages and Service (flows).
            if ln.startswith(lab + " ") and lab not in got:
                vals = [_num(v) for v in _VAL.findall(ln[len(lab):])]
                if len(vals) != 10:
                    raise ValueError(f"DDPF TG T1 {lab}: {len(vals)} values")
                got[lab] = vals
    if set(got) != set(_T1):
        raise ValueError(f"DDPF TG T1: rows {sorted(got)}")
    for j, y in enumerate(_YEARS):
        for k in (0, 1):                          # USD, XOF
            i = 2 * j + k
            s = got["Dette Extérieure"][i] + got["Dette Intérieure"][i]
            if abs(s - got["Dette Totale"][i]) > 0.02:
                raise ValueError(f"DDPF TG T1 {y}: total {got['Dette Totale'][i]} "
                                 f"!= ext + int {s:.2f}")
        for lab, comp in _T1.items():
            for k, unit in ((0, "USD million"), (1, "XOF million")):
                rows.append({"component": comp, "period": y, "frequency": "annual",
                             "measure": "stock", "value": got[lab][2 * j + k],
                             "unit": unit, "series_code": "DDPF T1"})
    for ln in t21.splitlines():
        for lab, comp in _T21.items():
            if ln.startswith(lab + " "):
                vals = [_num(v) for v in re.findall(r"\d{1,3},\d{2}", ln[len(lab):])]
                if len(vals) != 5:
                    raise ValueError(f"DDPF TG T21 {lab}: {vals}")
                for y, v in zip(_YEARS, vals):
                    rows.append({"component": comp, "period": y, "frequency": "annual",
                                 "measure": "share_of_gdp", "value": v,
                                 "unit": "percent", "series_code": "DDPF T21"})
    if sum(r["series_code"] == "DDPF T21" for r in rows) != 10:
        raise ValueError("DDPF TG T21: debt ratios not found")
    return pd.DataFrame(rows)
