"""INSTAT Mali -- Annuaire statistique du Mali, "Tableau 1 : Répartition de la
population par sexe et par milieu de résidence": national population by sex,
read from three editions to give 2013-2023.

Added 2026-10-13 as a SECOND Mali descriptor (mali_annuaire.yaml) beside
mali.yaml (the 2022 RGPH5 census, Etat et structure de la population).

WHICH EDITION FOR WHICH YEAR. Each edition reprints a rolling window of the
DNP's "Projections démographiques du Mali 2010-2035":
* 2019 edition (anuair19) -- 2013-2019, printed ROUNDED to the thousand
  ("16 808 000"); read for 2013-2018 only;
* 2023 edition (anuair23) -- 2019-2021 (DNP, printed to the unit, "19 972 410")
  and 2022 (RGPH5 census); read for 2019-2021;
* 2024 edition (anuair24, the primary) -- 2020-2021 (DNP, = the 2023 edition,
  checked), 2022 (RGPH5) and 2023 (source NOT stated in the table's
  footnotes); read for 2023.
The newest printing of a year is the one kept; older printings of the same
year are only checked for agreement within their rounding.

NOT READ: 2022 -- the census figure, already collected by mali.yaml (series
census); 2024 -- printed "ND". Urban/rural rows -- in the 2019-2021 editions
they are "calcul des auteurs" from the EMOP survey, a different source from
the sex rows, and the schema has no locality column.

series_type: DNP years -> projection; 2023 (source unstated) -> estimate.
Checks: male + female = total (within 2 persons; the rounded 2019 edition
within 2 000), each year read from its designated edition.
"""
from __future__ import annotations

import os
import re

import fitz
import pandas as pd

_NUM = re.compile(r"(?<!\d)\d{1,3}(?: \d{3})+(?!\d)")
_ROWS = {"Population totale": "total", "Population masculine": "male",
         "Population féminine": "female"}
# edition file -> the years it supplies
_PLAN = {"anuair19": [str(y) for y in range(2013, 2019)],
         "anuair23": ["2019", "2020", "2021"],
         "anuair24": ["2023"]}


def _edition(path: str) -> str:
    base = os.path.basename(path).lower()
    for ed in _PLAN:
        if ed in base:
            return ed
    raise ValueError(f"INSTAT Mali annuaire: unknown edition {base}")


def _table1(path: str) -> dict[str, dict[str, float]]:
    """{year: {sex: value}} from the edition's Tableau 1 page."""
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text()
            if not (re.search(r"TABLEAU\s*1|Tableau 1", text, re.I)
                    and "Population masculine" in text
                    and re.search(r"R[ÉE]PARTITION DE LA POPULATION", text, re.I)):
                continue
            words = page.get_text("words")
            # the header line: the line carrying the most year tokens (the
            # title also names years -- "de 2019 à 2022")
            yw = [w for w in words if re.fullmatch(r"20[12]\d\**", w[4])]
            by_line: dict[int, list] = {}
            for w in yw:
                by_line.setdefault(round(w[1]), []).append(w)
            head = max(by_line.values(), key=len)
            years = sorted((w[0], w[4].rstrip("*")) for w in head)
            # values: a row's numbers are the spans on the label's line or the
            # line just below it (the label is set a few points higher)
            lines = {}
            for b in page.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    for s in ln["spans"]:
                        t = s["text"].strip()
                        if t:
                            y = round((s["bbox"][1] + s["bbox"][3]) / 2)
                            lines.setdefault(y, []).append((s["bbox"][0], s["bbox"][2], t))
            out: dict[str, dict[str, float]] = {}
            for y, spans in lines.items():
                lab = " ".join(t for x0, _, t in spans if x0 < 120)
                sex = next((v for k, v in _ROWS.items() if lab.startswith(k)), None)
                if sex is None:
                    continue
                cand = [(yy, sp) for yy, sp in lines.items() if 0 <= yy - y <= 16]
                vals = []
                for yy, sp in sorted(cand):
                    for x0, x1, t in sp:
                        if x0 < 120:
                            continue
                        ms = list(_NUM.finditer(t))
                        if not ms:
                            continue
                        # a span can hold several figures; spread its width
                        step = (x1 - x0) / len(ms)
                        for k, m in enumerate(ms):
                            vals.append((x0 + step * (k + 0.5), m.group(0)))
                for xc, v in vals:
                    yr = min(years, key=lambda p: abs(p[0] + 12 - xc))
                    out.setdefault(yr[1], {})
                    if sex in out[yr[1]] and out[yr[1]][sex] != float(v.replace(" ", "")):
                        raise ValueError(f"INSTAT Mali {path}: two {sex} {yr[1]}")
                    out[yr[1]][sex] = float(v.replace(" ", ""))
            if out:
                return out
    raise ValueError(f"INSTAT Mali: Tableau 1 not found in {path}")


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = {_edition(p): p for p in [local_path] + list(extras or [])}
    if set(files) != set(_PLAN):
        raise ValueError(f"INSTAT Mali annuaire: editions {sorted(files)}")
    tabs = {ed: _table1(p) for ed, p in files.items()}

    # the 2024 edition's 2020-2021 must equal the 2023 edition's
    for y in ("2020", "2021"):
        if tabs["anuair24"].get(y) != tabs["anuair23"].get(y):
            raise ValueError(f"INSTAT Mali {y}: editions differ "
                             f"{tabs['anuair24'].get(y)} / {tabs['anuair23'].get(y)}")
    # the rounded 2019 edition's 2019 agrees with the 2023 edition's
    for s in ("total", "male", "female"):
        a, b = tabs["anuair19"]["2019"][s], tabs["anuair23"]["2019"][s]
        if abs(a - b) > 1000:
            raise ValueError(f"INSTAT Mali 2019 {s}: {a} vs {b}")

    out = []
    for ed, years in _PLAN.items():
        tol = 2000 if ed == "anuair19" else 2
        for y in years:
            row = tabs[ed].get(y)
            if not row or set(row) != {"total", "male", "female"}:
                raise ValueError(f"INSTAT Mali {ed} {y}: {row}")
            if abs(row["male"] + row["female"] - row["total"]) > tol:
                raise ValueError(f"INSTAT Mali {ed} {y}: M + F != total {row}")
            st = "estimate" if y == "2023" else "projection"
            sc = (f"ML_INSTAT_{ed.upper()}_T1" if y == "2023"
                  else f"ML_DNP_PROJ_2010_2035_{ed.upper()}")
            for sex, v in row.items():
                out.append({"series_type": st, "sex": sex, "age_group": "Total",
                            "geography": "Total country", "period": y,
                            "frequency": "annual", "measure": "count",
                            "value": v, "unit": "persons", "series_code": sc})
    return pd.DataFrame(out)
