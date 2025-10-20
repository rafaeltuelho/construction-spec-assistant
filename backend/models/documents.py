"""Document models for the Construction Spec Assistant backend."""

import re
import uuid
from dataclasses import dataclass
from typing import List, Optional, Callable


@dataclass
class Section:
    """Represents a document section."""
    id: str
    level: int                      # 1 = PART, 2 = ARTICLE, 3 = sub-article (optional)
    header: str
    header_path: List[str]
    page_start: Optional[int]       # Unknown from MD; keep None unless you map later
    page_end: Optional[int]
    text: str                       # concatenated body text for this section


@dataclass
class SectionChunk:
    """Represents a chunk within a document section."""
    section_id: str
    header_path: List[str]
    chunk_index: int
    text: str                       # chunked text within the section


# CSI-aware heuristics for section detection
PART_RE = re.compile(r'^\s*PART\s+(?:[123]|I|II|III)\s*-\s+.+$', re.IGNORECASE)

# ALL-CAPS-ish line (len-limited)
ALLCAPS_RE = re.compile(r'^[A-Z0-9][A-Z0-9 \-/,()&\.]{3,}$')

# Numbered article headings like "1.1 SUMMARY", "2.3 MATERIALS"
NUM_ARTICLE_RE = re.compile(r'^\s*(?P<part>[1-3])\.(?P<art>\d+)\s+(?P<title>[A-Z][A-Z0-9 \-/,()&\.]{2,})\s*$')

# Things that look like list items, not headings: "1.", "1.1.", "a)", "-"
LIST_LIKE_RE = re.compile(r'^\s*(?:\d+(?:\.\d+)*[\.\)]|[a-zA-Z][\.\)])\s+')

CSI_ARTICLE_HINTS = {
    "SUMMARY", "REFERENCES", "SUBMITTALS", "QUALITY ASSURANCE",
    "DELIVERY, STORAGE, AND HANDLING", "SEQUENCING", "WARRANTY",
    "PERFORMANCE REQUIREMENTS", "SYSTEM DESCRIPTION", "ELEVATORS",
    "MATERIALS", "MANUFACTURERS", "PRODUCTS", "EXECUTION", "INSTALLATION",
    "FIELD QUALITY CONTROL", "CAR ENCLOSURES", "HOISTWAY ENTRANCES",
    "OPERATION", "CAR FIXTURES", "HALL FIXTURES", "DEFINITIONS"
}


def _looks_like_markdown_heading(line: str):
    """Check if a line looks like a markdown heading."""
    m = re.match(r'^(#{1,6})\s+(.+?)\s*$', line.strip())
    if m:
        return True, len(m.group(1)), m.group(2).strip()
    return False, 0, ""


def _normalize_header(text: str) -> str:
    """Normalize header text by collapsing whitespace."""
    return re.sub(r'\s+', ' ', text.strip())


def _slugify(parts: List[str]) -> str:
    """Create a URL-friendly slug from header parts."""
    s = "-".join(parts)
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s


