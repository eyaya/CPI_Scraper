"""Parser for NBS Nigeria quarterly "Foreign Trade Statistics" PDF reports (2016-2019 layout).

The back issues before the Excel era (nigeria_nbs_trade reads 2020 onward),
retained by the Wayback Machine from nigerianstat.gov.ng/pdfuploads/. The
2016-2019 reports print, in a tables annex with a text layer:

  Table 1 "Summary of Foreign Trade (N'Million)": imports, exports (fob),
          balance, total trade, crude-oil / non-crude-oil / non-oil exports,
          then shares and growth (not read) -- Jan-Dec, quarters, months.
  Table 8 "Summary of Nigeria's Merchandise Trade Value (N'Billion)":
          imports, exports, domestic exports, re-exports, balance. Only the
          domestic exports and re-exports are read (the rest repeats Table 1),
          and only from rows printing all five cells ("-" holds a place): a row
          with a blank cell cannot be aligned from the text and is skipped.
  Tab 2/3 imports (cif) / exports (fob) by HS section, annual + same quarter.
  Tab 6   imports by SITC section (10 sections + total), Jan-Dec, quarters, months.

Rows are read from the text lines; a Table 1 row is kept only when the printed
balance and total agree with its own exports and imports (the identity is a
CHECK on the column alignment -- nothing is computed or filled). Figures
marked "*" (NBS's revised values) are taken as printed. Section / SITC rows
need exactly one number per period column. Across issues the newest wins.
Older layouts (2011-2015) are not read by this module.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from ._common import row, scale_from_text
from ..schema import KEY

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
           "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_QSPAN = {"jan-mar": 1, "apr-jun": 2, "jul-sep": 3, "oct-dec": 4}
_NUM = re.compile(r"^-?\d{1,3}(,\d{3})*(\.\d+)?$|^-?\d+(\.\d+)?$")
_SITC = ["Food & live animals", "Beverages & tobacco", "Crude inedible materials", "Mineral fuel etc.",
         "Oils, fats & waxes", "Chemicals & related products", "Manufactured goods",
         "Machinery & transport equipment", "Miscellaneous manufactured articles", "Commodities n.e.s."]


def _f(tok: str) -> float:
    return float(tok.replace(",", ""))


def _tokens(line: str) -> list[str]:
    return [t for t in re.split(r"[\s*]+", line.strip()) if t]


class _Clock:
    def __init__(self):
        self.year, self.last = None, 0

    def lead(self, toks):
        """Consume the (year, period) prefix of a row; return (period, freq, rest) or None."""
        i, explicit = 0, False
        if toks and re.fullmatch(r"(19|20)\d{2}", toks[0]):
            self.year, self.last, explicit, i = int(toks[0]), 0, True, 1
        if i >= len(toks) or self.year is None:
            return None
        p = toks[i].lower().rstrip(".,")
        rest = toks[i + 1:]
        if p == "jan-dec":
            return str(self.year), "annual", rest
        m = re.fullmatch(r"q([1-4])", p)
        if m:
            return f"{self.year}-Q{m.group(1)}", "quarterly", rest
        if re.fullmatch(r"[a-z]+", p) and p[:3] in _MONTHS:
            mo = _MONTHS[p[:3]]
            if not explicit and mo <= self.last:
                self.year += 1
            self.last = mo
            return f"{self.year}-{mo:02d}", "monthly", rest
        return None


def _pages(pdf, needle):
    for pg in pdf.pages:
        t = pg.extract_text() or ""
        if re.search(needle, t, re.I):
            yield t


def _scale(text, caption_rx):
    m = re.search(caption_rx + r".{0,120}", text, re.I | re.S)
    mult, _ = scale_from_text(m.group(0) if m else "", "NGA")
    return mult


def _table1(pdf, sc):
    out = []
    for t in _pages(pdf, r"Table\s*1\.?\s*Summary of Foreign Trade"):
        mult = _scale(t, r"Summary of Foreign Trade")
        if mult != 1e6:
            continue
        clk = _Clock()
        for line in t.splitlines():
            toks = _tokens(line)
            got = clk.lead(toks)
            if not got:
                continue
            per, freq, rest = got
            nums = [x for x in rest if _NUM.match(x)]
            if len(nums) < 7 or len(nums) != len(rest):
                continue
            imp, exp, bal, tot, crude, ncrude, noil = (_f(x) for x in nums[:7])
            tol = 2.0 + 0.001 * max(abs(exp), abs(imp))
            if abs((exp - imp) - bal) > tol or abs((exp + imp) - tot) > tol:
                continue          # misaligned or misprinted row: not read
            for fl, v, com, basis in (("import", imp, None, ""), ("export", exp, None, "fob"),
                                      ("balance", bal, None, ""), ("total", tot, None, ""),
                                      ("export", crude, "Crude Oil", ""),
                                      ("export", ncrude, "Non-Crude Oil", ""),
                                      ("export", noil, "Non-Oil", "")):
                out.append(row(tradeflow=fl, period=per, frequency=freq, value=v, unit="NGN",
                               unit_multiplier=1e6, commodity=com,
                               commodity_classification="national" if com else "",
                               price_basis=basis, series_code=f"{sc}:Table 1"))
    return out


def _table8(pdf, sc):
    out = []
    for t in _pages(pdf, r"Table\s*8\.?\s*SUMMARY OF NIGERIA"):
        if _scale(t, r"Merchandise Trade Value") != 1e9:
            continue
        clk = _Clock()
        for line in t.splitlines():
            got = clk.lead(_tokens(line))
            if not got:
                continue
            per, freq, rest = got
            if len(rest) != 5 or not all(_NUM.match(x) or x == "-" for x in rest):
                continue
            for fl, tok in (("domestic_export", rest[2]), ("re_export", rest[3])):
                if tok != "-":
                    out.append(row(tradeflow=fl, period=per, frequency=freq, value=_f(tok), unit="NGN",
                                   unit_multiplier=1e9, series_code=f"{sc}:Table 8"))
    return out


def _col_periods(line):
    toks = _tokens(line)
    pers, i = [], 0
    while i < len(toks):
        t = toks[i]
        if re.fullmatch(r"(19|20)\d{2}", t):
            pers.append((t, "annual"))
        elif t.lower() in _QSPAN and i + 1 < len(toks) and re.fullmatch(r"(19|20)\d{2}", toks[i + 1]):
            pers.append((f"{toks[i + 1]}-Q{_QSPAN[t.lower()]}", "quarterly"))
            i += 1
        else:
            return None
        i += 1
    return pers if len(pers) >= 3 else None


def _sections(pdf, sc, needle, flow, basis, tab):
    out = []
    for t in _pages(pdf, needle):
        if _scale(t, needle) != 1e6:
            continue
        lines = t.splitlines()
        pers, seen = None, set()
        for line in lines:
            if pers is None:
                pers = _col_periods(line)
                continue
            if re.search(r"proportion|share|^\s*total\b", line, re.I):
                break
            m = re.match(r"^(\d{1,2})\s+(.*)$", line.strip())
            if not m or not 1 <= int(m.group(1)) <= 22:
                continue
            if m.group(1) in seen:      # the value block has ended (shares follow)
                break
            seen.add(m.group(1))
            toks = _tokens(m.group(2))
            k = len(toks)
            while k > 0 and _NUM.match(toks[k - 1]):
                k -= 1
            nums, label = toks[k:], " ".join(toks[:k])
            if len(nums) != len(pers) or not label:
                continue
            for (p, f), x in zip(pers, nums):
                out.append(row(tradeflow=flow, period=p, frequency=f, value=_f(x), unit="NGN",
                               unit_multiplier=1e6, commodity=label, commodity_classification="national",
                               commodity_code_nso=m.group(1), price_basis=basis,
                               series_code=f"{sc}:{tab}"))
        break                       # the first matching page holds the value block
    return out


def _table6(pdf, sc):
    out = []
    for t in _pages(pdf, r"Summary of\s+Imports by SITC"):
        if _scale(t, r"Imports by SITC") != 1e6:
            continue
        clk = _Clock()
        for line in t.splitlines():
            got = clk.lead(_tokens(line))
            if not got:
                continue
            per, freq, rest = got
            if len(rest) != 11 or not all(_NUM.match(x) for x in rest):
                continue
            for lab, x in zip(_SITC, rest[:10]):
                out.append(row(tradeflow="import", period=per, frequency=freq, value=_f(x), unit="NGN",
                               unit_multiplier=1e6, commodity=lab, commodity_classification="sitc1",
                               series_code=f"{sc}:Table 6"))
    return out


def _issue(path):
    n = os.path.basename(path)
    m = re.search(r"Q([1-4])[ _,]*(\d{4})", n, re.I)
    return (int(m.group(2)), int(m.group(1))) if m else (0, 0)


def parse_pdf(path: str) -> list[dict]:
    y, q = _issue(path)
    sc = f"NBS FTS {y}-Q{q} (PDF)"
    with pdfplumber.open(path) as pdf:
        out = _table1(pdf, sc) + _table8(pdf, sc)
        out += _sections(pdf, sc, r"Quarterly Imports By Section", "import", "cif", "Tab 2")
        out += _sections(pdf, sc, r"Quarterly Exports By Section", "export", "fob", "Tab 3")
        out += _table6(pdf, sc)
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = sorted({path, *(extras or [])}, key=_issue)
    rows = []
    for f in files:
        rows += parse_pdf(f)
    df = pd.DataFrame(rows)
    return df.loc[~df[KEY].astype(str).duplicated(keep="last")].reset_index(drop=True)
