"""Config-driven reader for labour cross-tabs printed in a report PDF.

The PDF counterpart of `excel_wide_labour`. Same idea -- a layout says where a
table is, what its columns MEAN and what its categories are classified under,
and every category row between the header and the end of the table is scanned
rather than listed. What differs is everything about getting at the text.

    Table 5.2: Number and Percentage Distribution of Employed Persons by
    Status in employment and Sex, Zambia 2024
                                      Total        Male        Female
    Status in employment
                                Number Percent  Number Percent  Number Percent
    Total                     3,972,883  100.0  2,425,055 100.0  1,547,828 100.0
    Employers in corporations    60,762    1.5     43,048   1.8     17,714   1.1
    Employers in household market
                                 34,196    0.9     23,589   1.0     10,607   0.7
    enterprises

Three things in that excerpt defeat a naive line reader, and each has an option
here:

* THE LABEL WRAPS AROUND ITS OWN NUMBERS. "Employers in household market" and
  "enterprises" sit either side of the values. `join_wrapped_labels` folds the
  tail back before matching, so the category is read whole.
* THE COLUMNS ARE (sex x measure), not one value per row. A row carries six
  numbers: a count and a percentage for each of Total, Male and Female. The
  column list says so, and a `skip` drops one that this schema has no home for.
* A CATEGORY IS NOT KNOWN IN ADVANCE. `row_scan` takes every line whose label
  matches and whose number count is right, with `expect_rows` as the guard: a
  scan yielding fewer categories than the layout says the table has raises,
  rather than quietly shipping half of it.

FRENCH AND PORTUGUESE SOURCES write "1 234" with a space, so `decimal: ","`
also switches number rebuilding to treat a thin gap as a thousands separator
rather than a column break.

MORE TRAPS, AND THE OPTION FOR EACH (all opt-in; a layout that sets none reads
exactly as before):

* SEVERAL TABLES SHARE A PAGE, often with the SAME row labels -- Statistics
  Botswana prints occupation counts (1.5a) and occupation percentages (1.5b)
  one above the other, both nine columns wide. Selecting by page alone read the
  counts twice. `caption` (a regex) opens a table's region and `end` (default:
  the next Table/Source/Figure line) closes it.
* A DASH IS A CELL. "613 - 613" is three columns, not two. With
  `dash_placeholder` the dash keeps its position and emits nothing, instead of
  sliding every later value one column left.
* ONE TABLE, SEVERAL BLOCKS. Botswana's status-in-employment table repeats its
  categories for Total, Male and Female, flagged only by a word at the start of
  each block's first row. `blocks` strips that word and applies its settings
  (e.g. `sex`) to every row until the next block.
* COLUMNS FROM MORE THAN ONE PERIOD. Trend tables print Q4 2020 ... Q1 2024
  side by side. `period_header` (a regex, with `period_count`) reads the
  periods from the table's own header line and a column takes one by
  `period_index` -- so a column is dated by what the report prints above it,
  never by an offset hardcoded against this issue.
* PERIODS DOWN THE ROWS. With `label_is_period` the row label is the period and
  each column names its own `characteristic`.
* DIGITS SPLIT BY LETTER-SPACING. NBS Seychelles' text layer yields "1 00.0"
  and "7 5.4" for 100.0 and 75.4. `split_digit_repair` rejoins them; enable it
  only for tables whose values all carry a decimal, because in a table of
  integers "3 1.8" is two cells.
* LABELS WRAPPED OVER THREE OR FOUR LINES, sometimes with the numbers on the
  middle line and sometimes capitalised on every line (NBS Tanzania: "Water
  Supply, Sewerage," / "Waste Management and 0.2 ..." / "Remediation
  Activities"). No line-by-line rule can tell whose label a fragment is. With
  `text_mode: "words"` rows are rebuilt from word POSITIONS instead: see
  `_word_lines`.
"""
from __future__ import annotations

import os
import re
import statistics
from typing import Callable

import pandas as pd

from . import _common as C

