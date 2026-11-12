"""Egypt -- CAPMAS "Producers Price Index" bulletin (publication 87).

CAPMAS's SPA API (`/api/Publication/SearchPublicationDetail?PublicationId=87
&Year=Y&Month=M`) lists every issue since the first (September 2007). Issues
were BIMONTHLY until May 2023 (January, March, ... November), each carrying
the previous month as well, so every month is covered; monthly since June
2023. Workbooks (bilingual Arabic / English) exist for Sep 2007 - Nov 2009
and from January 2021 (except January 2022); 2010-2020 (and Jan 2022) are PDF only.

Every issue's tables print, per row: the index for the previous month, the
current month and the same month a year earlier, then the % change from the
previous month and from the same month a year earlier. All three index
points are emitted (a later issue's revision of a month wins on merge); the
two changes belong to the current month only.

  Table 1     All items and ISIC sections A B C D E H I J
  Tables 2-9  detail of each section (ISIC divisions / groups / products)
  Table 10    major groups by END USE         -> industry "End use: <group>"
  Table 11    major groups by STAGE OF PROCESSING -> "Stage of processing: <group>"
  Table 12    selected CPC products (from 2021) -> "CPC product: <product>"
  (Tables 10-12 repeat labels with other values -- "Fuel" is 289.8 by end use
  and 489.2 by stage of processing in August 2026 -- hence the prefixes.)

WORKBOOKS (`parse_workbook`) yield all tables. PDF ISSUES (`parse_pdf`) yield
Table 1 only: their rows wrap labels across lines, and only the section rows
can be anchored safely (each starts "<letter> - " or "ALL ITEMS"). The PDF
prints the five numbers in REVERSE order (y/y %, m/m %, index a year ago,
index now, index previous month: "ALL ITEMS -6.6 -1.0 216.7 202.3 204.4" for
July 2015); the order is proved per issue by the ALL ITEMS row's arithmetic
before any row is read, and the issue is refused if it does not hold.

LABELS. CAPMAS rewords the English labels between issues ("Growing of rice"
in 2021, "rice" in 2026) while the Arabic labels stay put. So one run maps
every (table, Arabic label) to the English label of the NEWEST issue that
prints it; the series then keep one name across all issues. Leading section
letters / item numbers ("A . ", "(1) ") are stripped from the label; Table 1's
section letter goes to industry_code_nso.

BASES as printed: "2004/2005=100" (Sep 2007 - ...), "Jan 2016 = 100" (later).

CROSS-CHECK (verbatim): Aug 2026 all items 654.6 (Jul 646.2, Aug 2025 586.7,
m/m 1.3, y/y 11.6); Jan 2021 all items 201.480529977961 (base Jan 2016);
Jan 2008 all items 141.9 (base 2004/2005); Jul 2015 all items 202.3,
B Mining 118.2.
"""
from __future__ import annotations

import os
import re
import unicodedata

import pandas as pd

from . import _common as C

INDEX_NAME = "Producers Price Index (PPI)"
SKIPPED: list[tuple[str, str]] = []      # (file, reason): issues not read, filled by parse
CONFLICTS: list[tuple] = []              # (file, key, value, value): cells printed twice differently
_PREFIX = {10: "End use: ", 11: "Stage of processing: ", 12: "CPC product: "}
_MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul",
                                    "aug", "sep", "oct", "nov", "dec"], start=1)}


def _ar(s) -> str:
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[ً-ْـ]", "", s)          # harakat, tatweel
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"\s+", "", s)


