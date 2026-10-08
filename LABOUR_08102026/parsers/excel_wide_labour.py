"""Config-driven reader for labour cross-tabs in a wide workbook.

The shape this handles: PERIODS ACROSS THE COLUMNS, a category list DOWN the
rows, and the whole list repeated once per block (usually per sex).

    Table 3.1: Employed by industry and sex
                        Jan-Mar 2008   Apr-Jun 2008   ...
    Both sexes            14437.740      14584.495          <- block header
      Agriculture           838.059        820.205
      Mining                352.770        372.797
      ...
    Women                  6202.059       6265.661          <- next block
      Agriculture           294.070        257.054

WHY THE CATEGORIES ARE SCANNED, NOT LISTED. An unemployment table has a fixed
set of named indicator rows and enumerating them is right, because a row that
stops appearing is a real change. A labour cross-tab is a CLASSIFICATION -- ten
industry groups, ten ISCO major groups, twenty ISIC sections -- and listing
them in the layout would mean a new category silently vanishing rather than
being collected. So the layout says where the block starts and what the
categories MEAN, and every label between one block header and the next is
taken.

`expect_rows` is the guard that makes scanning safe: a block that yields fewer
categories than the layout says it should raises, rather than quietly shipping
half a table.
"""
from __future__ import annotations

import os
import re
from typing import Callable

import pandas as pd

from . import _common as C


def _sheets(path: str, cfg: dict) -> dict[str, pd.DataFrame]:
    xl = pd.ExcelFile(path)
    want = [s.lower() for s in cfg.get("sheet_contains", [])]
    skip = [s.lower() for s in cfg.get("sheet_excludes", [])]
    out = {}
    for name in xl.sheet_names:
        low = name.lower()
        if want and not any(w in low for w in want):
            continue
        if any(s in low for s in skip):
            continue
        out[name] = pd.read_excel(path, sheet_name=name, header=None)
    return out


def _find_header(df: pd.DataFrame, cfg: dict) -> tuple[int, dict[int, str]]:
    """The row of period labels, and which column each period sits in."""
    need = cfg.get("min_periods", 2)
    for i in range(min(30, len(df))):
        periods = {}
        for j in range(1, df.shape[1]):
            p = C.parse_period(df.iat[i, j])
            if p:
                periods[j] = p
        if len(periods) >= need:
            return i, periods
    raise ValueError(
        f"no period header row in the first 30 rows (needed >= {need} "
        f"parseable period cells). The workbook's layout has changed.")


def _label(df: pd.DataFrame, i: int, stop: int) -> str:
    for j in range(0, max(1, stop)):
        v = df.iat[i, j]
        if v is not None and str(v).strip() and str(v).strip().lower() != "nan":
            return str(v).strip()
    return ""


