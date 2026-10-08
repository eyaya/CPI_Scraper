"""CAPMAS Egypt — "تقديرات السكان" (population estimates), publication 150 of the
CAPMAS publication API, page 1: "عدد السكان التقديرى بالداخل للجمهورية موزعا
طبقا للمحافظات و النوع و (حضر / ريف / جملة) فى 2026/1/1" -- the estimated
population inside the country by governorate, sex and urban/rural, on
1 January of the edition's year.

WHY EGYPT WAS ON THE REJECTED LIST: the earlier scan of CAPMAS's API matched
ENGLISH keywords, but the catalogue's names are Arabic. Scanning the API's ids
in full finds 150 (estimates), 151 (census 2017 final results) and 106
(projections) -- all population, none with "population" in English.

COLLECTED: the national row ("إجمالى الجمهورية") and the 27 governorates, by
sex, from the table's TOTAL block. The urban / rural blocks have no column in
this schema. series_type `estimate`; period = the edition's year, and
`series_code` says "1 Jan" -- this is a 1 January figure, not a mid-year one.
The rest of the volume repeats the table per qism / markaz (districts).

THE ARABIC TEXT LAYER IS LIGATURE-MANGLED ("مشال سينــاء" for شمال سيناء,
"الوادى اجلديد" for الوادي الجديد). Governorate names are therefore STATED
here, as printed on the rendered page, in the table's order; each extracted
label must contain the same LETTERS as its stated name (the mangling reorders
letters, it does not change them), so a row can never be attached to the
wrong governorate silently. Each row must also satisfy urban + rural = total
and male + female = total in every block.

NOT READ: the 2017 census volume (151) -- its text layer is badly mangled and
its national total cannot be located in it; the projections report (106).

CROSS-CHECK (1 Jan 2026): Egypt 108 613 296 (M 55 778 095 / F 52 835 201);
Cairo 10 478 084; Giza 9 820 469; South Sinai 122 805.
"""
from __future__ import annotations

import re
import unicodedata

import fitz  # PyMuPDF
import pandas as pd

_GOVS = [
    "القاهرة", "الإسكندرية", "بور سعيد", "السويس", "دمياط", "الدقهلية",
    "الشرقية", "القليوبية", "كفر الشيخ", "الغربية", "المنوفية", "البحيرة",
    "الإسماعيلية", "الجيزة", "بنى سويف", "الفيوم", "المنيا", "أسيوط", "سوهاج",
    "قنا", "أسوان", "الأقصر", "البحر الأحمر", "الوادى الجديد", "مطروح",
    "شمال سيناء", "جنوب سيناء", "إجمالى الجمهورية",
]


def _letters(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("ـ", "")                       # tatweel (stretching)
    s = re.sub(r"[^ء-ي]", "", s)            # Arabic letters only
    s = re.sub(r"[إأآا]", "ا", s).replace("ى", "ي").replace("ة", "ه")
    return "".join(sorted(s))


def parse(path: str) -> pd.DataFrame:
    doc = fitz.open(path)
    text = doc[0].get_text()
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if not m:
        raise ValueError("CAPMAS estimates: no reference date on page 1")
    year, month, day = m.groups()
    if (month, day) != ("1", "1"):
        raise ValueError(f"CAPMAS estimates: reference date {m.group(0)}, "
                         f"expected 1/1 -- re-check the period convention")

    # "<label><n1>" then eight numbers, one per line.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rows, i = [], 0
    while i < len(lines):
        lm = re.fullmatch(r"(\D+?)(\d+)", lines[i])
        if lm and i + 8 < len(lines) and all(re.fullmatch(r"\d+", x)
                                             for x in lines[i + 1:i + 9]):
            vals = [int(lm.group(2))] + [int(x) for x in lines[i + 1:i + 9]]
            rows.append((lm.group(1).strip(), vals))
            i += 9
        else:
            i += 1
    if len(rows) != len(_GOVS):
        raise ValueError(f"CAPMAS estimates: {len(rows)} rows for {len(_GOVS)} "
                         f"governorates + total")

    out = []
    for (raw, v), name in zip(rows, _GOVS):
        if _letters(raw) != _letters(name):
            raise ValueError(f"CAPMAS estimates: row {raw!r} is not {name!r}")
        um, uf, ut, rm, rf, rt, tm, tf, tt = v
        if not (um + uf == ut and rm + rf == rt and tm + tf == tt
                and ut + rt == tt and um + rm == tm and uf + rf == tf):
            raise ValueError(f"CAPMAS estimates {name}: blocks do not add up {v}")
        geo = "Total country" if name == "إجمالى الجمهورية" else name
        for sex, val in (("male", tm), ("female", tf), ("total", tt)):
            out.append({"series_type": "estimate", "sex": sex,
                        "age_group": "Total", "geography": geo,
                        "period": year, "frequency": "annual",
                        "measure": "count", "value": val, "unit": "persons",
                        "series_code": f"CAPMAS pub.150 est. 1 Jan {year}"})
    df = pd.DataFrame(out)
    nat = df[(df.geography == "Total country") & (df.sex == "total")].value.iloc[0]
    govs = df[(df.geography != "Total country") & (df.sex == "total")].value.sum()
    if govs != nat:
        raise ValueError(f"CAPMAS estimates: governorates sum to {govs}, national {nat}")
    return df
