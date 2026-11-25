"""Parser for Botswana merchandise trade -- Statistics Botswana, "International
Merchandise Trade Statistics (IMTS) Monthly Digest" Excel tables
(statsbots.org.bw/sites/default/files/Publication Tables/..., April 2024 onward).

Tables are found by their TITLE, not their sheet name (sheet names change
from issue to issue: "Table1.0 ", "1", "Table 1 Nov", ...):

  Table 1.0 "Total Merchandise Trade - January <y> to <Month y> (Million Pula)":
      per month, quarter (Q1-Q4) and year (Total_<y>): imports CIF, imports FOB,
      domestic exports, re-exports, total exports, trade balance. Freight and
      insurance columns are not trade flows and are not taken.
  Table 2.1 "Principal Import Commodity Groups" / 2.2 "Principal Export
      Commodity Groups": the same periods, by Statistics Botswana's commodity
      groups (classification national). Exports are total exports.
  Table 3.1A / 3.2A "Total Imports / Exports By Country, Region and Principal
      ... Commodity Groups - <Month y>": the "Total Goods" column per partner
      (partner cut, the release month only). The section x partner cells are
      not taken (matrix). SACU, SADC, Other SADC, Africa, Other Africa, Asia,
      Other Asia, EU, Other EU, Rest of the World are groups.

Values in million pula (BWP, unit_multiplier 1e6), exactly as stored in the
workbook (unrounded). Imports CIF rows are emitted after imports FOB so that
the schema's balance identity (exports - imports CIF) is checked against CIF.
"""
from __future__ import annotations

import os
import re
import warnings

import pandas as pd

from ._common import row

CUR, MULT = "BWP", 1e6
_MON = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]
_T1_COLS = (("imports fob", ("import", "fob")), ("imports cif", ("import", "cif")),
            ("domestic export", ("domestic_export", "")), ("re-export", ("re_export", "")),
            ("re export", ("re_export", "")), ("total export", ("export", "")),
            ("trade balance", ("balance", "")))
_GROUPS = {"sacu", "sadc", "other sadc", "africa", "other africa", "asia", "other asia", "eu",
           "other eu", "europe", "other europe", "rest of the world", "rest of world", "others",
           "other", "other countries", "americas", "other americas", "middle east", "oceania"}


def _title(df: pd.DataFrame) -> str:
    for v in df.iloc[:8].values.ravel():
        if isinstance(v, str) and v.strip().lower().startswith("table"):
            return " ".join(v.split())
    return ""


def _classify(df: pd.DataFrame):
    """(kind, flow, header_row, label_col) from the header row's contents --
    many issues carry no table title. kind: t1 | t2 | t3."""
    for i in range(min(len(df), 20)):
        cells = [" ".join(str(c).lower().split()) if isinstance(c, str) else "" for c in df.iloc[i]]
        joined = " | ".join(cells)
        lj = next((j for j, c in enumerate(cells) if c.startswith(("period", "partner"))), None)
        if lj is None:
            continue
        flow = "export" if "copper" in joined else "import" if "fuel" in joined else None
        if "imports cif" in joined and "total export" in joined:
            return "t1", None, i, lj
        if not flow:
            continue
        # The label column holds periods (Table 2.x) or partners (Table 3.x,
        # whose header is sometimes also "Period \ HS").
        first = next((df.iat[k, lj] for k in range(i + 1, min(len(df), i + 6))
                      if isinstance(df.iat[k, lj], str) and df.iat[k, lj].strip()), "")
        is_period = _period(first, 2000)[0] is not None
        if cells[lj].startswith("partner") or not is_period:
            return "t3", flow, i, lj
        return "t2", flow, i, lj
    return None, None, None, None


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _period(label: str, year: int | None):
    """'Jan_2025' / 'Feb' / 'Q1' / 'Total_2024' -> (period, frequency, year)."""
    lab = str(label).strip().lower().replace(" ", "_")
    m = re.match(r"^([a-z]{3})[a-z]*[_\-\s]*(\d{4})?$", lab)
    if m and m.group(1) in _MON:
        y = int(m.group(2)) if m.group(2) else year
        if y is None:
            return None, None, year
        return f"{y}-{_MON.index(m.group(1)) + 1:02d}", "monthly", y
    m = re.match(r"^q([1-4])(?:[_\-](\d{4}))?$", lab)
    if m and (year or m.group(2)):
        y = int(m.group(2) or year)
        return f"{y}-Q{m.group(1)}", "quarterly", y
    m = re.match(r"^(?:total|annual)[_\-]*(\d{4})$", lab)
    if m:
        # the year after a "Total_<y>" row is y + 1 ("Jan" without a year, 2019 digests)
        return m.group(1), "annual", int(m.group(1)) + 1
    return None, None, year


