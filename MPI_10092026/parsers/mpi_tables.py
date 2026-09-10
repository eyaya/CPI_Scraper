"""Config-driven parser for MPI tables in NSO reports.

Seventeen African MPI reports were read while building this, and their headline
tables converge on ONE shape far more tightly than labour-force reports do:

    rows are POPULATION GROUPS (national, urban, rural, regions, sex of the
    household head), and columns are METRICS (H, A, M0, and sometimes
    population share, vulnerable, severe).

    Row / Group            H (%)    A (%)     MPI
    National                46.6     69.4    0.323
    Urbain                  21.4     67.9    0.146
    Rural                   54.4     69.5    0.379

So the topic lives in the COLUMNS and the disaggregation in the ROWS — the
transpose of the usual labour-force layout. A second, smaller shape appears for
the per-indicator tables (contributions, censored headcounts), where the rows
are deprivation indicators and there is a single value column.

Both are expressed with the same row-by-column cell model: every cell inherits
the union of its table's `defaults`, its row spec and its column spec, with the
column winning ties.

--- The layout dict -------------------------------------------------------

    mpi_type            national | global
    measure_name        the index's own published name ("SAMPI", "IPM-A", ...)
    survey              the source survey, e.g. "EICV7", "RGPH 2024"
    k_cutoff            the deprivation cutoff IN PERCENT (25, 33.3, 60, ...)
    n_dimensions        how many dimensions the measure uses
    n_indicators        how many indicators it uses
    unit_of_analysis    person | household
    frequency           annual | ad_hoc
    decimal             "." (EN) or "," (FR/PT/ES)
    period              the reference YEAR as YYYY
    reference_period    as published ("2015/16", "Census 2011")
    period_patterns     optional regexes to read the year from the document text
    tables              list of table specs, each:
        page_contains   ALL of these (lowercased) must appear on a page
        page_excludes   ANY of these on a page skips it
        columns         positional meaning of the numbers on a matched row;
                        each entry may set metric / unit / dimension /
                        mpi_indicator / sex / locality / ... or {"skip": True}
        rows            the population groups (or indicators) to capture
        defaults        attributes every cell in the table inherits
        take            "leading" (default) or "trailing"
        first_match_only  default True

Row specs may carry `drop_leading` / `drop_trailing` to discard digits that are
part of the LABEL rather than the data ("Youth (15-35)", "15 ou mais anos"), and
`exclude` to prevent substring collisions.

WHAT THIS PARSER WILL NOT DO
----------------------------
Madagascar's MPI is published as a four-page infographic and Morocco's headline
M0 is printed as a percentage on a census cartography. Neither is bent to fit:
Madagascar carries a small explicit layout for its headline block only, and
Morocco declares `unit: percent` on its M0 column rather than being rescaled.
Nothing here recomputes H x A, converts a percentage to a decimal, or derives a
national figure from sub-national rows.
"""
from __future__ import annotations
import re
from typing import Callable

import pandas as pd

from . import _common as C

_CELL_ATTRS = ("metric", "unit", "dimension", "mpi_indicator", "topic",
               "characteristic", "sex", "age_group", "geography", "locality",
               "locality_label", "label", "period", "reference_period",
               "mpi_type", "measure_name", "survey", "k_cutoff",
               "n_dimensions", "n_indicators", "unit_of_analysis",
               "series_code")


def _pages(path: str) -> list[str]:
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
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
    """Date the measure from the document text where a pattern is given, else
    from the descriptor's fixed `period`.

    MPI reports make this unusually treacherous: the publication year, the
    cover date and the SURVEY REFERENCE year routinely all differ. Burkina's
    2019 index sits in a `/2024-10/` upload folder under a December 2023 cover;
    Mali's 2024-titled bulletin describes 2021-2022. So `period` is normally
    pinned explicitly per country and never inferred from a URL.
    """
    for pat in cfg.get("period_patterns", []):
        for text in pages:
            m = re.search(pat, text, re.I)
            if not m:
                continue
            for raw in ([m.group(1)] if m.groups() else []) + [m.group(0)]:
                y = re.search(r"\b(19\d{2}|20\d{2})\b", str(raw))
                if y:
                    return y.group(1), str(raw).strip()
    fixed = cfg.get("period")
    if fixed:
        return str(fixed), cfg.get("reference_period", str(fixed))
    raise ValueError(
        "could not date this measure: no `period_patterns` matched and the "
        "layout sets no fixed `period`. Refusing to guess -- an MPI dated to "
        "its publication year instead of its survey year is silently wrong.")


def _merge(*specs: dict) -> dict:
    out: dict = {}
    for s in specs:
        for k in _CELL_ATTRS:
            if k in s and s[k] is not None:
                out[k] = s[k]
    return out


