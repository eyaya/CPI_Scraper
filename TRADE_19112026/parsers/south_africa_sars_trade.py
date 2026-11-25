"""Parsers for South Africa merchandise trade -- SARS (South African Revenue
Service), the official compiler of South Africa's merchandise trade statistics
(Stats SA does not compile them; it republishes SARS figures).

Two source families, both from sars.gov.za/customs-and-excise/trade-statistics/reports/:

parse(path, extras)  -- the SARS Excel workbooks (zipped):
  * YoY-World-Zone-Comparison.zip, sheet "WorldZone Incl BLNS": exports and
    imports by world zone (AFRICA, EUROPE, AMERICA, ASIA, OCEANIA, OTHER
    UNCLASSIFIED, SHIP/AIRCRAFT) and TOTAL, every month from January 2014, in
    rand (unit 1). The GRAND TOTAL column is emitted as the annual figure only
    for years with all twelve months published (the current year is YTD).
  * Cumulative-Bilateral-Trade-by-Country-<year>.zip: per region sheet, the
    exports block and the imports block, HS section x partner country; ONLY the
    "Total" row (all products) per partner country is taken (the section x
    partner matrix is not collected), for complete years only. Sheets
    "... Excl BLNS" and the "World Zone" summaries are skipped (the former is a
    different coverage, the latter duplicates the YoY workbook).

parse_pdf(path, extras) -- the monthly "Trade Statistics" press releases (PDF,
  January 2010 onward):
  * page 1 headline: exports, imports and TRADE BALANCE for the reporting month
    and the previous month (revised), in rand;
  * the monthly statement (including BLNS where the release splits coverage):
    world zones and the sections of the Harmonised System, current and
    previous month, in R million. HS sections carry commodity_classification
    "national" (the schema has no HS-section level) with the printed roman
    numeral as commodity_code_nso;
  * December releases: the cumulative statement's "January to December"
    columns are the annual figures (both years printed).
  World-zone rows from 2014 are left to the Excel workbook. Monthly exports,
  imports and balance come from page 1 as one release's triplet (run this
  descriptor AFTER the Excel one, so the triplet's vintage is what is kept).

Coverage: releases up to the September 2013 figures exclude the BLNS
countries (Botswana, Lesotho, Namibia, Eswatini); from the October 2013 release
the national total includes them and the release says so. Only releases that
print "including BLNS/BELN" are read. Negative printed values outside the balance
(a correction booked against a section, e.g. -16.18 Rm exports of "Other
unclassified goods" in January 2010) are not emitted.
"""
from __future__ import annotations

import io
import os
import re
import zipfile

import openpyxl
import pandas as pd

from ._common import row

CUR = "ZAR"
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]
_MON3 = [m[:3] for m in _MONTHS]

# --------------------------------------------------------------------------- Excel

_ZONE_LABEL = {"AFRICA": "AFRICA", "EUROPE": "EUROPE", "AMERICA": "AMERICA", "ASIA": "ASIA",
               "OCEANIA": "OCEANIA", "OTHER UNCLASSIFIED": "OTHER UNCLASSIFIED",
               "OTHER UNCLASSIFIED GOODS": "OTHER UNCLASSIFIED",
               "SHIP/AIRCRAFT": "SHIP/AIRCRAFT", "SHIPS'/AIRCRAFT STORES": "SHIP/AIRCRAFT",
               "SHIPS/AIRCRAFT STORES": "SHIP/AIRCRAFT"}
_TOTAL_LABELS = {"TOTAL", "GRAND TOTAL"}
_NOT_COUNTRY = {"origin of the goods is unknown", "ship/aircraft", "gold, petroleum and other",
                "total", "unknown"}


def _wb_from_zip(path: str):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith((".xlsx", ".xlsm")))
        data = z.read(name)
    return openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)


