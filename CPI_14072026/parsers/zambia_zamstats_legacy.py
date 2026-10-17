"""ZamStats 'The Monthly' bulletins BEFORE the 2023 layout change -- the CPI
by division on the 2009 basket (base 2009 = 100), back to 2008.

The current parser (`zambia_zamstats.py`) reads Table 1.2 of today's bulletin,
a series from 2023. Every December bulletin from 2010 to 2022 prints the same
table in an older, text-only layout covering its own year and the two before:

    Weight: 1 000.00 534.85 15.21 80.78 114.11 82.36 8.15 58.08 12.94 ...
    January 191.28 190.96 178.38 198.38 192.51 195.14 179.31 207.35 ...
    ...
    2017                     <- the year sits mid-block, between June and July

WHAT VARIES, AND HOW IT IS HANDLED
* The CAPTION varies ("CONSUMER PRICE INDEX BY DIVISION", "INDEX NUMBERS OF
  CONSUMER PRICES: COMPOSITE (2009 WEIGHTS)", "Consumer Price Index (2009 =
  100)"), so the table is found by its WEIGHTS ROW -- the 2009 basket's weights
  are identical in every issue and nothing else on the page carries them.
* Some issues add two inflation columns after the 13 indices; the first 13
  numbers of a month line are the indices.
* The YEAR LABEL is unreliable (the 2013 issue's text layer prints "2013" as
  "1102"). Blocks run January..December in chronological order and a December
  issue's last block is its own year, so years are assigned BACKWARDS from the
  issue year (from the file name), and any readable year label inside a block
  must agree or the issue is refused.
* COLUMN ORDER is settled every run, by page GEOMETRY (each value on the
  weights row matched to the nearest header keyword in x must give COICOP
  00..12 in order -- it does in 2019, 2020, 2022) or, where a page yields no
  word positions, by the weights row printing the geometry-verified weights
  sequence exactly (each division's weight is distinct). Otherwise refused.
* "127..51" (Dec 2019, Communication, Feb 2017) is a printed double dot; it is
  read as 127.51, the only reading consistent with its neighbours.

Older bulletins (2003-2009) are on the 1994 basket and carry different
weights; they do not match the anchor and are not read.
"""
from __future__ import annotations
import os
import re
import pdfplumber
import pandas as pd

BASE = "2009 = 100"
_WEIGHTS = ("534.85", "15.21", "80.78", "114.11")
_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december"]
_LABELS = [
    ("00", "All items"), ("01", "Food and non-alcoholic beverages"),
    ("02", "Alcoholic beverages and tobacco"), ("03", "Clothing and footwear"),
    ("04", "Housing, water, electricity, gas and other fuels"),
    ("05", "Furnishings, household equipment and routine maintenance"),
    ("06", "Health"), ("07", "Transport"), ("08", "Communication"),
    ("09", "Recreation and culture"), ("10", "Education"),
    ("11", "Restaurants and hotels"), ("12", "Miscellaneous goods and services"),
]
_HEADER_KEYS = {"items": "00", "non-": "01", "tobacco": "02", "footwear": "03",
                "fuels": "04", "routine": "05", "health": "06",
                "transport": "07", "communication": "08", "recreation": "09",
                "education": "10", "restaurant": "11", "miscellaneous": "12"}
_ROW = re.compile(r"^([A-Za-z]+)\s+((?:\d[\d ]*\.\d+\s*){13,})")


def issue_year(path: str) -> int | None:
    m = re.search(r"-(20\d\d)-The-Monthly-December", os.path.basename(path))
    return int(m.group(1)) if m else None


def _geometry_ok(page) -> bool:
    """Columns on the weights row map to COICOP 00..12, in order."""
    ws = page.extract_words()
    wrow = next((w for w in ws if w["text"].lower().startswith("weight")), None)
    if wrow is None:
        return False
    nums = sorted((w for w in ws if abs(w["top"] - wrow["top"]) < 3
                   and re.fullmatch(r"[\d.]+", w["text"])), key=lambda w: w["x0"])
    cols = []
    for w in nums:                     # "1" "000.00" -> one cell
        if cols and w["x0"] - cols[-1]["x1"] < 4:
            cols[-1] = {"x0": cols[-1]["x0"], "x1": w["x1"]}
        else:
            cols.append({"x0": w["x0"], "x1": w["x1"]})
    hdr = [w for w in ws if wrow["top"] - 140 < w["top"] < wrow["top"]]
    got = []
    for c in cols[:13]:
        cx = (c["x0"] + c["x1"]) / 2
        cands = [(abs((w["x0"] + w["x1"]) / 2 - cx), code)
                 for w in hdr for k, code in _HEADER_KEYS.items()
                 if k in w["text"].lower()]
        got.append(min(cands)[1] if cands else "?")
    return got == [c for c, _ in _LABELS]


