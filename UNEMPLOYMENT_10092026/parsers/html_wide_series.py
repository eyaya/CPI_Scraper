"""Config-driven parser for a WIDE labour series published as an HTML TABLE.

One NSO in Africa publishes its quarterly labour series as real, server-rendered
HTML tables rather than a report PDF or a workbook: **INS Tunisie**, on its
theme pages `ins.tn/statistiques/151` (population active), `/152` (population
occupée) and `/153` (chômage).

That route matters because the alternative is unusable. INS's quarterly PDF is a
bilingual Arabic/French document whose numeric runs come out of the text layer
in bidi-scrambled order — reversed on one table, rotated on another, digits run
together on a third. There is no reliable way to align those numbers with their
quarters. The HTML tables carry the same series in reading order, so this is not
a convenience, it is the only correct way to collect Tunisia.

Shape (identical on all three pages): row labels in the first column
(`Total` / `Masculin` / `Féminin`, or sector names), and column headers that are
French ordinal quarter labels — `première-trimestre 2024`, `deuxième-trimestre
2024`, … through the current quarter.

--- The layout dict -------------------------------------------------------

    survey / frequency / working_age_base / decimal   as elsewhere
    tables    list, one entry per HTML table to capture:
                caption      regex identifying the table; matched against the
                             markup PRECEDING the table plus the table's own
                             text, because INS puts each series title in a
                             heading above its table rather than inside it.
                             The first table whose context matches is taken.
                defaults     attributes every cell inherits (usually `topic`)
                rows         {match, ...} keyed on the row label
                unit/measure may be set in defaults or per row

Only tables whose `caption` matches are read, so a page carrying several series
(`/152` has active-population, job-creation and sector-distribution tables)
yields only the ones asked for.
"""
from __future__ import annotations
import io
import re
from typing import Callable

import pandas as pd

from . import _common as C


_TABLE_RE = re.compile(r"<table\b.*?</table>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _read_tables(path: str) -> list[tuple[pd.DataFrame, str]]:
    """Every table on the saved page, paired with its CONTEXT text.

    Context is the markup immediately preceding the table plus the table's own
    text, because a table's caption is usually in a heading ABOVE it rather
    than inside it -- INS Tunisie titles each series in an <h3>. Matching only
    on cell contents would miss every one.

    The markup is wrapped in a StringIO: pandas treats a bare string as a path
    or URL, so passing the HTML itself raises FileNotFoundError.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()
    out: list[tuple[pd.DataFrame, str]] = []
    for m in _TABLE_RE.finditer(html):
        head = html[max(0, m.start() - 1200):m.start()]
        context = _TAG_RE.sub(" ", head + " " + m.group(0))
        context = re.sub(r"\s+", " ", context)
        try:
            frames = pd.read_html(io.StringIO(m.group(0)))
        except ValueError:
            continue
        for df in frames:
            out.append((df, context))
    return out


def _periods(df: pd.DataFrame) -> dict:
    """Map each column to a reference period, reading the header first and
    falling back to the first row when the table has no real header."""
    out = {}
    for col in df.columns:
        p = C.parse_period(str(col))
        if p:
            out[col] = p
    if out:
        return out
    if len(df):
        for col in df.columns:
            p = C.parse_period(str(df.iloc[0][col]))
            if p:
                out[col] = p
    return out


def make_parser(cfg: dict) -> Callable[[str], pd.DataFrame]:
    """Build a `parse(path, extras=[...]) -> DataFrame` for one country's pages.

    `extras` are the additional saved pages listed as `extra_urls` in the
    descriptor; all of them are scanned for every configured table, so it does
    not matter which page a given table happens to live on.
    """
    def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
        frames: list[tuple[pd.DataFrame, str]] = []
        for p in [path] + list(extras or []):
            frames.extend(_read_tables(p))
        if not frames:
            raise ValueError(
                f"{path}: no HTML table found. The page is probably now "
                f"JS-rendered — re-check the source before trusting any output.")

        rows: list[dict] = []
        misses: list[str] = []
        for tbl in cfg["tables"]:
            pat = re.compile(tbl["caption"], re.I)
            target = None
            for df, context in frames:
                if pat.search(context):
                    target = df
                    break
            if target is None:
                misses.append(tbl["caption"])
                continue

            periods = _periods(target)
            if not periods:
                misses.append(f"{tbl['caption']} (no parseable period columns)")
                continue
            label_col = target.columns[0]
            defaults = tbl.get("defaults", {})

            for _, r in target.iterrows():
                label = str(r[label_col]).strip()
                if not label or label.lower() == "nan":
                    continue
                for spec in tbl["rows"]:
                    if spec.get("exclude") and re.search(spec["exclude"], label, re.I):
                        continue
                    if not re.search(spec["match"], label, re.I):
                        continue
                    cell = {**defaults, **spec}
                    for col, period in periods.items():
                        value = C.to_number(r[col], decimal=cfg.get("decimal", "."))
                        if value is None:
                            continue
                        rows.append(C.row(
                            topic=cell["topic"],
                            definition=cell.get("definition", "not_applicable"),
                            value=value,
                            series_label=cell.get("label", label),
                            survey=cfg["survey"],
                            period=period, reference_period=str(col),
                            frequency=cfg["frequency"],
                            working_age_base=cfg["working_age_base"],
                            measure=cell.get("measure"), unit=cell.get("unit"),
                            sex=cell.get("sex", "total"),
                            age_group=cell.get("age_group", "Total"),
                            education=cell.get("education", "Total"),
                            geography=cell.get("geography", "Total country"),
                            locality=cell.get("locality", "all"),
                            locality_label=cell.get("locality_label", "Total"),
                            series_code=cell.get("series_code", ""),
                        ))
                    break

        if not rows:
            raise ValueError(
                f"{path}: no configured table/row matched "
                f"({len(frames)} table(s) on the page(s)). "
                + ("; ".join(misses) if misses else ""))
        if misses:
            print(f"[html_wide_series] {path}: no match for {misses}")
        return pd.DataFrame.from_records(rows)

    parse.__name__ = f"parse_{cfg.get('survey', 'html').lower().replace(' ', '_')}"
    return parse
