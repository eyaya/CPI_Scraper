"""South Africa -- the superseded editions of Stats SA's "Poverty Trends in
South Africa" (Report 03-10-06), each a re-estimate of the same IES / LCS
rounds on its own line series. Both are Wayback `id_` captures of Stats SA's
own PDFs (statssa.gov.za answers plain requests with an Incapsula challenge;
see south_africa.yaml).

parse_2014 -- PTR 2014, "An examination of absolute poverty between 2006 and
    2011" (Report-03-10-06March2014.pdf). IES 2005/06, LCS 2008/09, IES
    2010/11. Lines per person per month at March prices (Table 2): FPL
    210 / 305 / 321, LBPL 300 / 416 / 443, UBPL 431 / 577 / 620. Every
    characteristic table is on the UBPL.
      Tables 3 / 4 -- national FPL headcount and gap (the UBPL rows repeat
        Table 7's Total row, which also gives P2)
      Tables 7, 9, 10 (18+), 11, 12 -- persons: P0 P1 P2 by sex, age,
        education, province, settlement type (UBPL)
      Tables 14, 16, 17, 18 -- households: by sex, education of the head,
        province, settlement type (UBPL); Table 17's Total row is the
        national household rate (Table 14's prints its digits split, "4 2,2")
parse_2017 -- PTR 2017, "... between 2006 and 2015" (Report-03-10-062015.pdf).
    IES 2005/06, LCS 2008/09, IES 2010/11, LCS 2014/15, on the rebased lines
    of Table 1.2 (March prices; 2015 April): FPL 219 / 318 / 335 / 441, LBPL
    370 / 456 / 501 / 647, UBPL 575 / 709 / 779 / 992.
      Tables 3.1-3.20 -- persons: P0 P1 P2 by sex, age, education (18+),
        province, settlement type, on each of UBPL / LBPL / FPL
      Tables 4.1-4.20 -- households: by sex, age and education of the head,
        province, settlement type, on each line
      National rows: the Total rows of the sex tables (3.1 / 3.9 / 3.15 and
        4.1 / 4.9 / 4.15); Tables 2.1 / 2.2 print the same P0 and P1 and are
        checked against them, not read twice.

THE 2017 TEXT LAYER IS CID-CODED, AND IS DECODED WITH A CHARACTER MAP -- NOT
OCR. Every font is a CID-keyed CFF subset (Identity-H, no ToUnicode), and
pdfplumber returns "(cid:N)"; the CIDs are the characters' own code points
(CID 32 = space; the subset charsets list cid00032, cid00034 ...). Decoded
with chr(N): all 108 printed page numbers equal the PDF page index minus 12,
digit for digit, and the decoded Table 2.1 prints Stats SA's published 2015
headline rates (UBPL 55,5%, FPL 25,2%).

Population group is not collected (no schema topic), nor counts of poor
(printed in MILLIONS), shares, Gini, NDP/SDG and SAMPI tables. Survey labels
carry the edition ("IES 2010/11 (Poverty Trends 2014)") so each re-estimate
stays beside the 2025 edition's.

CROSS-CHECK (verbatim): 2014 -- UBPL 57,2 / 56,8 / 45,5, FPL 26,6 / 32,4 /
20,2, UBPL gap 2011 19,6, households 42,2 / 42,7 / 32,9, Limpopo 2009 78,9;
2017 -- UBPL 66,6 / 62,1 / 53,2 / 55,5, LBPL 51,0 / 47,6 / 36,4 / 40,0, FPL
28,4 / 33,5 / 21,4 / 25,2, UBPL P2 2015 17,0, households UBPL 2015 40,0,
Limpopo households FPL 2009 40,0.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

UNIT = "ZAR per person per month"
_NAME = {"FPL": ("extreme", "Food poverty line (FPL)"),
         "LBPL": ("other", "Lower-bound poverty line (LBPL)"),
         "UBPL": ("overall", "Upper-bound poverty line (UBPL)")}
_SURVEY = {"2006": ("IES 2005/06", "2005/06"), "2009": ("LCS 2008/09", "2008/09"),
           "2011": ("IES 2010/11", "2010/11"), "2015": ("LCS 2014/15", "2014/15")}
_ED = {
    "2014": (" (Poverty Trends 2014)", ["2006", "2009", "2011"],
             {"FPL": {"2006": 210, "2009": 305, "2011": 321},
              "LBPL": {"2006": 300, "2009": 416, "2011": 443},
              "UBPL": {"2006": 431, "2009": 577, "2011": 620}}),
    "2017": (" (Poverty Trends 2017)", ["2006", "2009", "2011", "2015"],
             {"FPL": {"2006": 219, "2009": 318, "2011": 335, "2015": 441},
              "LBPL": {"2006": 370, "2009": 456, "2011": 501, "2015": 647},
              "UBPL": {"2006": 575, "2009": 709, "2011": 779, "2015": 992}}),
}
LAYOUT_2014 = {"survey": "IES 2010/11" + _ED["2014"][0], "welfare_aggregate": "consumption",
               "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
               "line_type": "national", "line_level": "overall",
               "line_name": _NAME["UBPL"][1], "line_unit": UNIT,
               "period": "2011", "reference_period": "2010/11", "tables": []}
LAYOUT_2017 = {**LAYOUT_2014, "survey": "LCS 2014/15" + _ED["2017"][0],
               "period": "2015", "reference_period": "2014/15"}

_PROVINCES = {"Western Cape", "Eastern Cape", "Northern Cape", "Free State", "KwaZulu-Natal",
              "North West", "Gauteng", "Mpumalanga", "Limpopo"}
_EDU = {"None", "Some primary", "Primary", "Some secondary", "Matric", "Higher"}
_AGE = re.compile(r"\d+ ?[–-] ?\d+|\d+\+")


def _cut(topic, label):
    if topic == "province":
        return {"topic": "total", "geography": label} if label in _PROVINCES else None
    if topic in ("sex", "sex_of_head"):
        sx = {"Male": "male", "Female": "female", "Male-headed": "male",
              "Female-headed": "female"}.get(label)
        return {"topic": topic, "characteristic": label, "sex": sx} if sx else None
    if topic == "locality":
        loc = {"Urban": "urban", "Rural": "rural"}.get(label)
        return {"topic": "locality", "locality": loc, "locality_label": label} if loc else None
    if topic in ("age", "age_of_head"):
        return {"topic": topic, "characteristic": label} if _AGE.fullmatch(label) else None
    if topic in ("education", "education_of_head"):
        return {"topic": topic, "characteristic": label} if label in _EDU else None
    raise ValueError(topic)


def _lines(text):
    out = []
    for ln in text.splitlines():
        s = re.sub(r"\s+", " ", ln).strip()
        if not s or s.startswith("=== p") or re.fullmatch(r"\d{1,3}", s):
            continue
        # Split labels as printed: "Mpum alanga" (PTR 2014 Table 11), "M ale"
        # (PTR 2017 Table 4.15).
        s = s.replace("Mpum alanga", "Mpumalanga")
        out.append(re.sub(r"^M ale ", "Male ", s))
    # "Some" wraps onto the next line in the education tables.
    j = []
    for s in out:
        if j and j[-1] == "Some":
            j[-1] = f"Some {s}"
        else:
            j.append(s)
    return j


def _segment(lines, tid):
    """Lines from the LAST caption 'Table <tid>:' to the next caption."""
    cap = re.compile(rf"^Table {re.escape(tid)}:")
    starts = [i for i, s in enumerate(lines) if cap.match(s)]
    if not starts:
        raise ValueError(f"Stats SA PTR: Table {tid} not found")
    i = starts[-1]
    seg = []
    for s in lines[i + 1:i + 80]:
        if re.match(r"^(Table|Figure) \d+(\.\d+)?:", s):
            break
        seg.append(s)
    return seg


def _base(ed, period, line, unit):
    suffix, _, values = _ED[ed]
    level, name = _NAME[line]
    survey, ref = _SURVEY[period]
    return dict(survey=survey + suffix, welfare_aggregate="consumption", unit_of_analysis=unit,
                line_type="national", line_level=level, line_name=name,
                line_value=values[line][period], line_unit=UNIT,
                period=period, reference_period=ref, frequency="ad_hoc")


def _val(tok):
    return float(tok.replace(",", "."))


def _measures(rows, ed, seg, topic, unit, line, total=None):
    """Rows 'label P0 x years, P1 x years, P2 x years'. `total`: attributes for
    the Total row, or None to skip it. Returns rows read."""
    years = _ED[ed][1]
    k = len(years)
    rx = re.compile(rf"^(.+?) ((?:\d+,\d ){{{3 * k - 1}}}\d+,\d)$")
    n = 0
    for s in seg:
        m = rx.match(s)
        if not m:
            continue
        label, vals = m.group(1), [_val(t) for t in m.group(2).split()]
        if label in ("Total", "All adults (18+)"):
            cut = total
        else:
            cut = _cut(topic, label)
        if cut is None:
            continue
        extra = {"age_group": "18 years and older"} if topic == "education" else {}
        for j, metric in enumerate(("headcount", "gap", "severity")):
            for y, v in zip(years, vals[j * k:(j + 1) * k]):
                rows.append(C.row(metric=metric, value=v, **_base(ed, y, line, unit), **cut, **extra))
        n += 1
    return n


_EXPECT = {"sex": 2, "sex_of_head": 2, "age": 7, "age_of_head": 7, "education": 6,
           "education_of_head": 6, "province": 9, "locality": 2}


def _read(rows, ed, lines, tid, topic, unit, line, total=None):
    got = _measures(rows, ed, _segment(lines, tid), topic, unit, line, total)
    want = _EXPECT[topic] + (1 if total is not None else 0)
    if got != want:
        raise ValueError(f"Stats SA PTR {ed} Table {tid}: {got} rows, expected {want}")


def _text(path, decode_cid=False):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        t = "\n".join(f"=== p{i + 1}\n" + (p.extract_text() or "") for i, p in enumerate(pdf.pages))
    if decode_cid:
        t = re.sub(r"\(cid:(\d+)\)", lambda m: chr(int(m.group(1))), t)
    return t


def parse_2014(path: str) -> pd.DataFrame:
    lines = _lines(_text(path))
    rows: list[dict] = []
    nat = {"topic": "total"}
    # Tables 3 / 4: national FPL headcount and gap.
    joined = " ".join(_segment(lines, "3") + _segment(lines, "4"))
    for rx, metric in ((r"living in extreme poverty((?: \d+,\d%){3})", "headcount"),
                       (r"Poverty gap for the FPL((?: \d+,\d%){3})", "gap")):
        m = re.search(rx, joined)
        if not m:
            raise ValueError(f"Stats SA PTR 2014: national FPL {metric} not found")
        for y, tok in zip(_ED["2014"][1], m.group(1).split()):
            rows.append(C.row(metric=metric, value=_val(tok.rstrip("%")),
                              **_base("2014", y, "FPL", "person"), **nat))
    _read(rows, "2014", lines, "7", "sex", "person", "UBPL", total=nat)
    _read(rows, "2014", lines, "9", "age", "person", "UBPL")
    _read(rows, "2014", lines, "10", "education", "person", "UBPL", total=nat)
    _read(rows, "2014", lines, "11", "province", "person", "UBPL")
    _read(rows, "2014", lines, "12", "locality", "person", "UBPL")
    _read(rows, "2014", lines, "14", "sex_of_head", "household", "UBPL")
    _read(rows, "2014", lines, "16", "education_of_head", "household", "UBPL")
    _read(rows, "2014", lines, "17", "province", "household", "UBPL", total=nat)
    _read(rows, "2014", lines, "18", "locality", "household", "UBPL")
    return pd.DataFrame.from_records(rows)


# 2017: table numbers per line, persons (3.x) and households (4.x).
_T17 = {"UBPL": {"p": {"sex": "3.1", "age": "3.3", "education": "3.5", "province": "3.7", "locality": "3.8"},
                 "h": {"sex_of_head": "4.1", "age_of_head": "4.4", "education_of_head": "4.5",
                       "province": "4.7", "locality": "4.8"}},
        "LBPL": {"p": {"sex": "3.9", "age": "3.11", "education": "3.12", "province": "3.13", "locality": "3.14"},
                 "h": {"sex_of_head": "4.9", "age_of_head": "4.11", "education_of_head": "4.12",
                       "province": "4.13", "locality": "4.14"}},
        "FPL": {"p": {"sex": "3.15", "age": "3.17", "education": "3.18", "province": "3.19", "locality": "3.20"},
                "h": {"sex_of_head": "4.15", "age_of_head": "4.17", "education_of_head": "4.18",
                      "province": "4.19", "locality": "4.20"}}}


def parse_2017(path: str) -> pd.DataFrame:
    lines = _lines(_text(path, decode_cid=True))
    rows: list[dict] = []
    nat = {"topic": "total"}
    for line, groups in _T17.items():
        for key, unit in (("p", "person"), ("h", "household")):
            for topic, tid in groups[key].items():
                # National = the sex tables' Total rows; education (persons)
                # Total = the 18+ population.
                total = nat if topic in ("sex", "sex_of_head", "education") else None
                _read(rows, "2017", lines, tid, topic, unit, line, total)
    df = pd.DataFrame.from_records(rows)
    # Tables 2.1 / 2.2 print the same national P0 and P1: check, do not re-read.
    joined = " ".join(_segment(lines, "2.1") + _segment(lines, "2.2"))
    checks = [(r"population that is UBPL poor((?: \d+,\d%){4})", "headcount", "UBPL"),
              (r"population that is LBPL poor((?: \d+,\d%){4})", "headcount", "LBPL"),
              (r"poverty \(below FPL\)((?: ?\d+,\d%){4})", "headcount", "FPL"),
              (r"Poverty gap for the UBPL((?: \d+,\d%){4})", "gap", "UBPL"),
              (r"Poverty gap for the LBPL((?: \d+,\d%){4})", "gap", "LBPL"),
              (r"Poverty gap for the FPL((?: \d+,\d%){4})", "gap", "FPL")]
    natl = df[(df.topic == "total") & (df.geography == "Total country") & (df.unit_of_analysis == "person")
              & (df.age_group == "Total")]
    for rx, metric, line in checks:
        m = re.search(rx, joined)
        if not m:
            raise ValueError(f"Stats SA PTR 2017: Table 2.1/2.2 {line} {metric} not found")
        printed = [_val(t.rstrip("%")) for t in m.group(1).split()]
        got = natl[(natl.metric == metric) & (natl.line_name == _NAME[line][1])].sort_values("period")["value"].tolist()
        if got != printed:
            raise ValueError(f"Stats SA PTR 2017: {line} {metric} {got} vs Table 2.1/2.2 {printed}")
    return df
