"""Mali — INSTAT EMOP table workbooks ("tab-emop<YY>pas<N>_eq.xlsx"), chapter 4
"Emploi": the underutilisation tables, one reading a year, 2020-2025.

WHY THESE AND NOT ONLY THE BULLETIN. The labour-market bulletin
(`mali_pdf_bulletin`) gives nine national figures for 2021-2022 and draws every
breakdown as a chart. INSTAT's EMOP workbooks -- the same files `labour/` reads
for composition -- TABULATE the ILO underutilisation ladder every year, by
region, milieu, sex and age, and for the youth band:

* Tab4.2  SU1 (taux de chômage BIT), SU2, SU3, SU4 for the 15+, by région,
          milieu (Urbain with its Bamako / Autres villes sub-strata, Rural),
          sexe and groupe d'âge;
* Tab4.3  the same four rates for the 15-24 ("des jeunes (15-24 ans)") by
          région, milieu and sexe;
* Tab4.8  NEET rates for the 15-24 and 15-35, by région, milieu and sexe.

TOPICS, as elsewhere in this corpus: SU1 -> `unemployment_rate` (strict);
SU2-SU4 -> `labour_underutilisation_rate` (broad); SU1 for a youth band ->
`youth_unemployment_rate`, never ALSO `unemployment_rate` (the Angola / Niger
convention); NEET -> `neet_rate`, band in `age_group`.

THE YOUTH NATIONAL ROW IS PRINTED TWICE -- Tab4.2's "15 à 24 ans" row and
Tab4.3's "Ensemble" -- and they must agree; they are checked equal and emitted
once (from Tab4.2). A disagreement raises rather than shipping two values for
one merge key.

DATING: the employment module is fielded April-June (passage 2 from 2021,
passage 1 in 2020), so each workbook is one reading dated YYYY-Q2, frequency
annual. The year comes from INSTAT's file name and is checked against the
workbook's source lines by majority (2022's Tab4.5 source line says "EMOP
2021" -- one slip must not re-date a table). THIS IS NOT THE BULLETIN'S
SERIES: the bulletin's 2,4% is a 2021-2022 survey reading dated 2022 (annual);
EMOP 2022-Q2's SU1 is 5,39. Different instruments, different periods, both
kept as published.

GUARDS, per row: the ladder must be ordered as the ILO defines it (SU2 >= SU1,
SU3 >= SU1, SU4 >= SU2 and SU3, to rounding); the national SU1 must lie between
its male and female values. Either failure raises -- the same class of check
that caught 2023's copied national row in `labour/`.

REGIONS ARE KEPT AS PRINTED: 9 to 2021, 11 in 2022-23, 20 from 2024, spellings
varying across years (Taoudénit / Taoudenni). Kidal, Ménaka, Nara, Douentza and
Bandiagara are partial-coverage (the workbook's Infos sheet).

NOT COLLECTED: Tab4.1 (structure of the 15+ by activity status -- shares of
the population, `labour/`'s activity_status territory); Tab4.4 (children
5-17); Tab4.8's "taux d'emplois vulnérables" (no topic); Tab4.9 (a trend digest
that repeats earlier years and carries a copied 2023 row).

CROSS-CHECK (Ensemble SU1 / SU4): 2020 4,2 / 13,1; 2021 6,1 / 16,89; 2022
5,39 / 15,51; 2023 4,68 / 13,74; 2024 5,69 / 14,84; 2025 5,28 / 14,51. Youth
15-24 SU1 2025: 8,61. NEET 15-24 2025: 26,03.
"""
from __future__ import annotations

import os
import re
from collections import Counter

import openpyxl

_SURVEY = "Enquête Modulaire et Permanente auprès des Ménages (EMOP)"
_FILE_RE = re.compile(r"tab-emop(\d\d)pas(\d)", re.I)
_SRC_RE = re.compile(r"EMOP[\s-]*(20\d\d),?\s*passage\s*(\d)\s*\(([^)]*)\)", re.I)
_SECTIONS = {"région": "geography", "milieu": "locality", "sexe": "sex",
             "groupe d'âge": "age"}
