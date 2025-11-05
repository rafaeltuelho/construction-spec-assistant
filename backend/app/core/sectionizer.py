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
import uuid
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

from app.utils.logging import get_logger

logger = get_logger(__name__)


class Section(BaseModel):
    """Recursive section model for hierarchical document structure."""

    title: str = Field(..., description="Section title")
    level: int = Field(..., ge=1, le=5, description="Section level (1-5)")
    content: str = Field(default="", description="Section content (text only)")
    subsections: List["Section"] = Field(default_factory=list, description="Child sections")
    section_number: Optional[str] = Field(
        None, description="Section number (e.g., '1.1', 'A', '1')"
    )
    # New fields for notebook compatibility
    section_id: Optional[str] = Field(None, description="Unique section identifier (UUID-based)")
    header_path: List[str] = Field(
        default_factory=list, description="Full hierarchical path from root to this section"
    )
    page_start: Optional[int] = Field(
        None, description="Starting page number (0-indexed, from Docling provenance)"
    )
    page_end: Optional[int] = Field(
        None, description="Ending page number (0-indexed, from Docling provenance)"
    )

    class Config:
        arbitrary_types_allowed = True


# CSI Format Regex Patterns (in order of precedence)
CSI_PATTERNS = [
    (1, re.compile(r"^PART\s+([IVX\d]+)\s*[-:]\s*(.+)$", re.IGNORECASE)),
    (2, re.compile(r"^(\d+(?:\.\d+)+)\s+(.+)$")),
    (3, re.compile(r"^([A-Z])[\.)]\s+(.+)$")),
    (4, re.compile(r"^(\d+)[\.)]\s+(.+)$")),
    (5, re.compile(r"^([a-z])[\.)]\s+(.+)$")),
]

# Notebook-style CSI-aware heuristics
PART_RE = re.compile(r"^\s*PART\s+(?:[123]|I|II|III)\s*-\s+.+$", re.IGNORECASE)
ALLCAPS_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-/,()&\.]{3,}$")
NUM_ARTICLE_RE = re.compile(
    r"^\s*(?P<part>[1-3])\.(?P<art>\d+)\s+(?P<title>[A-Z][A-Z0-9 \-/,()&\.]{2,})\s*$"
)
LIST_LIKE_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*[\.\)]|[a-zA-Z][\.\)])\s+")

CSI_ARTICLE_HINTS = {
    "SUMMARY",
    "REFERENCES",
    "SUBMITTALS",
    "QUALITY ASSURANCE",
    "DELIVERY, STORAGE, AND HANDLING",
    "SEQUENCING",
    "WARRANTY",
    "PERFORMANCE REQUIREMENTS",
    "SYSTEM DESCRIPTION",
    "ELEVATORS",
    "MATERIALS",
    "MANUFACTURERS",
    "PRODUCTS",
    "EXECUTION",
    "INSTALLATION",
    "FIELD QUALITY CONTROL",
    "CAR ENCLOSURES",
    "HOISTWAY ENTRANCES",
    "OPERATION",
    "CAR FIXTURES",
    "HALL FIXTURES",
    "DEFINITIONS",
}


def _slugify(parts: List[str]) -> str:
    """
    Convert header path parts to a URL-friendly slug.

    Example: ["PART 1 - GENERAL", "1.1 SUMMARY"] -> "part-1-general-1-1-summary"
    """
    s = "-".join(parts)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _generate_section_id(header_path: List[str]) -> str:
    """
    Generate unique section ID from header path.

    Format: sec-{slugified-path}-{uuid8}
    Example: sec-part-1-general-1-1-summary-a3f4b2c1
    """
    slug = _slugify(header_path)
    short_uuid = uuid.uuid4().hex[:8]
    return f"sec-{slug}-{short_uuid}"


def _build_header_path(section_stack: List[tuple[int, str]]) -> List[str]:
    """
    Build header path from section stack.

    Args:
        section_stack: Stack of (level, header) tuples

    Returns:
        List of header strings from root to current section
    """
    return [header for _, header in section_stack]


def _normalize_header(text: str) -> str:
    """Normalize header text by collapsing whitespace."""
    return re.sub(r"\s+", " ", text.strip())


def _looks_like_markdown_heading(line: str) -> tuple[bool, int, str]:
    """
    Check if line is a markdown heading.

    Returns:
        (is_heading, level, header_text)
    """
    m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
    if m:
        return True, len(m.group(1)), m.group(2).strip()
    return False, 0, ""


