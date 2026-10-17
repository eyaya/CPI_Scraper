"""INS Niger -- Annuaire statistique du Niger, population chapter (07.01),
read from six editions. Source line of every table: "Institut National de la
Statistique/Projections démographiques, Niger 2012-2024" (RGP/H 2012-based
projections) -> series_type projection, persons.

Added 2026-10-13 as a SECOND Niger descriptor (niger_annuaire.yaml) beside
niger.yaml (the RGP/H 2012 census).

* Tableau 07.01.b "Population du Niger par région, département et commune" --
  a FIVE-YEAR WINDOW of totals (both sexes) ending at the edition's year.
  REGION rows and ENSEMBLE NIGER are read. Editions overlap; for each year the
  NEWEST edition's printing is filed (later editions revise -- e.g. Agadez
  2016 585 735 in the 2016-2020 edition, 585 737 in the 2017-2021 one).
* Tableau 07.01.c "... selon le sexe en <year>" -- the edition's final year
  by sex. Its MALE and FEMALE region / national rows are filed; its Total
  column is not (07.01.b's printing of the same figure is), but compared.

EDITIONS (file-name fragment -> final year): 2013-2017 -> 2017, 2015_2019 ->
2019, 2016_2020 -> 2020, 31122023 ("version du 31/12/2023", the 2017-2021
edition) -> 2021, 2019_2023 -> 2023, 2020_2024 -> 2024. NOT USED: the
2018-2022 edition -- its 07.01.c pages carry 2016-2020 and 2017-2021 running
heads, its regions mix 2021 and 2022 figures (Tillabéri 3 762 348 = 2021,
Dosso 2 944 264 = 2022) and its ENSEMBLE NIGER is 2021's; its 2022 figures are
read from the 2019-2023 and 2020-2024 editions' 07.01.b instead.

PUBLISHED INCONSISTENCIES, pinned in _KNOWN (filed as printed, newest
edition): see the set. Anything new raises.

LAYOUT. Figures are set as one span per cell, one span per digit group, or
several cells in one span separated by runs of spaces; a span is split on runs
of 2+ spaces and pieces are placed by x into the header's columns. A row whose
figures sit on the next line takes that line. Header years may print as
"2 021".
"""
from __future__ import annotations

import collections
import os
import re
import unicodedata

import fitz
import pandas as pd

_REGIONS = {"agadez": "Agadez", "diffa": "Diffa", "dosso": "Dosso",
            "maradi": "Maradi", "tahoua": "Tahoua", "tillaberi": "Tillabéri",
            "zinder": "Zinder", "niamey": "Niamey"}
_GEOS = set(_REGIONS.values()) | {"Total country"}
_EDITIONS = {"2013-2017": "2017", "2015_2019": "2019", "2016_2020": "2020",
             "31122023": "2021", "2019_2023": "2023", "2020_2024": "2024"}
_SC_B = "NE_INS_PROJ_2012_2024_T07.01.b_ED{}"
_SC_C = "NE_INS_PROJ_2012_2024_T07.01.c_ED{}"
# Published, pinned (filed as printed). (check, edition, geo|year, detail)
_KNOWN: set = {
    # 07.01.c's Tillabéri Total is the 07.01.b figure, but its M / F are not
    # (they sum 233 925 and 2 short of it respectively)
    ("M+F!=T", "2020", "Tillabéri", "1677529+1714775 vs 3626229"),
    ("M+F!=T", "2021", "Tillabéri", "1740499+1779143 vs 3762348"),
    # Dosso 2020 is printed 3 172 644 in 07.01.b of every edition from
    # 2016-2020 on -- the 2024 value; 07.01.c of the 2016-2020 edition prints
    # 2 733 875. Hence also the 2020 regions-vs-Niger gap of 438 770.
    ("c!=b", "2020", "Dosso", "2733875 vs 3172644"),
    ("regions!=Niger", "2020", "2020", "23191156 vs 22752385"),
    ("regions!=Niger", "2021", "2020", "23191155 vs 22752385"),
    ("regions!=Niger", "2023", "2020", "23191155 vs 22752385"),
    # 2015-2017: the regions over-run ENSEMBLE NIGER by 47-87 thousand, the
    # same in every edition that prints those years
    ("regions!=Niger", "2019", "2015", "19022433 vs 18975221"),
    ("regions!=Niger", "2019", "2016", "19745463 vs 19679500"),
    ("regions!=Niger", "2019", "2017", "20494913 vs 20407944"),
    ("regions!=Niger", "2020", "2016", "19745463 vs 19679500"),
    ("regions!=Niger", "2020", "2017", "20494913 vs 20407944"),
    ("regions!=Niger", "2021", "2017", "20494913 vs 20407944"),
}
# Rows an edition does not print (checked exactly):
# * 2020-2024 edition, 07.01.b: no Maradi section (its 2020-2023 come from the
#   2019-2023 edition; 2024 Maradi is not collected);
# * 2015-2019 edition, 07.01.c: the Maradi and Zinder pages (81, 84) carry no
#   text layer -- not OCRed;
# * 2020-2024 edition, 07.01.c: the last page (Niamey) is printed in the
#   five-year layout without a sex split, and no ENSEMBLE NIGER by sex.
_MISSING_B = {"2024": {"Maradi"}}
_MISSING_C = {"2019": {"Maradi", "Zinder"}, "2024": {"Niamey", "Total country"}}


