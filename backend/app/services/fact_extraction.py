"""
Fact extraction service.

This module orchestrates the fact extraction pipeline:
1. Extract facts from document chunks using LLM
2. Validate facts with Pydantic models
3. Normalize units
4. Deduplicate facts
5. Store in MongoDB

Reference: notebooks/document_processing_new_pipeline.ipynb (lines 979-1136)
"""

import json
import uuid
import re
import asyncio
from typing import List, Dict, Any, Optional, Union
from collections import defaultdict

from langchain_openai import ChatOpenAI
from langchain_together import ChatTogether
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from app.models.document import DocumentChunk
from app.models.fact import Fact, Entity, Attribute, Value, Context, ValueType
from app.agents.prompts import FACT_EXTRACTOR_SYSTEM_PROMPT, EXTRACTOR_PROMPT_TEMPLATE
from app.core.unit_normalizer import normalize_fact_value
from app.utils.logging import get_logger
from app.utils.exceptions import FactExtractionError

logger = get_logger(__name__)


def parse_jsonl(text: str) -> List[Dict[str, Any]]:
    """
    Parse NDJSON (JSON Lines) format.

    Ignores blank lines and tolerates trailing code fences.

    Args:
        text: NDJSON text

    Returns:
        List of parsed JSON objects
    """
    cleaned = text.strip()

    # Strip code fences if the model added them
    cleaned = re.sub(r"^```(?:jsonl|json)?\s*|```$", "", cleaned, flags=re.MULTILINE).strip()

    items = []
    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            # Best-effort repair: try to fix single quotes
            line2 = line.replace("'", '"')
            try:
                items.append(json.loads(line2))
            except Exception:
                logger.warning(f"Failed to parse JSONL line: {line[:100]}...")
                continue

    return items


def self_verify_against_span(facts: List[Fact], chunk_text: str) -> List[Fact]:
    """
    Quick self-verification (cheap guardrail).

    Verifies that:
    1. source_span exists in chunk_text
    2. value.raw appears in source_span

    Lowers confidence if verification fails.

    Args:
        facts: List of facts to verify
        chunk_text: Original chunk text

    Returns:
        List of verified facts
    """
    verified = []

    for fact in facts:
        span = fact.context.source_span
        value_raw = fact.value.raw

        span_ok = span and (span in chunk_text)
        value_ok = (value_raw.lower() in span.lower()) if value_raw else True

        if span_ok and value_ok:
            verified.append(fact)
        else:
            # Keep but lower confidence
            fact.context.confidence = min(0.6, fact.context.confidence)
            verified.append(fact)
            logger.debug(f"Lowered confidence for fact {fact.id} due to verification failure")

    return verified


