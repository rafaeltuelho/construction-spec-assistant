"""Constraint parsing utilities for the Construction Spec Assistant backend."""

import re
from typing import List, Dict, Any, Optional, Tuple


# Pre-compiled patterns (cover common spec language)
P_THROUGH = re.compile(r'\b(?:between|from)\s+([0-9]+(?:\.[0-9]+)?)\s*(\w+)?\s+(?:to|and|-|–|—)\s*([0-9]+(?:\.[0-9]+)?)\s*(\w+)?', re.I)
P_RANGE_DASH = re.compile(r'\b([0-9]+(?:\.[0-9]+)?)\s*(\w+)?\s*[–—-]\s*([0-9]+(?:\.[0-9]+)?)\s*(\w+)?')
P_GE = re.compile(r'\b(?:≥|>=|not less than|minimum|min\.|at least)\b', re.I)
P_LE = re.compile(r'\b(?:≤|<=|not more than|maximum|max\.|no more than|up to|not to exceed|nte)\b', re.I)
P_GT = re.compile(r'\b(?:>|greater than|more than)\b', re.I)
P_LT = re.compile(r'\b(?:<|less than)\b', re.I)
P_PLUSMINUS = re.compile(r'([0-9]+(?:\.[0-9]+)?)\s*(\w+)?\s*(?:±|\+/-)\s*([0-9]+(?:\.[0-9]+)?)\s*(\w+)?')

# Find a primary (num, unit) pair
P_NUMUNIT = re.compile(r'([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%/]+)?')

# Alt value in parentheses, e.g. "42 inches (1067 mm)"
P_ALT_PARENS = re.compile(r'\(([^)]+)\)')


def _first_num_unit(s: str) -> Tuple[Optional[float], Optional[str]]:
    """Extract first number and unit from string."""
    m = P_NUMUNIT.search(s)
    if not m: 
        return (None, None)
    num = float(m.group(1))
    unit = m.group(2).lower() if m.group(2) else None
    return (num, unit)


def parse_value_constraints(value_raw: str) -> Dict[str, Any]:
    """
    Parse a single value.raw into structured constraints:
    returns fields that you can merge back into f["value"]/f["op"]/f["qualifiers"].
    Handles: ranges (between X and Y, X–Y), >=, <=, >, <, ± tolerance, alt units in parentheses.
    """
    s = value_raw.strip()

    # ± tolerance
    m = P_PLUSMINUS.search(s)
    if m:
        num = float(m.group(1))
        unit = (m.group(2) or "").lower() or None
        tol = float(m.group(3))
        tol_unit = (m.group(4) or "").lower() or unit
        return {
            "op": "~",
            "value": {"type": "quantity", "num": num, "unit": unit or tol_unit, "raw": value_raw},
            "qualifiers": {"tolerance": {"plus_minus": tol, "unit": tol_unit or unit}}
        }

    # between / from ... to ...
    m = P_THROUGH.search(s) or P_RANGE_DASH.search(s)
    if m:
        a = float(m.group(1))
        a_u = (m.group(2) or "").lower() or None
        b = float(m.group(3))
        b_u = (m.group(4) or "").lower() or None
        unit = a_u or b_u  # prefer first if present
        lo, hi = (a, b) if a <= b else (b, a)
        return {
            "op": "between",
            "value": {"type": "range", "min": lo, "max": hi, "unit": unit, "raw": value_raw}
        }

    # inequalities (>=, <=, >, <)
    if P_GE.search(s):
        num, unit = _first_num_unit(s)
        return {"op": ">=", "value": {"type": "quantity", "num": num, "unit": unit, "raw": value_raw}}
    if P_LE.search(s):
        num, unit = _first_num_unit(s)
        return {"op": "<=", "value": {"type": "quantity", "num": num, "unit": unit, "raw": value_raw}}
    if P_GT.search(s):
        num, unit = _first_num_unit(s)
        return {"op": ">", "value": {"type": "quantity", "num": num, "unit": unit, "raw": value_raw}}
    if P_LT.search(s):
        num, unit = _first_num_unit(s)
        return {"op": "<", "value": {"type": "quantity", "num": num, "unit": unit, "raw": value_raw}}

    # plain quantity (fallback)
    num, unit = _first_num_unit(s)
    if num is not None:
        out = {"op": "=", "value": {"type": "quantity", "num": num, "unit": unit, "raw": value_raw}}
    else:
        out = {"op": "=", "value": {"type": "text", "raw": value_raw}}

    # alt units in parentheses → stash in qualifiers.alt_values
    alts = []
    for m in P_ALT_PARENS.finditer(s):
        # naive parse "1067 mm" inside the parens
        n2, u2 = _first_num_unit(m.group(1))
        if n2 is not None:
            alts.append({"num": n2, "unit": u2})
    if alts:
        out.setdefault("qualifiers", {})
        out["qualifiers"]["alt_values"] = alts
    return out


def apply_ranges_inequalities(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply range and inequality parsing to facts."""
    out = []
    for f in facts:
        v = f.get("value", {})
        raw = v.get("raw") or ""
        parsed = parse_value_constraints(raw)
        # merge: keep original raw, but update structured fields
        f["op"] = parsed.get("op", f.get("op", "="))
        # keep both raw + structured
        f["value"]["type"] = parsed["value"]["type"]
        # copy numeric fields if present
        for k in ["num", "unit", "min", "max"]:
            if k in parsed["value"] and parsed["value"][k] is not None:
                f["value"][k] = parsed["value"][k]
        # add qualifiers if any
        if "qualifiers" in parsed:
            # Ensure qualifiers is a dict (handle None case)
            f["qualifiers"] = f.get("qualifiers") or {}
            f["qualifiers"].update(parsed["qualifiers"])
        out.append(f)
    return out


DEFAULT_TOLERANCES_BY_UNIT = {
    "fpm": {"abs": 5.0},
    "in":  {"abs": 0.25},
    "mm":  {"abs": 2.0},
    "lb":  {"pct": 0.0},
}


def tolerances_for_fact(
    spec_fact: Dict[str, Any],
    policy_by_canonical: Optional[Dict[str, Any]] = None,
    default_by_unit: Optional[Dict[str, Any]] = None
) -> Tuple[float, float]:
    """Calculate tolerances for a fact based on policy and defaults."""
    policy_by_canonical = policy_by_canonical or {}
    default_by_unit = default_by_unit or DEFAULT_TOLERANCES_BY_UNIT

    # 1) explicit tolerance in the fact (from "±" parse) wins
    tol = (spec_fact.get("qualifiers") or {}).get("tolerance")
    if tol and "plus_minus" in tol:
        return float(tol["plus_minus"]), 0.0

    # 2) policy by canonical
    canon = spec_fact.get("attribute", {}).get("canonical")
    if canon and canon in policy_by_canonical:
        t = policy_by_canonical[canon]
        return float(t.get("abs", 0.0)), float(t.get("pct", 0.0))

    # 3) fallback by unit
    unit = (spec_fact.get("value") or {}).get("unit", "")
    t = default_by_unit.get((unit or "").lower(), {})
    return float(t.get("abs", 0.0)), float(t.get("pct", 0.0))
