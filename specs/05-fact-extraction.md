# Fact Extraction System Specification

## Purpose

This document specifies the implementation of the fact extraction system, including LLM-based structured extraction, Pydantic models, unit normalization, and deduplication.

## Overview

The fact extraction system transforms unstructured construction document text into structured, searchable facts using an Entity-Attribute-Value (EAV) schema.

```
┌──────────────────┐
│  Document Chunks │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  LLM Extraction  │
│  (GPT-4 family)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Pydantic        │
│  Validation      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Unit            │
│  Normalization   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Deduplication   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  MongoDB Storage │
└──────────────────┘
```

---

## 1. Pydantic Models

### Module: `backend/app/models/fact.py`

### Notebook Reference
- **Lines**: 779-1152
- **Key Models**: `Entity`, `Attribute`, `Value`, `Context`, `Fact`

### Implementation

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

class EntityType(str, Enum):
    """Entity type categories."""
    EQUIPMENT = "equipment"
    MATERIAL = "material"
    SYSTEM = "system"
    COMPONENT = "component"
    LOCATION = "location"
    ORGANIZATION = "organization"
    PERSON = "person"
    OTHER = "other"

class AttributeCategory(str, Enum):
    """Attribute categories."""
    PERFORMANCE = "performance"
    DIMENSION = "dimension"
    MATERIAL_PROPERTY = "material_property"
    REQUIREMENT = "requirement"
    SPECIFICATION = "specification"
    STANDARD = "standard"
    MANUFACTURER = "manufacturer"
    OTHER = "other"

class Entity(BaseModel):
    """Entity in EAV schema (e.g., 'Elevator', 'Concrete')."""
    raw: str = Field(..., description="Raw entity text from document")
    normalized: Optional[str] = Field(None, description="Normalized entity name")
    type: Optional[EntityType] = Field(None, description="Entity type category")
    
    @validator('normalized', always=True)
    def normalize_entity(cls, v, values):
        """Auto-normalize entity if not provided."""
        if v is None and 'raw' in values:
            return values['raw'].lower().strip()
        return v

class Attribute(BaseModel):
    """Attribute in EAV schema (e.g., 'capacity', 'strength')."""
    raw: str = Field(..., description="Raw attribute text from document")
    normalized: Optional[str] = Field(None, description="Normalized attribute name")
    category: Optional[AttributeCategory] = Field(None, description="Attribute category")
    
    @validator('normalized', always=True)
    def normalize_attribute(cls, v, values):
        """Auto-normalize attribute if not provided."""
        if v is None and 'raw' in values:
            return values['raw'].lower().strip()
        return v

class Value(BaseModel):
    """Value in EAV schema with unit normalization."""
    raw: str = Field(..., description="Raw value text from document")
    normalized: Optional[str] = Field(None, description="Normalized value")
    unit: Optional[str] = Field(None, description="Normalized unit")
    numeric: Optional[float] = Field(None, description="Numeric value if applicable")
    
    @validator('normalized', always=True)
    def normalize_value(cls, v, values):
        """Auto-normalize value if not provided."""
        if v is None and 'raw' in values:
            return values['raw'].strip()
        return v

class Context(BaseModel):
    """Context information for fact provenance."""
    source_document: str = Field(..., description="Document ID")
    section_path: str = Field(..., description="Section hierarchy path")
    chunk_id: str = Field(..., description="Chunk identifier")
    page_number: Optional[int] = Field(None, description="Page number if available")
    
class Fact(BaseModel):
    """Complete fact with EAV structure and context."""
    fact_id: Optional[str] = Field(None, description="Unique fact identifier")
    entity: Entity
    attribute: Attribute
    value: Value
    context: Context
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

---

## 2. LLM Extraction

### Module: `backend/app/services/fact_extraction.py`

### Notebook Reference
- **Lines**: 779-1152
- **Key Functions**: `extract_facts_from_chunk()`, `harvest_facts_for_doc()`

### System Prompt

