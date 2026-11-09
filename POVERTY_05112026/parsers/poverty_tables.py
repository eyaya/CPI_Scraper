"""Config-driven parser for monetary-poverty tables in NSO reports.

Adapted from `mpi/parsers/mpi_tables.py`, because poverty profiles print the
same shape: rows are POPULATION GROUPS (milieu, regions, a characteristic of the
household head), columns are METRICS -- and often a metric per locality or per
survey year:

    Milieu de        Ratio de pauvreté  Gap de pauvreté  Sévérité   Population
    résidence          P0     CTR         P1     CRT     P2   CRT   Effectif Part
    Abidjan urbain    7,0%   3,9%        1,6%   3,3%    0,5% 2,8%  6 217 509 20,9%

Every cell inherits the union of the layout, the table's `defaults`, its row
spec and its column spec (column wins). A column may carry `period`, `survey`,
`locality`, `line_level` ... so a "2011 | 2018/19" or "Rural | Urbain | Total"
header is one column spec per printed column.

--- The layout dict -------------------------------------------------------

    survey, welfare_aggregate, unit_of_analysis, frequency, decimal
    line_type, line_level, line_name, line_value, line_unit   -- the default line
    period / reference_period, or period_patterns
    percent_cells      cells carry their own "%" (see _common.numbers_in)
    tables             list of table specs, each:
        page_contains / page_excludes   page selection, lowercased substrings
        half           "left" | "right": read only that half of each page.
                       Some profiles (ANStat 2021) print TWO-UP spreads whose
                       text layer interleaves two tables line by line.
        start / end    line regexes bounding the block read on each page (the
                       start line itself is not data unless `start_inclusive`).
                       Blocks stacked under one header ("Sexe du CM", then
                       "Alphabétisation du CM", each with Non/Oui/Total) are
                       separate tables with their own start/end.
        columns        positional meaning of the numbers on a row
        rows           row specs ({match, exclude, ...attrs}) or
        row_scan       enumerate rows (regions) -- see mpi_tables._scan_rows
        defaults, take ("leading"|"trailing"), exact_numbers

WHAT THIS PARSER WILL NOT DO: recompute P1 from P0, derive a count from a
rate, convert a 0-1 gap to percent, or read a value off a chart.
"""
from __future__ import annotations
import re
from typing import Callable

import pandas as pd

from . import _common as C

_CELL_ATTRS = ("metric", "unit", "topic", "characteristic", "sex", "age_group",
               "geography", "locality", "locality_label", "label", "period",
               "reference_period", "survey", "welfare_aggregate",
               "unit_of_analysis", "line_type", "line_level", "line_name",
               "line_value", "line_unit", "series_code")
_LAYOUT_DEFAULTS = ("survey", "welfare_aggregate", "unit_of_analysis",
                    "line_type", "line_level", "line_name", "line_value",
                    "line_unit")


def _pages(path: str, halves: bool = True) -> dict[str, list[str]]:
    """Each page's text three ways: whole, left half, right half.

    ONLY TEXT INSIDE THE PAGE BOX IS READ. ANStat's 2021 profile carries, on
    every other page, the PREVIOUS page's content placed off-page at negative
    x -- invisible in a viewer, but `extract_text()` returns it, interleaving
    two tables line by line (Tableau 3-2's regions beside 3-3's). Cropping to
    the page's own bbox drops it.
    """
    import pdfplumber
    out: dict[str, list[str]] = {"full": [], "left": [], "right": []}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            w, h = page.width, page.height
            page = page.crop((0, 0, w, h))
            out["full"].append(page.extract_text() or "")
            # Halves only when some table asks for one: extracting every page
            # three times made a 400-page report take minutes to parse.
            if halves:
                out["left"].append(page.crop((0, 0, w / 2, h)).extract_text() or "")
                out["right"].append(page.crop((w / 2, 0, w, h)).extract_text() or "")
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


def _block(lines: list[str], tbl: dict) -> list[str]:
    """The lines between `start` and `end` (first occurrence on the page)."""
    if not tbl.get("start"):
        return lines
    out, inside = [], False
    for ln in lines:
        if not inside:
            if re.search(tbl["start"], ln, re.I):
                inside = True
                if tbl.get("start_inclusive"):
                    out.append(ln)
            continue
        if tbl.get("end") and re.search(tbl["end"], ln, re.I):
            if tbl.get("end_inclusive"):
                out.append(ln)
            break
        out.append(ln)
    return out


