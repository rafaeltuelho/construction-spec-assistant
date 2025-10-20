"""Catalog loading utilities for the Construction Spec Assistant backend."""

import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path


def load_attribute_catalog(path: str) -> Dict[str, Any]:
    """
    Load attribute catalog from YAML file.
    
    Args:
        path: Path to the YAML catalog file
        
    Returns:
        Dictionary containing the catalog data
    """
    catalog_path = Path(path)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog file not found: {path}")
    
    with open(catalog_path, "r", encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}


def validate_catalog(catalog: Dict[str, Any]) -> List[str]:
    """
    Validate catalog structure and return any validation errors.
    
    Args:
        catalog: Catalog dictionary to validate
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    if not isinstance(catalog, dict):
        errors.append("Catalog must be a dictionary")
        return errors
    
    attributes = catalog.get("attributes", {})
    if not isinstance(attributes, dict):
        errors.append("'attributes' must be a dictionary")
        return errors
    
    for attr_name, attr_spec in attributes.items():
        if not isinstance(attr_spec, dict):
            errors.append(f"Attribute '{attr_name}' must be a dictionary")
            continue
            
        # Check required fields
        if "synonyms" not in attr_spec:
            errors.append(f"Attribute '{attr_name}' missing 'synonyms' field")
        elif not isinstance(attr_spec["synonyms"], list):
            errors.append(f"Attribute '{attr_name}' 'synonyms' must be a list")
            
        # Check optional fields
        if "value_type" in attr_spec and attr_spec["value_type"] not in ["quantity", "text", "enum", "boolean", "range"]:
            errors.append(f"Attribute '{attr_name}' 'value_type' must be one of: quantity, text, enum, boolean, range")
            
        if "unit_hints" in attr_spec and not isinstance(attr_spec["unit_hints"], list):
            errors.append(f"Attribute '{attr_name}' 'unit_hints' must be a list")
    
    return errors


def get_default_catalog_path() -> Path:
    """Get the default catalog path in the backend data directory."""
    return Path(__file__).parent.parent / "data" / "spec_attributes_catalog.yaml"


def load_default_catalog() -> Dict[str, Any]:
    """Load the default attribute catalog."""
    default_path = get_default_catalog_path()
    return load_attribute_catalog(str(default_path))
