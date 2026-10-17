"""INS DR Congo -- Annuaire statistique 2015, section 2.1.1 "Etat de la
population": the 2010-2014 BACK-SERIES of the official population estimates.

Added 2026-10-13 as a SECOND DR Congo descriptor (drc_backseries.yaml) beside
drc.yaml, which reads the same yearbook's 2015 tables (1.29-1.56). Same file,
same Wayback `id_` capture of INS's own PDF (ins-rdc.org answers 403).

* Tableau 2.1         province x sex, 2010-2015 (thousands);
* Tableaux 2.2-2.6    province x sex x 5-year age group, one table per year
                      2010-2014 (thousands).

2015 IS NOT READ HERE. Tableau 2.1's 2015 column and Tableau 2.7 (2015 by age)
repeat figures drc.yaml already collects from 1.29-1.56 under the same merge
key; reading them twice would let one descriptor overwrite the other.

WHY THESE TABLES WERE SKIPPED BEFORE. Their pages carry a second, ROTATED copy
of the table in the text layer, and plain text extraction interleaves the two.
This parser reads spans by coordinate and keeps only horizontal lines
(dir == (1, 0)); the rotated copy is dropped and rows come out clean.

PROVINCE OF AN AGE-TABLE BLOCK. The age tables wrap province names over two or
three lines in a narrow column ("Tangany" / "ika"), so a block (Total, M, F
rows) is identified by its printed TOTAL, which must equal exactly one
province's Tableau 2.1 total for that year. The wrapped label fragments are
then checked against that province's name.

UNITS AS PUBLISHED: thousands -> unit `thousand_persons` (as drc.yaml's age
tables). Geography spelling follows drc.yaml (Tableau 1.29: "Kongo-Central",
"Mai-Ndombe", "Sud-Kivu"); the national row "RDC" -> "Total country".

PUBLISHED INCONSISTENCIES, kept and pinned (never corrected):
* Tableau 2.1 Sud Kivu 2010: M 2748 + F 2873 = 5621, which is NORD Kivu's 2010
  total; Sud Kivu's printed total is 4874.
* Tableau 2.1 Sud Ubangi 2010: M 1042 + F 1074 = 2116 against Total 2145.
* Tableau 2.1 RDC 2010: M 35967 + F 36817 = 72784 against Total 72884.
The figures are filed as printed.
Any other sex or age-band disagreement beyond rounding raises.

series_type = estimate (INS's annual estimates; no census since 1984).
"""
from __future__ import annotations

import collections
import re
import unicodedata

import fitz
import pandas as pd

_SC = "CD_INS_ANNUAIRE2015_T2"
_YEARS = ["2010", "2011", "2012", "2013", "2014"]       # 2015 left to drc.yaml
_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75+"]
_GEOS = ["Bas-Uele", "Haut-Katanga", "Haut-Lomami", "Haut-Uele", "Ituri",
         "Kasaï", "Kasaï-Central", "Kasaï-Oriental", "Kinshasa",
         "Kongo-Central", "Kwango", "Kwilu", "Lomami", "Lualaba", "Mai-Ndombe",
         "Maniema", "Mongala", "Nord-Kivu", "Nord-Ubangi", "Sankuru",
         "Sud-Kivu", "Sud-Ubangi", "Tanganyika", "Tshopo", "Tshuapa",
         "Équateur"]
_SEX = {"Total": "total", "M": "male", "F": "female"}
# Published, pinned: (year, geography) whose M + F != Total in Tableau 2.1.
_KNOWN_SEX_GAPS = {("2010", "Sud-Kivu"), ("2010", "Sud-Ubangi"),
                   ("2010", "Total country")}
