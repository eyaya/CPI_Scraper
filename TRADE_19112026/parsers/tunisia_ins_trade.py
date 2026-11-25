"""Parsers for INS Tunisia merchandise trade ("Commerce extérieur aux prix courants").

INS (the NSO) compiles Tunisia's foreign-trade statistics from customs records.

`parse` -- the INS "Statistiques > Commerce extérieur" web pages (HTML tables,
  "Unité : Millions de dinars"), live and as Wayback `id_` copies of the same
  INS pages (each capture holds the window the page showed that day):
    /statistiques/50  balance commerciale: annual (2017-) and the current
                      year's months -- exports, imports, balance
    /statistiques/52  exports / imports by "groupement sectoriel d'activité",
                      the last twelve months (raw tables; the CVS-CEC seasonally
                      adjusted tables are not read)
    /statistiques/53  exports / imports by type d'utilisation, annual
    /statistiques/54  exports / imports by continent, annual (groups)
    /statistiques/55  principal products exported / imported, annual
  Rows are emitted as printed; a table without a "Millions de dinars" unit row
  is skipped. Shares/variations are not on these pages.

`parse_notes` -- the Excel annexes of the monthly "Commerce extérieur aux prix
  courants" note, read ONLY for the issues whose cumulative window is a schema
  period: the December issue ("12 mois" / "Année" = the calendar year) and the
  March issue ("3 mois" = the first quarter). Other issues are year-to-date.
    Balance par chapitres  exports / imports by HS chapter: value (TND) and net
                           weight (kg), three years
    Balance par pays       exports / imports by country and bloc (MD), three years
    Comext "Global"        total exports, imports, balance (MD), three years
    Comext "GP"            exports / imports by product group (MD), three years
"""
from __future__ import annotations

import html as _html
import re
import unicodedata

import openpyxl
import pandas as pd

from ._common import row, to_number

_MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
           "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip().lower()


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _col_period(h: str):
    t = _fold(h)
    m = re.match(r"^(\d{4})$", t)
    if m:
        return m.group(1), "annual"
    m = re.match(r"^([a-z�?]+)\s+(\d{4})$", t)
    if m:
        name = m.group(1)
        mo = _MONTHS.get(name)
        if mo is None:                # mis-decoded accents (f�vrier, ao�t, d�cembre)
            pat = "^" + re.escape(name).replace("�", ".").replace(r"\?", ".") + "$"
            hits = [v for k, v in _MONTHS.items() if re.match(pat, k) or
                    (len(k) == len(name) + 1 and re.match(pat.replace(".", ".{1,2}"), k))]
            mo = hits[0] if len(hits) == 1 else None
        if mo:
            return f"{m.group(2)}-{mo:02d}", "monthly"
    return None


def _web_tables(text: str):
    """Yield (title, unit, headers, [(label, [cells])]) for every INS stats table."""
    for m in re.finditer(r"<table[^>]*>(.*?)</table>", text, re.S):
        body = m.group(1)
        hidden = [_clean(x) for x in re.findall(r'<tr class="hide">(.*?)</tr>', body, re.S)]
        unit = next((h for h in hidden if _fold(h).startswith("unit")), "")
        title = next((h for h in hidden[1:] if h and not _fold(h).startswith(("unit", "source", "nofilter"))), "")
        heads = [_clean(h) for h in re.findall(r"<th scope=\"col\">(.*?)</th>", body, re.S)]
        rows = []
        for tr in re.findall(r"<tr>\s*<th>(.*?)</th>(.*?)</tr>", body, re.S):
            cells = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr[1], re.S)]
            rows.append((_clean(tr[0]), cells))
        yield title, unit, heads, rows


def _flow_of(title: str, label: str):
    t, l = _fold(title), _fold(label)
    if "balance commerciale" in t and ("annuelle" in t or "mensuelle" in t):
        if l.startswith("balance"):
            return "balance", None
        if l.startswith("exportation"):
            return "export", None
        if l.startswith("importation"):
            return "import", None
        return None, None
    if re.search(r"\bexport|exporte", t) or "a l'export" in t or "l'export" in t:
        return "export", label
    if re.search(r"\bimport|importe", t) or "l'import" in t:
        return "import", label
    return None, None


