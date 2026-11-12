"""Botswana -- Statistics Botswana "Producer Price Index (Mining and Utilities)", 2017=100.

One PDF per release (quarterly since Q2 2019; some releases cover two to four
quarters). Every edition is read (`extras` = the older ones), OLDEST FIRST, and
for each quarter the NEWEST edition's value is kept: Statistics Botswana
revises heavily (Mining 2019-Q2 is 99.2 in the Q2 2019 release, 84.5 from the
2020 release on), and the merge key has no edition, so only the latest
vintage can be stored.

Headline tables (one Mining, one Utilities per edition):
    Year Quarter PPI Index | Quarter on Quarter | Year on Year
    2018 Quarter 1 88.1 (11.9) -          <- older editions: year inline
    Quarter 1 72.2 (9.1) (2.8) / 2021 / Quarter 3 ...   <- 2026: year centred
  Negatives are in parentheses; the 2019 editions use a decimal comma. The
  quarters are consecutive, so the year of every row follows from ONE start
  year: the parser takes the only start year consistent with every printed
  year (inline = that row's; a year on its own line = the row above or below)
  and fails if none or several fit. The "2017 Base Period 100.0" row is the
  annual base, not a quarter, and is skipped.

Component tables ("Mining Producer Price Index for Quarter n, yyyy", and from
2026 the Utilities one): group code, group, weight, previous-quarter index,
current-quarter index, % change on the previous quarter. The column headers
misname the quarters in places (Table 2.4 of 2020 heads Q4 "2nd / 3rd
Quarter"; 2026 heads Q1 2026 "1th Quarter 2025"), so the quarters come from
the CAPTION (or, where the caption names none, the edition's latest quarter)
and the previous column is the quarter before. A component table is read only
when ALL its groups parse (7 mining, 10 utilities rows); several editions'
text layers break rows apart, and those tables are skipped rather than read
in part. Weights (reference year 2017, per the technical notes) are filed as
period 2017.

Not read: the 2019 technical-note weight table ("Mineral Products and their
Weights"), which assigns 0.93 to Gold and 1.94 to Coal where every component
table since prints Coal 0.93 and Soda Ash 1.94.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from . import _common as C

_MINING = "Mining Producer Price Index"
_UTIL = "Utilities Producer Price Index (Water and Electricity)"
_BASE = "2017=100"
_QROW = re.compile(r"^\s*(?:((?:19|20)\d\d)\s+)?Quarter\s+([1-4])\s+((?:\S+\s*){1,3})$", re.I)
_YEAR = re.compile(r"^\s*((?:19|20)\d\d)\s*$")
_NUMTOK = re.compile(r"^(?:\(?-?\d+(?:[.,]\d+)?\)?|-)$")
_WORDQ = {"one": 1, "two": 2, "three": 3, "four": 4, "1": 1, "2": 2, "3": 3, "4": 4}


def _num(tok: str):
    return C.to_number(tok, decimal="," if re.search(r"\d,\d", tok) else ".", negative_parens=True)


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [l for pg in pdf.pages for l in (pg.extract_text() or "").splitlines()]


def _years(rows: list[tuple], tokens: list[tuple]) -> list[int]:
    """rows: (quarter, inline_year|None, position); tokens: standalone (year, position).
    Return each row's year from the one consistent start year."""
    fits = []
    for y0 in range(1995, 2040):
        ys, y, prevq = [], y0, None
        for q, _, _ in rows:
            if prevq is not None and q != prevq % 4 + 1:
                return []                                   # not consecutive
            if prevq is not None and q == 1:
                y += 1
            ys.append(y)
            prevq = q
        ok = all(iy is None or int(iy) == yy for (_, iy, _), yy in zip(rows, ys))
        for ty, tpos in tokens:
            near = [yy for (_, _, pos), yy in zip(rows, ys) if abs(pos - tpos) == 1]
            ok = ok and int(ty) in near
        if ok and (any(iy for _, iy, _ in rows) or tokens):
            fits.append(ys)
    if len(fits) != 1:
        raise ValueError(f"{len(fits)} start years fit the printed years")
    return fits[0]


