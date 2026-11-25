"""Parser for Mozambique merchandise trade -- Instituto Nacional de Estatística
(INE), Anuário Estatístico, chapter 4.2 "Exportações e Importações" (PDF).

  Quadro 4.2.1 / 4.2.3: value of exports / imports registered by Customs, by
      section of the customs tariff (HS sections 01-21, classification national
      with the printed code), and the total, in 10^3 MT (MZN) and 10^3 USD;
  Quadro 4.2.2 / 4.2.4: value of exports / imports by the 10 principal
      partner countries (and the annual total), same units.
Annual, the Anuário's reference year. The balance-of-payments table (4.2.5,
f.o.b. imports) is not merchandise-trade statistics and is not taken.

The figures are printed with spaces as thousands separators and the two
value columns side by side ("3 163 620 49 501 0,64"), so where one figure
ends is not visible. The split is the one whose US$ figure reproduces the
printed percentage share (to 0.01 point), or -- for a row whose share prints
"-" -- whose MT/US$ ratio equals the total row's (1 %). A row no split
satisfies is dropped.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row


def _groups_ok(toks):
    return bool(toks) and re.fullmatch(r"\d{1,3}", toks[0]) and all(re.fullmatch(r"\d{3}", t) for t in toks[1:])


def _splits(toks):
    for k in range(1, len(toks)):
        a, b = toks[:k], toks[k:]
        if _groups_ok(a) and _groups_ok(b):
            yield float("".join(a)), float("".join(b))


def _parse_one(path: str) -> list[dict]:
    import pdfplumber
    base = os.path.basename(path)
    rows = []
    with pdfplumber.open(path) as pdf:
        lines = []
        for p in pdf.pages:
            lines += (p.extract_text() or "").split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        m = re.match(r"^Quadro\s+4\.2\.([1-4])\s+Valor das (exporta|importa)\w+.*?(\d{4})", ln)
        if not m:
            i += 1
            continue
        q, flow, year = m.group(1), "export" if m.group(2) == "exporta" else "import", m.group(3)
        kind = "section" if q in ("1", "3") else "partner"
        tag = f"{base}: Quadro 4.2.{q}"
        body = []
        k = i + 1
        while k < len(lines) and not lines[k].strip().startswith(("Fonte", "Quadro")):
            body.append(lines[k].strip())
            k += 1
        i = k
        total = None
        parsed = []
        for l in body:
            mm = re.match(r"^(.*?)\s+((?:\d{1,3}(?:\s\d{3})*\s+)\d[\d\s]*?)\s+(\d{1,3},\d{2}|-)$", l)
            if not mm:
                continue
            label, nums, pct = mm.group(1), mm.group(2).split(), mm.group(3)
            parsed.append((label, nums, None if pct == "-" else float(pct.replace(",", "."))))
        # the total row: share 100,00
        for label, nums, pct in parsed:
            if pct == 100.0 and re.search(r"total", label, re.I) and "sub" not in label.lower():
                cands = [(a, b) for a, b in _splits(nums) if 30 < a / b < 200]
                if len(cands) == 1:
                    total = cands[0]
                break
        if not total:
            continue
        ratio = total[0] / total[1]
        for label, nums, pct in parsed:
            if pct is not None:
                cands = [(a, b) for a, b in _splits(nums) if abs(b / total[1] * 100 - pct) <= 0.011]
            else:
                cands = [(a, b) for a, b in _splits(nums) if abs(a / b / ratio - 1) <= 0.01]
            if len(cands) != 1:
                continue
            mt, usd = cands[0]
            lab = label.strip()
            if pct == 100.0 and re.search(r"total", lab, re.I):
                kw = {}
            elif lab.lower().startswith("subtotal"):
                continue
            elif kind == "section":
                mc = re.match(r"^(\d{2})\s+(.+)$", lab)
                if not mc:
                    continue
                kw = dict(commodity=mc.group(2), commodity_classification="national",
                          commodity_code_nso=mc.group(1))
            else:
                mc = re.match(r"^(\d{2})\s+(.+)$", lab)
                if not mc:
                    continue
                kw = dict(partner=mc.group(2), partner_type="country")
            for unit, v in (("MZN", mt), ("USD", usd)):
                rows.append(row(tradeflow=flow, period=year, frequency="annual", value=v, unit=unit,
                                unit_multiplier=1e3, series_code=tag, **kw))
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in sorted(set([path] + [p for p in (extras or []) if p.lower().endswith(".pdf")])):
        rows += _parse_one(p)
    if not rows:
        raise ValueError("mozambique_ine: no rows decoded")
    return pd.DataFrame.from_records(rows).drop_duplicates().reset_index(drop=True)