def _characteristic(cell: dict) -> str:
    """The value of the row's disaggregating `topic`.

    A layout may state it outright; otherwise it is the row's own label. When
    neither exists the row is either undisaggregated -- "Total" -- or split by
    locality, where the locality column already carries the value and the two
    columns agree rather than one being blank.
    """
    explicit = cell.get("characteristic") or cell.get("label")
    if explicit:
        return explicit
    if cell.get("topic") == "locality":
        return cell.get("locality_label") or "Total"
    return "Total"


def _emit(cell: dict, value: float, cfg: dict, period: str, reference: str,
          line: str) -> dict:
    metric = cell.get("metric")
    if not metric:
        raise ValueError(
            f"no `metric` for a cell on line {line!r}: put it in the table's "
            f"`defaults`, its row spec, or its column spec.")
    return C.row(
        metric=metric, value=value,
        mpi_type=cell.get("mpi_type", cfg["mpi_type"]),
        survey=cell.get("survey", cfg["survey"]),
        measure_name=cell.get("measure_name", cfg["measure_name"]),
        k_cutoff=cell.get("k_cutoff", cfg["k_cutoff"]),
        n_dimensions=cell.get("n_dimensions", cfg["n_dimensions"]),
        n_indicators=cell.get("n_indicators", cfg["n_indicators"]),
        unit_of_analysis=cell.get("unit_of_analysis",
                                  cfg.get("unit_of_analysis", "person")),
        unit=cell.get("unit"),
        period=cell.get("period", period),
        reference_period=cell.get("reference_period", reference),
        frequency=cfg.get("frequency", "ad_hoc"),
        dimension=cell.get("dimension", "Total"),
        mpi_indicator=cell.get("mpi_indicator", "Total"),
        topic=cell.get("topic", "total"),
        characteristic=_characteristic(cell),
        sex=cell.get("sex", "total"),
        age_group=cell.get("age_group", "Total"),
        geography=cell.get("geography", "Total country"),
        locality=cell.get("locality", "all"),
        locality_label=cell.get("locality_label", "Total"),
        series_code=cell.get("series_code", ""),
    )


def _join_wrapped(lines: list[str]) -> list[str]:
    """Re-attach a row label that the PDF wrapped onto its own line.

    French and Portuguese MPI tables wrap long stratum names, and pdfplumber
    then emits the label and its numbers as two lines:

        Autres villes
        11,7 0,211 0,191 0,230 30,6 ...
        urbaines

    Botswana wraps the OTHER way -- the continuation word lands on the line
    AFTER the numbers, which is worse than untidy, it is ambiguous:

        Kweneng 13.34 1.02% 49.76 0.066 ...
        East
        Kweneng 50.34 5.33% 55.89 0.281 ...
        West

    Both rows begin "Kweneng", so without the following line there is no way to
    tell Kweneng East from Kweneng West, and five Central districts collide the
    same way. So a trailing label-only line is folded back into its row's
    label, giving "Kweneng West 50.34 ...".

    Both merges are narrow. The backward one fires only when the next line
    begins with a digit (the numeric line carries no label of its own); the
    forward one only when the following line is short, wordy and digit-free.
    A data row whose own label is numeric (a year, "2011 17,9 43,9 0,08") is
    therefore never merged -- and the whole behaviour is opt-in per table via
    `join_wrapped_labels` rather than being applied globally.
    """
    _CONT = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\- ]{0,23}\.?$")

    # Pass 1: a label-only line followed by a bare numeric line.
    merged: list[str] = []
    prev_label: str | None = None
    for raw in lines:
        s = raw.strip()
        if not s:
            prev_label = None
            continue
        if re.match(r"^[\d(]", s) and prev_label:
            merged.append(f"{prev_label} {s}")
            prev_label = None
            continue
        merged.append(s)
        prev_label = s if not re.search(r"\d", s) else None

    # Pass 2: a numeric row followed by the tail of its own label.
    out: list[str] = []
    i = 0
    while i < len(merged):
        s = merged[i]
        nxt = merged[i + 1] if i + 1 < len(merged) else ""
        head = re.match(r"^([A-Za-zÀ-ÿ][^\d]*?)\s+(?=[\d(])", s)
        if (head and nxt and not re.search(r"\d", nxt)
                and len(nxt.split()) <= 3 and _CONT.match(nxt)):
            label = head.group(1).strip()
            out.append(f"{label} {nxt.strip()} {s[head.end():]}")
            i += 2
            continue
        out.append(s)
        i += 1
    return out


