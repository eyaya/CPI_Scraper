"""ANSD Senegal -- "Projections démographiques 2023-2050" workbook (RGPH-5
based, posted 2024-11): population by region and département x sex
(HOMME / FEMME / ENSEMBLE), one column triple per year.

Added 2026-10-13 as a SECOND Senegal descriptor (senegal_projections.yaml)
beside the RGPH-5 Chapter 1 report.

The first triple is headed "RGPH-5 2023" -- the census count the projection
starts from -- and is filed as series_type census; 2024-2050 are projection.
The workbook has no national row; the 14 regions sum to the RGPH-5 national
total (18,126,390) in 2023 (checked) and no national figure is computed.

Geography names are printed with their level ("REGION DAKAR", "DEPARTEMENT DE
DAKAR") and kept so -- region and département names collide otherwise.
Internal runs of spaces are collapsed. Never sum regions with départements.

Checks: HOMME + FEMME = ENSEMBLE in every cell triple; each region's
départements sum to it every year (within 5, rounding).

EXTRA (the report "Projections démographiques 2023-2073", same page): its
national table "PROJECTION DE LA POPULATION RESIDENTE DU SENEGAL DE 2023 A
2073" (HOMME / FEMME / TOTAL, every year), filed as projection under "Total
country". Its 2023 row (9 178 894 / 8 947 496) is the projection base, not
the census count (9 178 896 / 8 947 494), so it stays projection beside the
census row. Figures use space-thousand separators (and, for 2024-2026, none);
words are rejoined by x-gap and every row must satisfy HOMME + FEMME = TOTAL
(within 5 -- 24 of the 51 rows are off by 1-3, rounding, kept as printed)
and grow year on year. Its age-target tables and commune annexes are not read.
"""
from __future__ import annotations

import re

import fitz
import openpyxl
import pandas as pd

_SC = "ANSD_PROJ_2023_2050"
_SC_NAT = "ANSD_PROJ_2023_2073_NATIONAL"
_GAP = 4.5
_NAT_2023 = 18126390


def _national(path: str) -> list[dict]:
    rows: dict[str, list[float]] = {}
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text("text")
            if not ("ANNEES" in text and "HOMME" in text and "TOTAL" in text):
                continue
            ws = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
            lines: list[list] = []
            for x0, y0, x1, y1, w, *_ in ws:
                # a figure can be ONE word with (non-breaking) spaces inside
                # ("9 178 894") or several words ("9 178 894" split): both
                w = re.sub(r"\s", "", w)
                y = (y0 + y1) / 2
                if lines and y - lines[-1][0] <= 2.5:
                    lines[-1][1].append((x0, x1, w))
                else:
                    lines.append([y, [(x0, x1, w)]])
            for _, words in lines:
                words.sort()
                if not re.fullmatch(r"20[2-7]\d", words[0][2]) or len(words) < 4 \
                        or not all(w.isdigit() for _, _, w in words):
                    continue
                nums: list[list] = []
                for x0, x1, w in words[1:]:
                    if nums and x0 - nums[-1][1] < _GAP and len(w) == 3:
                        nums[-1] = [nums[-1][0], x1, nums[-1][2] + w]   # split figure
                    else:
                        nums.append([x0, x1, w])
                if len(nums) != 3:
                    raise ValueError(f"ANSD national {words[0][2]}: {nums}")
                h, f, t = (float(n[2]) for n in nums)
                if abs(h + f - t) > 5:      # rounding: off by 1-3 in 24 of 51 rows
                    raise ValueError(f"ANSD national {words[0][2]}: {h} + {f} != {t}")
                if words[0][2] in rows:
                    raise ValueError(f"ANSD national {words[0][2]}: read twice")
                rows[words[0][2]] = [h, f, t]
    years = [str(y) for y in range(2023, 2074)]
    if sorted(rows) != years:
        raise ValueError(f"ANSD national: years {sorted(rows)[:3]}..{len(rows)}")
    if any(rows[b][2] <= rows[a][2] for a, b in zip(years, years[1:])):
        raise ValueError("ANSD national: total does not grow")
    return [{"series_type": "projection", "sex": sex, "age_group": "Total",
             "geography": "Total country", "period": y, "frequency": "annual",
             "measure": "count", "value": v, "unit": "persons",
             "series_code": _SC_NAT}
            for y in years for sex, v in zip(("male", "female", "total"), rows[y])]


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    wb = openpyxl.load_workbook(local_path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    head, sexes = rows[0], rows[1]
    years: list[tuple[int, str, str]] = []      # (col, year, series_type)
    for c, v in enumerate(head):
        if v is None or c == 0:
            continue
        m = re.search(r"(20\d\d)", str(v))
        if not m:
            raise ValueError(f"ANSD projection: header {v!r}")
        if [str(s).strip().upper() for s in sexes[c:c + 3]] != ["HOMME", "FEMME", "ENSEMBLE"]:
            raise ValueError(f"ANSD projection {v}: sex columns {sexes[c:c + 3]}")
        years.append((c, m.group(1), "census" if "RGPH" in str(v) else "projection"))
    if [y for _, y, _ in years] != [str(y) for y in range(2023, 2051)] \
            or years[0][2] != "census":
        raise ValueError(f"ANSD projection: years {[y for _, y, _ in years]}")
    out, region = [], None
    reg_sum: dict[tuple[str, str], float] = {}
    dep_sum: dict[tuple[str, str], float] = {}
    nat: dict[str, float] = {}
    for r in rows[2:]:
        if not r or r[0] is None or not str(r[0]).strip():
            continue
        geo = re.sub(r"\s+", " ", str(r[0])).strip()
        if geo.startswith("REGION"):
            region = geo
        elif not geo.startswith("DEPARTEMENT"):
            raise ValueError(f"ANSD projection: row {geo!r}")
        for c, y, st in years:
            h, f, e = (float(r[c + k]) for k in range(3))
            if h + f != e:
                raise ValueError(f"ANSD projection {geo} {y}: {h} + {f} != {e}")
            if geo is region:
                reg_sum[(geo, y)] = e
                nat[y] = nat.get(y, 0) + e
            else:
                dep_sum[(region, y)] = dep_sum.get((region, y), 0) + e
            for sex, v in (("male", h), ("female", f), ("total", e)):
                out.append({"series_type": st, "sex": sex, "age_group": "Total",
                            "geography": geo, "period": y, "frequency": "annual",
                            "measure": "count", "value": v, "unit": "persons",
                            "series_code": _SC})
    if len({g for g, _ in reg_sum}) != 14:
        raise ValueError(f"ANSD projection: {len({g for g, _ in reg_sum})} regions")
    for k, v in reg_sum.items():
        if abs(dep_sum.get(k, 0) - v) > 5:      # rounded départements
            raise ValueError(f"ANSD projection {k}: départements {dep_sum.get(k)} != {v}")
    if nat["2023"] != _NAT_2023:
        raise ValueError(f"ANSD projection: 2023 regions {nat['2023']} != RGPH-5 {_NAT_2023}")
    for ex in extras or []:
        if ex.lower().endswith(".pdf"):
            nat_rows = _national(ex)
            # the report's regional split is the workbook's: 2050 must agree
            t2050 = next(r["value"] for r in nat_rows
                         if r["period"] == "2050" and r["sex"] == "total")
            if abs(t2050 - nat["2050"]) > 30:
                raise ValueError(f"ANSD: report 2050 {t2050} vs workbook regions {nat['2050']}")
            out += nat_rows
    return pd.DataFrame(out)
