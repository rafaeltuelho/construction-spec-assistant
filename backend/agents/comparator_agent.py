"""Comparator agent using LangGraph for spec vs submittal comparison."""

import json
import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from .graph_definitions import ComparisonState
from .retrieval_agent import RetrievalAgent
from ..models.enums import RetrievalStrategy, ComparisonVerdict
from ..utils.constraint_parser import tolerances_for_fact

logger = logging.getLogger(__name__)


# LLM prompts for comparison
RAG_SYSTEM_COMPARATOR_PROMPT = """
You are a construction/architecture spec assistant. You understand CSI specs and submittals.
Decide if a contractor submittal chunk supports a spec fact. Output JSON only.

Rules:
- No inference beyond the chunk text.
- Provide submittal_evidence as a ≤25-word verbatim substring of the chunk.
- For numeric facts: compare units and numbers; respect operators (=, <=, >=, between, ~).
- If the chunk is irrelevant or missing the value, verdict="unclear".
- JSON keys: verdict, reason, submittal_evidence.
"""

RAG_HUMAN_COMPARATOR_PROMPT_TEMPLATE = """
Spec fact:
{spec_fact_json}

Submittal chunk (metadata: tier={source_tier}, tags={tags}):
<<<
{submittal_chunk}
>>>

Return only:
{{"verdict":"consistent|inconsistent|unclear","reason":"...", "submittal_evidence":"..."}}
"""