_NUMS_ONLY = re.compile(r"^[\s\d.,%()\-–]+$")
_HAS_DIGIT = re.compile(r"\d")
_END_DEFAULT = r"^\s*(?:Table|Tableau|Sources?\s*:|Figure|Graphique)\b"
_CAPTIONLIKE = re.compile(r"^\s*(?:Table|Tableau|Sources?|Figure|Graphique|Note)\b",
                          re.I)
_NUM_TOKEN = re.compile(r"^\(?-?\d[\d.,]*%?\)?$|^[-–—]$")


# --------------------------------------------------------------------------
# Getting at the text
# --------------------------------------------------------------------------

def _word_lines(page, min_nums: int = 2, barrier_re=None) -> list[str]:
    """Rebuild a page's table rows from word positions.

    Each physical line is split into a LABEL part and a trailing NUMBER run. A
    line with a number run is a data row; a digit-free line lying entirely left
    of a data row's first number is a label FRAGMENT. Anything else (captions,
    column headers, notes) is a barrier: no fragment is ever carried across it.

    Fragments lying between two data rows have to be shared out between them,
    and that is decided by GEOMETRY rather than by case or punctuation: a table
    cell centres its numbers vertically against its label, so the split chosen
    is the one that leaves each data row with the most even number of label
    lines above and below it (solved for the whole page at once, because one
    row's choice fixes its neighbour's). Ties go to reading sense -- a fragment
    starting lower-case continues the row above, a capitalised one starts the
    row below.

    Anything not attached is emitted as its own line, so captions and headers
    are still there for `caption` and `period_header` to find.
    """
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
    if not words:
        return []
    words.sort(key=lambda w: (w["top"], w["x0"]))
    rows: list[dict] = []
    for w in words:
        if rows and abs(w["top"] - rows[-1]["top"]) <= 3:
            rows[-1]["words"].append(w)
            rows[-1]["bottom"] = max(rows[-1]["bottom"], w["bottom"])
        else:
            rows.append({"top": w["top"], "bottom": w["bottom"], "words": [w]})

    for r in rows:
        ws = sorted(r["words"], key=lambda w: w["x0"])
        k = len(ws)
        while k and _NUM_TOKEN.match(ws[k - 1]["text"]):
            k -= 1
        run = ws[k:]
        r["text"] = " ".join(w["text"] for w in ws)
        r["label"] = " ".join(w["text"] for w in ws[:k])
        r["nums"] = " ".join(w["text"] for w in run)
        r["num_x0"] = run[0]["x0"] if run else None
        r["x1"] = max(w["x1"] for w in ws)
        digits = sum(1 for w in run if _HAS_DIGIT.search(w["text"]))
        r["data"] = len(run) >= min_nums and digits >= 1
        r["frag"] = (not r["data"] and not _HAS_DIGIT.search(r["text"])
                     and not _CAPTIONLIKE.match(r["text"]))
        # A SUB-HEADING IS NOT A LABEL FRAGMENT. HCP Morocco stacks four
        # distributions under one header, each introduced by "- Structure de
        # l'emploi selon ... (en %)" -- a digit-free line sitting directly
        # above the first category, which the fragment rule then folded into
        # that category's label. The heading text ended up inside the
        # characteristic, the region opened one row late, and the first
        # category of every block was lost. `barrier_pattern` marks such lines
        # so they stay where they are and close the run instead.
        if barrier_re is not None and barrier_re.search(r["text"]):
            r["frag"] = False

    lh = statistics.median(r["bottom"] - r["top"] for r in rows) or 8.0
    gap_max = 1.5 * lh
    data_idx = [i for i, r in enumerate(rows) if r["data"]]
    if not data_idx:
        return [r["text"] for r in rows]

    def fits(f: int, d: int | None) -> bool:
        return d is not None and rows[f]["x1"] <= rows[d]["num_x0"] + 1

    # One run per gap: before the first data row, between each pair, after the
    # last. A run is FREE (its split is chosen) only when every line in it is a
    # fragment reachable from both neighbours; otherwise the fragments touching
    # each neighbour are forced onto it and the rest are left alone.
    bounds = [-1] + data_idx + [len(rows)]
    runs = []
    for a, b in zip(bounds, bounds[1:]):
        prev = a if a >= 0 else None
        nxt = b if b < len(rows) else None
        between = list(range(a + 1, b))
        tail, j = [], a
        for i in between:
            if (rows[i]["frag"] and fits(i, prev)
                    and rows[i]["top"] - rows[j]["bottom"] <= gap_max):
                tail.append(i)
                j = i
            else:
                break
        head, j = [], b
        for i in reversed(between):
            if (rows[i]["frag"] and fits(i, nxt) and j < len(rows)
                    and rows[j]["top"] - rows[i]["bottom"] <= gap_max):
                head.insert(0, i)
                j = i
            else:
                break
        if between and tail == between and head == between:
            # A DATA ROW WHOSE OWN LABEL STARTS LOWER-CASE IS A CONTINUATION:
            # its label began on a line above it, so it cannot be left with
            # none. HCP Morocco wraps two occupation groups around their own
            # numbers --
            #     Membres des corps legislatifs, elus
            #     locaux, responsables hierarchiques
            #     de la fonction publique directeurs et   0,9 0,5 1,3 0,1 0,9
            #     cadres de direction d'entreprises
            #     Cadres superieurs et membres des
            #     professions liberales                   3,4 10,7 7,3 0,8 4,9
            # -- and handing BOTH loose lines to the row above balances both
            # rows perfectly (cost 1.1 against 3.0 for the right answer), so
            # the capitalised-fragment nudge alone lost. That reading ends one
            # category with the next one's opening words and publishes the
            # next as "professions liberales", a fragment of "Cadres
            # superieurs et membres des professions liberales".
            needs_head = (nxt is not None
                          and re.match(r"^[a-zà-ÿ]", rows[nxt]["label"]))
            opts = []
            for k in range(len(between) + 1):
                # A CAPITALISED fragment is weak evidence, worth only a nudge:
                # it may open the next row's label ("Accommodation and Food"
                # above its numbers) or close the previous one ("Fishing" under
                # "Agriculture, Forestry and").
                pen = sum(0.1 for i in between[:k]
                          if re.match(r"^[A-Z]", rows[i]["text"]))
                # A LOWER-CASE fragment is strong evidence: English continues a
                # wrapped label in lower case and starts a new one capitalised.
                # This has to outweigh balance, not tie-break it -- CSO
                # Eswatini prints "Electricity, gas, steam and air conditioning
                # 1.1 0.4 0.7" / "supply" / "Water supply; ...", where giving
                # "supply" to the row BELOW balances both rows perfectly and is
                # wrong, truncating one category and prefixing the next.
                pen += sum(3.0 for i in between[k:]
                           if re.match(r"^[a-zà-ÿ]", rows[i]["text"]))
                if needs_head and k == len(between):
                    pen += 3.0
                opts.append((between[:k], between[k:], pen))
        else:
            head = [i for i in head if i not in tail]
            opts = [(tail, head, 0.0)]
        runs.append(opts)

    # Dynamic programme over the runs: cost of data row t is
    # |lines above it - lines below it|.
    best = [[(o[2], None) for o in runs[0]]]
    for r in range(1, len(runs)):
        layer = []
        for o in runs[r]:
            cands = [(best[r - 1][p][0] + abs(len(runs[r - 1][p][1]) - len(o[0])) + o[2], p)
                     for p in range(len(runs[r - 1]))]
            layer.append(min(cands))
        best.append(layer)
    choice = [0] * len(runs)
    choice[-1] = min(range(len(best[-1])), key=lambda i: best[-1][i][0])
    for r in range(len(runs) - 1, 0, -1):
        choice[r - 1] = best[r][choice[r]][1]

    above = {d: [] for d in data_idx}
    below = {d: [] for d in data_idx}
    attached: set[int] = set()
    for r, (a, b) in enumerate(zip(bounds, bounds[1:])):
        down, up, _ = runs[r][choice[r]]
        if a >= 0:
            below[a].extend(down)
            attached.update(down)
        if b < len(rows):
            above[b].extend(up)
            attached.update(up)

    out = []
    for i, r in enumerate(rows):
        if i in attached:
            continue
        if r["data"]:
            parts = ([rows[f]["text"] for f in above[i]]
                     + ([r["label"]] if r["label"] else [])
                     + [rows[f]["text"] for f in below[i]])
            out.append(" ".join(parts + [r["nums"]]).strip())
        else:
            out.append(r["text"])
    return out


