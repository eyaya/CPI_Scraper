"""Parser for GBoS (The Gambia) "International Merchandise Trade Statistics" reports (PDF).

GBoS compiles merchandise trade from GRA-Customs ASYCUDA World records and
posts an annual report (2015-2020, 2022, 2024) and quarterly reports
(2019 Q1 - 2025 Q1) on gbosdata.org/downloads (IMTS <year> folders). All
values GMD thousand ("GMD ('000)"); net weight in tons. Three layouts, read
from the text layer by table title:

  * Trade summary tables -- "Trade summary ..." (one column, several years
    "YEARS 2015 ... 2019", or "2016 % 2017 %") and, from 2023, "Quarterly /
    Annual Trade Summary" over five quarters / two years: imports, domestic
    exports ("EXPORTS" in the 2015-2017 tables, beside RE-EXPORTS and TOTAL
    EXPORTS), re-exports, total exports, total trade, balance. A single-column
    summary is the report's own period (from the file name).
  * Monthly trade statistics -- "MONTHS IMPORTS EXPORTS RE-EXPORTS TOTAL
    EXPORTS" (2015-2017: EXPORTS = domestic exports) or "MONTHS IMPORTS %
    EXPORTS %" (2018-2022; EXPORTS = domestic exports: the 2019 annual
    report's monthly TOTAL, 451,891, is its Table 8 domestic exports). The TOTAL row is the
    report's period. Shares (%) are not read.
  * Imports / exports by continent and economic zone ("PARTNER IMPORTS %
    EXPORTS %", 2015-2022, the report's period) and, from 2023, the annexes
    "Imports by Continent", "Imports by Regional Economic Communities" (value
    and net weight) and "Imports by SITC SECTION" (value and net weight) over
    the summary's five quarters / two years.
Not read: top-ten partner and product tables (partial lists), selected basic
commodities, HS6 tables, export shares, "excluding oil" and SITC3 annexes.
Rows must print one number per period column; a row that does not is skipped.
Across reports the newest wins for a key; within a report, repeats are left
to the validator.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from ._common import row
from ..schema import KEY

_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
           "october", "november", "december"]
_ORD = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "first": 1, "second": 2, "third": 3, "fourth": 4}
_NUM = re.compile(r"^-?\d{1,3}(,\d{3})+$|^-?\d+(\.\d+)?$")
_SITC = ["Food and Live Animals", "Beverages and Tobacco", "Crude Materials, Inedible, Except Fuels",
         "Mineral Fuels, Lubricants and Related Materials", "Animal And Vegetable Oils, Fats and Waxes",
         "Chemicals and Related Products, N.E.S.", "Manufactured Goods Classified Chiefly by Material",
         "Machinery and Transport Equipment", "Miscellaneous Manufactured Articles",
         "Commodities and Transactions not Classified Elsewhere"]
_FLOWS = (("TOTAL EXPORTS", "export"), ("DOMESTIC EXPORTS", "domestic_export"), ("RE-EXPORTS", "re_export"),
          ("TOTAL TRADE", "total"), ("TRADE BALANCE", "balance"), ("BALANCE", "balance"),
          ("IMPORTS", "import"), ("EXPORTS", "domestic_export"))


def _f(t):
    return float(t.replace(",", ""))


def _report(path):
    """(period, frequency, sort key) of the report from its file name."""
    n = os.path.basename(path)
    y = int(re.search(r"(20\d{2})", n).group(1))
    m = re.search(r"Quarter\s*([1-4])", n, re.I)
    if m:
        return f"{y}-Q{m.group(1)}", "quarterly", (y, int(m.group(1)), 0)
    return str(y), "annual", (y, 4, 1)


def _strip_noise(line):
    return re.sub(r"\s*(Formatted|Commented)\b.*$", "", line).strip()


def _split_tail(line):
    toks = line.split()
    k = len(toks)
    while k > 0 and _NUM.match(toks[k - 1]):
        k -= 1
    return " ".join(toks[:k]), toks[k:]


def _header_periods(text_lines):
    """Periods named in a header (years or 'nth QTR yyyy'), in order."""
    s = " ".join(text_lines)
    qs = re.findall(r"(1st|2nd|3rd|4th)\s*QTR\s*(\d{4})", s, re.I)
    if qs:
        return [(f"{y}-Q{_ORD[o.lower()]}", "quarterly") for o, y in qs]
    return [(y, "annual") for y in re.findall(r"\b(20\d{2})\b", s)]


def _split_qtr_header(lines):
    """Quarter header printed over two lines ('4th QTR 1st QTR ...' / '2023 2024 ...')."""
    for i, l in enumerate(lines[:-1]):
        ords = re.findall(r"(1st|2nd|3rd|4th)\s*QTR", l, re.I)
        if len(ords) >= 2 and not re.search(r"\d{4}", l):
            for j in (i + 1, i + 2):
                if j < len(lines):
                    ys = re.findall(r"\b(20\d{2})\b", lines[j])
                    if len(ys) == len(ords):
                        return [(f"{y}-Q{_ORD[o.lower()]}", "quarterly") for o, y in zip(ords, ys)]
    return None


def _flow(label):
    lab = label.upper().strip()
    for k, fl in _FLOWS:
        if lab == k:
            return fl
    return None


def _summary(lines, rep, sc, tab):
    """A trade-summary block (lines after its title)."""
    out, pers, pct = [], None, False
    for line in lines[:14]:
        line = _strip_noise(line)
        if pers is None and re.match(r"^(YEARS|TRADEFLOW)", line, re.I):
            p = _header_periods([line])
            pct = "%" in line
            if p:
                pers = p
            elif re.match(r"^TRADEFLOW\s+VALUES", line, re.I) or re.match(r"^TRADEFLOW\s*$", line, re.I):
                pers = pers or [(rep[0], rep[1])]
            continue
        lab, nums = _split_tail(line)
        fl = _flow(lab)
        if not fl or not nums:
            continue
        if pers is None:
            pers = [(rep[0], rep[1])]
        if pct and len(nums) == 2 * len(pers):
            nums = nums[0::2]
        elif len(pers) == 1 and len(nums) == 2:      # value + share
            nums = nums[:1]
        if len(nums) != len(pers):
            continue
        for (p, f), x in zip(pers, nums):
            out.append(row(tradeflow=fl, period=p, frequency=f, value=_f(x), unit="GMD",
                           unit_multiplier=1e3, series_code=f"{sc}:{tab}"))
    # A balance printed without its minus sign (2021 Q4: "TRADE BALANCE
    # 10,774,975" beside imports 10,986,777 and total exports 211,802) is not
    # read: the sign is checked against the table's own flows, never repaired.
    by = {}
    for r in out:
        by.setdefault(r["period"], {})[r["tradeflow"]] = r["value"]
    keep = []
    for r in out:
        if r["tradeflow"] == "balance":
            f = by[r["period"]]
            ex = f.get("export", f.get("domestic_export"))
            if ex is not None and "import" in f and (ex - f["import"]) * r["value"] < 0:
                continue
        keep.append(r)
    return keep


def _monthly(lines, rep, sc, tab):
    out, cols = [], None
    year = rep[0][:4]
    for line in lines[:22]:
        line = _strip_noise(line)
        u = line.upper()
        if cols is None and re.match(r"^MONTHS?\b", u):
            if "%" in u:
                cols = ["import", None, "domestic_export", None]
            else:
                hdr = u.replace("TOTAL EXPORTS", "TOTAL_EXPORTS").split()[1:]
                m = {"IMPORTS": "import", "EXPORTS": "domestic_export", "RE-EXPORTS": "re_export",
                     "TOTAL_EXPORTS": "export"}
                if not all(h in m for h in hdr):
                    return out
                cols = [m[h] for h in hdr]
            continue
        if cols is None:
            continue
        lab, nums = _split_tail(line)
        lab = lab.lower()
        if lab in _MONTHS:
            per, freq = f"{year}-{_MONTHS.index(lab) + 1:02d}", "monthly"
        elif lab.startswith("total"):
            per, freq = rep[0], rep[1]
        else:
            continue
        if len(nums) != len(cols):
            continue
        for fl, x in zip(cols, nums):
            if fl:
                out.append(row(tradeflow=fl, period=per, frequency=freq, value=_f(x), unit="GMD",
                               unit_multiplier=1e3, series_code=f"{sc}:{tab}"))
        if freq != "monthly":
            break
    return out


def _zones(lines, rep, sc, tab):
    """2015-2022 'PARTNER IMPORTS % EXPORTS %' for the report's period."""
    out, ok = [], False
    for line in lines[:30]:
        line = _strip_noise(line)
        if re.match(r"^PARTNER\s+IMPORTS\s+%\s+EXPORTS\s+%", line, re.I):
            ok = True
            continue
        if not ok:
            continue
        lab, nums = _split_tail(line)
        if re.match(r"^(SUB\s*TO\w*|GROUPING)$", lab, re.I):
            continue
        if not lab or lab.upper().startswith(("TOTAL", "SOURCE")):
            if lab.upper().startswith("TOTAL"):
                break
            continue
        if len(nums) != 4:
            continue
        for fl, x in (("import", nums[0]), ("export", nums[2])):
            out.append(row(tradeflow=fl, period=rep[0], frequency=rep[1], value=_f(x), unit="GMD",
                           unit_multiplier=1e3, partner=lab, partner_type="group", series_code=f"{sc}:{tab}"))
    return out