async def extract_facts_from_chunk(
    chunk: DocumentChunk,
    document_id: str,
    llm_client: Union[ChatOpenAI, ChatTogether],
    entity_hint: Optional[str] = None,
    temperature: float = 0.0,
) -> List[Fact]:
    """
    Extract facts from a single document chunk using LLM.

    Args:
        chunk: Document chunk to process
        document_id: Source document identifier
        llm_client: OpenAI LLM client
        entity_hint: Optional hint for entity type
        temperature: LLM temperature (default: 0.0 for deterministic)

    Returns:
        List of extracted Fact objects
    """
    try:
        # Prepare system prompt
        system_prompt = FACT_EXTRACTOR_SYSTEM_PROMPT
        if entity_hint:
            system_prompt += (
                f"\nEntity hint: The entity.type in this section is likely '{entity_hint}'."
            )

        # Prepare user prompt
        header_path_str = (
            " > ".join(chunk.section_title.split(" > "))
            if chunk.section_title
            else chunk.section_id
        )
        user_prompt = EXTRACTOR_PROMPT_TEMPLATE.format(
            doc_id=document_id,
            section_id=chunk.section_id,
            header_path=header_path_str,
            chunk_text=chunk.content,
        )

        # Call LLM with LangSmith metadata
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

        # Add LangSmith metadata for tracing
        config = RunnableConfig(
            tags=[
                "fact-extraction",
                f"doc:{document_id}",
                f"chunk:{chunk.chunk_id}",
                f"section:{chunk.section_id}",
            ],
            metadata={
                "operation": "fact_extraction",
                "document_id": document_id,
                "chunk_id": chunk.chunk_id,
                "section_id": chunk.section_id,
                "section_title": chunk.section_title,
                "entity_hint": entity_hint,
                "temperature": temperature,
                "chunk_length": len(chunk.content),
            },
        )

        response = await llm_client.ainvoke(messages, config=config)
        logger.debug(f"LLM response for chunk {chunk.chunk_id}: {response.content[:200]}...")

        # Parse JSONL response
        items = parse_jsonl(response.content)

        # Convert to Fact objects
        facts: List[Fact] = []
        for item in items:
            # Always generate a UUID for the fact ID (ignore LLM-provided IDs)
            item["id"] = str(uuid.uuid4())
            item.setdefault("context", {})
            item["context"].setdefault("doc_id", document_id)
            item["context"].setdefault("section_id", chunk.section_id)

            # Fix: Convert string header_path back to list if needed
            llm_header_path = item["context"].get("header_path", header_path_str)
            if isinstance(llm_header_path, str):
                # Split the string back into a list
                item["context"]["header_path"] = llm_header_path.split(" > ")
            else:
                # Use the original header_path from chunk if LLM didn't provide one
                item["context"]["header_path"] = [header_path_str]

            if "confidence" not in item["context"]:
                item["context"]["confidence"] = 0.9

            # Basic resilience: ensure sub-objects exist
            item.setdefault("entity", {})
            item.setdefault("attribute", {"raw": ""})
            item.setdefault("value", {"raw": "", "type": "text"})

            try:
                fact = Fact(**item)
                facts.append(fact)
            except ValidationError as ve:
                logger.error(f"Validation error for fact: {ve}")
                continue

        # Verify each fact against span before returning
        facts = self_verify_against_span(facts, chunk.content)

        logger.info(f"Extracted {len(facts)} facts from chunk {chunk.chunk_id}")
        return facts

    except Exception as e:
        logger.error(f"Error extracting facts from chunk {chunk.chunk_id}: {e}")
        return []


def fact_signature(fact: Fact) -> str:
    """
    Generate signature for deduplication.

    Used for dedupe: same entity + attribute + value.raw within the same section.

    Args:
        fact: Fact to generate signature for

    Returns:
        Signature string
    """
    entity_parts = (fact.entity.type or "", fact.entity.name or "", fact.entity.manufacturer or "")
    attr = fact.attribute.canonical or fact.attribute.raw
    return "|".join([*entity_parts, attr, fact.value.raw, fact.context.section_id])


def dedupe_facts(facts: List[Fact]) -> List[Fact]:
    """
    Deduplicate facts based on entity-attribute-value similarity.

    Strategy:
    1. Group facts by signature (entity + attribute + value + section)
    2. Keep first occurrence of each signature

    Args:
        facts: List of facts to deduplicate

    Returns:
        Deduplicated list of facts
    """
    seen = set()
    deduplicated = []

    for fact in facts:
        sig = fact_signature(fact)
        if sig in seen:
            continue
        seen.add(sig)
        deduplicated.append(fact)

    logger.info(f"Deduplicated {len(facts)} facts to {len(deduplicated)} unique facts")
    return deduplicated