# Published, pinned: age-table disagreements (year, geo, sex, check, a, b) --
# "bands": the 16 bands sum to a, the table prints total b; "vs2.1": the age
# table's total a against Tableau 2.1's b. Filed as printed.
_KNOWN_AGE_ISSUES: set = {
    # Sud Ubangi 2010: bands = M + F (2116); the printed totals say 2145
    ("2010", "Sud-Ubangi", "total", "bands", 2116.0, 2145.0),
    # RDC 2011 25-29 printed 5773 (2010: 5175, 2012: 5555) -> bands 402 over
    ("2011", "Total country", "total", "bands", 75661.0, 75259.0),
    # 2012, four Katanga-split provinces: 15-19 printed far below trend
    # (Haut-Katanga M 81 against 205 in 2011 and 221 in 2013)
    ("2012", "Haut-Katanga", "female", "bands", 1925.0, 2071.0),
    ("2012", "Haut-Katanga", "male", "bands", 1918.0, 2048.0),
    ("2012", "Haut-Katanga", "total", "bands", 3805.0, 4119.0),
    ("2012", "Haut-Lomami", "female", "bands", 1234.0, 1326.0),
    ("2012", "Haut-Lomami", "male", "bands", 1227.0, 1312.0),
    ("2012", "Haut-Lomami", "total", "bands", 2435.0, 2638.0),
    ("2012", "Lualaba", "female", "bands", 1069.0, 1153.0),
    ("2012", "Lualaba", "male", "bands", 1069.0, 1140.0),
    ("2012", "Lualaba", "total", "bands", 2118.0, 2293.0),
    ("2012", "Tanganyika", "female", "bands", 1277.0, 1373.0),
    ("2012", "Tanganyika", "male", "bands", 1270.0, 1358.0),
    ("2012", "Tanganyika", "total", "bands", 2523.0, 2731.0),
    # RDC 2013 65-69 (both sexes) wraps over two lines ("101" / "5"): the
    # cell is dropped, not reassembled
    ("2013", "Total country", "total", "wrapped", "65-69", None),
}
_NUM = re.compile(r"^\d+$")


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


_GEO_BY_KEY = {_key(g): g for g in _GEOS}
_GEO_BY_KEY["rdc"] = "Total country"


def _rows(page):
    """Horizontal spans grouped into rows: [(y, [(x, text), ...]), ...]."""
    rows = collections.defaultdict(list)
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            if tuple(round(v) for v in line["dir"]) != (1, 0):
                continue                         # the rotated duplicate
            for s in line["spans"]:
                t = s["text"].strip()
                if t:
                    y = (s["bbox"][1] + s["bbox"][3]) / 2
                    rows[round(y)].append((s["bbox"][0], t))
    out = []
    for y in sorted(rows):
        if out and y - out[-1][0] <= 2:
            out[-1][1].extend(rows[y])
        else:
            out.append([y, list(rows[y])])
    return [(y, sorted(ws)) for y, ws in out]


def _blocks(rows, blocks):
    """Group (Total, M, F) data rows into blocks; attach label fragments (spans
    left of the sex column) to the nearest block by y. The sex column's x is
    the page's own (it drifts 85-88 between pages, 163 in Tableau 2.1)."""
    xs = [x for _, ws in rows for x, t in ws if t == "M"]
    if not xs:
        return blocks
    sex_x = min(xs)
    data, labels, frags = [], [], []
    for y, ws in rows:
        sex = [t for x, t in ws if abs(x - sex_x) < 12 and t in _SEX]
        # a span can hold two figures ("14139 11516"): split it, keeping the
        # span's x for each part
        cells = [(x, n) for x, t in ws if x > sex_x + 20 for n in t.split()]
        if sex and cells and not all(_NUM.match(n) for _, n in cells):
            raise ValueError(f"INS RDC: non-numeric cell in row {ws}")
        lab = " ".join(t for x, t in ws if x < sex_x - 8)
        if sex and cells:
            data.append((y, sex[0], [[x, float(n)] for x, n in cells]))
        elif cells and not lab and all(_NUM.match(n) for _, n in cells):
            frags.append((y, cells))         # a figure wrapped onto its own line
        if lab and not re.search(r"Province|Grou|pe$|d'âge|^s$|Tableau|Source",
                                 lab):
            labels.append((y, lab))
    # WRAPPED CELLS: a cell printed over two lines ("101" above "5" = 1015 on
    # the page) leaves a numbers-only line beside a data row. The cell's value
    # is not reconstructed from fragments; it is dropped (None) and reported.
    for fy, cells in frags:
        # the wrapped line sits ABOVE the row's own figure line
        near = [d for d in data if 0 < d[0] - fy <= 12]
        if not near:
            continue                         # a page number, not a fragment
        row = min(near, key=lambda d: d[0] - fy)[2]
        for fx, _ in cells:
            k = min(range(len(row)), key=lambda j: abs(row[j][0] - fx))
            if abs(row[k][0] - fx) > 12:
                raise ValueError(f"INS RDC: fragment at x={fx} matches no cell")
            row[k][1] = None
    data = [(y, sex, [v for _, v in row]) for y, sex, row in data]
    first = len(blocks)              # blocks before this page may continue
    if blocks:
        blocks[-1]["y"] = []         # its y's were on the previous page
    for y, sex, nums in data:
        if sex == "Total":
            blocks.append({"y": [y], "rows": {"total": nums}, "label": []})
        elif blocks and _SEX[sex] not in blocks[-1]["rows"]:
            blocks[-1]["rows"][_SEX[sex]] = nums
            blocks[-1]["y"].append(y)
        else:
            raise ValueError(f"INS RDC: orphan {sex} row at y={y}")
    page_blocks = blocks[max(first - 1, 0):]
    for y, lab in labels:
        if not page_blocks:
            continue
        dist = lambda b: min((abs(y - v) for v in b["y"]), default=1e9)
        b = min(page_blocks, key=dist)
        if dist(b) <= 14:
            b["label"].append(lab)
    return blocks


