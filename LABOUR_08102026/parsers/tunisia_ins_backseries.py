"""Tunisia -- INS theme page PLUS INS's 2006-2026 employment workbook.

The descriptor's primary is INS's theme page /statistiques/152 (employment by
branch, a rolling window of about eight quarters), read by `tunisia_labour`.
The back series is INS's own workbook attached to every quarterly note
("Indicateurs de l'emploi et du chômage"):

    Statistiques_Emploi_Tunisie_2006_2026.xlsx

Source line: "Institut National de la Statistique (INS), Enquête Nationale sur
la Population et l'Emploi". The `unemployment` indicator reads its headline
tables (1-3, 7-10); this reads the composition tables:

    Tableau 5  population active occupée by branch of activity, thousands --
               three blocks on one sheet:
                 2007-2010 annual, 2011 Q2 - 2026 Q2 quarterly (21 branches,
                   the manufacturing / non-manufacturing / services sub-
                   branches printed only in some years);
                 1966-2005, survey and census years (19 branches, upper case);
                 2006 (and 2005 again, identical to the block above -- read
                   once, from the 1966-2005 block).
    Tableau 6  population active occupée by professional status, thousands,
               2006-2010 annual, 2011 Q2 - 2026 Q2 quarterly.

NOT READ: Tableau 5.bis (2026 Q1-Q2 under a new upper-case nomenclature;
two quarters only).

TOPIC AND CLASSIFICATION as for the theme page (see `tunisia_labour`): the
branches are `industry`, nomenclature not named, so `National`; the statuses
are `employment_status`, `National`. Labels verbatim (whitespace collapsed);
INS's footnote marker on "COMMERCE*" is dropped from the label and its
meaning kept here: for 1966-2004 the row groups commerce with "IMMOBILIER,
REPARATIONS, SERVICES AUX ENTREPRISES".

PERIODS: "2007" / "année 2006" are annual (the annual survey was collected
April-June, per the footnote; the header is kept as `reference_period`);
"Trimestre 2- 2011" (sometimes "Trimestrre") is quarterly. The 1966-2005
columns are the survey and census years INS prints (1966, 1975, 1984, 1987,
1989, 1994, 1996, ...), filed as annual. No missing year or quarter is filled.

PUBLISHED, KEPT: in Tableau 6, 2018 Q1, the four statuses sum to 1.9
thousand more than the printed Total; every other period agrees within 0.25.

UNITS: thousands; values as stored, binary float noise removed. "-" and blank
cells are not published and are skipped.

THE THEME PAGE WINS WHERE IT OVERLAPS: a workbook row whose full identity
(the merge key) the theme page already carries is not read twice.
"""
from __future__ import annotations

import re

import pandas as pd

from . import tunisia_labour

_SURVEY = "Enquête Nationale sur la Population et l'Emploi"
_ANNUAL = re.compile(r"^\s*(?:année\s*)?((?:19|20)\d{2})(?:\s*année)?\s*$", re.I)
_QUARTER = re.compile(r"^\s*Trimest?r+e\s*([1-4])\s*-\s*((?:19|20)\d{2})\s*$", re.I)
_KEY = ["topic", "characteristic", "classification", "sex", "age_group",
        "education", "geography", "locality", "locality_label",
        "working_age_base", "period", "measure"]


def _clean(v) -> str:
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else ""


def _num(v):
    t = _clean(v).replace(" ", "")
    if not t or t.lower() == "nan" or t in {"-", "–"}:
        return None
    try:
        return round(float(t.replace(",", ".")), 9)
    except ValueError:
        return None


def _period(h: str):
    m = _QUARTER.match(h)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}", "quarterly"
    m = _ANNUAL.match(h)
    if m:
        return m.group(1), "annual"
    return None


def _block(d: pd.DataFrame, hdr: int, topic: str, code: str,
           only: set | None = None) -> list[dict]:
    cols = {j: (_period(_clean(v)), _clean(v)) for j, v in enumerate(d.iloc[hdr])
            if _period(_clean(v))}
    if only is not None:
        cols = {j: c for j, c in cols.items() if c[0][0] in only}
    rows = []
    for i in range(hdr + 1, len(d)):
        name = _clean(d.iloc[i, 0])
        if not name or name.startswith(("*", "Source")) or name.lower() == "secteur":
            if rows and not name:
                break                         # the blank line closing the block
            continue
        label = name.rstrip("*").strip()
        for j, ((period, freq), head) in cols.items():
            v = _num(d.iloc[i, j])
            if v is None:
                continue
            rows.append({
                "survey": _SURVEY, "topic": topic, "characteristic": label,
                "classification": "National", "sex": "total",
                "age_group": "Total", "education": "Total",
                "geography": "Total country", "locality": "all",
                "locality_label": "Total", "working_age_base": "15+",
                "period": period, "reference_period": head, "frequency": freq,
                "measure": "count", "value": v, "unit": "thousand_persons",
                "series_code": code,
            })
        if label.lower() == "total":
            break
    if not rows:
        raise ValueError(f"INS workbook {code}: block at row {hdr} read no rows")
    return rows


def _header_rows(d: pd.DataFrame) -> list[int]:
    return [i for i in range(len(d))
            if sum(_period(_clean(v)) is not None for v in d.iloc[i]) >= 1
            and _clean(d.iloc[i, 0]).lower() in {"", "secteur", "nan"}]


def _workbook(path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    t5 = next(s for s in xl.sheet_names if s.startswith("Pop_Occ_SectAct_2007"))
    t6 = next(s for s in xl.sheet_names if s.startswith("Evol_Pop_Occ_Statut"))
    rows = []

    d = xl.parse(t5, header=None, dtype=str)
    if not _clean(d.iloc[0, 0]).lower().startswith("tableau 5"):
        raise ValueError(f"INS workbook {t5!r}: not Tableau 5")
    # Header rows: the main block's French header, then the two history
    # blocks. The Arabic header line beneath each carries "سنة ..." and is
    # not matched.
    heads = [i for i in _header_rows(d)
             if any(_period(_clean(v)) for v in d.iloc[i])]
    main, hist, y2006 = heads[0], heads[1], heads[2]
    rows += _block(d, main, "industry", "INS Emploi 2006-2026 T5")
    rows += _block(d, hist, "industry", "INS Emploi 2006-2026 T5 (1966-2005)")
    rows += _block(d, y2006, "industry", "INS Emploi 2006-2026 T5 (2006)",
                   only={"2006"})

    d = xl.parse(t6, header=None, dtype=str)
    if not _clean(d.iloc[0, 0]).lower().startswith("tableau 6"):
        raise ValueError(f"INS workbook {t6!r}: not Tableau 6")
    rows += _block(d, _header_rows(d)[0], "employment_status",
                   "INS Emploi 2006-2026 T6")

    df = pd.DataFrame(rows)
    dup = df.duplicated(_KEY, keep=False)
    if dup.any():
        raise ValueError(f"INS workbook: {int(dup.sum())} rows share a key -- "
                         f"{df.loc[dup, ['characteristic', 'period']].head(4).values.tolist()}")
    return df


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    base = tunisia_labour.parse(path)
    frames = [base]
    norm = lambda x: x[_KEY].astype(str).agg("|".join, axis=1)
    have = set(norm(base))
    for b in extras or []:
        wb = _workbook(b)
        frames.append(wb[~norm(wb).isin(have)])
    return pd.concat(frames, ignore_index=True)
