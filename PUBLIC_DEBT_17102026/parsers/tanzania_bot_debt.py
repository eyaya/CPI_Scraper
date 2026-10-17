"""Tanzania — Bank of Tanzania (BoT), Monthly Economic Review, statistical
Table A10 "National Debt Developments" (Millions of USD).

PUBLISHER: Bank of Tanzania; the table is credited "Source: Ministry of
Finance, and Bank of Tanzania" -- both accepted official compilers.

COVERAGE AS PUBLISHED: BoT calls it NATIONAL debt, and it is wider than
public debt: the external stock is "public and private" (section 3 splits it
by borrower -- central government, public corporations, PRIVATE SECTOR), while
the domestic stock is the Government's. "13. Total debt stock" = external
(public + private) + government domestic. Recorded as such in `coverage`, and
the borrower split is kept so the public part can be read off.

WHAT IS READ: every STOCK row of the table, for each of the 13 monthly
columns printed (a rolling window -- merge-on-write accumulates history):

* 1. Overall total external debt committed, disbursed outstanding,
  undisbursed;
* 2-5. disbursed external debt by creditor category, borrower category,
  currency and use of funds;
* 10. external debt arrears by creditor category (principal and interest);
* 11. external debt stock, 12. domestic debt stock, 13. total debt stock.

Sub-rows repeat across sections ("Bilateral debt" is a creditor class and an
arrears class), so every component is prefixed with its section heading; and
inside section 10 the creditor rows repeat under "Principal" and "Interest",
so those carry the sub-heading too ("...: Interest: Bilateral debt").

NOT READ: sections 6-9 (disbursements, debt service, net flows, net
transfers) are FLOWS during the month, not stocks; the end-of-period exchange
rate is not a debt figure.

BACK ISSUES (added 2026-10-12): the descriptor passes one issue per year
back to the July 2023 issue (window June 2022 - June 2023), plus the August
2025 issue to bridge July 2025. Issues before mid-2022 are NOT read: the 2022
issue prints the table (then "A9") as an image, and the 2021 issue ("A7")
uses different section labels and misprints its header ("Oct-20 Nov-21 Dec-21
Jan-21") -- the consecutive-month guard below would refuse it anyway.

DATING: column heads "Aug-25" ... "Jul-26r" ... "Aug-26p" -> YYYY-MM. The r
(revised) / p (provisional) flags are NOT carried into any key column: a later
issue that revises or firms up a month must REPLACE it by merge-on-write, and
a flag in `series_code` (part of the merge key) would leave the provisional
row standing beside the final one.

CHECKS: each of sections 2-5 sums to its printed total (within 0.25 -- the
table's own rounding: section 5 prints Feb-26 as 35,069.2 while sections 2-4
print 35,069.3, kept as printed); committed = disbursed + undisbursed; 11 + 12
= 13. A row without one value per column raises.

CROSS-CHECK (September 2026 issue): Aug-26p total debt 52,224.4, external
36,731.5, domestic 15,493.0; central-government external DOD 30,671.3;
multilateral 21,842.7.
"""
from __future__ import annotations

import re

import pdfplumber
import pandas as pd

_UNIT = "USD million"
# Month labels are usually three letters, but some issues print "Sept-24" and
# "June-25"; the first three letters always name the month.
_HEAD = re.compile(r"^Item((?:\s+[A-Z][a-z]{2,3}-\d{2}[rp]?)+)\s*$")
_MON = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
     "Nov", "Dec"], 1)}
_NUM = r"-?\d{1,3}(?:,\d{3})*\.\d"
_SECTION = re.compile(r"^(\d{1,2})\.\s+(.*?)\d?\s*$")
_STOCK_SECTIONS = {1, 2, 3, 4, 5, 10, 11, 12, 13}


def _period(h: str) -> tuple[str, str]:
    m = re.fullmatch(r"([A-Z][a-z]{2,3})-(\d{2})([rp]?)", h)
    return f"20{m.group(2)}-{_MON[m.group(1)[:3]]:02d}", m.group(3)


