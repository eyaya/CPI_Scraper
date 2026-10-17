"""Togo — the Treasury's (DGTCP, Direction de la Dette Publique et du
Financement) quarterly "Bulletin statistique de la dette" and annual
"Rapport analytique de la dette publique", from tresorpublic.gouv.tg.

The 2013-2017 bulletin (togo.yaml, parser togo_ddpf_debt) is the DDPF's first
edition; these are its successors, read here into their own series codes.

QUARTERLY BULLETINS (2020-Q1 .. now), Tableau 3 "Position de la dette totale de
l'Administration Centrale par trimestre" (QPDS Tableau 4), XOF million, a
rolling window of 4-7 quarters ending at the issue's quarter. Only the rows
that print on one line and can be checked are read:
  Dette brute totale; Par Monnaie de dénomination (its total), Monnaie locale,
  Monnaie étrangère; Par résidence du créancier (its total), Créanciers
  résidents, Créanciers non-résidents.
The instrument/maturity rows are NOT read: their cells wrap and run together
in the text layer ("2 1 61 148,99", "2138454,248"). A wrapped "Créanciers
non-/résidents" label is skipped for that issue (never reconstructed).
Headers come as "2020T1", "2019 T1", "mars-25", "Juin-25"; every header must
resolve to consecutive quarters ending at the issue's own quarter.
The 31 March 2024 issue prints a different Tableau 3 (year-ends 2020-2023 and
31-mars-24); every date in it is also printed by a neighbouring issue, so that
issue's table is skipped, not mapped.

ANNUAL REPORTS (2019 .. 2025 editions), "Tableau n : Situation de la dette (publique)
de YYYY à YYYY": Dette Totale / Extérieure / Intérieure at year-end, FCFA
milliards, 3-5 years each (2017-2025 overall). The 2023 edition prints USD and
XOF pairs; the XOF column is read.

Where issues overlap, the NEWEST issue wins (files are read oldest first and
later rows replace earlier ones): the Treasury revises (2019 total 2 196,64 in
the 2019 report, 2 197,74 from the 2020 report on).

PUBLISHED INCONSISTENCIES, kept and pinned:
* 2023-Q2 and 2023-Q3 "Dette brute totale" print the LOCAL-CURRENCY figure
  (2 283 569,27; 2 352 457,59) while the currency and residence totals print
  3 585 604,01 and 3 692 401,19 -- in the Sept 2023, Dec 2023, June 2024 and
  Sept 2024 issues (the June 2023 issue printed 2023-Q2 correctly, 3 583 632).
  Both rows are kept under their own labels. CONSEQUENCE of "newest wins":
  the filed "Dette brute totale" for those two quarters is the misprinted one;
  use "Par monnaie de dénomination (total)" for them.
Any other identity break raises.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import fitz  # PyMuPDF
import pdfplumber

_NUM = r"\d{1,3}(?: \d{3})+(?:,\d+)?|\d+(?:,\d+)?"
_MONTH_Q = {"mars": 1, "juin": 2, "sept": 3, "septembre": 3, "dec": 4, "déc": 4,
            "decembre": 4, "décembre": 4}
# Tableau 3 rows read, label as printed -> component.
_T3_ROWS = [
    ("Dette brute totale", "Dette brute totale"),
    ("Par Monnaie de dénomination", "Par monnaie de dénomination (total)"),
    ("Monnaie locale", "Monnaie locale"),
    ("Monnaie étrangère", "Monnaie étrangère"),
    ("Par résidence du créancier", "Par résidence du créancier (total)"),
    ("Créanciers résidents", "Créanciers résidents"),
    ("Créanciers non-résidents", "Créanciers non-résidents"),
]
# (issue, period) whose printed "Dette brute totale" is not the currency /
# residence total. The 30 June 2023 issue prints 2023-Q2 correctly; the misprint
# starts with the September 2023 issue and is repeated while the quarters stay
# in the window.
_KNOWN_TOTAL_MISPRINT = {(iss, per) for iss in ("2023-Q3", "2023-Q4", "2024-Q2", "2024-Q3")
                         for per in ("2023-Q2", "2023-Q3")}
_T3_SERIES = "DGTCP Bulletin statistique T3 (QPDS T4)"
_RA_SERIES = "DGTCP Rapport analytique (Situation de la dette)"


def _f(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _pages(path: str, needle: str) -> list[str]:
    """Page texts: the first two (cover) via PyMuPDF, and pdfplumber's layout
    text for the pages whose PyMuPDF text contains `needle` -- pdfplumber on
    every page of a 40-page bulletin is minutes per file. Other pages ''."""
    with fitz.open(path) as doc:
        quick = [pg.get_text() for pg in doc]
    hits = {i for i, t in enumerate(quick) if needle in t}
    out = [quick[i] if i < 2 else "" for i in range(len(quick))]
    with pdfplumber.open(path) as pdf:
        for i in sorted(hits):
            out[i] = pdf.pages[i].extract_text() or ""
    return out


def _issue_quarter(pages: list[str]) -> tuple[int, int] | None:
    """The bulletin's own quarter, from its cover ("... à fin juin 2026")."""
    head = " ".join(" ".join(pages[:2]).split()).lower()
    # "... DU TOGO AU 30 JUIN 2021" (the usual cover), else "à fin mars 2020".
    m = (re.search(r"\bau\s+3[01]\s+(mars|juin|septembre|décembre|decembre)\s+(20\d\d)", head)
         or re.search(r"fin\s+(mars|juin|septembre|sept|décembre|decembre|déc|dec)\w*\s+(20\d\d)", head))
    if not m:
        m = re.search(r"(premier|1er|deuxième|2ème|troisième|3ème|quatrième|4ème)\s+trimestre\s+(20\d\d)", head)
        if not m:
            return None
        q = {"premier": 1, "1er": 1, "deuxième": 2, "2ème": 2, "troisième": 3, "3ème": 3,
             "quatrième": 4, "4ème": 4}[m.group(1)]
        return int(m.group(2)), q
    return int(m.group(2)), _MONTH_Q[m.group(1)]


