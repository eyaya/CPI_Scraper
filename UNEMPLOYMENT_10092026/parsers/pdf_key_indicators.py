"""Config-driven parser for LFS headline tables in PDF reports.

Thirty African LFS reports were read while building this. There is no single
table shape -- but there IS a single *model* that covers all of them:

    a table is a grid of ROW specs by COLUMN specs, and every cell inherits
    the union of its row's and its column's attributes.

That one idea absorbs every layout encountered:

* **Nigeria NLFS** -- rows are indicators, columns are (sex x residence):
  rows carry `topic`, columns carry `sex` and `locality`.
* **Sierra Leone SLLFS** -- the transpose: rows are population groups, columns
  are indicators. Columns carry `topic`, rows carry `geography`/`sex`.
* **Rwanda annual LFS** -- rows are indicators, columns are YEARS:
  rows carry `topic`, columns carry `period`.
* **Tanzania ILFS** -- one topic per table, rows are breakdown categories,
  columns are (year x area x sex): `topic` sits in the table's `defaults`.
* **Zimbabwe QLFS** -- a two-level `Number | Percent` header: the columns carry
  `measure` and `unit`, the rows carry `topic`.
* **Angola IEA** -- the SAME eleven row labels appear twice, once under a
  "População com 15 ou mais anos" heading and once under "18 ou mais anos".
  `blocks` re-scopes the rows that follow a heading, so the second block does
  not silently overwrite the first.

Attribute precedence is `defaults < block < row < column`. Column wins ties
because the column is the finer key in the common (indicator-rows) layout.

WHAT THIS PARSER DELIBERATELY WILL NOT DO
-----------------------------------------
Several NSOs publish their headline numbers only as INFOGRAPHICS or CHART DATA
LABELS with no table at all -- Senegal's ENES note, Burkina's ENSE bulletin,
Rwanda's quarterly bulletin, most of Uganda's LMS deck. Chart labels lose
trailing zeros ("80" for 80,0), carry no category names, and put the y-axis
tick sequence right next to the data. Scraping them positionally produces
numbers that look right and are wrong. Those sources are marked in their
descriptors as needing a bespoke parser or a different tier, and are not
bodged through here.
"""
from __future__ import annotations
import re
from typing import Callable

import pandas as pd

from . import _common as C

# Attributes a row / column / block spec may contribute to a cell.
_CELL_ATTRS = ("topic", "definition", "label", "sex", "age_group", "education",
               "geography", "locality", "locality_label", "period",
               "reference_period", "measure", "unit", "working_age_base",
               "series_code")


def _pages(path: str, split_columns: int = 1) -> list[str]:
    """Page text, optionally read one PRINTED COLUMN at a time.

    A leaflet laid out in columns is a trap for any line-based parser, because
    the extractor walks each line right across the page and splices unrelated
    columns together:

        Taux (en %) de chômage BIT (SU1) 15,4 11,7 9,4 1,6 6,1 Rural 93,3 96,7 94,9
        ^-- the unemployment table --------------------^ ^-- a different table --^

    Reading the trailing numbers off that line gives Cameroon an urban
    unemployment rate of 93.3%, which is really an informal-employment share
    from the column alongside. The values are wrong but individually plausible,
    so nothing downstream can catch it.

    `split_columns: 2` crops each page into vertical bands and extracts them
    separately, so a line never spans two columns. Cropping (rather than
    clustering words by x) keeps this predictable on the multi-band leaflets
    where a table itself has several numeric columns.
    """
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            if split_columns <= 1:
                out.append(page.extract_text() or "")
                continue
            width = float(page.width)
            for i in range(split_columns):
                band = page.crop((width * i / split_columns, 0,
                                  width * (i + 1) / split_columns,
                                  float(page.height)))
                out.append(band.extract_text() or "")
    return out


def _select(pages: list[str], spec: dict) -> list[str]:
    want = [t.lower() for t in spec.get("page_contains", [])]
    skip = [t.lower() for t in spec.get("page_excludes", [])]
    hits = []
    for text in pages:
        low = text.lower()
        if want and not all(t in low for t in want):
            continue
        if skip and any(t in low for t in skip):
            continue
        hits.append(text)
    return hits