def _pages(path: str, split_columns: int = 1, mode: str = "text",
           min_nums: int = 2, barrier_re=None) -> list[str]:
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            if mode == "words":
                out.append("\n".join(_word_lines(page, min_nums, barrier_re)))
                continue
            if split_columns <= 1:
                out.append(page.extract_text() or "")
                continue
            w = float(page.width)
            for i in range(split_columns):
                band = page.crop((w * i / split_columns, 0,
                                  w * (i + 1) / split_columns, float(page.height)))
                out.append(band.extract_text() or "")
    return out


def _select(pages: list[str], spec: dict) -> list[str]:
    want = [t.lower() for t in spec.get("page_contains", [])]
    skip = [t.lower() for t in spec.get("page_excludes", [])]
    cap = re.compile(spec["caption"], re.I | re.M) if spec.get("caption") else None
    hits = []
    for text in pages:
        low = text.lower()
        if want and not all(t in low for t in want):
            continue
        if skip and any(t in low for t in skip):
            continue
        if cap and not cap.search(text):
            continue
        hits.append(text)
    return hits


def _regions(lines: list[str], spec: dict, drop_re: re.Pattern) -> list[list[str]]:
    """The line ranges belonging to this table: caption (exclusive) to `end`."""
    if not spec.get("caption"):
        return [lines]
    cap_re = re.compile(spec["caption"], re.I)
    end_re = re.compile(spec.get("end", _END_DEFAULT), re.I)
    # `end_after` closes the region AFTER a matching line (typically the Total
    # row). Needed where commentary follows a table with no caption between:
    # Statistics Botswana's "... from 144,200 persons (18.3 percent) in Q3 2023
    # to 153,044 persons (20.3" carries exactly six numbers, and was read as a
    # seventh-column-perfect industry row.
    after_re = re.compile(spec["end_after"], re.I) if spec.get("end_after") else None
    # THE SUB-HEADING CAN SHARE ITS LINE WITH THE FIRST CATEGORY. Where a
    # narrow first column wraps the heading, its tail sits level with the first
    # data row and is rebuilt into that row: HCP Morocco's "groupes de
    # professions (en %) Membres des corps legislatifs ... 0,9 0,5 1,3 0,1 0,9"
    # is heading, category and values on one line. Dropping the caption line
    # whole would drop the first category of every block with it, so with
    # `caption_inline` what follows the caption opens the region instead.
    inline = spec.get("caption_inline", False)
    out: list[list[str]] = []
    cur: list[str] | None = None
    for ln in lines:
        s = ln.strip()
        if cur is None:
            # A caption on a table-of-contents line (dot leaders) is not the table.
            m = cap_re.search(s)
            if not m or drop_re.search(s):
                continue
            cur = []
            if not inline:
                continue
            s = s[m.end():].strip()
            if not s:
                continue
            ln = s
        elif end_re.search(s) and not cap_re.search(s):
            out.append(cur)
            cur = None
            continue
        cur.append(ln)
        if after_re and after_re.search(s):
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return out


