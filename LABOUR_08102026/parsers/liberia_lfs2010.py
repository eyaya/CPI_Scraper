"""Liberia — LISGIS / Ministry of Labour, Labour Force Survey 2010 (the round
BEFORE the 2016-17 LFS that `liberia_labour` reads). Added 2026-10-12.

Same publisher, same site (lisgis.gov.lr/uploads/surveys/lfs-2010.pdf, listed
by LISGIS's survey-report API beside the 2016-17 report). Fieldwork February to
May 2010, combined with the CWIQ; 6,233 households. Base 15+.

Three tables, each printed as COUNTS then PERCENTAGES, by sex within Urban /
Rural / Total (nine columns):

* Table 4.2  main occupation, "ISCO-08" major groups (named in the header);
* Table 4.4  sector of economic activity, "ISIC rev 4" sections (named);
* Table 4.6  status in employment -- no scheme named, so National.

Counts are printed ROUNDED TO THE NEAREST THOUSAND ("233,000") and kept as
printed. "*" (fewer than 500 persons) and "‐" (none) are missing cells, never
0. The report warns that totals differ slightly between tables because of
item non-response (employed 1,063,000 in 4.2; 1,073,000 in 4.4; 1,080,000 in
4.6) -- kept as published, each table's own Total.

NOT COLLECTED: 4.6's "Vulnerable employment indicator" (a derived sum), 4.3 /
4.5 detailed groups (two-digit; the one-digit tables carry the same totals),
4.7-4.16 (cross-tabs, hours, wages).

CROSS-CHECK: skilled agricultural workers 417,000 (Total); A. Agriculture
47.3%; own-account workers 675,000 = 62.7%; paid employees urban male 96,000.
"""
from __future__ import annotations

import re

import pdfplumber

from . import _common as C

SURVEY = "Liberia Labour Force Survey 2010"
_CELL = r"(?:[\d,]+(?:\.\d+)?|\*|‐|-)"
_ROW = re.compile(rf"^(.+?)\s+({_CELL}(?:\s+{_CELL}){{8}})\s*$")
_COLS = [(loc, lab, sex)
         for loc, lab in (("urban", "Urban"), ("rural", "Rural"), ("all", "Total"))
         for sex in ("male", "female", "total")]
_TABLES = [
    (r"^Table 4\.2 Employed persons aged 15 and over, by sex, locality and main occupation",
     "occupation", "ISCO-08", "LBR-LFS2010 T4.2", 10),
    (r"^Table 4\.4 Employed persons aged 15 and over, by sex, locality, and sector",
     "industry", "ISIC Rev.4", "LBR-LFS2010 T4.4", 22),
    (r"^Table 4\.6 Employed persons aged 15 and over by sex, locality and status",
     "employment_status", "National", "LBR-LFS2010 T4.6", 6),
]
_HEADER = re.compile(r"^(Occupation|major group|Male Female|ISCO|ISIC|Sector of|"
                     r"economic activity|Status in employment|Urban Rural)", re.I)


def _num(tok: str):
    if tok in ("*", "‐", "-"):
        return None
    return float(tok.replace(",", ""))


def _table_lines(pages: list[str], caption: str) -> list[str]:
    cap = re.compile(caption, re.M)
    for i, text in enumerate(pages):
        m = cap.search(text)
        if m:
            # a table may run onto the next page (4.2's percentages do)
            body = text[m.end():] + "\n" + (pages[i + 1] if i + 1 < len(pages) else "")
            return [ln.strip() for ln in body.splitlines()]
    raise ValueError(f"LBR LFS 2010: {caption!r} not found")


def parse_2010(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages[45:60]]
    out = []
    for caption, topic, scheme, code, expect in _TABLES:
        lines = _table_lines(pages, caption)
        block, counts, shares = "count", [], []
        for ln in lines:
            if re.fullmatch(r"(%\s*){9}", ln):
                block = "share"
                continue
            if _HEADER.match(ln):
                continue
            m = _ROW.match(ln)
            if not m:
                continue
            label, cells = m.group(1).strip(), m.group(2).split()
            (counts if block == "count" else shares).append((label, cells))
            if label == "Total":
                if block == "share":
                    break
                # Table 4.6 prints its percentages straight after the count
                # Total, with no "% % %" line between
                block = "share"
        if len(counts) < expect or len(shares) < expect:
            raise ValueError(f"{code}: read {len(counts)} count / {len(shares)} share "
                             f"rows, expected {expect}")
        if [l for l, _ in counts] != [l for l, _ in shares]:
            raise ValueError(f"{code}: count and share labels differ")
        for rows, measure, unit in ((counts, "count", "persons"),
                                    (shares, "share", "percent")):
            for label, cells in rows:
                for (loc, loc_label, sex), tok in zip(_COLS, cells):
                    v = _num(tok)
                    if v is None:
                        continue
                    out.append(C.row(
                        topic=topic, characteristic=label, classification=scheme,
                        value=v, survey=SURVEY, period="2010",
                        reference_period="February-May 2010", frequency="ad_hoc",
                        measure=measure, unit=unit, sex=sex, locality=loc,
                        locality_label=loc_label, working_age_base="15+",
                        series_code=code))
    return out
