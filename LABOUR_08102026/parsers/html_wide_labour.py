"""Config-driven reader for a labour cross-tab published as an HTML TABLE.

The third engine in this indicator, beside `excel_wide_labour` (a workbook with
periods across the columns) and `pdf_tables_labour` (a report PDF). It exists
for one NSO: **INS Tunisie**, which publishes its quarterly labour series as
real, server-rendered HTML tables on its theme pages rather than as a file.

WHY HTML AND NOT THE PDF -- the conclusion `unemployment` reached first, and
the whole reason Tunisia is collectable at all. INS's quarterly note is a
bilingual Arabic/French document whose numeric runs come out of the text layer
BIDI-SCRAMBLED, and differently in each table: one row fully reversed, another
rotated by four positions, a third with its digits run together. There is no
correct way to align those numbers with their quarters, so the note is not
parsed at all. The theme pages carry the same series in reading order.

SHAPE: category labels run DOWN the first column and periods run ACROSS the
header as French ordinal quarters ("première-trimestre 2024"). That is the same
wide shape `excel_wide_labour` reads, in a different container.

--- The layout dict -------------------------------------------------------

    survey / frequency / working_age_base / decimal   as elsewhere
    tables    list, one entry per HTML table to capture:
                caption        regex identifying the table, matched against the
                               markup PRECEDING it plus its own text -- INS
                               titles each series in a heading ABOVE its table,
                               so matching on cell contents alone would miss it
                topic          the schema topic every row of it carries
                classification the scheme those categories belong to
                measure / unit as published
                relabel        [[regex, label], ...] rewriting a published row
                               label; INS labels its TOTAL row with the table's
                               own title rather than "Total"
                expect_rows    minimum categories, so a table that changes shape
                               fails instead of shipping half of itself
                series_code

CATEGORIES ARE SCANNED, NOT LISTED, as everywhere in this indicator: every
labelled row carrying at least one value is taken, so a category the NSO adds
is collected rather than silently dropped. `expect_rows` is what makes that
safe.

A ROW WITH NO VALUES AT ALL IS PAGE FURNITURE. INS renders "NoFilter",
"Unité : Nombre", "Source : ..." and the series title as rows of the table
itself, every period cell empty. They are skipped for HAVING NO VALUE rather
than by being named, which keeps one country's page chrome out of the engine.

A DASH IS A MISSING CELL, NOT A ZERO. INS prints "--" where a quarter has no
figure ("Non déclarés" in three of nine quarters). `to_number` returns None and
the cell is skipped, because writing a 0 would publish a figure the NSO did not.
"""
from __future__ import annotations

import io
import os
import re
from typing import Callable

import pandas as pd

from . import _common as C

_TABLE_RE = re.compile(r"<table\b.*?</table>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _read_tables(path: str) -> list[tuple[pd.DataFrame, str]]:
    """Every table on the saved page, paired with its CONTEXT text.

    Context is the markup immediately preceding the table plus the table's own
    text, because a series title sits in a heading ABOVE its table rather than
    inside it. The markup is wrapped in a StringIO because pandas treats a bare
    string as a path or URL.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        html = fh.read()
    out: list[tuple[pd.DataFrame, str]] = []
    for m in _TABLE_RE.finditer(html):
        head = html[max(0, m.start() - 1200):m.start()]
        context = re.sub(r"\s+", " ", _TAG_RE.sub(" ", head + " " + m.group(0)))
        try:
            frames = pd.read_html(io.StringIO(m.group(0)))
        except ValueError:
            continue
        for df in frames:
            out.append((df, context))
    return out


def _periods(df: pd.DataFrame) -> dict:
    """Map each column to its period, from the header or the first row."""
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


def make_parser(cfg: dict) -> Callable[..., pd.DataFrame]:
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
                f"JS-rendered -- re-check the source before trusting any output.")

        decimal = cfg.get("decimal", ".")
        base = os.path.basename(path)
        rows: list[dict] = []

        for spec in cfg["tables"]:
            where = f"{base} [{spec.get('series_code', spec['topic'])}]"
            pat = re.compile(spec["caption"], re.I)
            target = next((df for df, ctx in frames if pat.search(ctx)), None)
            if target is None:
                raise ValueError(
                    f"{where}: no table matched {spec['caption']!r} "
                    f"({len(frames)} table(s) on the page(s))")

            periods = _periods(target)
            if not periods:
                raise ValueError(
                    f"{where}: the table has no parseable period columns "
                    f"({[str(c)[:30] for c in target.columns][:4]}). A header "
                    f"that cannot be read must be taught to `parse_period`, "
                    f"never defaulted to the run's own date.")

            relabel = [(re.compile(rx, re.I), lab)
                       for rx, lab in spec.get("relabel", ())]
            label_col = target.columns[0]
            found = 0

            for _, r in target.iterrows():
                label = str(r[label_col]).strip()
                if not label or label.lower() == "nan":
                    continue
                values = {col: C.to_number(r[col], decimal=decimal)
                          for col in periods}
                # Page furniture: a labelled row with no value in any period.
                if all(v is None for v in values.values()):
                    continue
                for rx, lab in relabel:
                    if rx.search(label):
                        label = lab
                        break
                found += 1
                for col, period in periods.items():
                    if values[col] is None:
                        continue
                    rows.append(C.row(
                        topic=spec["topic"], characteristic=label,
                        classification=spec["classification"],
                        value=values[col],
                        survey=cfg["survey"], period=period,
                        reference_period=str(col),
                        frequency=cfg["frequency"],
                        working_age_base=cfg.get("working_age_base", "15+"),
                        measure=spec.get("measure", "count"),
                        unit=spec.get("unit", "persons"),
                        sex=spec.get("sex", "total"),
                        age_group=spec.get("age_group", "Total"),
                        education=spec.get("education", "Total"),
                        geography=spec.get("geography", "Total country"),
                        locality=spec.get("locality", "all"),
                        locality_label=spec.get("locality_label", "Total"),
                        series_code=spec.get("series_code", ""),
                    ))

            expect = spec.get("expect_rows")
            if expect and found < expect:
                raise ValueError(
                    f"{where}: scanned {found} categories but the layout "
                    f"expects at least {expect}. Either the table changed or "
                    f"its caption now selects a different one -- re-read the "
                    f"page rather than lowering expect_rows.")

        if not rows:
            raise ValueError(f"{path}: no rows produced")
        return pd.DataFrame.from_records(rows)

    parse.__name__ = f"parse_{cfg.get('survey', 'html')[:40].lower().replace(' ', '_')}"
    return parse
