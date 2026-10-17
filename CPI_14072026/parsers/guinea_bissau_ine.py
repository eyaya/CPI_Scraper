"""Parser for the INE Guinea-Bissau INHPC monthly note PDF (Tier 3).

Guinea-Bissau (INE) publishes the WAEMU harmonised CPI (INHPC, base 2023 = 100
since the January 2025 issue) as a monthly PDF. 'Tabela 1' is a spreadsheet
object pasted into the page with per-glyph letter spacing, so the note's text
layer comes out column-major and scrambled — 'INDICE GLOBAL' arrives as
'I N D I C E G L O B A L' and a whole column of indices arrives as one run.
Line-based regexes (Mali / Togo / CAR) cannot read it, so we rebuild the table
from glyph GEOMETRY instead:

  * group chars into row bands by `top`, then into cells by x-gap;
  * read the header band ('Descrição | jan-24 | out-24 | … | /1mês | /3meses |
    /12meses') for the column anchors and the periods they carry;
  * assign every numeric cell of a row to the column whose anchor it sits under.

That also survives the layout's two quirks: a label's last letters can be typeset
INSIDE the weight column ('… não alcoólica4s271.3'), and a long label wraps to
bands above/below its own number row ('Habitação, água, gás, eletricidade e' /
numbers / 'outros combustíveis'). Digits are stripped out of label text and a
wrapped label is joined from the neighbouring label-only bands.

Table 1 interleaves division sub-items (Cereais, Pão e produtos de pastelaria,
…) between the divisions, so rows are matched on a fixed COICOP-2018 keyword map
rather than on position; 'Produtos alimentares' (a sub-item) is kept out of
division 01 by keying 01 on 'bebidas não alcoólicas'.

One note carries five index columns (same month a year earlier, then m-3 … m),
so a single PDF yields several periods; the three variation columns are for the
report month only. We emit index + inflation_mom (/1mês) + inflation_yoy
(/12meses). The /3meses variation has no measure in the CPI schema and is
dropped. Portuguese labels are kept as published.
"""
from __future__ import annotations
import re
import unicodedata
import pdfplumber
import pandas as pd

from .ihpc_note_pdf import over_issues

_BASE_PERIOD = "2023 = 100"
_GEOGRAPHY = "National"

# Portuguese month abbreviations as they appear in the column headers ('jan-25').
_MONTHS = {"jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05",
           "jun": "06", "jul": "07", "ago": "08", "set": "09", "out": "10",
           "nov": "11", "dez": "12"}

# (COICOP-2018 code, keyword matched against the row's accent-stripped, letters-
# only label). First match wins, so the order is the table's own order.
_DIVISIONS = [
    ("00", "indiceglobal"),
    ("01", "bebidasnaoalcoolica"),
    ("02", "tabacoeestupefacientes"),
    ("03", "vestuarioecalcado"),
    ("04", "habitacaoagua"),
    ("05", "mobiliarioequipamentos"),
    ("06", "saude"),
    ("07", "transporte"),
    ("08", "informacaoecomunicacao"),
    ("09", "lazeresecultura"),
    ("10", "educacao"),
    ("11", "restaurantesehoteis"),
    ("12", "servicosfinanceiros"),
    ("13", "protecaosocial"),
]

_MONTH_COL = re.compile(r"^([a-z]{3})-(\d{2})$")
_VAR_COL = re.compile(r"^/(\d{1,2})m")
_Y_TOL = 2.5      # pt: chars this close in `top` are the same row band
_X_GAP = 9.0      # pt: a wider horizontal gap than this starts a new cell
_X_SLACK = 3.0    # pt: how far left of its anchor a value may start


def _norm(s: str) -> str:
    """Accent-stripped, lowercased, letters only — for label matching."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def _number(text: str) -> float | None:
    """A cell's numeric value, or None if it isn't one. Stray label letters
    typeset inside the number ('4s271.3', '3s9(N1.D3)') are dropped, but a cell
    carrying a real word — two adjacent letters, which no number ever has — is a
    label however many digits the weight column pushed into it."""
    if re.search(r"[^\W\d_]{2}", text):
        return None
    s = re.sub(r"[^\d.,\-]", "", text).replace(",", ".").replace(" ", "")
    return float(s) if re.fullmatch(r"-?\d+(?:\.\d+)?", s or "") else None


def _bands(page) -> list[tuple[float, list]]:
    """Page chars grouped into row bands, each band's cells split on x-gaps."""
    out = []
    for c in sorted(page.chars, key=lambda c: (c["top"], c["x0"])):
        if out and abs(c["top"] - out[-1][0]) <= _Y_TOL:
            out[-1][1].append(c)
        else:
            out.append([c["top"], [c]])

    bands = []
    for top, chars in out:
        cells, cur, prev_x1 = [], [], None
        for c in sorted(chars, key=lambda c: c["x0"]):
            if prev_x1 is not None and c["x0"] - prev_x1 > _X_GAP:
                cells.append(cur)
                cur = []
            cur.append(c)
            prev_x1 = c["x1"]
        if cur:
            cells.append(cur)
        bands.append((top, [("".join(c["text"] for c in g).strip(), g[0]["x0"])
                            for g in cells]))
    return bands


