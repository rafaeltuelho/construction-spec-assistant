# CSI Document processing pipeline proposal

Rafael, you’re on the right track. Since you can’t lock into a fixed schema across CSI sections, treat “facts” as open-ended EAV records (Entity–Attribute–Value) with evidence and light normalization. Then you can index those records for retrieval and run a comparison pass. Below is a practical, PoC-friendly approach that works well on specs + submittals.

⸻

1) Represent facts with an open model (no fixed schema)

Use a generic “Fact” that fits any CSI section:

```json
{
  "id": "auto or hash",
  "entity": {"type": "elevator", "name": "Endura MRL", "manufacturer": "ThyssenKrupp"},
  "attribute": {"raw": "Rated Speed (Up)", "canonical": "rated_speed_up"},
  "value": {"raw": "120 fpm", "type": "quantity", "num": 120, "unit": "fpm"},
  "op": "=",
  "qualifiers": {"direction": "up"},
  "context": {
    "doc_id": "Spec_14_24_00.pdf",
    "source_span": "Rated Speed: a. Up: 120 fpm.",
    "header_path": ["PART 2 - PRODUCTS","ELEVATORS","Elevator Description"],
    "line_nums": [..],
    "confidence": 0.94
  }
}
```

Key ideas:
 * entity = the “thing” being specified (elevator, pump, panel, etc.).
 * attribute.raw preserves wording; attribute.canonical maps to your growing catalog (see §3).
 * value carries raw + normalized (num/unit/type). Keep op so you can represent =, <=, range, etc.
 * Always keep evidence: the exact span + section headers.

Output JSON Lines: one fact per line. That makes indexing and diffing trivial.

⸻

2) Multi-pass LLM pipeline (small, reliable steps)

Pass A — Sectionizer
 * Goal: split text into logical chunks aligned to headings/bullets.
 * Prompt the LLM: “return a list of sections with title, path, text.”
 * This keeps later prompts short and scoped.

Pass B — Open-schema Fact Harvest
 * For each section chunk, ask the LLM to list all extractable facts as EAV JSONL.
 * Rules: “Only extract explicit facts; copy values verbatim; add op, value.type (quantity/text/enum/bool/range), units if present; include a 10–20 word source_span verbatim.”
 * This pass does not require prior knowledge of which attributes exist.

Pass C — Self-verify (optional but worth it)
 * Feed harvested facts + their spans back to the LLM: “For each fact, confirm the span actually supports it; remove/flag anything unsupported.”
 * This dramatically reduces hallucinations.

Pass D — Normalize/Canonicalize (LLM + rules)
 * Map attribute.raw → attribute.canonical, unify units (e.g., fpm → m/s if you want), fill entity fields when missing.
 * Use a tiny Attribute Catalog (next section) plus a unit library (pint later in code) to normalize numbers.

⸻

3) Lightweight Attribute Catalog (grow it over time)

You don’t want a rigid schema, but you do want canonical handles for matching. Start with a small YAML you can evolve:

```yaml
attributes:
  rated_load:
    synonyms: ["rated load", "capacity", "load capacity", "rated capacity"]
    value_type: quantity
    unit_hints: ["lb", "kg"]
  rated_speed_up:
    synonyms: ["rated speed up", "up speed"]
    value_type: quantity
    unit_hints: ["fpm", "m/s"]
  rated_speed_down:
    synonyms: ["rated speed down", "down speed"]
    value_type: quantity
    unit_hints: ["fpm", "m/s"]
  hoistway_entrance_width:
    synonyms: ["hoistway entrance width", "door width", "opening width"]
    value_type: quantity
    unit_hints: ["in", "mm"]
  finish_car_fixtures:
    synonyms: ["car fixtures", "fixtures finish"]
    value_type: text
```

Use it in Pass D to map raw keys to canonicals. Unknowns still pass through as attribute.canonical = null—you can match on raw text if needed.

⸻

4) Indexing for retrieval (spec ↔ submittal)

Index both full text chunks and facts:
 * Dense vectors (for semantic match):
 * Doc chunks (the usual RAG baseline)
 * Fact strings (concise, canonical text like: `"elevator | rated_speed_up | 120 fpm | ThyssenKrupp Endura MRL"`
 * Sparse/BM25 (for exact keywords/units):
 * Useful for attributes like “42 inches” or “stainless steel No. 4”.
 * Metadata filters: `entity.type=elevator, manufacturer=ThyssenKrupp, model=Endura MRL, attribute.canonical=rated_speed_up`

POC choice: Postgres + pgvector (cheap, simple), or OpenSearch hybrid (BM25 + vectors).

⸻

5) Candidate matching (blocking) before comparison

To avoid noisy comparisons, first get candidate pairs of (spec_fact, submittal_fact):
 * Block by entity keys: same manufacturer/model if available; else same division/section + entity type (e.g., “Elevator”).
 * Block by attribute: exact canonical match; if missing, fuzzy on attribute.raw using synonym list.
 * Where units differ, convert during comparison.

Now each spec fact has 0..N submittal candidates.

⸻

6) Inconsistency engine (rules first, LLM second)

Rules engine pass (fast, deterministic):
 * If op is = on spec and submittal value differs beyond tolerance → inconsistent.
 * If spec says >= X and submittal is < X → inconsistent.
 * If spec requires a material/finish and submittal lists a different material (exact string or synonym mismatch) → inconsistent.
 * Missing in submittal → gap (flag separately).

LLM reasoning pass (only for close calls):
 * Feed the spec fact + top-K submittal facts + their spans + your tolerance policy.
 * Ask: consistent | inconsistent | unclear with a one-sentence justification and cite the spans.

This keeps cost low and outcomes explainable.

⸻

7) Prompt blueprints