def _key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def _edition(path: str) -> str:
    base = os.path.basename(path).replace(" ", "_")
    hits = [y for frag, y in _EDITIONS.items() if frag in base]
    if len(hits) != 1:
        raise ValueError(f"INS Niger: unknown edition {base}")
    return hits[0]


def _spans(page):
    rows = collections.defaultdict(list)
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                if s["text"].strip():
                    rows[round((s["bbox"][1] + s["bbox"][3]) / 2)].append(
                        (s["bbox"][0], s["bbox"][2], s["text"]))
    out = []
    for y in sorted(rows):
        if out and y - out[-1][0] <= 2:
            out[-1][1].extend(rows[y])
        else:
            out.append([y, list(rows[y])])
    return [(y, sorted(ws)) for y, ws in out]


def _cells(spans, cols: list[float], xmin: float):
    """Values for each column. A span is split on runs of 2+ spaces; each
    piece is placed at its own position inside the span (by character offset
    -- spans carry leading padding) and goes to the nearest column; digit
    groups landing in one column are joined."""
    n = len(cols)
    parts: dict[int, list[str]] = {k: [] for k in range(n)}
    found = False
    for x0, x1, t in spans:
        if not t.strip():
            continue
        w = (x1 - x0) / max(len(t), 1)
        for m in re.finditer(r"\S+(?: \S+)*", t):
            piece = m.group(0)
            xc = x0 + w * (m.start() + m.end()) / 2
            if xc < xmin:
                continue
            if not re.fullmatch(r"[\d ]+", piece):
                continue
            found = True
            k = min(range(n), key=lambda j: abs(cols[j] - xc))
            parts[k].append(piece.replace(" ", ""))
    if not found:
        return None
    if not all(parts.values()):
        raise ValueError(f"INS Niger: incomplete row {[t for _, _, t in spans]}")
    return [float("".join(parts[k])) for k in range(n)]


def _geo(label: str) -> str | None:
    k = _key(label)
    if k.startswith("regiondepartement"):
        return None
    if k.startswith("region"):
        g = _REGIONS.get(re.sub(r"^region(de|d)?", "", k))
        if g is None:
            raise ValueError(f"INS Niger: region label {label!r}")
        return g
    # no digits: the wrapped source line "Niger 2012-2024" is not the total
    if k in ("ensembleniger", "niger", "totalniger") and not re.search(r"\d", label):
        return "Total country"
    return None


def _scan(rows, cols, xmin, out, where):
    for i, (_, ws) in enumerate(rows):
        label = " ".join(t.strip() for x0, _, t in ws if x0 < xmin)
        g = _geo(label)
        if g is None:
            continue
        v = _cells(ws, cols, xmin)
        if v is None and i + 1 < len(rows):
            nxt = rows[i + 1][1]
            if not any(x0 < xmin and t.strip() for x0, _, t in nxt):
                try:
                    v = _cells(nxt, cols, xmin)
                except ValueError:
                    v = None
        if v is None:
            raise ValueError(f"INS Niger {where} {g}: no figures")
        if g in out and out[g] != v:
            raise ValueError(f"INS Niger {where} {g}: {out[g]} / {v}")
        out[g] = v