def _header_quarters(line: str) -> list[tuple[int, int]]:
    out = []
    for tok in re.finditer(r"(20\d\d)\s*T([1-4])|([A-Za-zéû]+)-(\d\d)\b", line):
        if tok.group(1):
            out.append((int(tok.group(1)), int(tok.group(2))))
        else:
            mo = tok.group(3).lower()
            if mo not in _MONTH_Q:
                return []
            out.append((2000 + int(tok.group(4)), _MONTH_Q[mo]))
    return out


def _bulletin(path: str) -> list[dict]:
    pages = _pages(path, "Position de la dette totale")
    issue = _issue_quarter(pages)
    t = next((x for x in pages if "Tableau 3 : Position de la dette totale" in x
              and "Source" in x), None)
    if t is None or issue is None:
        raise ValueError(f"Togo DGTCP bulletin {os.path.basename(path)}: "
                         f"Tableau 3 or issue quarter not found")
    lines = t.splitlines()
    hdr_i = next((i for i, ln in enumerate(lines[:6]) if re.search(r"20\d\d\s*T[1-4]|-\d\d\b", ln)), None)
    if hdr_i is None:
        raise ValueError(f"Togo DGTCP {os.path.basename(path)}: no Tableau 3 header")
    if re.search(r"\b20\d\d\s+20\d\d\b", lines[hdr_i]) and not re.search(r"T[1-4]", lines[hdr_i]):
        # 31 March 2024 issue: year-end columns (see module docstring).
        print(f"  [Togo DGTCP] {os.path.basename(path)}: Tableau 3 in year-end layout -- skipped")
        return []
    qs = _header_quarters(lines[hdr_i])
    # Quarters must rise and end at the issue's own quarter. Not necessarily
    # consecutive: the 30 Sept 2024 issue prints 2023T2..2024T1 then 2024T3
    # (2024T2 omitted; its 2024T3 column matches later issues).
    if not qs or qs[-1] != issue or any(
            (b[0] * 4 + b[1]) <= (a[0] * 4 + a[1]) for a, b in zip(qs, qs[1:])):
        raise ValueError(f"Togo DGTCP {os.path.basename(path)}: header {lines[hdr_i]!r} "
                         f"does not end at issue quarter {issue}")
    periods = [f"{y}-Q{q}" for y, q in qs]
    got: dict[str, list[float]] = {}
    for ln in lines[hdr_i + 1:]:
        for lab, comp in _T3_ROWS:
            if comp in got or not ln.startswith(lab):
                continue
            rest = ln[len(lab):]
            if rest and not rest.startswith(" "):
                continue            # e.g. "Créanciers non-" wrapped
            vals = re.findall(_NUM, rest)
            if len(vals) == len(periods):
                got[comp] = [_f(v) for v in vals]
    need = {"Dette brute totale", "Monnaie locale", "Monnaie étrangère"}
    if not need <= set(got):
        raise ValueError(f"Togo DGTCP {os.path.basename(path)}: rows {sorted(got)}")

    for j, p in enumerate(periods):
        cur = got["Monnaie locale"][j] + got["Monnaie étrangère"][j]
        tot = got["Dette brute totale"][j]
        ref = got.get("Par monnaie de dénomination (total)", [cur] * len(periods))[j]
        if abs(cur - ref) > 1.5:
            raise ValueError(f"Togo DGTCP {p}: currency split {cur:.2f} != its total {ref}")
        if "Créanciers non-résidents" in got and "Créanciers résidents" in got:
            res = got["Créanciers résidents"][j] + got["Créanciers non-résidents"][j]
            if abs(res - ref) > 1.5:
                raise ValueError(f"Togo DGTCP {p}: residence split {res:.2f} != {ref}")
        iss = f"{issue[0]}-Q{issue[1]}"
        if (abs(tot - ref) > 1.5) != ((iss, p) in _KNOWN_TOTAL_MISPRINT):
            raise ValueError(f"Togo DGTCP {p}: Dette brute totale {tot} vs currency "
                             f"total {ref} -- pinned misprints changed")
    out = []
    for comp, vals in got.items():
        for p, v in zip(periods, vals):
            out.append({"component": comp, "period": p, "frequency": "quarterly",
                        "measure": "stock", "value": v, "unit": "XOF million",
                        "series_code": _T3_SERIES})
    return out


