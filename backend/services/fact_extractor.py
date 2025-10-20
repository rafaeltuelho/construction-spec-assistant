"""Fact extraction service using LLM for extracting structured facts from documents."""

import json
import uuid
import logging
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..models.facts import Fact, Entity, Attribute, Value, Context
from ..utils.constraint_parser import apply_ranges_inequalities

logger = logging.getLogger(__name__)


# LLM prompts for fact extraction
FACT_EXTRACTOR_SYSTEM_PROMPT = """
You are a construction/architecture spec assistant. You understand CSI specs.
Act like a construction specialist and carefully extract explicit technical facts paying attention to technincal standards, codes and specifications. 
These facts will be further used to perform a comparison with submttal and product description (manufecture brochures, etc).
Do extract them as JSON Lines (one JSON object per line)!

Rules:
- NO inference: only facts explicitly stated in the text.
- Copy values verbatim into value.raw; if numeric, also parse value.num and value.unit.
- Use op in {"=",">=","<=","~","between"}; use "between" when a closed range is printed.
- Keep source_span ≤ 25 words, verbatim from the text.
- If multiple subfacts (e.g., Up/Down speeds), emit multiple JSON lines with qualifiers.
- If nothing factual is present, output nothing (empty response).
- Preserve factual meaning.
- Output ONLY JSON Lines. Do not wrap in arrays. No prose.
"""

EXTRACTOR_PROMPT_TEMPLATE = """DOC_ID: {doc_id}
SECTION_ID: {section_id}
HEADER_PATH: {header_path}

TEXT:
<<<
{chunk_text}
>>>

Emit JSON Lines with fields:
id (uuid), entity{{type?,name?,manufacturer?}}, attribute{{raw,canonical?}}, value{{raw,type,num?,unit?,min?,max?}}, op, qualifiers?, context{{doc_id,section_id,header_path,source_span,confidence}}.
"""


