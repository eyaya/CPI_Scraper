"""Libya — Bureau of Statistics and Census (BSC), Labour Force Survey 2022
("نتائج مسح القوى العاملة 2022").

LIBYAN NATIONALS ONLY. The survey population (p.10, "مجتمع الدراسة") is
"Libyans who are economically active, aged 15 and over, resident in Libya in
2022", so every figure here excludes the non-Libyan workforce, which is a
large share of employment in Libya. The schema has no nationality column, so
the restriction is carried in `survey` and must travel with any comparison.
Fieldwork: 1-28 February 2022 (p.13). Base 15+.

THE TEXT LAYER'S ARABIC IS UNREADABLE -- the embedded fonts map glyphs to the
wrong code points in both pdfplumber and PyMuPDF ("جدول" reads "جدرل"), and
in the caption font even digits are wrong (the year 2022 reads "2222", "60
hours" reads "62"). The TABLE CELLS' digits are clean. So:

* LABELS ARE STATED, NOT READ. Each label below was read off the rendered page
  (PyMuPDF pixmap at 110-150 dpi) and is recorded verbatim in Arabic, with an
  English gloss in a comment only. `characteristic` is the Arabic as printed.
* ROWS ARE ANCHORED BY ARITHMETIC, not by text position. A row is a run of
  cells whose own arithmetic holds -- male + female = total (Tables 12, 15),
  admin + public + private = total (13-a), or a printed row number 1..20
  followed by three percentages (14) -- and the number of rows found must
  equal the number of labels stated, in order.
* EVERY TABLE IS HELD TO ITS OWN TOTALS: counts sum to the printed total row,
  percentages to 100, regional counts to the national row.

TABLES:

* Table 12 (p.39) employed by "القطاع" -- counts and % by sex -> `sector`.
  The ten categories mix institutional sector (government, community-owned
  enterprise, joint-stock / joint / foreign companies) with status in the
  private economy (works for others / on own account with others / alone /
  for the family). BSC calls the whole list the sector; it partitions the
  employed, and it is filed under `sector` as BSC names it.
* Table 13-a (p.41) employed by region (22 regions + national) x administrative
  apparatus / public sector / private sector -> `sector`, region in
  `geography`. COUNTS ONLY -- see below. The region Total column is a level
  and is not collected.
* Table 14 (p.44) employed by the 20 sections of economic activity, % by sex
  -> `industry`. The sections follow ISIC Rev.4's A-T order and wording, but
  no scheme is named in the methodology pages (pp.10-14, read visually) or
  against the table -> National.
* Table 15 (p.46) employed by usual weekly hours band, counts and % by sex ->
  `hours`.

PUBLISHED DEFECTS KEPT AS PRINTED, EACH PINNED SO A CORRECTION IS NOTICED:

* TABLE 14'S COLUMNS SUM TO ABOUT 104, NOT 100 (male 103.9, female 104.6,
  total 104.1 from the printed shares). A uniform excess across all three
  columns, not one mislabelled row -- the same shape as Angola 2024 Q1 -- so the
  shares are collected with those sums pinned in `_T14_SUMS`; if BSC corrects
  the table the run raises and the pin is removed deliberately.
* TABLE 13-A'S PERCENTAGES CONTRADICT ITS OWN COUNTS in 20 of 23 rows --
  almost always the private-sector share, printed low (Tobruk 8.4 where
  5867/62924 is 9.3; national 12.8 where 261883/1955751 is 13.4), and the
  printed shares then sum to 98.5-99.7, not 100. The COUNTS are consistent
  every way they can be checked: each row's three sectors sum to its total,
  and the 22 regions sum exactly to the national row. Which side is wrong
  cannot be settled from the page, so the consistent side -- the counts -- is
  collected and the shares are not. (Not a recomputation: no share is
  derived.) The parse raises if the shares ever agree, so a corrected table
  gets collected in full.
* The tables' totals differ slightly from each other (employed 1 955 387 in
  Table 12, 1 955 751 in 13-a, 1 934 406 in 15, 1 956 577 in Tableau 6) --
  item non-response per question; each table is internally consistent.

NOT COLLECTED: Table 13-b (share employed by the state, per region -- a
rate); Table 16 (social-security coverage by age -- a rate); Tables 20, 25 and
the activity tables (unemployment's territory); disability tables 28-29. No
occupation or status-in-employment table is published.

CROSS-CHECK: government 1 595 163 (81.6%); private sector 261 883 (12.8%,
13-a); public administration and defence 44.1%; education 26.8%; under 25
hours 641 251 (33.2%).
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

from . import _common as C

_SURVEY = ("Labour Force Survey 2022 (مسح القوى العاملة) -- Libyan nationals "
           "aged 15+")
_REF = "February 2022"

_T12 = [
    "يعمل بالحكومة",                     # works in government
    "يعمل بمنشأة مملوكة للمجتمع",         # community-owned enterprise
    "يعمل بشركة مساهمة ليبية",            # Libyan joint-stock company
    "يعمل في شركة مشتركة عامة",           # public joint company
    "يعمل بشركة اجنبية",                  # foreign company
    "يعمل في شركة مشتركة خاصة",           # private joint company
    "يعمل لدى الغير",                     # works for others
    "يعمل لحسابه ومعه آخرون",             # own account, with others
    "يعمل بمفرده",                        # works alone
    "يعمل لدى الأسرة",                    # works for the family
]
_T13_REGIONS = [
    "طبرق", "درنه", "الجبل الاخضر", "المرج", "بنغازى", "الواحات", "الكفرة",
    "سرت", "الجفرة", "مصراته", "المرقب", "طرابلس", "الجفارة", "الزاوية",
    "المنطقة الغربية", "الجبل الغربي", "نالوت", "سبها", "وادى الشاطئ",
    "مرزق", "وادى الحياة", "غات",
]
_T13_CATS = ["الجهاز الاداري",   # administrative apparatus
             "القطاع العام",     # public sector
             "القطاع الخاص"]     # private sector
_T14 = [
    "الزراعه وصيد الاسماك",
    "التعدين واستغلال المحاجر",
    "الصناعه التحويلية",
    "امدادات الكهرباء والغاز والبخار وتكييف الهواء",
    "امدادات المياه وانشطة الصرف وادارة النفايات ومعالجتها",
    "التشييد والبناء",
    "تجارة الجملة والتجزئة واصلاح المركبات ذات المحركات والدرجات النارية",
    "النقل والتخزين",
    "انشطة الاقامة والخدمات الغذائية",
    "تكنولوجيا المعلومات والاتصالات",
    "الأنشطة المالية وانشطة التأمين",
    "الانشطة العقارية",
    "الانشطة المهنية والعلمية والتقنية",
    "انشطة الخدمات الإدارية وخدمات الدعم",
    "الادارة العامة والدفاع والضمان الاجتماعي الالزامي",
    "التعليم",
    "انشطة صحة الانسان والعمل الاجتماعي",
    "انشطة الفنون والترفيه والتسلية",
    "انشطة الخدمات الاخري",
    "انشطة الاسر المعيشية التي تستخدم افرادا انشطة الاسر المعيشية لانتاج "
    "السلع والخدمات",
]
_T15 = ["اقل من25ساعة", "25-34", "35-39", "40-48", "49-59",
        "أكثر من او يساوي 60 ساعة"]

# Published sums of Table 14's shares (male, female, total) -- see docstring.
_T14_SUMS = (103.9, 104.6, 104.1)

_SEX3 = ("male", "female", "total")
_TOK = re.compile(r"\d+(?:\.\d+)?%?")


def _candidates(doc, table: str) -> list[list[str]]:
    """Cell tokens after every caption that reads as Table `table`. The
    caption font garbles digits too -- Table 10 (p.35) reads "جدرل12", the
    same as Table 12 -- so a caption number selects CANDIDATES only."""
    cap = re.compile(rf"جدرل\s*\(?\s*{table}\b")
    out = []
    for page in doc:
        text = page.get_text()
        m = cap.search(text)
        if m:
            out.append(_TOK.findall(text[m.end():]))
    return out


def _one(doc, table: str, reader, *args):
    """The single candidate page whose cells fit the stated table -- its label
    count, its arithmetic and its totals. None, or several, is an error."""
    got, why = [], []
    for toks in _candidates(doc, table):
        try:
            got.append(reader(toks, *args))
        except ValueError as e:
            why.append(str(e))
    _check(len(got) == 1, f"Table {table}: {len(got)} candidate pages fit "
                          f"({'; '.join(why)})")
    return got[0]


def _num(t: str) -> float:
    return float(t.rstrip("%"))


def _runs(toks: list[str], n_int: int, n_dec: int) -> list[list[float]]:
    """Runs of n_int integers then n_dec decimals whose integers add up
    (the last integer is the sum of the others)."""
    out, i = [], 0
    while i + n_int + n_dec <= len(toks):
        w = toks[i:i + n_int + n_dec]
        ints, decs = w[:n_int], w[n_int:]
        if (all("." not in t for t in ints) and all("." in t for t in decs)
                and sum(int(t) for t in ints[:-1]) == int(ints[-1])):
            out.append([_num(t) for t in w])
            i += n_int + n_dec
        else:
            i += 1
    return out


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(f"BSC LFS 2022: {msg}")


def _row(topic, lab, value, measure, sex="total", geography="Total country",
         classification="Not applicable", code=""):
    return C.row(topic=topic, characteristic=lab, classification=classification,
                 value=value, survey=_SURVEY, period="2022",
                 reference_period=_REF, frequency="ad_hoc", measure=measure,
                 unit="persons" if measure == "count" else "percent",
                 sex=sex, geography=geography, working_age_base="15+",
                 series_code=code)


def _sex_table(toks, labels, topic, code, total_label="Total"):
    """Tables 12 and 15: male, female, total counts then the same as %."""
    runs = _runs(toks, 3, 3)
    _check(len(runs) == len(labels) + 1,
           f"{code}: {len(runs)} rows for {len(labels)} labels + total")
    *body, total = runs
    for j in range(3):
        _check(abs(sum(r[j] for r in body) - total[j]) <= 2,
               f"{code}: counts column {j} do not sum to the total")
        _check(abs(sum(r[3 + j] for r in body) - 100) <= 0.3
               and total[3 + j] == 100.0, f"{code}: % column {j} != 100")
    out = []
    for lab, r in zip(labels + [total_label], runs):
        for j, sex in enumerate(_SEX3):
            out.append(_row(topic, lab, r[j], "count", sex=sex, code=code))
            out.append(_row(topic, lab, r[3 + j], "share", sex=sex, code=code))
    return out


def _table_13a(toks):
    code = "BSC LFS 2022 T13-a"
    runs = _runs(toks, 4, 4)
    names = _T13_REGIONS + ["Total country"]
    _check(len(runs) == len(names), f"{code}: {len(runs)} rows for {len(names)}")
    *regions, nat = runs
    for j in range(4):
        _check(sum(r[j] for r in regions) == nat[j],
               f"{code}: regions do not sum to the national row, column {j}")
    # The printed shares contradict these counts in most rows (see docstring).
    # If they ever agree throughout, BSC has corrected the table and the
    # shares can be collected: raise so that is decided deliberately.
    bad = sum(abs(r[j] / r[3] * 100 - r[4 + j]) > 0.06
              for r in runs for j in range(3))
    _check(bad > 0, f"{code}: printed shares now agree with the counts -- "
                    f"collect them")
    out = []
    for name, r in zip(names, runs):
        for j, cat in enumerate(_T13_CATS):
            out.append(_row("sector", cat, r[j], "count", geography=name, code=code))
    return out


def _table_14(toks):
    code = "BSC LFS 2022 T14"
    rows, i = [], 0
    for n in range(1, len(_T14) + 1):
        while i < len(toks) and toks[i] != str(n):
            i += 1
        w = toks[i + 1:i + 4]
        _check(len(w) == 3 and all(t.endswith("%") for t in w),
               f"{code}: row {n} reads {w}")
        rows.append([_num(t) for t in w])
        i += 4
    total = [_num(t) for t in toks[i:i + 3]]
    _check(total == [100.0] * 3, f"{code}: total row reads {toks[i:i + 3]}")
    for j, want in enumerate(_T14_SUMS):
        got = round(sum(r[j] for r in rows), 1)
        _check(got == want, f"{code}: column {j} sums to {got}, pinned {want} "
                            f"-- if BSC corrected the table, update _T14_SUMS")
    out = []
    for lab, r in zip(_T14 + ["Total"], rows + [total]):
        for j, sex in enumerate(_SEX3):
            out.append(_row("industry", lab, r[j], "share", sex=sex,
                            classification="National", code=code))
    return out


def parse(path: str) -> pd.DataFrame:
    with fitz.open(path) as doc:
        out = (_one(doc, "12", _sex_table, _T12, "sector", "BSC LFS 2022 T12")
               + _one(doc, "13", _table_13a)
               + _one(doc, "14", _table_14)
               + _one(doc, "15", _sex_table, _T15, "hours", "BSC LFS 2022 T15"))
    return pd.DataFrame(out)