```python
# In backend/app/agents/prompts.py

FACT_EXTRACTOR_SYSTEM_PROMPT = """You are an expert at extracting structured facts from construction specification documents.

Your task is to identify and extract facts in Entity-Attribute-Value (EAV) format.

**Entity**: The subject (e.g., "Elevator", "Concrete", "Steel Beam")
**Attribute**: The property or characteristic (e.g., "capacity", "strength", "dimension")
**Value**: The specific value (e.g., "2500 lbs", "4000 PSI", "12 inches")

**Guidelines**:
1. Extract only explicit facts stated in the text
2. Do not infer or assume information not present
3. Preserve original units and values
4. Include context about where the fact was found
5. Assign confidence score (0.0-1.0) based on clarity

**Output Format**:
Return a JSON array of facts, each with:
- entity: {raw: string, type: string}
- attribute: {raw: string, category: string}
- value: {raw: string}
- confidence: number (0.0-1.0)

**Example**:
Text: "The elevator shall have a minimum capacity of 2500 pounds."

Output:
[
  {
    "entity": {"raw": "Elevator", "type": "equipment"},
    "attribute": {"raw": "capacity", "category": "performance"},
    "value": {"raw": "2500 pounds"},
    "confidence": 0.95
  }
]
"""
```

### Extraction Function

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from typing import List
import json
import logging

logger = logging.getLogger(__name__)

async def extract_facts_from_chunk(
    chunk: SectionChunk,
    document_id: str,
    llm_client: ChatOpenAI
) -> List[Fact]:
    """
    Extract facts from a single document chunk using LLM.
    
    Args:
        chunk: Document chunk to process
        document_id: Source document identifier
        llm_client: OpenAI LLM client
    
    Returns:
        List of extracted Fact objects
    """
    try:
        # Prepare messages
        messages = [
            SystemMessage(content=FACT_EXTRACTOR_SYSTEM_PROMPT),
            HumanMessage(content=f"Extract facts from this text:\n\n{chunk.content}")
        ]
        
        # Call LLM with structured output
        response = await llm_client.ainvoke(messages)
        
        # Parse JSON response
        facts_data = json.loads(response.content)
        
        # Convert to Fact objects
        facts = []
        for fact_data in facts_data:
            # Add context
            context = Context(
                source_document=document_id,
                section_path=chunk.section_path,
                chunk_id=chunk.chunk_id,
                page_number=None  # TODO: Extract from chunk metadata
            )
            
            # Create Fact object
            fact = Fact(
                entity=Entity(**fact_data['entity']),
                attribute=Attribute(**fact_data['attribute']),
                value=Value(**fact_data['value']),
                context=context,
                confidence=fact_data['confidence']
            )
            
            facts.append(fact)
        
        logger.info(f"Extracted {len(facts)} facts from chunk {chunk.chunk_id}")
        return facts
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response for chunk {chunk.chunk_id}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error extracting facts from chunk {chunk.chunk_id}: {e}")
        return []
```

### Batch Extraction

```python
import asyncio
from typing import List

async def harvest_facts_for_doc(
    document_id: str,
    chunks: List[SectionChunk],
    llm_client: ChatOpenAI,
    batch_size: int = 10
) -> List[Fact]:
    """
    Extract facts from all chunks in a document.
    
    Args:
        document_id: Document identifier
        chunks: List of document chunks
        llm_client: OpenAI LLM client
        batch_size: Number of concurrent extractions
    
    Returns:
        List of all extracted facts
    """
    all_facts = []
    
    # Process chunks in batches
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        
        # Extract facts concurrently
        tasks = [
            extract_facts_from_chunk(chunk, document_id, llm_client)
            for chunk in batch
        ]
        
        batch_results = await asyncio.gather(*tasks)
        
        # Flatten results
        for facts in batch_results:
            all_facts.extend(facts)
        
        logger.info(f"Processed batch {i//batch_size + 1}/{(len(chunks)-1)//batch_size + 1}")
    
    logger.info(f"Extracted {len(all_facts)} total facts from document {document_id}")
    
    return all_facts
```

---

## 3. Unit Normalization

### Module: `backend/app/core/unit_normalizer.py`

### Notebook Reference
- **Lines**: 779-1152
- **Uses**: `pint` library

### Implementation

```python
from pint import UnitRegistry
from typing import Tuple, Optional
import re
import logging

logger = logging.getLogger(__name__)

# Initialize unit registry
ureg = UnitRegistry()

# Construction-specific unit aliases
ureg.define('pound = lb')
ureg.define('pounds = lb')
ureg.define('foot = ft')
ureg.define('feet = ft')
ureg.define('inch = in')
ureg.define('inches = in')
ureg.define('PSI = psi')