_SU_TOPIC = ["unemployment_rate", "labour_underutilisation_rate",
             "labour_underutilisation_rate", "labour_underutilisation_rate"]
_SU_DEF = ["strict", "broad", "broad", "broad"]
_YOUTH = {"15-24"}   # INSTAT's own youth band: Tab4.3 "jeunes (15-24 ans)"


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s).replace("’", "'")).strip()


def _label(s) -> str:
    return _norm(s).lstrip("'‘").strip()


def _age(label: str) -> str:
    """'15 à 24 ans' -> '15-24'; '65 ans et plus' -> '65+' (band as printed)."""
    t = label.lower()
    m = re.fullmatch(r"(\d+) à (\d+) ans", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.fullmatch(r"(\d+) ans et plus", t)
    if m:
        return f"{m.group(1)}+"
    raise ValueError(f"EMOP: unreadable age band {label!r}")


def _date(path: str, wb) -> tuple[str, str]:
    m = _FILE_RE.search(os.path.basename(path))
    if not m:
        raise ValueError(f"EMOP: cannot date {path!r} from INSTAT's file name")
    year = f"20{m.group(1)}"
    hits = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for v in row:
                if isinstance(v, str) and v.strip().startswith("Source"):
                    s = _SRC_RE.search(v)
                    if s:
                        hits.append((s.group(1), s.group(2), s.group(3).strip()))
    if not hits:
        raise ValueError(f"EMOP {year}: no source line")
    (y, passage, months), _ = Counter(hits).most_common(1)[0]
    if y != year or passage != m.group(2):
        raise ValueError(f"EMOP: file says {year} passage {m.group(2)}, source "
                         f"lines say {y} passage {passage}")
    if not re.match(r"avril\s*-\s*juin", months, re.I):
        raise ValueError(f"EMOP {year}: module fielded {months!r}, not April-June")
    return year, f"EMOP {year}, passage {passage} ({months.lower()})"


def _sheet(ws, where: str):
    """(caption, headers, [(section, label, values)]) for one sheet."""
    rows = [r for r in ws.iter_rows(values_only=True)
            if any(v is not None for v in r)]
    caption = _norm(next(v for v in rows[0] if v is not None))
    lab_col = next(r.index(v) for r in rows[1:] for v in r
                   if isinstance(v, str) and _norm(v).lower() == "région")
    body = [r[lab_col:] for r in rows[1:]]
    headers = [_norm(v) for v in body[0] if v is not None
               and not re.match(r"(Région|Caractéristiques)", _norm(v))]
    first = next(r for r in body[1:] if any(isinstance(v, (int, float)) for v in r))
    vcols = [i for i, v in enumerate(first) if isinstance(v, (int, float))]
    if len(vcols) != len(headers):
        raise ValueError(f"{where}: {len(headers)} headers for {len(vcols)} values")
    section, out = None, []
    for r in body[1:]:
        lab = r[0]
        if lab is None or _norm(lab).startswith("Source"):
            continue
        vals = [r[i] if i < len(r) else None for i in vcols]
        # INSTAT stores some zeros as the TEXT "0".
        vals = [float(v) if isinstance(v, str) and re.fullmatch(r"\d+(\.\d+)?", v.strip())
                else v for v in vals]
        key = _norm(lab).lower()
        if all(v is None for v in vals):
            if key not in _SECTIONS:
                raise ValueError(f"{where}: unknown section {lab!r}")
            section = _SECTIONS[key]
            continue
        if key in ("ensemble", "total"):
            section = None
        out.append((section, _label(lab), vals))
    return caption, headers, out


def _ctx(section, label, where):
    if section == "geography":
        return {"geography": label}
    if section == "locality":
        return {"locality": "rural" if label == "Rural" else "urban",
                "locality_label": label}
    if section == "sex":
        return {"sex": {"masculin": "male", "féminin": "female"}[label.lower()]}
    if section == "age":
        return {"age_group": _age(label)}
    if section is None and label in ("Ensemble", "Total"):
        return {}
    raise ValueError(f"{where}: row {label!r} outside any section")


_TOL = 0.06
# Notes on what was refused and why, per workbook -- surfaced by parse() so a
# run says what it left out instead of silently thinning the table.
DROPPED: list[str] = []


def _ladder_ok(v) -> bool:
    su1, su2, su3, su4 = v
    return (su2 >= su1 - _TOL and su3 >= su1 - _TOL
            and su4 >= max(su2, su3) - _TOL)


def _clean(rows, where):
    """Drop what the table's own identities prove misprinted.

    1. A row whose ladder is out of order (SU3 < SU1 is impossible by
       definition) is dropped -- 2021 Koulikoro and Gao, 2022 Gao and Kidal.
    2. Two rows of one section with identical values are BOTH dropped: one is a
       copy and nothing says which (2023: "65 ans et plus" repeats "15 à 34
       ans"). Bamako as a région and as a milieu stratum is the same population
       and is legitimately identical -- the check is within a section only.
    3. Every partition (sexes; Urbain/Rural; the régions; 15-34/35+) must
       bracket the national value on every rate. A block that cannot is
       dropped whole (2024: régions, milieu and sexes all lie below an
       Ensemble that the age split and Tab4.9's trend both confirm).
    4. A parent age band must lie between its sub-bands (15-34 within 15-24 and
       25-34; 35+ within 35-64 and 65+); otherwise the age block is dropped
       (2022: the age rows are shifted one row down).
    The national row itself must pass (1), or the whole table is refused for
    that year (2021 Tab4.3: SU4 18,19 below SU2 18,62).
    """
    kept = []
    for sec, lab, v in rows:
        if not _ladder_ok(v):
            DROPPED.append(f"{where} {lab!r}: ladder out of order {fmt(v)}")
            if sec is None:
                DROPPED.append(f"{where}: the NATIONAL ladder is out of order "
                               f"-- table refused for this year")
                return []
            continue
        kept.append((sec, lab, v))
    by_sec: dict = {}
    for sec, lab, v in kept:
        by_sec.setdefault(sec, []).append((lab, v))
    for sec, items in by_sec.items():
        if sec is None:
            continue
        seen: dict = {}
        for lab, v in items:
            seen.setdefault(tuple(round(x, 6) for x in v), []).append(lab)
        for labs in seen.values():
            if len(labs) > 1:
                DROPPED.append(f"{where}: {labs} print identical values -- "
                               f"a copy, both dropped")
                kept = [k for k in kept if not (k[0] == sec and k[1] in labs)]
    nat = next((v for s_, l, v in kept if s_ is None), None)
    if nat is None:
        return kept

    def block(sec, labels=None):
        return [(l, v) for s_, l, v in kept
                if s_ == sec and (labels is None or l in labels)]

    partitions = {
        "sex": block("sex"),
        "locality": block("locality", {"Urbain", "Rural"}),
        "geography": block("geography"),
        "age": block("age", {"15 à 34 ans", "35 ans et plus"}),
    }
    bad = set()
    for sec, items in partitions.items():
        if len(items) < 2:
            continue
        for k in range(4):
            vals = [v[k] for _, v in items]
            if not min(vals) - _TOL <= nat[k] <= max(vals) + _TOL:
                bad.add(sec)
    ages = {l: v for l, v in block("age")}
    for parent, kids in (("15 à 34 ans", ("15 à 24 ans", "25 à 34 ans")),
                         ("35 ans et plus", ("35 à 64 ans", "65 ans et plus"))):
        if parent in ages and all(k in ages for k in kids):
            for k in range(4):
                lo = min(ages[c][k] for c in kids)
                hi = max(ages[c][k] for c in kids)
                if not lo - _TOL <= ages[parent][k] <= hi + _TOL:
                    bad.add("age")
    for sec in sorted(bad):
        DROPPED.append(f"{where}: the {sec} block cannot bracket the national "
                       f"value -- dropped whole")
    return [k for k in kept if k[0] not in bad]


def fmt(v):
    return [round(x, 2) for x in v]


def _row(base, ctx, **kw):
    r = {"sex": "total", "age_group": "Total", "education": "Total",
         "geography": "Total country", "locality": "all",
         "locality_label": "Total", "working_age_base": "15+",
         "frequency": "annual", "survey": _SURVEY, "measure": "rate",
         "unit": "percent", **base, **ctx, **kw}
    r["value"] = float(r["value"])
    return r


def parse_workbook(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    year, ref = _date(path, wb)
    base = {"period": f"{year}-Q2", "reference_period": ref}
    out, youth_nat = [], {}

    # --- Tab4.2: the 15+ ladder ------------------------------------------
    where = f"EMOP {year} Tab4.2"
    cap, hdr, rows = _sheet(wb["Tab4.2"], where)
    if "sous-utilisation" not in cap or len(hdr) != 4:
        raise ValueError(f"{where}: unexpected table {cap!r} {hdr}")
    for section, label, vals in _clean(rows, where):
        ctx = _ctx(section, label, where)
        youth = ctx.get("age_group") in _YOUTH
        if ctx.get("age_group") == "15-24":
            youth_nat = vals
        for k, (h, v) in enumerate(zip(hdr, vals)):
            topic = ("youth_unemployment_rate" if youth and k == 0
                     else _SU_TOPIC[k])
            out.append(_row(base, ctx, topic=topic, definition=_SU_DEF[k],
                            series_label=h, value=v, series_code="EMOP Tab4.2"))

    # --- Tab4.3: the 15-24 ladder ----------------------------------------
    where = f"EMOP {year} Tab4.3"
    cap, hdr, rows = _sheet(wb["Tab4.3"], where)
    # 2025 heads this sheet "Tableau 4-2" -- identify it by content.
    if "jeunes (15-24 ans)" not in cap or len(hdr) != 4:
        raise ValueError(f"{where}: unexpected table {cap!r} {hdr}")
    for section, label, vals in _clean(rows, where):
        ctx = _ctx(section, label, where)
        if section is None:
            # The national youth row repeats Tab4.2's "15 à 24 ans" row and
            # is emitted from there. When the two DISAGREE (2023: 5,96 vs
            # 7,04) neither is right by evidence, so Tab4.2's is withdrawn too.
            if youth_nat and any(abs(a - b) > 0.011 for a, b in zip(vals, youth_nat)):
                DROPPED.append(f"{where}: national 15-24 {fmt(vals)} contradicts "
                               f"Tab4.2's 15-24 row {fmt(youth_nat)} -- both withdrawn")
                out[:] = [r for r in out if not (r["series_code"] == "EMOP Tab4.2"
                          and r["age_group"] == "15-24")]
                continue
            if youth_nat:
                continue            # agrees: already emitted from Tab4.2
            # Tab4.2's age block was refused (2022), so this is the one
            # reading of the national youth ladder: emit it from here.
        ctx["age_group"] = "15-24"
        for k, (h, v) in enumerate(zip(hdr, vals)):
            topic = "youth_unemployment_rate" if k == 0 else _SU_TOPIC[k]
            out.append(_row(base, ctx, topic=topic, definition=_SU_DEF[k],
                            series_label=h, value=v, series_code="EMOP Tab4.3"))

    # --- Tab4.8: NEET -----------------------------------------------------
    where = f"EMOP {year} Tab4.8"
    cap, hdr, rows = _sheet(wb["Tab4.8"], where)
    neet = [(k, h) for k, h in enumerate(hdr) if "ni dans le système" in h]
    if len(neet) != 2:
        raise ValueError(f"{where}: NEET columns not found in {hdr}")
    for section, label, vals in rows:
        ctx = _ctx(section, label, where)
        for k, h in neet:
            band = re.search(r"(\d+)\s*-\s*(\d+)\s*ans", h)
            if vals[k] is None:
                continue
            out.append(_row(base, {**ctx, "age_group": f"{band.group(1)}-{band.group(2)}"},
                            topic="neet_rate", definition="not_applicable",
                            series_label=h, value=vals[k],
                            series_code="EMOP Tab4.8"))
    return out