class FactExtractor:
    """Service for extracting facts from document chunks using LLM."""
    
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0):
        """
        Initialize the fact extractor.
        
        Args:
            model: LLM model to use for extraction
            temperature: Temperature for LLM generation
        """
        self.model = model
        self.temperature = temperature
        self.llm = ChatOpenAI(model=model, temperature=temperature)
    
    def llm_extract_jsonl(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call LLM to extract facts as JSON Lines.
        
        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt with the document chunk
            
        Returns:
            Raw text response from LLM containing JSON Lines
        """
        try:
            # Create messages list
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self.llm.invoke(messages)
            logger.debug(f"LLM response: {response.content}")
            return response.content
            
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            raise
    
    def parse_jsonl(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse NDJSON response from LLM.
        
        Args:
            text: Raw text response from LLM
            
        Returns:
            List of parsed JSON objects
        """
        cleaned = text.strip()
        # Strip code fences if the model added them
        import re
        cleaned = re.sub(r"^```(?:jsonl|json)?\s*|```$", "", cleaned, flags=re.MULTILINE).strip()
        items = []
        for line in cleaned.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                # Best-effort repair: try to fix trailing commas or single quotes
                line2 = line.replace("'", '"')
                try:
                    items.append(json.loads(line2))
                except Exception:
                    # Log and skip
                    logger.debug(f"Bad JSONL line: {line}")
                    continue
        return items
    
    def extract_facts_from_chunk(
        self,
        doc_id: str,
        chunk: Dict[str, Any],
        entity_hint: Optional[str] = None
    ) -> List[Fact]:
        """
        Extract facts from a single document chunk.
        
        Args:
            doc_id: Document identifier
            chunk: Document chunk dictionary
            entity_hint: Hint for entity type in this section
            
        Returns:
            List of extracted facts
        """
        section_id = chunk["section_id"]
        header_path = chunk["header_path"]
        text = chunk["text"]

        system_prompt = FACT_EXTRACTOR_SYSTEM_PROMPT
        if entity_hint:
            system_prompt += f"\nEntity hint: The entity.type in this section is likely '{entity_hint}'."

        user_prompt = EXTRACTOR_PROMPT_TEMPLATE.format(
            doc_id=doc_id,
            section_id=section_id,
            header_path=" > ".join(header_path),
            chunk_text=text
        )

        raw = self.llm_extract_jsonl(system_prompt, user_prompt)
        items = self.parse_jsonl(raw)

        facts: List[Fact] = []
        for it in items:
            # fill required context bits if missing
            it.setdefault("id", str(uuid.uuid4()))
            it.setdefault("context", {})
            it["context"].setdefault("doc_id", doc_id)
            it["context"].setdefault("section_id", section_id)
            
            # Fix: Convert string header_path back to list if needed
            llm_header_path = it["context"].get("header_path", header_path)
            if isinstance(llm_header_path, str):
                # Split the string back into a list
                it["context"]["header_path"] = llm_header_path.split(" > ")
            else:
                # Use the original header_path from chunk if LLM didn't provide one
                it["context"]["header_path"] = header_path
                
            if "confidence" not in it["context"]:
                it["context"]["confidence"] = 0.9

            # basic resilience: ensure sub-objects exist
            it.setdefault("entity", {})
            it.setdefault("attribute", {"raw": ""})
            it.setdefault("value", {"raw": "", "type": "text"})

            try:
                facts.append(Fact(**it))
            except Exception as ve:
                # inspect ve.errors() to improve prompts
                logger.error(f"Validation error: {ve}")
                continue

        # Verify each fact against span before returning
        facts = self.self_verify_against_span(facts, chunk["text"])
        return facts
    
    def self_verify_against_span(self, facts: List[Fact], chunk_text: str) -> List[Fact]:
        """
        Quick self-verification (cheap guardrail) for facts.
        
        Args:
            facts: List of facts to verify
            chunk_text: Original chunk text
            
        Returns:
            List of verified facts
        """
        verified_facts = []
        for f in facts:
            span = f.context.source_span 
            vr = f.value.raw 
            span_ok = span and (span in chunk_text)
            value_ok = (vr.lower() in span.lower()) if vr else True
            if span_ok and value_ok:
                verified_facts.append(f)
            else:
                # keep but lower confidence or tag
                f.context.confidence = min(0.6, f.context.confidence)
                verified_facts.append(f)
        return verified_facts
    
    def fact_signature(self, f: Fact) -> str:
        """
        Create signature for fact deduplication.
        
        Args:
            f: Fact to create signature for
            
        Returns:
            Signature string for deduplication
        """
        ent = (f.entity.type or "", f.entity.name or "", f.entity.manufacturer or "")
        attr = f.attribute.canonical or f.attribute.raw
        return "|".join([*ent, attr, f.value.raw, f.context.section_id])
    
    def dedupe_facts(self, facts: List[Fact]) -> List[Fact]:
        """
        Deduplicate facts based on signature.
        
        Args:
            facts: List of facts to deduplicate
            
        Returns:
            List of deduplicated facts
        """
        seen = set()
        out = []
        for f in facts:
            sig = self.fact_signature(f)
            if sig in seen:
                continue
            seen.add(sig)
            out.append(f)
        return out
    
    def harvest_facts_for_doc(
        self,
        doc_info: Dict[str, Any],
        entity_hints: Optional[Dict[str, str]] = None,  # {section_id: "elevator"}
        normalize: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Extract facts from all chunks in a document.
        
        Args:
            doc_info: Document information dictionary
            entity_hints: Optional hints for entity types by section
            normalize: Whether to normalize facts after extraction
            
        Returns:
            List of extracted facts as dictionaries
        """
        doc_id = doc_info["filename"]
        chunks = doc_info.get("section_chunks", [])
        all_facts: List[Fact] = []

        for ch in chunks:
            hint = None
            if entity_hints:
                hint = entity_hints.get(ch["section_id"]) or entity_hints.get("default")
            facts = self.extract_facts_from_chunk(doc_id, ch, entity_hint=hint)
            all_facts.extend(facts)

        if normalize:
            # Convert to dicts for normalization, then back to Facts
            fact_dicts = [f.model_dump() for f in all_facts]
            fact_dicts = apply_ranges_inequalities(fact_dicts)
            all_facts = [Fact(**d) for d in fact_dicts]

        all_facts = self.dedupe_facts(all_facts)

        # Convert to JSON-serializable format
        return [json.loads(f.model_dump_json()) for f in all_facts]
    
    def save_facts_to_jsonl(self, facts: List[Dict[str, Any]], output_path: Path):
        """
        Save facts to JSONL file.
        
        Args:
            facts: List of fact dictionaries
            output_path: Path to save the JSONL file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fp:
            for f in facts:
                fp.write(json.dumps(f, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(facts)} facts to {output_path}")
