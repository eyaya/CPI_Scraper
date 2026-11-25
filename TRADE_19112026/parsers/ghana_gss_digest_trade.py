"""Parser for GSS (Ghana Statistical Service) "Digest of External Trade Statistics" PDFs.

The pre-StatsBank years (the StatsBank descriptor ghana.yaml starts in 2021).
GSS's digest prints five-year annual tables in GH¢ million (a Wayback copy of
statsghana.gov.gh/docfiles/Econs_Stats/2016/Digest of trade.pdf, 2011-2015):

  Table 1  imports (CIF), exports (FOB), balance of trade (exports minus
           imports; a deficit printed in parentheses is read as negative).
  Table 2/3  imports / exports by HS section (GSS's own section labels; no
           codes printed -> classification "national", code blank).
  Table 6/7  imports from / exports to major trading partners (countries).
  Table 9/10 imports from / exports to ECOWAS countries.
  Table 11/12 imports from / exports to world economic blocs (groups); the
           "World Trade" line repeats Table 1 and is not read.
Not read: selected items (Tables 4/5) and non-traditional exports (Table 8,
a different product coverage and year span).

The text layer splits numbers after their first digit ("8 86.2 1 ,014.2"),
so a row's figures are recovered by their one-decimal ending (each printed
figure ends ".d"); a row must yield exactly one figure per year column. A
label wrapped over two lines around its figures is re-joined.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from ._common import row

_FIG = re.compile(r"\(?-?\d[\d ,]*\.\d{1,2}\)?")
_TABLES = {"1": None, "2": ("import", "product"), "3": ("export", "product"),
           "6": ("import", "partner"), "7": ("export", "partner"), "9": ("import", "partner"),
           "10": ("export", "partner"), "11": ("import", "group"), "12": ("export", "group")}


def _val(tok):
    neg = tok.startswith("(") and tok.endswith(")")
    v = float(re.sub(r"[ ,()]", "", tok))
    return -v if neg else v


def _split(line):
    m = re.search(r"\(?\d", line)
    if not m:
        return line.strip(), []
    lab, tail = line[:m.start()].strip(), line[m.start():]
    figs = _FIG.findall(tail)
    rest = _FIG.sub("", tail).strip()
    if rest and not re.fullmatch(r"[\s\d]*", rest):
        return line.strip(), []           # text after the figures: not a data row
    return lab, figs


def _blocks(pdf):
    """(table number, years, lines) for each table on the pages."""
    lines = []
    for pg in pdf.pages:
        lines += (pg.extract_text() or "").splitlines()
    out, cur = [], None
    for l in lines:
        m = re.match(r"^\s*Table\s+(\d+)\s*:\s*(.*)$", l)
        if m:
            cur = [m.group(1), None, [], m.group(2)]
            out.append(cur)
            continue
        if cur is None:
            continue
        ys = re.findall(r"\b(20\d{2}|19\d{2})\b", l)
        if cur[1] is None and len(ys) >= 3 and re.fullmatch(r"[A-Za-z ]*((19|20)\d{2}\s*)+", l.strip()):
            cur[1] = ys
            continue
        cur[2].append(l)
    return out


def parse(path, extras=None):
    rows = []
    for f in [path, *(extras or [])]:
        sc = os.path.basename(f)
        with pdfplumber.open(f) as pdf:
            blocks = _blocks(pdf)
        for tno, years, lines, title in blocks:
            if tno not in _TABLES or (not years and tno != "1"):
                continue
            if "million" not in " ".join(lines[:3]).lower() and "million" not in title.lower():
                continue
            spec = _TABLES[tno]
            pending = ""
            parsed = []
            for i, l in enumerate(lines):
                if re.match(r"^\s*(S\s*o\s*u\s*r\s*c\s*e|Source|\d+\s+Exports minus)", l):
                    break
                lab, figs = _split(l)
                if not figs:
                    if lab and not re.fullmatch(r"[\d\s]+", lab):
                        pending = lab
                    continue
                if not lab:              # label wrapped around the figures
                    nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    lab = (pending + " " + (nxt if not _FIG.search(nxt) else "")).strip()
                pending = ""
                if years is None or len(figs) != len(years):
                    continue
                parsed.append((lab, [_val(x) for x in figs]))
            for lab, vals in parsed:
                low = lab.lower()
                if spec is None:
                    if re.fullmatch(r"(19|20)\d{2}", lab) is None and not re.match(r"^(19|20)\d{2}", lab):
                        pass
                    continue
                if not lab or low.startswith(("total", "world trade", "others", "section")):
                    continue
                fl, kind = spec
                key = (dict(commodity=lab, commodity_classification="national") if kind == "product"
                       else dict(partner=lab, partner_type="group" if kind == "group" else "country"))
                for y, v in zip(years, vals):
                    rows.append(row(tradeflow=fl, period=y, frequency="annual", value=v, unit="GHS",
                                    unit_multiplier=1e6, series_code=f"{sc}:Table {tno}", **key))
            if spec is None:          # Table 1: rows are years, columns imports / exports / balance
                for l in lines:
                    m = re.match(r"^\s*((?:19|20)\d{2})\s+(.*)$", l)
                    if not m:
                        continue
                    figs = _FIG.findall(m.group(2))
                    if len(figs) != 3:
                        continue
                    for fl, x, pb in zip(("import", "export", "balance"), figs, ("cif", "fob", "")):
                        rows.append(row(tradeflow=fl, period=m.group(1), frequency="annual", value=_val(x),
                                        unit="GHS", unit_multiplier=1e6, price_basis=pb,
                                        series_code=f"{sc}:Table 1"))
    return pd.DataFrame(rows)