def _web_rows(path: str) -> list[dict]:
    raw = open(path, "rb").read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    out = []
    for title, unit, heads, rows in _web_tables(text):
        if "cvs" in _fold(title) or "millions de dinars" not in _fold(unit):
            continue
        cols = [_col_period(h) for h in heads[1:]]
        # A period printed twice in one header (INS's phosphates table ends
        # "... 2025, 2021") cannot be told apart: drop every copy of it.
        seen = [c for c in cols if c]
        cols = [c if c and seen.count(c) == 1 else None for c in cols]
        tf = _fold(title)
        if "par pays" in tf:
            kind = "partner"
        elif "balance commerciale" in tf and ("annuelle" in tf or "mensuelle" in tf):
            kind = "headline"
        else:
            kind = "product"
        for label, cells in rows:
            flow, com = _flow_of(title, label)
            if flow is None:
                continue
            # "Exports,Produits agricoles ..." / "Imports, Europe": the flow is in the title
            lab = re.sub(r"^(exports?|imports?)\s*,\s*", "", label, flags=re.I).strip()
            if kind == "partner" and _fold(lab) == "total":
                continue              # = total exports/imports, from the balance table
            for per, c in zip(cols, cells):
                v = to_number(c)
                if per is None or v is None:
                    continue
                kw = dict(tradeflow=flow, period=per[0], frequency=per[1], value=v, unit="TND",
                          unit_multiplier=1e6, series_code=f"web: {title[:60]}")
                if kind == "headline":
                    out.append(row(**kw))
                elif kind == "partner":
                    out.append(row(**kw, partner=lab, partner_type="group"))
                else:
                    out.append(row(**kw, commodity=lab, commodity_classification="national"))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """INS stats pages: the live pages plus Wayback captures, oldest capture
    first, so the live page (the newest figures) wins any repeated key."""
    from ..schema import KEY
    files = list(dict.fromkeys([*(extras or []), path]))

    def order(p):                     # wayback_<YYYYMMDDhhmmss>_... sort first, by stamp; live last
        m = re.search(r"wayback_(\d{14})", p)
        return (0, m.group(1)) if m else (1, "")
    frames = [pd.DataFrame(_web_rows(p)) for p in sorted(files, key=order)]
    frames = [f for f in frames if not f.empty]
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates(KEY, keep="last").reset_index(drop=True)


# ------------------------------------------------------------------ notes (xlsx)
def _xrows(ws):
    return [list(r) for r in ws.iter_rows(values_only=True)]


def _window(text: str):
    """'9 mois 2026' -> (9, 2026); 'Année 2025' / '12 mois' -> (12, y)."""
    t = _fold(text)
    m = re.search(r"(\d{1,2})\s*mois\s*(\d{2,4})", t)
    if m:
        y = int(m.group(2))
        return int(m.group(1)), (2000 + y if y < 100 else y)
    m = re.search(r"annee\s*(\d{4})", t)
    if m:
        return 12, int(m.group(1))
    return None


def _per(months: int, year: int):
    if months == 12:
        return str(year), "annual"
    if months == 3:
        return f"{year}-Q1", "quarterly"
    return None


def _chapters(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        rows = _xrows(wb.worksheets[0])
    finally:
        wb.close()
    hi = next(i for i, r in enumerate(rows) if any(_fold(c) == "code" for c in r if c))
    head = rows[hi]
    jc = next(j for j, c in enumerate(head) if c and _fold(c) == "code")
    cols = []
    for j, h in enumerate(head):
        t = _fold(h or "")
        m = re.match(r"(export|import)\s+(valeur|poids)\s+(.+)$", t)
        if not m:
            continue
        w = _window(m.group(3))
        p = _per(*w) if w else None
        if p:
            cols.append((j, m.group(1), m.group(2), p))
    out = []
    for r in rows[hi + 2:]:
        code = str(r[jc]).strip() if len(r) > jc and r[jc] is not None else ""
        if not re.fullmatch(r"\d{1,2}", code):
            continue
        label = str(r[jc + 1]).strip()
        for j, flow, kind, (per, freq) in cols:
            v = r[j] if j < len(r) else None
            if not isinstance(v, (int, float)):
                continue
            if kind == "valeur":
                out.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit="TND",
                               commodity=label, commodity_classification="hs2",
                               commodity_code_nso=code.zfill(2), series_code="Balance par chapitres"))
            else:
                out.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit="kg",
                               measure="net_weight", commodity=label, commodity_classification="hs2",
                               commodity_code_nso=code.zfill(2), series_code="Balance par chapitres"))
    return out


_BLOCS = re.compile(r"^(pays |autres?|avitaillement|total|union|ue|europe$|afrique$|asie$|"
                    r"amerique$|oceanie$|maghreb|uma|monde arabe|non specifie|reste)", re.I)


