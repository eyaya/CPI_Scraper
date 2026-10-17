"""Shared reader for the WAEMU IHPC monthly-note PDF, ACROSS ISSUES.

The eight WAEMU statistics offices publish the harmonised CPI (IHPC) as a
monthly note whose division table has one shape everywhere:

    Libellé [Pondération] <m-12> <m-3> <m-2> <m-1> <m> [Contribution] /1mois /3mois /12mois
    INDICE GLOBAL 10000 105,0 104,6 105,0 106,2 106,7 0,5 2,1 1,6
    I  Produits alimentaires ...   2797 112,8 109,0 110,1 112,8 113,3 0,5 4,0 0,5

So ONE NOTE PRINTS FIVE MONTHS OF INDEX (the same month a year earlier, plus
the last four), and the three % variations for the report month. Reading only
the report month -- which the per-country parsers did -- threw four fifths of
each note away; reading BACK ISSUES on top recovers the whole published
history.

HOW A ROW IS READ, and why strictly. The numbers are taken as the TRAILING run
of well-formed numeric tokens ("112,8", "-0,7", "10000"), counted EXACTLY:
n_months index values + [1 contribution] + 3 variations. A row whose trailing
run is shorter -- a garbled cell such as INSD's "p1a01g,e61" -- is DROPPED
with a printed message, never re-split: a loose regex would read that cell as
three plausible numbers. The months come from the table's own header line,
never from a position assumed in advance.

THE REBASE (January 2025): every WAEMU office moved from base 2014 (COICOP
1999, 12 divisions) to base 2023 (COICOP 2018, 13 divisions). The two scales
must never meet under one merge key (coicop_code . geography . period .
measure -- `base_period` is NOT in it), yet a January-2025 note prints its
year-ago column on the NEW base while the 2024 notes printed the same month
on the OLD one. So an INDEX belongs only to the base that was current for
its month: periods up to 2024-12 are taken from base-2014 issues, periods
from 2025-01 from base-2023 issues. The % variations are scale-free and are
taken from whichever issue reports them.

ACROSS ISSUES THE NEWEST ISSUE WINS (a later note revising an earlier
month's index is the office's revision).
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

from .togo_inseed import _DIVISIONS as DIVISIONS_2023   # COICOP 2018, base 2023

# COICOP 1999 divisions as the base-2014 IHPC notes number them.
DIVISIONS_2014 = {
    "I": ("01", "Produits alimentaires et boissons non alcoolisées"),
    "II": ("02", "Boissons alcoolisées, tabac et stupéfiants"),
    "III": ("03", "Articles d'habillement et chaussures"),
    "IV": ("04", "Logement, eau, gaz, électricité et autres combustibles"),
    "V": ("05", "Meubles, articles de ménage et entretien courant du foyer"),
    "VI": ("06", "Santé"),
    "VII": ("07", "Transport"),
    "VIII": ("08", "Communication"),
    "IX": ("09", "Loisirs et culture"),
    "X": ("10", "Enseignement"),
    "XI": ("11", "Restaurants et Hôtels"),
    "XII": ("12", "Biens et services divers"),
}
REBASE = "2025-01"
BASES = {"2014": ("2014 = 100", DIVISIONS_2014), "2023": ("2023 = 100", DIVISIONS_2023)}

_ROMAN_RE = re.compile(r"^(XIII|XII|XI|IX|X|VIII|VII|VI|IV|V|III|II|I)\b")
_NUM = re.compile(r"^-?\d+(?:,\d+)?$")
_MONTHS = {"janv": 1, "jan": 1, "janvier": 1, "fevr": 2, "févr": 2, "fev": 2, "fév": 2,
           "février": 2, "fevrier": 2, "mars": 3, "mar": 3, "avr": 4, "avril": 4,
           "mai": 5, "juin": 6, "juil": 7, "juillet": 7, "aout": 8, "août": 8,
           "sept": 9, "sep": 9, "septembre": 9, "oct": 10, "octobre": 10,
           "nov": 11, "novembre": 11, "dec": 12, "déc": 12, "décembre": 12,
           "decembre": 12}
_MTOK = re.compile(r"([A-Za-zéèûôâç]+)\.?[-\s]?(\d{2}|\d{4})\b")


def _header_months(line: str) -> list[str]:
    out = []
    for name, yy in _MTOK.findall(line):
        m = _MONTHS.get(name.lower())
        if m:
            y = int(yy) if len(yy) == 4 else 2000 + int(yy)
            out.append(f"{y}-{m:02d}")
    return out


def _f(tok: str) -> float:
    return float(tok.replace(",", "."))


def read_issue(text: str, *, contribution: bool, where: str,
               min_divisions: int | None = None) -> pd.DataFrame:
    """Every index month + the report month's variations, from one note."""
    lines = [l.strip() for l in text.splitlines()]
    months = None
    for l in lines:
        ms = _header_months(l)
        if len(ms) >= 3 and ("/1mois" in l.replace(" ", "").lower()
                            or "1 mois" in l.lower() or "1mois" in l.lower()):
            months = ms
            break
    if not months:
        raise ValueError(f"{where}: no dated header line in the division table")
    report = max(months)
    base_key = "2023" if report >= REBASE else "2014"
    base_label, divisions = BASES[base_key]
    n_after = (1 if contribution else 0) + 3
    need = len(months) + n_after

    rows: dict[str, tuple[str, list[float]]] = {}
    for l in lines:
        m = _ROMAN_RE.match(l)
        if m and m.group(1) in divisions:
            code, label = divisions[m.group(1)]
        elif l.lower().startswith(("indice global", "global", "ensemble")):
            code, label = "00", "All items"
        else:
            continue
        if code in rows:
            continue
        toks = l.split()
        run = []
        for t in reversed(toks):
            if _NUM.match(t):
                run.append(t)
            else:
                break
        run.reverse()
        if len(run) < need:
            if run:          # numbers present but cut short: a garbled cell
                print(f"  [ihpc] {where}: row {code} unreadable "
                      f"({' '.join(toks[-need:])!r}) -- dropped")
            continue
        rows[code] = (label, [_f(t) for t in run[-need:]])

    if "00" not in rows:
        raise ValueError(f"{where}: no all-items row")
    floor = min_divisions if min_divisions is not None else len(divisions) - 1
    if len(rows) - 1 < floor:
        raise ValueError(f"{where}: only {len(rows) - 1} divisions read (base {base_key})")

    recs = []
    for code, (label, nums) in rows.items():
        idx = nums[:len(months)]
        mom, yoy = nums[-3], nums[-1]
        for per, v in zip(months, idx):
            # the index belongs to the base current for its month (see above)
            if (per >= REBASE) == (base_key == "2023"):
                recs.append((code, label, per, "index", v, "Index", base_label))
        recs.append((code, label, report, "inflation_mom", mom, "percent", ""))
        recs.append((code, label, report, "inflation_yoy", yoy, "percent", ""))
    out = pd.DataFrame.from_records(recs, columns=[
        "coicop_code", "coicop_label", "period", "measure", "value", "unit",
        "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    out["_issue"] = report
    return out


def pdf_text(path: str, max_pages: int = 6) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages[:max_pages])


def combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Newest issue wins on a shared (code, geography, period, measure)."""
    df = pd.concat(frames, ignore_index=True).sort_values("_issue")
    df = df.drop_duplicates(["coicop_code", "geography", "period", "measure"],
                            keep="last")
    return df.drop(columns="_issue").reset_index(drop=True)


def read_many(paths: list[str], reader, label: str) -> pd.DataFrame:
    """Apply `reader(path)` to every issue; an issue that does not read is
    skipped WITH A MESSAGE, never half-read.

    THE NEWEST ISSUE FAILING IS LOUD, NOT FATAL. It used to have to read, so
    that a layout change could not slip by -- but one defective newest note
    (INS Niger 2026-09: table incomplete) then discarded every back issue's
    history with it. Now the run continues on the back issues and prints a
    WARNING naming the newest issue; if NO issue reads, it still raises."""
    frames, newest_error = [], None
    for i, p in enumerate(paths):
        try:
            frames.append(reader(p))
        except Exception as e:                          # noqa: BLE001
            name = p.rsplit(chr(92), 1)[-1].rsplit('/', 1)[-1]
            if i == 0:
                newest_error = e
                print(f"  [{label}] WARNING -- the NEWEST issue {name} did not read "
                      f"({type(e).__name__}: {str(e)[:90]}); continuing on back "
                      f"issues, so this run adds no new period")
            else:
                print(f"  [{label}] skipped {name}: {type(e).__name__}: {str(e)[:90]}")
    if not frames:
        raise newest_error or ValueError(f"[{label}] no issue read")
    return combine(frames)


def over_issues(single, label: str):
    """Turn a ONE-ISSUE parser (report month only) into one that reads the
    newest issue plus its back issues. Each issue is tagged with the latest
    period it reports, so `combine` can let the newest issue win; an issue the
    single parser refuses is skipped with a message (the primary must read).
    Used by the CPI parsers whose table does not date every printed column."""
    def _tagged(path: str) -> pd.DataFrame:
        df = single(path)
        df = df.copy()
        df["_issue"] = df["period"].max()
        return df

    def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
        return read_many([path, *(extras or [])], _tagged, label)
    return parse