def _annex(lines, pers, sc, tab, weight, kind):
    """2023+ annex block over `pers`: continents / RECs (groups) or SITC sections."""
    out, pending = [], ""
    meas, unit, mult = ("net_weight", "tonnes", 1) if weight else ("value", "GMD", 1e3)
    for line in lines[:24]:
        line = _strip_noise(line)
        if re.match(r"^(Annex|Table)\s*\d", line):
            break
        lab, nums = _split_tail(line)
        if re.match(r"^(PARTNER|SITC)\b", lab, re.I) or re.search(r"QTR|^\d{4}", line):
            continue
        if len(nums) != len(pers):
            if lab and not nums:
                pending = (pending + " " + lab).strip()
            continue
        if kind == "sitc":
            full = (pending + " " + lab).strip()
            name = next((s for s in _SITC if s.lower() == full.lower()), None)
            if name is None and not lab:        # numbers printed between two halves of a label
                pending = pending + " |"
                continue
            pending = ""
            if name is None:
                continue
            key = dict(commodity=name, commodity_classification="sitc1")
        else:
            pending = ""
            if not lab or lab.upper() in ("TOTAL", "VALUES", "NET WEIGHT") or re.match(r"^(SUB\s*TO\w*|GROUPING)$", lab, re.I):
                continue
            key = dict(partner=lab, partner_type="group")
        for (p, f), x in zip(pers, nums):
            out.append(row(tradeflow="import", period=p, frequency=f, value=_f(x), unit=unit,
                           unit_multiplier=mult, measure=meas, series_code=f"{sc}:{tab}", **key))
    return out


