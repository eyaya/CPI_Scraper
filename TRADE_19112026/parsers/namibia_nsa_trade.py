"""Parser for Namibia merchandise trade -- Namibia Statistics Agency (NSA),
"Namibia (International) Merchandise Trade Statistics Bulletin", monthly Excel
tables (nsa.org.na/document/... , March 2021 onward).

Tables are found by TITLE (sheet names and numbering change between issues):

  "Import/Export/Trade bal ..." : exports, imports and trade balance, monthly,
      13-month window (the "Imports (-)" helper column is not taken).
  "Export/Import series by month_quarter_annual" (2021), "Cumulative Trade
      Value - <year>" : exports and imports by month (and quarter); the
      cumulative-to-date columns are not taken.
  "Overall trade highlight for the period of 2018 to 2022" : annual exports
      and imports.
  "Exports / Re-exports / Imports by partner" : by partner country, for the
      three months printed (current, previous, same month a year earlier).
  "Exports / Re-exports / Imports by product(s)" : by SITC group (3-digit,
      "286:Uranium or thorium ores ..."; the only commodity level the NSA
      publishes monthly -> sitc3), same three months; in the current month of
      the exports table also domestic exports and re-exports.
  "Export(s) / Imports by economic region(s)" : groups (SACU, SADC_excl_SACU,
      COMESA, EU, OECD, BRIC+ ...; overlapping), value columns only.

Period of a month column: the year and month of its header date (the NSA's
header cells are dates, e.g. 2026-09-01; the 2021 sheets store "Mar-20" style
labels as 2021-03-20 -- the month and the column order still identify the
month, which is what is used). Values in N$ million (NAD x 1e6). Not
collected: % shares and changes, ISIC tables (activity, not product), top-5
products by country (matrix), mode of transport, border posts, annual product
tables without SITC codes, revisions tables.

One SITC group is spelled differently across issues ("682:Copper" /
"682:Copper"...); each code takes the label of the newest issue, so one code
is one series.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import warnings

import pandas as pd

from ._common import row

CUR, MULT = "NAD", 1e6
_MON = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_NOT_COUNTRY = {"high sea", "high seas", "unknown", "other", "others", "not specified", "ship stores",
                "ships stores", "stores and provisions", "rest of the world", "unallocated"}


def _s(v) -> str:
    return " ".join(str(v).split()) if isinstance(v, str) else ""


def _num(v):
    if v is None or isinstance(v, str) and not v.strip():
        return None
    if isinstance(v, (int, float)):
        return None if pd.isna(v) else float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def _month_of(v):
    """A header/period cell -> 'YYYY-MM', or None."""
    if isinstance(v, (dt.datetime, dt.date, pd.Timestamp)):
        return f"{v.year}-{v.month:02d}"
    s = _s(v).lower()
    m = re.match(r"^([a-z]{3})[a-z]*[\s\-_']*(\d{2}|\d{4})$", s)
    if m and m.group(1) in _MON:
        y = int(m.group(2))
        y = y + 2000 if y < 100 else y
        return f"{y}-{_MON.index(m.group(1)) + 1:02d}"
    return None


def _title(df) -> str:
    for v in df.iloc[:8].values.ravel():
        s = _s(v)
        if re.match(r"^table\s*\d", s.lower()):
            return s
    return ""


def _flow(tl: str):
    if "re-export" in tl or "re export" in tl:
        return "re_export"
    if "import" in tl:
        return "import"
    if "export" in tl:
        return "export"
    return None


def _period_table(df, tag: str, year_hint: int | None, title: str = "") -> list[dict]:
    """Rows = periods; columns Export(s) / Import(s) / Trade bal."""
    rows = []
    for hi in range(min(len(df), 12)):
        cells = [_s(c).lower() for c in df.iloc[hi]]
        if any(c.startswith("period") for c in cells):
            break
    else:
        return rows
    lj = next(j for j, c in enumerate(cells) if c.startswith("period"))
    yj = next((j for j, c in enumerate(cells) if c == "year"), None)
    cols = {}
    for j, c in enumerate(cells):
        if "cumulative" in c or "(-)" in c or "%" in c:
            continue
        if c.startswith("trade bal"):
            cols[j] = "balance"
        elif re.match(r"^(total )?exports?\b", c):
            cols[j] = "export"
        elif re.match(r"^(total )?imports?\b", c):
            cols[j] = "import"
    if not any(f == "export" for f in cols.values()):
        return rows
    # The scale is read from the caption or the header ("(N$ m)", "(N$ b)" --
    # the July 2022 issue prints billions). A table that prints none is used
    # only to anchor the month columns of the other tables, never emitted.
    txt = (title + " " + " ".join(cells)).lower()
    mult = 1e9 if re.search(r"n\$\s*b(n|illion)?\b", txt) else 1e6 if re.search(r"n\$\s*m(n|illion)?\b", txt) else None
    year = year_hint
    # "Table 7: Imports/Exports/Trade bal (N$ m) Dec 2021 to Dec 2022": rows are
    # bare month names; the year starts at the caption's first month and steps
    # up when the month wraps (Dec -> Jan).
    start = next((mm for mm in re.finditer(r"\b([a-z]{3})[a-z]*[\s\-]+(20\d{2}|\d{2})\b", title.lower())
                  if mm.group(1) in _MON), None)
    run_year, last_m = None, None
    if start and start.group(1) in _MON:
        y0 = int(start.group(2))
        run_year = y0 + 2000 if y0 < 100 else y0
    for i in range(hi + 1, len(df)):
        if yj is not None:
            yv = _num(df.iat[i, yj])
            if yv and 1990 < yv < 2100:
                year = int(yv)
        lab = df.iat[i, lj]
        per, freq = _month_of(lab), "monthly"
        if per and isinstance(lab, str) and not re.search(r"\d", lab):
            per = None
        if per is None:
            s = _s(lab).lower()
            m = re.match(r"^([a-z]{3})[a-z]*$", s)
            if m and m.group(1) in _MON:
                mi = _MON.index(m.group(1)) + 1
                if yj is None and year_hint is None and run_year:
                    if last_m is not None and mi < last_m:
                        run_year += 1
                    last_m = mi
                    per = f"{run_year}-{mi:02d}"
                elif year:
                    per = f"{year}-{mi:02d}"
            m = re.match(r"^q([1-4])[\s\-_']*(\d{2}|\d{4})$", s)
            if m:
                y = int(m.group(2))
                y = y + 2000 if y < 100 else y
                per, freq, year = f"{y}-Q{m.group(1)}", "quarterly", y
            m = re.match(r"^(0[1-9]|1[0-2])$", s)       # "01" under a "q1-2021" row
            if m and year and yj is None:
                per = f"{year}-{m.group(1)}"
            if re.match(r"^(19|20)\d{2}$", s):
                per, freq = s, "annual"
        if per is None:
            continue
        for j, flow in cols.items():
            v = _num(df.iat[i, j])
            if v is None or (v < 0 and flow != "balance"):
                continue
            r = row(tradeflow=flow, period=per, frequency=freq, value=v, unit=CUR,
                    unit_multiplier=mult or MULT, series_code=tag)
            if mult is None:
                r["_anchor_only"] = True
            rows.append(r)
    return rows


def _annual_highlights(df, tag: str) -> list[dict]:
    rows = []
    for hi in range(min(len(df), 8)):
        yrs = {j: int(v) for j, v in enumerate(df.iloc[hi]) if isinstance(v, (int, float))
               and not pd.isna(v) and 1990 < v < 2100}
        if len(yrs) >= 2:
            break
    else:
        return rows
    for i in range(hi + 1, len(df)):
        lab = _s(df.iat[i, 0]).lower()
        flow = "export" if lab.startswith("export") else "import" if lab.startswith("import") else \
            "balance" if lab.startswith("trade bal") else None
        if not flow:
            continue
        for j, y in yrs.items():
            v = _num(df.iat[i, j])
            if v is None or (v < 0 and flow != "balance"):
                continue
            rows.append(row(tradeflow=flow, period=str(y), frequency="annual", value=v, unit=CUR,
                            unit_multiplier=MULT, series_code=tag))
    return rows


def _shift(per: str, k: int) -> str:
    y, m = int(per[:4]), int(per[5:])
    n = y * 12 + (m - 1) + k
    return f"{n // 12}-{n % 12 + 1:02d}"


def _offset(per: str, rel: str) -> int:
    return (int(per[:4]) * 12 + int(per[5:])) - (int(rel[:4]) * 12 + int(rel[5:]))


def _date_cols_table(df, flow: str, kind: str, tag: str, head: dict, rel: str | None,
                     pattern: list, used: list | None = None) -> list[dict]:
    """Partner / product / region rows x month columns.

    The header cells are dates, but some issues store a typed "Aug-23" as
    23 August 2024, so two columns can claim one month. Each column's month is
    therefore anchored on its own Total row: the column whose total equals the
    file's headline exports / imports of a month IS that month. Where no total
    matches (re-exports, regions) the header date is used if it is unambiguous,
    else the column layout (offsets from the release month) found for another
    table of the same file. Otherwise the table is skipped, never guessed."""
    rows = []
    for hi in range(min(len(df), 12)):
        dcols = [j for j, v in enumerate(df.iloc[hi]) if _month_of(v) and not isinstance(v, (int, float))]
        if len(dcols) >= 2:
            break
    else:
        return rows
    sub = [_s(c).lower() for c in df.iloc[hi + 1]] if hi + 1 < len(df) else []
    lj = 0
    total_i = next((i for i in range(hi + 2, len(df))
                    if _s(df.iat[i, lj]).lower().startswith(("total", "grand total"))), None)
    spans = []
    for k, c in enumerate(dcols):
        end = dcols[k + 1] if k + 1 < len(dcols) else min(len(df.columns), c + 6)
        picks = {}
        for j in range(c, end):
            h = sub[j] if j < len(sub) else ""
            if "%" in h or "share" in h:
                continue
            if "domestic" in h:
                picks["domestic_export"] = j
            elif "re-export" in h or "re export" in h:
                if flow == "export":
                    picks["re_export"] = j
            elif "total export" in h or h.startswith("value"):
                picks[flow] = j
        per = _month_of(df.iat[hi, c])
        anchored = None
        if total_i is not None and flow in picks and flow in ("export", "import"):
            tv = _num(df.iat[total_i, picks[flow]])
            if tv:
                hits = [p for (f, p), v in head.items() if f == flow and abs(v - tv) <= 0.02 + 1e-6 * tv]
                if len(hits) == 1:
                    anchored = hits[0]
                    if used is not None:
                        used.append((flow, anchored))
        spans.append([anchored or per, picks, anchored is not None])
    if not all(a for _, _, a in spans) and rel and pattern and len(pattern) == len(spans):
        # an unanchored table (re-exports, regions) follows the column layout
        # proven for the anchored tables of the same file, not its header dates
        for sp, off in zip(spans, pattern):
            sp[0] = _shift(rel, off)
    elif len({p for p, _, _ in spans}) != len(spans):
        if rel and pattern and len(pattern) == len(spans):
            for sp, off in zip(spans, pattern):
                sp[0] = _shift(rel, off)
        else:
            return rows                  # two columns claim one month: not guessed
    if rel and all(a for _, _, a in spans):
        pattern[:] = [_offset(p, rel) for p, _, _ in spans]
    for i in range(hi + 2, len(df)):
        lab = _s(df.iat[i, lj])
        if not lab:
            continue
        if lab.lower().startswith(("total", "grand total")):
            break
        if kind == "product":
            m = re.match(r"^([0-9]{3}|[IVX]+)\s*:\s*(.+)$", lab)
            if not m:
                continue
            kw = dict(commodity=lab, commodity_classification="sitc3", commodity_code_nso=m.group(1))
        else:
            ptype = "group" if kind == "region" or lab.lower() in _NOT_COUNTRY else "country"
            kw = dict(partner=lab, partner_type=ptype)
        for per, picks, _ in spans:
            for fl, j in picks.items():
                v = _num(df.iat[i, j])
                if v is None or v < 0:
                    continue
                rows.append(row(tradeflow=fl, period=per, frequency="monthly", value=v, unit=CUR,
                                unit_multiplier=MULT, series_code=tag, **kw))
    return rows


def _parse_book(path: str) -> list[dict]:
    rows = []
    base = os.path.basename(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        xl = pd.ExcelFile(path)
        sheets = []
        for sh in xl.sheet_names:
            df = xl.parse(sh, header=None)
            t = _title(df)
            if t:
                sheets.append((sh, df, t))
        xl.close()
    later = []
    for sh, df, t in sheets:              # pass 1: the period tables (headline)
        tl = t.lower()
        tag = f"{base}: {t[:70]}"
        if ("trade bal" in tl and not re.search(r"partner|product|region", tl)) or "quarterly trade" in tl:
            rows += _period_table(df, tag, None, t)
        elif "series by month" in tl or "cumulative trade value" in tl:
            m = re.search(r"(20\d{2})", tl) or re.search(r"(20\d{2})", sh)
            rows += _period_table(df, tag, int(m.group(1)) if m else None, t)
        elif "overall trade highlight" in tl:
            rows += _annual_highlights(df, tag)
        else:
            later.append((sh, df, t))
    head = {(r["tradeflow"], r["period"]): r["value"] * r["unit_multiplier"] / 1e6
            for r in rows if r["frequency"] == "monthly"}
    held = [r for r in rows if r.get("_anchor_only")]
    rows = [r for r in rows if not r.get("_anchor_only")]
    used: list = []
    months = [p for (_, p) in head]
    rel = max(months) if months else None
    pattern: list = []
    # pass 2: export/import tables first (they anchor the column layout), then the rest
    later.sort(key=lambda x: 0 if _flow(x[2].lower()) in ("export", "import") else 1)
    for sh, df, t in later:
        tl = t.lower()
        tag = f"{base}: {t[:70]}"
        fl = _flow(tl)
        if not fl:
            continue
        if re.search(r"by partner\b", tl) and not re.search(r"top|balance|product", tl):
            rows += _date_cols_table(df, fl, "partner", tag, head, rel, pattern, used)
        elif re.search(r"by products?\b", tl) and not re.search(r"annual|top|balance|region|mode|partner", tl):
            rows += _date_cols_table(df, fl, "product", tag, head, rel, pattern, used)
        elif "economic region" in tl and not re.search(r"product|annual", tl):
            rows += _date_cols_table(df, fl, "region", tag, head, rel, pattern, used)
    # A period table without a printed scale (2021 issues) is emitted only when
    # one of its months equals, to the unit, the Total of a table printed in
    # "Value (N$ m)" in the same file: the scale is then the printed N$ million.
    held_keys = {(r["tradeflow"], r["period"]) for r in held}
    if any(k in held_keys for k in used):
        for r in held:
            r.pop("_anchor_only", None)
            r["series_code"] += " [scale: N$ m, as the file's partner/product tables]"
        rows += held
    return rows


def _release(rows: list[dict], path: str) -> str:
    months = [r["period"] for r in rows if r["frequency"] == "monthly"]
    return max(months) if months else os.path.basename(path)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = sorted(set([path] + [p for p in (extras or []) if p.lower().endswith((".xls", ".xlsx"))]))
    rows = []
    for p in paths:
        got = _parse_book(p)
        rel = _release(got, p)
        rows += [dict(r, _order=rel) for r in got]
    if not rows:
        raise ValueError("namibia_nsa: no rows decoded")
    df = pd.DataFrame.from_records(rows).sort_values("_order", kind="stable")
    # one SITC code = one series, labelled as in the newest issue
    prod = df["commodity_classification"] == "sitc3"
    newest = dict(zip(df.loc[prod, "commodity_code_nso"], df.loc[prod, "commodity"]))
    df.loc[prod, "commodity"] = df.loc[prod, "commodity_code_nso"].map(newest)
    key = ["tradeflow", "commodity_code_nso", "commodity", "partner", "frequency", "period"]
    df = df.drop_duplicates(key, keep="last")
    return df.drop(columns="_order").reset_index(drop=True)