def _clean_en(s) -> tuple[str, str]:
    """('C', 'Manufacturing') from 'C. Manufacturing'; ('', 'food products') from '(1) food products'."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    m = re.match(r"^([A-U])\s*[.\-]\s+(.*)$", s)
    if m:
        return m.group(1), m.group(2).strip()
    s = re.sub(r"^\(\s*\d+\s*\)\s*", "", s)
    s = re.sub(r"^\d+\s*-\s*", "", s)
    return "", s.strip()


def _ym(mon: str, year) -> str:
    return f"{int(year):04d}-{_MON[str(mon).strip().strip('.').lower()[:3]]:02d}"


def _lag(p: str, n: int) -> str:
    y, m = int(p[:4]), int(p[5:])
    k = y * 12 + m - 1 - n
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


# ------------------------------------------------------------- workbooks ---

def _sheet_rows(ws):
    """(table_no, base, [(col, period)], [(arabic, english, {col: value})])."""
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    tno = int(re.search(r"\d+", ws.title).group())
    base = ""
    for r in rows[:8]:
        for c in r:
            if isinstance(c, str) and re.search(r"=\s*100|100\s*=", c) and re.search(r"[A-Za-z]|\d{4}/\d{4}", c):
                base = re.sub(r"\s+", " ", c).strip()
    hdr = None
    for i, r in enumerate(rows[:14]):
        cols = [(j, c) for j, c in enumerate(r) if isinstance(c, str) and c.strip().strip(".").lower()[:3] in _MON]
        if len(cols) == 5 and i + 1 < len(rows):
            yrs = rows[i + 1]
            hdr = [(j, _ym(c, yrs[j])) for j, c in cols]
            start = i + 2
            break
    if hdr is None:
        raise ValueError(f"{ws.title}: no month/year header")
    out = []
    for r in rows[start:]:
        vals = {j: r[j] for j, _ in hdr if isinstance(r[j], (int, float))}
        strs = [c for c in r if isinstance(c, str) and c.strip()]
        if len(vals) != 5 or len(strs) < 2:
            continue
        out.append((strs[0], strs[-1], vals))
    return tno, base, hdr, out


def _roles(hdr):
    """Index columns = first three, changes = last two; name them by period."""
    idx, chg = hdr[:3], hdr[3:]
    cur = max(p for _, p in idx)
    roles = {}
    for j, p in idx:
        roles[j] = ("index", p)
    for j, p in chg:
        if p == _lag(cur, 1):
            roles[j] = ("inflation_mom", cur)
        elif p == _lag(cur, 12):
            roles[j] = ("inflation_yoy", cur)
        else:
            raise ValueError(f"change column 'from {p}' is neither m/m nor y/y of {cur}")
    if {r[1] for j, r in roles.items() if r[0] == "index"} != {cur, _lag(cur, 1), _lag(cur, 12)}:
        raise ValueError(f"index columns {idx} are not previous / current / year-ago")
    return roles


def _label_map(paths):
    """(table, arabic) -> (code, english) from the NEWEST workbook printing it."""
    import openpyxl
    lab = {}
    for p in sorted(paths, key=os.path.basename):              # oldest first; newest overwrites
        wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
        for ws in wb.worksheets:
            if not ws.title.startswith("Table"):
                continue
            tno, _, _, rows = _sheet_rows(ws)
            for ar, en, _ in rows:
                lab[(tno, _ar(ar))] = _clean_en(en) + (re.sub(r"\s+", " ", ar).strip(),)
        wb.close()
    return lab


def _industry(tno, ar, en, lab, clash=frozenset()):
    # A section row repeated at the top of its detail table (Tables 2-9: "ح -
    # النقل و التخزين") is Table 1's section: same Arabic, same series.
    if tno in range(2, 10) and (1, _ar(ar)) in lab and lab[(1, _ar(ar))][0]:
        tno = 1
    code, name, raw = lab.get((tno, _ar(ar))) or (_clean_en(en) + (ar,))
    # Two Arabic labels sharing one English label IN ONE ISSUE'S TABLE (Table 4
    # of Aug 2026 has two "Processing and preserving of fruit and vegetables",
    # 673.2 and 349.1) are two series: each keeps its Arabic label beside.
    if (tno, name) in clash:
        name = f"{name} [{re.sub(r'\s+', ' ', raw).strip()}]"
    return (code if tno == 1 else ""), _PREFIX.get(tno, "") + name


def parse_workbook(path, lab=None) -> list[dict]:
    import openpyxl
    lab = lab if lab is not None else _label_map([path])
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out, bad = {}, set()
    sheets = [_sheet_rows(ws) for ws in wb.worksheets if ws.title.startswith("Table")]
    # A sheet that omits the base line (Table 12 of April 2026) takes the one
    # base every other sheet of the same issue prints -- only if they agree.
    printed = {s[1] for s in sheets if s[1]}
    for tno, base, hdr, rows in sheets:
        if not base:
            if len(printed) != 1:
                raise ValueError(f"{os.path.basename(path)} Table {tno}: no base period printed")
            base = next(iter(printed))
        roles = _roles(hdr)
        names = {}
        for ar, en, _ in rows:
            names.setdefault((lab.get((tno, _ar(ar))) or _clean_en(en) + (ar,))[1], set()).add(_ar(ar))
        clash = {(tno, n) for n, a in names.items() if len(a) > 1}
        for ar, en, vals in rows:
            code, ind = _industry(tno, ar, en, lab, clash)
            for j, v in vals.items():
                measure, period = roles[j]
                key = (ind, period, measure)
                if key in bad:
                    continue
                if measure == "index" and float(v) <= 0:
                    # an impossible printed index (-632.8, "Finished goods",
                    # January 2025) is logged, never "corrected"
                    CONFLICTS.append((os.path.basename(path), key, float(v), "non-positive index"))
                    continue
                if key in out:
                    # ONE ISSUE, TWO FIGURES for one cell: July 2025's Table 1
                    # prints B Mining's year-ago index as 580.6 (crude
                    # petroleum's, in Table 3) against Table 3's 284.8. Neither
                    # is chosen: the cell is dropped and logged.
                    if abs(out[key]["value"] - float(v)) > 1e-6:
                        CONFLICTS.append((os.path.basename(path), key, out[key]["value"], float(v)))
                        bad.add(key)
                        del out[key]
                    continue
                out[key] = C.row(index_name=INDEX_NAME, industry=ind, industry_code_nso=code,
                                 period=period, frequency="monthly", measure=measure, value=v,
                                 base_period=base)
    wb.close()
    return list(out.values())


# ------------------------------------------------------------------ PDFs ---

_NUM = r"-?\d+(?:\.\d+)?"
_SECTION = re.compile(r"^(ALL\s*ITEMS|[A-J]\s*-\s+\S.*?)\s*((?:" + _NUM + r"\s+){4}" + _NUM + r")?\s*(?:[؀-ۿ].*)?$")


def parse_pdf(path, lab=None) -> list[dict]:
    import pdfplumber
    lab = lab or {}
    with pdfplumber.open(path) as pdf:
        text = None
        for pg in pdf.pages[:30]:
            t = pg.extract_text() or ""
            # 2018-2020 issues set spaces as U+F220 and the Arabic in private-
            # use glyphs (U+F2xx): a space, and nothing, respectively.
            t = re.sub("[-]+", lambda m: " " if "" in m.group() and len(m.group()) == m.group().count("") else " ", t)
            # the table page itself, not the contents page that names it
            if re.search(r"Table\s*\(1\)\s*All Items", t) and re.search(r"ALL\s*ITEMS\s+-?\d", t):
                text = t
                break
    if text is None:
        raise ValueError(f"{os.path.basename(path)}: no Table (1) page")
    m = re.search(r"For\s+([A-Za-z]{3})[a-z]*\.?\s*(\d{4})", text)
    cur = _ym(m.group(1), m.group(2))
    bm = re.search(r"(\d{4}/\d{4}\s*=\s*100|[A-Za-z]{3}\.? ?\d{4}\s*=\s*100)", text)
    base = re.sub(r"\s+", " ", bm.group(1)).strip() if bm else ""
    if not base:
        raise ValueError(f"{os.path.basename(path)}: no base period printed")
    lines = [l.strip() for l in text.splitlines()]
    sections = {}
    pending = None
    for l in lines:
        # 2018-2020 issues drop the spaces ("A-AgricultureandFishing") and
        # end number lines with a stray "-": both layouts are accepted.
        m = re.match(r"^(ALL\s*ITEMS|([A-J])\s*-\s*([A-Za-z].*?))\s*((?:" + _NUM + r"\s+){4}" + _NUM + r")?(?:\s+-)?(?:\s+[؀-ۿﭐ-﷿ﹰ-﻿].*)?$", l)
        nums = re.fullmatch(r"(?:[A-Za-z][A-Za-z ,;&()\-]*\s+)?((?:" + _NUM + r"\s+){4}" + _NUM + r")(?:\s+-)?(?:\s+[؀-ۿﭐ-﷿ﹰ-﻿].*)?", l)
        if m:
            letter = "_T" if m.group(1).startswith("ALL") else m.group(2)
            if m.group(4):
                sections.setdefault(letter, [float(x) for x in m.group(4).split()])
                pending = None
            else:
                pending = letter
        elif nums and pending:
            sections.setdefault(pending, [float(x) for x in nums.group(1).split()])
            pending = None
    if "_T" not in sections or len(sections) < 8:
        raise ValueError(f"{os.path.basename(path)}: Table (1) rows not found ({sorted(sections)})")
    # PROVE the column order on ALL ITEMS: (yoy, mom, idx_yago, idx_cur, idx_prev).
    yoy, mom, ya, now, prev = sections["_T"]
    if not (abs((now / prev - 1) * 100 - mom) <= 0.15 and abs((now / ya - 1) * 100 - yoy) <= 0.15):
        raise ValueError(f"{os.path.basename(path)}: ALL ITEMS {sections['_T']} does not fit "
                         f"(y/y, m/m, year-ago, current, previous)")
    names = {code: name for (t, _), (code, name, _r) in lab.items() if t == 1 and code}
    names["_T"] = next((name for (t, _), (code, name, _r) in lab.items() if t == 1 and not code
                        and re.search(r"all\s*items", name, re.I)), "ALL ITEMS")
    out = []
    for letter, (yoy, mom, ya, now, prev) in sections.items():
        ind = names.get(letter) or letter
        code = "" if letter == "_T" else letter
        for measure, period, v in (("index", _lag(cur, 1), prev), ("index", cur, now),
                                   ("index", _lag(cur, 12), ya), ("inflation_mom", cur, mom),
                                   ("inflation_yoy", cur, yoy)):
            out.append(C.row(index_name=INDEX_NAME, industry=ind, industry_code_nso=code,
                             period=period, frequency="monthly", measure=measure, value=v,
                             base_period=base))
    return out


# ----------------------------------------------------------------- entry ---

def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """All issues: `path` (the newest workbook) plus every back issue in `extras`.
    Issues are read oldest first, so where two issues print the same month the
    NEWER one's value is kept (its revision)."""
    files = sorted({path, *(extras or [])}, key=lambda p: os.path.basename(p))
    lab = _label_map([f for f in files if f.lower().endswith(".xlsx")])
    out = {}
    SKIPPED.clear()
    CONFLICTS.clear()
    for f in files:
        if f.lower().endswith(".xlsx"):
            rows = parse_workbook(f, lab)
        else:
            try:
                rows = parse_pdf(f, lab)
            except ValueError as e:          # scanned issue (no text layer) or unprovable order
                SKIPPED.append((os.path.basename(f), str(e)[:160]))
                continue
        for r in rows:
            out[(r["industry"], r["period"], r["measure"], r["base_period"])] = r
    if not out:
        raise ValueError("egypt_capmas_ppi: no rows")
    return pd.DataFrame(list(out.values()))