def _scan_rows(lines: list[str], tbl: dict, decimal: str) -> list[tuple[str, dict]]:
    """Harvest an enumerated table (166 Mauritian wards, 45 Burkinabè
    provinces) without writing one row spec per row.

    A `row_scan` table names no rows. Instead every line on the selected pages
    that carries EXACTLY as many numbers as the table has columns, and whose
    leading text looks like a label, becomes a row -- the captured label going
    into the attribute `row_scan['attr']` (default `geography`).

    This is the one place the parser generalises over rows it has not been
    shown, so it is fenced in three ways: the table must scope itself with
    `page_contains`; the number count must match exactly, never merely reach
    the minimum; and the table must declare `expect_rows`, so a scan that
    quietly collects half a table fails loudly instead of shipping.
    """
    spec = tbl["row_scan"]
    label_re = re.compile(spec.get("label", r"^(?:\d{1,4}\s+)?([^\d]{2,60}?)\s+(?=[\d(])"))
    ok_re = re.compile(spec.get("label_ok", r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-\.\/ ]+$"))
    n = len(tbl["columns"])
    attr = spec.get("attr", "geography")

    # A table of contents is the scanner's natural enemy: "Quadro 2 - IPM-A,
    # incidência e intensidade, IIMS 2015-2016 ......... 28" carries a label,
    # four numbers and a page number, and looks exactly like a data row. Lines
    # holding leader dots are dropped by default.
    drop_re = re.compile(spec.get("exclude_lines", r"…|\.{4,}"))

    found: list[tuple[str, dict]] = []
    seen_labels: set[str] = set()
    for line in lines:
        if drop_re.search(line):
            continue
        m = label_re.match(line)
        if not m:
            continue
        # Numbers are counted and read from AFTER the label, so digits that
        # belong to the label never land in the data. Mauritius prefixes every
        # row with a four-digit geographical code and names thirty of its
        # areas "... Ward 5"; counting the whole line would give those rows one
        # number too many and drop them silently.
        if len(C.numbers_in(line[m.end():], decimal=decimal)) != n:
            continue
        label = m.group(1).strip(" .:-–")
        if not ok_re.match(label) or label.lower() in seen_labels:
            continue
        # `exclude_labels` drops a scanned row that another table in the same
        # layout already supplies in full -- Botswana's district table repeats
        # the national line that Table 3.4.1 gives with every metric.
        if label in spec.get("exclude_labels", ()):
            continue
        seen_labels.add(label.lower())
        # `label_map` renames the handful of scanned labels that are not
        # geographies -- a table's own "National"/"Total" line, which must
        # become "Total country" like every other national row in the file.
        mapped = spec.get("label_map", {}).get(label, label)
        # The label goes in the column the scan is FOR -- `attr`, normally
        # `geography`, and `mpi_indicator` for a table whose rows are the
        # indicators. It is deliberately NOT copied into `characteristic` as
        # well: `characteristic` names the value of the row's disaggregating
        # `topic`, and a district or an indicator already has its own column.
        # Copying it made Botswana, Burkina Faso and Mauritius repeat their
        # geography there while every enumerated-row country wrote "Total",
        # and made Angola file indicator names under a `locality` topic.
        found.append((line, {attr: mapped,
                             "_nums": C.numbers_in(line[m.end():],
                                                   decimal=decimal),
                             **{k: v for k, v in spec.get("defaults", {}).items()}}))
    return found


def _parse_table(pages: list[str], cfg: dict, tbl: dict,
                 period: str, reference: str) -> tuple[list[dict], set[int]]:
    decimal = cfg.get("decimal", ".")
    columns = tbl["columns"]
    defaults = tbl.get("defaults", {})
    take = tbl.get("take", "leading")
    once = tbl.get("first_match_only", True)

    scoped = _select(pages, tbl) or pages
    rows: list[dict] = []
    matched: set[int] = set()
    seen: set[int] = set()

    if tbl.get("row_scan"):
        lines: list[str] = []
        for text in scoped:
            src = text.splitlines()
            lines.extend(_join_wrapped(src) if tbl.get("join_wrapped_labels")
                         else [l.strip() for l in src])
        hits = _scan_rows(lines, tbl, decimal)
        want = tbl["row_scan"]["expect_rows"]
        if len(hits) < want:
            raise ValueError(
                f"row_scan found {len(hits)} row(s) on the selected pages but "
                f"the layout expects at least {want}. Either the report's "
                f"table changed or `page_contains` no longer selects it -- "
                f"re-read the PDF rather than lowering expect_rows.")
        for line, rspec in hits:
            nums = rspec.pop("_nums")
            for cspec, value in zip(columns, nums):
                if cspec.get("skip"):
                    continue
                cell = _merge(defaults, rspec, cspec)
                rows.append(_emit(cell, value, cfg, period, reference, line))
        return rows, set(range(len(tbl.get("rows", []))))

    for text in scoped:
        src = text.splitlines()
        if tbl.get("join_wrapped_labels"):
            src = _join_wrapped(src)
        for line in src:
            stripped = line.strip()
            if not stripped:
                continue
            for ri, rspec in enumerate(tbl["rows"]):
                if once and ri in seen:
                    continue
                if rspec.get("exclude") and re.search(rspec["exclude"], stripped, re.I):
                    continue
                if not re.search(rspec["match"], stripped, re.I):
                    continue
                cols = rspec.get("columns") or columns
                if tbl.get("leading_run"):
                    # Read ONLY the run of numbers that immediately follows the
                    # row's own label, stopping at the first word. Madagascar's
                    # MPI is a three-page infographic whose chart labels and
                    # body text share lines:
                    #
                    #   Sava 21,1 (21,1%), Analanjirofo (21,6%) et
                    #   Sava 63,4 46,1 0,292
                    #
                    # Counting every number on the first line would read the
                    # neighbouring sentence as Sava's H, A and MPI. Confining
                    # the read to the numeric run makes that line come up two
                    # numbers short, so it is skipped and the real table row is
                    # the one that matches.
                    lm = re.search(rspec["match"], stripped, re.I)
                    tail = stripped[lm.end():] if lm else stripped
                    run = re.match(r"^[\s\d.,%()\-–]+", tail)
                    nums = C.numbers_in(run.group(0) if run else "",
                                        decimal=decimal)
                else:
                    nums = C.numbers_in(stripped, decimal=decimal)
                if rspec.get("drop_leading"):
                    nums = nums[rspec["drop_leading"]:]
                if rspec.get("drop_trailing"):
                    nums = nums[:-rspec["drop_trailing"]]
                # `exact_numbers` disambiguates two tables printed on the SAME
                # page whose rows share labels -- Madagascar prints a severe
                # poverty chart (one number per region) directly above an
                # H | A | M0 table (three per region), and only the count of
                # numbers on the line tells the two apart.
                if tbl.get("exact_numbers") and len(nums) != len(cols):
                    continue
                if len(nums) < len(cols):
                    # A sparse row is skipped rather than shifted left. Several
                    # MPI tables leave a cell blank (a region with no estimate,
                    # a metric not computed for a stratum) and guessing which
                    # one is missing would silently mis-assign every value after
                    # it.
                    continue
                rtake = rspec.get("take") or take
                picked = nums[-len(cols):] if rtake == "trailing" else nums[:len(cols)]
                for cspec, value in zip(cols, picked):
                    if cspec.get("skip"):
                        continue
                    cell = _merge(defaults, rspec, cspec)
                    rows.append(_emit(cell, value, cfg, period, reference, stripped))
                seen.add(ri)
                matched.add(ri)
                break
    return rows, matched


def make_parser(cfg: dict) -> Callable[[str], pd.DataFrame]:
    """Build a `parse(path) -> DataFrame` for one country's MPI report."""
    tables = cfg.get("tables") or [cfg]

    def parse(path: str) -> pd.DataFrame:
        pages = _pages(path)
        if not pages or not any(p.strip() for p in pages):
            raise ValueError(
                f"{path}: no extractable text. This is a scanned/image PDF -- "
                f"it needs OCR, not a text parser (Mauritania's MPI brief is "
                f"one of these). Do not 'fix' this by loosening the regexes.")
        period, reference = _resolve_period(pages, cfg)

        rows: list[dict] = []
        misses: list[str] = []
        for t, tbl in enumerate(tables):
            got, matched = _parse_table(pages, cfg, tbl, period, reference)
            rows.extend(got)
            # A `row_scan` table has no row specs to miss; its own
            # `expect_rows` guard has already run inside _parse_table.
            for ri, rspec in enumerate(tbl.get("rows", [])):
                if ri not in matched:
                    misses.append(f"table[{t}].{rspec['match']!r}")

        if not rows:
            raise ValueError(
                f"{path}: not one configured row matched. The report's layout "
                f"has changed -- re-read the current PDF and fix the layout in "
                f"the country's parsers/<country>_mpi.py before trusting any output.")
        if misses:
            print(f"[mpi_tables] {path}: no match for {len(misses)} row "
                  f"spec(s): {misses[:8]}" + (" ..." if len(misses) > 8 else ""))
        return pd.DataFrame.from_records(rows)

    parse.__name__ = f"parse_{cfg.get('measure_name', 'mpi').lower().replace(' ', '_')}"
    return parse
