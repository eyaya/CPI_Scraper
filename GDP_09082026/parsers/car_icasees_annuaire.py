"""Annual back series for the Central African Republic: ICASEES, Annuaire
statistique 2018-2021, chapitre V 'Comptes nationaux' (PDF), years 2014-2019,
SCN 1993 (the chapter's methodology says so). Not a registry parser:
`car_icasees_gdp.parse` hands it the yearbook as an extra.

Tables read (captions as printed; ICASEES numbers two different tables 234):
  231  real growth by sector, percent
  232  contribution of sectors to growth, percentage points
  233  uses of GDP at current prices
  234  uses of GDP at constant prices (base 100=2005)
  234  GDP by sector (base 100=2005)

These are the OLD (SCN 1993) accounts. The rebased SCN 2008 / base 2019
accounts are the workbook and report this parser's caller reads; the two are
never chained, and `category_group` names the yearbook and table.

UNIT -- the captions say "million de FCFA", the figures are billions: GDP 2019
prints as 1 432,1, the same figure ICASEES's 2026 national-accounts workbook
gives for its old series (1 432,0) in a sheet it describes "en milliards de
FCFA", and a GDP of 1.4 million FCFA is impossible. Recorded as
"milliard FCFA" (the caller's convention for the same contradiction).

Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import fitz

_YEARS = 6
_NUM = re.compile(r"-?(?:\d{1,3}(?: \d{3})+|\d+)(?:,\d+)?")
_CAP = re.compile(r"Tableau\s*(23[1-4])\s*:\s*(.+?)(?=\n\s*\n| SECTEUR| Rubriques)", re.S)
_HEADS = ("Consommation Finale", "Formation Brut de Capitale", "Exportations",
          "Importations")


def _f(t: str) -> float:
    return float(t.replace(" ", "").replace(",", "."))


def _spec(cap: str):
    c = cap.lower()
    if "contribution" in c:
        return "constant", "contribution", "percentage points", ""
    if "croissance" in c:
        return "constant", "growth_yoy", "percent", ""
    if "constant" in c or "base 100=2005" in c:
        return "constant", "level", "milliard FCFA", "constant prices, base 100=2005"
    return "current", "level", "milliard FCFA", ""


def parse_annuaire(path: str) -> list[dict]:
    with fitz.open(path) as doc:
        pages = [p.get_text() for p in doc]
    text = "\n".join(p for p in pages if "Tableau 23" in p)
    starts = [m for m in re.finditer(r"Tableau\s*(23[1-4])\s*:", text)]
    rows = []
    for k, m in enumerate(starts):
        tno = m.group(1)
        body = text[m.end(): starts[k + 1].start() if k + 1 < len(starts) else len(text)]
        lines = [l.strip() for l in body.split("\n") if l.strip()]
        # the header is a run of six year lines (a caption may end in a year)
        yi = next(i for i in range(len(lines)) if all(
            re.fullmatch(r"20\d\d", x) for x in lines[i:i + _YEARS]))
        caption = re.sub(r"\s+", " ", " ".join(lines[:yi - 1])).strip()
        years = lines[yi: yi + _YEARS]
        assert all(re.fullmatch(r"20\d\d", y) for y in years), (tno, years)
        basis, measure, unit, base = _spec(caption)
        group = f"Annuaire statistique 2018-2021, Tableau {tno} : {caption}"
        approach_default = "production" if "secteur" in caption.lower() else "expenditure"
        label, nums, head = [], [], ""

        def flush():
            nonlocal label, nums, head
            lab = re.sub(r"\s+", " ", " ".join(label)).strip()
            vals = nums
            label, nums = [], []
            if not lab or not vals:
                return
            if len(vals) != _YEARS:
                raise ValueError(f"T{tno} '{lab}': {len(vals)} values")
            if any(lab.startswith(h) for h in _HEADS):
                head = lab
                cat = lab
            elif lab in ("Biens", "Services") and head:
                cat = f"{head}: {lab}"
            elif lab in ("Ménage", "Administration Publique", "ISBSLM") and head:
                cat = f"{head}: {lab}"
            else:
                cat = lab
            appr = "aggregate" if "intérieur brut" in cat.lower() or \
                "interieur brut" in cat.lower() else approach_default
            for y, v in zip(years, vals):
                rows.append({"approach": appr, "category": cat,
                             "category_group": group,
                             "series_code": f"ICASEES AS2018-2021 T{tno}",
                             "geography": "Total country", "period": y,
                             "frequency": "annual", "price_basis": basis,
                             "seasonal_adjustment": "nsa", "measure": measure,
                             "value": _f(v), "unit": unit, "base_period": base})

        for l in lines[yi + _YEARS:]:
            if l.startswith("Source"):
                flush()
                break
            if re.search(r"[A-Za-zÀ-ÿ]", l):
                if nums:
                    flush()
                elif label and l[0].isupper() and                         " ".join(label).count("(") == " ".join(label).count(")"):
                    label = []      # a row printed without figures: dropped
                label.append(l)
            else:
                nums.extend(_NUM.findall(l))
        flush()
    if not rows:
        raise ValueError(f"no national-accounts rows read from {path}")
    return rows