def _headline(lines: list[str]):
    """Yield (index_name, [(period, index, qoq, yoy)]) for each headline table."""
    caption, run, toks, out = "", [], [], []

    def flush():
        if run:
            ys = _years([(q, iy, pos) for q, iy, pos, _ in run], toks)
            name = _UTIL if re.search(r"utilit", caption, re.I) else _MINING
            out.append((name, [(f"{y}-Q{q}", vals) for (q, _, _, vals), y in zip(run, ys)]))
        run.clear()
        toks.clear()

    for i, l in enumerate(lines):
        if re.match(r"\s*table\s*\d", l, re.I):
            flush()
            caption = l
            continue
        m = _QROW.match(l)
        if m and all(_NUMTOK.match(t) for t in m.group(3).split()):
            run.append((int(m.group(2)), m.group(1), i, m.group(3).split()))
            continue
        if _YEAR.match(l) and run:
            toks.append((_YEAR.match(l).group(1), i))
            continue
        if run and not re.match(r"\s*(?:20\d\d\s+)?(?:base period|jan)", l, re.I):
            flush()
    flush()
    return out


def _components(lines: list[str], last: str):
    out = []
    for i, l in enumerate(lines):
        m = re.match(r"\s*table\s*(?:2(?:\.\d)?|4)\b(.*)$", l, re.I)
        if not m or re.search(r"\.{5}|…", l) or not re.search(r"producer price", l, re.I):
            continue
        cap = m.group(1)
        qm = re.search(r"quarter\s+(one|two|three|four|[1-4])(?:\s*\(\d\))?\s*(?:,|of)?\s*((?:19|20)\d\d)", cap, re.I)
        cur = f"{qm.group(2)}-Q{_WORDQ[qm.group(1).lower()]}" if qm else last
        y, q = int(cur[:4]), int(cur[-1])
        prev = f"{y - (q == 1)}-Q{(q - 2) % 4 + 1}"
        util = bool(re.search(r"utilit", cap, re.I))
        need = 10 if util else 7
        rows = []
        for l2 in lines[i + 1:i + 25]:
            r = re.match(r"^\s*(\d(?:\.\d)?)\s+([A-Za-z][A-Za-z &']*?)(?:\s+Index)?\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$", l2)
            if r and all(_NUMTOK.match(t) for t in r.groups()[2:]):
                rows.append(r.groups())
            if len(rows) == need or re.match(r"\s*table\s*\d", l2, re.I):
                break
        codes = [r[0] for r in rows]
        want = (["0", "1.0", "1.1", "1.2", "1.3", "1.4", "2.0", "2.1", "2.2", "2.3"] if util
                else ["1", "1.0", "2.0", "3.0", "4.0", "5.0", "6.0"])
        if codes != want:
            continue                                    # a broken text layer: skip the table
        parent = {}
        for code, label, w, pv, cv, chg in rows:
            label = label.strip()
            if code in ("0", "1") and (util or code == "1"):
                industry = "Utilities (water and electricity)" if util else "Mining"
            elif util and not code.endswith(".0"):
                industry = f"{parent[code[0]]}: {label}"
            else:
                industry = label
            if code.endswith(".0"):
                parent[code[0]] = label
            out.append((_UTIL if util else _MINING, industry, code, prev, cur, w, pv, cv, chg))
    return out


def _edition_rows(path: str) -> dict:
    lines = _lines(path)
    rows = {}
    heads = _headline(lines)
    if not any(n == _MINING for n, _ in heads):
        raise ValueError(f"{os.path.basename(path)}: no Mining headline table")
    last = max(p for n, s in heads for p, _ in s)

    def put(name, industry, code, period, measure, v, freq="quarterly", unit=None):
        if v is None:
            return
        r = C.row(index_name=name, industry=industry, industry_code_nso=code, period=period,
                  frequency=freq, measure=measure, value=v, base_period=_BASE, unit=unit)
        rows[(name, industry, period, measure)] = r

    for name, series in heads:
        industry = "Mining" if name == _MINING else "Utilities (water and electricity)"
        code = "1" if name == _MINING else "0"
        for period, vals in series:
            vals = vals + ["-"] * (3 - len(vals))
            put(name, industry, code, period, "index", _num(vals[0]))
            put(name, industry, code, period, "inflation_qoq", _num(vals[1]))
            put(name, industry, code, period, "inflation_yoy", _num(vals[2]))
    for name, industry, code, prev, cur, w, pv, cv, chg in _components(lines, last):
        put(name, industry, code, prev, "index", _num(pv))
        put(name, industry, code, cur, "index", _num(cv))
        put(name, industry, code, cur, "inflation_qoq", _num(chg))
        put(name, industry, code, "2017", "weight", _num(w), freq="annual", unit="percent")
    return rows, last


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    editions = []
    for p in [path] + list(extras or []):
        rows, last = _edition_rows(p)
        editions.append((last, p, rows))
    editions.sort(key=lambda e: e[0])                 # oldest first: newest wins
    merged = {}
    for _, _, rows in editions:
        merged.update(rows)
    # Weights: rounding differs by edition (94.67 vs 94.7); the newest is kept.
    return pd.DataFrame(list(merged.values()))
