"""Parser for the Bureau of Statistics and Census (BSC) Libya annual "External Trade Statistics" (PDF).

Bilingual (English/Arabic) text-layer PDF, one per year (bsc.ly, 2019-2025):
  Table 1  value of exports and imports 1999-<year>, thousand LYD (with %
           changes, not read). Columns, left to right in the text layer:
           year | imports | % | exports | % | year (verified: 2025 exports -
           imports = the 5 661.6 million LYD surplus printed in the summary).
  Table 3  exports and imports by HS section and chapter ("division"), LYD:
           section rows (code in the "Sec" column) -> national, chapter rows
           (code in the "Div" column) -> hs2.
  Table 4  exports and imports by country, LYD, under regional headings
           ("Arab league countries", "European union countries" ...) whose
           "Total" lines are emitted as the region (group).
In Tables 3-4 the value columns read imports then exports (verified: Italy
takes 35.7 % of 2025 exports, as the text says). English labels wrap over
several lines around the line that carries the code and figures; each English
fragment is attached to the nearest code line (by vertical position), Arabic
words are dropped. Thousands in Table 1 are separated by spaces, so numbers
are formed from the words' x-gaps (as in the ONS Algeria parser).
"""
from __future__ import annotations

import re

import pandas as pd

from ._common import row

_AR = re.compile(r"[؀-ۿ]")
_GHOST = re.compile(r"\s*(?:Arab league|African|European union|Other European|N\.M\.S\.American|Asian|Other)"
                    r"\s+countries\s*$", re.I)


def _lines(page):
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    lines, cur, top = [], [], None
    for w in words:
        if top is None or abs(w["top"] - top) > 3:
            if cur:
                lines.append(sorted(cur, key=lambda w: w["x0"]))
            cur, top = [w], w["top"]
        else:
            cur.append(w)
    if cur:
        lines.append(sorted(cur, key=lambda w: w["x0"]))
    return lines


def _clusters(words):
    out = []
    for w in words:
        if out and w["x0"] - out[-1][-1]["x1"] < 3.5:
            out[-1].append(w)
        else:
            out.append([w])
    return [" ".join(x["text"] for x in c) for c in out]


def _table1(page, year_max: int) -> list[dict]:
    out = []
    for ln in _lines(page):
        nums = [w for w in ln if re.fullmatch(r"[\d.]+", w["text"])]
        cl = _clusters(nums)
        if len(cl) < 4 or not re.fullmatch(r"(19|20)\d\d", cl[0]) or cl[-1] != cl[0]:
            continue
        mid = cl[1:-1]
        ints = [c for c in mid if re.fullmatch(r"\d{1,3}(?: \d{3})+|\d{1,3}", c) and " " in c]
        if len(ints) != 2:
            continue
        imp, exp = (float(c.replace(" ", "")) for c in ints)
        for fl, v in (("import", imp), ("export", exp)):
            out.append(row(tradeflow=fl, period=cl[0], frequency="annual", value=v, unit="LYD",
                           unit_multiplier=1e3, series_code="Table 1"))
    return out


def _sec_x(pages) -> float:
    """The x that parts the Table 3 SECTION code column from the CHAPTER code column,
    over ALL its pages (midway between the leftmost and rightmost code x). Taken per
    page as "the leftmost code", a page holding only chapters filed its chapters
    (59, 60, 68 ...) as sections."""
    xs = []
    for page in pages:
        for ln in _lines(page):
            if re.fullmatch(r"\d{1,2}", ln[0]["text"]) and ln[-1]["text"] == ln[0]["text"] and len(ln) > 2:
                xs.append(ln[0]["x0"])
                if re.fullmatch(r"\d{1,2}", ln[1]["text"]) and ln[1]["x0"] - ln[0]["x0"] < 40:
                    xs.append(ln[1]["x0"])
    return (min(xs) + max(xs)) / 2 if xs else 0.0


