"""Parser for Zambia merchandise trade -- Zambia Statistics Agency (ZamStats),
"The Monthly" bulletin, Annex 2 "International Merchandise Trade" (PDF).

Taken from each issue:
  Table 2.8 "Zambia's Trade Flows in Absolute US $ and Zambian Kwacha, 2000 - ...":
      annual total exports, domestic exports, re-exports, imports and trade
      balance, in kwacha (ZMW) and US dollars, unit 1. Only complete years (the
      current year-to-date is not taken); a row is kept only when domestic +
      re-exports = total exports to rounding (a check against misread rows).
  Tables 2.1 / 2.2 / 2.3 / 2.5 / 2.6 (and their a/b $ and K versions):
      monthly and quarterly, current year, million kwacha / million US$ as
      captioned: total exports split into traditional / non-traditional exports
      (national), exports and imports by product category (Raw Materials,
      Intermediate, Consumer, Capital Goods -> bec), exports and imports by
      regional grouping (Asia, COMESA, EU, SADC -> partner groups). The "Total:"
      row is the annual figure when the caption covers January-December.
  Table 10 "Total Exports, Imports and Trade Balance" (K' Billion): monthly and
      quarterly imports, domestic exports, total exports, trade balance.
A table whose caption currency contradicts its twin (the October 2026 issue
captions both Table 2.3a and 2.3b "$' Million") is skipped for the duplicate.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row

_MON = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_NUM = r"-?\d[\d,]*(?:\.\d+)?"
# header phrase -> (kind, value)
_COLS = [("trade balance", ("flow", "balance")), ("domestic exports", ("flow", "domestic_export")),
         ("total exports", ("flow", "export")), ("total imports", ("flow", "import")),
         ("imports", ("flow", "import")), ("nte's", ("national", "Non-Traditional Exports (NTEs)")),
         ("te's", ("national", "Traditional Exports (TEs)")), ("raw materials", ("bec", "Raw Materials")),
         ("intermediate goods", ("bec", "Intermediate Goods")), ("consumer goods", ("bec", "Consumer Goods")),
         ("capital goods", ("bec", "Capital Goods")), ("asia", ("group", "Asia")), ("comesa", ("group", "COMESA")),
         ("eu", ("group", "EU")), ("sadc", ("group", "SADC"))]


def _norm(l: str) -> str:
    """Pre-2020 layout: '8 282.3' (thousands by space), '(1 105.7)' (negative).
    The row label is split off first so that 'Quarter 2 123.4' is not merged."""
    m = re.match(r"^(Quarter\s*\d[®*]?|Total:?|[A-Za-z]{3}[\w\-]*[®*]?)\s+(.*)$", l)
    if not m:
        return l
    tail = re.sub(r"\((\d[\d ,]*(?:\.\d+)?)\)", r"-\1", m.group(2))
    tail = re.sub(r"(?<![\d.])(-?\d{1,3})((?: \d{3})+)(?=\.\d)",
                  lambda x: x.group(1) + x.group(2).replace(" ", ""), tail)
    return m.group(1) + " " + tail


def _header_cols(h: str):
    h = " " + h.lower() + " "
    found, used = [], [False] * len(h)
    for phrase, spec in _COLS:
        for m in re.finditer(r"(?<![a-z'])" + re.escape(phrase) + r"(?![a-z'])", h):
            if any(used[m.start():m.end()]):
                continue
            for k in range(m.start(), m.end()):
                used[k] = True
            found.append((m.start(), spec))
    return [s for _, s in sorted(found)]


def _period(label: str, year: int):
    s = label.lower().replace(" ", "")
    s = re.sub(r"[®*]", "", s)
    m = re.match(r"^([a-z]{3})[a-z]*-?(\d{2})$", s)
    if m and m.group(1) in _MON:
        return f"{2000 + int(m.group(2))}-{_MON.index(m.group(1)) + 1:02d}", "monthly"
    m = re.match(r"^quarter([1-4])$", s)
    if m:
        return f"{year}-Q{m.group(1)}", "quarterly"
    return None, None


def _parse_one(path: str) -> list[dict]:
    import pdfplumber
    base = os.path.basename(path)
    rows = []
    with pdfplumber.open(path) as pdf:
        lines = []
        for p in pdf.pages:
            lines += (p.extract_text() or "").split("\n")
    seen_caps = {}
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        m = re.match(r"^Table\s*(2\.(?:1|2|3|5|6)|10)([ab]?)\s*:\s*(.*)$", ln)
        if not m and re.match(r"^Total Exports\s*\(FOB\)\s*and Imports\s*\(CIF\)", ln):
            # pre-2020 issues print the same monthly table untitled
            m = re.match(r"^Table\s*(10)()\s*:\s*(.*)$", "Table 10: " + ln)
        if m and re.search(r"(K|\$)\s*['’]\s*(Million|Billion)", ln):
            tno, cap = m.group(1), ln
            cur = "USD" if "$" in cap else "ZMW"
            mult = 1e9 if re.search(r"Billion", cap) else 1e6
            years = re.findall(r"(20\d{2})", cap)
            year = int(years[-1]) if years else None
            fullyear = bool(re.search(r"Jan[a-z.]*\s*\d{0,4}\s*[-–]\s*Dec", cap))
            tag = f"{base}: Table {tno}{m.group(2)}"
            if (tno, cur) in seen_caps or year is None:
                i += 1
                continue                    # duplicate caption (2.3b mislabelled "$")
            seen_caps[(tno, cur)] = True
            # header line
            j = i + 1
            while j < len(lines) and not re.match(r"^(Months?|Period|PERIOD)\b", lines[j].strip()):
                j += 1
                if j - i > 3:
                    break
            if j >= len(lines) or j - i > 3:
                i += 1
                continue
            cols = _header_cols(lines[j].strip())
            k = j + 1
            pending_label = None
            while k < len(lines):
                l = _norm(lines[k].strip())
                if l.startswith(("Source", "Table", "Note")):
                    break
                mm = re.match(r"^(.*?[A-Za-z®*:0-9])\s+((?:" + _NUM + r"\s+)*" + _NUM + r")$", l)
                label, nums = (mm.group(1), mm.group(2).split()) if mm else (None, None)
                if mm is None and re.match(r"^[A-Za-z]{3}[\w\s\-®*]*$", l):
                    pending_label = l                    # "Jul-26®" alone, numbers on next line
                    k += 1
                    continue
                if pending_label and re.match(r"^(" + _NUM + r"\s+)*" + _NUM + r"$", l):
                    label, nums = pending_label, l.split()
                pending_label = None
                k += 1
                if not label or len(nums) != len(cols):
                    continue
                if label.lower().startswith("total"):
                    if not fullyear:
                        continue
                    per, freq = str(year), "annual"
                else:
                    per, freq = _period(label, year)
                if per is None:
                    continue
                for (kind, val), tok in zip(cols, nums):
                    v = float(tok.replace(",", ""))
                    flow = val if kind == "flow" else ("import" if tno in ("2.5", "2.6") else "export")
                    if v < 0 and flow != "balance":
                        continue
                    kw = {}
                    if kind in ("national", "bec"):
                        kw = dict(commodity=val, commodity_classification=kind)
                    elif kind == "group":
                        kw = dict(partner=val, partner_type="group")
                    rows.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit=cur,
                                    unit_multiplier=mult, trade_system="general", series_code=tag, **kw))
            i = k
            continue
        if re.match(r"^Table\s*2\.8\s*:", ln) and "Trade Flows" in ln:
            rows += _table28(lines[i + 1:], base)
        i += 1
    return rows


def _table28(lines, base) -> list[dict]:
    rows, pending, year, last = [], [], None, None
    tag = f"{base}: Table 2.8"
    for l in lines:
        l = l.strip()
        if l.startswith(("Source", "Table")):
            break
        m = re.match(r"^(ZMW|US\s*\$)\s+((?:" + _NUM + r"\s+){4}" + _NUM + r")$", l)
        y = re.match(r"^(20\d{2}|19\d{2})(\s*\(?[A-Za-z].*)?$", l)
        if y:
            year = int(y.group(1))
            ytd = bool(y.group(2))
            for cur, nums in pending:
                rows += _t28_row(cur, nums, year, ytd, tag)
            pending = []
            last = (year, ytd)
            continue
        if m:
            cur = "ZMW" if m.group(1) == "ZMW" else "USD"
            nums = [float(x.replace(",", "")) for x in m.group(2).split()]
            if cur == "ZMW":          # printed above its year label; US $ below it
                pending.append((cur, nums))
            elif last:
                rows += _t28_row(cur, nums, last[0], last[1], tag)
    return rows


def _t28_row(cur, nums, year, ytd, tag):
    tot, dom, rex, imp, bal = nums
    if ytd or abs(dom + rex - tot) > 2 + 1e-6 * tot:
        return []
    out = []
    for flow, v in (("export", tot), ("domestic_export", dom), ("re_export", rex), ("import", imp),
                    ("balance", bal)):
        if v < 0 and flow != "balance":
            continue
        out.append(row(tradeflow=flow, period=str(year), frequency="annual", value=v, unit=cur,
                       unit_multiplier=1, trade_system="general", series_code=tag))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    def vol(p):
        m = re.search(r"Vol[-_ ]?(\d+)", os.path.basename(p))
        return int(m.group(1)) if m else 0
    paths = sorted(set([path] + [p for p in (extras or []) if p.lower().endswith(".pdf")]), key=vol)
    rows = []
    for p in paths:
        rows += _parse_one(p)
    if not rows:
        raise ValueError("zambia_zamstats: no rows decoded")
    df = pd.DataFrame.from_records(rows)
    key = ["tradeflow", "commodity", "partner", "frequency", "period", "unit"]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
