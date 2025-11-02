"""
CSI-aware hierarchical section parser.

This module parses markdown documents into hierarchical sections
following the Construction Specifications Institute (CSI) format:
- Level 1: PART X - TITLE
- Level 2: X.X TITLE
- Level 3: A. Title
- Level 4: 1. Title
- Level 5: a. Title
"""

import re
from typing import List, Optional
from pydantic import BaseModel, Field

from app.utils.logging import get_logger

logger = get_logger(__name__)


class Section(BaseModel):
    """Recursive section model for hierarchical document structure."""
    title: str = Field(..., description="Section title")
    level: int = Field(..., ge=1, le=5, description="Section level (1-5)")
    content: str = Field(default="", description="Section content (text only)")
    subsections: List['Section'] = Field(default_factory=list, description="Child sections")
    section_number: Optional[str] = Field(None, description="Section number (e.g., '1.1', 'A', '1')")
    
    class Config:
        arbitrary_types_allowed = True


# CSI Format Regex Patterns (in order of precedence)
CSI_PATTERNS = [
    (1, re.compile(r'^PART\s+([IVX\d]+)\s*[-:]\s*(.+)$', re.IGNORECASE)),
    (2, re.compile(r'^(\d+(?:\.\d+)+)\s+(.+)$')),
    (3, re.compile(r'^([A-Z])[\.)]\s+(.+)$')),
    (4, re.compile(r'^(\d+)[\.)]\s+(.+)$')),
    (5, re.compile(r'^([a-z])[\.)]\s+(.+)$')),
]


def _parse_line(line: str) -> Optional[tuple[int, str, str]]:
    """Parse a line to detect CSI section header."""
    line = line.strip()
    for level, pattern in CSI_PATTERNS:
        match = pattern.match(line)
        if match:
            return (level, match.group(1), match.group(2).strip())
    return None


def _build_hierarchy(lines: List[str]) -> List[Section]:
    """Build hierarchical section structure from lines."""
    root_sections: List[Section] = []
    section_stack: List[tuple[int, Section]] = []
    current_content: List[str] = []
    
    for line in lines:
        parsed = _parse_line(line)
        
        if parsed:
            level, section_number, title = parsed
            
            if section_stack:
                _, prev_section = section_stack[-1]
                prev_section.content = '\n'.join(current_content).strip()
                current_content = []
            elif current_content:
                current_content = []
            
            new_section = Section(
                title=title,
                level=level,
                section_number=section_number,
                content="",
                subsections=[]
            )
            
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()
            
            if section_stack:
                _, parent_section = section_stack[-1]
                parent_section.subsections.append(new_section)
            else:
                root_sections.append(new_section)
            
            section_stack.append((level, new_section))
        else:
            if line.strip():
                current_content.append(line)
    
    if section_stack and current_content:
        _, last_section = section_stack[-1]
        last_section.content = '\n'.join(current_content).strip()
    
    return root_sections


def sectionize_markdown(markdown_content: str) -> List[Section]:
    """Parse markdown content into hierarchical CSI sections."""
    if not markdown_content:
        logger.warning("Empty markdown content provided")
        return []
    
    lines = markdown_content.split('\n')
    sections = _build_hierarchy(lines)
    logger.info(f"Parsed {len(sections)} top-level sections")
    return sections


def flatten_sections(sections: List[Section]) -> List[Section]:
    """Flatten hierarchical sections into a flat list."""
    flat_list: List[Section] = []
    
    def _flatten(section: Section):
        flat_list.append(section)
        for subsection in section.subsections:
            _flatten(subsection)
    
    for section in sections:
        _flatten(section)
    
    return flat_list


def get_section_path(section: Section) -> str:
    """Get the full path of a section."""
    path_parts = []
    if section.section_number:
        path_parts.append(section.section_number)
    path_parts.append(section.title)
    return " > ".join(path_parts)


def validate_sections(sections: List[Section]) -> bool:
    """Validate section hierarchy."""
    def _validate_level(section: Section, expected_parent_level: int) -> bool:
        if section.level <= expected_parent_level:
            logger.warning(f"Invalid level {section.level} for section '{section.title}'")
            return False
        for subsection in section.subsections:
            if not _validate_level(subsection, section.level):
                return False
        return True
    
    for section in sections:
        if not _validate_level(section, 0):
            return False
    return True


def count_sections(sections: List[Section]) -> dict:
    """
    Count sections by level.

    Returns:
        Dictionary with string keys (for MongoDB compatibility).
        MongoDB requires all dictionary keys to be strings.
    """
    counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    def _count(section: Section):
        counts[section.level] += 1
        for subsection in section.subsections:
            _count(subsection)

    for section in sections:
        _count(section)

    # Convert integer keys to strings for MongoDB compatibility
    return {str(k): v for k, v in counts.items()}