def _repair_split_digits(line: str) -> str:
    line = re.sub(r"(?<![\d.,])(\d) (?=\d{1,2}\.\d)", r"\1", line)
    return re.sub(r"(\d) (?=\.\d)", r"\1", line)


def _rejoin_wrapped(lines: list[str], decimal: str = ".") -> list[str]:
    """Rebuild a row whose LABEL wraps around its own numbers.

    A narrow first column makes the renderer emit three lines where the report
    shows one -- the label's head, then the values, then the label's tail. The
    tail is folded back when it carries at most one number of its own (a unit,
    an age bound); more than one and it is the next data row, not a
    continuation.
    """
    out: list[str] = []
    i = 0
    while i < len(lines):
        head = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        tail = lines[i + 2].strip() if i + 2 < len(lines) else ""
        after = lines[i + 3].strip() if i + 3 < len(lines) else ""
        if (head and not _HAS_DIGIT.search(head)
                and nxt and _NUMS_ONLY.match(nxt) and _HAS_DIGIT.search(nxt)):
            if (tail and len(C.numbers_in(tail, decimal=decimal)) <= 1
                    and len(tail.split()) <= 8
                    and not (after and _NUMS_ONLY.match(after)
                             and len(C.numbers_in(after, decimal=decimal)) >= 2)):
                out.append(f"{head} {tail} {nxt}")
                i += 3
                continue
            out.append(f"{head} {nxt}")
            i += 2
            continue
        # THE OTHER WRAP: the label's middle carries the numbers, so the data
        # line is part-label part-values --
        #     Own account workers in household
        #     market enterprises without 1,739,620 43.8 966,389 39.9 ...
        #     employees
        # Read alone, that middle line's category reads "market enterprises
        # without". What separates a continuation from a new row is CASE: a
        # continuation resumes mid-sentence and starts lower-case, while every
        # category and every column header starts capitalised. That is what
        # keeps the header line ("Number Percent Number Percent ...") from
        # being glued onto the first data row.
        if (head and not _HAS_DIGIT.search(head) and nxt
                and re.match(r"^[a-zà-ÿ]", nxt) and _HAS_DIGIT.search(nxt)):
            merged = f"{head} {nxt}"
            if (tail and not _HAS_DIGIT.search(tail)
                    and re.match(r"^[a-zà-ÿ]", tail) and len(tail.split()) <= 4):
                merged = re.sub(r"(\D)\s+(?=[\d(])",
                                lambda m: f"{m.group(1)} {tail} ", merged, count=1)
                i += 1
            out.append(merged)
            i += 2
            continue
        out.append(head)
        i += 1
    return out


