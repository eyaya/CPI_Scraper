"""South Africa -- National Treasury, Budget Review, statistical annexure
Table 10 "Total debt of government" (R million, fiscal years ending March).

PUBLISHER: National Treasury; the table's source line reads "National
Treasury and Reserve Bank". COVERAGE: national government debt -- footnote 1:
"Debt of the national government, excluding extra-budgetary institutions and
social security funds".

THE TABLE runs over four pages, seven fiscal-year columns each, 2001/02 to the
end of the medium-term estimates. Footnote 2 marks the last AUDITED outcome
("Audited outcomes at the end of March 2025"); only outcome columns up to and
including that year are collected -- the revised estimate and the
medium-term projections are not statistics. Fiscal year 2024/25 ends 31 March
2025 and is dated "2025" (annual).

COLLECTED, as printed:
  * domestic debt -- marketable, government bonds, Treasury bills, bridging
    bonds, non-marketable, gross loan debt, net loan debt; foreign debt --
    gross and net loan debt; total gross and net loan debt -> `stock`
    ("ZAR million"), components "Domestic debt: ...", "Foreign debt: ...",
    "Total: ...";
  * "Composition of gross debt" -> `share` ("... (share of gross loan
    debt)");
  * "Total as percentage of GDP" -> `share_of_gdp`.
NOT COLLECTED: the National Revenue Fund cash balances (printed negative, a
deduction, not a debt stock -- net = gross less cash is collected) and the
Gold and Foreign Exchange Contingency Reserve Account (a revaluation
balance, not debt). Nil cells ("-") are skipped.

TRAP: the PDF text layer splits numbers with stray kerning spaces ("3 49 415"
= 349 415, "8 2 009" = 82 009), so values are read from character positions:
each digit belongs to the right-aligned column whose year header it falls
under. Pages 1 and 3 print labels left of the numbers, pages 2 and 4 right.

Checks: marketable + non-marketable = domestic gross; bonds + bills +
bridging = marketable; domestic + foreign gross = total gross (to R2 million,
rounding).

CROSS-CHECK: 2024/25 total gross loan debt 5 693 713 (Table 7.7: R5 693.7
bn), 77.0% of GDP; domestic gross 5 091 811, foreign 601 902; 2001/02 total
gross 433 454 (36.0% of GDP).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_FY = re.compile(r"^(\d{4})/(\d{2})$")
_CODE = "NT Budget Review statistical annexure Table 10"
_STOCK = {"Marketable", "Government bonds", "Treasury bills", "Bridging bonds",
          "Non-marketable", "Gross loan debt", "Net loan debt"}
_SHARE = {"Marketable domestic debt", "Government bonds", "Treasury bills",
          "Bridging bonds", "Non-marketable domestic debt", "Domestic debt",
          "Foreign debt"}
_GDP = {"Gross domestic debt", "Net domestic debt", "Gross foreign debt",
        "Net foreign debt", "Gross loan debt", "Net loan debt"}


def _page_rows(page):
    """[(label, [cell per column])], years -- cells None where blank."""
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    hdr = [w for w in words if _FY.match(w["text"])]
    if len(hdr) < 5:
        return [], []
    top = min(w["top"] for w in hdr)
    hdr = sorted((w for w in hdr if abs(w["top"] - top) < 3), key=lambda w: w["x0"])
    years = [int(_FY.match(w["text"]).group(1)) + 1 for w in hdr]
    right = [w["x1"] for w in hdr]
    width = right[1] - right[0]
    lo, hi = right[0] - width + 2, right[-1] + 2       # numeric band
    lines = {}
    for ch in page.chars:
        if ch["top"] <= top + 5 or not ch["text"].strip():
            continue
        lines.setdefault(round(ch["top"]), []).append(ch)
    rows = []
    for _, chs in sorted(lines.items()):
        chs.sort(key=lambda c: c["x0"])
        cells, label = [""] * len(years), []
        for c in chs:
            xc = (c["x0"] + c["x1"]) / 2
            if lo <= xc <= hi and re.match(r"[\d.,%\-–]", c["text"]):
                k = next(i for i, r in enumerate(right) if xc <= r + 2)
                cells[k] += c["text"]
            else:
                label.append(c)
        txt = "".join(_spaced(label)).strip()
        txt = re.sub(r"^\d\)\s*|\s*\d\)$", "", txt).strip()     # footnote marks
        if any(cells):
            rows.append((txt, cells))
        elif txt:
            rows.append((txt, None))
    return rows, years


def _spaced(chs):
    out, prev = [], None
    for c in chs:
        if prev is not None and c["x0"] - prev["x1"] > 1.0:
            out.append(" ")
        out.append(c["text"])
        prev = c
    return out


def _val(cell):
    cell = cell.replace(",", "").replace("%", "")
    if not cell or set(cell) <= {"-", "–"}:
        return None
    return float(cell)


def parse(path: str, extras=None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = [p for p in pdf.pages
                 if "Total debt of government" in (p.extract_text() or "")
                 and "Composition of gross debt" in (p.extract_text() or "")]
        text = "\n".join(p.extract_text() for p in pages)
        m = re.search(r"Audited outcomes at the end of March (\d{4})", text)
        if not m:
            raise ValueError("NT T10: audited-outcome footnote not found")
        last = int(m.group(1))
        recs = {}
        for page in pages:
            rows, years = _page_rows(page)
            section = None
            for label, cells in rows:
                if cells is None:
                    if label in ("Domestic debt", "Foreign debt"):
                        section = label
                    elif label.startswith("Composition of gross debt"):
                        section = "share"
                    elif label.startswith("Total as percentage of GDP"):
                        section = "gdp"
                    elif label.startswith("Gold and Foreign"):
                        section = "gfecra"
                    continue
                if section == "gfecra" or label.startswith("Contingency"):
                    section = "after"            # GFECRA row, then composition
                    continue
                if section in ("Domestic debt", "Foreign debt", "Total", "after"):
                    if label not in _STOCK:
                        continue                 # cash balances
                    comp = f"{'Total' if section == 'after' else section}: {label}"
                    meas, unit = "stock", "ZAR million"
                    if section == "Foreign debt" and label == "Net loan debt":
                        section = "after"        # next gross/net are totals
                elif section == "share" and label in _SHARE:
                    comp, meas, unit = f"{label} (share of gross loan debt)", "share", "percent"
                elif section == "gdp" and label in _GDP:
                    comp, meas, unit = label, "share_of_gdp", "percent"
                else:
                    continue
                for y, c in zip(years, cells):
                    v = _val(c)
                    if v is None or y > last:
                        continue
                    key = (comp, str(y), meas, unit)
                    if key in recs and abs(recs[key] - v) > 1e-9:
                        raise ValueError(f"NT T10: {key} printed twice: {recs[key]} vs {v}")
                    recs[key] = v
    df = pd.DataFrame([{"component": c, "period": p, "frequency": "annual",
                        "measure": m, "value": v, "unit": u, "series_code": _CODE}
                       for (c, p, m, u), v in recs.items()])

    s = df[df.measure == "stock"].pivot_table(index="period", columns="component",
                                              values="value")
    bridging = s.get("Domestic debt: Bridging bonds", pd.Series(0, index=s.index)).fillna(0)
    for lhs, rhs, name in [
        (s["Domestic debt: Marketable"] + s["Domestic debt: Non-marketable"],
         s["Domestic debt: Gross loan debt"], "marketable + non-marketable"),
        (s["Domestic debt: Government bonds"] + s["Domestic debt: Treasury bills"] + bridging,
         s["Domestic debt: Marketable"], "bonds + bills"),
        (s["Domestic debt: Gross loan debt"] + s["Foreign debt: Gross loan debt"],
         s["Total: Gross loan debt"], "domestic + foreign"),
    ]:
        bad = (lhs - rhs).abs()
        if (bad > 2).any():
            raise ValueError(f"NT T10: {name} != total in {list(bad[bad > 2].index)}")
    if df.period.nunique() < 20:
        raise ValueError(f"NT T10: only {df.period.nunique()} years parsed")
    return df