def _resolve_period(pages: list[str], cfg: dict) -> tuple[str, str]:
    """Date the survey. A poverty profile's cover year, upload folder and
    survey year routinely differ (the EHCVM 2018/19 reports appeared in 2020-21),
    so `period` is normally pinned per country, never read from a URL."""
    for pat in cfg.get("period_patterns", []):
        for text in pages:
            m = re.search(pat, text, re.I)
            if m:
                raw = m.group(1) if m.groups() else m.group(0)
                y = re.search(r"\b(19\d{2}|20\d{2})\b", raw)
                if y:
                    return y.group(1), raw.strip()
    if cfg.get("period"):
        return str(cfg["period"]), cfg.get("reference_period", str(cfg["period"]))
    raise ValueError("could not date this survey: set `period` in the layout -- "
                     "a poverty rate dated to its publication year is silently wrong")


def _merge(*specs: dict) -> dict:
    out: dict = {}
    for s in specs:
        for k in _CELL_ATTRS:
            if k in s and s[k] is not None:
                out[k] = s[k]
    return out


def _characteristic(cell: dict) -> str:
    explicit = cell.get("characteristic") or cell.get("label")
    if explicit:
        return explicit
    if cell.get("topic") == "locality":
        return cell.get("locality_label") or "Total"
    return "Total"