def _report(path: str) -> list[dict]:
    pages = _pages(path, "Situation de la dette")
    for t in pages:
        m = re.search(r"Tableau\s*\d+\s*:\s*Situation de la dette[^\n]*", t)
        if not m or "...." in m.group(0):
            continue
        lines = t[m.start():].splitlines()
        hdr = lines[1]
        years = re.findall(r"\b(20\d\d)\b|-(\d\d)\b", hdr)
        years = [a or f"20{b}" for a, b in years]
        paired = re.search(r"USD\s+XOF", lines[2]) is not None
        got = {}
        for ln in lines[2:12]:
            for lab in ("Dette Totale", "Dette Extérieure", "Dette Intérieure"):
                if lab in got or not ln.startswith(lab + " "):
                    continue
                vals = re.findall(_NUM, ln[len(lab):])
                if paired:
                    vals = vals[1::2]
                if len(vals) != len(years):
                    raise ValueError(f"Togo DGTCP report {os.path.basename(path)}: "
                                     f"{lab} {vals} vs years {years}")
                got[lab] = [_f(v) for v in vals]
        if len(got) != 3:
            raise ValueError(f"Togo DGTCP report {os.path.basename(path)}: rows {sorted(got)}")
        for j, y in enumerate(years):
            gap = got["Dette Totale"][j] - got["Dette Extérieure"][j] - got["Dette Intérieure"][j]
            if abs(gap) > 0.015:
                raise ValueError(f"Togo DGTCP report {os.path.basename(path)} {y}: "
                                 f"total - (external + domestic) = {gap:.3f}")
        return [{"component": lab, "period": y, "frequency": "annual", "measure": "stock",
                 "value": v, "unit": "FCFA milliards", "series_code": _RA_SERIES}
                for lab, vals in got.items() for y, v in zip(years, vals)]
    raise ValueError(f"Togo DGTCP report {os.path.basename(path)}: summary table not found")


def _order(path: str) -> tuple:
    """Oldest first, so the newest issue's printing wins on overlap."""
    m = re.search(r"(20\d\d)[-_](\d\d)", os.path.basename(path))
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.search(r"(20\d\d)", os.path.basename(path))
    return (int(m.group(1)), 99) if m else (0, 0)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    # The primary is the newest bulletin (discovered, original filename); the
    # extras are named by date (save_as) and sorted. The primary is read last.
    files = sorted(set(extras or []) - {path}, key=_order) + [path]
    rows = []
    for f in files:
        name = os.path.basename(f).lower()
        if "rapport" in name:
            rows += _report(f)
        else:
            rows += _bulletin(f)
    df = pd.DataFrame(rows)
    # Newest issue wins: files were read oldest first.
    df = df.drop_duplicates(["component", "period", "frequency", "unit", "series_code"],
                            keep="last")
    return df.reset_index(drop=True)
