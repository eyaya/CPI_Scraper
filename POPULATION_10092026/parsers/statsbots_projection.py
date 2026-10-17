"""Statistics Botswana -- "Population Projections for Botswana 2011-2026"
(2011 census based, published 2015), MEDIUM scenario ("Scenario 2") only:

* Appendix 1 -- projected national population, 2011-2026 (Medium column);
* Appendix 4 -- Medium scenario by five-year age group (0-4 .. 80+, Total) for
  Males and Females, four years per block;
* Appendix 18 -- Medium scenario by census district (both sexes), 2011-2026.

Added 2026-10-13 as a SECOND Botswana descriptor (botswana_projections.yaml)
beside the 2022 census report.

ONE SCENARIO. The report also publishes High 1a, High 1b, Low and HIV/AIDS
scenarios; the merge key has no scenario column, so only the Medium -- the
report's central variant -- is kept. Appendices 2-5 share pages, so rows are
bound to the latest caption read in page order.

Appendix 4 prints no both-sexes column; that total is NOT computed -- the
national both-sexes figure comes from Appendix 1, and Males Total + Females
Total must equal it each year (checked). District names are as printed
("Kanye/Moshupa", "Selibe Phikwe", "Central Serowe", ...). The first Appendix
18 block (2011-2016) prints no Ghanzi row; Ghanzi starts in 2017. Where all 27
districts are printed they sum to +92 (2017) .. +760 (2026) above the printed
national Total -- the report's own footnote blames "rounding errors"; kept as
published, bounded at 0.05%.

series_type = projection.
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_SC = "STATSBOTS_PROJ_2011_2026_MEDIUM"
_BANDS = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
          "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
          "75-79", "80+"]
_NUM = re.compile(r"^\d{1,3}(,\d{3})*$")
_CAP = re.compile(r"^Appendix\s+(\d+)\b")


def _lines(page):
    ws = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    out = []
    for x0, y0, x1, y1, w, *_ in ws:
        y = (y0 + y1) / 2
        if out and y - out[-1][0] <= 2.5:
            out[-1][1].append((x0, w))
        else:
            out.append([y, [(x0, w)]])
    return [[w for _, w in sorted(ws)] for _, ws in out]


def _split(words):
    label = []
    for w in words:
        if _NUM.match(w):
            break
        label.append(w)
    return " ".join(label), [float(w.replace(",", "")) for w in words[len(label):]
                             if _NUM.match(w)], len(words) - len(label)


def _row(sex, age, geo, year, value):
    return {"series_type": "projection", "sex": sex, "age_group": age,
            "geography": geo, "period": year, "frequency": "annual",
            "measure": "count", "value": float(value), "unit": "persons",
            "series_code": _SC}


def parse(local_path: str) -> pd.DataFrame:
    nat: dict[str, float] = {}                  # Appendix 1 Medium
    age: dict[tuple[str, str, str], float] = {}  # (year, band, sex)
    dist: dict[tuple[str, str], float] = {}      # (district, year)
    dist_total: dict[str, float] = {}
    app, years, cols = None, [], []
    with fitz.open(local_path) as doc:
        for page in doc:
            for words in _lines(page):
                text = " ".join(words)
                m = _CAP.match(text)
                if m:
                    app, years = int(m.group(1)), []
                    continue
                if app == 1:
                    if "Medium" in words:
                        cols = [w for w in words if w in ("High", "Medium", "Low", "HIV")]
                        continue
                    lab, vals, _ = _split(words)
                    if re.fullmatch(r"20[12]\d", lab) and len(vals) == 5:
                        # High 1A, High 1B, Medium, Low, HIV
                        if cols[:3] != ["High", "High", "Medium"]:
                            raise ValueError(f"Statsbots App 1: columns {cols}")
                        nat[lab] = vals[2]
                elif app in (4, 18):
                    ys = re.findall(r"(?<!\d)20[12]\d(?!\d)", text)
                    if len(ys) >= 4 and "," not in text:
                        years = ys
                        continue
                    lab, vals, n = _split(words)
                    if not years or not vals or not lab or lab.isupper():
                        continue        # page numbers, running footers
                    if app == 4 and lab not in _BANDS and lab != "Total":
                        continue        # completeness is checked below
                    if len(vals) != len(years) * (2 if app == 4 else 1) or n != len(vals):
                        raise ValueError(f"Statsbots App {app} {lab}: {vals} for {years}")
                    if app == 4:
                        for j, v in enumerate(vals):
                            key = (years[j // 2], lab, ("male", "female")[j % 2])
                            if key in age:
                                raise ValueError(f"Statsbots App 4 {key}: read twice")
                            age[key] = v
                    else:
                        for y, v in zip(years, vals):
                            if lab.rstrip("*") == "Total":
                                dist_total[y] = v
                            else:
                                if (lab, y) in dist:
                                    raise ValueError(f"Statsbots App 18 {lab} {y}: read twice")
                                dist[(lab, y)] = v
    yrs = [str(y) for y in range(2011, 2027)]
    if sorted(nat) != yrs:
        raise ValueError(f"Statsbots App 1: years {sorted(nat)}")
    out = []
    for y in yrs:
        for sex in ("male", "female"):
            s = sum(age[(y, b, sex)] for b in _BANDS)
            if abs(s - age[(y, "Total", sex)]) > 17:     # 17 rounded bands
                raise ValueError(f"Statsbots App 4 {y} {sex}: bands {s} != {age[(y, 'Total', sex)]}")
        mf = age[(y, "Total", "male")] + age[(y, "Total", "female")]
        if abs(mf - nat[y]) > 2:
            raise ValueError(f"Statsbots {y}: M+F Total != App 1 Medium {nat[y]}")
        if dist_total.get(y) != nat[y]:
            raise ValueError(f"Statsbots App 18 {y}: Total {dist_total.get(y)} != {nat[y]}")
        out.append(_row("total", "Total", "Total country", y, nat[y]))
        ds = [v for (d, yy), v in dist.items() if yy == y]
        # the districts drift above the national total by +92 (2017) to +760
        # (2026), 0.03% -- the report's own "rounding errors" footnote; kept
        if len(ds) == 27 and abs(sum(ds) - nat[y]) > 0.0005 * nat[y]:
            raise ValueError(f"Statsbots App 18 {y}: districts {sum(ds)} != {nat[y]}")
        if len(ds) != (26 if y < "2017" else 27):
            raise ValueError(f"Statsbots App 18 {y}: {len(ds)} districts")
    for (y, b, sex), v in age.items():
        out.append(_row(sex, b, "Total country", y, v))
    for (d, y), v in dist.items():
        out.append(_row("total", "Total", d, y, v))
    return pd.DataFrame(out)