# --------------------------------------------------------------------------
# Dating
# --------------------------------------------------------------------------

def _resolve_period(pages: list[str], cfg: dict) -> tuple[str, str]:
    for pat in cfg.get("period_patterns", []):
        for text in pages:
            m = re.search(pat, text, re.I)
            if m:
                got = C.parse_period(m.group(1))
                if got:
                    return got, m.group(1).strip()
    fixed = cfg.get("period")
    if fixed:
        return str(fixed), cfg.get("reference_period", str(fixed))
    raise ValueError(
        "could not date this report: no `period_patterns` matched and the "
        "layout sets no fixed `period`. Refusing to guess -- a wrongly dated "
        "series is worse than a missing one.")


def _column_periods(lines: list[str], spec: dict,
                    where: str) -> tuple[list[tuple[str, str]] | None, int | None]:
    """Periods printed across a table's header, in column order, and the index
    of the header line -- which is never read as data: "ISIC High level 2019
    2020 ... 2025" otherwise scans as an industry whose shares are years.

    Returns (None, None) when the region has no such header. The caller skips
    the region rather than failing, because a caption repeated in a list of
    tables WITHOUT dot leaders (NBS Seychelles, NBS Tanzania) opens a region
    holding nothing; a real table that lost its header still fails, on
    `expect_rows`.
    """
    pat = spec.get("period_header")
    if not pat:
        return None, None
    need = spec.get("period_count")
    # A header may label its columns in a form no general parser should be
    # asked to guess: ESS Ethiopia heads four survey rounds "Mar-99 Mar-05
    # Jun-13 Feb-21". `period_map` states what each means, rather than the
    # engine inventing a century for "99".
    pmap = spec.get("period_map", {})
    rx = re.compile(pat, re.I)
    for n, ln in enumerate(lines):
        hits = [m.group(0).strip() for m in rx.finditer(ln)]
        if hits and (len(hits) == need if need else len(hits) >= 2):
            periods = [C.parse_period(pmap.get(h, h)) for h in hits]
            if None in periods:
                raise ValueError(f"{where}: unreadable period in header {hits}")
            return list(zip(periods, hits)), n
    return None, None


