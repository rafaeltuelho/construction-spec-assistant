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

        # Call LLM
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

        response = await llm_client.ainvoke(messages)
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


async def harvest_facts_for_doc(
    document_id: str,
    chunks: List[DocumentChunk],
    llm_client: Union[ChatOpenAI, ChatTogether],
    entity_hints: Optional[Dict[str, str]] = None,
    normalize: bool = True,
    batch_size: int = 10,
    progress_callback: Optional[callable] = None,
) -> List[Fact]:
    """
    Extract facts from all chunks in a document.

    Args:
        document_id: Document identifier
        chunks: List of document chunks
        llm_client: OpenAI LLM client
        entity_hints: Optional hints for entity types by section_id
        normalize: Whether to normalize units (default: True)
        batch_size: Number of concurrent extractions (default: 10)
        progress_callback: Optional callback function to report progress (chunks_processed, total_chunks, percentage)

    Returns:
        List of all extracted facts (deduplicated)
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

    logger.info(f"Extracted {len(all_facts)} total facts from document {document_id}")

    return all_facts
