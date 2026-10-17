"""Senegal — Bulletin statistique de la dette publique (Ministère des Finances
et du Budget / Direction de la Dette Publique), quarterly, published on the
Trésor public's site sentresor.org.

HOSTING. sentresor.org answers "Site en maintenance" (HTTP 503) since at least
2026-10-08, so the issues are read from Wayback Machine `id_` captures of the
Treasury's OWN files (original bytes) -- the precedent other indicators use
for an unreachable official host. The descriptor says so.

COVERAGE. The bulletin's Tableau 4 is titled "Dette de l'administration
centrale" -> coverage "Administration centrale". (Its first row is labelled
"Dette publique totale" but is the central-government total: 14 981,8 at end
June 2024, against 16 613,6 for the whole public sector incl. the parapublic
sector, which the bulletin gives only in prose and is not collected.)

WHAT IS READ: Tableau 4 "Dette de l'administration centrale - par type
d'intérêt": Dette publique totale / Dette intérieure / Dette extérieure, and
their fixed/variable split, for the issue's quarter and the previous
year-end. The column header says "M FCFA", but the bulletin's own prose gives
the same total as "14 981,8 milliards de FCFA" -- the values are milliards and
are recorded as such (unit "FCFA milliards"), the header's "M" read as the
abbreviation the prose resolves. The "% total" and "Variation" columns are
derived and not collected.

A NOTE FOR USERS. Senegal's debt figures for 2019-2023 were substantially
revised upward after the 2024-2025 public-finance audit. These are the
figures AS PUBLISHED in each issue at the time; a later revised series is a
different vintage.

CROSS-CHECK (T2 2024 issue): total 14 981,8; intérieure 4 973,4; extérieure
10 008,4 (= 7 610,5 fixed + 2 398,2 variable, to 0,3); end-2023 total 13 854.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_AC = "Administration centrale"
_NUM = re.compile(r"\d{1,3}(?: ?\d{3})*(?:,\d+)?")
_ISSUE = re.compile(r"(\d)\s*(?:ème|er|e)\s*Trimestre\s*(20\d\d)", re.I)
_ROWS = [("Dette publique totale", None), ("Dette intérieure", None),
         ("Taux fixe", "Dette intérieure"),
         ("Taux variable (Bon du trésor < à 1 an)", "Dette intérieure"),
         ("Dette extérieure", None), ("Taux fixe", "Dette extérieure"),
         ("Taux variable", "Dette extérieure")]


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _read_issue(path: str):
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages[:16]]
    issue_m = next((m for t in pages for m in [_ISSUE.search(t)] if m), None)
    if not issue_m:
        raise ValueError(f"DDP SN: cannot date {path}")
    q, year = int(issue_m.group(1)), int(issue_m.group(2))
    text = next(t for t in pages if "Tableau 4. Dette de l'administration centrale" in t
                or "Tableau 4. Dette de l’administration centrale" in t)
    lines = text.splitlines()
    hdr = next(ln for ln in lines if re.match(r"T[1-4]\s+20\d\d\s+20\d\d", ln.strip()))
    hm = re.match(r"T([1-4])\s+(20\d\d)\s+(20\d\d)", hdr.strip())
    if (int(hm.group(1)), int(hm.group(2))) != (q, year):
        raise ValueError(f"DDP SN: Tableau 4 header {hdr!r} vs issue T{q} {year}")
    periods = [f"{year}-Q{q}", hm.group(3)]

    i = lines.index(hdr)
    out, values = [], {}
    j = i + 1
    for label, parent in _ROWS:
        while j < len(lines) and not lines[j].startswith(label):
            j += 1
        if j >= len(lines):
            raise ValueError(f"DDP SN {year}-Q{q}: row {label!r} not found")
        rest = lines[j][len(label):]
        # cols: current value, % total, previous year-end value, variation %.
        # Values carry SPACE thousands ("10 008,4"), so the row is cut at its
        # "%" cells, never split on spaces.
        segs = [x.strip() for x in re.split(r"\s+\S+%", rest.strip()) if x.strip()]
        if not segs or not re.fullmatch(r"\d[\d ]*(?:,\d+)?", segs[0]):
            raise ValueError(f"DDP SN {year}-Q{q}: cannot read {lines[j]!r}")
        cur = _num(segs[0])
        prev = _num(segs[1]) if len(segs) > 1 and re.fullmatch(r"\d[\d ]*(?:,\d+)?", segs[1]) else None
        comp = label if parent is None else f"{parent} — {label}"
        values[comp] = (cur, prev)
        j += 1
    tot, dom, ext = (values[k][0] for k in ("Dette publique totale", "Dette intérieure",
                                             "Dette extérieure"))
    if abs(tot - dom - ext) > 0.2:
        raise ValueError(f"DDP SN {year}-Q{q}: {tot} != {dom} + {ext}")
    for comp, (cur, prev) in values.items():
        for period, v, freq in ((periods[0], cur, "quarterly"), (periods[1], prev, "annual")):
            if v is None:
                continue
            out.append({"coverage": _AC, "component": comp, "period": period,
                        "frequency": freq, "measure": "stock", "value": v,
                        "unit": "FCFA milliards", "series_code": "DDP BSDP T4"})
    return (year, q), out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    # The primary issue must parse; a BACK ISSUE that cannot be read (a
    # truncated Wayback capture -- the Q3/Q4 2023 captures stop at exactly
    # 1 MiB -- or the end-June 2022 issue, whose rate-type rows are worded
    # differently) is skipped with a message, never misread.
    got = [_read_issue(path)]
    for p in extras or []:
        try:
            got.append(_read_issue(p))
        except Exception as e:                                  # noqa: BLE001
            print(f"  [senegal] back issue skipped ({p.replace(chr(92), '/').rsplit('/', 1)[-1]}): {type(e).__name__} {e}")
    issues = sorted(got, key=lambda x: x[0])
    keep: dict[tuple, dict] = {}
    for _issue, rows in issues:               # oldest first: the newest wins
        for r in rows:
            keep[(r["component"], r["period"])] = r
    return pd.DataFrame(list(keep.values()))