def make_parser(cfg: dict) -> Callable[[str], pd.DataFrame]:
    """Build a `parse(path) -> DataFrame` for one country's workbook layout."""

    def parse(path: str) -> pd.DataFrame:
        rows: list[dict] = []
        problems: list[str] = []
        sheets = _sheets(path, cfg)
        if not sheets:
            raise ValueError(
                f"{path}: no sheet matched {cfg.get('sheet_contains')}; the "
                f"workbook holds {pd.ExcelFile(path).sheet_names[:8]}")

        for spec in cfg["tables"]:
            name = next((s for s in sheets
                         if s.strip().lower() == spec["sheet"].strip().lower()),
                        None)
            if name is None:
                problems.append(f"{spec['sheet']}: sheet not present")
                continue
            df = sheets[name]
            try:
                hdr, periods = _find_header(df, cfg)
            except ValueError as e:
                problems.append(f"{spec['sheet']}: {e}")
                continue
            stop = min(periods) if periods else df.shape[1]

            blocks = spec.get("blocks") or [{"match": r".", "sex": "total"}]
            block = None
            seen_in_block = 0
            # SOME SHEETS CONTINUE PAST THE BLOCKS WE WANT. Stats SA's Table
            # 3.10 gives formal/informal for Both sexes, Women and Men, and
            # then repeats the whole thing broken down by AGE BAND. Left to
            # run, the scan attributes those later rows to the last sex block
            # and emits a second, contradictory "Formal employment" for Men.
            # `max_blocks` stops at the end of the blocks the layout asked for.
            max_blocks = spec.get("max_blocks")
            blocks_done = 0
            # AND SOME SHEETS CONTINUE PAST THE BLOCKS WITHOUT A NEW HEADER.
            # `max_blocks` alone is not enough for Stats SA's Table 3.10: after
            # the three sex blocks it repeats formal/informal by age, by
            # education, by industry and by occupation, under sub-headings that
            # are not block headers -- so nothing stopped the scan and all of
            # them were swept into `formality`, colliding with each other.
            # `max_rows_per_block` says how many categories a block actually
            # has, and anything past that is a different cut.
            max_in_block = spec.get("max_rows_per_block")
            exclude = spec.get("exclude_labels", [])
            drop_re = re.compile(spec["exclude_pattern"]) if spec.get("exclude_pattern") else None
            counts: dict[str, int] = {}

            for i in range(hdr + 1, len(df)):
                label = _label(df, i, stop)
                if not label:
                    continue
                hit = next((b for b in blocks
                            if re.search(b["match"], label, re.I)), None)
                if hit is not None:
                    blocks_done += 1
                    if max_blocks and blocks_done > max_blocks:
                        break
                    block = hit
                    seen_in_block = 0
                    # A block header carries the block TOTAL beside it. It is a
                    # real published figure, so it is emitted as the topic's
                    # "Total" rather than thrown away.
                    if spec.get("emit_block_total", True):
                        for col, period in periods.items():
                            v = C.to_number(df.iat[i, col], cfg.get("decimal", "."))
                            if v is None:
                                continue
                            rows.append(C.row(
                                topic=spec["topic"], characteristic="Total",
                                classification=spec["classification"],
                                value=v, survey=cfg["survey"], period=period,
                                reference_period=str(df.iat[hdr, col]).strip(),
                                frequency=cfg["frequency"],
                                measure=spec.get("measure", "count"),
                                unit=spec.get("unit", "persons"),
                                sex=block.get("sex", "total"),
                                age_group=block.get("age_group", "Total"),
                                geography=block.get("geography", "Total country"),
                                locality=block.get("locality", "all"),
                                locality_label=block.get("locality_label", "Total"),
                                working_age_base=cfg["working_age_base"],
                                series_code=f"{name}!r{i + 1}"))
                    continue
                if block is None:
                    continue
                if max_in_block and seen_in_block >= max_in_block:
                    continue
                if label in exclude or (drop_re and drop_re.search(label)):
                    continue

                emitted = False
                for col, period in periods.items():
                    v = C.to_number(df.iat[i, col], cfg.get("decimal", "."))
                    if v is None:
                        continue
                    rows.append(C.row(
                        topic=spec["topic"], characteristic=label,
                        classification=spec["classification"],
                        value=v, survey=cfg["survey"], period=period,
                        reference_period=str(df.iat[hdr, col]).strip(),
                        frequency=cfg["frequency"],
                        measure=spec.get("measure", "count"),
                        unit=spec.get("unit", "persons"),
                        sex=block.get("sex", "total"),
                        age_group=block.get("age_group", "Total"),
                        geography=block.get("geography", "Total country"),
                        locality=block.get("locality", "all"),
                        locality_label=block.get("locality_label", "Total"),
                        working_age_base=cfg["working_age_base"],
                        series_code=f"{name}!r{i + 1}"))
                    emitted = True
                if emitted:
                    seen_in_block += 1
                    counts[str(block.get("sex", "total"))] = seen_in_block

            want_rows = spec.get("expect_rows")
            if want_rows:
                short = {k: v for k, v in counts.items() if v < want_rows}
                if short or not counts:
                    raise ValueError(
                        f"{os.path.basename(path)} [{spec['sheet']}]: expected "
                        f"at least {want_rows} categories per block, got "
                        f"{counts or 'none'}. A short block means the scan "
                        f"stopped early -- re-read the sheet rather than "
                        f"lowering expect_rows.")

        if not rows:
            raise ValueError(
                f"{path}: no rows read. " + ("; ".join(problems) if problems
                                             else "Every sheet was readable "
                                                  "but no block header matched."))
        return pd.DataFrame.from_records(rows)

    parse.__name__ = f"parse_{cfg.get('survey', 'labour').lower().replace(' ', '_')}"
    return parse