def _num(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_yoy(path: str) -> list[dict]:
    wb = _wb_from_zip(path)
    ws = next(w for w in wb.worksheets if w.title.strip().lower() == "worldzone incl blns")
    rows, flow, cols, year = [], None, {}, None
    for r in ws.iter_rows(values_only=True):
        c0 = str(r[0]).strip().upper() if r[0] is not None else ""
        if c0 in ("EXPORTS", "IMPORTS"):
            flow = "export" if c0 == "EXPORTS" else "import"
            cols = {}
            for j, h in enumerate(r):
                h = str(h).strip().lower() if h is not None else ""
                if h in _MONTHS:
                    cols[j] = _MONTHS.index(h) + 1
                elif h == "grand total":
                    cols[j] = 0
            year = None
            continue
        if flow is None or len(r) < 2:
            continue
        if isinstance(r[0], (int, float)) and 1990 < r[0] < 2100:
            year = int(r[0])
        zone = str(r[1]).strip().upper() if r[1] is not None else ""
        if not zone or year is None:
            continue
        if zone in _TOTAL_LABELS:
            partner, ptype = None, "world"
        elif zone in _ZONE_LABEL:
            partner, ptype = _ZONE_LABEL[zone], "group"
        else:
            raise ValueError(f"south_africa_sars: unknown world zone {zone!r}")
        months = {m: _num(r[j]) for j, m in cols.items() if m}
        n_months = sum(v is not None for v in months.values())
        for m, v in months.items():
            if v is None or v < 0:
                continue
            rows.append(row(tradeflow=flow, period=f"{year}-{m:02d}", frequency="monthly", value=v,
                            unit=CUR, partner=partner, partner_type=ptype,
                            series_code="YoY World Zone Comparison (incl BLNS)"))
        tot_col = next((j for j, m in cols.items() if m == 0), None)
        if tot_col is not None and n_months == 12:
            v = _num(r[tot_col])
            if v is not None and v >= 0:
                rows.append(row(tradeflow=flow, period=str(year), frequency="annual", value=v,
                                unit=CUR, partner=partner, partner_type=ptype,
                                series_code="YoY World Zone Comparison (incl BLNS)"))
    wb.close()
    return rows


_TITLE_RX = re.compile(r"SOUTH AFRICAN (EXPORTS|IMPORTS) FOR JANUARY TO (\w+) (\d{4})", re.I)


def _parse_bilateral(path: str) -> list[dict]:
    wb = _wb_from_zip(path)
    rows = []
    for ws in wb.worksheets:
        t = ws.title.strip().lower()
        if "excl" in t or "world zone" in t or "worldzone" in t:
            continue
        flow, header, complete, year = None, None, False, None
        for r in ws.iter_rows(values_only=True):
            cells = [c for c in r if c is not None and str(c).strip()]
            joined = " ".join(str(c) for c in cells)
            m = _TITLE_RX.search(joined)
            if m:
                flow = "export" if m.group(1).upper() == "EXPORTS" else "import"
                complete = m.group(2).lower() == "december"
                year = int(m.group(3))
                header = None
                continue
            if r and str(r[0]).strip().lower() == "section":
                header = list(r)
                continue
            if header and r and str(r[0]).strip().lower() == "total":
                if not complete:
                    continue
                for j in range(2, len(header)):
                    name = header[j]
                    if name is None or not str(name).strip():
                        continue
                    name = str(name).strip()
                    if name.lower() == "total":       # the region total: in the YoY workbook
                        continue
                    v = _num(r[j]) if j < len(r) else None
                    if v is None or v < 0:
                        continue
                    ptype = "group" if name.lower() in _NOT_COUNTRY else "country"
                    if name.lower() in ("unclassified", "other", "others"):
                        # 2010-2011: an "Unclassified" column inside a region
                        # sheet (Africa) besides the "Unclassified" sheet --
                        # two different figures, so the region is named.
                        region = re.split(r"\s+incl", ws.title.strip(), flags=re.I)[0]
                        if region.lower() != "unclassified":
                            name = f"{name} ({region})"
                        ptype = "group"
                    rows.append(row(tradeflow=flow, period=str(year), frequency="annual", value=v,
                                    unit=CUR, partner=name, partner_type=ptype,
                                    series_code=f"Cumulative Bilateral Trade by Country {year}: {ws.title.strip()}"))
                header = None
    wb.close()
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path] + list(extras or []):
        b = os.path.basename(p).lower()
        if "yoy" in b and "world" in b:
            rows += _parse_yoy(p)
        elif "bilateral" in b:
            rows += _parse_bilateral(p)
    if not rows:
        raise ValueError("south_africa_sars: no rows decoded")
    return pd.DataFrame.from_records(rows).reset_index(drop=True)


