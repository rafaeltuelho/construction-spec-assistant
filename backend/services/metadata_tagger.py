"""Metadata tagging service for document chunks."""

import re
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..utils.catalog_loader import load_attribute_catalog


# Generic detectors (no product bias)
ORG_SUFFIX = r"(?:inc\.?|llc|l\.?l\.?c\.?|corp\.?|corporation|co\.|company|ltd\.?|gmbh|s\.?a\.?)"
RE_MANUF_LINE = re.compile(r"\b(manufacturer|by|supplier)\s*[:\-]\s*(.+)$", re.I | re.M)
RE_ORG = re.compile(r"\b([A-Z][A-Za-z0-9&\.\- ]+)\s+" + ORG_SUFFIX + r"\b", re.I)
RE_MODEL = re.compile(r"\b(model|series|type|product\s*code|catalog\s*no\.?|cat\.\s*no\.?|part\s*no\.?|sku)\s*[:\-#]\s*([A-Za-z0-9\-\._/]+)", re.I)
RE_STANDARDS = re.compile(r"\b(ISO|IEC|ASME|ASTM|ANSI|NFPA|UL|CSA|EN|NEMA|IEEE)\s*[-: ]?\s*([A-Z0-9\.\-]+)", re.I)
RE_CSI_SECTION = re.compile(r"\bSECTION\s+(\d{2}\s*\d{2}\s*\d{2})\b|\bDIVISION\s+(\d{2})\b", re.I)

# numbers + units (very broad)
UNIT = r"(?:mm|cm|m|in|inch|inches|ft|feet|yd|kg|lb|lbs|g|N|kN|Pa|kPa|MPa|psi|bar|C|F|V|VAC|VDC|A|amp[s]?|Hz|kW|W|hp|rpm|rps|fpm|m/s|gpm|l/s|L/s|cfm|scfm|°[CF])"
RE_NUMUNIT = re.compile(r"(-?\d{1,3}(?:[\d,]{0,3})?(?:\.\d+)?)\s*(" + UNIT + r")\b", re.I)

# section/title heuristics for tiering (generic)
TIER_MAP = [
    (re.compile(r"\b(shop\s*drawing|submittal|product\s*data|data\s*sheet|cut\s*sheet)\b", re.I), "submittal"),
    (re.compile(r"\b(specification[s]?|technical\s*data|specs|layout|power\s*data|wiring\s*diagram)\b", re.I), "technical"),
    (re.compile(r"\b(brochure|marketing|sales)\b", re.I), "brochure"),
]


class MetadataTagger:
    """Service for tagging document chunks with metadata."""
    
    def __init__(self, catalog_path: Optional[str] = None):
        """
        Initialize the metadata tagger.
        
        Args:
            catalog_path: Path to the attribute catalog YAML file
        """
        self.catalog_path = catalog_path
        self.catalog = None
        self.attr_patterns = None
        
        if catalog_path:
            self.load_catalog()
    
    def load_catalog(self, catalog_path: Optional[str] = None):
        """Load the attribute catalog."""
        if catalog_path:
            self.catalog_path = catalog_path
        
        if self.catalog_path:
            try:
                self.catalog = load_attribute_catalog(self.catalog_path)
                self.attr_patterns = self.compile_attr_patterns(self.catalog)
            except Exception as e:
                print(f"Warning: Failed to load catalog: {e}")
                self.catalog = {}
                self.attr_patterns = {}
    
    def compile_attr_patterns(self, catalog: Dict[str, Any]) -> Dict[str, List[re.Pattern]]:
        """Compile regex patterns from catalog."""
        pats = {}
        for canon, spec in (catalog.get("attributes") or {}).items():
            pats[canon] = []
            for syn in spec.get("synonyms", []):
                if isinstance(syn, dict) and "regex" in syn:
                    pats[canon].append(re.compile(syn["regex"], re.I))
                else:
                    # escape and allow whitespace variants
                    patt = re.compile(r"\b" + re.sub(r"\s+", r"\\s+", re.escape(syn)) + r"\b", re.I)
                    pats[canon].append(patt)
        return pats
    
    def detect_source_tier(self, text: str) -> str:
        """Detect source tier based on text content."""
        head = text[:400]
        for rx, tier in TIER_MAP:
            if rx.search(head):
                return tier
        return "unknown"
    
    def dedupe_keep_order(self, seq: List[str]) -> List[str]:
        """Remove duplicates while keeping order."""
        seen, out = set(), []
        for x in seq:
            if x and x not in seen:
                seen.add(x)
                out.append(x)
        return out
    
    def tag_payload_generic(self, text: str, attr_patterns: Optional[Dict[str, List[re.Pattern]]] = None) -> Dict[str, Any]:
        """
        Domain-agnostic metadata to store in Qdrant payload.
        
        Args:
            text: Text content to tag
            attr_patterns: Compiled attribute patterns
            
        Returns:
            Dictionary containing metadata tags
        """
        if attr_patterns is None:
            attr_patterns = self.attr_patterns or {}
        
        md = {}

        # attributes present (catalog-driven)
        attrs = []
        for canon, pats in attr_patterns.items():
            if any(p.search(text) for p in pats):
                attrs.append(canon)
        md["attributes_present"] = attrs

        # manufacturer candidates
        mans = []
        for m in RE_MANUF_LINE.finditer(text):
            mans.append(m.group(2).strip())
        for m in RE_ORG.finditer(text):
            mans.append(m.group(0).strip())
        md["manufacturer_candidates"] = self.dedupe_keep_order(mans)

        # model / series / codes
        models = [m.group(2).strip() for m in RE_MODEL.finditer(text)]
        md["model_tokens"] = self.dedupe_keep_order(models)

        # standards
        stds = [f"{m.group(1).upper()} {m.group(2).upper()}" for m in RE_STANDARDS.finditer(text)]
        md["standards"] = self.dedupe_keep_order(stds)

        # numbers + units
        nums = [f"{m.group(1)} {m.group(2)}" for m in RE_NUMUNIT.finditer(text)]
        md["numbers_units"] = self.dedupe_keep_order(nums)
        md["unit_set"] = self.dedupe_keep_order([u.split()[-1].lower() for u in nums])

        # CSI hints
        sec = RE_CSI_SECTION.search(text)
        md["csi_section"] = (sec.group(1) or sec.group(2)) if sec else None

        # tier
        md["source_tier"] = self.detect_source_tier(text)

        return md
