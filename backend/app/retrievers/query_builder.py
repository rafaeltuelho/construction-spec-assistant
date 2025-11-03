"""
Query builder for hybrid search.

This module builds dense and sparse queries from specification facts for hybrid retrieval.
"""

from typing import Dict, List, Any
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class QueryTerms(BaseModel):
    """Query representations for hybrid search."""

    dense: str  # Natural language query for dense retrieval
    sparse: Dict[str, Any]  # Structured sparse query with must/should/boost


def _expand_phrase(phrase: str) -> List[str]:
    """
    Expand a phrase into multiple variations for sparse search.

    Args:
        phrase: Input phrase

    Returns:
        List of phrase variations
    """
    if not phrase:
        return []

    out = []
    phrase = phrase.lower().strip()

    # Original phrase
    out.append(phrase)

    # Replace hyphens with spaces
    if "-" in phrase:
        out.append(phrase.replace("-", " "))

    # Replace spaces with hyphens
    if " " in phrase:
        out.append(phrase.replace(" ", "-"))

    # Remove special characters
    cleaned = "".join(c if c.isalnum() or c in " -" else "" for c in phrase)
    if cleaned != phrase:
        out.append(cleaned)

    # Quote multi-word phrases
    if " " in phrase:
        out.append(f'"{phrase}"')

    return list(set(out))


def _numeric_terms(value: Dict[str, Any]) -> List[str]:
    """
    Extract numeric terms from a quantity value.

    Args:
        value: Value dict with num, unit, etc.

    Returns:
        List of numeric terms
    """
    terms = []

    if value.get("num") is not None:
        terms.append(str(value["num"]))

    if value.get("unit"):
        unit = value["unit"]
        terms.append(unit)

        # Add common unit variations
        unit_variations = {
            "lbs": ["pounds", "lb"],
            "fpm": ["feet per minute", "ft/min"],
            "psi": ["pounds per square inch"],
            "in": ["inches", "inch"],
            "ft": ["feet", "foot"],
            "mm": ["millimeters", "millimeter"],
            "cm": ["centimeters", "centimeter"],
            "m": ["meters", "meter"],
            "kg": ["kilograms", "kilogram"],
            "mph": ["miles per hour"],
            "kph": ["kilometers per hour"],
        }

        if unit.lower() in unit_variations:
            terms.extend(unit_variations[unit.lower()])

    if value.get("raw"):
        terms.append(value["raw"])

    return terms


def _value_text_terms(value: Dict[str, Any]) -> List[str]:
    """
    Extract text terms from a non-quantity value.

    Args:
        value: Value dict

    Returns:
        List of text terms
    """
    terms = []

    if value.get("raw"):
        terms.extend(_expand_phrase(value["raw"]))

    return terms


def build_query_terms_from_fact(spec_fact: Dict[str, Any]) -> QueryTerms:
    """
    Build query terms from a specification fact.

    Args:
        spec_fact: Fact dict with entity, attribute, value, operator

    Returns:
        QueryTerms with dense and sparse representations

    Example:
        Input: {
            "entity": {"type": "Elevator"},
            "attribute": {"raw": "capacity"},
            "value": {"raw": "2500 lbs", "type": "quantity", "num": 2500, "unit": "lbs"},
            "op": ">="
        }

        Output: QueryTerms(
            dense="Find submittal statements about Elevator capacity.",
            sparse={
                "must": ["capacity"],
                "should": ["elevator", "2500", "lbs", "pounds"],
                "boost": {"capacity": 2.5}
            }
        )
    """
    # Extract components
    entity = spec_fact.get("entity", {}) or {}
    attribute = spec_fact.get("attribute", {}) or {}
    value = spec_fact.get("value", {}) or {}
    operator = spec_fact.get("op", "=")

    # Get attribute raw text
    attr_raw = attribute.get("raw", "") or attribute.get("canonical", "")

    # Build dense query (natural language for embeddings)
    subject = entity.get("type", "") or entity.get("name", "")
    dense_bits = [subject, attr_raw]

    # Add value for non-quantity types
    if value.get("type") != "quantity" and value.get("raw"):
        dense_bits.append(value["raw"])

    dense_query = " ".join(b for b in dense_bits if b).strip()
    if dense_query:
        dense_query = f"Find submittal statements about {dense_query}."
    else:
        dense_query = attr_raw or subject or "product requirement"

    # Build sparse terms (keywords for BM25)
    sparse_terms: List[str] = []

    # Add attribute terms (most important)
    if attr_raw:
        sparse_terms.extend(_expand_phrase(attr_raw))

    # Add value terms
    if value.get("type") == "quantity":
        sparse_terms.extend(_numeric_terms(value))
    else:
        sparse_terms.extend(_value_text_terms(value))

    # Add entity terms (light hints)
    for key in ("manufacturer", "name", "type"):
        if entity.get(key):
            sparse_terms.extend(_expand_phrase(str(entity[key])))

    # Add attribute synonyms
    if attr_raw:
        attr_lower = attr_raw.lower()
        if "capacity" in attr_lower:
            sparse_terms.extend(["load", "weight", "rating"])
        if "speed" in attr_lower:
            sparse_terms.extend(["velocity", "fpm", "feet per minute"])
        if "dimension" in attr_lower or "size" in attr_lower:
            sparse_terms.extend(["width", "height", "depth", "length"])

    # Clean up and deduplicate
    seen = set()
    sparse_terms_clean = []
    for term in sparse_terms:
        term = term.strip()
        if not term or term in seen:
            continue
        # Skip very long single tokens (likely concatenations)
        if " " not in term and len(term) > 30:
            continue
        seen.add(term)
        sparse_terms_clean.append(term)

    # Limit to top 20 terms
    sparse_terms_clean = sparse_terms_clean[:20]

    # Build structured sparse query
    sparse_query = {
        "must": sparse_terms_clean[:1] if sparse_terms_clean else [],
        "should": sparse_terms_clean[1:],
        "boost": {sparse_terms_clean[0]: 2.5} if sparse_terms_clean else {},
    }

    logger.debug(f"Built query - Dense: {dense_query}, Sparse terms: {len(sparse_terms_clean)}")

    return QueryTerms(dense=dense_query, sparse=sparse_query)


def bm25_query_from_sparse(sparse: Dict[str, Any]) -> str:
    """
    Convert sparse query to BM25 query string.

    Args:
        sparse: Sparse query dict with must/should/boost

    Returns:
        BM25 query string
    """
    parts = []

    # Strip quotes from terms (BM25 doesn't use them)
    def strip_quotes(s: str) -> str:
        return s.strip('"')

    # Add must terms
    must = [strip_quotes(t) for t in sparse.get("must", [])]
    parts.extend(must)

    # Add should terms
    should = [strip_quotes(t) for t in sparse.get("should", [])]
    parts.extend(should)

    # Add boosted terms (repeat to emulate boost)
    for term, weight in (sparse.get("boost") or {}).items():
        term = strip_quotes(term)
        repeat_count = int(round(max(1.0, weight)))
        parts.extend([term] * repeat_count)

    return " ".join(parts)
