"""Nigeria MPI 2022 -- Appendix D, read cell by cell.

The body tables (`nigeria_mpi.LAYOUT`) give the national, area, zone,
disability and age headlines. Appendix D reprints those AND carries what the
body leaves out: every State (D6), all 109 senatorial districts (D7), and the
whole Nigeria CHILD MPI (D27, D30-D34). Each row prints

    label | MPI  lo  hi | H  lo  hi | A  lo  hi | population share | number poor

and PyMuPDF yields ONE CELL PER LINE, so a row is its label lines followed by
exactly eleven numeric cells. Labels wrap ("Akwa \\nIbom", "Adamawa \\nCentral")
and are rejoined.

TAKEN: M0, H and A with their 95% confidence bounds (the schema names each
bound's subject: `index_M0_ci_low` ...). NOT TAKEN: the population share (a
share of Nigeria's population, not an MPI measure) and the number of poor --
printed in MILLIONS (D4-D6, D30-D32) or THOUSANDS (D7, D33), while
`population_poor` is a count of persons; rescaling would be computing.

FOR THE CUTS THE BODY ALREADY PRINTS (D4 area, D5 zone, D8 disability, D9 age)
only the confidence bounds are new; the point values are CHECKED EQUAL to what
the body layout emits and not emitted twice (they would share a merge key).

THE CHILD MPI IS A DIFFERENT MEASURE, not a breakdown: children aged 0-4,
5 dimensions (Child survival and development added), 23 indicators (the 15 of
the Nigeria MPI plus 8 child indicators -- birth attendance, playground, child
engagement, child care, breastfeeding, supplement, immunisation, severe
undernutrition; D37's column headers list all 23), and k = 21% (D27: "k
value=21%"). Its rows carry age_group "0-4" and their own methodology fields.

FCT ABUJA is both a State and its single senatorial district, printed
identically in D6/D7 (and D32/D33); emitted once, as the State.

PUBLISHED DEFECT: D7 prints "Osun West" twice with identical cells (110 rows
for 109 districts); kept once, and a repeat with different values raises.

GUARDS: every table must yield its printed number of rows (D6: 37, D7: 109);
every bound must bracket its value; M0 must agree with H x A / 100 to printed
rounding (a CHECK only -- M0 is read, never computed); and no geography name
may be shared by a State and a senatorial district.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF

from . import _common as C

_NUM = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
_FURNITURE = {"Appendix D: Tables", "Nigeria Multidimensional Poverty Index (2022)"}
_POINT = ("index_M0", "incidence_H", "intensity_A")
_METHOD_MPI = dict(mpi_type="national", measure_name="Nigeria MPI",
                   survey="MPIS 2021/2022 (Multidimensional Poverty Index Survey)",
                   k_cutoff=25, n_dimensions=4, n_indicators=15)
_METHOD_CHILD = dict(mpi_type="national", measure_name="Nigeria Child MPI",
                     survey="MPIS 2021/2022 (Multidimensional Poverty Index Survey)",
                     k_cutoff=21, n_dimensions=5, n_indicators=23)


def _lines_from(doc, code: str) -> list[str]:
    """The table's lines from its caption to its 'Note:', across pages,
    with the running head, page numbers and repeated column headers removed."""
    cap = re.compile(rf"^{re.escape(code)}\s")
    out, started = [], False
    for pno in range(len(doc)):
        lines = [ln.strip() for ln in doc[pno].get_text().splitlines()]
        if not started:
            idx = next((i for i, ln in enumerate(lines) if cap.match(ln)), None)
            if idx is None:
                continue
            started, lines = True, lines[idx + 1:]
        else:
            # Page number, running head: the first lines of a continuation page.
            while lines and (lines[0] in _FURNITURE or re.fullmatch(r"\d{1,3}", lines[0])
                             or not lines[0]):
                lines = lines[1:]
        # The column header ends at the last "interval (95%)" line.
        hdr = [i for i, ln in enumerate(lines[:30]) if ln == "interval (95%)"]
        if hdr:
            lines = lines[hdr[-1] + 1:]
        for ln in lines:
            if ln.startswith("Note") or re.match(r"^D\d+\.\s", ln):
                return out
            if ln:
                out.append(ln)
    raise ValueError(f"Nigeria MPI {code}: caption or its Note not found")


def _rows(doc, code: str) -> list[tuple[str, list[float]]]:
    toks: list[str] = []
    for ln in _lines_from(doc, code):
        parts = ln.split()
        toks += parts if all(_NUM.match(p) for p in parts) else [ln]
    rows, label, i = [], [], 0
    while i < len(toks):
        t = toks[i]
        if _NUM.match(t):
            if not label:
                raise ValueError(f"Nigeria MPI {code}: number {t!r} with no label")
            cells = toks[i:i + 11]
            if len(cells) < 11 or not all(_NUM.match(c) for c in cells):
                raise ValueError(f"Nigeria MPI {code} {' '.join(label)!r}: "
                                 f"expected 11 cells, got {cells}")
            vals = [float(c.replace(",", "")) for c in cells]
            rows.append((" ".join(label), vals))
            label, i = [], i + 11
        else:
            label.append(t)
            i += 1
    if label:
        raise ValueError(f"Nigeria MPI {code}: trailing label {label}")
    return rows


def _check(code: str, label: str, v: list[float]) -> None:
    for j in (0, 3, 6):
        if not (v[j + 1] <= v[j] <= v[j + 2]):
            raise ValueError(f"Nigeria MPI {code} {label!r}: bound does not "
                             f"bracket its value {v[j:j + 3]}")
    if abs(v[0] - v[3] * v[6] / 1e4) > 0.006:
        raise ValueError(f"Nigeria MPI {code} {label!r}: MPI {v[0]} != H x A "
                         f"({v[3]} x {v[6]}) to printed rounding")


# PUBLISHED BOUNDS PAST 100%. NBS's intervals are symmetric (normal
# approximation), so near 100% an upper bound can exceed it: the Child MPI's H
# for Bayelsa West (97.4 +/- ..., printed 100.5) and Borno North (101.1).
# A share above 100 is not a valid percentage, and the schema refuses it; the
# two cells are left out BY NAME, and any other out-of-range bound raises.
_BOUNDS_OVER_100 = {("D33.", "Bayelsa West", "incidence_H_ci_high"),
                    ("D33.", "Borno North", "incidence_H_ci_high")}


def _emit(code, label, v, method, points, **ctx):
    names = []
    for j, m in zip((0, 3, 6), _POINT):
        if points:
            names.append((m, v[j]))
        names += [(f"{m}_ci_low", v[j + 1]), (f"{m}_ci_high", v[j + 2])]
    kept = []
    for m, val in names:
        if m.startswith(("incidence_H", "intensity_A")) and not 0 <= val <= 100:
            if (code, label, m) not in _BOUNDS_OVER_100:
                raise ValueError(f"Nigeria MPI {code} {label!r}: {m} {val} "
                                 f"outside 0..100 and not a known published bound")
            continue
        kept.append((m, val))
    names = kept
    return [C.row(metric=m, value=val, period="2022",
                  reference_period="MPIS 2021/2022", frequency="ad_hoc",
                  unit_of_analysis="person", series_code=f"NBS MPI {code}",
                  **method, **ctx)
            for m, val in names]


# As the body layout's _vocab entries: Urban / Rural carry topic "locality".
_AREA = {"National": {},
         "Rural": {"locality": "rural", "locality_label": "Rural", "topic": "locality",
                   "characteristic": "Rural"},
         "Urban": {"locality": "urban", "locality_label": "Urban", "topic": "locality",
                   "characteristic": "Urban"}}
_DISAB = {"No PLWDs": "No person living with a disability",
          "With PLWDs": "At least one person living with a disability"}


def _ctx(kind: str, label: str) -> dict:
    if kind == "area":
        if label not in _AREA:
            raise ValueError(f"Nigeria MPI: unknown area {label!r}")
        return dict(_AREA[label])
    if kind == "geo":
        return {"geography": label}
    if kind == "disability":
        if label not in _DISAB:
            raise ValueError(f"Nigeria MPI: unknown disability row {label!r}")
        return {"topic": "disability", "characteristic": _DISAB[label]}
    if kind == "age":
        lab = label.replace("–", "-")
        return {"topic": "age", "age_group": lab, "characteristic": lab}
    raise ValueError(kind)


# code -> (cut, child?, emit point values?, expected rows)
_TABLES = [
    ("D4.", "area", False, False, 3),
    ("D5.", "geo", False, False, 6),
    ("D6.", "geo", False, True, 37),
    ("D7.", "geo", False, True, 109),   # FCT emitted via D6
    ("D8.", "disability", False, False, 2),
    ("D9.", "age", False, False, 3),    # 0-17, 18+ (body) and Under 5 (new)
    ("D30.", "area", True, True, 3),
    ("D31.", "geo", True, True, 6),
    ("D32.", "geo", True, True, 37),
    ("D33.", "geo", True, True, 109),
    ("D34.", "disability", True, True, 2),
]


def parse_appendix(path: str, body_points: dict) -> list[dict]:
    """`body_points` maps (geography, locality, topic, characteristic,
    age_group, metric) -> value for the Nigeria MPI rows the body layout
    already emits, so a repeated point can be checked and left out."""
    doc = fitz.open(path)
    out, geo_kind = [], {}
    for code, cut, child, points, n in _TABLES:
        rows = _rows(doc, code)
        # D7 PRINTS "Osun West" TWICE -- in the Osun block and again after
        # Rivers West -- all eleven cells identical (110 rows for 109
        # districts; the child table D33 has the 109). An exact repeat is kept
        # once; a repeated label with DIFFERENT values would be a mislabelled
        # district and raises.
        seen: dict[str, list[float]] = {}
        uniq = []
        for label, v in rows:
            if label in seen:
                if seen[label] != v:
                    raise ValueError(f"Nigeria MPI {code}: {label!r} printed "
                                     f"twice with different values")
                continue
            seen[label] = v
            uniq.append((label, v))
        rows = uniq
        if len(rows) != n:
            raise ValueError(f"Nigeria MPI {code}: {len(rows)} rows, expected {n}")
        method = _METHOD_CHILD if child else _METHOD_MPI
        for label, v in rows:
            _check(code, label, v)
            ctx = _ctx(cut, label)
            if child:
                ctx.setdefault("age_group", "0-4")
            if cut == "geo" and code in ("D6.", "D7.", "D32.", "D33."):
                kind = "state" if code in ("D6.", "D32.") else "district"
                # FCT ABUJA is ONE senatorial district covering the whole
                # territory, so it is printed as a State AND as a district with
                # the same nine cells. Emitted once (as the State); any other
                # shared name, or the FCT with different cells, raises.
                prev = geo_kind.get((child, label))
                if prev and prev[0] != kind:
                    if prev[1] != v[:9]:
                        raise ValueError(f"Nigeria MPI {code}: {label!r} is both "
                                         f"a State and a district, with "
                                         f"different values")
                    continue
                geo_kind[(child, label)] = (kind, v[:9])
            emit_points = points
            if not points:
                key = (ctx.get("geography", "Total country"),
                       ctx.get("locality", "all"), ctx.get("topic", "total"),
                       ctx.get("characteristic", "Total"),
                       ctx.get("age_group", "Total"))
                have = [body_points.get(key + (m,)) for m in _POINT]
                if all(h is None for h in have):
                    # A cut the body never prints (D9's "Under 5"): new rows.
                    emit_points = True
                else:
                    for j, m, h in zip((0, 3, 6), _POINT, have):
                        if h != v[j]:
                            raise ValueError(f"Nigeria MPI {code} {label!r}: {m} "
                                             f"{v[j]} differs from the body "
                                             f"table's {h}")
            out += _emit(code, label, v, method, emit_points, **ctx)
    return out