def _find_header(df: pd.DataFrame, needle: str):
    for i in range(min(len(df), 12)):
        cells = [str(c).strip().lower() if isinstance(c, str) else "" for c in df.iloc[i]]
        for j, c in enumerate(cells):
            if needle in c:
                return i, j
    return None, None


def _table1(df: pd.DataFrame, hi: int, lj: int, tag: str) -> list[dict]:
    cols = {}
    for j, c in enumerate(df.iloc[hi]):
        c = " ".join(str(c).lower().split()) if isinstance(c, str) else ""
        for key, fl in _T1_COLS:
            if c.startswith(key):
                cols[j] = fl
                break
    if not any(f == ("export", "") for f in cols.values()):
        return []
    order = sorted(cols, key=lambda j: 1 if cols[j] == ("import", "cif") else 0)
    rows, year = [], None
    ycol = lj > 0 and "year" in str(df.iat[hi, lj - 1]).lower()
    for i in range(hi + 1, len(df)):
        lab = df.iat[i, lj]
        if isinstance(lab, str) and (lab.strip().lower().startswith(("table", "period", "partner"))
                                     or "%" in lab):
            break      # a second block (shares in %, another table) starts here
        if ycol:   # a separate "Year" column (January 2026 issue)
            yv = _num(df.iat[i, lj - 1])
            if yv and 1990 < yv < 2100:
                year = int(yv)
        per, freq, year = _period(lab, year)
        if per is None:
            continue
        for j in order:
            v = _num(df.iat[i, j])
            flow, basis = cols[j]
            if v is None or (v < 0 and flow != "balance"):
                continue
            rows.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit=CUR,
                            unit_multiplier=MULT, price_basis=basis, series_code=tag))
    return rows


def _table2(df: pd.DataFrame, hi: int, lj: int, flow: str, tag: str) -> list[dict]:
    names = {j: " ".join(str(c).split()) for j, c in enumerate(df.iloc[hi])
             if j > lj and isinstance(c, str) and c.strip() and not c.strip().lower().startswith(("total", "%"))}
    rows, year = [], None
    ycol = lj > 0 and "year" in str(df.iat[hi, lj - 1]).lower()
    for i in range(hi + 1, len(df)):
        lab = df.iat[i, lj]
        if isinstance(lab, str) and (lab.strip().lower().startswith(("table", "period", "partner"))
                                     or "%" in lab):
            break      # a second block (shares in %, another table) starts here
        if ycol:   # a separate "Year" column (January 2026 issue)
            yv = _num(df.iat[i, lj - 1])
            if yv and 1990 < yv < 2100:
                year = int(yv)
        per, freq, year = _period(lab, year)
        if per is None:
            continue
        for j, name in names.items():
            v = _num(df.iat[i, j])
            if v is None or v < 0:
                continue
            rows.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit=CUR,
                            unit_multiplier=MULT, commodity=name, commodity_classification="national",
                            price_basis="cif" if flow == "import" else "", series_code=tag))
    return rows