def _countries(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        rows = _xrows(wb.worksheets[0])
    finally:
        wb.close()
    hi = next(i for i, r in enumerate(rows) if any(re.match(r"(export|import)\s+\d", _fold(c or ""))
                                                    for c in r))
    cols = []
    for j, h in enumerate(rows[hi]):
        m = re.match(r"(export|import)\s+(.+)$", _fold(h or ""))
        if m:
            w = _window(m.group(2))
            p = _per(*w) if w else None
            if p:
                cols.append((j, m.group(1), p))
    jl = next((j for j, c in enumerate(rows[hi]) if isinstance(c, str) and c.strip()
               and not re.match(r"(export|import)\s+\d", _fold(c))), 0)
    out = []
    for r in rows[hi + 1:]:
        lab = str(r[jl]).strip() if len(r) > jl and r[jl] is not None else ""
        if not lab or _fold(lab) in ("total", "total general", "ensemble"):
            continue
        ptype = "group" if _BLOCS.search(_fold(lab)) else "country"
        for j, flow, (per, freq) in cols:
            v = r[j] if j < len(r) else None
            if not isinstance(v, (int, float)):
                continue
            out.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit="TND",
                           unit_multiplier=1e6, partner=lab, partner_type=ptype,
                           series_code="Balance par pays"))
    return out


def _comext(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out = []
    try:
        names = {_fold(n): n for n in wb.sheetnames}
        gname = next((names[k] for k in ("global", "globale", "ensemble") if k in names), None)
        if gname:
            rows = _xrows(wb[gname])
            hi = next((i for i, r in enumerate(rows) if sum(_window(str(c)) is not None
                                                            for c in r if c) >= 2), None)
            if hi is not None:
                cols = [(j, _per(*_window(str(c)))) for j, c in enumerate(rows[hi]) if c and _window(str(c))]
                for r in rows[hi + 1:]:
                    lab = next((_fold(c) for c in r if isinstance(c, str) and c.strip()), "")
                    if lab.startswith("balance par regime") or lab.startswith("regime"):
                        break
                    flow = {"exportations": "export", "importations": "import", "solde": "balance"}.get(lab)
                    if not flow:
                        continue
                    for j, p in cols:
                        v = r[j] if j < len(r) else None
                        if p and isinstance(v, (int, float)):
                            out.append(row(tradeflow=flow, period=p[0], frequency=p[1], value=v, unit="TND",
                                           unit_multiplier=1e6, series_code="Comext Global"))
        if "gp" in names:
            rows = _xrows(wb[names["gp"]])
            hi = next((i for i, r in enumerate(rows) if any(_fold(c or "") == "groupes de produits"
                                                            for c in r if isinstance(c, str))), None)
            if hi is not None:
                win = [_fold(c) for c in rows[hi] if isinstance(c, str)]
                yrs = rows[hi + 1]
                months = next((int(m.group(1)) for w in win for m in [re.match(r"(\d{1,2})\s*mois", w)] if m),
                              12 if any(w.startswith("annee") for w in win) else None)
                cols = [(j, int(y)) for j, y in enumerate(yrs) if isinstance(y, (int, float)) and 1990 < y < 2100]
                group = None
                for r in rows[hi + 2:]:
                    lab = next((c for c in r if isinstance(c, str) and c.strip()), None)
                    if isinstance(lab, str) and all(not isinstance(c, (int, float)) for c in r):
                        if _fold(lab).startswith(("total", "deficit", "tx ")):
                            break
                        group = lab.strip()
                        continue
                    flow = {"export": "export", "import": "import", "solde": "balance"}.get(_fold(lab or ""))
                    if not flow or not group or not months:
                        continue
                    for j, y in cols:
                        p = _per(months, y)
                        v = r[j] if j < len(r) else None
                        if p and isinstance(v, (int, float)):
                            out.append(row(tradeflow=flow, period=p[0], frequency=p[1], value=v, unit="TND",
                                           unit_multiplier=1e6, commodity=group,
                                           commodity_classification="national", series_code="Comext GP"))
    finally:
        wb.close()
    return out


def parse_notes(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """December and March note annexes; the newest issue wins a repeated key."""
    from ..schema import KEY
    frames = []
    for p in dict.fromkeys([*(extras or []), path]):
        name = _fold(p.replace("\\", "/").rsplit("/", 1)[-1])
        if "chapitre" in name:
            rows = _chapters(p)
        elif "pays" in name:
            rows = _countries(p)
        else:
            rows = _comext(p)
        if rows:
            df = pd.DataFrame(rows)
            frames.append((df["period"].max(), df))
    frames.sort(key=lambda t: t[0])
    df = pd.concat([f for _, f in frames], ignore_index=True)
    return df.drop_duplicates(KEY, keep="last").reset_index(drop=True)
