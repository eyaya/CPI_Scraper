"""Zambia -- back rounds of monetary poverty (CSO / ZamStats), one parser per report.

`zambia_poverty` reads the 2022 LCMS report (2015 and 2022). This module
reads every earlier survey report ZamStats publishes on its own site
(wp-content/uploads, found through the WordPress media API):

  parse_1993  Social Dimensions of Adjustment Priority Survey II (1993) --
              ch. 10, Tables 10.2 / 10.4 / 10.5: EXTREME poverty only. The
              overall headcount is never printed in a table (it is extreme +
              moderate, which is not summed here), and Table 10.8's P0/P1/P2
              average over the poor only, so are not FGT measures.
  parse_1996  LCMS 1996 -- Tables 12.1 / 12.2 / 12.4 / 12.5: total-poor and
              extremely-poor headcounts by rural/urban, province, province x
              residence, stratum, socio-economic group, sex of head, household
              size. Table 12.8's "P1"/"P2" (0.615 / 0.443 against P0 0.780)
              are not the FGT gap and severity (as in 1993) -- skipped.
  parse_1998  LCMS 1998 -- Tables 12.1 / 12.2a / 12.2b / 12.2c / 12.3: same
              cuts, plus each province's share of the (extremely) poor.
              Table 12.4's P1 (0.548) is skipped for the same reason.
  parse_2002  LCMS 2002-2003 -- Tables 13.4 / 13.5 (headcounts) and 13.7
              (FGT P1 and P2 "averaged across the total population", printed
              on 0-1 -> unit index). Lines K64,530 (extreme) / K92,185
              (moderate) per adult equivalent per month.
  parse_2010  LCMS 2006 and 2010 report -- Appendix Tables A9 / A10 (P0
              with 95% CI by rural/urban, stratum, province); Tables 12.4 /
              12.5 (overall and extreme P0 by age of head and household size,
              2006 and 2010; education and employment status of head, 2010).
              Moderate lines K100,012 (2006) / K146,009 (2010) per AE per
              month. Its province and stratum EXTREME rates are chart labels
              only and are not read.
  parse_2015  LCMS 2015 report -- Annex Tables E.1-E.6, the "revised 2015
              poverty estimates": P0/P1/P2 on the lower (overall) and food
              (extreme) lines, with the CI of P0, by rural/urban, province and
              stratum. Lines ZMW 214 / 152 per AE per month. Survey label
              "LCMS 2015", the label `zambia_poverty` gives the same estimates
              from the 2022 report, so identical rows coincide.

METHOD BREAKS: each report computed poverty its own way (the 2015 annex
revises 2015; 2006/2010 use year-specific Engel ratios) -- each round is its
own `survey`, never one series silently.

Strata are Zambia's own: rural small/medium/large-scale farmers and
non-agricultural households; urban low/medium/high-cost areas, filed as
locality rural/urban with the stratum as `locality_label` (one canonical
spelling across rounds).

CROSS-CHECK (verbatim): 1993 extreme 76 (rural 89); 1996 total poor 78,
extreme 66; 1998 73 / 58, Western 89; 2002 67 / 46, P1 0.271, P2 0.139;
2006 62.80, 2010 60.508; 2015 54.4 / 40.8, P1 26.4, P2 16.0, Western 82.2.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

PROVINCES = ["Central", "Copperbelt", "Eastern", "Luapula", "Lusaka", "Muchinga",
             "Northern", "North-Western", "Southern", "Western"]
_PROV_RX = {"North-Western": r"N(?:orth)?[\s-]*[Ww]estern"}
STRATA = [  # (regex, locality, canonical label)
    (r"Small[\s-]*[Ss]cale(?: [Ff]armers)?", "rural", "Small-scale farmers"),
    (r"Medium[\s-]*[Ss]cale(?: [Ff]armers)?", "rural", "Medium-scale farmers"),
    (r"Large[\s-]*[Ss]cale(?: [Ff]armers)?", "rural", "Large-scale farmers"),
    (r"Non[\s‐-]*[Aa]gricultural(?: [Hh]ouseholds)?", "rural", "Non-agricultural households"),
    (r"(?:Urban )?[Ll]ow[\s-]*[Cc]ost(?: [Aa]reas)?", "urban", "Low-cost areas"),
    (r"(?:Urban )?[Mm]edium[\s-]*[Cc]ost(?: [Aa]reas)?", "urban", "Medium-cost areas"),
    (r"(?:Urban )?[Hh]igh[\s-]*[Cc]ost(?: [Aa]reas)?", "urban", "High-cost areas"),
]
_NUM = re.compile(r"^(?:-?\d{1,3}(?:,\d{3})+|-?\d+(?:\.\d+)?|-|—)$")


def _pages(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def _clean(line: str) -> str:
    line = line.replace("¦", " ").replace("\\", " ")
    return re.sub(r"\s+", " ", line).strip()


def _split(line: str):
    """(label, numbers) -- numbers are the trailing numeric tokens."""
    toks = _clean(line).split()
    nums = []
    while toks and _NUM.match(toks[-1]):
        nums.insert(0, toks.pop())
    return " ".join(toks), nums


def _val(tok):
    return None if tok in ("-", "—") else float(tok.replace(",", ""))


def _segment(pages, caption, end=None, nxt=0, occurrence=-1):
    """Text from the chosen occurrence of `caption` up to `end` (regex)."""
    hits = [i for i, t in enumerate(pages) if re.search(caption, t)]
    if not hits:
        raise ValueError(f"Zambia: caption not found: {caption!r}")
    i = hits[occurrence]
    text = "\n".join(pages[i:i + 1 + nxt])
    text = text[re.search(caption, text).end():]
    if end:
        m = re.search(end, text)
        if m:
            text = text[:m.start()]
    lines = [l for l in (_clean(x) for x in text.splitlines()) if l]
    # A province name wrapped over two lines ("North" / "western 90 5 5 ..."):
    # re-join when the joined label is a province and the first part is not.
    out = []
    for l in lines:
        if out and not _split(out[-1])[1] and _cut_for(out[-1]) is None:
            c = _cut_for(_split(f"{out[-1]} {l}")[0])
            if c is not None and "geography" in c:
                out[-1] = f"{out[-1]} {l}"
                continue
        out.append(l)
    return out


def _cut_for(label: str):
    lab = label.strip(" :")
    if re.fullmatch(r"All Zambia(?: Total)?|Zambia(?: Total)?", lab):
        return {}
    if lab in ("Rural", "Urban"):
        return {"topic": "locality", "locality": lab.lower(), "locality_label": lab}
    for p in PROVINCES:
        if re.fullmatch(_PROV_RX.get(p, p), lab):
            return {"geography": p}
    for rx, loc, canon in STRATA:
        if re.fullmatch(rx, lab):
            return {"topic": "locality", "locality": loc, "locality_label": canon}
    return None


def read_rows(lines, n, labels=None):
    """{label: first-n values} for every row of a block. Rows whose label and
    numbers are on one line are taken directly; a block whose labels sit on
    their own lines ABOVE or BELOW their numbers (CSO's 1998/2002 tables do
    both, even within one table) is paired in ORDER: k-th label line with
    k-th number line, only when the two counts agree."""
    out, lab_only, num_only = [], [], []
    for l in lines:
        label, nums = _split(l)
        ok = (labels(label) if labels else _cut_for(label) is not None)
        if label and nums and len(nums) >= n and ok:
            out.append((label, [_val(x) for x in nums[:n]]))
        elif label and not nums and ok:
            lab_only.append(label)
        elif not label and len(nums) >= n:
            num_only.append([_val(x) for x in nums[:n]])
    if lab_only or num_only:
        if len(lab_only) != len(num_only):
            raise ValueError(f"Zambia: cannot pair {len(lab_only)} labels with "
                             f"{len(num_only)} number lines: {lab_only[:4]}")
        out += list(zip(lab_only, num_only))
    return out


def _base(survey, period, ref, level, value="", unit="ZMK per adult equivalent per month"):
    name = {"extreme": "Extreme (food) poverty line",
            "overall": "Moderate (basic needs) poverty line"}[level]
    return dict(survey=survey, welfare_aggregate="consumption", line_type="national",
                line_level=level, line_name=name, line_value=value,
                line_unit=unit if value != "" else "", period=period,
                reference_period=ref, frequency="ad_hoc")


def _emit(rows, metric, value, base, cut, unit=None):
    if value is None:
        return
    rows.append(C.row(metric=metric, value=value, unit=unit, **base, **cut))


def _prov_residence(rows, lines, cols, bases, national=False):
    """'<Province> Total v..' then 'Rural v..' / 'Urban v..' (1993, 1996, 1998).
    A province owns at most the TWO residence rows that follow it; residence
    rows after that (1993 prints the national Rural/Urban after Western) are
    national and are emitted only when `national` (the other reports give
    them in their own table)."""
    prov, since, got = None, 0, 0
    for l in lines:
        label, nums = _split(l)
        label = re.sub(r"\s*Total$", "", re.sub(r"(?<=[a-z])Total$", "", label)).strip()
        c = _cut_for(label)
        if c is not None and "geography" in c:
            prov, since = c["geography"], 0      # a (possibly wrapped) province line
            if nums and national:
                for (metric, idx), base in zip(cols, bases):
                    _emit(rows, metric, _val(nums[idx]), base, c)
            continue
        if not nums or c is None:
            continue
        if label in ("Rural", "Urban"):
            if prov and since < 2:
                for (metric, idx), base in zip(cols, bases):
                    _emit(rows, metric, _val(nums[idx]), base, {**c, "geography": prov})
                since += 1
                got += 1
            elif national:
                for (metric, idx), base in zip(cols, bases):
                    _emit(rows, metric, _val(nums[idx]), base, c)
        elif national and c == {}:
            for (metric, idx), base in zip(cols, bases):
                _emit(rows, metric, _val(nums[idx]), base, c)
    return got


def _need(got, want, what):
    if got < want:
        raise ValueError(f"Zambia {what}: read {got} rows, expected >= {want}")


# ------------------------------------------------------------------ 1993 ---
_S93 = ("SDA Priority Survey II 1993", "1993", "1993")
LAYOUT_1993 = {"survey": _S93[0], "welfare_aggregate": "consumption", "line_type": "national",
               "line_level": "extreme", "line_name": "Extreme (food) poverty line",
               "period": "1993", "reference_period": "1993", "tables": []}


def parse_1993(path):
    pages = _pages(path)
    rows = []
    bx = _base(*_S93, "extreme", 5910, "ZMK per adult equivalent per month (1993)")
    seg = _segment(pages, r"Table 10\.2:", r"_-{10}")
    got = _prov_residence(rows, seg, [("headcount", 0)], [bx], national=True)
    _need(got, 18, "1993 T10.2 province x residence")
    seg = _segment(pages, r"Table 10\.4:", r"_-{10}")
    for label, (ext,) in read_rows(seg, 1):
        _emit(rows, "headcount", ext, bx, _cut_for(label))
    seg = _segment(pages, r"Table 10\.5:", r"_-{10}")
    for label, (ext,) in read_rows(seg, 1, labels=lambda l: bool(_hh(l)) or l in ("Male", "Female")):
        _emit(rows, "headcount", ext, bx, _hh(label) or _sex(label))
    return _dedupe(rows, 30, "1993")


def _sex(label):
    return {"Male": {"topic": "sex_of_head", "characteristic": "Male", "sex": "male"},
            "Female": {"topic": "sex_of_head", "characteristic": "Female", "sex": "female"}}.get(label)


def _hh(label):
    lab = label.strip()
    if re.fullmatch(r"(?:I|1) [Pp]ersons?|\d+ ?\+ [Pp]ersons|\d+\s*(?:-|to)\s*\d+ [Pp]ersons|\d+\+(?: [Pp]ersons)?|"
                    r"\d+ [Pp]ersons or more|1-2|3-4|5-6|7-8|9\+", lab):
        return {"topic": "household_size", "characteristic": "1 person" if lab.startswith("I ") else lab}
    return None


def _dedupe(rows, want, what):
    df = pd.DataFrame.from_records(rows)
    key = [c for c in df.columns if c not in ("value",)]
    if df.duplicated(key).any():
        dup = df[df.duplicated(key, keep=False)]
        # the same cut read from two tables must agree; then keep one
        if (dup.groupby(key)["value"].nunique() > 1).any():
            raise ValueError(f"Zambia {what}: two tables disagree on one cut")
        df = df.drop_duplicates(key)
    _need(len(df), want, what)
    return df


# ------------------------------------------------------------------ 1996 ---
_S96 = ("LCMS 1996", "1996", "1996")
LAYOUT_1996 = {**LAYOUT_1993, "survey": _S96[0], "line_level": "overall",
               "line_name": "Moderate (basic needs) poverty line", "period": "1996",
               "reference_period": "1996"}


def parse_1996(path):
    pages = _pages(path)
    rows = []
    b, bx = _base(*_S96, "overall"), _base(*_S96, "extreme")
    cols = [("headcount", 2), ("headcount", 0)]   # Total poor, Extremely poor
    seg = _segment(pages, r"Table 12\.1: Incidence of poverty within", r"\n?\d{3}\s*$|Graph")
    for label, v in read_rows(seg, 3):
        c = _cut_for(label)
        _emit(rows, "headcount", v[2], b, c)
        _emit(rows, "headcount", v[0], bx, c)
    seg = _segment(pages, r"Table 12\.2: Incidence of Poverty within", r"Table 12\.2 shows")
    _need(_prov_residence(rows, seg, cols, [b, bx]), 18, "1996 T12.2")
    seg = _segment(pages, r"Table 12\.4: Incidence of Poverty by Stratum", r"Table 12\.4 shows")
    seg = seg[:next(i for i, l in enumerate(seg) if l.startswith("Socio-Economic Group"))]
    for label, v in read_rows(seg, 3):
        c = _cut_for(label)
        _emit(rows, "headcount", v[2], b, c)
        _emit(rows, "headcount", v[0], bx, c)
    seg = _segment(pages, r"Table 12\.4: Incidence of Poverty by Stratum", r"Table 12\.4 shows")
    seg = seg[next(i for i, l in enumerate(seg) if l.startswith("Socio-Economic Group")) + 1:]
    for label, v in read_rows(seg, 3, labels=lambda l: bool(l) and not l.startswith("All")):
        c = {"topic": "employment_of_head", "characteristic": label}
        _emit(rows, "headcount", v[2], b, c)
        _emit(rows, "headcount", v[0], bx, c)
    seg = _segment(pages, r"Table 12\.5 Incidence of poverty by sex", r"Both Sexes")
    for label, v in read_rows(seg, 3, labels=lambda l: bool(_hh(l) or _sex(l))):
        c = _hh(label) or _sex(label)
        _emit(rows, "headcount", v[2], b, c)
        _emit(rows, "headcount", v[0], bx, c)
    return _dedupe(rows, 112, "1996")


# ------------------------------------------------------------------ 1998 ---
_S98 = ("LCMS 1998", "1998", "1998")
LAYOUT_1998 = {**LAYOUT_1996, "survey": _S98[0], "period": "1998", "reference_period": "1998"}


def parse_1998(path):
    pages = _pages(path)
    rows = []
    b, bx = _base(*_S98, "overall"), _base(*_S98, "extreme")
    for cap, end in ((r"Table 12 ?\.1: Incidence ?of Poverty by Stratum", r"12\.3\. INCIDENCE"),
                     (r"Table 12\. 2a: Incidence of Poverty by Level", r"\n\d{3}\s*$|115")):
        for label, v in read_rows(_segment(pages, cap, end), 2):
            c = _cut_for(label)
            _emit(rows, "headcount", v[0], b, c)       # Total poor
            _emit(rows, "headcount", v[1], bx, c)      # Extremely poor
    seg = _segment(pages, r"Table 12\.2b: Incidence of Poverty by Province", r"Table 12\.2c")
    for label, v in read_rows(seg, 2, labels=lambda l: _cut_for(l) is not None and l != "Zambia Total"):
        c = _cut_for(label)
        if c:
            _emit(rows, "poor_share", v[0], b, c)
            _emit(rows, "poor_share", v[1], bx, c)
    seg = _segment(pages, r"Table 12\.2c: Incidenceof Poverty", r"12\.4\. INCIDENCE")
    _need(_prov_residence(rows, seg, [("headcount", 0), ("headcount", 1)], [b, bx]), 18, "1998 T12.2c")
    seg = _segment(pages, r"Incidence of Poverty by Sex of Head and Household Size, Zambia, 1998",
                   r"In addition to the incidence")
    for label, v in read_rows(seg, 2, labels=lambda l: bool(_hh(l) or _sex(l))):
        c = _hh(label) or _sex(label)
        _emit(rows, "headcount", v[0], b, c)
        _emit(rows, "headcount", v[1], bx, c)
    return _dedupe(rows, 80, "1998")


# ------------------------------------------------------------------ 2002 ---
_S02 = ("LCMS 2002-2003", "2002", "2002/03")
LAYOUT_2002 = {**LAYOUT_1996, "survey": _S02[0], "period": "2002", "reference_period": "2002/03"}


def parse_2002(path):
    pages = _pages(path)
    rows = []
    b, bx = _base(*_S02, "overall", 92185), _base(*_S02, "extreme", 64530)
    seg = _segment(pages, r"Table 13\.4: Incidence of Poverty by Residence", r"Figure 13\.1")
    seg = [l for l in seg if l not in ("Rural/Urban", "Province")]
    for label, v in read_rows(seg, 3):
        c = _cut_for(label)
        _emit(rows, "headcount", v[2], b, c)
        _emit(rows, "headcount", v[0], bx, c)
    seg = _segment(pages, r"Table 13\.5: Incidence of Poverty by Stratum", r"Living Conditions in Zambia")
    rural = seg[seg.index("Rural Stratum") + 1:seg.index("Urban Stratum")]
    urban = seg[seg.index("Urban Stratum") + 1:]
    rural = [l for l in rural if l != "Households"]
    for part in (rural, urban):
        for label, v in read_rows(part, 3):
            c = _cut_for(label)
            _emit(rows, "headcount", v[2], b, c)
            _emit(rows, "headcount", v[0], bx, c)
    seg = _segment(pages, r"Table 13\.7: Intensity of Poverty by Stratum", r"13\.12 Perception")
    seg = [l for l in seg if l not in ("Rural/Urban", "Province", "Index (P2)")]
    got = 0
    for label, v in read_rows(seg, 3):
        c = _cut_for(label)
        _emit(rows, "gap", v[1], b, c, unit="index")
        _emit(rows, "severity", v[2], b, c, unit="index")
        got += 1
    _need(got, 12, "2002 T13.7")
    return _dedupe(rows, 60, "2002")


# ------------------------------------------------------------------ 2010 ---
_S06 = ("LCMS 2006", "2006", "2006")
_S10 = ("LCMS 2010", "2010", "2010")
LAYOUT_2010 = {**LAYOUT_1996, "survey": _S10[0], "period": "2010", "reference_period": "2010"}


def _a9(rows, pages, cap, s, value):
    b = _base(*s, "overall", value)
    seg = _segment(pages, cap, r"\n\d{3}\s*$")
    got, cur = 0, None
    for l in seg:
        label, nums = _split(l)
        m = re.match(r"^(.*?)\s*(Non-poor|Poor)$", label)
        if not m or len(nums) < 4:
            continue
        name = m.group(1) or cur
        cur = name
        if m.group(2) != "Poor":
            continue
        c = _cut_for("All Zambia" if name in ("", None) else name)
        if c is None:
            continue
        est, _se, lo, hi = (_val(x) for x in nums[:4])
        _emit(rows, "headcount", est, b, c)
        _emit(rows, "headcount_ci_low", lo, b, c)
        _emit(rows, "headcount_ci_high", hi, b, c)
        got += 1
    _need(got, 19, f"{s[0]} appendix CI table")


def parse_2010(path):
    pages = _pages(path)
    rows = []
    _a9(rows, pages, r"Table A9: Confidence interval for the 2010", _S10, 146009)
    _a9(rows, pages, r"Table A10: Confidence interval for the 2006", _S06, 100012)
    # Table 12.4: 2006 | 2010 x Total | Rural | Urban x Overall | Extreme
    seg = _segment(pages, r"Table 12\.4: Distribution of the population by overall", r"Table 12\.5", nxt=1)
    blocks = [(s, loc) for s in (_S06, _S10) for loc in ("all", "rural", "urban")]
    got = 0
    for label, v in read_rows(seg, 12, labels=lambda l: bool(re.fullmatch(r"\d{2}-\d{2}|65\+", l) or _hh(l))):
        c = ({"topic": "age_of_head", "characteristic": label}
             if re.fullmatch(r"\d{2}-\d{2}|65\+", label) else _hh(label))
        for k, (s, loc) in enumerate(blocks):
            locc = {} if loc == "all" else {"locality": loc, "locality_label": loc.title()}
            for j, level in enumerate(("overall", "extreme")):
                val = {("overall", "2006"): 100012, ("overall", "2010"): 146009}.get((level, s[1]), "")
                _emit(rows, "headcount", v[2 * k + j], _base(*s, level, val), {**c, **locc})
        got += 1
    _need(got, 11, "2006/2010 T12.4")
    # Table 12.5 (2010): Total | Rural | Urban x Overall | Extreme
    seg = _segment(pages, r"Table 12\.5: Distribution of the population by overall", r"12\.11\.1\.")
    topic = None
    got = 0
    for l in seg:
        if l.startswith("Education level of head"):
            topic = "education_of_head"; continue
        if l.startswith("Employment status"):
            topic = "employment_of_head"; continue
        label, nums = _split(l)
        if topic and label and len(nums) == 6:
            for k, loc in enumerate(("all", "rural", "urban")):
                locc = {} if loc == "all" else {"locality": loc, "locality_label": loc.title()}
                for j, level in enumerate(("overall", "extreme")):
                    _emit(rows, "headcount", _val(nums[2 * k + j]),
                          _base(*_S10, level, 146009 if level == "overall" else ""),
                          {"topic": topic, "characteristic": label, **locc})
            got += 1
    _need(got, 12, "2010 T12.5")
    return _dedupe(rows, 300, "2006/2010")


# ------------------------------------------------------------------ 2015 ---
_S15 = ("LCMS 2015", "2015", "2015")
LAYOUT_2015 = {**LAYOUT_1996, "survey": _S15[0], "period": "2015", "reference_period": "2015"}
_U15 = "ZMW per adult equivalent per month (average national prices, April/May 2015)"


def parse_2015(path):
    pages = _pages(path)
    rows = []
    specs = [("E.1: Poverty incidence", "headcount", "overall", True),
             ("E.2: Poverty gap", "gap", "overall", False),
             ("E.3: Squared poverty gap", "severity", "overall", False),
             ("E.4: Extreme poverty incidence", "headcount", "extreme", True),
             ("E.5: Extreme poverty gap", "gap", "extreme", False),
             ("E.6: Squared extreme poverty gap", "severity", "extreme", False)]
    for cap, metric, level, ci in specs:
        name = "Lower poverty line" if level == "overall" else "Food poverty line"
        b = {**_base(*_S15, level, 214 if level == "overall" else 152, _U15), "line_name": name}
        got = 0
        for label, (est, _se, lo, hi) in read_rows(_segment(pages, re.escape("Table " + cap), r"Source:"), 4):
            c = _cut_for(label)
            _emit(rows, metric, est, b, c)
            if ci:
                _emit(rows, "headcount_ci_low", lo, b, c)
                _emit(rows, "headcount_ci_high", hi, b, c)
            got += 1
        _need(got, 20, f"2015 Table {cap}")
    return _dedupe(rows, 200, "2015")
