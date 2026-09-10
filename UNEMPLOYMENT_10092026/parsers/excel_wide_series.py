"""Config-driven parser for a WIDE Excel labour time series.

The Tier-2 shape (DEVELOPER_GUIDE 7.5): rows are indicators, columns are
reference periods, and one workbook carries the whole back-series. Stats SA's
"QLFS Trends 2008-<YYYY>Q<n>.xlsx" and Statistics Mauritius's
"LF_Emp_Unemp_<n>Qtr<YY>_<DDMMYY>.xlsx" are both this shape.

The parser does NOT hardcode cell addresses, because NSOs insert rows every
rebase. Instead it discovers structure the way the guide prescribes:

1. read every sheet (or only those whose name matches `sheet_contains`);
2. find the PERIOD HEADER ROW -- the first row with at least
   `min_periods` cells that parse as a reference period (a datetime, "2026Q2",
   "Apr-Jun 2026", "Jun-26", ...);
3. find the LABEL COLUMN -- the left-most column carrying text on data rows;
4. match each configured indicator row by keyword on that label;
5. emit EVERY dated column, honouring "all reported periods".

`unit: thousand_persons` matters here: Stats SA publishes levels in thousands
and a parser that relabels them as persons silently inflates nothing but
misleads every downstream join, so the unit travels with the value.

--- The layout dict -------------------------------------------------------

    survey / frequency / working_age_base / decimal    as in pdf_key_indicators
    sheet_contains    list  only scan sheets whose name contains any of these
    sheet_excludes    list  skip sheets whose name contains any of these
    min_periods       int   cells needed on a row for it to be the header
                            (default 4) -- guards against a stray date cell
    header_scan_rows  int   how far down to look for the header (default 30)
    rows              list  {match, topic, definition, label, measure, unit,
                            age_group, sex, locality, locality_label,
                            geography, exclude} -- `match` is a case-insensitive
                            regex on the row label; `exclude` prevents
                            substring collisions.
    blocks            list  headings that re-scope the rows beneath them
    first_match_only  bool  default True: the first matching row per spec per
                            sheet wins, so analytical aggregates repeated
                            lower down do not shadow the real series.
"""
from __future__ import annotations
import re
from typing import Callable

import pandas as pd

from . import _common as C