def parse(local_path: str) -> pd.DataFrame:
    with fitz.open(local_path) as doc:
        pages = []
        start = None
        for i, page in enumerate(doc):
            t = page.get_text()
            if start is None and re.search(r"Tableau 2\.1 : R.partition de la population", t):
                start = i
            if start is not None:
                if re.search(r"Tableau 2\.8\s*:", t):
                    break
                pages.append((i, t, _rows(page)))
    if not pages:
        raise ValueError("INS RDC: Tableau 2.1 not found")

    # Split every page's rows at table captions: a page can end one table and
    # start the next. Tables are keyed "2.1" or by the age table's year.
    by_table: dict[str, list] = collections.defaultdict(list)    # -> blocks
    table, pending = None, None
    for i, text, rows in pages:
        seg = []
        for k, (y, ws) in enumerate(rows):
            line = " ".join(t for _, t in ws)
            m = re.search(r"Tableau 2\.([1-7])\s*:", line)
            if m:
                if table is not None and seg:
                    _blocks(seg, by_table[table])
                seg = []
                if m.group(1) == "1":
                    table = "2.1"
                else:
                    near = " ".join(" ".join(t for _, t in w) for _, w in rows[k:k + 3])
                    yr = re.search(r"en\s*(20\d\d)", near)
                    if not yr:
                        raise ValueError(f"INS RDC p{i+1}: no year in caption {near!r}")
                    table = yr.group(1)
                continue
            seg.append((y, ws))
        if table is not None and seg:
            _blocks(seg, by_table[table])

    # ---- Tableau 2.1: province x sex x year --------------------------------
    t21: dict[str, dict[str, dict[str, float]]] = {}      # geo -> sex -> year -> v
    for b in by_table["2.1"]:
        geo = None
        for lab in b["label"]:
            g = _GEO_BY_KEY.get(_key(lab))
            if g and geo and g != geo:
                raise ValueError(f"INS RDC 2.1: two labels {geo}/{g}")
            geo = g or geo
        if geo is None:
            raise ValueError(f"INS RDC 2.1: unlabelled block {b}")
        if set(b["rows"]) != {"total", "male", "female"}:
            raise ValueError(f"INS RDC 2.1 {geo}: rows {sorted(b['rows'])}")
        if geo in t21:
            raise ValueError(f"INS RDC 2.1 {geo}: read twice")
        for sex, nums in b["rows"].items():
            if len(nums) != 6:
                raise ValueError(f"INS RDC 2.1 {geo} {sex}: {nums}")
            t21.setdefault(geo, {})[sex] = dict(zip(_YEARS + ["2015"], nums))
    # the 2015 age table (Tableau 2.7) is deliberately not read
    age_tables = {y: [(0, b) for b in by_table[y]] for y in _YEARS if y in by_table}

    if set(t21) != set(_GEOS) | {"Total country"}:
        raise ValueError(f"INS RDC 2.1: geographies {sorted(set(t21) ^ (set(_GEOS) | {'Total country'}))}")
    out = []

    def emit(geo, sex, age, year, v):
        out.append({"series_type": "estimate", "sex": sex, "age_group": age,
                    "geography": geo, "period": year, "frequency": "annual",
                    "measure": "count", "value": v, "unit": "thousand_persons",
                    "series_code": _SC})

    for geo, by_sex in t21.items():
        for y in _YEARS:
            tot, m, f = (by_sex[s][y] for s in ("total", "male", "female"))
            if abs(m + f - tot) > 2 and (y, geo) not in _KNOWN_SEX_GAPS:
                raise ValueError(f"INS RDC 2.1 {geo} {y}: {m} + {f} != {tot}")
            for s in ("total", "male", "female"):
                emit(geo, s, "Total", y, by_sex[s][y])
    gaps = {(y, g) for g, bs in t21.items() for y in _YEARS
            if abs(bs["male"][y] + bs["female"][y] - bs["total"][y]) > 2}
    if gaps != _KNOWN_SEX_GAPS:
        raise ValueError(f"INS RDC 2.1: sex gaps changed: {sorted(gaps)}")

    # ---- Tableaux 2.2-2.6: age x sex x province, one per year ---------------
    issues: set = set()
    if sorted(age_tables) != _YEARS:
        raise ValueError(f"INS RDC age tables: years {sorted(age_tables)}")
    for y in _YEARS:
        by_total = collections.defaultdict(list)
        for g, bs in t21.items():
            by_total[bs["total"][y]].append(g)
        seen = set()
        for i, b in age_tables[y]:
            if "total" not in b["rows"]:
                raise ValueError(f"INS RDC {y} p{i+1}: block without Total {b}")
            tot = b["rows"]["total"][-1]
            if tot is None:
                raise ValueError(f"INS RDC {y}: a block's printed total is wrapped")
            geos = by_total.get(tot, [])
            if len(geos) != 1:
                raise ValueError(f"INS RDC {y} p{i+1}: total {tot} matches {geos}")
            geo = geos[0]
            frag = _key("".join(b["label"]))
            if frag and geo != "Total country" and not (
                    frag in _key(geo) or _key(geo) in frag):
                raise ValueError(f"INS RDC {y}: block {tot} labelled "
                                 f"{b['label']} but matched {geo}")
            if geo in seen:
                raise ValueError(f"INS RDC {y} {geo}: read twice")
            seen.add(geo)
            if set(b["rows"]) != {"total", "male", "female"}:
                raise ValueError(f"INS RDC {y} {geo}: rows {sorted(b['rows'])}")
            for sex, nums in b["rows"].items():
                if len(nums) != 17:
                    raise ValueError(f"INS RDC {y} {geo} {sex}: {len(nums)} values")
                if None in nums:
                    issues.add((y, geo, sex, "wrapped",
                                _BANDS[nums.index(None)] if nums.index(None) < 16
                                else "Total", None))
                elif abs(sum(nums[:16]) - nums[16]) > 12:
                    issues.add((y, geo, sex, "bands", sum(nums[:16]), nums[16]))
                if nums[16] is not None and abs(nums[16] - t21[geo][sex][y]) > 2:
                    issues.add((y, geo, sex, "vs2.1", nums[16], t21[geo][sex][y]))
                for band, v in zip(_BANDS, nums[:16]):
                    if v is not None:
                        emit(geo, sex, band, y, v)
        missing = set(_GEOS) - seen
        if missing:
            raise ValueError(f"INS RDC {y}: provinces missing {sorted(missing)}")
    if issues != _KNOWN_AGE_ISSUES:
        raise ValueError(f"INS RDC age tables: inconsistencies changed: "
                         f"new {sorted(issues - _KNOWN_AGE_ISSUES)}, "
                         f"gone {sorted(_KNOWN_AGE_ISSUES - issues)}")
    return pd.DataFrame(out)
