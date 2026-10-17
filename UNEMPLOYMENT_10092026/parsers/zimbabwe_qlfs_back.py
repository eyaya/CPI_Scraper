"""Zimbabwe -- ZIMSTAT Quarterly Labour Force Survey BACK-SERIES, 2021-2024.

The current QLFS (zimbabwe_unemployment.py) reads the newest report's own
quarter. Each QLFS report's "Table 1: Key findings" prints TWO quarters -- the
current one and the one before it -- so four earlier reports give seven
quarters:

    Fourth_Quarter_Labour_Force_Report_2021.pdf   2021 Q3 | 2021 Q4
    QLFS_SecondQter2022.pdf                       2022 Q1 | 2022 Q2
    2024_First_Quarter_QLFS_Report.pdf            2023 Q4 | 2024 Q1
    2024_Third_Quarter_QLFS_Report.pdf            2024 Q1 | 2024 Q3

A QUARTER PRINTED TWICE is taken from the NEWER report (2024 Q1 from the Q3
report), and every figure on which the two printings differ is pinned in
_KNOWN_REPRINT_DIFFS -- none is silently resolved.

NOT READ: "Labour_Force_Report_2021.pdf" (the first QLFS, 2021 Q3). The Q4
report reprints its quarter, and this first report prints the two youth
unemployment COUNTS SWAPPED (15-24: 501,003 and 15-34: 276,642, against
276,642 and 501,003 in the Q4 report, whose rates agree with either printing),
so the reprint is the one filed.

TWO WORKING-AGE BASES, never aligned: 2021-2022 reports count persons aged 15+
and their youth band is 15-34; from 2023 Q4 the base is 16+ and youth 15-35 --
both as each table prints them, in `working_age_base`, `age_group` and the
label.

ROWS (Unemployment): working-age population, labour force, LFPR, total
employed, EPR; strict unemployment (count and rate) national and youth;
expanded/relaxed unemployment (count where printed, and rate) national and
youth; NEET rates. Counts are filed under the count topics (`unemployed`,
`labour_force` ...), rates under the rate topics. NEET COUNTS are not filed --
the schema's NEET topic is a rate. The "Sector of employment" rows are
labour composition (labour/parsers/zimbabwe_qlfs_back_labour.py).

LABELS follow the current layout's ("Total Employed", "Labour Force
Participation Rate (LFPR)" ...) so a series continues across reports; the
base and youth band in each label are the report's own.
"""
from __future__ import annotations
import os
import re

import fitz
import pandas as pd

from . import _common as C

_ORD = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "first": 1, "second": 2,
        "third": 3, "fourth": 4}

# report (lower-cased basename fragment) -> (report order, its two quarters)
_REPORTS = {
    "fourth_quarter_labour_force_report_2021": (1, ("2021-Q3", "2021-Q4")),
    "qlfs_secondqter2022": (2, ("2022-Q1", "2022-Q2")),
    "2024_first_quarter_qlfs_report": (3, ("2023-Q4", "2024-Q1")),
    "2024_third_quarter_qlfs_report": (4, ("2024-Q1", "2024-Q3")),
}

# (period, series_label, sex, measure) -> (older printing, newer printing)
_KNOWN_REPRINT_DIFFS: dict = {}

_NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d+\.\d+|\d+")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def report_of(path: str):
    name = os.path.basename(path).lower()
    hits = [k for k in _REPORTS if k in name]
    if len(hits) != 1:
        raise ValueError(f"zimbabwe_qlfs_back: unknown report {name!r}")
    return hits[0], _REPORTS[hits[0]]


