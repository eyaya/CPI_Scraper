"""Dating a CAPMAS LFS PDF BACK ISSUE (2015-2020), shared by the
unemployment and labour back-issue readers.

The current-bulletin layouts date an issue from "Bulletin of Labour Force
(April - June) 2026". The 2015-2017 issues abbreviate the months with a full
stop ("( Jan. - Mar.) 2015", "(July - Sep.) 2016"), which that pattern does
not accept, and one 2015 Q1 page prints "(Jun. - Mar.) 2015" -- a typo in
the START month. So a back issue is filed under the quarter its `save_as`
name carries (`egypt_lfs_<YYYY>Q<n>.pdf`, from CAPMAS's API) and that quarter
is CHECKED against the bulletin's own text: every "Bulletin of Labour Force
(<m1> - <m2>) <year>" occurrence must END on the quarter's last month in the
filed year. The end month is what is checked because it is the one the
typo leaves intact, and it is read by its first three letters (CAPMAS also
prints "Sepetmber", "Septemper", "DEcember").

STRAY RUNNING HEADS. A few pages keep the previous issue's head (2017 Q4:
2 of 70 pages say "July - September"; 2018 Q1 and 2020 Q4: one page each
names the wrong year). So the check is on the DOMINANT phrase: at least 90%
of the occurrences must end on the filed quarter. An issue with no such
phrase, or a weaker majority, is refused.
"""
from __future__ import annotations

import os
import re

_NAME = re.compile(r"egypt_lfs_(20\d{2})Q([1-4])\.pdf$", re.I)
_PHRASE = re.compile(
    r"Bulletin\s*of\s*Labour\s*Force\s*\(\s*([A-Za-z]+)\.?\s*[-–]\s*([A-Za-z]+)\.?\s*\)\s*(20\d{2})",
    re.I)
_END = {"mar": 1, "jun": 2, "sep": 3, "dec": 4}


def filed_quarter(path: str) -> tuple[int, int]:
    m = _NAME.search(os.path.basename(path))
    if not m:
        raise ValueError(f"Egypt LFS PDF back issue {path!r}: name must be "
                         f"egypt_lfs_<YYYY>Q<n>.pdf (set by the descriptor)")
    return int(m.group(1)), int(m.group(2))


def check_period(path: str) -> tuple[str, str]:
    """(period, reference_period) for a PDF back issue, verified."""
    import fitz
    y, q = filed_quarter(path)
    text = " ".join(p.get_text() for p in fitz.open(path))
    seen = []
    for m1, m2, yr in _PHRASE.findall(text):
        seen.append((int(yr), _END.get(m2.lower()[:3])))
    if not seen:
        raise ValueError(f"{os.path.basename(path)}: no 'Bulletin of Labour "
                         f"Force (<months>) <year>' phrase to check the quarter")
    share = seen.count((y, q)) / len(seen)
    if share < 0.9:
        raise ValueError(f"{os.path.basename(path)}: filed as {y} Q{q} but only "
                         f"{share:.0%} of its month ranges say so ({sorted(set(seen), key=str)})")
    return f"{y}-Q{q}", f"Q{q} {y}"


def fixed_layout(layout: dict, path: str) -> dict:
    """The current layout, with its period pinned to the verified quarter."""
    period, ref = check_period(path)
    out = dict(layout)
    out["period_patterns"] = []
    out["period"] = period
    out["reference_period"] = ref
    return out