def _resolve_period(pages: list[str], cfg: dict) -> tuple[str, str]:
    """Date the report from its own text where possible.

    Filename dating is not offered: `save_as` renames and opaque CMS URLs
    destroy it (DEVELOPER_GUIDE 10.6). Several reports state no fieldwork dates
    at all (Zimbabwe's QLFS, Eswatini's ILFS booklet), so those descriptors set
    a fixed `period` instead -- an explicit constant beats a lucky regex.
    """
    for pat in cfg.get("period_patterns", []):
        for text in pages:
            m = re.search(pat, text, re.I)
            if not m:
                continue
            # A pattern is meant to capture the whole period phrase in one
            # group, but fall back to the entire match when group(1) alone is
            # not parseable -- a layout that splits the quarter and the year
            # across two groups would otherwise silently fail to date.
            for raw in ([m.group(1)] if m.groups() else []) + [m.group(0)]:
                period = C.parse_period(raw)
                if period:
                    return period, raw.strip()
    fixed = cfg.get("period")
    if fixed:
        return fixed, cfg.get("reference_period", fixed)
    raise ValueError(
        "could not date this report: no `period_patterns` matched its text and "
        "the layout sets no fixed `period`. Refusing to guess -- a wrongly "
        "dated series is worse than a missing one.")


def _merge(*specs: dict) -> dict:
    out: dict = {}
    for s in specs:
        for k in _CELL_ATTRS:
            if k in s and s[k] is not None:
                out[k] = s[k]
    return out


def _emit(cell: dict, value: float, cfg: dict, period: str, reference: str,
          line: str) -> dict:
    topic = cell.get("topic")
    if not topic:
        raise ValueError(
            f"no `topic` for a cell on line {line!r}: put it in the table's "
            f"`defaults`, its row spec, or its column spec.")
    return C.row(
        topic=topic,
        definition=cell.get("definition", "not_applicable"),
        value=value,
        series_label=cell.get("label", topic),
        survey=cfg["survey"],
        period=cell.get("period", period),
        reference_period=cell.get("reference_period",
                                  cell.get("period", reference)),
        frequency=cfg["frequency"],
        working_age_base=cell.get("working_age_base", cfg["working_age_base"]),
        measure=cell.get("measure"), unit=cell.get("unit"),
        sex=cell.get("sex", "total"),
        age_group=cell.get("age_group", "Total"),
        education=cell.get("education", "Total"),
        geography=cell.get("geography", "Total country"),
        locality=cell.get("locality", "all"),
        locality_label=cell.get("locality_label", "Total"),
        series_code=cell.get("series_code", ""),
    )


_NUMS_ONLY = re.compile(r"^[\s\d.,%()\-–]+$")
_HAS_DIGIT = re.compile(r"\d")


_SPACED_DECIMAL = re.compile(r"(?<=\d)\s+\.\s+(?=\d)")
_SPACED_LEAD = re.compile(r"(?:(?<=\s)|^)(\d)\s+(\d+\.\d)")


def _despace_numbers(line: str) -> str:
    """Rejoin a number whose own digits were letter-spaced by the renderer.

    NSA Namibia's Table 0.1 justifies some cells character by character, so the
    unemployment rate arrives as

        Unemployment Rate 3 6 . 9 34.6 39.6 36.4 38.0
        CRUPLF 5 4 . 8 5 0 . 6 5 9 . 0 4 8 . 7 6 3 . 6

    Counted naively that first row holds EIGHT numbers (3, 6, 9, 34.6, ...)
    instead of five, and CRUPLF holds fifteen. Raising pdfplumber's
    `x_tolerance` does not help: the gaps are real in the glyph positions.

    Two passes, both narrow: close the gaps either side of a decimal point,
    then join a LEFT-OVER SINGLE DIGIT to the decimal number that follows it.
    The second pass is the risky one -- it would also join a row number to its
    first value -- so this is opt-in per layout via `despace_numbers`, and only
    for tables whose labels carry no bare single digits.
    """
    line = _SPACED_DECIMAL.sub(".", line)
    prev = None
    while prev != line:                    # "5 4.8 5 0.6" needs two passes
        prev = line
        line = _SPACED_LEAD.sub(r"\1\2", line)
    return line


