"""Kenya QLFS back-issues (2020 Q1 - 2021 Q1), read cell by cell.

WHY NOT THE ENGINE. These five issues print the same tables as 2022 Q4 -- the
same captions, the same "Quarter X | Quarter Y | Quarter Z | Change" columns --
but pdfplumber letter-spaces their digits in forms the engine's
`despace_numbers` does not repair:

    15-19 7 93,017 5 ,177,385 1 5.3 1 ,784,269 ... - 8 .1 1 0.4

and some cells are a bare "-" (an empty cell), which a number-counting reader
drops, sliding every later value one column left. That is how an earlier
backfill produced 428 merge keys whose values disagreed between issues -- real
population figures published as `employed`. It was withdrawn.

PyMuPDF has neither problem. It returns each cell whole, one per line
("793,017", "5,177,385", "15.3"), and a "-" cell as a "-" token in its column
position. So each row is read as an ordered list of CELLS, a "-" is kept as an
empty cell, and the layout's own column specs (`kenya_unemployment.LAYOUT`,
re-dated per issue) say what each position means. Nothing about the meaning of
a column is restated here.

THE GUARD THAT WOULD HAVE CAUGHT THE WITHDRAWN BACKFILL: every cohort table
prints, per quarter, (numerator..., denominator, rate), and the rate must equal
100 x numerator / denominator to rounding (Table 6's LU2 sums its first two
cells). A cell read one column off fails this at once, so a mis-read issue
raises instead of publishing. It is checked on every row of every issue.

The "Change" columns are not read: their negative signs arrive AFTER the
number ("8.1", "-") and they are derived anyway.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF

from .pdf_key_indicators import _emit, _merge

_CAPTION = re.compile(r"^Table \d+[ab]?:")
_NUM = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^-?\d+\.\d+$")
_CONTENTS = ("list of tables", "table of contents")


def _tokens(path: str) -> list[list[str]]:
    """Per page, the non-empty text lines PyMuPDF yields, contents pages out."""
    out = []
    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text()
            if any(c in text.lower() for c in _CONTENTS):
                out.append([])
                continue
            out.append([ln.strip() for ln in text.splitlines() if ln.strip()])
    return out


def _cells(tok: str) -> list[str] | None:
    """A value token as cells ("1,091,495 17,727,199" is two), or None if the
    token is not purely values."""
    parts = tok.split()
    if parts and all(p == "-" or _NUM.match(p) for p in parts):
        return parts
    return None


def _num(cell: str) -> float | None:
    return None if cell == "-" else float(cell.replace(",", ""))


def _region(pages: list[list[str]], caption: str) -> list[str]:
    """Tokens from a table's caption to the next caption on its page."""
    rx = re.compile(caption, re.I)
    for toks in pages:
        for i, t in enumerate(toks):
            if rx.search(t):
                out = []
                for u in toks[i + 1:]:
                    if _CAPTION.match(u) or u.startswith("Source"):
                        break
                    out.append(u)
                return out
    raise ValueError(f"caption {caption!r} not found")


def _rows(region: list[str], specs: list[dict]) -> dict[int, list[str]]:
    """Row spec index -> the cells that follow its label, up to the next label."""
    got, cur = {}, None
    for tok in region:
        hit, rest = None, None
        for ri, r in enumerate(specs):
            m = re.search(r["match"], tok, re.I)
            if not m or ri in got:
                continue
            # A LABEL IS THE LABEL ALONE, or the label then values. The column
            # header "Total Total Total" also matches `^Total\b`, and taking it
            # would consume the spec before the real Total row is reached.
            rest = tok[m.end():].strip()
            if rest == "" or _cells(rest) is not None:
                hit = ri
                break
        if hit is not None:
            cur = hit
            got[cur] = _cells(rest) or []
            continue
        cells = _cells(tok)
        if cells is not None and cur is not None:
            got[cur].extend(cells)
        elif cells is None:
            # A header or note line ends the row. PyMuPDF emits the column
            # header ("Labour Force Total Population Rate") as single-word
            # tokens, so a bare "Total" there opens the Total row with no
            # cells; release it so the real Total row can take the spec.
            if cur is not None and not got[cur]:
                del got[cur]
            cur = None
    if cur is not None and not got[cur]:
        del got[cur]
    return got


def _check_rates(cells: list[str], groups: int, per: int, where: str) -> None:
    """(numerator..., denominator, rate) per quarter group must agree."""
    for g in range(groups):
        grp = [_num(c) for c in cells[g * per:(g + 1) * per]]
        if None in grp or grp[-2] in (None, 0):
            continue
        num, den, rate = sum(grp[:-2]), grp[-2], grp[-1]
        if abs(100 * num / den - rate) > 0.151:
            raise ValueError(f"{where} group {g}: {grp} -- {rate} is not "
                             f"100 x {num:,.0f} / {den:,.0f}; a cell is "
                             f"misread")


# TABLES WHOSE ROW LABELS ARE NOT IN THE TEXT LAYER, by (issue, block id).
# 2020 Q1's Table 3 prints its eleven rows of numbers straight after the
# caption with no "15-19" ... "Total" labels at all. Assigning them by order
# would be a guess, so the table is not read for that issue -- and the entry is
# re-checked: if a label ever appears, the skip raises so it is removed.
# Its 2020 Q1 and 2019 Q4 columns are restated by later issues; only 2019 Q1's
# employed-by-cohort figures are lost.
_UNLABELLED = {("2020-Q1", "t3")}