A) Fact Harvest (open schema, per section)

```
System: You extract explicit technical facts as JSON Lines (one record per line).

Rules:
- Do NOT infer; only extract what is explicitly stated.
- For each fact include:
  
  id (uuid-like), entity {type,name,manufacturer?}, attribute {raw}, value {raw,type,num?,unit?}, op, qualifiers (optional), context {source_span, header_path, confidence 0..1}.
  
- value.type in {quantity, text, enum, boolean, range}.
- If numeric, parse num and unit if present.
- Keep source_span to ≤20 words verbatim.

User Text (section):
<<<
{SECTION_TEXT}
>>>
```

B) Canonicalizer / Normalizer

```
System: You map fact attributes to a canonical label using this YAML catalog:
{ATTRIBUTE_CATALOG_YAML}

Task:
- For each fact, set attribute.canonical using synonyms (or null if unknown).
- Normalize value units if applicable; keep both raw and normalized.
- Return updated facts as JSON Lines.
```

C) Consistency Check (LLM backup after rules)

```
System: You are a compliance checker. Decide if the contractor submittal matches the spec.

Inputs:
- spec_fact: { ... }
- submittal_candidates: [ { ... }, ... ]
- policy: { "tolerances": { "rated_speed": {"abs_fpm": 5}, "rated_load": {"pct": 0.0} }, "material_match": "exact_or_synonym" }

Output JSON:
{
  "best_match_fact_id": "...",
  "verdict": "consistent" | "inconsistent" | "unclear",
  "reason": "short explanation",
  "spec_evidence": "verbatim span",
  "submittal_evidence": "verbatim span"
}
```

⸻

8) What lands in the vector store?

Store both:
1.	Chunk embeddings (for general Q&A and recall).
2.	Fact embeddings (for precise attribute lookups).

Suggested “fact text” for embedding:

"{entity.type}:{entity.name}|{attribute.canonical or attribute.raw}|{value.raw}|{manufacturer}|{model}"

Include metadata so you can filter before you embed-search.

⸻

9) Minimal scoring logic (PoC)
 * Exact attribute match (+2)
 * Entity manufacturer/model match (+2)
 * Unit-normalized numeric distance: score = 1 / (1 + |x−y|) (cap small ranges)
 * Span similarity (optional): cosine between spec span and submittal span embeddings

Use a weighted sum to pick best_match_fact_id. Only if score < threshold → send to LLM pass.

⸻

10) Reporting

Emit two artifacts:
 * Machine JSON: all comparisons with verdicts, reasons, and evidence spans.
 * Human PDF/HTML: grouped by entity → attribute, showing Spec vs Submittal, verdict badges, and quoted spans.

⸻

Example (your elevator snippet → facts, abbreviated)

```json
{"entity":{"type":"elevator","name":"Endura MRL","manufacturer":"ThyssenKrupp"},"attribute":{"raw":"Rated Load"},"value":{"raw":"3500 lb (1589 kg)","type":"quantity","num":3500,"unit":"lb"},"op":"=","context":{"source_span":"Rated Load: 3500 lb (1589 kg).","header_path":["PART 2 - PRODUCTS","ELEVATORS","Elevator Description"],"confidence":0.96}}

{"entity":{"type":"elevator","name":"Endura MRL","manufacturer":"ThyssenKrupp"},"attribute":{"raw":"Rated Speed (Up)"},"value":{"raw":"120 fpm","type":"quantity","num":120,"unit":"fpm"},"op":"=","qualifiers":{"direction":"up"},"context":{"source_span":"Rated Speed: a. Up: 120 fpm.","header_path":["PART 2 - PRODUCTS","ELEVATORS","Elevator Description"],"confidence":0.95}}

{"entity":{"type":"elevator","name":"Endura MRL","manufacturer":"ThyssenKrupp"},"attribute":{"raw":"Hoistway Entrance Width"},"value":{"raw":"42 inches (1067 mm)","type":"quantity","num":42,"unit":"in"},"op":"=","context":{"source_span":"Hoistway Entrances: a. Width: 42 inches (1067 mm).","header_path":["PART 2 - PRODUCTS","ELEVATORS","Hoistway Entrances"],"confidence":0.93}}

{"entity":{"type":"elevator"},"attribute":{"raw":"Car Fixtures Material"},"value":{"raw":"Satin stainless steel, No. 4 finish","type":"text"},"op":"=","context":{"source_span":"Car Fixtures: Satin stainless steel, No. 4 finish.","header_path":["PART 2 - PRODUCTS","ELEVATORS","Car Enclosures"],"confidence":0.92}}
```

Then a canonicalizer maps:
 * Rated Load → rated_load
 * Rated Speed (Up) → rated_speed_up
 * Hoistway Entrance Width → hoistway_entrance_width
 * Car Fixtures Material → finish_car_fixtures

⸻

Guardrails that really help
 * “Extract only what is explicitly stated” + evidence span (big hallucination reducer).
 * Two-model trick (optional): harvest with a small model, verify with a stronger one.
 * Strict JSON mode / tool calling so you never break your pipeline.
 * Unit normalization with a code step (not the LLM).
 * Confidence threshold: drop low-confidence facts or route them to human review.

⸻

What to build first (quick PoC order)
1.	Sectionizer prompt → JSON sections
2.	Fact Harvest (JSONL + spans)
3.	Canonicalizer + unit normalizer (small YAML + code)
4.	pgvector index for fact embeddings + metadata filters
5.	Simple rules engine for numeric/text equality
6.	LLM tie-breaker prompt for unclear cases
7.	JSON + HTML report

That’s it. This gives you a flexible, schema-less fact layer that still compares cleanly across Spec vs Submittal—and it scales as you add more CSI sections.