def _rejoin_wrapped(lines: list[str], decimal: str = ".") -> list[str]:
    """Rebuild rows whose LABEL wraps around its own numbers.

    A narrow indicator column makes the renderer emit three lines where the
    report shows one:

        Time related underemployment
        26.8 23.7 31.2 31.7 29.4 32.6 36.1
        rate(%)

    The label's head and tail sit either side of the data. Matching
    "^Time related underemployment rate" therefore hits a line with no numbers
    on it, and the numeric line has no label -- so the row is dropped in
    silence. Rwanda's seven-year trend table loses time-related
    underemployment, LU4 and female unemployment exactly this way.

    A tail line is only folded back when the line AFTER it is not itself a
    bare numeric line. That is what separates a continuation from the start of
    the next row: a real next row is a label followed by numbers, whereas
    "rate(%)" is followed by the next label, which is followed by ITS numbers.
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
            # A TAIL MAY CARRY A DIGIT OF ITS OWN -- HCP Morocco wraps
            # "Population active agee de / <numbers> / 15 ans et plus (en
            # milliers)" -- so "has no digits" is the wrong test. What
            # separates a continuation from the NEXT DATA ROW is how many
            # numbers it holds: a fragment carries at most one (a unit or an
            # age bound), a data row carries the whole series. Rwanda's
            # "Indicators" header sits directly above
            # "Labour force participation rate(%) 53.4 56.4 54 ...", and
            # folding that in as a tail destroyed the participation series.
            if (tail and len(C.numbers_in(tail, decimal=decimal)) <= 1
                    and len(tail.split()) <= 8
                    and not (after and _NUMS_ONLY.match(after)
                             and len(C.numbers_in(after,
                                                  decimal=decimal)) >= 2)):
                out.append(f"{head} {tail} {nxt}")
                i += 3
                continue
            out.append(f"{head} {nxt}")
            i += 2
            continue
        out.append(head)
        i += 1
    return out


def _parse_table(pages: list[str], cfg: dict, tbl: dict,
                 period: str, reference: str) -> tuple[list[dict], set[int]]:
    decimal = cfg.get("decimal", ".")
    columns = tbl["columns"]
    defaults = tbl.get("defaults", {})
    take = tbl.get("take", "leading")
    once = tbl.get("first_match_only", True)
    blocks = tbl.get("blocks", [])

    scoped = _select(pages, tbl) or pages
    rows: list[dict] = []
    matched: set[int] = set()
    seen: set[tuple] = set()          # (row index, block index) already taken
    block_i, block = -1, {}
    # Whether the current block has yielded a data row yet. A block
    # heading that WRAPS continues onto a second wordless line before
    # any numbers; a genuinely new heading only appears after them.
    block_has_data = False

    # Some headline tables NUMBER their indicator rows, so every line reads
    # "1 Population (15 years and above) 1,611,892 ..." and a `^Population`
    # pattern matches nothing at all. `strip_row_number` removes that index
    # from BOTH the text and the numbers, once, at the top of the loop --
    # rather than leaving every row spec to remember a `drop_leading: 1` that
    # is easy to apply to some rows and forget on others.
    row_no = re.compile(r"^\d{1,2}\s+(?=[A-Za-zÀ-ÿ])") if tbl.get("strip_row_number") else None

    for text in scoped:
        src = text.splitlines()
        if tbl.get("join_wrapped_labels"):
            src = _rejoin_wrapped(src, decimal)
        for line in src:
            stripped = line.strip()
            if tbl.get("despace_numbers"):
                stripped = _despace_numbers(stripped)
            if not stripped:
                continue
            if row_no is not None:
                stripped = row_no.sub("", stripped, count=1)

            # A block heading re-scopes every row that follows it. Checked
            # first so a heading that also carries numbers (Angola's
            # "População com 15 ou mais anos") still switches context.
            matched_block = False
            for bi, b in enumerate(blocks):
                if re.search(b["match"], stripped, re.I):
                    block_i, block, matched_block = bi, b, True
                    block_has_data = False
                    break
            # A BLOCK ENDS AT THE NEXT HEADING, not at the end of the page.
            # INS Niger's recap table prints "Taux de sous-utilisation de la
            # main oeuvre (%)" TWICE -- once over its sex rows, once over its
            # age rows -- and then moves on to "Duree moyenne de chomage (en
            # annees)", which is not a declared block. With the block left
            # open, that table's "Ensemble 5,24 ... 6,65" was read as a
            # sous-utilisation RATE: 6.65 years published as 6.65 per cent.
            # Opt-in, because a table whose rows are separated by stray
            # non-numeric lines would otherwise close its own block early.
            if (tbl.get("block_ends_on_heading") and not matched_block
                    and block and block_has_data
                    and not _HAS_DIGIT.search(stripped)
                    and len(stripped.split()) >= 2):
                block_i, block, block_has_data = -1, {}, False

            for ri, rspec in enumerate(tbl["rows"]):
                key = (ri, block_i)
                if once and key in seen:
                    continue
                if rspec.get("block") is not None and rspec["block"] != block.get("id"):
                    continue
                if rspec.get("exclude") and re.search(rspec["exclude"], stripped, re.I):
                    continue
                if not re.search(rspec["match"], stripped, re.I):
                    continue
                # A row, then its block, may override the table's column set --
                # Zimbabwe's strict block is `Number | Percent` while its
                # expanded block is `Percent` alone, on the same page.
                cols = rspec.get("columns") or block.get("columns") or columns
                nums = C.numbers_in(stripped, decimal=decimal)
                # Digits inside the label ("Youth (19-34 years)", "15 ou mais
                # anos", "(SU1)") are numbers too. `drop_leading` /
                # `drop_trailing` trim them; `take: trailing` handles the common
                # case where the label's digits all precede the data.
                if rspec.get("drop_leading"):
                    nums = nums[rspec["drop_leading"]:]
                if rspec.get("drop_trailing"):
                    nums = nums[:-rspec["drop_trailing"]]
                if len(nums) < len(cols):
                    # Sparse rows are real: Morocco prints only 3 of 5 cells on
                    # its "selon le sexe" sub-rows. Skipping beats guessing
                    # which cells are missing and shifting everything left.
                    continue
                rtake = rspec.get("take") or block.get("take") or take
                picked = nums[-len(cols):] if rtake == "trailing" \
                    else nums[:len(cols)]
                for cspec, value in zip(cols, picked):
                    if cspec.get("skip"):
                        # A column the NSO publishes that has no home in our
                        # topic vocabulary (Sierra Leone's "Unemployed (Broad)"
                        # is a share of the working-age population, not a rate).
                        # Held as a placeholder so the positional map stays
                        # honest rather than silently shifting.
                        continue
                    cell = _merge(defaults, block, rspec, cspec)
                    rows.append(_emit(cell, value, cfg, period, reference,
                                      stripped))
                seen.add(key)
                block_has_data = True
                matched.add(ri)
                break                  # one row spec per line

    return rows, matched


def make_parser(cfg: dict) -> Callable[[str], pd.DataFrame]:
    """Build a `parse(path) -> DataFrame` for one country's PDF layout.

    `cfg` carries the source-wide settings (`survey`, `frequency`,
    `working_age_base`, `decimal`, `period` / `period_patterns`) plus a
    `tables` list; each table has `page_contains`, `rows`, `columns` and
    optionally `defaults`, `blocks`, `take` and `first_match_only`.
    A single-table layout may put `rows`/`columns` at the top level instead.
    """
    tables = cfg.get("tables") or [cfg]
    # A few options describe the DOCUMENT, not one table in it: a report whose
    # renderer wraps one label wraps them throughout. Setting them once at the
    # layout level and letting each table inherit keeps a country from
    # declaring the same flag five times and missing the sixth.
    for _inherited in ("join_wrapped_labels", "strip_row_number",
                       "despace_numbers"):
        if _inherited in cfg:
            for _tbl in tables:
                _tbl.setdefault(_inherited, cfg[_inherited])

    def parse(path: str) -> pd.DataFrame:
        pages = _pages(path, cfg.get("split_columns", 1))
        if not pages or not any(p.strip() for p in pages):
            raise ValueError(
                f"{path}: no extractable text. This is a scanned/image PDF -- "
                f"it needs OCR, not a text parser. Do not 'fix' this by "
                f"loosening the regexes.")
        period, reference = _resolve_period(pages, cfg)

        rows: list[dict] = []
        misses: list[str] = []
        for t, tbl in enumerate(tables):
            got, matched = _parse_table(pages, cfg, tbl, period, reference)
            rows.extend(got)
            for ri, rspec in enumerate(tbl["rows"]):
                if ri not in matched:
                    misses.append(f"table[{t}].{rspec['match']!r}")

        if not rows:
            raise ValueError(
                f"{path}: not one configured row matched. The report's layout "
                f"has changed -- re-read the current PDF and fix the layout in "
                f"parsers/<country>_unemployment.py before trusting any output.")
        if misses:
            # Loud but non-fatal. A partial capture is acceptable when it is
            # visible; a silent one never is.
            print(f"[pdf_key_indicators] {path}: no match for "
                  f"{len(misses)} row spec(s): {misses[:8]}"
                  + (" ..." if len(misses) > 8 else ""))
        return pd.DataFrame.from_records(rows)

    parse.__name__ = f"parse_{cfg.get('survey', 'pdf').lower().replace(' ', '_')}"
    return parse
