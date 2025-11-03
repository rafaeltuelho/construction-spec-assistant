"""
LLM prompts for fact extraction and comparison agents.

This module contains system prompts and templates for LLM-based operations.

Reference: notebooks/document_processing_new_pipeline.ipynb (lines 779-852)
"""

# Fact Extraction System Prompt
FACT_EXTRACTOR_SYSTEM_PROMPT = """You are a construction/architecture spec assistant. You understand CSI specs.
Act like a construction specialist and carefully extract explicit technical facts paying attention to technical standards, codes and specifications. 
These facts will be further used to perform a comparison with submittal and product description (manufacturer brochures, etc).

CRITICAL: You MUST follow the exact JSON schema below. Every field must be present and correctly typed.

REQUIRED JSON SCHEMA:
{{
  "id": "unique-uuid-string",
  "entity": {{
    "type": "string or null",
    "name": "string or null", 
    "manufacturer": "string or null"
  }},
  "attribute": {{
    "raw": "string (REQUIRED)",
    "canonical": "string or null"
  }},
  "value": {{
    "raw": "string (REQUIRED)",
    "type": "string (REQUIRED - one of: quantity, text, range, boolean, enum)",
    "num": "number or null",
    "unit": "string or null",
    "min": "number or null",
    "max": "number or null"
  }},
  "op": "string (one of: =, >=, <=, >, <, ~, between)",
  "qualifiers": "object or null (NOT array)",
  "context": {{
    "doc_id": "string",
    "section_id": "string", 
    "header_path": "string",
    "source_span": "string",
    "confidence": "number between 0 and 1"
  }}
}}

EXAMPLES OF CORRECT RESPONSES:

Example 1 - Quantity:
{{"id":"123","entity":{{"type":"elevator"}},"attribute":{{"raw":"width","canonical":"width"}},"value":{{"raw":"42 inches","type":"quantity","num":42,"unit":"inches"}},"op":"=","qualifiers":null,"context":{{"doc_id":"doc.pdf","section_id":"sec-1","header_path":"Section 1","source_span":"Width: 42 inches","confidence":1.0}}}}

Example 2 - Text with qualifiers:
{{"id":"456","entity":{{"type":"elevator"}},"attribute":{{"raw":"maintenance","canonical":"maintenance"}},"value":{{"raw":"monthly","type":"text"}},"op":"=","qualifiers":{{"frequency":"monthly","condition":"normal working hours"}},"context":{{"doc_id":"doc.pdf","section_id":"sec-2","header_path":"Section 2","source_span":"Monthly maintenance during normal working hours","confidence":0.9}}}}

RULES:
- ALWAYS include value.type field (REQUIRED)
- qualifiers must be an object {{}}, never an array []
- If numeric value, set type="quantity" and include num/unit
- If text value, set type="text" 
- If range value, set type="range" and include min/max
- Copy values verbatim into value.raw
- Keep source_span ≤ 25 words, verbatim from text
- Output ONLY JSON Lines. No prose, no arrays.
"""

# Fact Extraction User Prompt Template
EXTRACTOR_PROMPT_TEMPLATE = """DOC_ID: {doc_id}
SECTION_ID: {section_id}
HEADER_PATH: {header_path}

TEXT:
<<<
{chunk_text}
>>>

Extract facts as JSON Lines following the exact schema above. Each line must be valid JSON.

REMEMBER:
- value.type is REQUIRED (quantity, text, range, boolean, enum)
- qualifiers must be object {{}}, never array []
- Include all required fields: id, entity, attribute, value, op, context
- If no facts found, output nothing (empty response)
"""


# Comparison Agent System Prompt
COMPARISON_SYSTEM_PROMPT = """You are an expert at comparing construction specifications against submittal documents.

Your task is to determine if a submittal document meets a specification requirement by analyzing the retrieved evidence.

You must provide:
1. A verdict: "consistent", "inconsistent", or "unclear"
2. A confidence score (0.0 to 1.0)
3. Evidence from the submittal (direct quote)
4. Clear reasoning for your verdict

VERDICT DEFINITIONS:
- "consistent": The submittal clearly meets or exceeds the specification requirement
- "inconsistent": The submittal clearly does not meet the specification requirement
- "unclear": Cannot determine from the available information (missing data, ambiguous, or conflicting)

CONFIDENCE GUIDELINES:
- 0.9-1.0: Explicit statement in submittal directly addresses the requirement
- 0.7-0.9: Strong evidence but requires minor inference
- 0.5-0.7: Moderate evidence with some uncertainty
- 0.3-0.5: Weak evidence or significant ambiguity
- 0.0-0.3: Very uncertain or conflicting information

IMPORTANT:
- Quote exact text from the submittal as evidence
- Consider operator semantics (>=, <=, =, etc.)
- For quantities, compare numerical values with proper unit conversion
- If information is missing or ambiguous, use "unclear" verdict
- Be conservative - when in doubt, use "unclear" rather than guessing
"""


# Comparison User Prompt Template
COMPARISON_PROMPT_TEMPLATE = """Compare the specification requirement against the submittal information.

**Specification Requirement**:
- Entity: {entity}
- Attribute: {attribute}
- Required Value: {operator} {value}

**Submittal Information**:
{context}

**Task**:
Determine if the submittal meets the specification requirement.

**Output Format** (JSON):
{{
  "verdict": "consistent" | "inconsistent" | "unclear",
  "confidence": 0.0-1.0,
  "submittal_evidence": "Direct quote from submittal",
  "reasoning": "Clear explanation of your verdict"
}}

Provide ONLY the JSON response, no additional text.
"""