# Patterns to ignore (document artifacts, headers, footers, etc.)
IGNORE_HEADER_PATTERNS = [
    re.compile(r"^\d{4}$"),  # Pure numbers like "2345" (page numbers)
    re.compile(r"^SECTION\s+\d{2}\s+\d{2}\s+\d{2}$", re.IGNORECASE),  # "SECTION 14 24 00"
    re.compile(r"^Construction Documents$", re.IGNORECASE),  # Header/footer text
    re.compile(r"^END OF SECTION$", re.IGNORECASE),  # End marker
]


def _should_ignore_header(header: str) -> bool:
    """
    Check if header should be ignored (document artifacts, etc.).

    Args:
        header: Header text to check

    Returns:
        True if header should be ignored, False otherwise
    """
    header = header.strip()
    for pattern in IGNORE_HEADER_PATTERNS:
        if pattern.match(header):
            return True
    return False


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
    header_stack: List[tuple[int, str]] = []  # Track headers for path building
    current_content: List[str] = []

    for line in lines:
        parsed = _parse_line(line)

        if parsed:
            level, section_number, title = parsed

            if section_stack:
                _, prev_section = section_stack[-1]
                prev_section.content = "\n".join(current_content).strip()
                current_content = []
            elif current_content:
                current_content = []

            # Update header stack for path tracking
            while header_stack and header_stack[-1][0] >= level:
                header_stack.pop()
            header_stack.append((level, title))

            # Build header path and generate section ID
            header_path = _build_header_path(header_stack)
            section_id = _generate_section_id(header_path)

            new_section = Section(
                title=title,
                level=level,
                section_number=section_number,
                content="",
                subsections=[],
                section_id=section_id,
                header_path=header_path,
                page_start=None,  # Will be populated if page info available
                page_end=None,
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
        last_section.content = "\n".join(current_content).strip()

    return root_sections


def _sectionize_notebook_style(md_text: str) -> List[Section]:
    """
    Build sections from markdown using notebook's CSI-aware logic.

    This implementation matches the notebook's sectionization algorithm:
    - PART detection has highest priority (even if it's a Markdown heading)
    - Numbered articles 'x.y TITLE' are anchored under PART x (imputed if missing)
    - ALLCAPS/known-article headings become Article level
    - Returns flat list of sections (not hierarchical tree)

    Returns:
        Flat list of Section objects with populated header_path
    """
    lines = md_text.splitlines()
    sections: List[Section] = []
    path_stack: List[tuple[int, str]] = []  # (level, header)
    current: Optional[Section] = None

    def start_section(level: int, header: str):
        """Start a new section and add it to the flat list."""
        nonlocal current, path_stack, sections
        header = _normalize_header(header)

        # Filter out document artifacts (page numbers, headers, footers, etc.)
        if _should_ignore_header(header):
            logger.debug(f"Ignoring header artifact: {header}")
            return

        # Pop to parent level
        while path_stack and path_stack[-1][0] >= level:
            path_stack.pop()
        path_stack.append((level, header))

        # Build header path and generate ID
        header_path = [h for _, h in path_stack]
        sec_id = _generate_section_id(header_path)

        # Create new section
        current = Section(
            title=header,
            level=level,
            content="",
            subsections=[],  # Flat structure, no subsections
            section_number=None,  # Will be populated if needed
            section_id=sec_id,
            header_path=header_path,
            page_start=None,
            page_end=None,
        )
        sections.append(current)

    def ensure_part(part_no: str):
        """Ensure top of stack is PART <part_no>; create an imputed PART if needed."""
        # Check if current top-level PART is already correct
        for lvl, hdr in reversed(path_stack):
            if lvl == 1:
                # Try to detect the number in existing header
                m = re.search(r"\bPART\s+([1-3]|I|II|III)\b", hdr, re.IGNORECASE)
                if m:
                    cur = m.group(1)
                    # Normalize roman <-> arabic (simple)
                    if cur in {"I", "II", "III"}:
                        cur = {"I": "1", "II": "2", "III": "3"}[cur]
                    if cur == part_no:
                        return
                # Wrong part at level 1 → pop it
                while path_stack and path_stack[-1][0] >= 1:
                    path_stack.pop()
                break
        # Create an imputed PART header if missing
        start_section(1, f"PART {part_no} - GENERAL (IMPUTED)")

    # Parse lines
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            # Preserve whitespace in current section
            if current:
                current.content += "\n"
            continue

        # Check if this is a Markdown heading
        is_md, md_level, md_header = _looks_like_markdown_heading(line)

        # 1) PART has highest priority (even if it's a MD heading)
        if (is_md and PART_RE.match(md_header)) or PART_RE.match(line):
            start_section(1, md_header if is_md else line)
            continue

        # 2) Numbered article like "1.1 SUMMARY" → anchor to PART 1
        m_num = NUM_ARTICLE_RE.match(line.upper())
        if m_num and not LIST_LIKE_RE.match(line):
            ensure_part(m_num.group("part"))  # creates PART if missing
            start_section(2, f"{m_num.group('part')}.{m_num.group('art')} {m_num.group('title')}")
            continue

        # 3) Other Markdown headings (non-PART) → treat as Article/Sub-article
        if is_md:
            # If we have a PART already, make this level 2; else level 1
            level = 2 if any(l == 1 for l, _ in path_stack) else 1
            start_section(level, md_header)
            continue

        # 4) ALLCAPS/known-article headings → Article
        t = line.strip()
        if t.upper() in CSI_ARTICLE_HINTS or (
            ALLCAPS_RE.match(t) and not LIST_LIKE_RE.match(t) and not t.endswith(".")
        ):
            level = 2 if any(l == 1 for l, _ in path_stack) else 1
            start_section(level, t)
            continue

        # 5) Content
        if current is None:
            start_section(1, "PREFACE")
        current.content += line + "\n"

    # Trim text
    for s in sections:
        s.content = s.content.strip()

    logger.info(f"Parsed {len(sections)} sections (notebook-style flat structure)")
    return sections


def _get_page_number_for_content(
    content: str, markdown_content: str, page_mapping: Optional[Dict[int, List[int]]]
) -> Optional[int]:
    """
    Determine the page number for a section based on its content position in the markdown.

    Args:
        content: Section content to find
        markdown_content: Full markdown content
        page_mapping: Page number mapping from Docling (char_position -> [page_no, ...])

    Returns:
        Page number (0-indexed) or None if not found
    """
    if not page_mapping or not content:
        return None

    try:
        # Find the position of the content in the markdown
        content_start = markdown_content.find(content[:100])  # Use first 100 chars to find position
        if content_start == -1:
            return None

        # Find the closest character position in the mapping
        closest_pos = None
        min_distance = float("inf")

        for pos in page_mapping.keys():
            distance = abs(pos - content_start)
            if distance < min_distance:
                min_distance = distance
                closest_pos = pos

        if closest_pos is not None and page_mapping[closest_pos]:
            return page_mapping[closest_pos][0]  # Return first page number

    except Exception as e:
        logger.debug(f"Failed to determine page number for content: {str(e)}")

    return None


def _assign_page_numbers_to_sections(
    sections: List[Section], markdown_content: str, page_mapping: Dict[int, List[int]]
) -> None:
    """
    Recursively assign page numbers to sections based on their content position.

    Args:
        sections: List of sections to process
        markdown_content: Full markdown content
        page_mapping: Page number mapping from Docling
    """
    for section in sections:
        # Determine page number for this section
        page_no = _get_page_number_for_content(section.content, markdown_content, page_mapping)
        if page_no is not None:
            section.page_start = page_no
            section.page_end = page_no  # For now, assume single page (can be refined later)

        # Recursively process subsections
        if section.subsections:
            _assign_page_numbers_to_sections(section.subsections, markdown_content, page_mapping)


def sectionize_markdown(
    markdown_content: str,
    use_notebook_logic: bool = False,
    page_mapping: Optional[Dict[int, List[int]]] = None,
) -> List[Section]:
    """
    Parse markdown content into hierarchical CSI sections.

    Args:
        markdown_content: Markdown text to parse
        use_notebook_logic: If True, use notebook-style flat section parsing with CSI-aware heuristics.
                           If False (default), use hierarchical tree-based parsing.
        page_mapping: Optional page number mapping from Docling (char_position -> [page_no, ...])
                     Used to determine page numbers for sections

    Returns:
        List of Section objects (hierarchical if use_notebook_logic=False, flat if True)
    """
    if not markdown_content:
        logger.warning("Empty markdown content provided")
        return []

    if use_notebook_logic:
        sections = _sectionize_notebook_style(markdown_content)
    else:
        lines = markdown_content.split("\n")
        sections = _build_hierarchy(lines)
        logger.info(f"Parsed {len(sections)} top-level sections")

    # Assign page numbers to sections if page mapping is available
    if page_mapping:
        _assign_page_numbers_to_sections(sections, markdown_content, page_mapping)

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
