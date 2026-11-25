"""Shared helpers for merchandise-trade parsers.

**Numbers and periods** are the PPI helpers (one implementation): `to_number`
(decimal comma, thin spaces, a dash / "n.d." / ".." -> None, never 0),
`month_period`, `quarter_period` (English, French, Portuguese).

**Scale and currency.** `scale_from_text("Valeurs en millions de FCFA", "SEN")`
-> (1e6, "XOF"); `("in thousands of US dollars")` -> (1e3, "USD"). Reads the
table's own caption; returns (None, None) for what it cannot tell -- then the
parser must not guess. The CFA franc is resolved by country (WAEMU XOF, CEMAC
XAF), since captions say only "FCFA".

**Rows.** `row(...)` builds one row and refuses a flow, classification, partner
type, measure, frequency, price basis or multiplier outside the schema
vocabulary. "All products" / "All partners" are spelled by the helper:
pass `commodity=None` / `partner=None` for the totals.
"""
from __future__ import annotations

import re

from indicators.ppi.parsers._common import _fold, month_period, quarter_period, to_number  # noqa: F401
from ..schema import (COMMODITY_CLASSIFICATIONS, FREQUENCIES, MEASURES, MULTIPLIERS, PARTNER_TYPES,
                      PRICE_BASES, PRICES, TRADE_SYSTEMS, TRADEFLOWS)

_WAEMU = {"BEN", "BFA", "CIV", "GNB", "MLI", "NER", "SEN", "TGO"}
_CEMAC = {"CMR", "CAF", "TCD", "COG", "GNQ", "GAB"}

_SCALE_WORDS = ((r"\bmil(?:l)?iards?\b|\bbillions?\b|\bbn\b|\bmil milh[oõ]es\b", 1e9),
                (r"\bmillions?\b|\bmilh[oõ]es\b|\bmn\b|\bmio\b|\bm\.?\s*(?:fcfa|usd|\$)", 1e6),
                (r"\bthousands?\b|\bmilliers?\b|\bmil\b|\b000\b|'000|\bk\b", 1e3))
_CURRENCY_WORDS = ((r"\bf\.?\s*cfa\b|\bfrancs? cfa\b|\bcfa\b", "CFA"),
                   (r"\bus\s*\$|\busd\b|\bus dollars?\b|\bdollars? (?:americains|us)\b|\bdolares\b", "USD"),
                   (r"\beuros?\b|\beur\b|€", "EUR"))


def scale_from_text(text: str, iso3: str = "") -> tuple[float | None, str | None]:
    t = _fold(text)
    mult = next((m for rx, m in _SCALE_WORDS if re.search(rx, t)), None)
    cur = next((c for rx, c in _CURRENCY_WORDS if re.search(rx, t)), None)
    if cur == "CFA":
        cur = "XOF" if iso3 in _WAEMU else "XAF" if iso3 in _CEMAC else None
    return mult, cur


# A partner line filed as a country that is not one. The world total under
# another name becomes the world row; aggregates, unknowns and non-territories
# become groups. Continents only as the WHOLE label ("Afrique"), since
# "South Africa" and "Central African Republic" are countries.
_WORLD_LABEL = re.compile(r"(?:total\s+)?(?:world|monde|mundo)(?:\s+new)?|total|total general|grand total")
_NOT_COUNTRY = re.compile(
    r"\b(?:various|divers|others?|autres?|rest of|reste du|not specified|non specifie|non determin|"
    r"indetermin|nao definido|unknown|inconnu|high[- ]?sea|ships?\b|aircrafts?|bunkers?|stores|"
    r"abastecimento|epz|export processing|free zones?|zone franche|regional office|neutral zone|"
    r"change of warehouse|nacoes unidas|nations unies|union euro|ecowas|cedeao|uemoa|cemac|ceeac|"
    r"comesa|sadc|sacu|cepgl|arab league|ligue arabe|dont\b)")
_CONTINENT = re.compile(r"(?:europe|asie|asia|afrique|africa|amerique|america|americas|oceanie|oceania|"
                        r"moyen[- ]orient|middle east|eac|eu|ue|ce)")


def classify_partner(label: str, partner_type: str) -> tuple[str | None, str]:
    """(partner, partner_type) with a mis-filed 'country' corrected; others unchanged."""
    if partner_type != "country":
        return label, partner_type
    n = _fold(label).strip(" .:")
    if _WORLD_LABEL.fullmatch(n):
        return None, "world"
    if _NOT_COUNTRY.search(n) or _CONTINENT.fullmatch(n):
        return label, "group"
    return label, partner_type


def row(*, tradeflow: str, period: str, frequency: str, value, unit: str,
        unit_multiplier: float = 1.0, commodity: str | None = None,
        commodity_classification: str = "", commodity_code_nso: str = "",
        partner: str | None = None, partner_type: str = "world", measure: str = "value",
        price_basis: str = "", prices: str = "current", trade_system: str = "",
        series_code: str = "") -> dict:
    if partner is not None:
        partner, partner_type = classify_partner(partner, partner_type)
    if commodity is None:
        commodity, commodity_classification = "All products", ""
    elif not commodity_classification:
        raise ValueError(f"commodity {commodity!r} needs a commodity_classification")
    if partner is None:
        partner, partner_type = "All partners", "world"
    elif partner_type == "world":
        raise ValueError(f"partner {partner!r} needs partner_type 'country' or 'group'")
    for name, v, allowed in (("tradeflow", tradeflow, TRADEFLOWS),
                             ("commodity_classification", commodity_classification, COMMODITY_CLASSIFICATIONS),
                             ("partner_type", partner_type, PARTNER_TYPES), ("measure", measure, MEASURES),
                             ("frequency", frequency, FREQUENCIES), ("price_basis", price_basis, PRICE_BASES),
                             ("prices", prices, PRICES), ("trade_system", trade_system, TRADE_SYSTEMS)):
        if v not in allowed:
            raise ValueError(f"unknown {name} {v!r}")
    if float(unit_multiplier) not in MULTIPLIERS:
        raise ValueError(f"unit_multiplier {unit_multiplier!r} not in {sorted(MULTIPLIERS)}")
    if value is None:
        raise ValueError(f"no value for {tradeflow} {commodity!r} {partner!r} {period} -- skip the cell")
    return {"tradeflow": tradeflow, "commodity": str(commodity).strip(),
            "commodity_classification": commodity_classification,
            "commodity_code_nso": str(commodity_code_nso).strip(), "partner": str(partner).strip(),
            "partner_type": partner_type, "period": period, "frequency": frequency, "measure": measure,
            "value": float(value), "unit": unit, "unit_multiplier": float(unit_multiplier),
            "price_basis": price_basis, "prices": prices, "trade_system": trade_system,
            "series_code": series_code}
