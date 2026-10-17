"""Zimbabwe -- Ministry of Finance, Zimbabwe Public Debt Management Office
(ZPDMO), "Public Debt Report 2023" (stocks at end September 2023), read from
a Wayback `id_` copy of the Treasury's own upload: zimtreasury.gov.zw now
answers 404 at its root and for this file (checked 2026-10-08).

PUBLISHER: ZPDMO; tables sourced "Zimbabwe Public Debt Management Office and
the Reserve Bank of Zimbabwe". COVERAGE: "Total public and publicly
guaranteed (PPG) debt" -- external (bilateral, multilateral, and the
liabilities on the RBZ balance sheet) and domestic (government securities,
domestic arrears, compensation of former farm owners). The report flags the
figures as "preliminary pending validation and reconciliation"; that is
carried in `series_code`.

TABLES READ:
  * Table 1 "Total PPG Debt Stock (Z$ billions)" -> unit "ZWL billion";
  * Table 2 the same in US$ millions -> unit "USD million";
  * Table 5 "PPG External Debt Stock (US$ millions)" -- ONLY its extra
    breakdown of the RBZ-balance-sheet liabilities (regional multilateral
    creditors, financial institutions, suppliers, blocked funds), which
    Table 2 does not print; its other rows repeat Table 2 and are checked
    equal, not emitted twice.
Each row prints six columns -- DOD (disbursed outstanding debt), PRA
(principal arrears), IRA (interest arrears), Penalties, PRA+IRA+Penalties,
Total -- emitted as components "<row> [<column>]". A row printing ONE value
(the RBZ liabilities, which carry no arrears) is that row's Total. Rows
printing a partial set (Table 1's "Assumed by Treasury in 2023 9,933 - 9,933")
cannot be placed by column and are not collected from Table 1; Table 2 prints
the same rows unambiguously. Table 3 repeats Table 1's domestic block.
Debt-service, borrowing-plan, guarantee and loan tables are flows or
pipelines, not stocks.

PERIOD "2023-09" (end-September stock), frequency monthly.

TRAPS: one value is split by a stray space ("3,5 56" = 3,556) and is
rejoined only when the joined form is a well-formed thousands number; "-"
is nil and skipped. Row labels keep the report's own numbering ("a.PPG
External Debt (1+2+3)").

CROSS-CHECK: Total PPG debt US$17 691 m (DOD 10 689, arrears and penalties
7 002); external 12 688; domestic 5 003; Z$ total 96 714 bn; RBZ-balance-
sheet liabilities US$3 556 m.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_COLS = ["DOD", "PRA", "IRA", "Penalties", "PRA+IRA+Penalties", "Total"]
_TITLES = {
    "Table 1": ("Total Public and Publicly Guaranteed Debt Stock", "ZWL billion"),
    "Table 2": ("Total Public and Publicly Guaranteed Debt Stock", "USD million"),
    "Table 5": ("Public and Publicly Guaranteed External Debt Stock", "USD million"),
}
_CODE = "ZPDMO Public Debt Report 2023 (preliminary)"
_TOK = re.compile(r"-|\d{1,3}(?:,\d{3})*(?:\.\d+)?")
# placeholder protecting a year inside a label; NOT whitespace (\s would
# match a no-break space and split the label anyway)
_NBSP = "§"


def _rejoin(s: str) -> str:
    # "3,5 56" -> "3,556": a broken thousands group, rejoined only when the
    # result is well formed.
    return re.sub(r"\b(\d{1,3}),(\d{1,2}) (\d{1,2})\b",
                  lambda m: f"{m.group(1)},{m.group(2)}{m.group(3)}"
                  if len(m.group(2) + m.group(3)) == 3 else m.group(0), s)


def _rows(text: str):
    out = []
    for ln in text.splitlines():
        # A year inside a label ("Assumed by Treasury in 2023 1,817") is part
        # of the label, not a value: protect it before splitting.
        s = re.sub(r"\b(in) (20\d\d)\b", "\\1" + _NBSP + "\\2", _rejoin(ln.strip()))
        if s.startswith("Source"):
            break
        m = re.match(r"^(.*?[A-Za-z)\d])\s+((?:(?:-|[\d,.]+)\s*)+)$", s)
        if not m or not re.search(r"[A-Za-z]", m.group(1)):
            continue
        toks = _TOK.findall(m.group(2))
        if not toks or "".join(toks).replace("-", "") == "" and len(toks) < 2:
            continue
        # footnote digit ("Others2"); a protected year gets its space back
        label = re.sub(r"(?<=[a-z])\d$", "", m.group(1)).replace(_NBSP, " ").strip()
        out.append((label, toks))
    return out


def _table(pages, key):
    title, unit = _TITLES[key]
    for t in pages:
        m = re.search(rf"{key}:\s*{re.escape(title)}[^\n]*\n", t)
        if m and "DOD" in t[m.end():m.end() + 200]:
            return _rows(t[m.end():]), unit
    raise ValueError(f"ZPDMO: {key} not found")


def _num(tok):
    return None if tok == "-" else float(tok.replace(",", ""))


def parse(path: str, extras=None) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    recs, seen = [], {}
    for key in ("Table 2", "Table 1"):
        rows, unit = _table(pages, key)
        for label, toks in rows:
            if label.startswith("DOD"):
                continue
            if len(toks) == len(_COLS):
                vals = dict(zip(_COLS, toks))
            elif len(toks) == 1:
                vals = {"Total": toks[0]}
            else:
                continue                      # partial row: column not placeable
            for col, tok in vals.items():
                v = _num(tok)
                if v is not None:
                    recs.append({"component": f"{label} [{col}]", "unit": unit, "value": v})
            if unit == "USD million":
                seen[label] = vals.get("Total")

    # Table 5: only the RBZ-liability breakdown Table 2 lacks; parents qualify
    # the repeated creditor names.
    rows, unit = _table(pages, "Table 5")
    parent = None
    for label, toks in rows:
        if label.startswith("DOD"):
            continue
        if label in seen or re.sub(r"^3\. ", "3.", label) in seen:
            t2 = seen.get(label, seen.get(re.sub(r"^3\. ", "3.", label)))
            tot = toks[-1] if toks else None
            if t2 is not None and tot != t2:
                raise ValueError(f"ZPDMO: Table 5 {label!r} total {tot} != Table 2 {t2}")
            if label.startswith(("Assumed by Treasury", "Other Liabilities")):
                parent = label
            continue
        if parent and len(toks) == 1:
            recs.append({"component": f"{parent}: {label} [Total]", "unit": unit,
                         "value": _num(toks[0])})
    df = pd.DataFrame(recs)
    df["period"], df["frequency"], df["measure"], df["series_code"] = (
        "2023-09", "monthly", "stock", _CODE)

    usd = df[df.unit == "USD million"].set_index("component")["value"]
    tot = usd["Total PPG Debt (a+b) [Total]"]
    ext = usd["a.PPG External Debt (1+2+3) [Total]"]
    dom = usd["b. Domestic Debt [Total]"]
    if abs(ext + dom - tot) > 1.0:
        raise ValueError(f"ZPDMO: external {ext} + domestic {dom} != total {tot}")
    df = df[["component", "period", "frequency", "measure", "value", "unit",
             "series_code"]]
    # EXTRAS are ZPDMO Annual Public Debt Bulletins (end-December), read by
    # `zimbabwe_pdmo_annual`; one whose tables differ (the 2020 bulletin is in
    # US$ under other captions; the 2018 capture is truncated) is skipped
    # with a message.
    from .zimbabwe_pdmo_annual import parse_bulletin
    more = []
    for p in extras or []:
        try:
            more += parse_bulletin(p)
        except Exception as e:                                  # noqa: BLE001
            print(f"  [zimbabwe] annual bulletin skipped ({p.replace(chr(92), '/').rsplit('/', 1)[-1]}): {type(e).__name__} {e}")
    return pd.concat([df, pd.DataFrame(more)], ignore_index=True) if more else df
