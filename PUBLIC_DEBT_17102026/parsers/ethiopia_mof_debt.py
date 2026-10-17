"""Ethiopia — Ministry of Finance (Debt Management Directorate), Public Sector
Debt Statistical Bulletin (quarterly, numbered), Table 25 "Total Public Debt
Outstanding" (Mn USD).

PUBLISHER: Ministry of Finance, DMD (an accepted official compiler).

COVERAGE AS PUBLISHED: PUBLIC SECTOR debt -- central government AND
state-owned enterprises, external and domestic. Each sub-row keeps its
section ("External debt: State-owned enterprises"), so the central-government
perimeter can be read off. Domestic debt is converted to USD by MoF at the
end-period exchange rate (the table's footnote); the USD figure is what is
published and is what is collected.

COLUMNS: four Ethiopian fiscal years and the latest quarter-end, e.g.
"2021/22R 2022/23R 2023/24R 2024/2025R 31/12/2025p" -- each a USD amount and a
% of total. Fiscal years end on 7 July (Hamle 30); a fiscal-year column is
dated to the year it ENDS ("2021/22" -> 2022, annual) and the quarter-end
column to its month ("31/12/2025" -> 2025-12, monthly). R (revised) and p
(provisional) flags are not part of the key: the next bulletin replaces them by
merge-on-write.

MEASURES: stock (USD million) and share (% of total public debt) as printed.

TRAP: two labels wrap ("State Owened" / "Enterprises <numbers>") and two
headings sit alone above their numbers ("Total Public Debt" / "<numbers>"),
so a pending label is joined to the next numeric line. The spelling "Owened"
is MoF's; the component name is normalised to "State-owned enterprises" only
in its section-qualified form, with the source label kept in this docstring.

CHECKS: external + domestic = total; central government + SOEs = each of
external and domestic (within 0.05); every share sums likewise (within 0.05).

CROSS-CHECK (Bulletin No. 56): total public debt 31/12/2025 USD 52,121.32 m;
external 34,456.17 (66.11%); domestic 17,665.15; 2021/22 total 57,665.75.
"""
from __future__ import annotations

import re

import pdfplumber
import pandas as pd

_UNIT = "USD million"
_HEAD = re.compile(r"(\d{4})/(\d{2,4})[RrPp]?|(\d{2})/(\d{2})/(\d{4})[RrPp]?")
_NUM = r"\d{1,3}(?:,\d{3})*\.\d{2}"
_SECTIONS = {"Total Public Debt": "Total public debt",
             "External Debt": "External debt",
             "Domestic Debt": "Domestic debt"}
_SUBS = {"Central Government": "Central government",
         "State Owened Enterprises": "State-owned enterprises"}


def _text(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            if "TOTAL PUBLIC DEBT OUTSTANDING" in t and "Total Public Debt" in t:
                return t
    raise ValueError("MoF Ethiopia: Table 25 not found")


def _periods(line: str) -> list[tuple[str, str]]:
    out = []
    for m in _HEAD.finditer(line):
        if m.group(1):
            end = m.group(2)
            year = int(end) if len(end) == 4 else int(m.group(1)[:2] + end)
            out.append((str(year), "annual"))
        else:
            out.append((f"{m.group(5)}-{m.group(4)}", "monthly"))
    return out


def _parse_one(path: str) -> list[dict]:
    lines = [ln.strip() for ln in _text(path).splitlines() if ln.strip()]
    # The column header is the line with the MOST period stamps (the subtitle
    # "2021/22 - 2024/25 and 31/12/2025" names only the range).
    hdr = max(lines, key=lambda ln: len(_HEAD.findall(ln)))
    if len(_HEAD.findall(hdr)) < 2:
        raise ValueError("MoF Ethiopia T25: period header not found")
    cols = _periods(hdr)
    n = len(cols)
    row = re.compile(rf"^(.*?)\s*((?:{_NUM}\s+)+{_NUM})$")
    table, pending, section = {}, "", None
    for ln in lines:
        m = row.match(ln)
        if not m:
            # Only a heading printed alone, or the first half of a wrapped
            # label, carries over to the next numeric line; titles and units
            # lines reset it.
            head = re.sub(r"\d+$", "", ln).strip()        # "Domestic Debt1"
            pending = head if (head in _SECTIONS or head == "State Owened") else ""
            continue
        label = f"{pending} {m.group(1)}".strip() if m.group(1) else pending
        pending = ""
        label = re.sub(r"\d+$", "", label).strip()          # "Domestic Debt1"
        nums = [float(x.replace(",", "")) for x in m.group(2).split()]
        if len(nums) != 2 * n:
            raise ValueError(f"MoF Ethiopia T25: {label!r} has {len(nums)} values "
                             f"for {n} periods")
        if label in _SECTIONS:
            section = _SECTIONS[label]
            comp = section
        elif label in _SUBS and section:
            comp = f"{section}: {_SUBS[label]}"
        else:
            raise ValueError(f"MoF Ethiopia T25: unexpected row {label!r}")
        table[comp] = nums
    need = ["Total public debt", "External debt", "Domestic debt"] + \
        [f"{s}: {x}" for s in ("External debt", "Domestic debt")
         for x in _SUBS.values()]
    if set(table) != set(need):
        raise ValueError(f"MoF Ethiopia T25: rows {sorted(table)}")
    for k in range(2 * n):
        if abs(table["External debt"][k] + table["Domestic debt"][k]
               - table["Total public debt"][k]) > 0.05:
            raise ValueError(f"MoF Ethiopia T25 col {k}: external + domestic != total")
        for s in ("External debt", "Domestic debt"):
            parts = sum(table[f"{s}: {x}"][k] for x in _SUBS.values())
            if abs(parts - table[s][k]) > 0.05:
                raise ValueError(f"MoF Ethiopia T25 col {k}: {s} parts != total")
    out = []
    for comp, nums in table.items():
        for j, (period, freq) in enumerate(cols):
            for val, meas, unit in ((nums[2 * j], "stock", _UNIT),
                                    (nums[2 * j + 1], "share", "percent")):
                out.append({"component": comp, "period": period, "frequency": freq,
                            "measure": meas, "value": val, "unit": unit,
                            "series_code": "MoF PSDSB Table 25"})
    return out


_KEY = ["component", "period", "frequency", "measure", "unit"]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The current bulletin must parse. BACK ISSUES (extras, newest first)
    each print four fiscal years and a quarter-end, so they overlap: where two
    bulletins print the same period, the NEWER one (listed earlier) wins --
    MoF revises earlier years (FY2017/18 total: 49,445.07 in No. 29, 49,372.95
    in No. 34) -- and the number of revised cells is printed. A back issue
    whose Table 25 does not read is skipped with a message (No. 48 wraps
    "State Owened / Enterprises" the other way round)."""
    frames = [pd.DataFrame(_parse_one(path))]
    for p in extras or []:
        try:
            frames.append(pd.DataFrame(_parse_one(p)))
        except ValueError as e:
            name = p.replace(chr(92), "/").rsplit("/", 1)[-1]
            print(f"  [ethiopia] back issue skipped ({name}): {e}")
    df = pd.concat(frames, ignore_index=True)
    first = df.drop_duplicates(_KEY, keep="first")
    changed = int((df.groupby(_KEY)["value"].nunique() > 1).sum())
    if changed:
        print(f"  [ethiopia] {changed} cell(s) revised by a newer bulletin; newest kept")
    return first.reset_index(drop=True)