def _emit(cell: dict, value: float, cfg: dict, period: str, reference: str, line: str) -> dict:
    if not cell.get("metric"):
        raise ValueError(f"no `metric` for a cell on line {line!r}")
    for k in ("survey", "welfare_aggregate", "line_type", "line_level", "line_name"):
        if not cell.get(k) and not cfg.get(k):
            raise ValueError(f"no `{k}` for a cell on line {line!r}: a poverty "
                             f"rate cannot be interpreted without its line and survey")
    return C.row(
        metric=cell["metric"], value=value,
        survey=cell.get("survey", cfg.get("survey")),
        welfare_aggregate=cell.get("welfare_aggregate", cfg.get("welfare_aggregate", "consumption")),
        unit_of_analysis=cell.get("unit_of_analysis", cfg.get("unit_of_analysis", "person")),
        line_type=cell.get("line_type", cfg.get("line_type", "national")),
        line_level=cell.get("line_level", cfg.get("line_level", "overall")),
        line_name=cell.get("line_name", cfg.get("line_name")),
        line_value=cell.get("line_value", cfg.get("line_value", "")),
        line_unit=cell.get("line_unit", cfg.get("line_unit", "")),
        unit=cell.get("unit"),
        period=cell.get("period", period),
        reference_period=cell.get("reference_period",
                                  reference if "period" not in cell else cell["period"]),
        frequency=cfg.get("frequency", "ad_hoc"),
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
    """A label-only line followed by a bare numeric line, and a numeric row
    followed by the tail of its own label (CIV: "Quatorze personnes" /
    "70,6% ..." / "et plus"), are re-joined. Opt-in per table."""
    cont = re.compile(r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\- ]{0,23}\.?$")
    merged: list[str] = []
    prev: str | None = None
    for raw in lines:
        s = raw.strip()
        if not s:
            prev = None
            continue
        if re.match(r"^[\d(,]", s) and prev:
            merged[-1] = f"{prev} {s}"
            prev = None
            continue
        merged.append(s)
        prev = s if not re.search(r"\d", s) else None
    out: list[str] = []
    i = 0
    while i < len(merged):
        s = merged[i]
        nxt = merged[i + 1] if i + 1 < len(merged) else ""
        head = re.match(r"^([A-Za-zÀ-ÿ][^\d]*?)\s+(?=[\d(,])", s)
        if head and nxt and not re.search(r"\d", nxt) and len(nxt.split()) <= 3 and cont.match(nxt):
            out.append(f"{head.group(1).strip()} {nxt.strip()} {s[head.end():]}")
            i += 2
            continue
        out.append(s)
        i += 1
    return out


def _lines(text: str, tbl: dict) -> list[str]:
    src = [l.strip() for l in text.splitlines()]
    src = _block(src, tbl)
    return _join_wrapped(src) if tbl.get("join_wrapped_labels") else src


def _scan_rows(lines, tbl, cfg):
    """Enumerate a table's rows (31 regions) without a spec per row. Fenced:
    the table must scope itself, the number count must match EXACTLY, and
    `expect_rows` must be declared (see mpi_tables._scan_rows)."""
    spec = tbl["row_scan"]
    label_re = re.compile(spec.get("label", r"^([^\d]{2,60}?)\s+(?=[\d(,-])"))
    ok_re = re.compile(spec.get("label_ok", r"^[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’\-\.\/ ]+$"))
    drop_re = re.compile(spec.get("exclude_lines", r"…|\.{4,}"))
    n = len(tbl["columns"])
    attr = spec.get("attr", "geography")
    found, seen = [], set()
    for line in lines:
        if drop_re.search(line):
            continue
        m = label_re.match(line)
        if not m:
            continue
        nums = C.numbers_in(line[m.end():], decimal=cfg.get("decimal", "."),
                            percent_cells=cfg.get("percent_cells", False))
        if len(nums) != n:
            continue
        label = m.group(1).strip(" .:-–")
        if not ok_re.match(label) or label.lower() in seen or label in spec.get("exclude_labels", ()):
            continue
        seen.add(label.lower())
        mapped = spec.get("label_map", {}).get(label, label)
        extra = spec.get("row_attrs", {}).get(label, {})
        found.append((line, {attr: mapped, "_nums": nums, **spec.get("defaults", {}), **extra}))
    return found


def _parse_table(pages: dict[str, list[str]], cfg: dict, tbl: dict,
                 period: str, reference: str) -> tuple[list[dict], set[int]]:
    decimal = cfg.get("decimal", ".")
    pct = cfg.get("percent_cells", False)
    columns = tbl["columns"]
    defaults = tbl.get("defaults", {})
    take = tbl.get("take", "leading")
    # Pages are SELECTED on the whole page (a caption sits wherever it sits)
    # but READ from the requested half.
    full = pages["full"]
    texts = pages.get(tbl.get("half", "full"))
    idx = [i for i, t in enumerate(full) if _select([t], tbl)]
    scoped = [texts[i] for i in idx]
    if not scoped and (tbl.get("page_contains") or tbl.get("page_excludes")):
        print(f"[poverty_tables] no page matched page_contains="
              f"{tbl.get('page_contains')!r}; table skipped")
    rows: list[dict] = []
    matched: set[int] = set()

    if tbl.get("row_scan"):
        lines = [l for t in scoped for l in _lines(t, tbl)]
        hits = _scan_rows(lines, tbl, cfg)
        want = tbl["row_scan"]["expect_rows"]
        if len(hits) < want:
            raise ValueError(
                f"row_scan found {len(hits)} row(s) but the layout expects at "
                f"least {want} -- re-read the PDF rather than lowering expect_rows")
        for line, rspec in hits:
            nums = rspec.pop("_nums")
            for cspec, value in zip(columns, nums):
                if not cspec.get("skip"):
                    rows.append(_emit(_merge(defaults, rspec, cspec), value, cfg, period, reference, line))
        return rows, set(range(len(tbl.get("rows", []))))

    seen: set[int] = set()
    for text in scoped:
        for line in _lines(text, tbl):
            if not line:
                continue
            for ri, rspec in enumerate(tbl["rows"]):
                if ri in seen:
                    continue
                if rspec.get("exclude") and re.search(rspec["exclude"], line, re.I):
                    continue
                lm = re.search(rspec["match"], line, re.I)
                if not lm:
                    continue
                cols = rspec.get("columns") or columns
                # Numbers are read AFTER the matched label, so digits inside a
                # label ("Secondaire 1", "26 à 30 ans") never land in the data.
                nums = C.numbers_in(line[lm.end():], decimal=decimal, percent_cells=pct)
                if tbl.get("exact_numbers") and len(nums) != len(cols):
                    continue
                if len(nums) < len(cols):
                    continue      # a sparse row is skipped, never shifted left
                picked = nums[-len(cols):] if (rspec.get("take") or take) == "trailing" else nums[:len(cols)]
                for cspec, value in zip(cols, picked):
                    if not cspec.get("skip"):
                        rows.append(_emit(_merge(defaults, rspec, cspec), value, cfg, period, reference, line))
                seen.add(ri)
                matched.add(ri)
                break
    return rows, matched


def make_parser(cfg: dict) -> Callable[[str], pd.DataFrame]:
    """Build a `parse(path) -> DataFrame` for one country's poverty report."""
    tables = cfg.get("tables") or [cfg]

    def parse(path: str) -> pd.DataFrame:
        pages = _pages(path, halves=any(t.get("half") for t in tables))
        if not any(p.strip() for p in pages["full"]):
            raise ValueError(f"{path}: no extractable text (scanned PDF) -- needs OCR, "
                             f"which this project does not do")
        period, reference = _resolve_period(pages["full"], cfg)
        rows: list[dict] = []
        misses: list[str] = []
        for t, tbl in enumerate(tables):
            got, matched = _parse_table(pages, cfg, tbl, period, reference)
            rows.extend(got)
            for ri, rspec in enumerate(tbl.get("rows", [])):
                if ri not in matched:
                    misses.append(f"table[{t}].{rspec['match']!r}")
        if not rows:
            raise ValueError(f"{path}: not one configured row matched -- the layout "
                             f"has changed; re-read the PDF")
        if misses:
            print(f"[poverty_tables] {path}: no match for {len(misses)} row spec(s): "
                  f"{misses[:8]}" + (" ..." if len(misses) > 8 else ""))
        if cfg.get("strict_rows") and misses:
            raise ValueError(f"{len(misses)} row spec(s) matched nothing: {misses[:8]}")
        return pd.DataFrame.from_records(rows)

    return parse