def parse_file(path):
    rep = _report(path)
    sc = os.path.splitext(os.path.basename(path))[0].strip()
    out = []
    with pdfplumber.open(path) as pdf:
        lines = []
        for pg in pdf.pages:
            lines += (pg.extract_text() or "").splitlines()
    summary_pers = None
    for i, l in enumerate(lines):
        s = _strip_noise(l)
        tm = re.match(r"^(Table|Annex)\s*(\d+[A-Z]?)\s*:\s*(.*)$", s, re.I)
        if not tm or re.search(r"\.{5,}", s):           # skip the list of tables
            continue
        tab, title = f"{tm.group(1).title()} {tm.group(2)}", tm.group(3)
        body = lines[i + 1:i + 40]
        tl = title.lower()
        if "trade summary" in tl:
            got = _summary(body, rep, sc, tab)
            out += got
            hp = _header_periods([_strip_noise(x) for x in body[:3] if re.match(r"^(YEARS|TRADEFLOW)", x, re.I)])
            if hp and len(hp) > 1:
                summary_pers = hp
        elif "monthly trade statistics" in tl:
            out += _monthly(body, rep, sc, tab)
        elif "continents" in tl and "imports and exports" in tl or "impots and exports" in tl:
            out += _zones(body, rep, sc, tab)
        elif re.search(r"imports by (continent|regional economic|sitc section)", tl):
            pers = _header_periods([title]) if "for 20" in tl and "quarter" not in tl else None
            hdr = [x for x in body[:4]]
            pers = (_split_qtr_header(hdr) or
                    (_header_periods([x for x in hdr if re.search(r"QTR", x)]) or None) or pers or summary_pers)
            if not pers:
                continue
            kind = "sitc" if "sitc" in tl else "group"
            out += _annex(body, pers, sc, tab, "net-weight" in tl or "net weight" in tl, kind)
    return out


def parse(path, extras=None):
    files = sorted({path, *(extras or [])}, key=lambda f: _report(f)[2], reverse=True)
    frames, seen = [], set()
    for f in files:
        df = pd.DataFrame(parse_file(f))
        if df.empty:
            continue
        k = df[KEY].astype(str).agg("|".join, axis=1)
        frames.append(df.loc[~k.isin(seen)])
        seen |= set(k)
    return pd.concat(frames, ignore_index=True)
