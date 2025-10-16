# Architectural Submittal Reviewer

## Overview
This is a high-level description of an agentic system. This system
aims to help Construction Architects to perform the task of reviewing Construction documents to capture inconsistencies and discrepancies between what was designed and specified in the original drawings and specifications and the various submittals created by 3rd party contractor contractors.
The system takes as input from the user the following types of documents.
 - Architectural Drawings (CAD).
 - Construction Specifications.
 - Submittals.

 These documents are usually large PDF files containing unstructured data (text, tables, pictures, CAD drawings, etc).

Here is a list of features initially planned for the backend, which is responsible for processing and parsing the input data files.

## High level processing steps

### Parse & normalize (using Docling project)
 * Extract sections, tables, page coords, figure anchors.
 * Normalize units and quantities (e.g., thickness_inch, R_value).
 * Generate atomic “facts” with stable IDs, something like the following structure:
```
{
 "id":"spec:07-21-00:2.2.a",
 "topic":"insulation",
 "attr":"min_thickness_in",
 "op":">=",
 "value":6.25,
 "source": {
    "pdf":"Spec_07_21_00.pdf",
    "page":14,
    "span":"¶2.2.A"
  }
}
```

### Index for retrieval (hybrid, not just vector)
 * Dense vector index (semantic recall).
 * Sparse/BM25 index (exact codes, product names, ASTM).
 * Metadata filters (doc type=spec/submittal/drawing, CSI div, section).
 * Optionally a facts store (Postgres/JSON) for numeric comparisons.

### Build a Context Pack (CP) per task
 * A small bundle assembled by a “Context-Builder” agent:
    * Top-K passages from spec + submittal (hybrid retrieval).
    * The matching normalized facts (from the facts store).
    * Page/figure coordinates for citations.
    * (If drawing) image crop references or VLM detections with coords.
 * Size target: 2–8 chunks per side (spec vs submittal) + a few facts → typically <3–6k tokens.
 * Cache a stable prompt prefix (role/instructions + schema) to benefit KV caching across repeated checks.


### Reasoning
 * Give the LLM the CP only (not whole docs).
 * Ask for structured output (JSON with fields decision, rationale, citations[]).
 * Keep humans in the loop to accept/reject.

## Pragmatic “first cut” architecture
### Indexes
 * spec_passages (dense + BM25), submittal_passages (dense + BM25)
 * facts (relational/JSON), fig_index (page → figure/callout boxes)

### Agents
 1. Ingestor (Docling → JSON/facts)
 2. Retriever (hybrid search + filters)
 3. Context-Builder (assembles CP; dedups; unit-normalizes)
 4. Comparator (LLM; returns JSON verdict + citations)
 5. Verifier (optional second model/tool to recheck numbers)
 6. Reviewer (human UI with Accept/Reject; writes feedback)

### Chunking & retrieval tips (that matter here)
 * Semantic chunks by heading/paragraph from Docling, not blind token windows.
 * Tables: chunk by logical row/section; keep headers with each row.
 * Overlap: small (50–100 tokens) only where paragraphs run on.
 * Metadata: store doc_type, csi_div, section_id, page, span_id, units.
 * Hybrid retrieval: dense (semantic) + BM25 union, then re-rank with a lightweight cross-encoder or an LLM re-ranker (on the top ~20).
 * Top-K: start K=6–8 per side; tune by SME feedback.

### Context engineering patterns to adopt
 * Stable prompt prefix: fixed system/dev instructions + output schema → great KV-cache reuse across many comparisons in a session.
 * Schema-first prompting: ask for {decision, rationale, citations[]} only; reject extra prose.
 * Evidence binding: pass snippets with [page=x, span=y] and require the model to cite them.
 * Failure routes: if retrieval returns low confidence or conflicting spans, the Context-Builder escalates to the SME (“need a page mark-up”).

## Additional considerations
### Architecture inspiration
As a blueprint (and inspiration) for the agentic system architecture design use the LangGraph Open Deep Research project implementation: https://github.com/langchain-ai/open_deep_research

### Why not “feed the whole content”?
 * Cost/latency: large contexts balloon price and response time.
 * Noise: more tokens ≠ better grounding; retrieval beats brute-force.
 * Explainability: CP enforces tight citations to specific spans/pages.
 * Reuse: CPs are cacheable per issue; whole-doc contexts aren’t.

### When you might skip the VectorDB
 * Extremely small, text-only docs (e.g., 3–5 pages). Use a simple section filter + BM25 and assemble a CP directly.
 * Deterministic, field-by-field comparisons already extracted into a facts store (you can have the LLM validate only the mismatches).