def sectionize_markdown(md_text: str) -> List[Section]:
    """
    Build sections from Docling-exported Markdown (CSI-aware):
    - PART detection has highest priority (even if it's a Markdown heading).
    - Numbered articles 'x.y TITLE' are anchored under PART x (imputed if missing).
    - ALLCAPS/known-article headings become Article level.
    """
    lines = md_text.splitlines()
    sections: List[Section] = []
    path_stack: List[tuple[int, str]] = []  # (level, header)
    current: Optional[Section] = None

    def start_section(level: int, header: str):
        nonlocal current, path_stack, sections
        header = _normalize_header(header)
        # pop to parent
        while path_stack and path_stack[-1][0] >= level:
            path_stack.pop()
        path_stack.append((level, header))
        header_path = [h for _, h in path_stack]
        sec_id = f"sec-{_slugify(header_path)}-{uuid.uuid4().hex[:8]}"
        current = Section(
            id=sec_id, level=level, header=header,
            header_path=header_path, page_start=None, page_end=None, text=""
        )
        sections.append(current)

    def ensure_part(part_no: str):
        """Ensure top of stack is PART <part_no>; create an imputed PART if needed."""
        # If current top-level PART is already correct, nothing to do
        for lvl, hdr in reversed(path_stack):
            if lvl == 1:
                # try to detect the number in existing header
                m = re.search(r'\bPART\s+([1-3]|I|II|III)\b', hdr, re.IGNORECASE)
                if m:
                    cur = m.group(1)
                    # Normalize roman <-> arabic (simple)
                    if cur in {"I", "II", "III"}:
                        cur = {"I": "1", "II": "2", "III": "3"}[cur]
                    if cur == part_no:
                        return
                # wrong part at level 1 → pop it
                while path_stack and path_stack[-1][0] >= 1:
                    path_stack.pop()
                break
        # Create an imputed PART header if missing
        start_section(1, f"PART {part_no} - GENERAL (IMPUTED)")

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            # still attach whitespace to current text to preserve spacing a bit
            if current:
                current.text += "\n"
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
            ensure_part(m_num.group('part'))  # creates PART if missing
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
        if (t.upper() in CSI_ARTICLE_HINTS or
            (ALLCAPS_RE.match(t) and not LIST_LIKE_RE.match(t) and not t.endswith('.'))):
            level = 2 if any(l == 1 for l, _ in path_stack) else 1
            start_section(level, t)
            continue

        # 5) Content
        if current is None:
            start_section(1, "PREFACE")
        current.text += (line + "\n")

    # Trim text
    for s in sections:
        s.text = s.text.strip()
    return sections


def default_token_count(s: str) -> int:
    """Default token counting function (~4 chars/token rough heuristic)."""
    # ~4 chars/token rough heuristic
    return max(1, int(len(s) / 4))


def chunk_sections(
    sections: List[Section],
    max_tokens: int = 700,
    overlap_tokens: int = 80,
    token_counter: Optional[Callable[[str], int]] = None
) -> List[SectionChunk]:
    """
    Chunk each section's text to fit LLM limits, with overlap. 
    Splits on paragraphs/sentences when possible.
    """
    tc = token_counter or default_token_count
    chunks: List[SectionChunk] = []

    SENT_SPLIT = re.compile(r'(?<=[\.\:\;])\s+\n?|\n{2,}')  # sentence/paragraph-ish

    for s in sections:
        text = s.text or ""
        if not text.strip():
            continue

        parts = [p.strip() for p in SENT_SPLIT.split(text) if p.strip()]
        buf: List[str] = []
        buf_tokens = 0
        idx = 0

        def flush():
            nonlocal buf, buf_tokens, idx
            if not buf:
                return
            chunk_text = " ".join(buf).strip()
            chunks.append(SectionChunk(
                section_id=s.id,
                header_path=s.header_path,
                chunk_index=idx,
                text=chunk_text
            ))
            idx += 1
            # build overlap
            enc_len = tc(chunk_text)
            # crude: keep last N tokens by truncating characters proportionally
            if enc_len > overlap_tokens:
                keep_ratio = overlap_tokens / enc_len
                keep_chars = max(1, int(len(chunk_text) * keep_ratio))
                overlap_text = chunk_text[-keep_chars:]
            else:
                overlap_text = chunk_text
            buf = [overlap_text]
            buf_tokens = tc(overlap_text)

        for part in parts:
            p_tokens = tc(part)
            if buf_tokens + p_tokens > max_tokens and buf:
                flush()
            buf.append(part)
            buf_tokens += p_tokens

        if buf:
            # final flush without adding overlap
            chunk_text = " ".join(buf).strip()
            chunks.append(SectionChunk(
                section_id=s.id,
                header_path=s.header_path,
                chunk_index=idx,
                text=chunk_text
            ))

    return chunks