class ComparatorAgent:
    """Agent for comparing specification facts with submittal documents using LangGraph."""
    
    def __init__(
        self,
        retrieval_agent: RetrievalAgent,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0
    ):
        """
        Initialize the comparator agent.
        
        Args:
            retrieval_agent: RetrievalAgent instance for finding relevant chunks
            model: LLM model to use for comparison
            temperature: Temperature for LLM generation
        """
        self.retrieval_agent = retrieval_agent
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        self.json_parser = JsonOutputParser()
        
        # Create prompt template
        self.comparator_prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SYSTEM_COMPARATOR_PROMPT),
            ("human", RAG_HUMAN_COMPARATOR_PROMPT_TEMPLATE),
        ])
        
        self.graph = self._create_comparison_graph()
    
    def _create_comparison_graph(self) -> StateGraph:
        """Create the LangGraph for comparison operations."""
        graph = StateGraph(ComparisonState)
        
        # Add nodes
        graph.add_node("retrieve_candidates", self._retrieve_candidates_node)
        graph.add_node("compare_facts", self._compare_facts_node)
        graph.add_node("validate_evidence", self._validate_evidence_node)
        graph.add_node("aggregate_results", self._aggregate_results_node)
        
        # Set entry point
        graph.set_entry_point("retrieve_candidates")
        
        # Add edges
        graph.add_edge("retrieve_candidates", "compare_facts")
        graph.add_edge("compare_facts", "validate_evidence")
        graph.add_edge("validate_evidence", "aggregate_results")
        graph.add_edge("aggregate_results", END)
        
        return graph.compile()
    
    def _retrieve_candidates_node(self, state: ComparisonState) -> ComparisonState:
        """Retrieve candidate submittal chunks for comparison."""
        try:
            spec_fact = state["spec_fact"]
            catalog = state["catalog"]
            collection_name = state["collection_name"]
            top_k = state.get("top_k", 3)
            
            # Build query from spec fact
            query = self._build_query_terms(spec_fact, catalog)
            state["query"] = query
            
            # Retrieve candidates using retrieval agent
            candidates = self.retrieval_agent.retrieve(
                query=query,
                collection_name=collection_name,
                strategy=RetrievalStrategy.HYBRID,
                top_k=top_k
            )
            
            state["candidates"] = candidates
            logger.debug(f"Retrieved {len(candidates)} candidates for comparison")
            
        except Exception as e:
            logger.error(f"Failed to retrieve candidates: {e}")
            state["candidates"] = []
        
        return state
    
    def _compare_facts_node(self, state: ComparisonState) -> ComparisonState:
        """Compare spec fact with each candidate chunk."""
        try:
            spec_fact = state["spec_fact"]
            candidates = state["candidates"]
            comparison_results = []
            
            for doc in candidates:
                try:
                    result = self._compare_one_fact(spec_fact, doc)
                    comparison_results.append(result)
                except Exception as e:
                    logger.error(f"Failed to compare fact with chunk: {e}")
                    continue
            
            state["comparison_results"] = comparison_results
            logger.debug(f"Completed {len(comparison_results)} fact comparisons")
            
        except Exception as e:
            logger.error(f"Failed to compare facts: {e}")
            state["comparison_results"] = []
        
        return state
    
    def _validate_evidence_node(self, state: ComparisonState) -> ComparisonState:
        """Validate evidence and apply guardrails."""
        try:
            spec_fact = state["spec_fact"]
            comparison_results = state["comparison_results"]
            validated_results = []
            
            for result in comparison_results:
                try:
                    # Apply guardrails
                    validated_result = self._apply_guardrails(result, spec_fact)
                    validated_results.append(validated_result)
                except Exception as e:
                    logger.error(f"Failed to validate evidence: {e}")
                    continue
            
            state["comparison_results"] = validated_results
            
        except Exception as e:
            logger.error(f"Failed to validate evidence: {e}")
        
        return state
    
    def _aggregate_results_node(self, state: ComparisonState) -> ComparisonState:
        """Aggregate comparison results and select best match."""
        try:
            spec_fact = state["spec_fact"]
            comparison_results = state["comparison_results"]
            candidates = state["candidates"]
            
            if not comparison_results:
                final_result = {
                    "verdict": ComparisonVerdict.GAP.value,
                    "reason": "no supporting evidence found",
                    "submittal_evidence": "",
                    "confidence": 0.0
                }
            else:
                # Score and rank results
                ranked_results = []
                for i, result in enumerate(comparison_results):
                    if i < len(candidates):
                        doc = candidates[i]
                        score = self._score_candidate(
                            result.get("verdict", ""),
                            doc.page_content,
                            spec_fact,
                            doc.metadata.get("source_tier", "unknown"),
                            result.get("submittal_evidence", "")
                        )
                        ranked_results.append((score, result, doc))
                
                # Sort by score and get best result
                ranked_results.sort(key=lambda x: x[0], reverse=True)
                if ranked_results:
                    best_score, best_result, best_doc = ranked_results[0]
                    final_result = best_result.copy()
                    final_result.update({
                        "chunk_meta": best_doc.metadata,
                        "chunk_preview": (best_doc.page_content[:280] + ("..." if len(best_doc.page_content) > 280 else "")),
                        "query_used": state["query"],
                        "confidence": best_score
                    })
                else:
                    final_result = {
                        "verdict": ComparisonVerdict.GAP.value,
                        "reason": "no valid comparisons found",
                        "submittal_evidence": "",
                        "confidence": 0.0
                    }
            
            state["final_result"] = final_result
            
        except Exception as e:
            logger.error(f"Failed to aggregate results: {e}")
            state["final_result"] = {
                "verdict": ComparisonVerdict.GAP.value,
                "reason": f"aggregation failed: {str(e)}",
                "submittal_evidence": "",
                "confidence": 0.0
            }
        
        return state
    
    def _build_query_terms(self, spec_fact: Dict[str, Any], catalog: Dict[str, Any]) -> str:
        """Build query terms from spec fact and catalog."""
        terms = []
        
        # Add attribute terms
        attr_raw = spec_fact.get("attribute", {}).get("raw", "")
        if attr_raw:
            terms.append(attr_raw)
            
            # Add canonical attribute synonyms if available
            canon = spec_fact.get("attribute", {}).get("canonical")
            if canon and canon in (catalog.get("attributes") or {}):
                syns = catalog["attributes"][canon].get("synonyms", [])
                for s in syns:
                    if isinstance(s, dict) and "regex" in s:
                        terms.append(s["regex"])
                    else:
                        terms.append(str(s))
        
        # Add value terms
        v = spec_fact.get("value", {})
        if v.get("num") is not None and v.get("unit"):
            terms.append(f"{v['num']} {v['unit']}")
        elif v.get("raw"):
            terms.append(v["raw"])
        
        # Add entity hints
        ent = spec_fact.get("entity", {})
        for k in ("manufacturer", "name", "type"):
            if ent.get(k):
                terms.append(str(ent[k]))
        
        return " | ".join([t for t in terms if t])
    
    def _compare_one_fact(self, spec_fact: Dict[str, Any], doc: Document) -> Dict[str, Any]:
        """Compare a single spec fact with a document chunk."""
        md = doc.metadata or {}
        inputs = {
            "spec_fact_json": json.dumps(spec_fact, ensure_ascii=False),
            "source_tier": md.get("source_tier", "unknown"),
            "tags": ", ".join(md.get("attributes_present", []) or md.get("unit_set", []) or md.get("numbers_units", []) or []),
            "submittal_chunk": doc.page_content
        }
        
        try:
            raw = (self.comparator_prompt | self.llm).invoke(inputs).content
            result = json.loads(raw)
        except Exception:
            try:
                result = self.json_parser.parse(raw)
            except Exception:
                result = {
                    "verdict": ComparisonVerdict.UNCLEAR.value,
                    "reason": "failed to parse LLM response",
                    "submittal_evidence": ""
                }
        
        return result
    
    def _apply_guardrails(self, result: Dict[str, Any], spec_fact: Dict[str, Any]) -> Dict[str, Any]:
        """Apply guardrails to comparison result."""
        evidence = result.get("submittal_evidence", "")
        verdict = result.get("verdict", "")
        
        # Guardrail 1: Evidence must be substring of chunk
        if not self._evidence_ok(evidence, result.get("chunk_content", "")):
            result["verdict"] = ComparisonVerdict.UNCLEAR.value
            result["reason"] = "evidence not found in chunk text"
            return result
        
        # Guardrail 2: Numeric sanity check
        if spec_fact.get("value", {}).get("type") in {"quantity", "range"}:
            if not self._numeric_sanity_check(spec_fact, evidence):
                # Keep result but lower confidence
                result["confidence"] = result.get("confidence", 0.5) * 0.5
        
        return result
    
    def _evidence_ok(self, evidence: str, chunk_text: str) -> bool:
        """Check if evidence is substring of chunk text."""
        return bool(evidence) and (evidence in chunk_text)
    
    def _numeric_sanity_check(self, spec_fact: Dict[str, Any], evidence: str) -> bool:
        """Check numeric sanity of evidence against spec fact."""
        try:
            # Get tolerances for this fact
            tol_abs, tol_pct = tolerances_for_fact(spec_fact)
            
            # Parse evidence for numbers and units
            evidence_nums = self._parse_numbers_units(evidence)
            spec_value = spec_fact.get("value", {})
            
            if not evidence_nums or spec_value.get("type") not in {"quantity", "range"}:
                return True
            
            # Check if any evidence number matches spec within tolerance
            for num, unit in evidence_nums:
                if self._matches_within_tolerance(num, unit, spec_value, tol_abs, tol_pct):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Numeric sanity check failed: {e}")
            return True  # Default to allowing if check fails
    
    def _parse_numbers_units(self, text: str) -> List[Tuple[float, str]]:
        """Parse numbers and units from text."""
        # Simple regex for numbers and units
        pattern = r'(-?\d+(?:[\d,]*)(?:\.\d+)?)\s*([a-zA-Z/%°]+)?'
        matches = re.findall(pattern, text.replace(",", ""))
        
        results = []
        for num_str, unit in matches:
            try:
                num = float(num_str)
                results.append((num, unit.lower() if unit else ""))
            except ValueError:
                continue
        
        return results
    
    def _matches_within_tolerance(
        self,
        num: float,
        unit: str,
        spec_value: Dict[str, Any],
        tol_abs: float,
        tol_pct: float
    ) -> bool:
        """Check if number matches spec value within tolerance."""
        try:
            spec_num = spec_value.get("num")
            spec_unit = spec_value.get("unit", "")
            
            # Simple unit matching (could be enhanced)
            if unit and spec_unit and unit != spec_unit:
                return False
            
            if spec_num is None:
                return True
            
            spec_num = float(spec_num)
            op = spec_value.get("op", "=")
            
            if op == "=":
                return abs(num - spec_num) <= max(tol_abs, tol_pct * max(abs(num), abs(spec_num), 1e-9))
            elif op == ">=":
                return num + tol_abs >= spec_num
            elif op == "<=":
                return num - tol_abs <= spec_num
            elif op == ">":
                return num > spec_num
            elif op == "<":
                return num < spec_num
            elif op == "~":
                return abs(num - spec_num) <= max(tol_abs, tol_pct * max(abs(num), abs(spec_num)))
            
            return True
            
        except Exception as e:
            logger.error(f"Tolerance check failed: {e}")
            return True
    
    def _score_candidate(
        self,
        verdict: str,
        chunk_text: str,
        spec_fact: Dict[str, Any],
        tier: str,
        evidence: str
    ) -> float:
        """Score a candidate based on various factors."""
        score = 0.0
        
        # Verdict scoring
        if verdict == ComparisonVerdict.CONSISTENT.value:
            score += 2.0
        elif verdict == ComparisonVerdict.INCONSISTENT.value:
            score += 0.8
        else:
            score += 0.2
        
        # Tier scoring
        if tier in {"technical", "submittal"}:
            score += 0.4
        elif tier == "brochure":
            score += 0.2
        
        # Unit matching
        unit = (spec_fact.get("value") or {}).get("unit", "")
        if unit and unit.lower() in chunk_text.lower():
            score += 0.2
        
        # Evidence presence
        if evidence:
            score += 0.2
        
        return score
    
    def compare(
        self,
        spec_fact: Dict[str, Any],
        collection_name: str,
        catalog: Dict[str, Any],
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Compare a spec fact with submittal documents.
        
        Args:
            spec_fact: Specification fact to compare
            collection_name: Name of the submittal collection
            catalog: Attribute catalog for query building
            top_k: Number of candidate chunks to retrieve
            
        Returns:
            Comparison result dictionary
        """
        try:
            initial_state = ComparisonState(
                spec_fact=spec_fact,
                catalog=catalog,
                submittal_documents=[],
                submittal_metadatas=[],
                vectorstore_manager=self.retrieval_agent.vectorstore_manager,
                collection_name=collection_name,
                top_k=top_k,
                query="",
                candidates=[],
                comparison_results=[],
                final_result={}
            )
            
            result_state = self.graph.invoke(initial_state)
            return result_state.get("final_result", {})
            
        except Exception as e:
            logger.error(f"Comparison failed: {e}")
            return {
                "verdict": ComparisonVerdict.GAP.value,
                "reason": f"comparison failed: {str(e)}",
                "submittal_evidence": "",
                "confidence": 0.0
            }