def _columns(bands) -> list[tuple[float, str]]:
    """Read the header band: [(x anchor, column key)] for the index columns
    (key = 'YYYY-MM') and the variation columns (key = '/1', '/3', '/12')."""
    for _, cells in bands:
        cols = []
        for text, x0 in cells:
            flat = text.replace(" ", "").lower()
            m = _MONTH_COL.match(flat)
            if m and m.group(1) in _MONTHS:
                cols.append((x0, f"20{m.group(2)}-{_MONTHS[m.group(1)]}"))
                continue
            v = _VAR_COL.match(flat)
            if v:
                cols.append((x0, f"/{int(v.group(1))}"))
        if len([c for c in cols if c[1][0] != "/"]) >= 3:
            return sorted(cols)
    return []


def _label(bands, i: int, own: str) -> str:
    """A row's label: its own label cell, plus the label-only bands immediately
    above/below when the label wraps around its number row."""
    parts = [own]
    for j, step in ((i - 1, -1), (i + 1, 1)):
        if not 0 <= j < len(bands):
            continue
        top, cells = bands[j]
        if abs(top - bands[i][0]) > 8 or not cells:
            continue
        if any(_number(t) is not None for t, _ in cells) or len(cells) > 1:
            continue
        (parts.insert(0, cells[0][0]) if step < 0 else parts.append(cells[0][0]))
    label = " ".join(p for p in parts if p)
    return re.sub(r"\s+", " ", re.sub(r"[\d.]+\s*$", "", label)).strip()


def _read_page(page) -> tuple[list, list] | None:
    """Return (columns, rows) for a page holding Tabela 1, else None."""
    bands = _bands(page)
    cols = _columns(bands)
    if not cols:
        return None
    first_x = cols[0][0]

    rows = []
    for i, (_, cells) in enumerate(bands):
        values, own = {}, []
        for text, x0 in cells:
            val = _number(text)
            if val is None:
                own.append(re.sub(r"[\d.]+", "", text).strip())
                continue
            anchors = [c for c in cols if c[0] <= x0 + _X_SLACK]
            if anchors and x0 + _X_SLACK >= first_x:
                values.setdefault(anchors[-1][1], val)
        if values:
            rows.append((_label(bands, i, " ".join(p for p in own if p)), values))
    return cols, rows


def _parse_geometry(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            read = _read_page(page)
            if not read:
                continue
            cols, rows = read
            picked = {}
            for label, values in rows:
                key = _norm(label)
                for code, kw in _DIVISIONS:
                    if code not in picked and kw in key:
                        picked[code] = (label, values)
                        break
            if len(picked) == len(_DIVISIONS):
                break
        else:
            raise ValueError("INE Guinea-Bissau: Tabela 1 not found in the note")

    periods = [c[1] for c in cols if c[1][0] != "/"]
    report = periods[-1]

    records = []
    for code, (label, values) in picked.items():
        missing = [p for p in periods if p not in values]
        if missing or "/1" not in values or "/12" not in values:
            raise ValueError(
                f"INHPC row {code} ({label!r}) incomplete: missing {missing or ''}"
                f"{'' if '/1' in values else ' MoM'}{'' if '/12' in values else ' YoY'}")
        for period in periods:
            records.append((code, label, period, "index",
                            round(values[period], 4), "Index", _BASE_PERIOD))
        records.append((code, label, report, "inflation_mom",
                        round(values["/1"], 4), "percent", ""))
        records.append((code, label, report, "inflation_yoy",
                        round(values["/12"], 4), "percent", ""))

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "period", "measure", "value",
                 "unit", "base_period"])
    out["geography"] = _GEOGRAPHY
    out["frequency"] = "monthly"
    return out


# --- the pre-2025 notes: a text table ----------------------------------------
# Before the 2023 = 100 rebase the note's summary table ('Quadro 01 - Resumo')
# has an ordinary text layer, one row per COICOP-1999 function:
#
#   Jul.23 Abr.24 Mai.24 Jun.24 Jul.24            (or 'Jul, 2019 …' / years
#   INDICE NACIONAL 10000.0 129.0 130.0 131.4 132.1 133.0 0.7 2.3 3.0  on a line
#   01 6030.7 147.4 145.7 147.7 148.7 149.9 0.8 2.9 1.7               below)
#
# Every row ends with 5 indices [m-12, m-3, m-2, m-1, m] and 3 variations, so
# the LAST 8 decimal numbers are read (the weight before them is sometimes
# typeset '1 0 000'). The header's month names must read exactly that
# sequence or the note is refused; the report year is the latest year printed
# in the header. The base is read from the note ('Base 100: Ano 2014', 'base
# 100 em 2008'); a note that states none (the 2019-2020 issues) is refused,
# never assumed. Coverage: the base-2008 IHPC covered the SECTOR AUTÓNOMO DE
# BISSAU only (geography 'Bissau'); the base-2014 INHPC four towns (National).
# A note whose numbers wrap mid-token (Nov 2023: '126.' / '9') reads
# incomplete and is refused. Only the index is emitted for these notes.
_PT_MON = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
           "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