def _coded_table(pages, year: str, table: str) -> list[dict]:
    """Table 3 (code lines) or Table 4 (country lines)."""
    out = []
    region = None
    sec_x = _sec_x(pages) if table == "Table 3" else 0.0
    imp3, exp3 = [], []
    for page in pages:
        lines = _lines(page)
        rows = []        # (top, kind, code, imp, exp, [english words])
        frags = []       # (top, english text)
        single, imp_x1, exp_x1 = [], [], []
        single3 = []
        for ln in lines:
            eng = [w for w in ln if not _AR.search(w["text"])]
            ints = [w for w in eng if re.fullmatch(r"\d+", w["text"])]
            text = " ".join(w["text"] for w in eng)
            if text.startswith(("Table no", "Value", "value", "Sec Div", "Country")):
                continue
            if table == "Table 3":
                # "15 81 ARTICLES ... 1156076 0 81": the section code printed only at the left
                head_sec = (len(ints) >= 4 and ln[-1] is ints[-1] and re.fullmatch(r"\d{1,2}", ints[1]["text"])
                            and ints[1]["x0"] - ints[0]["x0"] < 40 and ints[-1]["text"] == ints[1]["text"])
                tail_sec = (len(ints) >= 4 and ln[-1] is ints[-1] and ints[-2]["text"] == ints[0]["text"]
                            and re.fullmatch(r"\d{1,2}", ints[-1]["text"]))
                if len(ints) >= 3 and re.fullmatch(r"\d{1,2}", ints[0]["text"]) and ln[0] is ints[0]                         and re.fullmatch(r"\d{1,2}", ln[-1]["text"]) and (ln[-1]["text"] == ints[0]["text"] or tail_sec or head_sec):
                    # "11 59 23691309 0 ... 59 11": a chapter line that repeats its section's
                    # code (a section continued from the previous page). It is CHAPTER 59;
                    # read as section 11 it gave the section chapter 59's figures and title.
                    two = (len(ints) >= 5 and re.fullmatch(r"\d{1,2}", ints[1]["text"])
                           and ints[1]["x0"] - ints[0]["x0"] < 40 and ints[-2]["text"] == ints[1]["text"])
                    # "82 271104483 68449 82 15": the section code printed only at the right
                    lead, right = (ints[1], ints[-1]) if (head_sec and not two) else (ints[1], ints[-2]) if two else (ints[0], ints[-2]) if (
                        tail_sec and ln[-1]["text"] != ints[0]["text"]) else (ints[0], ints[-1])
                    # the two figures stand between the code columns ("22 99 ... 0 99 22"
                    # used to read the chapter code 99 as the exports figure)
                    big = [w for w in ints if w["x0"] > lead["x0"] + 50 and w["x1"] < right["x0"] - 50]
                    if len(big) == 1:
                        # one figure, the other cell blank ("83 329510906 83"): placed by
                        # its right edge under the imports or exports column (below)
                        lab = " ".join(w["text"] for w in eng if w not in ints and lead["x0"] < w["x0"]
                                       and w["x1"] <= big[0]["x0"])
                        single3.append([ln[0]["top"], lead["x0"], lead["text"], big[0]["x1"], big[0]["text"], [lab]])
                        continue
                    if len(big) != 2:
                        continue
                    imp3.append(big[0]["x1"])
                    exp3.append(big[1]["x1"])
                    # the English title is what stands LEFT of the figures; a "-" right of
                    # them ("LIVE ANIMALS - ANIMAL PRODUCTS -") is the Arabic title's dash
                    lab = " ".join(w["text"] for w in eng if w not in ints and lead["x0"] < w["x0"]
                                   and w["x1"] <= big[0]["x0"])
                    rows.append([ln[0]["top"], lead["x0"], lead["text"], big[0]["text"], big[1]["text"], [lab]])
                elif text and not ints:
                    frags.append((ln[0]["top"], text))
            else:
                # a figure may print with decimals ("Qatar 26141208.64 0", 2021)
                ints = [w for w in eng if re.fullmatch(r"\d+(?:\.\d+)?", w["text"])]
                if ints:
                    # brackets right of the figures belong to the Arabic name ("Congo
                    # (Brazzaville) 421013 0 ) (" used to lose the row)
                    eng = [w for w in eng if w["x0"] <= ints[-1]["x1"] + 1]
                if len(ints) == 1 and ints[-1] is eng[-1] and len(eng) > 1:
                    # one figure (the other cell blank, "Costa Rica 42311586"): kept when it
                    # stands right-aligned under the imports or the exports column
                    single.append((ln[0]["top"], " ".join(w["text"] for w in eng[:-1]).strip(), ints[-1]["x1"],
                                   ints[-1]["text"]))
                elif len(ints) >= 2 and ints[-1] is eng[-1] and ints[-2] is eng[-2]:
                    imp_x1.append(ints[-2]["x1"])
                    exp_x1.append(ints[-1]["x1"])
                    lab = " ".join(w["text"] for w in eng[:-2]).strip()
                    # the 2021 report prints a region heading ("Arab league countries")
                    # on the first row of every page, whatever the region: not part of
                    # the country's name ("Niger Arab league countries", "LuxeembourgArab
                    # league countries"). Repaired 2026-11-12.
                    lab = _GHOST.sub("", lab).strip() or lab
                    rows.append([ln[0]["top"], None, None, ints[-2]["text"], ints[-1]["text"], [lab]])
                elif text and not ints and re.search(r"countries$", text, re.I):
                    rows.append([ln[0]["top"], None, "HEADING", None, None, [text]])
                elif text and not ints and text.lower() not in ("country",):
                    rows.append([ln[0]["top"], None, "FRAG", None, None, [text]])
                # any other text line (the column header "country", a wrapped name) is not a
                # region heading: it used to name the next region total "country"
        if table != "Table 3" and single and imp_x1:
            mi, me = sorted(imp_x1)[len(imp_x1) // 2], sorted(exp_x1)[len(exp_x1) // 2]
            for top, lab, x1, tok in single:
                lab = _GHOST.sub("", lab).strip() or lab
                if abs(x1 - mi) <= 3:
                    rows.append([top, None, None, tok, None, [lab]])
                elif abs(x1 - me) <= 3:
                    rows.append([top, None, None, None, tok, [lab]])
            rows.sort(key=lambda r: r[0])
        if table == "Table 3" and single3 and imp3:
            mi, me = sorted(imp3)[len(imp3) // 2], sorted(exp3)[len(exp3) // 2]
            for top, x0, code, x1, tok, lab in single3:
                if abs(x1 - mi) <= 3:
                    rows.append([top, x0, code, tok, None, lab])
                elif abs(x1 - me) <= 3:
                    rows.append([top, x0, code, None, tok, lab])
            rows.sort(key=lambda r: r[0])
        if table == "Table 3":
            for top, txt in frags:
                if not rows:
                    break
                best = min(rows, key=lambda r: abs(r[0] - top))
                best[5].append((top, txt))
            for r in rows:
                parts = [(r[0], r[5][0])] + [p for p in r[5][1:]]
                label = " ".join(t for _, t in sorted(parts) if t).strip()
                label = re.sub(r"\s+", " ", label)
                is_sec = r[1] < sec_x and not r[2].startswith("0")
                code = r[2]
                for fl, v in (("import", r[3]), ("export", r[4])):
                    if v is None:
                        continue
                    out.append(row(tradeflow=fl, period=year, frequency="annual", value=float(v), unit="LYD",
                                   commodity=label or f"{code}",
                                   commodity_classification="national" if is_sec else "hs2",
                                   commodity_code_nso="" if is_sec else code.zfill(2), series_code=table))
        else:
            # A name wrapped AROUND its figures ("China, Hong Kong Special" / figures with
            # no name / "Administrative Region"): the figures line takes both fragments
            # when it has no name of its own and a fragment directly above and below.
            # Any other fragment is ignored (it once named a region "Administrative Region").
            for k, r in enumerate(rows):
                if r[2] is None and not r[5][0] and 0 < k < len(rows) - 1                         and rows[k - 1][2] == "FRAG" and rows[k + 1][2] == "FRAG":
                    r[5][0] = rows[k - 1][5][0] + " " + rows[k + 1][5][0]
            for r in rows:
                lab = r[5][0]
                if r[2] == "FRAG":
                    continue
                if r[2] == "HEADING":
                    region = lab
                    continue
                if lab.lower() == "grand total":
                    continue                  # = Table 1's totals
                if lab.lower() == "total":
                    if region is None:
                        continue
                    name, ptype = region, "group"
                else:
                    name, ptype = lab, "country"
                if not name:
                    continue
                for fl, v in (("import", r[3]), ("export", r[4])):
                    if v is None:
                        continue
                    out.append(row(tradeflow=fl, period=year, frequency="annual", value=float(v), unit="LYD",
                                   partner=name, partner_type=ptype, series_code=table))
    return out


def parse_rows(path: str) -> list[dict]:
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        t3, t4, year = [], [], None
        for page in pdf.pages[15:60]:
            head = (page.extract_text() or "")[:400]
            if "Table no (1)" in head or "Table no(1)" in head:
                out += _table1(page, 0)
            m = re.search(r"Table no 3\b.*?(20\d\d)", head, re.S)
            if m:
                t3.append(page)
                year = re.search(r"During (20\d\d)", head).group(1) if re.search(r"During (20\d\d)", head) else year
            if re.search(r"Table no 4\b", head):
                t4.append(page)
                y = re.search(r"By Country (20\d\d)", head)
                year = y.group(1) if y else year
        if year:
            out += _coded_table(t3, year, "Table 3")
            out += _coded_table(t4, year, "Table 4")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    from ..schema import KEY
    frames = []
    for p in dict.fromkeys([*(extras or []), path]):
        df = pd.DataFrame(parse_rows(p))
        if not df.empty:
            frames.append((df["period"].max(), df))
    frames.sort(key=lambda t: t[0])
    df = pd.concat([f for _, f in frames], ignore_index=True)
    return df.drop_duplicates(KEY, keep="last").reset_index(drop=True)