def normalize_unit(value_str: str, unit_str: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Normalize value and unit to standard units.
    
    Args:
        value_str: Numeric value as string
        unit_str: Unit as string
    
    Returns:
        Tuple of (normalized_value, normalized_unit)
    
    Examples:
        normalize_unit("2500", "pounds") -> (1133.98, "kg")
        normalize_unit("12", "inches") -> (0.3048, "m")
    """
    try:
        # Parse value
        value = float(value_str)
        
        # Create quantity
        quantity = value * ureg(unit_str)
        
        # Convert to base units
        base_quantity = quantity.to_base_units()
        
        return (base_quantity.magnitude, str(base_quantity.units))
        
    except Exception as e:
        logger.warning(f"Failed to normalize unit: {value_str} {unit_str}: {e}")
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
    """
    # Regex to extract number and unit
    pattern = r'([\d,]+\.?\d*)\s*([a-zA-Z]+)'
    match = re.search(pattern, raw_value)
    
    if match:
        value_str = match.group(1).replace(',', '')
        unit_str = match.group(2)
        
        try:
            value = float(value_str)
            return (value, unit_str)
        except ValueError:
            return (None, None)
    
    return (None, None)

async def normalize_fact_value(fact: Fact) -> Fact:
    """
    Normalize units in a fact's value.
    
    Args:
        fact: Fact object to normalize
    
    Returns:
        Fact with normalized value
    """
    # Parse raw value
    numeric, unit = parse_value_with_unit(fact.value.raw)
    
    if numeric and unit:
        # Normalize unit
        normalized_value, normalized_unit = normalize_unit(str(numeric), unit)
        
        if normalized_value and normalized_unit:
            fact.value.numeric = numeric
            fact.value.unit = unit
            fact.value.normalized = f"{normalized_value:.2f} {normalized_unit}"
    
    return fact
```

---

## 4. Deduplication

### Module: `backend/app/services/fact_extraction.py`

### Notebook Reference
- **Lines**: 779-1152
- **Key Function**: `dedupe_facts()`

### Implementation

```python
from typing import List
from collections import defaultdict

async def dedupe_facts(facts: List[Fact]) -> List[Fact]:
    """
    Deduplicate facts based on entity-attribute-value similarity.
    
    Strategy:
    1. Group facts by (entity.normalized, attribute.normalized)
    2. Within each group, keep fact with highest confidence
    3. If values differ, keep all (may be different contexts)
    
    Args:
        facts: List of facts to deduplicate
    
    Returns:
        Deduplicated list of facts
    """
    # Group by entity-attribute
    groups = defaultdict(list)
    
    for fact in facts:
        key = (
            fact.entity.normalized.lower(),
            fact.attribute.normalized.lower()
        )
        groups[key].append(fact)
    
    deduplicated = []
    
    for key, group_facts in groups.items():
        # Further group by value
        value_groups = defaultdict(list)
        
        for fact in group_facts:
            value_key = fact.value.normalized.lower()
            value_groups[value_key].append(fact)
        
        # Keep highest confidence fact for each value
        for value_key, value_facts in value_groups.items():
            best_fact = max(value_facts, key=lambda f: f.confidence)
            deduplicated.append(best_fact)
    
    logger.info(f"Deduplicated {len(facts)} facts to {len(deduplicated)} unique facts")
    
    return deduplicated
```

---

## 5. Storage

### Module: `backend/app/db/mongodb.py`

```python
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List

async def store_facts(facts: List[Fact]) -> List[str]:
    """
    Store facts in MongoDB.
    
    Args:
        facts: List of facts to store
    
    Returns:
        List of inserted fact IDs
    """
    collection = db["facts"]
    
    # Convert to dict and insert
    documents = [fact.dict() for fact in facts]
    result = await collection.insert_many(documents)
    
    return [str(id) for id in result.inserted_ids]

async def get_facts_by_document(document_id: str) -> List[Fact]:
    """
    Retrieve all facts for a document.
    
    Args:
        document_id: Document identifier
    
    Returns:
        List of Fact objects
    """
    collection = db["facts"]
    
    cursor = collection.find({"context.source_document": document_id})
    documents = await cursor.to_list(length=None)
    
    return [Fact(**doc) for doc in documents]
```

---

## Next Steps

Refer to the following specification document:

1. **06-rag-and-agents.md**: RAG retrieval and comparison agents