def key_findings(path: str):
    """[(label, [numbers])] of Table 1 'Key findings', plus the two header
    quarters as printed (checked against the expected ones)."""
    doc = fitz.open(path)
    for page in doc:
        t = page.get_text()
        if not re.search(r"Table 1\s*:\s*Key Findings", t, re.I):
            continue
        toks = [_clean(x) for x in t.splitlines() if _clean(x)]
        start = next(i for i, x in enumerate(toks)
                     if re.match(r"Table 1\s*:\s*Key Findings", x, re.I))
        # the list of tables also names Table 1: the real table has an
        # 'Indicator' column header within a few lines of its title
        ind = next((i for i in range(start + 1, min(start + 12, len(toks)))
                    if toks[i].lower() == "indicator"), None)
        if ind is None:
            continue
        head = " ".join(toks[start + 1:ind])
        quarters = []
        for m in re.finditer(r"(1st|2nd|3rd|4th)\s+Quarter(?:\s+(20\d\d))?", head, re.I):
            quarters.append((_ORD[m.group(1).lower()], m.group(2)))
        year = re.search(r"Year\s+(20\d\d)", head)
        quarters = [f"{y or (year.group(1) if year else '')}-Q{q}" for q, y in quarters]
        start = ind
        rows, label, nums = [], [], []
        for tok in toks[start + 1:]:
            if re.fullmatch(r"[\d,. ]+", tok):
                nums += [float(x.replace(",", "")) for x in _NUM.findall(tok)]
                continue
            if nums:
                rows.append((_clean(" ".join(label)), nums))
                label, nums = [], []
            if tok.lower() in ("indicator", "number", "percent", "value"):
                continue
            label.append(tok)
        if nums:
            rows.append((_clean(" ".join(label)), nums))
        return quarters, rows
    raise ValueError(f"zimbabwe_qlfs_back: no 'Table 1: Key findings' in {path}")


def split(nums: list[float], kind: str):
    """Two quarters' worth of figures -> [(q_index, measure, value)].
    kind: 'count', 'rate', or 'both' (count and percent per quarter)."""
    if kind == "both" and len(nums) == 4:
        return [(0, "count", nums[0]), (0, "rate", nums[1]),
                (1, "count", nums[2]), (1, "rate", nums[3])]
    if kind == "both" and len(nums) == 2 and all(v <= 100 for v in nums):
        return [(0, "rate", nums[0]), (1, "rate", nums[1])]
    if kind in ("count", "rate") and len(nums) == 2:
        return [(0, kind, nums[0]), (1, kind, nums[1])]
    raise ValueError(f"zimbabwe_qlfs_back: {len(nums)} figures for a {kind} row")


# "Labour Force" is a section header only where a row label follows it
# (2024: "Labour Force | Working Age Population ..."); otherwise it IS the row.
_SECTION = re.compile(r"^(?:Labour Force(?=\s+Working Age)|Sector of Employment|Unemployment|"
                      r"Expanded/Relaxed Unemployment|Youth Not in Education, "
                      r"Employment or Training \(NEET\))\s*", re.I)


def _strip_section(label: str) -> tuple[str, str | None]:
    sec = None
    while True:
        m = _SECTION.match(label)
        if not m or m.end() == len(label):
            return label, sec
        sec = m.group(0).strip().lower()
        label = label[m.end():].strip()


