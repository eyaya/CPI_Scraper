"""Ghana -- Bank of Ghana (BoG), "Summary of Economic and Financial Data",
"Government Fiscal Operations" page, "Public Debt" block. Bi-monthly PDF, each
issue printing a 12-column window of months (bog.gov.gh, WordPress uploads).

PUBLISHER: the Bank of Ghana (an accepted official national compiler under this
indicator's source policy). The block's own source line reads "Ministry of
Finance, Bank of Ghana, Ghana Statistical Service".

A SEPARATE SERIES FROM GSS's StatsBank table (`ghana_pxweb_debt`, US$ million,
2014-01..2024-06). The BoG block extends the record past mid-2024, but it is
BoG's publication, in US$/GHC BILLION, under BoG's definitions -- so it carries
its own `series_code` and is never merged into, or chained with, the GSS rows.

COVERAGE CHANGES BETWEEN ISSUES, and each issue says so in its own footnote:
* "Total Public Debt is defined as Central Government debt INCLUDING State
  Owned Enterprises/Special Purpose Vehicles Debt" (2024 onward);
* "... Central Government debt EXCLUDING State Owned Enterprises/Special
  Purpose Vehicles Debt" (2023);
* "Total Public Debt excludes ESLA Bonds" (2021).
`coverage` is read from each issue's footnote and set per row, so the same
month under two definitions (June 2024: GHC 742.0bn in the July 2024 issue,
744.8bn in July 2025) is kept as two distinct series, never overwritten. An
issue with no such footnote is recorded as "perimeter not stated".

COMPONENTS: Total Public Debt, External Debt (each in USD and GHC billion),
Domestic Debt (GHC billion), and each one's "percent of GDP" line, which is
filed `share_of_gdp` against the component above it. Nominal GDP is not
collected (it is a denominator, not debt).

DATING: columns are dated by the issue's own header ("2025:07 2025:08 ...").
The window is NOT always consecutive -- September 2026 skips 2025:11 -- so a
column is never dated by position. A row whose value count differs from the
header's (March 2023 prints 11 values under 12 months) cannot be aligned and
is skipped, never shifted. Where issues overlap with the same coverage, the
NEWEST issue wins ("Data subject to revision").

LABEL NOISE: the text layer injects stray glyphs from a side banner
("ExternPal Debt", "ubillion USD", "P%", and inside numbers: "2C021:09",
"9.L0"). A single letter wedged between digits is dropped before reading, and
rows are matched on their key phrases, not their exact text. May 2023 prints
"···" placeholders for missing months, so its rows cannot be aligned and are
skipped.

CROSS-CHECK (printed): September 2026 issue, 2026:07 total public debt USD
62.8bn / GHC 733.9bn (45.9% of GDP), external USD 28.8bn, domestic GHC
396.7bn; July 2024 issue, 2024:06 total GHC 742.0bn (70.6% of GDP).
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
     "nov", "dec"], 1)}
_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_HDR = re.compile(r"^\s*(\d{4}:\d{2}(?:\s+\d{4}:\d{2})+)\s*$")
SERIES = "BoG Summary of Economic and Financial Data"


def _coverage(text: str) -> str:
    flat = re.sub(r"\s+", "", text)
    m = re.search(r"TotalPublicDebtis(?:de\S{0,8}?ned|defined)as(CentralGovernment"
                  r"debt(in|ex)cluding)", flat, re.I)
    if m:
        verb = "including" if m.group(2).lower() == "in" else "excluding"
        return (f"Central government debt {verb} State-Owned Enterprises / "
                f"Special Purpose Vehicles debt (BoG definition)")
    if re.search(r"TotalPublicDebtexcludesESLA", flat, re.I):
        return "Total public debt excluding ESLA bonds (BoG note)"
    return "Public debt (perimeter not stated in this BoG issue)"


def _component(line: str) -> tuple[str, str] | None:
    low = line.lower()
    cur = "USD" if "usd" in low else ("GHC" if re.search(r"gh[c¢]", low) else None)
    if cur is None or "billion" not in low and "bn" not in low:
        return None
    if "total public debt" in low or re.search(r"total\s*public\s*debt", low):
        return "Total Public Debt", cur
    if "domestic" in low and "debt" in low:
        return "Domestic Debt", cur
    if "ext" in low and "debt" in low:
        return "External Debt", cur
    return None


def _deglyph(line: str) -> str:
    """Drop a stray banner glyph wedged between digits ("2C021:09" -> "2021:09",
    "9.L0" -> "9.0") so neither a date nor a value is misread."""
    return re.sub(r"(?<=[\d.:])[A-Za-z](?=[\d.:])", "", line)


def _issue_key(path: str) -> tuple:
    """Order issues oldest -> newest, from the month-year in the file name."""
    name = os.path.basename(path).lower()
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z.]*-(\d{4})", name)
    if not m:
        return (9999, 99, name)            # the latest-issue primary sorts last
    return (int(m.group(2)), _MONTHS[m.group(1)], name)


def _parse_one(path: str) -> list[dict]:
    where = os.path.basename(path)
    with pdfplumber.open(path) as pdf:
        page = next((p.extract_text() or "" for p in pdf.pages
                     if "Public Debt" in (p.extract_text() or "")
                     and "percent of GDP" in (p.extract_text() or "")), None)
        full = "\n".join(p.extract_text() or "" for p in pdf.pages)
    if page is None:
        print(f"[ghana_bog] {where}: no Public Debt block -- skipped")
        return []
    lines = [_deglyph(ln) for ln in page.splitlines()]
    hdr = next((m.group(1) for ln in lines for m in [_HDR.match(ln)] if m), None)
    if hdr is None:
        print(f"[ghana_bog] {where}: no YYYY:MM header on the debt page -- skipped")
        return []
    months = [f"{h[:4]}-{h[5:]}" for h in hdr.split()]
    coverage = _coverage(full)

    start = next((i for i, ln in enumerate(lines)
                  if re.match(r"^\s*Public\s*Debt\s*[A-Z]?\s*$", ln)), None)
    if start is None:
        print(f"[ghana_bog] {where}: no 'Public Debt' heading -- skipped")
        return []
    recs, last = [], None
    for ln in lines[start + 1:]:
        s = ln.strip()
        if re.match(r"^(Annual Nominal GDP|Source|NOTE|Note|\d{1,2}Total)", s):
            break
        nums = _NUM.findall(re.sub(r"\d{4}:\d{2}", "", s.split("billion")[-1]
                                   if "billion" in s else s.split("%")[-1]))
        if "percent of gdp" in s.lower():
            if last is None:
                continue                  # a stray ratio line with no debt row above it
            comp = last
            measure, unit = "share_of_gdp", "percent"
            last = None                   # one ratio per component
        else:
            c = _component(s)
            if c is None:
                last = None
                continue
            comp = c[0]
            measure, unit = "stock", f"{c[1]} billion"
            last = comp if c[1] == "GHC" else last
        if len(nums) != len(months):
            print(f"[ghana_bog] {where}: {comp} {measure} has {len(nums)} values "
                  f"for {len(months)} months -- skipped, cannot be aligned")
            continue
        for mth, v in zip(months, nums):
            recs.append(dict(component=comp, period=mth, frequency="monthly",
                             measure=measure, value=float(v), unit=unit,
                             series_code=SERIES, coverage=coverage))
    if not recs:
        print(f"[ghana_bog] {where}: Public Debt block read no rows -- skipped")
    return recs


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in sorted([path, *(extras or [])], key=_issue_key):
        got = _parse_one(p)
        # An old issue in another layout is skipped with a message; the
        # CURRENT issue reading nothing means the layout changed -- raise.
        if p == path and not got:
            raise ValueError(f"ghana_bog: the current issue {os.path.basename(path)} "
                             f"read no Public Debt rows -- layout changed?")
        rows += got
    df = pd.DataFrame(rows)
    key = ["coverage", "component", "period", "frequency", "measure", "unit",
           "series_code"]
    # Overlapping 12-month windows: the newest issue's figure wins.
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
