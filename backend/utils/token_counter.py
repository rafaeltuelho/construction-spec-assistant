"""Token counting utilities for the Construction Spec Assistant backend."""

import tiktoken
from typing import Dict, Any


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count the number of tokens in text using tiktoken.
    
    Args:
        text: The text to count tokens for
        model: The OpenAI model to use for tokenization (default: gpt-4)
    
    Returns:
        Number of tokens
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except KeyError:
        # Fallback to cl100k_base encoding (used by GPT-4, GPT-3.5-turbo, etc.)
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))


def analyze_document_tokens_with_limits(full_text: str, model: str = "gpt-4-turbo") -> Dict[str, Any]:
    """
    Analyze token count for a document with model limit checking.
    """
    # Model limits (input + output combined)
    MODEL_LIMITS = {
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4.1": 1000000
    }
    
    total_tokens = count_tokens(full_text, model)
    
    model_limit = MODEL_LIMITS.get(model, 128000)  # Default to GPT-4 Turbo limit
    reserved_output_tokens = 2000  # Reserve tokens for response
    
    token_analysis = {
        "model_used": model,
        "total_tokens": total_tokens,
        "model_limit": model_limit,
        "effective_input_limit": model_limit - reserved_output_tokens,
        "fits_in_context": total_tokens <= (model_limit - reserved_output_tokens),
        "utilization_percentage": (total_tokens / (model_limit - reserved_output_tokens)) * 100,
        "recommendation": ""
    }
    
    # Generate recommendations
    if token_analysis["fits_in_context"]:
        if token_analysis["utilization_percentage"] < 50:
            token_analysis["recommendation"] = "✅ Document fits comfortably in context window"
        elif token_analysis["utilization_percentage"] < 80:
            token_analysis["recommendation"] = "⚠️ Document uses significant portion of context window"
        else:
            token_analysis["recommendation"] = "🔶 Document uses most of context window - consider chunking for complex tasks"
    else:
        token_analysis["recommendation"] = f"❌ Document exceeds context limit by {total_tokens - token_analysis['effective_input_limit']:,} tokens - chunking required"
    
    return token_analysis


def print_token_analysis_with_limits(token_analysis: Dict[str, Any]):
    """Print formatted token analysis with limit information."""
    if "error" in token_analysis:
        print(f"❌ {token_analysis['error']}")
        return
    
    print("📊 Token Analysis with Model Limits")
    print("=" * 60)
    print(f"Model: {token_analysis['model_used']}")
    print(f"Document tokens: {token_analysis['total_tokens']:,}")
    print(f"Model limit: {token_analysis['model_limit']:,}")
    print(f"Effective input limit: {token_analysis['effective_input_limit']:,}")
    print(f"Utilization: {token_analysis['utilization_percentage']:.1f}%")
    print(f"Fits in context: {'Yes' if token_analysis['fits_in_context'] else 'No'}")
    print(f"Recommendation: {token_analysis['recommendation']}")