# --------------------------------------------------------------------------- PDF

# SARS's section captions (September 2026 release), keyed by the printed roman numeral.
_SECTIONS = {
    "I": "Live animals, animal products",
    "II": "Vegetable products",
    "III": "Animal or vegetable fats and oils and their cleavage products; prepared edible fats; animal or vegetable waxes",
    "IV": "Prepared foodstuffs, beverages, spirits, and vinegar; tobacco and manufactured tobacco substitutes",
    "V": "Mineral products",
    "VI": "Products of the chemicals or allied industries",
    "VII": "Plastics and articles thereof; rubber and articles thereof",
    "VIII": "Raw hides and skins, leather, fur skins and articles thereof; saddler and harness, travel articles, handbags and similar containers; articles of animal gut (other than silkworm-gut)",
    "IX": "Wood and articles of wood, wood charcoal, cork and articles of cork, manufactures of straw, of esparto or of other plaiting material, basket ware and wickerwork",
    "X": "Pulp of wood or of other fibrous cellulosic material; waste and scrap of paper or of paperboard; paper and paperboard and articles thereof",
    "XI": "Textiles and textile articles",
    "XII": "Footwear, headgear, umbrellas, sun umbrellas, walking-sticks, seat-sticks, whips, riding-crops and parts thereof; prepared feathers and articles made therewith, artificial flowers, articles of human hair",
    "XIII": "Articles of stone, plaster, cement, asbestos, mica or similar materials, ceramic products, glass and glassware",
    "XIV": "Natural or cultured pearls, precious or semi-precious stones, precious metals, metals clad with precious metal and articles thereof; imitation jewelry, coins",
    "XV": "Base metals and articles of base metal",
    "XVI": "Machinery and mechanical appliances, electrical equipment; parts thereof, sound recorders and reproducers, television image and sound recorders and reproducers, and parts and accessories of such articles",
    "XVII": "Vehicles, aircraft, vessels and associated transport equipment",
    "XVIII": "Optical, photographic, cinematographic, measuring, checking, precision, medical or surgical instruments and apparatus, clocks and watches, musical instruments; parts and accessories thereof",
    "XIX": "Arms and ammunition; parts and accessories thereof",
    "XX": "Miscellaneous manufactured articles",
    "XXI": "Works of art, collectors' pieces and antiques",
    "XXII": "Other unclassified goods",
    "XXIII": "Special classification provisions: Original Equipment Components",
}
_NUM = r"(?:-?\d{1,3}(?:[ ,]\d{3})*(?:\.\d+)?%?|-)"
_TAIL = re.compile(r"((?:\s+" + _NUM + r")+)\s*$")
_TOK = re.compile(r"(?<!\S)" + _NUM + r"(?!\S)")
_SEC_RX = re.compile(r"^(?P<rn>[IVX]+)\s*(?:\((?P<ch>[\d\s\-]*)\)?)?\s*(?P<rest>.*)$")
_MONTH_TOKEN = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|"
                          r"November|December)\s+(\d{4})\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|"
                          r"Nov|Dec)[-'](\d{2})\b", re.I)