def _page_text(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            # Table A10 in current issues; A9 in issues up to mid-2022.
            if (re.search(r"Table A\d+: National Debt Developments", t)
                    and "13. Total debt stock" in t):
                return t
    raise ValueError("BoT MER: Table A10 not found")


_KEY = ["component", "period", "frequency", "measure", "unit", "series_code"]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """Read the current issue and every back issue passed as an extra.

    Each issue is a 13-month window, so issues overlap. Where two issues print
    the same month, the NEWEST issue (the one whose window ends latest) wins,
    as a later revision should; the number of cells a later issue changed is
    printed so revisions stay visible.
    """
    frames = []
    for i, p in enumerate([path, *(extras or [])]):
        # The current issue must read whole. A back issue that does not is
        # read for its headline stocks only (`parse_headline`, below), and
        # one that fails that too is skipped with a message.
        try:
            rows = _parse_one(p)
        except ValueError as e:
            if i == 0:
                raise
            name = p.replace(chr(92), "/").rsplit("/", 1)[-1]
            try:
                rows = parse_headline(p)
                print(f"  [tanzania] {name}: headline stocks only ({e})")
            except ValueError as e2:
                print(f"  [tanzania] back issue skipped ({name}): {e2}")
                continue
        if rows:
            df = pd.DataFrame(rows)
            df["_issue_end"] = df["period"].max()
            frames.append(df)
    df = pd.concat(frames, ignore_index=True).sort_values("_issue_end")
    dup = df[df.duplicated(_KEY, keep=False)]
    if len(dup):
        changed = int((dup.groupby(_KEY)["value"].nunique() > 1).sum())
        if changed:
            print(f"[tanzania] {changed} cell(s) revised by a later MER issue; "
                  f"the newest issue's value is kept")
    return df.drop_duplicates(_KEY, keep="last").drop(columns="_issue_end")


def _parse_one(path: str) -> list[dict]:
    lines = [ln.strip() for ln in _page_text(path).splitlines()]
    head = next((m for m in map(_HEAD.match, lines) if m), None)
    if head is None:
        raise ValueError("BoT A10: column header not found")
    cols = [_period(h) for h in head.group(1).split()]
    n = len(cols)
    # THE HEADER MUST RUN MONTH BY MONTH. The July 2021 issue prints "Oct-20
    # Nov-21 Dec-21 Jan-21": read as printed, it would file Nov/Dec 2020 under
    # 2021 and collide with the real months. A non-consecutive header raises.
    seq = [int(p[:4]) * 12 + int(p[5:]) for p, _ in cols]
    if any(b - a != 1 for a, b in zip(seq, seq[1:])):
        raise ValueError(f"BoT A10: header months are not consecutive: "
                         f"{[p for p, _ in cols]}")
    row_re = re.compile(rf"^(.*?)\s+((?:{_NUM}\s+){{{n - 1}}}{_NUM})$")

    section, sec_no, sub, out, table = None, None, None, [], {}
    for ln in lines:
        m = row_re.match(ln)
        if not m:
            continue
        label = m.group(1).strip()
        vals = [float(v.replace(",", "")) for v in m.group(2).split()]
        sm = _SECTION.match(label)
        if sm:
            sec_no, section, sub = int(sm.group(1)), sm.group(2).strip(), None
            comp = section
        else:
            if section is None:
                continue
            if sec_no == 10 and label in ("Principal", "Interest"):
                sub = label
                comp = f"{section}: {label}"
            elif sub:
                comp = f"{section}: {sub}: {label}"
            else:
                comp = f"{section}: {label}"
        table[comp] = vals
        if sec_no not in _STOCK_SECTIONS or label.startswith("End of period"):
            continue
        for (period, flag), v in zip(cols, vals):
            out.append({"component": comp, "period": period,
                        "frequency": "monthly", "measure": "stock", "value": v,
                        "unit": _UNIT,
                        "series_code": "BoT MER Table A10"})

    _check(table, cols)
    if len(out) < 30 * n:
        raise ValueError(f"BoT A10: only {len(out)} stock values read")
    return out


def _check(t: dict, cols) -> None:
    def g(k):
        if k not in t:
            raise ValueError(f"BoT A10: row {k!r} not read")
        return t[k]
    dod = g("Overal total external debt committed: Disbursed outstanding debt")
    und = g("Overal total external debt committed: Undisbursed debt")
    com = g("Overal total external debt committed")
    for j, (p, _) in enumerate(cols):
        if abs(dod[j] + und[j] - com[j]) > 0.25:
            raise ValueError(f"BoT A10 {p}: committed != disbursed + undisbursed")
        if abs(g("External debt stock")[j] + g("Domestic debt stock")[j]
               - g("Total debt stock")[j]) > 0.25:
            raise ValueError(f"BoT A10 {p}: external + domestic != total")
    for sec in ("Disbursed external debt by creditor category",
                "Disbursed external debt by borrower category",
                "Disbursed external debt by currency",
                "Disbursed external debt by use of funds"):
        parts = [v for k, v in t.items() if k.startswith(sec + ": ")]
        for j, (p, _) in enumerate(cols):
            if abs(sum(x[j] for x in parts) - g(sec)[j]) > 0.25:
                raise ValueError(f"BoT A10 {p}: {sec} parts do not sum to total")


# --- OLDER ISSUES: headline stocks only ------------------------------------
# Issues before mid-2022 number the table A7/A9 and use other section
# structures (no currency section in 2020; "Overal external debt committed",
# "Disbursded ..."), so their sections cannot be filed under today's labels
# without relabelling. Their HEADLINE rows -- "11. External debt stock", "12.
# Domestic debt stock", "13. Total debt stock" -- carry the same labels in
# every issue and are read alone, through `parse_headline`. The month header
# must still run consecutively (the July 2021 issue's misprinted header is
# refused) and 11 + 12 = 13 must hold; an issue whose cells are fused in the
# text layer (July 2019: "28,063.128,064.6...") fails the row match and is
# refused, never split by guesswork. "P"/"R" flags are dropped as in _period.
_HEAD_OLD = re.compile(r"^Item((?:\s+[A-Z][a-z]{2,3}-\d{2}[rpRP]?)+)\s*$")
_HEADLINE = {"11": "External debt stock", "12": "Domestic debt stock",
             "13": "Total debt stock"}


def parse_headline(path: str) -> list[dict]:
    text = None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if re.search(r"Table A\d+: National Debt Developments", t) \
                    and "13. Total debt stock" in t:
                text = t
                break
    if text is None:
        raise ValueError("BoT MER: National Debt Developments table not found")
    lines = [ln.strip() for ln in text.splitlines()]
    head = next((m for m in map(_HEAD_OLD.match, lines) if m), None)
    if head is None:
        raise ValueError("BoT (old issue): column header not found")
    cols = [_period(re.sub(r"[RP]$", lambda m: m.group(0).lower(), h))[0]
            for h in head.group(1).split()]
    seq = [int(p[:4]) * 12 + int(p[5:]) for p in cols]
    if any(b - a != 1 for a, b in zip(seq, seq[1:])):
        raise ValueError(f"BoT (old issue): header months not consecutive: {cols}")
    n = len(cols)
    got = {}
    for no, lab in _HEADLINE.items():
        rx = re.compile(rf"^{no}\.\s+{lab}\d?\s+((?:{_NUM}\s+){{{n - 1}}}{_NUM})$")
        m = next((m for m in map(rx.match, lines) if m), None)
        if m is None:
            raise ValueError(f"BoT (old issue): row {no}. {lab} not read")
        got[lab] = [float(v.replace(",", "")) for v in m.group(1).split()]
    for j, p in enumerate(cols):
        if abs(got["External debt stock"][j] + got["Domestic debt stock"][j]
               - got["Total debt stock"][j]) > 0.25:
            raise ValueError(f"BoT (old issue) {p}: external + domestic != total")
    return [{"component": lab, "period": p, "frequency": "monthly",
             "measure": "stock", "value": v, "unit": _UNIT,
             "series_code": "BoT MER Table A10"}
            for lab, vals in got.items() for p, v in zip(cols, vals)]