_PT_DIVISIONS = {
    "01": "Produtos alimentares e bebidas não alcoólicas",
    "02": "Bebidas alcoólicas, tabaco e estupefacientes",
    "03": "Vestuário e calçado",
    "04": "Habitação, água, electricidade e outros combustíveis",
    "05": "Acessórios, equipamentos domésticos e sua manutenção regular",
    "06": "Serviços de saúde", "07": "Transportes", "08": "Comunicação",
    "09": "Lazer, recreio e cultura", "10": "Educação",
    "11": "Restaurantes e hotéis", "12": "Bens e serviços diversos",
}
_DEC = re.compile(r"-?\d+[,.]\d+")
_HDR_MON = re.compile(r"\b(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-zç]*[.,]?"
                      r"\s*(\d{4}|\d{2}(?!\d))?", re.I)


def _parse_text(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    b = (re.search(r"base\s*100\s*(?::\s*ano|em)\s*(\d{4})", text, re.I)
         or re.search(r"\(I?N?HPC\),?\s*base\s*(\d{4})", text, re.I))
    if not b:
        raise ValueError("INE Guinea-Bissau: base period not stated in the note")
    geo = ("Bissau" if re.search(r"sector\s+aut[óo]nomo\s+de\s+bissau", text, re.I)
           and not re.search(r"quatro\s+aglomera", text, re.I) else "National")
    lines = text.splitlines()
    top = next((i for i, l in enumerate(lines)
                if re.match(r"\s*indice\s+(nacional|geral)\b", l, re.I)
                and len(_DEC.findall(l)) >= 8), None)
    if top is None:
        raise ValueError("INE Guinea-Bissau: no all-items row in a text table")
    hdr = " ".join(lines[max(0, top - 6):top])
    mons = [(_PT_MON[m.group(1).lower()], m.group(2)) for m in _HDR_MON.finditer(hdr)]
    # prose above the table can name a month too ('realizado em Março 2008'):
    # the table's own five are the last ones, and the sequence check below
    # refuses anything else
    mons = mons[-5:]
    if len(mons) != 5:
        raise ValueError(f"INE Guinea-Bissau: {len(mons)} header months, expected 5")
    years = [int(y) % 100 for y in re.findall(r"\b(20\d\d)\b", hdr)] or \
            [int(y) for _, y in mons if y]
    if not years:
        raise ValueError("INE Guinea-Bissau: no year in the table header")
    rm, ry = mons[-1][0], 2000 + max(years)
    want = [(rm - k - 1) % 12 + 1 for k in (12, 3, 2, 1, 0)]
    if [m for m, _ in mons] != want:
        raise ValueError(f"INE Guinea-Bissau: header months {[m for m, _ in mons]}, "
                         f"expected {want}")
    periods = []
    for k in (12, 3, 2, 1, 0):
        idx = ry * 12 + rm - 1 - k
        periods.append(f"{idx // 12}-{idx % 12 + 1:02d}")

    rows = {}
    for l in lines[top:top + 60]:
        s = l.strip()
        code = ("00" if re.match(r"indice\s+(nacional|geral)\b", s, re.I)
                else (m.group(1) if (m := re.match(r"(\d{2})\s", s)) else None))
        nums = _DEC.findall(s)
        if code is None or code in rows or len(nums) < 8 \
                or (code != "00" and code not in _PT_DIVISIONS):
            continue
        rows[code] = [float(x.replace(",", ".")) for x in nums[-8:-3]]
    if len(rows) != 13:
        raise ValueError(f"INE Guinea-Bissau: text table incomplete, got {sorted(rows)}")
    records = [(code, "Índice nacional" if code == "00" and geo == "National"
                else "Índice geral" if code == "00" else _PT_DIVISIONS[code],
                p, "index", v, "Index", f"{b.group(1)} = 100")
               for code, vals in rows.items() for p, v in zip(periods, vals)]
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = geo
    out["frequency"] = "monthly"
    return out


def _parse_issue(pdf_path: str) -> pd.DataFrame:
    """The 2023 = 100 geometry reader first; the pre-2025 text table if the
    note has no letter-spaced 'Tabela 1'."""
    try:
        return _parse_geometry(pdf_path)
    except ValueError as geo_err:
        try:
            return _parse_text(pdf_path)
        except ValueError as txt_err:
            raise ValueError(f"{geo_err} | text table: {txt_err}") from None


parse = over_issues(_parse_issue, "guinea_bissau_ine")