def _to_float(tok: str):
    tok = tok.strip()
    if tok == "-" or tok.endswith("%"):
        return None
    return float(tok.replace(",", "").replace(" ", ""))


_MONTH_TOKEN_NS = re.compile(r"(January|February|March|April|May|June|July|August|September|October|"
                             r"November|December)(\d{4})|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|"
                             r"Nov|Dec)[-'](\d{2})(?!\d)", re.I)


def _ns(s: str) -> str:
    """Spaces removed: some releases (2020) space out letters ("A FR IC A")."""
    return re.sub(r"\s+", "", s)


def _month_tokens(line: str) -> list[str]:
    out = []
    for m in _MONTH_TOKEN_NS.finditer(_ns(line)):
        if m.group(1):
            out.append(f"{int(m.group(2))}-{_MONTHS.index(m.group(1).lower()) + 1:02d}")
        else:
            out.append(f"{2000 + int(m.group(4))}-{_MON3.index(m.group(3).lower()) + 1:02d}")
    return out


def _years(line: str) -> list[str]:
    """Years in a cumulative-column header: '2016 2015' or "Jan'09 Jan'10"."""
    yrs = re.findall(r"\b(20\d{2})\b", line)
    if len(yrs) >= 2:
        return yrs
    return [str(2000 + int(y)) for y in re.findall(r"[A-Za-z]{3}'(\d{2})\b", line)]


_ZONE_NS = {_ns(k): v for k, v in _ZONE_LABEL.items()}
_ZONE_NS.update({"SHIPS/AIRCRAFTSTORES": "SHIP/AIRCRAFT"})


def _pct_ok(blk: list[str]) -> bool:
    """Is block [v1, v2, pct, ...] self-consistent (pct = change between v1, v2)?"""
    if not blk[2].endswith("%"):
        return False
    a, b = _to_float(blk[0]), _to_float(blk[1])
    p = float(blk[2][:-1].replace(" ", ""))
    if not a or not b:
        return True
    for x, y in ((a, b), (b, a)):
        if abs((x / y - 1) * 100 - p) <= max(1.0, abs(p) * 0.02):
            return True
    return False


def _interpret(toks: list[str], ship: bool):
    """Token list of one row -> its blocks [(v1, v2, pct)], anchored on the
    percentage tokens: each block's two values are the two tokens just before
    its percentage. Whatever sits between (the revision column, printed as
    "- 76.1" or even "4 7.3" in 2011-2013 releases) is ignored. Two blocks, or
    one (exports) for the ships' stores row; each must be self-consistent."""
    pct = [i for i, t in enumerate(toks) if t.endswith("%")]
    if len(pct) not in (1, 2) or (len(pct) == 1 and not ship):
        return None
    blocks = []
    for i in pct:
        if i < 2:
            return None
        blk = [toks[i - 2], toks[i - 1], toks[i]]
        if not _pct_ok(blk):
            return None
        blocks.append(blk)
    if len(blocks) == 2 and pct[0] + 2 >= pct[1]:
        return None
    return blocks


def _tail_tokens(line: str):
    m = _TAIL.search(line)
    if not m:
        return line, []
    return line[:m.start()].strip(), _TOK.findall(m.group(1))


def _page_kind(text: str) -> tuple[str, str]:
    """(kind, coverage): kind monthly | cumulative | other; coverage incl | excl."""
    head = _ns(" ".join(text.split("\n")[:4]).lower())
    excl = ("excluding" in head or re.search(r"(blns|beln)(monthly|cumulative)", head) is not None)
    cov = "excl" if excl else "incl"
    low = text.lower()
    period = next((l for l in low.splitlines() if l.strip().startswith("period")), "")
    # A cumulative page: titled so, or its PERIOD line runs "January - April"
    # (the 2010 releases' progressive Table A is captioned like the monthly one).
    if ("cumulativestatement" in head or "progressive" in low[:3000]
            or re.search(r"jan[a-z]*\s*(-|to)\s*[a-z]", period)):
        return "cumulative", cov
    if "monthlystatement" in head or "monthly figures" in low[:600]:
        return "monthly", cov
    if "table a: totals" in text.lower() and "period:" in text.lower():
        return "monthly", cov
    return "other", cov


