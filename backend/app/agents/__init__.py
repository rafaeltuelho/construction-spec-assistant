"""
LangGraph agents for agentic workflows.

This package provides LangGraph-based agents for:
- Spec-to-submittal comparison
"""

from app.agents.comparison_graph import (
    ComparisonState,
    create_comparison_graph,
    retrieve_node,
    compare_node,
)
from app.agents.prompts import (
    FACT_EXTRACTOR_SYSTEM_PROMPT,
    EXTRACTOR_PROMPT_TEMPLATE,
    COMPARISON_SYSTEM_PROMPT,
    COMPARISON_PROMPT_TEMPLATE,
)

__all__ = [
    "ComparisonState",
    "create_comparison_graph",
    "retrieve_node",
    "compare_node",
    "FACT_EXTRACTOR_SYSTEM_PROMPT",
    "EXTRACTOR_PROMPT_TEMPLATE",
    "COMPARISON_SYSTEM_PROMPT",
    "COMPARISON_PROMPT_TEMPLATE",
]