# The 2009 basket's weights in COICOP order 00..12. Each division has a
# DISTINCT weight, and page geometry ties this sequence to 00..12 in the 2019
# and 2022 issues; so a weights row printing exactly this sequence has the same
# column order. It is the proof used where a page yields no word positions
# (2014, 2015, 2017: text extracts, words do not).
_WEIGHT_SEQ = ["1000.00", "534.85", "15.21", "80.78", "114.11", "82.36", "8.15",
               "58.08", "12.94", "13.84", "26.62", "3.37", "49.69"]


def _weights_in_order(text: str) -> bool:
    for ln in text.splitlines():
        if ln.strip().lower().startswith("weight"):
            nums = re.findall(r"\d[\d ]*\.\d+", ln)
            nums = [n.replace(" ", "") for n in nums][:13]
            return nums == _WEIGHT_SEQ
    return False


def parse(pdf_path: str) -> pd.DataFrame:
    year = issue_year(pdf_path)
    if year is None:
        raise ValueError(f"ZamStats legacy: cannot date {pdf_path!r} (expects a "
                         f"'-<YYYY>-The-Monthly-December' file name)")
    # The weights also appear on the annual-inflation page (Table 2), so the
    # table is the weights page that ALSO carries 12+ month rows of 13 indices.
    text = None
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            if not all(w in t for w in _WEIGHTS):
                continue
            rows = [ln for ln in t.splitlines()
                    if (m := _ROW.match(ln.strip().replace("..", ".")))
                    and m.group(1).lower() in _MONTHS]
            if len(rows) < 12:
                continue
            if not (_geometry_ok(p) or _weights_in_order(t)):
                raise ValueError(f"ZamStats legacy {year}: column geometry is not "
                                 f"COICOP 00..12 in order -- refused")
            text = t
            break
    if text is None:
        raise ValueError(f"ZamStats legacy {year}: no 2009-basket monthly CPI table")

    blocks, cur = [], []
    for ln in text.splitlines():
        s = ln.strip().replace("..", ".")
        if re.fullmatch(r"(19|20)\d\d", s):
            cur.append(("Y", int(s)))
            continue
        m = _ROW.match(s)
        if m and m.group(1).lower() in _MONTHS:
            # A new year starts when the month order goes BACKWARDS -- not on
            # a "January" line, which the text layer does not always deliver.
            prev = [x for x in cur if x[0] == "M"]
            if prev and _MONTHS.index(m.group(1).lower()) <= _MONTHS.index(prev[-1][1]):
                # a year label printed just before this line belongs to the new block
                tail = []
                while cur and cur[-1][0] == "Y":
                    tail.insert(0, cur.pop())
                blocks.append(cur)
                cur = tail
            cur.append(("M", m.group(1).lower(), m.group(2).split()[:13]))
    if cur:
        blocks.append(cur)
    blocks = [b for b in blocks if any(x[0] == "M" for x in b)]
    if not blocks:
        raise ValueError(f"ZamStats legacy {year}: no month rows read")

    # A December issue's table ENDS with its own December. One that does not
    # (the 2013 issue prints a different, partial table) cannot be dated by
    # counting back, and is refused.
    last = [x for x in blocks[-1] if x[0] == "M"]
    if last[-1][1] != "december":
        raise ValueError(f"ZamStats legacy {year}: table does not end in "
                         f"December (ends {last[-1][1]}) -- refused")
    records = []
    for k, b in enumerate(reversed(blocks)):
        y = year - k
        labels = {x[1] for x in b if x[0] == "Y" and 2000 <= x[1] <= year}
        # The page title can carry the issue year too, so the block's own year
        # must be AMONG its labels; a block whose labels exclude it is misdated.
        if labels and y not in labels:
            raise ValueError(f"ZamStats legacy {year}: block dated {y} carries "
                             f"year label(s) {sorted(labels)}")
        for x in b:
            if x[0] != "M":
                continue
            period = f"{y}-{_MONTHS.index(x[1]) + 1:02d}"
            for (code, label), v in zip(_LABELS, x[2]):
                records.append({"coicop_code": code, "coicop_label": label,
                                "geography": "National", "period": period,
                                "value": round(float(v.replace(" ", "")), 4)})
    out = pd.DataFrame.from_records(records).drop_duplicates(["coicop_code", "period"])
    out["measure"] = "index"
    out["unit"] = "Index"
    out["base_period"] = BASE
    out["frequency"] = "monthly"
    return out