def extract_manufacturer_mappings(
    facts: List[Fact],
    document_chunks: List[DocumentChunk],
) -> Dict[str, List[str]]:
    """
    Extract manufacturer mappings from PART 2 - PRODUCTS sections using pattern matching.

    This function identifies manufacturer information from specification documents
    by analyzing facts from manufacturer listing sections (typically PART 2 - PRODUCTS).
    It uses the header_path from facts' context to identify manufacturer sections,
    then extracts manufacturer names using regex patterns.

    Strategy:
    1. Identify facts from manufacturer listing sections (sections with "MANUFACTURERS" in header path)
    2. Build section_id -> content mapping from chunks
    3. Extract manufacturer names from section content using regex patterns
    4. Build a dictionary mapping entity_type -> [manufacturer1, manufacturer2, ...]

    Args:
        facts: All extracted facts from document (contains header_path in context)
        document_chunks: All document chunks (used to get content for manufacturer sections)

    Returns:
        Dictionary mapping entity_type -> [manufacturer1, manufacturer2, ...]
        Example: {"elevator": ["ThyssenKrupp Elevator", "Otis", "KONE"], "door": ["Stanley"]}

    Example:
        >>> facts = [...]
        >>> chunks = [...]
        >>> mappings = extract_manufacturer_mappings(facts, chunks)
        >>> mappings
        {"elevator": ["ThyssenKrupp Elevator", "Otis", "KONE"]}
    """
    manufacturer_mappings = defaultdict(list)

    # Build a mapping of section_id -> chunk content for quick lookup
    section_content_map = {}
    for chunk in document_chunks:
        if chunk.section_id not in section_content_map:
            section_content_map[chunk.section_id] = []
        section_content_map[chunk.section_id].append(chunk.content)

    # Find facts from manufacturer listing sections
    # Use facts' context.header_path since DocumentChunk doesn't have header_path
    manufacturer_sections = set()

    # DEBUG: Log sample header paths to understand the data structure
    logger.info(f"Analyzing {len(facts)} facts for manufacturer sections...")
    sample_header_paths = set()
    for i, fact in enumerate(facts[:10]):  # Sample first 10 facts
        header_path = " > ".join(fact.context.header_path)
        sample_header_paths.add(header_path)

    if sample_header_paths:
        logger.info(f"Sample header paths from facts (first 10 unique):")
        for hp in list(sample_header_paths)[:10]:
            logger.info(f"  - {hp}")

    # Search for manufacturer sections
    for fact in facts:
        header_path = " > ".join(fact.context.header_path)

        # Look for manufacturer sections
        # Note: Facts may not have full hierarchical path (e.g., "2.1 HYDRAULIC ELEVATOR MANUFACTURERS")
        # So we search for sections that contain "MANUFACTURERS" and start with "2." (PART 2 sections)
        header_path_upper = header_path.upper()

        # Check if this is a manufacturer section:
        # 1. Contains "MANUFACTURERS" (plural or singular)
        # 2. Either contains "PART 2" OR starts with "2." (section number pattern)
        is_manufacturer_section = "MANUFACTURER" in header_path_upper and (
            "PART 2" in header_path_upper
            or any(part.strip().startswith("2.") for part in fact.context.header_path)
        )

        if is_manufacturer_section:
            manufacturer_sections.add((fact.context.section_id, tuple(fact.context.header_path)))
            logger.info(f"✓ Found manufacturer section: {header_path}")

    if not manufacturer_sections:
        logger.warning("No manufacturer sections found in document")
        logger.warning(
            f"Searched {len(facts)} facts for sections containing 'PART 2' AND 'MANUFACTURERS'"
        )
        return dict(manufacturer_mappings)

    # Extract manufacturer names from sections
    for section_id, header_path_tuple in manufacturer_sections:
        header_path = list(header_path_tuple)

        # Infer entity type from section header
        # Example: "2.1 HYDRAULIC ELEVATOR MANUFACTURERS" -> "elevator"
        entity_type = _infer_entity_type_from_header(header_path)

        # Get content for this section
        section_content = " ".join(section_content_map.get(section_id, []))

        if not section_content:
            logger.debug(f"No content found for section {section_id}")
            continue

        # Extract manufacturer names from section text
        manufacturers = _extract_manufacturers_from_text(section_content)

        if entity_type and manufacturers:
            for manufacturer in manufacturers:
                if manufacturer not in manufacturer_mappings[entity_type]:
                    manufacturer_mappings[entity_type].append(manufacturer)
                    logger.info(f"Found manufacturer mapping: {entity_type} -> {manufacturer}")

    logger.info(
        f"Extracted {len(manufacturer_mappings)} entity type mappings with "
        f"{sum(len(v) for v in manufacturer_mappings.values())} total manufacturers"
    )

    return dict(manufacturer_mappings)


def _infer_entity_type_from_header(header_path: List[str]) -> Optional[str]:
    """
    Infer entity type from section header path.

    Examples:
        ["PART 2 - PRODUCTS", "2.1 HYDRAULIC ELEVATOR MANUFACTURERS"] -> "elevator"
        ["PART 2 - PRODUCTS", "2.1 DOOR MANUFACTURERS"] -> "door"
        ["PART 2 - PRODUCTS", "2.1 MANUFACTURERS"] -> None (ambiguous)

    Args:
        header_path: Section header path (e.g., ["PART 2 - PRODUCTS", "2.1 HYDRAULIC ELEVATOR MANUFACTURERS"])

    Returns:
        Entity type (e.g., "elevator") or None if cannot be inferred
    """
    # Get the last header (most specific)
    if not header_path:
        return None

    last_header = header_path[-1].upper()

    # Remove section numbers (e.g., "2.1 ")
    last_header = re.sub(r"^\d+(\.\d+)*\s+", "", last_header)

    # Remove "MANUFACTURERS" suffix
    last_header = last_header.replace("MANUFACTURERS", "").strip()

    # If nothing left, cannot infer
    if not last_header:
        return None

    # Extract entity type (e.g., "HYDRAULIC ELEVATOR" -> "elevator")
    # Common patterns:
    # - "HYDRAULIC ELEVATOR" -> "elevator"
    # - "ELEVATOR" -> "elevator"
    # - "DOOR" -> "door"
    # - "WINDOW" -> "window"

    # Simple heuristic: take the last word and lowercase it
    words = last_header.split()
    if words:
        entity_type = words[-1].lower()
        logger.debug(f"Inferred entity type '{entity_type}' from header: {' > '.join(header_path)}")
        return entity_type

    return None


