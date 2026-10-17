"""Burkina Faso — Bulletin statistique de la dette publique (Ministère de
l'Economie et des Finances / Direction Générale du Trésor et de la Comptabilité
Publique, Direction de la Dette Publique), quarterly, on finances.gov.bf.

PUBLISHER AND COVERAGE. The bulletin's "Champ de couverture": the debt of the
Administration Centrale, of the State's dependent bodies (sociétés d'Etat,
collectivités territoriales) and the debt guaranteed by the Administration
Centrale. Two perimeters are printed and kept apart, per row:

* "Administration centrale" -- Total de l'encours / Dette extérieure / Dette
  intérieure of Tableaux 1-1 (milliards FCFA) and 1-2 (millions USD), and
  Tableau 2's debt/GDP ratios;
* "Dette publique totale (AC + garanties + dette non garantie)" -- the
  "Encours de la dette publique totale" line of the same tables.

COLUMNS. Each issue prints 2020-2023 year-ends, then "2024 T1", "2024",
"2025 T1" (in the N°2-2025 issue): a year with T<n> is the QUARTER, a bare year
the YEAR-END. Note "2024 T1" sits BEFORE "2024". Dated from Tableau 1-2's
header, which is clean; Tableau 1-1's header carries stray spaces ("2 025 T1")
and must list the same columns.

TRAPS.
* A WATERMARK ("BULLETIN STATISTIQUE DE LA DETTE N.° 3-2022 / PAGE 2", printed
  in orange RGB 0.749/0.561/0) is overlaid on every page and interleaves with
  the figures. Characters in that colour are filtered out before extraction.
* Some cells keep a stray space inside a number ("8 2 01,18"). Every value
  carries exactly two decimals, so a row is split at each ",dd" and the spaces
  inside each chunk are removed; the result must satisfy Total = extérieure +
  intérieure (to 0,02) in every column, or the issue raises.
* Flows (tirages, service, principal, intérêts) are not stocks and are not
  read; nor are the creditor/instrument breakdowns of Tableau 2 (a later layout).

CROSS-CHECK (N°2-2025): AC debt end-March 2025 = 8 201,18 milliards FCFA
(13 496,38 M USD); extérieure 3 342,42; intérieure 4 858,75; end-2024
8 029,60; dette publique totale 8 415,83; debt/GDP (sans arriérés) 60,1 %.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_WATERMARK = (0.749, 0.561, 0.0)
_CHUNK = re.compile(r"([\d ]+,\d{2})")
_AC = "Administration centrale"
_TOTAL = "Dette publique totale (AC + garanties + dette non garantie)"
_ISSUE = re.compile(r"N\.?°\s*(\d)\s*-\s*(20\d\d)")


def _keep(obj) -> bool:
    c = obj.get("non_stroking_color")
    return not (obj.get("object_type") == "char" and c is not None
                and tuple(round(x, 3) for x in c) == _WATERMARK)


def _vals(s: str) -> list[float]:
    return [float(c.replace(" ", "").replace(",", ".")) for c in _CHUNK.findall(s)]


def _periods(header: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r"(20\d\d)(?:\s+T([1-4]))?", header):
        out.append((f"{m.group(1)}-Q{m.group(2)}", "quarterly") if m.group(2)
                   else (m.group(1), "annual"))
    return out


def _read_issue(path: str):
    with pdfplumber.open(path) as pdf:
        pages = [(p.filter(_keep).extract_text() or "") for p in pdf.pages[:12]]
    issue_m = _ISSUE.search(" ".join(pages[:3]))
    issue = (int(issue_m.group(2)), int(issue_m.group(1))) if issue_m else (0, 0)
    # The captions also sit in the list of tables (page 2): require the data.
    t11 = next(t for t in pages if "en milliards FCFA" in t and "Total de l'encours" in t)
    t12 = next(t for t in pages if "en millions de dollars US" in t and "Total de l'encours" in t)
    t2 = next(t for t in pages if "Dette AC SANS arriérés" in t)

    # The header line is the first that is nothing but years and T<n> marks
    # (N°1-2025 starts at 2019 and prints annual columns only).
    hdr = next(ln for ln in t12.splitlines()
               if re.fullmatch(r"(?:20\d\d(?:\s+T[1-4])?\s*)+", ln.strip()))
    periods = _periods(hdr)
    if len(periods) < 5:
        raise ValueError(f"DGTCP BF {issue}: header {hdr!r}")

    rows = []
    for text, unit, code in ((t11, "FCFA milliards", "DGTCP BSD T1-1"),
                             (t12, "USD million", "DGTCP BSD T1-2")):
        lines = text.splitlines()
        i0 = next(i for i, ln in enumerate(lines) if ln.startswith("Total de l'encours"))
        # The USD table wraps each label onto its own line, numbers below.
        def row_after(label, start):
            for j in range(start, len(lines)):
                if lines[j].startswith(label):
                    v = _vals(lines[j][len(label):])
                    if not v and j + 1 < len(lines):
                        v = _vals(lines[j + 1])
                    return v, j
            raise ValueError(f"DGTCP BF {issue} {code}: {label!r} not found")
        tot, j = row_after("Total de l'encours", i0)
        ext, j = row_after("Dette extérieure", j + 1)
        dom, j = row_after("Dette intérieure", j + 1)
        # Earlier issues (N°1-2025) print no whole-public-sector line.
        try:
            pub, _ = row_after("Encours de la dette publique totale", j + 1)
        except ValueError:
            pub = None
        checks = [("Total de l'encours", tot), ("Dette extérieure", ext),
                  ("Dette intérieure", dom)]
        if pub is not None:
            checks.append(("Encours de la dette publique totale", pub))
        for name, v in checks:
            if len(v) != len(periods):
                raise ValueError(f"DGTCP BF {issue} {code}: {name} gives {len(v)} "
                                 f"values for {len(periods)} periods")
        for k in range(len(periods)):
            if abs(tot[k] - ext[k] - dom[k]) > 0.02:
                raise ValueError(f"DGTCP BF {issue} {code}: total {tot[k]} != "
                                 f"{ext[k]} + {dom[k]} in column {k}")
        series = [("Total de l'encours", tot, _AC), ("Dette extérieure", ext, _AC),
                  ("Dette intérieure", dom, _AC)]
        if pub is not None:
            series.append(("Encours de la dette publique totale", pub, _TOTAL))
        for name, v, cov in series:
            for (period, freq), x in zip(periods, v):
                rows.append({"coverage": cov, "component": name, "period": period,
                             "frequency": freq, "measure": "stock", "value": x,
                             "unit": unit, "series_code": code})

    lines = t2.splitlines()
    for label in ("Dette AC SANS arriérés", "Dette AC AVEC arriérés"):
        j = next(i for i, ln in enumerate(lines) if ln.startswith(label))
        pct = [float(x.replace(",", ".")) for x in re.findall(r"\d{1,3},\d", lines[j + 1])]
        if len(pct) != len(periods):
            raise ValueError(f"DGTCP BF {issue}: {label} row {lines[j + 1]!r}")
        comp = f"{label} en pourcentage du PIB"
        for (period, freq), x in zip(periods, pct):
            rows.append({"coverage": _AC, "component": comp, "period": period,
                         "frequency": freq, "measure": "share_of_gdp", "value": x,
                         "unit": "percent", "series_code": "DGTCP BSD T2"})
    return issue, rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    # Issues are ordered by the latest period each one reports (not every
    # cover prints its number in a readable place); the newest wins.
    issues = sorted((_read_issue(p) for p in [path, *(extras or [])]),
                    key=lambda x: max(r["period"] for r in x[1]))
    keep: dict[tuple, dict] = {}
    for _issue, rows in issues:               # oldest first: the newest wins
        for r in rows:
            keep[(r["coverage"], r["component"], r["period"], r["unit"])] = r
    return pd.DataFrame(list(keep.values()))
