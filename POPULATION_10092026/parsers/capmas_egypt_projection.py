"""CAPMAS Egypt -- "إسقاطات السكان المستقبلية" (Future Population Projections)
2022-2072, CAPMAS publication 106 (2017-census based, issue year 2022, posted
2026-01-08). Arabic PDF; the Arabic text layer is ligature-mangled, so tables
are read by POSITION and their figures, never by Arabic labels except where
noted.

Added 2026-10-13 as a SECOND Egypt descriptor (egypt_projections.yaml) beside
egypt.yaml (publication 150, population estimates on 1 January, by
governorate).

Read:
* Annex A, Tables A-1..A-4 "عدد السكان وفقاً لفئات السن والنوع في منتصف عام
  <year>": MID-YEAR population 2018-2021 by 5-year age group (0-4 .. 80+) x
  sex, persons. series_type estimate (past years, the projection's base
  reconstruction); series_code says mid-year.
* Table 5-1 "تقديرات السكان طبقا لفروض الإنجاب": total population 2022-2072
  under four fertility hypotheses; ONLY the MEDIUM hypothesis (الفرض المتوسط,
  the third column from the left) is read -- the merge key has no variant
  column. Persons.
* Annex D, Tables D-2-1..D-2-51: the MEDIUM hypothesis by 5-year age group x
  sex, one page per year 2022-2072, THOUSANDS (العدد بالألف) -> unit
  thousand_persons. The both-sexes Total row is not filed (Table 5-1 files
  that figure, in persons, under the same key); it is checked against Table
  5-1 / 1000 instead. Male and female totals are filed.
Low / high / constant hypotheses: not read.

COLUMN ORDER. Pages are right-to-left: in Annex A/D the columns from left
to right are Total, Female, Male (header order checked by x position of
"ذكور"/"إناث" headers' figures summing: M + F = Total). In Table 5-1 the four
columns left to right are constant, high, medium, low; medium is the one
whose 2072 value the report's text quotes (159.8 million) -- checked.

Checks: bands sum to Total (Annex A within 10 persons; Annex D within 15
thousand, rounding), M + F = Total, 4 + 51 years present, Annex D total
within 1 thousand of Table 5-1.
"""
from __future__ import annotations

import collections
import re

import fitz
import pandas as pd

_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
          "75-79", "80+"]


def _rows(page):
    rows = collections.defaultdict(list)
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                t = s["text"].strip()
                if t:
                    rows[round((s["bbox"][1] + s["bbox"][3]) / 2)].append((s["bbox"][0], t))
    out = []
    for y in sorted(rows):
        if out and y - out[-1][0] <= 2:
            out[-1][1].extend(rows[y])
        else:
            out.append([y, list(rows[y])])
    return [(y, sorted(ws)) for y, ws in out]


def _band(tokens: list[str]) -> str | None:
    """Age label from the right-hand tokens: '0-4' | ['4','-','0'] |
    ['+','80']."""
    s = "".join(tokens).replace(" ", "")
    if "+" in s:
        n = re.sub(r"\D", "", s)
        return f"{n}+" if n else None
    ns = sorted(int(n) for n in re.findall(r"\d+", s))
    if len(ns) == 2:
        return f"{ns[0]}-{ns[1]}"
    return None


def _age_table(page, label_x: float):
    """{band|'Total': (total, female, male)} from an Annex A/D page. Figures
    are the spans left of `label_x`; a label can sit on the line above its
    figures (Annex D '5-9', '30-34'), so pending labels carry to the next
    figure line."""
    out, pending = {}, None
    for _, ws in _rows(page):
        lab = [t for x, t in ws if x >= label_x]
        nums = [(x, t) for x, t in ws if x < label_x]
        band = _band(lab) if lab else None
        figs = [float(re.sub(r"[^\d]", "", t)) for x, t in nums
                if re.search(r"\d", t) and re.fullmatch(r"[\d,]+|\D*\d+", t.replace(" ", ""))]
        is_total = any(re.search(r"جمل|جلمل|إلجمال|اجل", t) for _, t in ws)
        if band and not figs:
            pending = band
            continue
        if len(figs) == 3 and (band or pending or is_total):
            key = "Total" if is_total and not band else (band or pending)
            if key in out:
                raise ValueError(f"CAPMAS projections: {key} twice")
            out[key] = tuple(figs)
            pending = None
    return out


