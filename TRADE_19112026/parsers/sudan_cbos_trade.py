"""Parser for the Central Bank of Sudan "Foreign Trade Statistical Digest" (Tier 3 PDF).

COMPILER. The Central Bureau of Statistics has no reachable site; Sudan's
merchandise-trade statistics are compiled and published by the Central Bank of
Sudan (Policies, Research & Statistics Department) from Sudan Customs Authority
(and Ministry of Energy & Petroleum) records -- the official compiler.

THE DIGEST is bilingual (English / Arabic) and YEAR-TO-DATE: the "1st Quarter"
issue covers January-March, the "4th Quarter" issue January-December. Values are
"US.$000'S" throughout (2004-2026). Read here:

- **Trade balance table** (Table "Trade Balance During The Period <y0> - <y1>"):
  annual rows for the previous ~10 years and a row per month of the issue year.
  Columns: balance, imports, exports (+ non-petroleum and petroleum exports in the
  2004-2022 issues, kept as the NSO's national groups). The issue year's own
  annual row is a year-to-date sum and is kept only when the issue covers
  January-December.
- **Monthly tables** "Exports / Imports By Commodit(y|ies) ... (Monthly)" and
  "Exports / Imports By Country ... (Monthly)": one column per month and a
  "Total" (year-to-date; kept as the annual figure only in a January-December
  issue). Each row must add up to its own Total (within rounding) or it is
  dropped, never guessed.

BALANCE SIGN. A deficit is printed in parentheses ("(1,932,542)", or "(" and ")"
as separate text items), or with a trailing minus ("497,269-", 2004-2006). The
2023-2025 issues draw the parentheses as graphics: the text layer carries the
bare magnitude, so a balance is kept ONLY when its sign is explicit in the text.

ROW LABELS. A header line ending in ":" with no figures ("Foodstuffs:",
"Industrial Countries:") names the block; the block's "Total" line is filed
under the block name. A header WITH figures ("Minerals:", "COMESA Countries:")
is a row of its own. Generic labels ("Others", "Other ...") are qualified by
their block ("Others (Asia)"). Indented lines (petroleum products' "Jazolin",
"Benzine", "Others") are qualified by their parent row.

MERGE. Issues are parsed oldest first and the newest figure of a key wins
(annual rows are revised from one issue to the next).
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ..schema import KEY
from ._common import row

_UNIT_MULT = 1e3
_MONTHS_FULL = ["january", "february", "march", "april", "may", "june", "july", "august",
                "september", "october", "november", "december"]
_MON_ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
             "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_ARABIC = re.compile(r"[؀-ۿﭐ-﷿ﹰ-﻿]+")
# a figure, optionally in parentheses or with a trailing minus
_NUM = re.compile(r"^\(?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?-?$|^\(?-?\d+(?:\.\d+)?\)?-?$")
_YEAR_ROW = re.compile(r"^\*{0,2}((?:19|20)\d{2})\*{0,2}$")


def _clean(line: str) -> str:
    """Drop Arabic script; keep leading spaces (indentation). A figure that carried
    an Arabic label ("373,822.26المعادن:") keeps only the figure."""
    s = _ARABIC.sub("", line).replace("\u200f", "").replace("\u200e", "").rstrip()
    m = re.match(r"^(\s*\(?-?[\d,]+(?:\.\d+)?\)?-?)[\s:\"*]+$", s)
    return m.group(1) if m else s


def _num(tok: str):
    t = tok.strip()
    neg = t.startswith("(") or t.endswith(")") or t.endswith("-") or t.startswith("-")
    t = t.strip("()-").replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None, False
    explicit = neg
    return (-v if neg else v), explicit


def _page_lines(page) -> list[str]:
    return [_clean(ln) for ln in page.get_text().split("\n")]


def _caption(text: str) -> str:
    caps = [ln.strip() for ln in text.split("\n")
            if re.search(r"(Exports?|Imports?|Impoets|Trade\s+Balance)\b.*\b(During|by|By)\b", ln)]
    return " ".join(caps)


def _caption_last_month(cap: str) -> int | None:
    """Last month a caption covers: "(Jan. - Mar)" -> 3, "During The Year 2006" -> 12."""
    m = re.search(r"Jan[a-z]*\.?\s*-+\s*([A-Za-z]{3})", cap)
    if m and m.group(1).lower() in _MON_ABBR:
        return _MON_ABBR[m.group(1).lower()]
    if re.search(r"During\s+(?:The\s*)?Year", cap, re.I):
        return 12
    return None


def _table_months(cap: str, header: list[int]) -> list[int]:
    """The month columns of a monthly table: the caption's window, provided the
    header prints those months (the 2018-Q1 import tables print a 12-month header
    template over three months of figures)."""
    last = _caption_last_month(cap)
    if not header or header != list(range(1, len(header) + 1)):
        return []
    if last is None:
        return header
    return list(range(1, last + 1)) if last <= len(header) else []


def _issue_window(doc) -> tuple[int, int] | None:
    """(year, last month covered). Primary: the "(Monthly)" tables -- the year their
    caption carries and the last month column their header prints. Captions
    elsewhere also cite comparison periods ("(Jan.-Sept) 2004" in a 2005 issue, a
    contents page repeating last year's titles), so they are only a fallback."""
    from collections import Counter
    monthly = Counter()
    for p in doc:
        t = p.get_text()
        cap = _caption(t)
        if "monthly" in cap.lower() and "government" not in cap.lower():
            yrs = [int(y) for y in re.findall(r"(?:19|20)\d{2}", cap)]
            months = _table_months(cap, _month_header(_page_lines(p)))
            if yrs and months:
                monthly[(max(yrs), len(months))] += 1
    if monthly:
        yr = Counter({y: 0 for y, _ in monthly})
        for (y, _), n in monthly.items():
            yr[y] += n
        year = yr.most_common(1)[0][0]
        return year, max(m for y, m in monthly if y == year)
    seen = Counter()
    for p in doc:
        t = p.get_text()
        for m in re.finditer(r"\(\s*Jan[a-z]*\.?\s*-+\s*([A-Za-z]{3})[a-z]*\.?\s*\)\s*\*{0,2}\s*((?:19|20)\d{2})", t):
            mo, yr = _MON_ABBR.get(m.group(1).lower()), int(m.group(2))
            if mo:
                seen[(yr, mo)] += 1
        for m in re.finditer(r"During\s+(?:The\s*)?Year\s*((?:19|20)\d{2})", t, re.I):
            seen[(int(m.group(1)), 12)] += 1
        for m in re.finditer(r"\(\s*Jan[a-z]*\.?\s*-+\s*([A-Za-z]{3})[a-z]*\.?\s*((?:19|20)\d{2})\s*\)", t):
            mo, yr = _MON_ABBR.get(m.group(1).lower()), int(m.group(2))
            if mo:
                seen[(yr, mo)] += 1
    # captions also cite the comparison year ("(Jan.-Sept) 2004" in a 2005 issue):
    # the issue's own window is the one most captions carry
    return seen.most_common(1)[0][0] if seen else None


# ----------------------------------------------------------------- trade balance
def _trade_balance(doc, year: int, last_month: int, tag: str) -> list[dict]:
    best: list[dict] = []
    for p in doc:
        raw = p.get_text()
        # any "Trade Balance During ..." page; the contents page and the charts yield
        # no rows, and the page with the most rows wins
        if not re.search(r"Trade\s+Balance\s+During", raw, re.I):
            continue
        ncol = 5 if len(re.findall(r"Petroleum", raw, re.I)) >= 2 else 3
        # the months belong to the latest year in THIS page's caption: the 2004-Q1
        # issue reprints "Trade Balance During The Period (Jan. - Dec.) 2003"
        cap_years = [int(y) for m in re.finditer(r"Trade\s+Balance\s+During(.{0,80})", raw, re.I | re.S)
                     for y in re.findall(r"(?:19|20)\d{2}", m.group(1))]
        tb_year = max(cap_years) if cap_years else year
        lines = [ln.strip() for ln in _page_lines(p)]
        out, i = [], 0
        while i < len(lines):
            lab = lines[i]
            ym = _YEAR_ROW.match(lab)
            mo = _MONTHS_FULL.index(lab.lower()) + 1 if lab.lower() in _MONTHS_FULL else None
            if not ym and not mo:
                i += 1
                continue
            vals, j, paren = [], i + 1, False
            while j < len(lines) and len(vals) < ncol:
                tok = lines[j]
                if tok == "(":
                    paren = True
                elif tok == ")":
                    pass
                elif tok == "":
                    pass
                elif tok == "-":
                    vals.append((None, False))    # nil (no petroleum exports since 2021)
                elif _YEAR_ROW.match(tok):
                    break             # the row's year label repeated at its end, or the next row
                elif _NUM.match(tok):
                    v, explicit = _num(tok)
                    if paren and not vals:
                        v, explicit, paren = -abs(v), True, False
                    vals.append((v, explicit))
                else:
                    break
                j += 1
            if len(vals) < ncol:
                i += 1
                continue
            if ym:
                per, freq = str(int(ym.group(1))), "annual"
            else:
                per, freq = f"{tb_year}-{mo:02d}", "monthly"
            (bal, bal_explicit), (imp, _), (exp, _) = vals[0], vals[1], vals[2]
            kw = dict(period=per, frequency=freq, unit="USD", unit_multiplier=_UNIT_MULT,
                      series_code=f"CBoS digest {tag} trade balance")
            if imp is not None:
                out.append(row(tradeflow="import", value=abs(imp), price_basis="cif", **kw))
            if exp is not None:
                out.append(row(tradeflow="export", value=abs(exp), price_basis="fob", **kw))
            # sign explicit (parentheses / minus) or a surplus that the identity shows
            # is positive: a bare magnitude with imports > exports is a lost sign
            if bal is not None and imp is not None and exp is not None and \
                    (bal_explicit or (bal >= 0 and exp >= imp)):
                out.append(row(tradeflow="balance", value=bal, **kw))
            if ncol == 5:
                for (v, _), lab2 in zip(vals[3:5], ("Non-petroleum exports", "Petroleum exports")):
                    if v is not None:
                        out.append(row(tradeflow="export", value=abs(v), commodity=lab2, price_basis="fob",
                                       commodity_classification="national", **kw))
            i = j
        # a period printed twice on one page (the 2012 issue labels its 2012 row
        # "2011**" next to the real 2011 row) is ambiguous: neither is read
        flows: dict = {}
        for r in out:
            flows.setdefault((r["period"], r["tradeflow"], r["commodity"]), set()).add(r["value"])
        twice = {k[0] for k, v in flows.items() if len(v) > 1}
        # the caption year's own annual row is a calendar year only when the page
        # prints all twelve of its months; otherwise it is a year-to-date sum
        nmonths = len({r["period"] for r in out if r["frequency"] == "monthly"})
        if nmonths < 12:
            twice.add(str(tb_year))
        out = [r for r in out if r["period"] not in twice]
        if len(out) > len(best):
            best = out
    return best


# ----------------------------------------------------------------- monthly tables
_GENERIC = re.compile(r"^(others?|other\b.*|total|grand total)$", re.I)


def _month_header(lines: list[str]) -> list[int]:
    seen = []
    for ln in lines:
        t = ln.strip().lower().rstrip(".")
        if t[:3] in _MON_ABBR and (t in _MON_ABBR or t in _MONTHS_FULL or len(t) <= 4):
            m = _MON_ABBR[t[:3]]
            if m not in seen:
                seen.append(m)
        if len(seen) == 12:
            break
    return seen


def _monthly_table(lines: list[str], months: list[int], year: int, full_year: bool,
                   flow: str, kind: str, tag: str, ctx: dict, dropped: list) -> list[dict]:
    k = len(months) + 1
    out = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        lab = raw.strip().strip('"').strip()
        if not lab or _NUM.match(lab) or not re.search(r"[A-Za-z]", lab) or re.match(r"[\d(]", lab):
            i += 1
            continue                  # a figure, or figures fused into a label: not a row label
        low = lab.lower().rstrip(":- ").strip()
        if low in ("commodity", "commodities", "commoeities", "countries", "jan", "total") and i + 1 < len(lines) \
                and not _NUM.match(lines[i + 1].strip()):
            i += 1
            continue
        vals, j = [], i + 1
        while j < len(lines) and len(vals) < k:
            tok = lines[j].strip().strip('"').strip()
            if tok == "":
                j += 1
                continue
            if _NUM.match(tok):
                vals.append(_num(tok)[0])
                j += 1
                continue
            break
        is_header = lab.rstrip().endswith(":") or lab.rstrip().endswith(":-")
        name = re.sub(r"\s+", " ", lab.rstrip(":- ").strip())
        indented = len(raw) - len(raw.lstrip(" ")) >= 3
        if not vals:
            if is_header:
                # "block" names the next Total (consumed by it); "qual" qualifies
                # generic labels until the next header
                ctx["block"], ctx["qual"], ctx["parent"] = name, name, None
            i += 1
            continue
        if len(vals) != k:
            i = j
            continue
        *mvals, total = vals
        if abs(sum(mvals) - total) > max(1.0, 0.002 * abs(total)):
            dropped.append(f"{tag} {flow} {kind} {name!r}: months {sum(mvals):,.2f} vs total {total:,.2f}")
            i = j
            continue
        low = name.lower()
        if low == "grand total":
            i = j
            continue                  # the headline comes from the trade-balance table
        if low == "total":
            if not ctx.get("block"):
                i = j
                continue              # no block header since the last Total: ambiguous, not read
            name, generic = ctx.pop("block"), False
            ctx["qual"] = None        # the block ends with its Total
        else:
            generic = bool(_GENERIC.match(name))
        if indented and ctx.get("parent") and not is_header:
            label = f"{name} ({ctx['parent']})" if generic else name
        elif generic and ctx.get("qual"):
            label = f"{name} ({ctx['qual']})"
        else:
            label = name              # incl. a top-level "Others" (outside any block)
        if not indented and not is_header and low != "total":
            ctx["parent"] = name
        if is_header:
            ctx["parent"] = name
        if kind == "commodity":
            kw = dict(commodity=label, commodity_classification="national")
        else:
            group = is_header or low == "total" or generic
            kw = dict(partner=label, partner_type="group" if group else "country")
        common = dict(tradeflow=flow, unit="USD", unit_multiplier=_UNIT_MULT,
                      price_basis={"export": "fob", "import": "cif"}[flow],
                      series_code=f"CBoS digest {tag} {flow}s by {kind}", **kw)
        for m, v in zip(months, mvals):
            out.append(row(period=f"{year}-{m:02d}", frequency="monthly", value=v, **common))
        if full_year:
            out.append(row(period=str(year), frequency="annual", value=total, **common))
        i = j
    return out


def parse_issue(path: str) -> tuple[tuple[int, int], pd.DataFrame, list]:
    import fitz
    doc = fitz.open(path)
    try:
        win = _issue_window(doc)
        if not win:
            raise ValueError(f"Sudan digest {path}: no issue window (year / months) found")
        year, last = win
        tag = f"{year} Jan-{['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][last]}"
        out = _trade_balance(doc, year, last, tag)
        dropped: list = []
        section, kind, ctx, table_cap = None, None, {}, ""
        for p in doc:
            raw = p.get_text()
            if re.search(r"First\s+Section|Section\s*\(A\)", raw) and len(raw) < 600:
                section, kind = "export", None
                continue
            if re.search(r"Second\s+Section|Section\s*\(B\)", raw) and len(raw) < 600:
                section, kind = "import", None
                continue
            low = _caption(raw).lower()
            if low and "monthly" in low and "government" not in low and "&" not in low:
                section = "import" if "imp" in low else "export"
                kind = ("country" if "countr" in low else
                        "commodity" if ("commod" in low or "commoe" in low or "commed" in low) else None)
                ctx, table_cap = {}, low
            elif low:
                kind = None               # another table (quarterly, by country & commodity, ...)
            elif not re.search(r"Cont'?d|تابع", raw):
                kind = None               # chart or section page
            if not kind or not section:
                continue
            lines = _page_lines(p)
            months = _table_months(table_cap, _month_header(lines))
            if not months or len(months) != last:
                continue              # not this issue's window: never re-label months
            out += _monthly_table(lines, months, year, last == 12, section, kind, tag, ctx, dropped)
    finally:
        doc.close()
    df = pd.DataFrame.from_records(out)
    if not df.empty:
        k = [c for c in KEY if c in df.columns]
        nval = df.groupby(k, dropna=False)["value"].transform("nunique")
        for lab in sorted(set(df.loc[nval > 1, "commodity"] + " / " + df.loc[nval > 1, "partner"])):
            dropped.append(f"{tag}: two different figures under one label, not read: {lab}")
        df = df[nval <= 1].drop_duplicates(k).reset_index(drop=True)
    return win, df, dropped


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    parsed = []
    for p in {path, *(extras or [])}:
        if not p.lower().endswith(".pdf"):
            continue
        win, df, dropped = parse_issue(p)
        if dropped:
            print(f"  [sudan] {len(dropped)} row(s) dropped in {os.path.basename(p)}"
                  f" (e.g. {dropped[0]})")
        parsed.append((win, df))
    parsed.sort(key=lambda x: x[0])
    frames = [df for _, df in parsed if not df.empty]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates([c for c in KEY if c in df.columns], keep="last").reset_index(drop=True)
