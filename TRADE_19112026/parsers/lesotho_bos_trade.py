"""Parser for Lesotho merchandise trade -- Bureau of Statistics (BOS),
"Quarterly Foreign Trade Statistics Report" (PDF, 2021 Q1 onward, from
bos.gov.ls/BoS_reports/Copy of Economics/Foreign_Trade_Statistics_Report_<y>_Q<q>.pdf).

Taken from each report:
  * the monthly "Trade volume" table (recent issues): total exports (FOB),
    total imports (CIF), trade balance (signed, "-M1,387.1") and net trade
    volume (exports + imports, flow "total"), in million maloti;
  * Tables "Distribution of Imports ... by SITC Categories" / "Value of Exports
    ... by SITCs": the three months of the quarter by SITC section (sitc1;
    labels are the ten SITC section names, matched on their opening words --
    the code is not printed and is left blank), million maloti;
  * Annex "Total Value of Imports / Exports ... by SITCs and Partner": per
    partner the quarter's total (partner cut, quarterly). The annex is a
    partner x SITC matrix; only its total column is taken. Its position (first
    in 2021, last in recent issues) is not assumed: a row's total is the one
    figure equal to the sum of the other ten, to integer rounding, and the
    position that satisfies most rows of the table is used. "WORLD"/"Total" is
    the all-partner quarter. "-" is no value; "0" is a value below 0.5 million
    and is kept as printed.
Values are in million maloti (LSL x 1e6) as the captions state.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row

CUR, MULT = "LSL", 1e6
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]
_SITC = [("food and", "Food and live animals"), ("beverages and", "Beverages and tobacco"),
         ("crude materials", "Crude materials, inedible, except fuels"),
         ("mineral fuels", "Mineral fuels, lubricants and related materials"),
         ("animal and", "Animal and vegetable oils, fats and waxes"),
         ("chemicals and", "Chemicals and related products, n.e.s."),
         ("manufactured goods", "Manufactured goods classified chiefly by material"),
         ("machinery and", "Machinery and transport equipment"),
         ("miscellaneous manufactured", "Miscellaneous manufactured articles"),
         ("commodities and", "Commodities and transactions not classified elsewhere in the SITC")]
_GROUPS = {"sacu", "sadc", "unspec africa", "other", "others", "eu", "rest of the world", "asia",
           "unspecified", "africa"}
_NUM = r"-?M?-?\d[\d,]*(?:\.\d+)?|-"


def _v(tok: str):
    tok = tok.replace("M", "").replace(",", "")
    if tok in ("-", ""):
        return None
    return float(tok)


def _quarter(path: str):
    m = re.search(r"(20\d{2})_Q([1-4])", os.path.basename(path))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _parse_one(path: str) -> list[dict]:
    import pdfplumber
    y, q = _quarter(path)
    if y is None:
        return []
    qp = f"{y}-Q{q}"
    months = [f"{y}-{3 * (q - 1) + k:02d}" for k in (1, 2, 3)]
    base = os.path.basename(path)
    rows = []
    with pdfplumber.open(path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    text = "\n".join(pages)
    lines = text.split("\n")

    # 1. monthly trade volume table
    in_vol = False
    for ln in lines:
        l = ln.strip()
        if re.match(r"^Month\s+Total Exports", l):
            in_vol = True
            continue
        if in_vol:
            m = re.match(r"^([A-Za-z]+)\s+(" + _NUM + r")\s+(" + _NUM + r")\s+(" + _NUM + r")\s+(" + _NUM + r")$", l)
            if not m:
                if l.startswith(("(FOB)", "Volume")):
                    continue
                if not l.lower().startswith("total"):
                    in_vol = False
                continue
            name = m.group(1).lower()
            if name not in _MONTHS:
                continue
            per = f"{y}-{_MONTHS.index(name) + 1:02d}"
            if per not in months:
                continue
            for flow, tok, basis in (("export", m.group(2), "fob"), ("import", m.group(3), "cif"),
                                     ("balance", m.group(4), ""), ("total", m.group(5), "")):
                v = _v(tok)
                if v is None or (v < 0 and flow != "balance"):
                    continue
                rows.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit=CUR,
                                unit_multiplier=MULT, price_basis=basis, series_code=f"{base}: trade volume"))

    # 2. SITC tables (monthly) and 3. annex partner tables (quarterly)
    flow, mode, cand = None, None, []
    def flush_annex():
        if not cand:
            return
        votes = {"first": 0, "last": 0}
        for _, toks, _a in cand:
            vals = [_v(t) or 0.0 for t in toks]
            if abs(vals[0] - sum(vals[1:])) <= 6:
                votes["first"] += 1
            if abs(vals[-1] - sum(vals[:-1])) <= 6:
                votes["last"] += 1
        pos = max(votes, key=votes.get)
        if votes[pos] < max(3, len(cand) // 2):
            cand.clear()
            return
        # The table is kept only when its country rows add up to its printed
        # WORLD / Total row (to 3 %): a check that the rows belong to one table
        # and one flow (a mis-detected caption would mix two annex tables).
        def total_of(toks):
            vals = [_v(t) for t in toks]
            return (vals[0] if pos == "first" else vals[-1]) or 0.0
        world = [total_of(t) for n, t, _a in cand if n.lower() in ("world", "total")]
        ctry = sum(total_of(t) for n, t, _a in cand if n.lower() not in ("world", "total")
                   and n.lower() not in _GROUPS)
        if len(world) != 1 or not world[0] or abs(ctry - world[0]) > 0.03 * world[0]:
            cand.clear()
            return
        for name, toks, amb in cand:
            low = name.lower()
            if low not in ("world", "total") and (amb or (re.search(r"\btotal\b|\bworld\b", low) and low not in _GROUPS)):
                continue        # a name that may hold a wrapped fragment, or two rows on one line
            vals = [_v(t) for t in toks]
            num = [x or 0.0 for x in vals]
            tot = vals[0] if pos == "first" else vals[-1]
            ok = abs(num[0] - sum(num[1:])) <= 6 if pos == "first" else abs(num[-1] - sum(num[:-1])) <= 6
            if tot is None or not ok:
                continue
            if name.lower() in ("world", "total"):
                kw = {}
            else:
                kw = dict(partner=name, partner_type="group" if name.lower() in _GROUPS else "country")
            rows.append(row(tradeflow=flow_annex, period=qp, frequency="quarterly", value=tot, unit=CUR,
                            unit_multiplier=MULT, price_basis="cif" if flow_annex == "import" else "fob",
                            series_code=f"{base}: annex {flow_annex}s by partner", **kw))
        cand.clear()

    flow_annex, pending = None, ""
    frags = []
    # every name printed whole on one line of the report (its figures stripped)
    printed = set()
    for ln in lines:
        mm = re.match(r"^([A-Za-z][A-Za-z .,'()&/-]*?[A-Za-z.)])(?:\s+[-\d.,%M]+)+\s*$", ln.strip())
        if mm:
            printed.add(" ".join(mm.group(1).split()).lower())
    for ln in lines:
        l = ln.strip()
        low = l.lower()
        if re.match(r"^table\s*\d+\s*:", low):
            if mode == "annex":
                flush_annex()
            mode, pending = None, ""
            frags = []
            if "by sitc" in low and "partner" not in low and "percentage" not in low and "region" not in low:
                flow = "import" if "import" in low else "export" if "export" in low else None
                mode = "sitc" if flow else None
            elif "partner" in low and "sitc" in low and "region" not in low:
                flow_annex = "import" if "imports" in low and "exports" not in low else \
                    "export" if "exports" in low and "imports" not in low else None
                mode = "annex" if flow_annex else None
            continue
        if mode == "sitc":
            m = re.match(r"^(.*?[A-Za-z.,)])\s+(" + _NUM + r")\s+(" + _NUM + r")\s+(" + _NUM + r")$", l)
            if not m:
                continue
            lab = " ".join(m.group(1).lower().split())
            if lab == "total":       # the table's printed monthly total (all products)
                for per, tok in zip(months, m.groups()[1:]):
                    v = _v(tok)
                    if v is None or v < 0:
                        continue
                    rows.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit=CUR,
                                    unit_multiplier=MULT, price_basis="cif" if flow == "import" else "fob",
                                    series_code=f"{base}: {flow}s by SITC, Total"))
                continue
            hit = next((full for k, full in _SITC if lab.startswith(k)), None)
            if not hit:
                continue
            for per, tok in zip(months, m.groups()[1:]):
                v = _v(tok)
                if v is None or v < 0:
                    continue
                rows.append(row(tradeflow=flow, period=per, frequency="monthly", value=v, unit=CUR,
                                unit_multiplier=MULT, commodity=hit, commodity_classification="sitc1",
                                price_basis="cif" if flow == "import" else "fob",
                                series_code=f"{base}: {flow}s by SITC"))
        elif mode == "annex":
            m = re.match(r"^([A-Za-z][A-Za-z .,'()&\-/]*?)\s+((?:(?:" + _NUM + r")\s+){8,11}(?:" + _NUM + r"))$", l)
            # PARTNER NAMES THAT WRAP. A text-only line in the annex either begins a
            # name continued on the figures line below ("United States of" / "America
            # 0 - ..."), or is a row printed without any figures ("Comoros" / "DRC - - 0
            # ..." became "Comoros DRC"; "United Arab" / "Emirates" / "Argentine 0 ..."
            # became "Emirates Argentine"). The fragments above a figures line are joined
            # to its name ONLY when the joined name is printed whole on one line
            # somewhere in the same report ("United States of America 116.0 1.4" in the
            # summary tables); otherwise that row is not emitted (its figures still count
            # in the table check below). Repaired 2026-11-12.
            if m:
                name = " ".join(m.group(1).split())
                amb = False
                if frags:
                    joined = " ".join(" ".join(frags + [name]).split())
                    if joined.lower() in printed:
                        name = joined
                    else:
                        amb = True
                cand.append([name, m.group(2).split(), amb])
                frags = []
            elif re.search(r"[A-Za-z]", l) and not re.search(r"\d", l) and len(l) <= 40:
                frags.append(l)     # (a longer text line is the rotated column header)
            else:
                frags = []
    if mode == "annex":
        flush_annex()
    # Check (nothing derived): an annex table is kept only when its WORLD/Total
    # equals, to 2 %, the three monthly totals printed in the SITC table of the
    # same flow added up. Otherwise its rows are dropped (garbled extraction).
    out = []
    for fl in ("import", "export"):
        ann = [r for r in rows if r["frequency"] == "quarterly" and r["tradeflow"] == fl]
        mon = [r["value"] for r in rows if r["frequency"] == "monthly" and r["tradeflow"] == fl
               and r["commodity"] == "All products" and r["series_code"].endswith("Total")]
        world = [r["value"] for r in ann if r["partner"] == "All partners"]
        keep = len(mon) == 3 and len(world) == 1 and abs(sum(mon) - world[0]) <= 0.02 * world[0]
        if keep:
            out += ann
    return [r for r in rows if r["frequency"] != "quarterly"] + out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = sorted(set([path] + [p for p in (extras or []) if p.lower().endswith(".pdf")]),
                   key=lambda p: _quarter(p))
    rows = []
    for p in paths:
        rows += _parse_one(p)
    if not rows:
        raise ValueError("lesotho_bos: no rows decoded")
    df = pd.DataFrame.from_records(rows)
    key = ["tradeflow", "commodity", "partner", "frequency", "period", "price_basis"]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
