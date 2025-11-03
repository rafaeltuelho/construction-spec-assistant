"""
Unit normalization using pint library.

This module provides utilities for normalizing units in fact values,
converting them to standard/preferred units for comparison.

Reference: notebooks/document_processing_new_pipeline.ipynb (lines 1039-1084)
"""

import re
import logging
from typing import Tuple, Optional
from pint import UnitRegistry

from app.models.fact import Fact
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize unit registry
ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)

# Construction-specific unit aliases
ureg.define("fpm = foot / minute")
ureg.define("inches = inch")

# Preferred units for construction specs
PREFERRED_UNITS = {
    "fpm": "fpm",  # keep native for elevator speeds
    "inch": "in",
    "inches": "in",
    "mm": "mm",
    "lb": "lb",
    "kg": "kg",
    "psi": "psi",
    "ft": "ft",
    "feet": "ft",
    "m": "m",
    "meter": "m",
    # Add more as needed
}


def normalize_unit(value: float, unit_str: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Normalize value and unit to standard units.

    Args:
        value: Numeric value
        unit_str: Unit as string

    Returns:
        Tuple of (normalized_value, normalized_unit)

    Examples:
        normalize_unit(2500, "pounds") -> (2500.0, "lb")
        normalize_unit(12, "inches") -> (12.0, "in")
    """
    try:
        # Normalize unit string
        unit_normalized = unit_str.strip().lower()
        unit_normalized = {
            "inches": "in",
            "inch": "in",
            "fpm": "fpm",
            "pounds": "lb",
            "pound": "lb",
            "feet": "ft",
            "foot": "ft",
        }.get(unit_normalized, unit_normalized)

        # Create quantity
        quantity = value * ureg(unit_normalized)

        # Choose target unit
        target = PREFERRED_UNITS.get(unit_normalized, unit_normalized)

        # Convert to target unit
        converted = quantity.to(target)

        return (float(converted.magnitude), target)

    except Exception as e:
        logger.warning(f"Failed to normalize unit: {value} {unit_str}: {e}")
        return (None, None)


def parse_value_with_unit(raw_value: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Parse raw value string to extract numeric value and unit.

    Args:
        raw_value: Raw value string (e.g., "2500 lbs", "4000 PSI")

    Returns:
        Tuple of (numeric_value, unit)

    Examples:
        parse_value_with_unit("2500 lbs") -> (2500.0, "lbs")
        parse_value_with_unit("4000 PSI") -> (4000.0, "PSI")
        parse_value_with_unit("42 inches") -> (42.0, "inches")
    """
    # Regex to extract number and unit
    pattern = r"([\d,]+\.?\d*)\s*([a-zA-Z]+)"
    match = re.search(pattern, raw_value)

    if match:
        value_str = match.group(1).replace(",", "")
        unit_str = match.group(2)

        try:
            value = float(value_str)
            return (value, unit_str)
        except ValueError:
            return (None, None)

    return (None, None)


def normalize_fact_value(fact: Fact) -> Fact:
    """
    Normalize units in a fact's value.

    This function updates the fact's value with normalized units
    if the value type is 'quantity' and has a numeric value with unit.

    Args:
        fact: Fact object to normalize

    Returns:
        Fact with normalized value (modified in place)

    Examples:
        Input: Fact with value.raw="2500 pounds", value.type="quantity"
        Output: Fact with value.num=2500.0, value.unit="lb"
    """
    # Only normalize quantity values
    if fact.value.type != "quantity":
        return fact

    # If num and unit already set, normalize them
    if fact.value.num is not None and fact.value.unit:
        normalized_value, normalized_unit = normalize_unit(fact.value.num, fact.value.unit)

        if normalized_value is not None and normalized_unit is not None:
            fact.value.num = normalized_value
            fact.value.unit = normalized_unit
            logger.debug(f"Normalized {fact.value.raw} to {normalized_value} {normalized_unit}")

        return fact

    # Otherwise, try to parse from raw value
    numeric, unit = parse_value_with_unit(fact.value.raw)

    if numeric and unit:
        # Normalize unit
        normalized_value, normalized_unit = normalize_unit(numeric, unit)

        if normalized_value and normalized_unit:
            fact.value.num = normalized_value
            fact.value.unit = normalized_unit
            logger.debug(
                f"Parsed and normalized {fact.value.raw} to {normalized_value} {normalized_unit}"
            )

    return fact


def normalize_facts(facts: list[Fact]) -> list[Fact]:
    """
    Normalize units in a list of facts.

    Args:
        facts: List of facts to normalize

    Returns:
        List of facts with normalized values
    """
    normalized = []

    for fact in facts:
        try:
            normalized_fact = normalize_fact_value(fact)
            normalized.append(normalized_fact)
        except Exception as e:
            logger.error(f"Error normalizing fact {fact.id}: {e}")
            # Keep original fact if normalization fails
            normalized.append(fact)

    logger.info(f"Normalized {len(normalized)} facts")
    return normalized