def _cell_period(v) -> str | None:
    """Read a reference period out of one header cell, whatever its type."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return f"{v.year}-Q{(v.month - 1) // 3 + 1}"
    s = str(v).strip()
    if not s:
        return None
    # A bare 4-digit year is a period; a bare 2-digit number is not.
    if re.fullmatch(r"(19|20)\d{2}(\.0)?", s):
        return s.split(".")[0]
    return C.parse_period(s)


def _sheets(path: str, cfg: dict) -> dict[str, pd.DataFrame]:
    xl = pd.ExcelFile(path)
    want = [s.lower() for s in cfg.get("sheet_contains", [])]
    skip = [s.lower() for s in cfg.get("sheet_excludes", [])]
    out = {}
    for name in xl.sheet_names:
        low = name.lower()
        if want and not any(w in low for w in want):
            continue
        if skip and any(s in low for s in skip):
            continue
        out[name] = xl.parse(name, header=None)
    if not out:
        raise ValueError(
            f"{path}: no sheet matched {cfg.get('sheet_contains')}; workbook has "
            f"{xl.sheet_names}")
    return out


def _find_header(df: pd.DataFrame, cfg: dict) -> tuple[int, dict[int, str]]:
    """Return (header row index, {column index -> period})."""
    min_periods = cfg.get("min_periods", 4)
    for i in range(min(cfg.get("header_scan_rows", 30), len(df))):
        mapping = {}
        for j in range(df.shape[1]):
            p = _cell_period(df.iat[i, j])
            if p:
                mapping[j] = p
        if len(mapping) >= min_periods:
            return i, mapping
    raise ValueError(
        f"no period header row found in the first "
        f"{cfg.get('header_scan_rows', 30)} rows (needed >= {min_periods} "
        f"parseable period cells). The workbook layout has changed.")


def _label(df: pd.DataFrame, i: int, max_col: int) -> str:
    for j in range(min(max_col, df.shape[1])):
        v = df.iat[i, j]
        if isinstance(v, str) and v.strip():
            return re.sub(r"\s+", " ", v).strip()
    return ""


def make_parser(cfg: dict) -> Callable[[str], pd.DataFrame]:
    """Build a `parse(path) -> DataFrame` for one country's workbook layout."""
    first_only = cfg.get("first_match_only", True)

    def parse(path: str) -> pd.DataFrame:
        rows: list[dict] = []
        problems: list[str] = []
        for sheet, df in _sheets(path, cfg).items():
            try:
                hdr, periods = _find_header(df, cfg)
            except ValueError as e:
                problems.append(f"{sheet}: {e}")
                continue
            label_stop = min(periods) if periods else df.shape[1]
            done: set[int] = set()
            # A SHEET CAN HOLD SEVERAL BLOCKS OF THE SAME ROWS. Stats SA's
            # Table 2 prints its whole indicator list three times over -- under
            # "Both sexes", then "Women", then "Men" -- and with
            # `first_match_only` and no notion of a block, only the first was
            # read: two thirds of the table was dropped, and what survived was
            # labelled `sex: total` whether it was or not.
            #
            # A block heading is a label with no values beside it that matches
            # one of `blocks`; its attributes apply to every row beneath it
            # until the next heading.
            blocks = cfg.get("blocks", [])
            block: dict = {}
            block_i = -1
            for i in range(hdr + 1, len(df)):
                label = _label(df, i, label_stop)
                if not label:
                    continue
                hit = next((b for b in blocks
                            if re.search(b["match"], label, re.I)), None)
                if hit is not None:
                    block, block_i = hit, blocks.index(hit)
                    done = set()          # the row specs run again per block
                    continue
                for k, spec in enumerate(cfg["rows"]):
                    if first_only and (k, block_i) in done:
                        continue
                    if spec.get("exclude") and re.search(spec["exclude"], label, re.I):
                        continue
                    if not re.search(spec["match"], label, re.I):
                        continue
                    emitted = False
                    for col, period in periods.items():
                        value = C.to_number(df.iat[i, col],
                                            decimal=cfg.get("decimal", "."))
                        if value is None:
                            continue
                        rows.append(C.row(
                            topic=spec["topic"],
                            definition=spec.get("definition", "not_applicable"),
                            value=value,
                            series_label=spec.get("label", label),
                            survey=cfg["survey"],
                            period=period, reference_period=period,
                            frequency=cfg["frequency"],
                            working_age_base=cfg["working_age_base"],
                            measure=spec.get("measure"), unit=spec.get("unit"),
                            sex=block.get("sex", spec.get("sex", "total")),
                            age_group=block.get("age_group", spec.get("age_group", "Total")),
                            education=block.get("education", spec.get("education", "Total")),
                            geography=block.get("geography", spec.get("geography", "Total country")),
                            locality=block.get("locality", spec.get("locality", "all")),
                            locality_label=block.get("locality_label", spec.get("locality_label", "Total")),
                            series_code=f"{sheet}!r{i + 1}",
                        ))
                        emitted = True
                    if emitted:
                        done.add((k, block_i))
                    break        # one spec per label; first spec wins

        if not rows:
            raise ValueError(
                f"{path}: no configured indicator row matched. "
                + ("; ".join(problems) if problems else
                   "Sheets were readable but no row label matched -- the "
                   "workbook's wording has changed (Stats SA, for example, "
                   "renamed 'Not economically active' to 'Outside the labour "
                   "force'). Re-check the row regexes against the file."))
        return pd.DataFrame.from_records(rows)

    parse.__name__ = f"parse_{cfg.get('survey', 'excel').lower().replace(' ', '_')}"
    return parse
