"""Libya — Bureau of Statistics and Census (BSC), Labour Force Survey 2022
("نتائج مسح القوى العاملة 2022").

The SAME report `labour/` reads for sector, industry and hours; this module
takes its headline series. LIBYAN NATIONALS AGED 15+ ONLY (survey population,
p.10) -- the non-Libyan workforce is excluded, which the `survey` value says.
Fieldwork 1-28 February 2022.

THE ARABIC TEXT LAYER IS UNREADABLE (glyphs mapped to the wrong code points,
and in caption fonts even digits: 2022 reads "2222"); the table CELLS' digits
are clean. As in labour/parsers/libya_labour.py, labels are STATED -- read
off the rendered pages and recorded verbatim in Arabic -- and rows are
anchored by arithmetic, never by text position. Both tables list the same 22
regions in the same order as labour's Table 13-a, then the national row.

* Table 8 (p.29) "العاملين اقتصاديا ومعدلات النشاط حسب المناطق والجنس":
  counts and "activity rates" by region x sex.
* Table 20 (p.57) "البطالة ومعدلات البطالة حسب المناطق والجنس": unemployed
  counts and unemployment rates by region x sex.

TABLE 8'S COUNT COLUMNS ARE THE EMPLOYED, THOUGH ITS CAPTION SAYS "ECONOMICALLY
ACTIVE" -- three independent checks: the national total 1 956 577 is the
employed total of the report's own summary (p.26: employed 1 956 577 +
unemployed 354 265 = active 2 310 842); each region equals Table 13-a's
employed total (Tobruk 62 924); and Table 20's rates are unemployed /
(Table 8 + unemployed) -- national 354 267 / 2 310 844 = 15,33 -> 15,3. So the
counts are filed as `employed`, the caption kept in series_label.
ITS RATES ARE ACTIVITY RATES over the working-age population: the national
49,1 (M 58,2 / F 39,6) is the labour force over the 15+ population the report
gives in prose (2 310 842 / 4 734 396 = 48,8; men 57,9; women 39,4) -- close,
not exact, so filed as `labour_force_participation_rate` as published, never
recomputed.

TABLE 20's rate is the report's only unemployment rate, defined (p.10-11) on
the international concepts the survey says it follows -> `strict`.

NOT COLLECTED: Table 13-b and 16 (rates belonging to no topic here), the
duration / reason tables after Table 20, the disability tables.

CROSS-CHECK: unemployment 15,3 (M 13,3 / F 18,4); Tobruk 10,1, Ghat 24,0;
unemployed 354 267 (M 185 201 / F 169 066); employed 1 956 577; activity
rate 49,1 (Benghazi 43,5).
"""
from __future__ import annotations

import fitz  # PyMuPDF
import pandas as pd

from . import _common as C

_SURVEY = ("Labour Force Survey 2022 (مسح القوى العاملة) -- Libyan nationals "
           "aged 15+")
_REGIONS = [
    "طبرق", "درنه", "الجبل الاخضر", "المرج", "بنغازى", "الواحات", "الكفرة",
    "سرت", "الجفرة", "مصراته", "المرقب", "طرابلس", "الجفارة", "الزاوية",
    "المنطقة الغربية", "الجبل الغربي", "نالوت", "سبها", "وادى الشاطئ",
    "مرزق", "وادى الحياة", "غات",
]
_SEX3 = [{"sex": "male"}, {"sex": "female"}, {}]
# table -> (pdf page, count topic, count label, rate topic, rate label, definition)
_TABLES = {
    8: (29, "employed", "العاملين اقتصاديا", "labour_force_participation_rate",
        "معدلات النشاط", "strict"),
    20: (57, "unemployed", "البطالة", "unemployment_rate", "معدلات البطالة",
         "strict"),
}


def _rows(page_text: str, where: str) -> list[list[float]]:
    """Runs of three integers (M, F, T with M + F = T) then three decimals."""
    toks = page_text.split()
    out, i = [], 0
    while i + 6 <= len(toks):
        w = toks[i:i + 6]
        if all(t.isdigit() for t in w[:3]) and all(
                t.count(".") == 1 and t.replace(".", "").isdigit() for t in w[3:]):
            m, f, t = (float(x) for x in w[:3])
            if abs(m + f - t) <= 2:
                out.append([m, f, t] + [float(x) for x in w[3:]])
                i += 6
                continue
        i += 1
    if len(out) != len(_REGIONS) + 1:
        raise ValueError(f"{where}: {len(out)} rows, want {len(_REGIONS) + 1}")
    *regions, nat = out
    for j in range(3):
        if abs(sum(r[j] for r in regions) - nat[j]) > 3:
            raise ValueError(f"{where}: regions do not sum to the national row")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    out = []
    with fitz.open(path) as doc:
        rows = {n: _rows(doc[pg - 1].get_text(), f"BSC Table {n}")
                for n, (pg, *_r) in _TABLES.items()}
    # Table 20's rate must be U / (Table 8 + U) -- the check that proves
    # Table 8's counts are the employed.
    for r8, r20 in zip(rows[8], rows[20]):
        for j in range(3):
            rate = 100 * r20[j] / (r8[j] + r20[j])
            if abs(rate - r20[3 + j]) > 0.11:
                raise ValueError(f"BSC: Table 20 rate {r20[3 + j]} is not "
                                 f"U/(E+U) = {rate:.2f} -- Table 8 is no longer "
                                 f"the employed")
    for n, (pg, ctopic, clab, rtopic, rlab, dfn) in _TABLES.items():
        for geo, r in zip(_REGIONS + [None], rows[n]):
            g = {"geography": geo} if geo else {}
            for sx, cnt, rate in zip(_SEX3, r[:3], r[3:]):
                kw = dict(survey=_SURVEY, period="2022",
                          reference_period="February 2022", frequency="ad_hoc",
                          working_age_base="15+", series_code=f"BSC LFS2022 T{n}",
                          **g, **sx)
                out.append(C.row(topic=ctopic, value=cnt, series_label=clab,
                                 definition="strict" if ctopic == "unemployed"
                                 else "not_applicable", **kw))
                out.append(C.row(topic=rtopic, value=rate, series_label=rlab,
                                 definition=dfn, **kw))
    return pd.DataFrame(out)