def _flow_order(lines: list[str]) -> list[str]:
    for ln in lines:
        u = _ns(ln.upper())
        if "EXPORTS" in u and "IMPORTS" in u:
            return ["export", "import"] if u.index("EXPORTS") < u.index("IMPORTS") else ["import", "export"]
    return []


def _col_months(lines: list[str], start: int) -> list[str]:
    for ln in lines[start:]:
        if ln.strip().upper().startswith("PERIOD"):
            continue
        toks = _month_tokens(ln)
        if len(toks) >= 2:
            return toks[:2]
    return []


def _orientation(blocks_list) -> int | None:
    """Which column is the CURRENT period: 1 if the percentage is v2 against
    v1 (columns previous, current), 0 if v1 against v2. Voted over the rows."""
    votes = [0, 0]
    for blocks in blocks_list:
        for blk in blocks:
            a, b = _to_float(blk[0]), _to_float(blk[1])
            if not a or not b or a == b:
                continue
            p = float(blk[2][:-1].replace(" ", ""))
            e1 = abs((b / a - 1) * 100 - p)
            e0 = abs((a / b - 1) * 100 - p)
            if abs(e1 - e0) > 0.05:
                votes[1 if e1 < e0 else 0] += 1
    if votes[0] == votes[1]:
        return None
    return 1 if votes[1] > votes[0] else 0


def _statement_rows(text: str, kind: str, cur: str, src: str) -> list[dict]:
    """World-zone and HS-section rows of one statement page: a monthly page
    (current and previous month) or the cumulative page of a December release
    (January-December of the current and previous year). `cur` is the release's
    reporting month (YYYY-MM); which column holds it is read from the printed
    percentage change (current against previous), so a header whose month
    labels are split, spaced out or missing cannot misplace a column."""
    lines = [l for l in text.split("\n") if l.strip()]
    flows = _flow_order(lines)
    if not flows:
        return []
    y, m = int(cur[:4]), int(cur[5:])
    if kind == "monthly":
        prev = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
        periods, freq = (cur, prev), "monthly"
    else:
        periods, freq = (str(y), str(y - 1)), "annual"
    parsed = []
    for ln in lines:
        label, toks = _tail_tokens(ln)
        if not toks:
            continue
        lab_u = _ns(label.upper())
        commodity, code = None, ""
        if lab_u in _ZONE_NS:
            partner, ptype = _ZONE_NS[lab_u], "group"
        elif lab_u in ("TOTAL", "GRANDTOTAL"):
            partner, ptype = None, "world"
        else:
            mm = _SEC_RX.match(label.strip())
            if not mm or mm.group("rn") not in _SECTIONS:
                continue
            if not re.match(r"^[IVX]+(\s|\(|$)", label.strip()):
                continue
            code = mm.group("rn")
            commodity = _SECTIONS[code]
            partner, ptype = None, "world"
        blocks = _interpret(toks, partner == "SHIP/AIRCRAFT")
        if blocks is None:
            continue
        fl = flows if len(blocks) == 2 else ["export"]
        parsed.append((partner, ptype, commodity, code, fl, blocks))
    ori = _orientation([p[5] for p in parsed])
    if ori is None:
        return []
    col_period = {ori: periods[0], 1 - ori: periods[1]}
    out = []
    for partner, ptype, commodity, code, fl, blocks in parsed:
        for f, blk in zip(fl, blocks):
            for ci in (0, 1):
                v = _to_float(blk[ci])
                if v is None or v < 0:
                    continue
                out.append(row(tradeflow=f, period=col_period[ci], frequency=freq, value=v, unit=CUR,
                               unit_multiplier=1e6, commodity=commodity,
                               commodity_classification="national" if commodity else "",
                               commodity_code_nso=code, partner=partner, partner_type=ptype,
                               series_code=src))
    return out


