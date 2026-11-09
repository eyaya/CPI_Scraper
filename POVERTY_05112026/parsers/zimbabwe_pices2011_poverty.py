"""Zimbabwe -- PICES 2011/12 poverty report (ZIMSTAT, "Poverty and Poverty
Datum Line Analysis in Zimbabwe 2011/12", April 2013; zimstat.co.zw/
Poverty_Statistics/Zimbabwe_Poverty_Report_2011_published_17032013.pdf).

THE TEXT LAYER IS FONT-SHIFTED, AND IS DECODED WITH A CHARACTER MAP -- NOT OCR.
The four embedded Times New Roman subsets (IODIxx+TimesNewRoman[,Bold|,Italic|
,BoldItalic]) draw the glyph of character c-2 at code c: "Vcdng" is printed
"Table", "4235" is 2013. Proof from the font itself: for every code 34..126
the PDF's /Widths entry equals the advance width of character c-2 in standard
Times New Roman (81/84, 70/71, 77/79, 29/29 codes; the exceptions are only the
three high codes below), and for no other shift (<= 25 matches). The three
high codes are punctuation, identified by width: 130 (333) a closing quote,
155 (444 / 556 italic) a double quote, 164 (1000) an em dash. Other fonts
(Arial cover, Symbol, the IOENNK/IOMNHG Times subsets) are not shifted and are
left alone. The decoded text reproduces, verbatim, the 2011/12 figures ZIMSTAT
prints in plain text in the PICES 2017 report (households 62.6, people 72.3).

Lines: Total Consumption Poverty Line (TCPL, upper -> overall) and Food
Poverty Line (FPL, lower -> extreme); P1/P2 FGT on the TCPL; consumption per
capita. HOUSEHOLDS except Table 2.4's People block and Table 2.8. The lines
vary by province and month (Tables 2.1/2.2 give provincial means), so
line_value is blank. Survey label "PICES 2011/12 (2011/12 poverty report)"
keeps this report's estimates apart from the 2017 report's republication.

Collected
  2.4    households and people x rural / urban / all: P0, extreme P0, P1, P2
  2.7    10 provinces (households): share of poor households, P0, ext, P1, P2
  2.8    10 provinces (people): P0, extreme P0, P1, P2
  2.10   urban areas of the 10 provinces: share of poor, P0, ext, P1, P2
  2.13-2.15  headship (male / female-headed, de facto, de jure divorced /
         widowed / never married) x all / rural / urban: P0, ext, P1, P2
  2.16   P0 by main activity of the head x rural / urban / all
  2.17   P0 and extreme P0 by sector of employment of the head x rural / urban
  3.1    8 rural provinces: share of poor, P0, ext, P2, P1 -- THE PRINTED
         HEADER puts the gap before the severity but the columns are P2 then
         P1: the Total row (76.0 22.9 20.6 36.1) is Table 2.4's rural row
         (P1 36.1, P2 20.6), and P1 >= P2 in every row.
  3.2    4 rural land-use areas: P0, ext, P2, P1 (the same column order as
         3.1: P1 >= P2 in every row).
  3.4    P0 by household size x rural land-use area
  3.6    P0 by main activity of the head x rural land-use area
  3.22-3.24  education of head x all / rural / urban: P0, ext, P1, P2
  3.25   education x sex of head: P0, ext, P1, P2
Not collected: 2.9 (a simulation), 2.18-2.22 (members' employment and income
source: no topic), asset / energy / health / school tables. Cells starred for
small samples (Employer 32.0*) are kept as printed, as in the 2001 report.

CROSS-CHECK (verbatim): households 62.6 / 16.2 / 27.7 / 15.2; people 72.3 /
22.5 / 34.1 / 19.6; rural households 76.0, urban 38.2; Matabeleland North
households 81.7, people 89.9; Harare 35.7; provincial shares of poor
households sum to 100.0 (2.7), 100.1 (2.10, urban) and 100.2 (3.1, rural;
printed totals 100.0); widowed female heads 68.9; rural Manicaland P1 35.9,
P2 20.0 (3.1, after the column fix);
communal lands 79.4; post-secondary heads 17.5.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_SURVEY = "PICES 2011/12 (2011/12 poverty report)"
_TPL, _FPL = "Total Consumption Poverty Line (TCPL)", "Food Poverty Line (FPL)"
PROVS = ["Manicaland", "Mashonaland Central", "Mashonaland East", "Mashonaland West",
         "Matabeleland North", "Matabeleland South", "Midlands", "Masvingo", "Bulawayo", "Harare"]
LAYOUT = {"survey": _SURVEY, "welfare_aggregate": "consumption", "unit_of_analysis": "household",
          "frequency": "ad_hoc", "decimal": ".", "line_type": "national", "line_level": "overall",
          "line_name": _TPL, "period": "2011", "reference_period": "2011/12", "tables": []}
_N = r"(\d+\.\d\*?|-)"

# ------------------------------------------------------------ text decode ---
_SHIFTED = re.compile(r"^IODI[A-Z]{2}\+TimesNewRoman")
_HIGH = {"‚": "'", "›": '"', "\xa4": "-"}   # codes 130, 155, 164


def _decode(ch: str) -> str:
    o = ord(ch)
    return chr(o - 2) if 34 <= o <= 126 else _HIGH.get(ch, ch)


def decoded_text(path: str) -> str:
    """The report's text with the shifted fonts' characters mapped back."""
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for c in pg.chars:
                if _SHIFTED.match(c["fontname"]):
                    c["text"] = _decode(c["text"])
            pages.append(pg.extract_text() or "")
    return "\n".join(pages)


# ------------------------------------------------------------------- rows ---
def _b(level, unit="household"):
    return dict(survey=_SURVEY, welfare_aggregate="consumption", unit_of_analysis=unit,
                line_type="national", line_level=level,
                line_name=_TPL if level == "overall" else _FPL,
                period="2011", reference_period="2011/12", frequency="ad_hoc")


def _emit(rows, metric, v, level, cut, unit="household"):
    if v in (None, "-"):
        return
    rows.append(C.row(metric=metric, value=float(str(v).rstrip("*")), **_b(level, unit), **cut))


def _four(rows, vals, cut, unit="household"):
    p0, ext, p1, p2 = vals
    _emit(rows, "headcount", p0, "overall", cut, unit)
    _emit(rows, "headcount", ext, "extreme", cut, unit)
    _emit(rows, "gap", p1, "overall", cut, unit)
    _emit(rows, "severity", p2, "overall", cut, unit)


def _seg(text, caption, end="Source"):
    # The LAST occurrence: the first is the list of tables.
    i = text.rindex(caption)
    return [l.strip() for l in text[i:text.index(end, i)].splitlines()]


_LOC = {"Rural": {"topic": "locality", "locality": "rural", "locality_label": "Rural"},
        "Urban": {"topic": "locality", "locality": "urban", "locality_label": "Urban"},
        "All Zimbabwe": {}}


def _place(loc):
    return {k: v for k, v in _LOC[loc].items() if k != "topic"}


_LAND = ["Communal lands", "Small scale commercial farms", "Large scale commercial farms",
         "Resettlement areas"]


def _land(lab):
    return {"locality": "rural", "locality_label": lab}


def parse(path: str) -> pd.DataFrame:
    text = decoded_text(path)
    rows, n = [], {}

    def count(k, got):
        n[k] = n.get(k, 0) + got

    unit = None
    for ln in _seg(text, "Table 2.4: Poverty Indices by Place of Residence"):
        if ln in ("Households", "People"):
            unit = "household" if ln == "Households" else "person"
        m = re.match(rf"^(Rural|Urban|All Zimbabwe) {_N} {_N} {_N} {_N}$", ln)
        if m and unit:
            _four(rows, m.groups()[1:], _LOC[m.group(1)], unit)
            count("2.4", 1)
    prov = "|".join(PROVS)
    for ln in _seg(text, "Table 2.7: Household Poverty Indices by Province"):
        m = re.match(rf"^({prov}) {_N} {_N} {_N} {_N} {_N}$", ln)
        if m:
            c = {"geography": m.group(1)}
            _emit(rows, "poor_share", m.group(2), "overall", c)
            _four(rows, m.groups()[2:], c)
            count("2.7", 1)
    for ln in _seg(text, "Table 2.8: Prevalence of Poor and Severely Poor People"):
        m = re.match(rf"^({prov}) {_N} {_N} {_N} {_N}$", ln)
        if m:
            _four(rows, m.groups()[1:], {"geography": m.group(1)}, "person")
            count("2.8", 1)
    for ln in _seg(text, "Table 2.10: Household Poverty Prevalence by Province and by Urban"):
        m = re.match(rf"^({prov}) {_N} {_N} {_N} {_N} {_N}$", ln)
        if m:
            c = {"geography": m.group(1), **_LOC["Urban"]}
            _emit(rows, "poor_share", m.group(2), "overall", c)
            _four(rows, m.groups()[2:], c)
            count("2.10", 1)
    for cap, loc in (("Table 2.13: Household Poverty by Household Headship", "All Zimbabwe"),
                     ("Table 2.14: Household Poverty by Household Headship", "Rural"),
                     ("Table 2.15: Household Poverty by Household Headship", "Urban")):
        head = None
        for ln in _seg(text, cap):
            m = re.match(rf"^(Male-headed|Female headed|Defacto|-Divorced|-Widowed|Never [Mm]arried) "
                         rf"{_N} {_N} {_N} {_N}$", ln)
            if not m:
                continue
            lab = m.group(1)
            if lab in ("Male-headed", "Female headed"):
                head = "male" if lab.startswith("Male") else "female"
                c = {"topic": "sex_of_head", "characteristic": lab, "sex": head}
            else:
                kind = {"Defacto": "De facto", "-Divorced": "De jure: divorced",
                        "-Widowed": "De jure: widowed"}.get(lab, "De jure: never married")
                c = {"topic": "marital_status_of_head", "sex": head,
                     "characteristic": f"{'Male' if head == 'male' else 'Female'}-headed: {kind}"}
            _four(rows, m.groups()[1:], {**c, **_place(loc)})
            count(cap[:10], 1)
    for ln in _seg(text, "Table 2.16: Prevalence of Household Poverty by Main Activity"):
        m = re.match(rf"^([A-Z][A-Za-z/ -]+?) {_N} {_N} {_N}$", ln)
        if m:
            for loc, v in zip(("Rural", "Urban", "All Zimbabwe"), m.groups()[1:]):
                _emit(rows, "headcount", v, "overall",
                      {"topic": "employment_of_head", "characteristic": m.group(1), **_place(loc)})
            count("2.16", 1)
    for ln in _seg(text, "Table 2.17: Prevalence of Household Poverty by Sector"):
        m = re.match(rf"^(Communal farmer|Resettlement farmer|Own account worker other|Government worker|"
                     rf"Parastatal worker|Private sector|Formal sector|Informal sector) {_N} {_N} {_N} {_N}$", ln)
        if m:
            vals = m.groups()[1:]
            for k, loc in enumerate(("Rural", "Urban")):
                c = {"topic": "employment_of_head", "characteristic": f"Sector: {m.group(1)}", **_place(loc)}
                _emit(rows, "headcount", vals[2 * k], "overall", c)
                _emit(rows, "headcount", vals[2 * k + 1], "extreme", c)
            count("2.17", 1)
    # 3.1 / 3.2: columns are P0, extreme, P2, P1 (see docstring).
    for ln in _seg(text, "Table 3.1: Household Poverty in Percentages by Province in Rural"):
        m = re.match(rf"^({prov}) {_N} {_N} {_N} {_N} {_N}$", ln)
        if m:
            c = {"geography": m.group(1), **_LOC["Rural"]}
            share, p0, ext, p2, p1 = m.groups()[1:]
            _emit(rows, "poor_share", share, "overall", c)
            _four(rows, (p0, ext, p1, p2), c)
            count("3.1", 1)
    for ln in _seg(text, "Table 3.2: Rural Household Poverty Prevalence by Land Use"):
        m = re.match(rf"^({'|'.join(_LAND)}) {_N} {_N} {_N} {_N}$", ln)
        if m:
            p0, ext, p2, p1 = m.groups()[1:]
            _four(rows, (p0, ext, p1, p2), {"topic": "locality", **_land(m.group(1))})
            count("3.2", 1)
    for ln in _seg(text, "Table 3.4: Prevalence of Household Poverty by Size and Rural"):
        m = re.match(rf"^(1|2-3|4-5|6-7|8\+) {_N} {_N} {_N} {_N}$", ln)
        if m:
            for lab, v in zip(_LAND, m.groups()[1:]):
                _emit(rows, "headcount", v, "overall",
                      {"topic": "household_size", "characteristic": m.group(1), **_land(lab)})
            count("3.4", 1)
    for ln in _seg(text, "Table 3.6: Prevalence of Household Poverty by Main Activity of the Household Head,"):
        m = re.match(rf"^([A-Z][A-Za-z/ ().-]+?) {_N} {_N} {_N} {_N}$", ln)
        if m:
            for lab, v in zip(_LAND, m.groups()[1:]):
                _emit(rows, "headcount", v, "overall",
                      {"topic": "employment_of_head", "characteristic": m.group(1), **_land(lab)})
            count("3.6", 1)
    edu = r"(No education|Primary education|Secondary education|Post-secondary education)"
    for cap, loc in (("Table 3.22: Household Poverty by Education", "All Zimbabwe"),
                     ("Table 3.23: Household Poverty by Education", "Rural"),
                     ("Table 3.24: Household Poverty by Education", "Urban")):
        for ln in _seg(text, cap):
            m = re.match(rf"^{edu} {_N} {_N} {_N} {_N}$", ln)
            if m:
                _four(rows, m.groups()[1:], {"topic": "education_of_head", "characteristic": m.group(1),
                                             **_place(loc)})
                count(cap[:10], 1)
    sex = None
    for ln in _seg(text, "Table 3.25: Poverty Indices for Households by Sex and Education"):
        if ln in ("Male-headed", "Female-headed"):
            sex = "male" if ln.startswith("Male") else "female"
        m = re.match(rf"^(None|Primary school|Secondary school|Post-secondary school) {_N} {_N} {_N} {_N}$", ln)
        if m and sex:
            _four(rows, m.groups()[1:], {"topic": "education_of_head", "characteristic": m.group(1),
                                         "sex": sex})
            count("3.25", 1)
    want = {"2.4": 6, "2.7": 10, "2.8": 10, "2.10": 10, "Table 2.13": 10, "Table 2.14": 10,
            "Table 2.15": 10, "2.16": 7, "2.17": 8, "3.1": 8, "3.2": 4, "3.4": 5, "3.6": 6,
            "Table 3.22": 4, "Table 3.23": 4, "Table 3.24": 4, "3.25": 8}
    short = {k: (n.get(k, 0), v) for k, v in want.items() if n.get(k, 0) != v}
    if short:
        raise ValueError(f"Zimbabwe PICES 2011/12: table rows (got, want) {short}")
    return pd.DataFrame.from_records(rows)