def _read(path: str):
    ed = _edition(path)
    tb: dict[str, list] = {}                 # geo -> 5 totals
    tc: dict[str, list] = {}                 # geo -> [M, F, T]
    years_b: list[str] | None = None
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text()
            if "Tableau 07.01.b" not in text and "Tableau 07.01.c" not in text:
                continue
            rows = _spans(page)
            if "Tableau 07.01.b" in text:
                head = None
                for _, ws in rows:
                    ys = [(x0, x1, re.sub(r"\s", "", t)) for x0, x1, t in ws
                          if re.fullmatch(r"2\s?0\s?[12]\d", t.strip())]
                    if len(ys) == 5:
                        head = ys
                if head is None:
                    continue
                yrs = [t for _, _, t in head]
                if years_b and yrs != years_b:
                    raise ValueError(f"INS Niger ed{ed} 07.01.b: header {yrs} vs {years_b}")
                years_b = yrs
                cols = [(a + b) / 2 for a, b, _ in head]
                _scan(rows, cols, cols[0] - 45, tb, f"ed{ed} 07.01.b p{page.number+1}")
            elif "Tableau 07.01.c" in text:
                m = re.search(r"selon\s+le\s+sexe\s+en\s+(20\d\d)", text)
                if m and m.group(1) != ed:
                    raise ValueError(f"INS Niger ed{ed}: 07.01.c caption year {m.group(1)}")
                head = next((ws for _, ws in rows if any("Masculin" in t for _, _, t in ws)), None)
                if head is None:
                    continue
                cols = []
                for word in ("masculin", "feminin", "total"):    # "Fém inin" too
                    x0, x1, _ = next(s for s in head if word in _key(s[2]))
                    cols.append((x0 + x1) / 2)
                _scan(rows, cols, cols[0] - 70, tc, f"ed{ed} 07.01.c p{page.number+1}")
    if years_b is None or years_b[-1] != ed:
        raise ValueError(f"INS Niger ed{ed}: 07.01.b years {years_b}")
    return ed, years_b, tb, tc


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    eds = {}
    for p in [local_path] + list(extras or []):
        ed, yrs, tb, tc = _read(p)
        if ed in eds:
            raise ValueError(f"INS Niger: two editions ending {ed}")
        eds[ed] = (yrs, tb, tc)
    if sorted(eds) != sorted(_EDITIONS.values()):
        raise ValueError(f"INS Niger: editions {sorted(eds)}")

    issues: set = set()
    # 07.01.b: newest edition wins for each year
    totals: dict[str, dict[str, tuple[float, str]]] = {}
    for ed in sorted(eds):
        yrs, tb, _ = eds[ed]
        miss = _GEOS - set(tb)
        if miss != _MISSING_B.get(ed, set()):
            raise ValueError(f"INS Niger ed{ed} 07.01.b: missing {sorted(miss)}")
        for g, vals in tb.items():
            for y, v in zip(yrs, vals):
                totals.setdefault(y, {})[g] = (v, ed)
    # within each edition: regions sum to ENSEMBLE NIGER
    for ed, (yrs, tb, _) in sorted(eds.items()):
        if set(tb) != _GEOS:
            continue
        for k, y in enumerate(yrs):
            s = sum(v[k] for g, v in tb.items() if g != "Total country")
            if abs(s - tb["Total country"][k]) > 10:
                issues.add(("regions!=Niger", ed, y,
                            f"{s:.0f} vs {tb['Total country'][k]:.0f}"))
    out = []

    def emit(sex, g, y, v, sc):
        out.append({"series_type": "projection", "sex": sex, "age_group": "Total",
                    "geography": g, "period": y, "frequency": "annual",
                    "measure": "count", "value": v, "unit": "persons",
                    "series_code": sc})

    for y, d in sorted(totals.items()):
        for g, (v, ed) in d.items():
            emit("total", g, y, v, _SC_B.format(ed))
    # 07.01.c: the edition's final year by sex
    for ed, (_, _, tc) in sorted(eds.items()):
        for g, (m, f, t) in tc.items():
            if abs(m + f - t) > 2:
                issues.add(("M+F!=T", ed, g, f"{m:.0f}+{f:.0f} vs {t:.0f}"))
            b = eds[ed][1].get(g)               # same edition's 07.01.b
            if b is not None and abs(b[-1] - t) > 2:
                issues.add(("c!=b", ed, g, f"{t:.0f} vs {b[-1]:.0f}"))
            emit("male", g, ed, m, _SC_C.format(ed))
            emit("female", g, ed, f, _SC_C.format(ed))
        if _GEOS - set(tc) != _MISSING_C.get(ed, set()):
            raise ValueError(f"INS Niger ed{ed} 07.01.c: missing {sorted(_GEOS - set(tc))}")
    if issues != _KNOWN:
        raise ValueError(f"INS Niger: inconsistencies changed: new "
                         f"{sorted(issues - _KNOWN)}, gone {sorted(_KNOWN - issues)}")
    return pd.DataFrame(out)