def _clean(t: str) -> str:
    """Unicode dashes -> '-'; a decimal comma (2020 releases: '1 519,3', '6,6%') -> '.'."""
    t = re.sub("[‐‑‒–−]", "-", t)
    return re.sub(r"(?<=\d),(?=\d{1,2}(?!\d))", ".", t)


def _reporting_month(page1: str, fname: str) -> str | None:
    mm = _MONTH_TOKEN_NS.search(_ns(page1))
    if mm and mm.group(1):
        return f"{mm.group(2)}-{_MONTHS.index(mm.group(1).lower()) + 1:02d}"
    b = fname.lower()
    y = re.search(r"20\d{2}", b)
    mo = next((i for i, x in enumerate(_MON3) if re.search(rf"[-_]{x}", b)), None)
    if y and mo is not None:
        return f"{y.group(0)}-{mo + 1:02d}"
    return None


def _headline(path: str, src: str) -> list[dict]:
    """Page 1: exports, imports, trade balance, in rand, by word position."""
    import fitz
    rows = []
    doc = fitz.open(path)
    try:
        words = doc[0].get_text("words")
    finally:
        doc.close()
    lines: dict = {}
    anchors: list = []
    for x0, y0, x1, y1, w, *_ in sorted(words, key=lambda t: (t[1] + t[3]) / 2):
        ym = (y0 + y1) / 2
        if anchors and abs(ym - anchors[-1]) <= 3:
            key = anchors[-1]
        else:
            anchors.append(ym)
            key = ym
        lines.setdefault(key, []).append((x0, w))
    order = sorted(lines)
    # header x-positions
    hdr = None
    for k in order:
        ws = sorted(lines[k])
        txt = [w.upper() for _, w in ws]
        if "EXPORTS" in txt and "IMPORTS" in txt and "BALANCE" in txt:
            hdr = {"export": ws[txt.index("EXPORTS")][0], "import": ws[txt.index("IMPORTS")][0],
                   "balance": ws[txt.index("TRADE")][0] if "TRADE" in txt else ws[txt.index("BALANCE")][0]}
            break
    if not hdr:
        return rows
    seen_cum = False
    n_taken = 0
    for k in order:
        ws = sorted(lines[k])
        text = " ".join(w for _, w in ws)
        if re.search(r"CUMULATIVE|PROGRESSIVE", text, re.I):
            seen_cum = True
        if seen_cum:
            break
        m = re.match(r"^(January|February|March|April|May|June|July|August|September|October|November|"
                     r"December)\s+(\d{4})\s*\((Preliminary|Prelim|Revised|Unaudited|Audited)\)", text, re.I)
        if not m:
            continue
        period = f"{m.group(2)}-{_MONTHS.index(m.group(1).lower()) + 1:02d}"
        # The reporting month always; the previous month only when labelled
        # "(Revised)" -- the 2010-2012 releases repeat the previous month's
        # UNREVISED total on page 1 ("December 2009 (Unaudited)") while their
        # Table A carries the revised one.
        if n_taken and m.group(3).lower() != "revised":
            continue
        n_taken += 1
        # value words to the right of the label, grouped into numbers
        label_end = None
        for i, (x, w) in enumerate(ws):
            if w.endswith(")") and re.search(r"(Preliminary|Prelim|Revised|Unaudited|Audited)\)$", w, re.I):
                label_end = i
                break
        if label_end is None:
            continue
        nums, cur = [], None
        for x, w in ws[label_end + 1:]:
            if w == "R":
                if cur:
                    nums.append(cur)
                cur = [x, ""]
                continue
            if re.fullmatch(r"-?[\d,]+", w):
                if cur is None:
                    cur = [x, w]
                elif "," in w and cur[1]:
                    nums.append(cur)
                    cur = [x, w]
                else:
                    if not cur[1]:
                        cur[0] = x
                    cur[1] += w
        if cur and cur[1]:
            nums.append(cur)
        if len(nums) != 3:
            continue
        for flow, (x, s) in zip(sorted(hdr, key=hdr.get), nums):
            v = float(s.replace(",", ""))
            if flow != "balance" and v < 0:
                continue
            rows.append(row(tradeflow=flow, period=period, frequency="monthly", value=v, unit=CUR,
                            series_code=src + " p1"))
    return rows


