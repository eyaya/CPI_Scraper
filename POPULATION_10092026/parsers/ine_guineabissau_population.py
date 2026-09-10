"""INE Guinea-Bissau — national population by sex, projection (Tier-3 PDF).

Parser for INE-GB's "Relatorio de projecao 2014-2063", Tabela 10 ("Numeros da
populacao total, urbana e rural por idade e sexo de 2014 a 2040"). The table runs
one year per block with a national "Total" row (age bands then Total). Extraction
is hard: the year captions are unreliable in the text layer, and French/Portuguese
thousands separators alternate between "." and OCR-broken spaces, so the nine
columns cannot be split by delimiter.

We therefore take only the national "Total" rows (national population by sex),
which are unambiguous under the constraint Male + Female = Both. The GB total is
always 7 digits, so Both = the first three digit-groups; Male/Female are recovered
by the split that satisfies M+F=Both. Total rows appear in year order, so the year
is assigned by position starting at 2014. To stay faithful, we emit only the
leading run of consecutive years whose totals grow smoothly (< 3% YoY) and
reconcile; at the first anomaly (a symptom of a dropped/mis-paginated row) we stop.
Age detail and the later projection years are deliberately left out (not guessed).
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_BASE_YEAR = 2014
_MAX_YOY = 0.03


def _reconstruct(groups):
    """From the digit-groups of a Total row, return (both, male, female) with
    male+female==both, or None. Both is a 7-digit national total = first 3 groups."""
    if len(groups) < 7:
        return None
    both = int("".join(groups[0:3]))
    if not (1_000_000 <= both <= 9_999_999):
        return None
    rest = groups[3:]
    for k in (2, 3):
        for m in (2, 3):
            if k + m <= len(rest):
                male = int("".join(rest[0:k]))
                female = int("".join(rest[k:k + m]))
                if abs(male + female - both) <= 5:
                    return both, male, female
    return None


def parse(local_path: str) -> pd.DataFrame:
    totals = []
    with pdfplumber.open(local_path) as pdf:
        for page in pdf.pages:
            for ln in (page.extract_text() or "").splitlines():
                s = ln.strip()
                if s.startswith("Total") and re.search(r"\d", s):
                    rec = _reconstruct(re.findall(r"\d+", s))
                    if rec:
                        totals.append(rec)

    out, prev = [], None
    for i, (both, male, female) in enumerate(totals):
        if prev is not None and (both - prev) / prev > _MAX_YOY:
            break                       # pagination drift -> stop at first anomaly
        year = str(_BASE_YEAR + i)
        for sex, v in (("male", male), ("female", female), ("total", both)):
            out.append({
                "series_type": "projection", "sex": sex, "age_group": "Total",
                "geography": "Total country", "period": year,
                "frequency": "annual", "measure": "count", "value": float(v),
                "unit": "persons", "series_code": "GW_INE_PROJ_T10",
            })
        prev = both

    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("ine_guineabissau_population: no national totals parsed")
    return df