def _table3(df: pd.DataFrame, hi: int, lj: int, flow: str, period: str, tag: str) -> list[dict]:
    tj = next((j for j, c in enumerate(df.iloc[hi]) if isinstance(c, str)
               and " ".join(c.lower().split()) in ("total goods", "total")), None)
    if tj is None:
        return []
    rows = []
    for i in range(hi + 1, len(df)):
        name = df.iat[i, lj]
        if not isinstance(name, str) or not name.strip():
            if rows:
                break
            continue
        name = " ".join(name.split())
        if name.lower() == "total" or name.lower().startswith("table"):
            if name.lower() == "total":
                break
            continue
        if re.fullmatch(r"(total\s+)?world(\s+new)?", name.lower()):
            # "World" / "TOTAL WORLD NEW" (Apr-Jun 2024, Dec 2024-Feb 2025
            # workbooks) equals that workbook's own Table 1.0 month exactly: it
            # is the release-vintage world total, which later workbooks revise.
            # The headline series is Table 1.0 (newest wins), so it is not emitted.
            continue
        v = _num(df.iat[i, tj])
        if v is None or v < 0:
            continue
        ptype = "group" if name.lower() in _GROUPS else "country"
        rows.append(row(tradeflow=flow, period=period, frequency="monthly", value=v, unit=CUR,
                        unit_multiplier=MULT, partner=name, partner_type=ptype,
                        price_basis="cif" if flow == "import" else "", series_code=tag))
    return rows


def _title_month(title: str):
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|"
                  r"December)\s+(\d{4})\s*(?:\(|$)", title, re.I)
    if not m:
        m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|"
                      r"December)\s+(\d{4})", title, re.I)
    return f"{m.group(2)}-{_MONTHS.index(m.group(1).lower()) + 1:02d}" if m else None


