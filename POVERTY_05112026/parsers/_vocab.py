"""Shared column vocabularies and row builders for the poverty layouts.

Every entry was written against a report's ACTUAL rendered text. Never assume
the column order: the commonest silent error in these tables is P1 and P2, or a
contribution and a rate, read in each other's place -- all are plausible
percentages. `schema.validate_poverty` enforces P0 >= P1 >= P2 per group, which
catches a swap of the FGT measures but not of a rate with a share.
"""
from __future__ import annotations
import re

_RURAL = {"locality": "rural", "locality_label": "Rural"}
_URBAN = {"locality": "urban", "locality_label": "Urbain"}
_ALL = {"locality": "all", "locality_label": "Total"}


def loc3_p0_pop_part(rural="Rural", urban="Urbain"):
    """Rural | Urbain | Total, each `P0 | Population | Part` (EHCVM profiles).
    `Part` is the category's share of that locality's population."""
    out = []
    for loc, lab in (("rural", rural), ("urban", urban), ("all", "Total")):
        out += [{"metric": "headcount", "locality": loc, "locality_label": lab},
                {"skip": True},                                   # population count
                {"metric": "population_share", "locality": loc, "locality_label": lab}]
    return out


def label_rows(topic: str, labels, **attrs) -> list[dict]:
    """One row spec per printed category label, matched at line start and
    followed by the first number, so "Secondaire 1" never matches
    "Secondaire 1 ..." of a different block (blocks are scoped by start/end)."""
    out = []
    for lab in labels:
        out.append({"match": r"^" + re.escape(lab) + r"(?=\s+[-\d,])",
                    "topic": topic, "characteristic": lab, **attrs})
    return out
