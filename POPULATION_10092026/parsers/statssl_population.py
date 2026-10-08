"""Stats SL Sierra Leone — 2015 census national population by sex (Tier-2 docx).

Parser for the Word document "Sierra Leone 2015 population census data for 16
districts / 5 regions". Its tables list chiefdom populations (REGION | DISTRICT |
CHIEFDOM | MALE | FEMALE | TOTAL) but the chiefdom coverage is incomplete and the
region subtotals mix old (4-region) and new (5-region incl. North-West) boundaries,
so the sub-national detail does NOT reconcile to the national total. We therefore
emit only the authoritative national row ("SIERRA LEONE" = 7,092,113), which is the
published 2015 PHC total. Sub-national/age detail is left out (not reconciled).
"""
from __future__ import annotations
import re
from docx import Document
import pandas as pd


def _num(cell):
    s = re.sub(r"[^\d]", "", str(cell))
    return int(s) if s else None


_REGIONS = ("EASTERN", "NORTH EAST", "NORTH WEST", "SOUTH", "WESTERN")


def _mtphc2021(path: str) -> list[dict]:
    """2021 Digital Mid-Term Census, "Final results by district" (added
    2026-10-06): male / female / total and sex ratio for the 16 districts, the
    five regions' "REGIONAL TOTAL" rows and the NATIONAL TOTAL (7,548,702).

    PyMuPDF yields one cell per line, so the table is read as a stream: a
    region heading, then name + four values per district, then the region's
    total. Every district block must sum to its printed regional total, the
    regions to the national total, and every row satisfy Male + Female = Total.
    Regions and districts are both collected, under distinct names ("<Region>
    Region" for the totals), as the README asks for overlapping geographies:
    never sum all geographies together.
    """
    import fitz
    with fitz.open(path) as doc:
        lines = [ln.strip() for p in doc for ln in p.get_text().splitlines()
                 if ln.strip()]
    if not any("MID-TERM CENSUS FINAL RESULTS BY DISTRICT" in ln for ln in lines):
        raise ValueError(f"{path}: not the 2021 MTPHC district results")
    val = lambda s: float(s.replace(",", ""))
    is_num = lambda s: bool(re.fullmatch(r"[\d,]+(\.\d)?", s))
    start = lines.index("SEX RATIO") + 1
    regions, cur, nat = [], None, None
    i = start
    while i < len(lines):
        s = lines[i]
        nums = [lines[j] for j in range(i + 1, min(i + 5, len(lines)))]
        if s in _REGIONS:
            cur = {"name": s, "districts": [], "total": None}
            regions.append(cur)
            i += 1
        elif s in ("REGIONAL TOTAL", "NATIONAL TOTAL") and all(map(is_num, nums)):
            row = tuple(val(x) for x in nums)
            if s == "NATIONAL TOTAL":
                nat = row
                break
            cur["total"] = row
            i += 5
        elif cur is not None and all(map(is_num, nums)):
            cur["districts"].append((s, tuple(val(x) for x in nums)))
            i += 5
        else:
            i += 1
    if nat is None or len(regions) != 5 or sum(len(r["districts"]) for r in regions) != 16:
        raise ValueError("2021 MTPHC: expected 5 regions, 16 districts and a "
                         "national total")
    out = []

    def emit(geo, row):
        m, f, t, ratio = row
        if m + f != t:
            raise ValueError(f"2021 MTPHC {geo}: {m} + {f} != {t}")
        for sex, v in (("male", m), ("female", f), ("total", t)):
            out.append({"series_type": "census", "sex": sex, "age_group": "Total",
                        "geography": geo, "period": "2021", "frequency": "annual",
                        "measure": "count", "value": v, "unit": "persons",
                        "series_code": "SL_MTPHC2021"})
        out.append({"series_type": "census", "sex": "total", "age_group": "Total",
                    "geography": geo, "period": "2021", "frequency": "annual",
                    "measure": "sex_ratio", "value": ratio, "unit": "ratio",
                    "series_code": "SL_MTPHC2021"})

    for r in regions:
        for k in range(3):
            if sum(d[1][k] for d in r["districts"]) != r["total"][k]:
                raise ValueError(f"2021 MTPHC {r['name']}: districts do not sum "
                                 f"to the regional total")
        for name, row in r["districts"]:
            emit(name, row)
        emit(f"{r['name'].title()} Region", r["total"])
    for k in range(3):
        if sum(r["total"][k] for r in regions) != nat[k]:
            raise ValueError("2021 MTPHC: regions do not sum to the national total")
    emit("Total country", nat)
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    base = _parse_2015(local_path)
    rows = []
    for p in extras or []:
        rows += _mtphc2021(p)
    return pd.concat([base, pd.DataFrame(rows)], ignore_index=True) if rows else base


def _parse_2015(local_path: str) -> pd.DataFrame:
    doc = Document(local_path)
    national = None
    for tbl in doc.tables:
        for r in tbl.rows:
            cells = [c.text.strip() for c in r.cells]
            if len(cells) < 6:
                continue
            if cells[2].strip().upper() != "SIERRA LEONE":
                continue
            male, female, total = _num(cells[3]), _num(cells[4]), _num(cells[5])
            if None in (male, female, total) or abs(male + female - total) > 5:
                continue
            national = (male, female, total)
            break
        if national:
            break

    if national is None:
        raise ValueError("statssl_population: national 'SIERRA LEONE' row not found")

    out = []
    for sex, v in (("male", national[0]), ("female", national[1]), ("total", national[2])):
        out.append({
            "series_type": "census", "sex": sex, "age_group": "Total",
            "geography": "Total country", "period": "2015", "frequency": "annual",
            "measure": "count", "value": float(v), "unit": "persons",
            "series_code": "SL_PHC2015",
        })
    return pd.DataFrame(out)