# --------------------------------------------------------------------------
# The reader
# --------------------------------------------------------------------------

def make_parser(cfg: dict) -> Callable[[str], pd.DataFrame]:
    """Build a `parse(path) -> DataFrame` for one country's report layout."""

    def parse(path: str) -> pd.DataFrame:
        decimal = cfg.get("decimal", ".")
        mode = cfg.get("text_mode", "text")
        barrier_re = (re.compile(cfg["barrier_pattern"], re.I)
                      if cfg.get("barrier_pattern") else None)
        pages = _pages(path, cfg.get("split_columns", 1), mode,
                       cfg.get("min_nums", 2), barrier_re)
        if not any(p.strip() for p in pages):
            raise ValueError(
                f"{path}: no extractable text. This is a scanned/image PDF -- "
                f"it needs OCR, not a text parser. Do not 'fix' this by "
                f"loosening the patterns.")
        period, reference = _resolve_period(pages, cfg)
        base = os.path.basename(path)

        rows: list[dict] = []
        for spec in cfg["tables"]:
            cols = spec["columns"]
            n_cols = len(cols)
            scan = spec.get("row_scan", {})
            label_re = re.compile(
                scan.get("label", r"^([A-Za-zÀ-ſ][^\d]{2,80}?)\s+(?=[\d(-])"))
            ok_re = re.compile(scan.get("label_ok", r"^[A-Za-zÀ-ſ]"))
            drop_re = re.compile(scan.get("exclude_lines", r"…|\.{4,}"))
            exclude = set(scan.get("exclude_labels", ()))
            keep_dash = spec.get("dash_placeholder", False)
            # Whether a space groups thousands. True everywhere except a
            # French table of percentages, where "100 100 100" is three values.
            space_th = spec.get("space_thousands", cfg.get("space_thousands", True))
            label_map = spec.get("label_map", {})
            blocks = [(re.compile(b["match"]), b.get("set", {}), b.get("name", b["match"]))
                      for b in spec.get("blocks", ())]
            tag = spec.get("series_code", spec["topic"])
            where = f"{base} [{tag}]"

            scoped = _select(pages, spec)
            if not scoped:
                raise ValueError(
                    f"{where}: no page matched "
                    f"{spec.get('caption') or spec.get('page_contains')}")

            seen: set[str] = set()
            found = 0
            regions = 0
            headerless = 0
            for text in scoped:
                for src in _regions(text.splitlines(), spec, drop_re):
                    regions += 1
                    if spec.get("split_digit_repair"):
                        src = [_repair_split_digits(ln) for ln in src]
                    if spec.get("join_wrapped_labels", mode == "text"):
                        src = _rejoin_wrapped(src, decimal)
                    # SEVERAL SUB-TABLES CAN SHARE ONE PERIOD HEADER. ESS
                    # Ethiopia stacks occupation, industry and status blocks
                    # under a single "Mar-99 Mar-05 Jun-13 Feb-21" row, so a
                    # block's own region never contains it.
                    hdr_src = (text.splitlines()
                               if spec.get("period_header_scope") == "page" else src)
                    col_periods, header_at = _column_periods(hdr_src, spec, where)
                    if spec.get("period_header_scope") == "page":
                        header_at = None   # it is not a line of this region
                    if spec.get("period_header") and col_periods is None:
                        headerless += 1
                        continue
                    ctx: dict = {}
                    block = ""
                    for n, line in enumerate(src):
                        if n == header_at:
                            continue
                        stripped = line.strip()
                        if not stripped or drop_re.search(stripped):
                            continue
                        for rx, settings, name in blocks:
                            bm = rx.match(stripped)
                            if bm:
                                ctx, block = settings, name
                                stripped = stripped[bm.end():].strip()
                                break
                        m = label_re.match(stripped)
                        if not m:
                            continue
                        label = m.group(1).strip(" .:-–,")
                        if not ok_re.match(label) or label in exclude:
                            continue
                        # Numbers are counted from AFTER the label, so a digit
                        # that belongs to the category ("15-24 yrs", "ISIC 01")
                        # can never be read as data.
                        nums = C.numbers_in(stripped[m.end():], decimal=decimal,
                                            keep_dash=keep_dash,
                                            space_thousands=space_th)
                        if len(nums) != n_cols:
                            continue
                        # DEDUPE ON THE LABEL THAT WILL BE WRITTEN, not the raw
                        # text. Where a duplicated text layer splits a category
                        # across copies, `label_map` rejoins the halves -- and
                        # NSA Namibia's orphan half "professionals" collides
                        # case-insensitively with the real category
                        # "Professionals", so keying on the raw label dropped
                        # "Technicians and associate professionals" as a
                        # duplicate. Had the orphan been read first it would
                        # have won instead, publishing one category's figures
                        # under another's name.
                        char = label_map.get(label, label)
                        key = f"{block}|{char.lower()}"
                        if key in seen:
                            continue
                        seen.add(key)
                        found += 1

                        row_period, row_ref = period, reference
                        if spec.get("label_is_period"):
                            row_period, row_ref = C.parse_period(label), label
                            if not row_period:
                                raise ValueError(f"{where}: row label {label!r} is not a period")
                        # THE ROW LABEL IS A PLACE, not a category: a table of
                        # one measure broken down by region ("Proportion of
                        # informal employment by region and sex"). The columns
                        # then name the characteristic, and `geography_map`
                        # renames the published national row ("All regions") to
                        # the schema's own "Total country".
                        row_geo = None
                        if spec.get("label_is_geography"):
                            row_geo = spec.get("geography_map", {}).get(label, label)
                        # A TRANSPOSED TABLE: the categories run ACROSS the
                        # columns and the row label names the sex. CAPMAS
                        # Egypt's bulletin is laid out this way -- each column
                        # is an economic activity, each row a Male / Female /
                        # Total line within a region block.
                        row_sex = None
                        if spec.get("label_is_sex"):
                            row_sex = C.normalise_sex(label)

                        for cspec, val in zip(cols, nums):
                            if cspec.get("skip") or val is None:
                                continue
                            eff = {**cspec, **ctx}
                            p, ref = row_period, row_ref
                            if "period_index" in eff:
                                if col_periods is None:
                                    raise ValueError(
                                        f"{where}: a column sets period_index but the "
                                        f"table declares no period_header")
                                p, ref = col_periods[eff["period_index"]]
                            rows.append(C.row(
                                topic=spec["topic"],
                                characteristic=eff.get("characteristic") or char,
                                classification=spec["classification"],
                                value=val,
                                survey=cfg["survey"], period=p,
                                reference_period=ref,
                                frequency=cfg["frequency"],
                                measure=eff.get("measure", "count"),
                                unit=eff.get("unit", "persons"),
                                sex=eff.get("sex") or row_sex or "total",
                                age_group=eff.get("age_group", spec.get("age_group", "Total")),
                                education=eff.get("education", "Total"),
                                geography=(eff.get("geography") or row_geo
                                           or "Total country"),
                                locality=eff.get("locality", "all"),
                                locality_label=eff.get("locality_label", "Total"),
                                working_age_base=spec.get("working_age_base",
                                                          cfg["working_age_base"]),
                                series_code=tag,
                            ))

            if spec.get("caption") and not regions:
                raise ValueError(
                    f"{where}: caption {spec['caption']!r} is on a selected page "
                    f"but only in a table of contents")
            want = scan.get("expect_rows")
            if want and found < want:
                why = (f" {headerless} region(s) carried no period header."
                       if headerless else "")
                raise ValueError(
                    f"{where}: scanned {found} categories but the layout expects "
                    f"at least {want}.{why} Either the table changed or its "
                    f"caption no longer selects it -- re-read the PDF rather "
                    f"than lowering expect_rows.")

        if not rows:
            raise ValueError(
                f"{path}: not one configured table produced a row. Re-read the "
                f"current PDF and fix the layout in "
                f"parsers/<country>_labour.py before trusting any output.")
        return pd.DataFrame.from_records(rows)

    parse.__name__ = f"parse_{cfg.get('survey', 'labour').lower().replace(' ', '_')}"
    return parse