def _parse_book(path: str) -> list[dict]:
    rows = []
    base = os.path.basename(path)
    release = _release(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        xl = pd.ExcelFile(path)
        for sh in xl.sheet_names:
            df = xl.parse(sh, header=None)
            kind, flow, hi, lj = _classify(df)
            if kind is None:
                continue
            t = _title(df)
            tag = f"{base}: " + (t[:60] if t else f"sheet {sh.strip()}")
            if kind == "t1":
                rows += _table1(df, hi, lj, tag)
            elif kind == "t2":
                rows += _table2(df, hi, lj, flow, tag)
            elif kind == "t3":
                per = _title_month(t) if t else None
                rows += _table3(df, hi, lj, flow, per or "RELEASE", tag)
        xl.close()
    # An untitled partner table is for the release month: the last month of
    # Table 1.0 (more reliable than the file name, e.g. "AUGUST IMTS TABLES.xlsx").
    months = [r["period"] for r in rows if r["frequency"] == "monthly" and r["period"] != "RELEASE"
              and r["commodity"] == "All products" and r["partner"] == "All partners"]
    rel = max(months) if months else release
    for r in rows:
        if r["period"] == "RELEASE":
            r["period"] = rel
    return rows


def _fold_group(label: str) -> str:
    k = re.sub(r"[^a-z]", "", str(label).lower())
    for a, b in (("vehicles", "vehicle"), ("metals", "metal"), ("electricalproducts", "electricalequipment"),
                 ("textilesimports", "textilesfootwear")):
        k = k.replace(a, b)
    return k


def _release(path: str) -> str:
    """Release month from the file name, for ordering (newest wins)."""
    b = os.path.basename(path).lower()
    y = re.search(r"20\d{2}", b)
    mo = next((i for i, m in enumerate(_MON) if m in b), 0)
    return f"{y.group(0) if y else '0000'}-{mo + 1:02d}"


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = sorted(set([path] + [p for p in (extras or []) if p.lower().endswith((".xls", ".xlsx"))]),
                   key=_release)
    rows = []
    for p in paths:
        rows += [dict(r, _order=_release(p)) for r in _parse_book(p)]
    if not rows:
        raise ValueError("botswana_statsbots: no rows decoded")
    df = pd.DataFrame.from_records(rows)
    # One commodity group is spelled differently from issue to issue ("Vehicle"
    # / "Vehicles & Transport Equipment", "Food, Beverages" / "Food Beverages",
    # "Machinery & Electrical Products" / "... Equipment", "Metals" / "Metal &
    # Metal Products" -- same figures). Each group takes the spelling of the
    # newest issue that prints it, so one group is one series.
    df = df.sort_values("_order", kind="stable")
    fold = df["commodity"].map(_fold_group)
    newest = dict(zip(fold, df["commodity"]))          # last (newest) spelling wins
    df["commodity"] = [newest[f] if c != "All products" else c for f, c in zip(fold, df["commodity"])]
    key = ["tradeflow", "commodity", "partner", "frequency", "period", "price_basis"]
    df = df.drop_duplicates(key, keep="last")
    # keep imports CIF after FOB within each cell (see module docstring)
    df["_cif"] = (df["price_basis"] == "cif").astype(int)
    df = df.sort_values(["_order", "_cif"], kind="stable")
    return df.drop(columns=["_order", "_cif"]).reset_index(drop=True)


# --------------------------------------------------------------------------- PDF back series
# The monthly Digest PDFs (2013-2023) print the same Table 1 with a window of
# two to four years (December 2015: January 2012 - December 2015). Its column
# order is fixed: Imports CIF, Imports FOB, Freight, Insurance, Domestic
# Exports, Re-Exports, Total Exports, Trade Balance (the rotated header text
# is not readable, so each row is accepted only when its own figures satisfy
# FOB + freight + insurance = CIF, domestic + re-exports = total exports and
# total exports - CIF = balance, to rounding -- a check, nothing is derived).
# The 2015-2016 layout also prints Tables 3.1A/3.2A as partner x month for
# "January <y> to December <y>" (12 calendar-month columns).
_PNUM = r"\(?-?\d[\d,]*(?:\.\d+)?\)?|-"
_T1_ORDER = [("import", "cif"), ("import", "fob"), None, None, ("domestic_export", ""),
             ("re_export", ""), ("export", ""), ("balance", "")]


def _pnum(tok: str):
    if tok == "-":
        return None
    neg = tok.startswith("(") and tok.endswith(")")
    v = float(tok.strip("()").replace(",", ""))
    return -v if neg else v


def _t1_ok(v) -> bool:
    cif, fob, fr, ins, dom, rex, tot, bal = v
    if None in (cif, fob, tot, bal):
        return False
    ok = abs(fob + (fr or 0) + (ins or 0) - cif) <= 0.25 + 0.002 * abs(cif)
    ok &= abs((dom or 0) + (rex or 0) - tot) <= 0.25 + 0.002 * abs(tot)
    ok &= abs(tot - cif - bal) <= 0.25 + 0.002 * abs(cif)
    return ok


def _pdf_rows(path: str) -> list[dict]:
    import pdfplumber
    base = os.path.basename(path)
    rows = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            t = pg.extract_text() or ""
            title = next((l for l in t.split("\n") if re.match(r"^Table\s+(1(\.0)?|3\.[12]A)\b", l)), "")
            if not title:
                continue
            tag = f"{base}: {' '.join(title.split())[:70]}"
            if re.match(r"^Table\s+1(\.0)?\b", title) and "Total Merchandise Trade" in title:
                year = None
                lines_ = t.split("\n")
                ti = lines_.index(title)
                tl = " ".join(lines_[ti:ti + 2]).lower()     # the caption may wrap: "(Million Pula)"
                if "million pula" in tl:
                    mult = MULT
                elif re.search(r"['’‘`]000 pula", tl):
                    mult = 1e3
                else:
                    continue          # scale not printed in the caption: not guessed
                names = ["cif", "fob", "freight", "insurance", "domestic", "re", "total", "balance"]
                order = names
                hdr = next((l.lower() for l in t.split("\n") if "imports cif" in l.lower()
                            and "total exports" in l.lower()), None)
                if hdr:   # a readable header (2013 layout: Re-Exports BEFORE Domestic Exports)
                    pos = {"cif": hdr.find("imports cif"), "fob": hdr.find("imports fob"),
                           "freight": hdr.find("freight"), "insurance": hdr.find("insurance"),
                           "domestic": hdr.find("domestic export"), "re": hdr.find("re-export"),
                           "total": hdr.find("total export"), "balance": hdr.find("trade balance")}
                    if min(pos.values()) >= 0:
                        order = sorted(pos, key=pos.get)
                spec = {"cif": ("import", "cif"), "fob": ("import", "fob"), "domestic": ("domestic_export", ""),
                        "re": ("re_export", ""), "total": ("export", ""), "balance": ("balance", "")}
                for ln in t.split("\n"):
                    ln = re.sub(r"^Total\s*_?\s*(\d{4})", r"Total_\1", ln.strip())
                    m = re.match(r"^(\S+)\s+((?:(?:" + _PNUM + r")\s+){7}(?:" + _PNUM + r"))\s*$", ln)
                    if not m:
                        continue
                    per, freq, year = _period(m.group(1), year)
                    if per is None:
                        continue
                    vals = dict(zip(order, [_pnum(x) for x in m.group(2).split()]))
                    scale = 1 if mult == MULT else 1000
                    if not _t1_ok([None if vals[n] is None else vals[n] / scale for n in names]):
                        continue
                    for n in ["fob", "domestic", "re", "total", "balance", "cif"]:
                        v = vals[n]
                        flow, basis = spec[n]
                        if v is None or (v < 0 and flow != "balance"):
                            continue
                        rows.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit=CUR,
                                        unit_multiplier=mult, price_basis=basis, series_code=tag))
            elif re.match(r"^Table\s+3\.[12]A", title):
                m = re.search(r"January\s+(\d{4})\s+to\s+December\s+(\d{4})", title)
                if not m or m.group(1) != m.group(2):
                    continue
                y = m.group(1)
                flow = "import" if "Imports" in title else "export"
                for ln in t.split("\n"):
                    mm = re.match(r"^([A-Za-z][A-Za-z .,&'()\-]*?)\s+((?:(?:" + _PNUM + r")\s+){11}(?:" + _PNUM + r"))\s*$",
                                  ln.strip())
                    if not mm:
                        continue
                    name = " ".join(mm.group(1).split())
                    if name.lower() in ("total", "grand total"):
                        continue
                    ptype = "group" if name.lower() in _GROUPS else "country"
                    for k, x in enumerate(mm.group(2).split()):
                        v = _pnum(x)
                        if v is None or v < 0:
                            continue
                        rows.append(row(tradeflow=flow, period=f"{y}-{k + 1:02d}", frequency="monthly",
                                        value=v, unit=CUR, unit_multiplier=MULT, partner=name,
                                        partner_type=ptype, price_basis="cif" if flow == "import" else "",
                                        series_code=tag))
    return rows


def parse_pdf(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = sorted(set([path] + [p for p in (extras or []) if p.lower().endswith(".pdf")]), key=_release)
    rows = []
    for p in paths:
        rows += [dict(r, _order=_release(p)) for r in _pdf_rows(p)]
    if not rows:
        raise ValueError("botswana_statsbots: no rows decoded from the PDFs")
    df = pd.DataFrame.from_records(rows)
    key = ["tradeflow", "commodity", "partner", "frequency", "period", "price_basis"]
    df = df.sort_values("_order", kind="stable").drop_duplicates(key, keep="last")
    df["_cif"] = (df["price_basis"] == "cif").astype(int)
    df = df.sort_values(["_order", "_cif"], kind="stable")
    return df.drop(columns=["_order", "_cif"]).reset_index(drop=True)