def read_issue(path: str, cfg: dict) -> list[dict]:
    """Every value the layout `cfg` (already re-dated for this issue) defines,
    read from PyMuPDF cells."""
    pages = _tokens(path)
    out: list[dict] = []
    period, reference = cfg["period"], cfg["reference_period"]
    for tbl in cfg["tables"]:
        cols, specs = tbl["columns"], tbl["rows"]
        if tbl.get("blocks"):
            caption = tbl["blocks"][0]["match"]
            block = tbl["blocks"][0]
            region = _region(pages, caption)
            data_cols = cols[:-2]                    # the two "Change" columns
            per = len(data_cols) // 3
            got = _rows(region, specs)
            if (cfg["period"], block.get("id")) in _UNLABELLED:
                if got:
                    raise ValueError(f"{path}: {caption!r} now carries row "
                                     f"labels -- remove it from _UNLABELLED")
                continue
            missing = [specs[i]["match"] for i in range(len(specs)) if i not in got]
            if missing:
                raise ValueError(f"{path}: {caption!r} -- rows not found: {missing}")
            for ri, cells in got.items():
                if len(cells) < len(data_cols):
                    raise ValueError(f"{path}: {caption!r} row {specs[ri]['match']!r}"
                                     f" has {len(cells)} cells, needs "
                                     f"{len(data_cols)}: {cells}")
                cells = cells[:len(data_cols)]
                _check_rates(cells, 3, per, f"{path} {caption} {specs[ri]['match']}")
                for cspec, cell in zip(data_cols, cells):
                    v = _num(cell)
                    if cspec.get("skip") or v is None:
                        continue
                    c = _merge(tbl.get("defaults", {}), block, specs[ri], cspec)
                    out.append(_emit(c, v, cfg, period, reference, cell))
        else:
            out += _table_1(pages, tbl, cfg, path)
    return out


# TABLE 1 WAS RENAMED ROW BY ROW ACROSS ISSUES. The same indicator carries a
# different printed label in 2020 Q2-2021 Q1 than in 2022 Q4, which the layout
# was written against. Each mapping below is a rename of ONE indicator, never a
# merge of two -- the report's own footnotes define the series identically
# ("2 Includes the unemployed under the strict definition and the potential
# labourforce" is LU3 in both vintages).
_T1_RENAMED = [
    (r"^Combined rate of unemployment and potential labou?r ?force \[LU3\]",
     "Unemployment Rate [LU3]"),
    (r"^Labour Force Participation Rate\s*\(%\)", "Labour Force Participation (%)"),
    (r"^Not in Labou?r Force \(Inactive\)$", "Not in Labor Force (Inactive)"),
]


def _table_1(pages: list[list[str]], tbl: dict, cfg: dict, path: str) -> list[dict]:
    """The headline table: dot-leader labels, three quarter columns, the
    current (last) one taken -- as the layout's `take: trailing` does.

    A label may be one token with dot leaders, carry its values inline after
    them, or be split over several word tokens ("Combined" "rate" "of" ...).
    """
    region = _region(pages, r"^Table 1: Key Labour Market Indicators")
    pairs, parts, cur = [], [], None
    for tok in region:
        # The column header ("Indicator", "Quarter 4", "2019", ...) is not part
        # of any label; left in, it was prepended to the first one and
        # "Population (15-64)" no longer began its own label.
        if re.fullmatch(r"Indicator|(?:Quarter \d,?\s*\d{0,4}\s*)+|\d{4}", tok):
            continue
        norm = re.sub(r"\s*…", "...", tok)
        norm = re.sub(r"\s+(?=\.)", "", norm)
        cells = _cells(tok)
        if cells is not None:
            if cur is not None:
                cur[1].extend(cells)
            elif parts:
                cur = [" ".join(parts), list(cells)]
                pairs.append(cur)
                parts = []
            continue
        cur = None
        # Values inline after the leaders. The value group must START at a
        # digit or a sign: left free it swallowed the leader dots themselves,
        # and the whole token then failed to read as values.
        m = re.match(r"^(.*?[^\d\s.,-].*?)(?:\.{2,}|\s{3,})\s*([\d-][\d,.\s-]*)$", norm)
        if m and _cells(m.group(2)) is not None:
            cur = [" ".join(parts + [m.group(1)]), _cells(m.group(2))]
            pairs.append(cur)
            parts = []
        elif re.search(r"\.{2,}$", norm):
            parts = [norm]            # a complete dot-leader label
        else:
            parts.append(norm)        # a word of a split label
    out, taken = [], set()
    for lab, cells in pairs:
        lab = re.sub(r"[.\s]+$", "", lab).strip()
        for rx, canon in _T1_RENAMED:
            if re.search(rx, lab, re.I):
                lab = canon
        probe = lab + "...."           # the layout's patterns expect leaders
        for ri, r in enumerate(tbl["rows"]):
            if ri in taken or not re.search(r["match"], probe, re.I):
                continue
            if len(cells) != 3:
                raise ValueError(f"{path}: Table 1 {lab!r} reads {cells}")
            v = _num(cells[-1])
            if v is not None:
                c = _merge(tbl.get("defaults", {}), r, {})
                out.append(_emit(c, v, cfg, cfg["period"],
                                 cfg["reference_period"], lab))
            taken.add(ri)
            break
    need = {r"^Population \(15", r"^Labour Force\.{2,}", r"^Employed\.{2,}",
            r"^Unemployed1", r"^Unemployment Rate \[?LU1"}
    got = {tbl["rows"][ri]["match"] for ri in taken}
    if not need <= got:
        raise ValueError(f"{path}: Table 1 headline rows missing: {need - got}")
    return out