def _check_age(t, tol, where):
    if set(t) != set(_BANDS) | {"Total"}:
        raise ValueError(f"CAPMAS {where}: rows {sorted(set(t) ^ (set(_BANDS) | {'Total'}))}")
    for k in range(3):
        s = sum(t[b][k] for b in _BANDS)
        if abs(s - t["Total"][k]) > tol:
            raise ValueError(f"CAPMAS {where}: bands {s} != Total {t['Total'][k]}")
    for b, (tot, f, m) in t.items():
        if abs(m + f - tot) > max(2, tol / 5):
            raise ValueError(f"CAPMAS {where} {b}: {m} + {f} != {tot}")


def parse(local_path: str) -> pd.DataFrame:
    annex_a, annex_d, t51 = {}, {}, {}
    with fitz.open(local_path) as doc:
        for page in doc:
            text = page.get_text()
            # Annex A: "... في منتصف عام<year>" with full-number figures
            m = re.search(r"منتصف عام\s*(20[12]\d)", text)
            if m and re.search(r"أ\s*-\s*[1-4]", text) and re.search(r"\b\d{7,8}\b", text):
                annex_a[m.group(1)] = _age_table(page, 440)
                continue
            # Annex D, medium hypothesis: 'للفـرض املتوسط' in the title
            if "العدد ابأللف" in text and re.search(r"للف.?رض امل?توسط", text):
                ym = re.search(r"عــام\s*(20[2-7]\d)", text)
                if not ym:
                    raise ValueError(f"CAPMAS annex D p{page.number+1}: no year")
                if ym.group(1) in annex_d:
                    raise ValueError(f"CAPMAS annex D {ym.group(1)}: twice")
                annex_d[ym.group(1)] = _age_table(page, 420)
                continue
            # Table 5-1: lines of four comma-grouped figures + a year line
            if re.search(r"\d{3},\d{3},\d{3}", text) and page.number < 80:
                rows = _rows(page)
                for i, (y, ws) in enumerate(rows):
                    figs = [(x, t) for x, t in ws if re.fullmatch(r"\d{2,3}(,\d{3}){2}", t)]
                    if len(figs) != 4:
                        continue
                    yrs = [t for yy, w in rows if abs(yy - y) <= 4
                           for x, t in w if re.fullmatch(r"20[2-7]\d", t) and x > 450]
                    if len(yrs) != 1:
                        raise ValueError(f"CAPMAS 5-1 p{page.number+1}: year {yrs}")
                    medium = sorted(figs)[2][1]
                    if yrs[0] in t51:
                        raise ValueError(f"CAPMAS 5-1 {yrs[0]}: twice")
                    t51[yrs[0]] = float(medium.replace(",", ""))
    if sorted(annex_a) != ["2018", "2019", "2020", "2021"]:
        raise ValueError(f"CAPMAS annex A: years {sorted(annex_a)}")
    years = [str(y) for y in range(2022, 2073)]
    if sorted(annex_d) != years:
        raise ValueError(f"CAPMAS annex D: years {sorted(set(years) ^ set(annex_d))}")
    if sorted(t51) != years:
        raise ValueError(f"CAPMAS 5-1: years {sorted(set(years) ^ set(t51))}")
    if round(t51["2072"] / 1e5) != 1598:          # the text: 159.8 million
        raise ValueError(f"CAPMAS 5-1: medium 2072 = {t51['2072']}, text says 159.8 m")

    out = []

    def emit(st, sex, age, yr, v, unit, sc):
        out.append({"series_type": st, "sex": sex, "age_group": age,
                    "geography": "Total country", "period": yr,
                    "frequency": "annual", "measure": "count", "value": v,
                    "unit": unit, "series_code": sc})

    for yr, t in annex_a.items():
        _check_age(t, 10, f"annex A {yr}")
        for b, (tot, f, m) in t.items():
            for sex, v in (("total", tot), ("female", f), ("male", m)):
                emit("estimate", sex, b, yr, v, "persons",
                     "EG_CAPMAS_PROJ2022_ANNEX_A_MIDYEAR")
    for yr in years:
        t = annex_d[yr]
        _check_age(t, 15, f"annex D {yr}")
        if abs(t["Total"][0] - t51[yr] / 1000) > 1:
            raise ValueError(f"CAPMAS {yr}: annex D total {t['Total'][0]} "
                             f"vs Table 5-1 {t51[yr]}")
        for b, (tot, f, m) in t.items():
            for sex, v in (("total", tot), ("female", f), ("male", m)):
                if b == "Total" and sex == "total":
                    continue                  # Table 5-1 files it, in persons
                emit("projection", sex, b, yr, v, "thousand_persons",
                     "EG_CAPMAS_PROJ2022_ANNEX_D_MEDIUM")
        emit("projection", "total", "Total", yr, t51[yr], "persons",
             "EG_CAPMAS_PROJ2022_T5-1_MEDIUM")
    return pd.DataFrame(out)