def _extract_manufacturers_from_text(text: str) -> List[str]:
    """
    Extract manufacturer names from text using pattern matching.

    This function looks for common patterns in manufacturer listing sections:
    - Numbered lists: "1. ThyssenKrupp Elevator."
    - Bulleted lists: "- ThyssenKrupp Elevator"
    - Inline lists: "provide products by the following: 1. ThyssenKrupp Elevator."

    Args:
        text: Text content from manufacturer section

    Returns:
        List of manufacturer names

    Example:
        >>> text = "Manufacturers: Subject to compliance with requirements, provide products by the following: 1. ThyssenKrupp Elevator."
        >>> _extract_manufacturers_from_text(text)
        ["ThyssenKrupp Elevator"]
    """
    manufacturers = []

    # Pattern 1: Numbered lists (e.g., "1. ThyssenKrupp Elevator.")
    # Match: digit(s) followed by period, then text until period or newline
    pattern1 = r"\d+\.\s+([A-Z][A-Za-z0-9\s&,.-]+?)(?:\.|$)"
    matches = re.findall(pattern1, text, re.MULTILINE)
    for match in matches:
        manufacturer = match.strip()
        # Filter out common non-manufacturer text
        if len(manufacturer) > 3 and not any(
            word in manufacturer.lower()
            for word in ["subject to", "provide", "obtain", "major", "shall be"]
        ):
            manufacturers.append(manufacturer)
            logger.debug(f"Extracted manufacturer (pattern 1): {manufacturer}")

    # Pattern 2: After "following:" keyword
    # Match: "following:" followed by numbered list
    pattern2 = r"following:\s*\d+\.\s+([A-Z][A-Za-z0-9\s&,.-]+?)(?:\.|$)"
    matches = re.findall(pattern2, text, re.MULTILINE | re.IGNORECASE)
    for match in matches:
        manufacturer = match.strip()
        if len(manufacturer) > 3 and manufacturer not in manufacturers:
            manufacturers.append(manufacturer)
            logger.debug(f"Extracted manufacturer (pattern 2): {manufacturer}")

    return manufacturers


def enrich_facts_with_manufacturers(
    facts: List[Fact],
    manufacturer_mappings: Dict[str, List[str]],
) -> List[Fact]:
    """
    Enrich facts with manufacturer information based on entity type.

    This function associates manufacturer information with facts that are missing it.
    It uses the manufacturer mappings extracted from PART 2 - PRODUCTS sections to
    populate the entity.manufacturer field for facts based on their entity type.

    Strategy:
    1. For each fact without manufacturer information
    2. Look up manufacturers for that entity type in the mappings
    3. If single manufacturer: use it directly
    4. If multiple manufacturers: use first one with "or equivalent" suffix
    5. If no manufacturers found: leave as None

    Args:
        facts: Facts to enrich
        manufacturer_mappings: Entity type -> manufacturers mapping from extract_manufacturer_mappings()

    Returns:
        Enriched facts with manufacturer information populated

    Example:
        >>> facts = [
        ...     Fact(entity=Entity(type="elevator", manufacturer=None), ...),
        ... ]
        >>> mappings = {"elevator": ["ThyssenKrupp", "Otis"]}
        >>> enriched = enrich_facts_with_manufacturers(facts, mappings)
        >>> enriched[0].entity.manufacturer
        "ThyssenKrupp or equivalent"

    Note:
        - Facts with existing manufacturer information are not modified
        - The "or equivalent" suffix indicates multiple acceptable manufacturers
        - This is a post-processing step that doesn't modify the original extraction logic
    """
    enriched_facts = []
    enriched_count = 0

    for fact in facts:
        # Skip if manufacturer already set
        if fact.entity.manufacturer:
            enriched_facts.append(fact)
            continue

        # Look up manufacturers for this entity type
        entity_type = fact.entity.type
        manufacturers = manufacturer_mappings.get(entity_type, [])

        if manufacturers:
            # If single manufacturer, use it directly
            # If multiple manufacturers, use first one with "or equivalent" suffix
            if len(manufacturers) == 1:
                fact.entity.manufacturer = manufacturers[0]
            else:
                fact.entity.manufacturer = f"{manufacturers[0]} or equivalent"

            enriched_count += 1
            logger.debug(f"Enriched fact {fact.id} with manufacturer: {fact.entity.manufacturer}")

        enriched_facts.append(fact)

    logger.info(
        f"Enriched {enriched_count}/{len(facts)} facts with manufacturer information "
        f"({len(manufacturer_mappings)} entity types)"
    )

    return enriched_facts


