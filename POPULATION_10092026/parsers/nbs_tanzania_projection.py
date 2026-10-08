"""NBS Tanzania -- National Population Projection Report 2023-2050 (based on
the 2022 Population and Housing Census), annex tables A5.n / B5.n / C5.n:
"Population Projection by Five Year Age Groups and Sex: <year>" for Tanzania,
Tanzania Mainland and Tanzania Zanzibar, one table per year 2023-2050.

Added 2026-10-06 as an extra of the 2022 census source.

TWO TABLES SHARE EACH PAGE, AND THE TEXT STREAM LIES ABOUT WHICH IS WHICH.
PyMuPDF's reading order emits both captions first and then both data blocks,
the LOWER block first -- read in order, 2024's figures (66,278,276) would be
filed under 2023 (64,416,042). So every data row is placed by PAGE GEOMETRY:
a block belongs to the nearest caption ABOVE it. The years must then run
2023..2050 with a total that grows every year (checked).

Only the "Total" column group (Both sexes / Male / Female) is read; the Rural
and Urban groups are deferred (no locality column), as for the census. Every
table's 17 age bands must sum to its printed Total row, and Male + Female =
Both sexes on every row.

GEOGRAPHIES OVERLAP: Tanzania = Mainland + Zanzibar. All three are collected
as published ("Total country", "Tanzania Mainland", "Tanzania Zanzibar") and
must never be summed together.

series_type = projection.
"""
from __future__ import annotations

import re

import fitz

# "Table A5. 12" / "B5. 11": NBS sometimes prints a space after the dot.
_CAP = re.compile(r"^Table\s+([ABC])5\.\s*(\d+)\s+.*Population Projection by Five "
                  r"Year Age Groups and Sex:?\s*(20\d\d)", re.I)
_GEO = {"A": "Total country", "B": "Tanzania Mainland", "C": "Tanzania Zanzibar"}
_AGES = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
         "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
         "80+"]
_NUM = re.compile(r"^\d{1,3}(,\d{3})*$")
_LABEL_X = 115          # age labels sit left of this; values to the right


def _lines(page) -> list[tuple[float, str, list[float]]]:
    """(y, label, values) per visual line, values ordered left to right."""
    rows: dict[int, list] = {}
    for x0, y0, x1, y1, w, *_ in page.get_text("words"):
        rows.setdefault(round((y0 + y1) / 2), []).append((x0, w))
    merged: list[list] = []
    for y in sorted(rows):
        if merged and y - merged[-1][0] <= 2:
            merged[-1][1].extend(rows[y])
        else:
            merged.append([y, list(rows[y])])
    out = []
    for y, words in merged:
        words.sort()
        # A word is a VALUE if it lies right of the label column OR is a
        # comma-grouped number: a Total row's first value can sit inside the
        # label column ("Total 101,679,464 ..."), while the age labels' own
        # digits ("0 - 4", "5 -9") must stay labels.
        is_val = lambda x, w: _NUM.match(w) and (x >= _LABEL_X or "," in w)
        label = " ".join(w for x, w in words
                         if x < _LABEL_X and not is_val(x, w))
        vals = [float(w.replace(",", "")) for x, w in words if is_val(x, w)]
        out.append((y, label, vals, " ".join(w for _, w in words)))
    return out


def _captions(lines) -> list[tuple[float, str, str]]:
    """(y, series, year) per caption. A caption can WRAP, its year on the
    next line ("Table A5.20 Tanzania:" / "...Sex: 2042"), so a "Table X5.n"
    line is joined with the lines after it until the pattern matches. Table-
    of-contents lines end in a page number after dot leaders and are skipped."""
    caps = []
    for k, (y, _, _, text) in enumerate(lines):
        if not re.match(r"^Table\s+[ABC]5\.\s*\d+", text) or ".." in text:
            continue
        joined = text
        for _, _, _, nxt in lines[k + 1:k + 4]:
            m = _CAP.match(joined)
            if m:
                break
            joined = f"{joined} {nxt}"
        m = _CAP.match(joined)
        if not m:
            raise ValueError(f"NBS projection: unreadable caption {text!r}")
        caps.append((y, m.group(1), m.group(3)))
    return caps


def parse_projection(path: str) -> list[dict]:
    tables: dict[tuple[str, str], dict] = {}
    with fitz.open(path) as doc:
        for page in doc:
            lines = _lines(page)
            caps = _captions(lines)
            if not caps:
                continue
            for y, label, vals, _ in lines:
                lab = re.sub(r"\s+", "", label)
                if lab != "Total" and lab not in _AGES:
                    continue
                if len(vals) < 3:
                    continue
                above = [c for c in caps if c[0] < y]
                if not above:
                    continue
                _, series, year = max(above)
                t = tables.setdefault((series, year), {})
                if lab in t:
                    raise ValueError(f"NBS projection {series}5 {year}: row "
                                     f"{lab!r} read twice")
                t[lab] = vals[:3]
    out = []
    for series in "ABC":
        prev = None
        years = sorted(y for s, y in tables if s == series)
        if years != [str(y) for y in range(2023, 2051)]:
            raise ValueError(f"NBS projection {series}5: years {years[:3]}..")
        for year in years:
            t = tables[(series, year)]
            if set(t) != set(_AGES) | {"Total"}:
                raise ValueError(f"NBS projection {series}5 {year}: rows "
                                 f"{sorted((set(_AGES) | {'Total'}) ^ set(t))} differ")
            for k, sex in enumerate(("total", "male", "female")):
                s = sum(t[a][k] for a in _AGES)
                if abs(s - t["Total"][k]) > 3:
                    raise ValueError(f"NBS projection {series}5 {year} {sex}: "
                                     f"bands {s} != Total {t['Total'][k]}")
            for lab, (b, m, f) in t.items():
                if abs(m + f - b) > 3:
                    raise ValueError(f"NBS projection {series}5 {year} {lab}: "
                                     f"{m} + {f} != {b}")
            if prev is not None and t["Total"][0] <= prev:
                raise ValueError(f"NBS projection {series}5 {year}: total does "
                                 f"not grow -- a year/block mismatch")
            prev = t["Total"][0]
            for lab, vals in t.items():
                for sex, v in zip(("total", "male", "female"), vals):
                    out.append({"series_type": "projection", "sex": sex,
                                "age_group": lab, "geography": _GEO[series],
                                "period": year, "frequency": "annual",
                                "measure": "count", "value": v,
                                "unit": "persons",
                                "series_code": f"NBS_TZ_PROJ_{series}5"})
    return out