def _rows(path: str) -> list[dict]:
    key, (order, expect) = report_of(path)
    quarters, table = key_findings(path)
    if quarters != list(expect):
        raise ValueError(f"zimbabwe_qlfs_back {key}: header quarters {quarters}, "
                         f"expected {expect}")
    out, block = [], None
    for raw, nums in table:
        label, sec = _strip_section(raw)
        if sec:
            block = sec
        m_base = re.search(r"\((1[56]) years and above\)", label)
        base = None
        spec = None
        if re.match(r"Working Age Population", label):
            spec = ("working_age_population", "count", "not_applicable", "Total")
        elif re.match(r"Labour Force \(1[56] years", label):
            spec = ("labour_force", "count", "not_applicable", "Total")
        elif re.match(r"Labour Force Participation Rate", label):
            spec = ("labour_force_participation_rate", "rate", "strict", "Total")
        elif re.match(r"Total Employed", label):
            spec = ("employed", "count", "not_applicable", "Total")
        elif re.match(r"Employment to Population Ratio", label):
            spec = ("employment_to_population_ratio", "rate", "not_applicable",
                    "Total")
        # NEET rows are recognised by their own label: the 2024 Q3 report
        # prints them straight after the expanded block, without its header
        elif re.match(r"Youth \((\d\d-\d\d) years\) NEET$", label):
            spec = ("neet", "both", "not_applicable",
                    re.match(r"Youth \((\d\d-\d\d)", label).group(1))
        elif block in ("unemployment", "expanded/relaxed unemployment"):
            definition = "strict" if block == "unemployment" else "broad"
            m_y = re.match(r"Youth \((\d\d-\d\d) years\)$", label)
            if re.match(r"National \(1[56] years and above\)$", label):
                spec = ("unemployment", "both", definition, "Total")
            elif m_y:
                spec = ("youth_unemployment", "both", definition, m_y.group(1))
        if spec is None:
            continue
        topic, kind, definition, age = spec
        base = (m_base.group(1) + "+") if m_base else None
        for qi, measure, v in split(nums, kind):
            if topic in ("unemployment", "youth_unemployment"):
                t = ("unemployed" if measure == "count" else
                     "unemployment_rate" if topic == "unemployment"
                     else "youth_unemployment_rate")
            elif topic == "neet":
                if measure == "count":
                    continue                     # no NEET count topic
                t = "neet_rate"
            else:
                t = topic
            series = label if definition != "broad" else f"{label}, expanded/relaxed"
            out.append(dict(_order=order, period=quarters[qi], topic=t,
                            measure=measure, value=v, definition=definition,
                            age=age, series=series, base=base))
    # every report must give the headline rows for both its quarters
    got = {(r["period"], r["topic"]) for r in out}
    for q in quarters:
        for t in ("working_age_population", "labour_force", "employed",
                  "unemployment_rate", "labour_force_participation_rate"):
            if (q, t) not in got:
                raise ValueError(f"zimbabwe_qlfs_back {key}: no {t} for {q}")
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    recs = []
    for p in [local_path] + list(extras or []):
        recs += _rows(p)
    df = pd.DataFrame(recs)
    # working-age base of a report = the base printed on its national rows
    bases = df.dropna(subset=["base"]).groupby(["_order"])["base"].unique()
    for o, b in bases.items():
        if len(b) != 1:
            raise ValueError(f"zimbabwe_qlfs_back: report {o} prints bases {b}")
    df["base"] = df["_order"].map({o: b[0] for o, b in bases.items()})
    key = ["period", "series", "topic", "measure", "age"]
    diffs = {}
    for k, g in df.groupby(key):
        if g["_order"].nunique() > 1:
            g = g.sort_values("_order")
            if abs(g["value"].iloc[0] - g["value"].iloc[-1]) > 1e-9:
                diffs[(k[0], k[1], k[3])] = (g["value"].iloc[0], g["value"].iloc[-1])
    if diffs != _KNOWN_REPRINT_DIFFS:
        raise ValueError(f"zimbabwe_qlfs_back: reprint differences changed: "
                         f"{diffs} vs pinned {_KNOWN_REPRINT_DIFFS}")
    df = df.sort_values("_order").drop_duplicates(key, keep="last")
    rows = []
    for r in df.itertuples():
        unit = "percent" if r.measure == "rate" else "persons"
        rows.append(C.row(
            topic=r.topic, value=r.value, series_label=r.series,
            survey="Quarterly Labour Force Survey (QLFS)", period=r.period,
            reference_period=r.period.replace("-", " "), frequency="quarterly",
            working_age_base=r.base, measure=r.measure, unit=unit,
            definition=r.definition, age_group=r.age,
            series_code="ZIMSTAT QLFS Table 1 Key findings"))
    return pd.DataFrame.from_records(rows)