async def harvest_facts_for_doc(
    document_id: str,
    chunks: List[DocumentChunk],
    llm_client: Union[ChatOpenAI, ChatTogether],
    entity_hints: Optional[Dict[str, str]] = None,
    normalize: bool = True,
    batch_size: int = 10,
    progress_callback: Optional[callable] = None,
    enrich_manufacturers: bool = True,
) -> List[Fact]:
    """
    Extract facts from all chunks in a document.

    This function orchestrates the complete fact extraction pipeline:
    1. Extract facts from chunks using LLM (in parallel batches)
    2. Normalize units (if requested)
    3. Deduplicate facts
    4. Enrich with manufacturer information (if requested)

    Args:
        document_id: Document identifier
        chunks: List of document chunks
        llm_client: OpenAI LLM client
        entity_hints: Optional hints for entity types by section_id
        normalize: Whether to normalize units (default: True)
        batch_size: Number of concurrent extractions (default: 10)
        progress_callback: Optional callback function to report progress (chunks_processed, total_chunks, percentage)
        enrich_manufacturers: Whether to enrich facts with manufacturer information (default: True)

    Returns:
        List of all extracted facts (deduplicated and enriched)

    Example:
        >>> facts = await harvest_facts_for_doc(
        ...     document_id="spec-123",
        ...     chunks=chunks,
        ...     llm_client=llm,
        ...     entity_hints={"default": "elevator"},
        ...     enrich_manufacturers=True
        ... )
        >>> # Facts now have manufacturer information populated
    """
    all_facts: List[Fact] = []
    total_chunks = len(chunks)
    chunks_processed = 0

    # Process chunks in batches
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]

        # Extract facts concurrently
        tasks = []
        for chunk in batch:
            hint = None
            if entity_hints:
                hint = entity_hints.get(chunk.section_id) or entity_hints.get("default")

            tasks.append(extract_facts_from_chunk(chunk, document_id, llm_client, entity_hint=hint))

        batch_results = await asyncio.gather(*tasks)

        # Flatten results
        for facts in batch_results:
            all_facts.extend(facts)

        # Update progress
        chunks_processed = min(i + batch_size, total_chunks)
        percentage = int((chunks_processed / total_chunks) * 100)

        logger.info(
            f"Processed batch {i // batch_size + 1}/{(len(chunks) - 1) // batch_size + 1} - {chunks_processed}/{total_chunks} chunks ({percentage}%)"
        )

        # Call progress callback if provided
        if progress_callback:
            await progress_callback(chunks_processed, total_chunks, percentage)

    # Normalize units if requested
    if normalize:
        all_facts = [normalize_fact_value(fact) for fact in all_facts]
        logger.info(f"Normalized units for {len(all_facts)} facts")

    # Deduplicate
    all_facts = dedupe_facts(all_facts)

    # Enrich with manufacturer information (post-processing step)
    if enrich_manufacturers:
        logger.info("Starting manufacturer enrichment...")
        manufacturer_mappings = extract_manufacturer_mappings(all_facts, chunks)
        all_facts = enrich_facts_with_manufacturers(all_facts, manufacturer_mappings)
        logger.info(
            f"Manufacturer enrichment complete: {len(manufacturer_mappings)} entity types mapped"
        )

    logger.info(f"Extracted {len(all_facts)} total facts from document {document_id}")

    return all_facts