def _parse_one_pdf(path: str, min_zone_period: str = "2014-01") -> tuple[str | None, list[dict]]:
    import pdfplumber
    src = os.path.basename(path)
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[:10]
        texts = [_clean(p.extract_text() or "") for p in pages[:3]]
        cur = _reporting_month(texts[0] if texts else "", src)
        if cur is None:
            return None, []
        # COVERAGE. Releases up to the September 2013 figures cover South Africa
        # WITHOUT the BLNS countries (their 2010 annual exports, R590.0bn, are
        # R76bn below the sum of SARS's own 2010 bilateral workbook including
        # BLNS); from the October 2013 release the national figures INCLUDE BLNS
        # and say so. Only releases that state "including BLNS/BELN" are read, so
        # that one series never mixes the two coverages.
        if not re.search(r"includ\w*\s*(blns|beln)", _ns(" ".join(texts).lower())):
            return cur, []
        texts += [_clean(p.extract_text() or "") for p in pages[3:]]
        rows = []
        # Only pages titled as a statement are read. An untitled page is never
        # taken as a continuation (March 2013: the cumulative page is untitled).
        kinds = [_page_kind(t) for t in texts]
        for want in ("monthly", "cumulative"):
            if want == "cumulative" and cur[5:] != "12":
                continue
            tag = src if want == "monthly" else src + " cumulative"
            for j, (kind, cov) in enumerate(kinds):
                if kind != want or cov == "excl":
                    continue
                got = _statement_rows(texts[j], want, cur, tag)
                if not got:   # letter-spaced page (Nov 2018): wider character tolerance
                    got = _statement_rows(_clean(pages[j].extract_text(x_tolerance=8) or ""), want, cur, tag)
                # Zones and totals from 2014 are in the Excel workbook (exact rand).
                lim = min_zone_period if want == "monthly" else min_zone_period[:4]
                rows += [r for r in got if r["commodity"] != "All products" or r["period"] < lim]

    # Page 1 gives exports, imports and balance of one release together; all
    # three are kept so that they are always of one vintage.
    return cur, rows + _headline(path, src)


def parse_pdf(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = sorted(set([path] + [p for p in (extras or []) if p.lower().endswith(".pdf")]))
    rows = []
    for p in paths:
        cur, got = _parse_one_pdf(p)
        rows += [dict(r, _order=cur or "") for r in got]
    if not rows:
        raise ValueError("south_africa_sars: no rows decoded from the PDFs")
    df = pd.DataFrame.from_records(rows)
    # Oldest release first, so the newest release's (revised) figure is kept.
    key = ["tradeflow", "commodity_code_nso", "commodity", "partner", "frequency", "period"]
    df = df.sort_values("_order", kind="stable").drop_duplicates(key, keep="last")
    # Where page 1 gives a month's exports/imports/balance, the statement's
    # Total row for that month (possibly of another release) is dropped.
    p1 = set(df.loc[df["series_code"].str.endswith(" p1"), "period"])
    tot = (df["commodity"] == "All products") & (df["partner"] == "All partners") &         (df["frequency"] == "monthly") & ~df["series_code"].str.endswith(" p1") & df["period"].isin(p1)
    return df[~tot].drop(columns="_order").reset_index(drop=True)
