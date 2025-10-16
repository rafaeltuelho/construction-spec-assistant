# LLM Integration Specification

## Overview

This specification defines the multi-provider LLM integration system that supports OpenAI, Anthropic, and Ollama providers with configurable models, prompt engineering, and context optimization.

## Multi-Provider LLM Architecture

### Installation and Dependencies

```python
# requirements.txt
langchain==0.1.0
langchain-openai==0.0.5
langchain-anthropic==0.1.0
langchain-community==0.0.10
openai==1.3.0
anthropic==0.7.0
ollama==0.1.0
```

### LLM Provider Configuration

```python
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
from enum import Enum
import asyncio
from abc import ABC, abstractmethod

class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"

class LLMModel(BaseModel):
    """LLM model configuration"""
    provider: LLMProvider
    model_name: str
    max_tokens: int = 4000
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    timeout: int = 60
    retry_attempts: int = 3
    retry_delay: float = 1.0

class LLMConfig(BaseModel):
    """LLM configuration settings"""
    
    # Provider configurations
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    
    # Default model settings
    default_provider: LLMProvider = LLMProvider.OPENAI
    default_model: str = "gpt-4-turbo"
    
    # Model configurations
    models: Dict[str, LLMModel] = Field(default_factory=dict)
    
    # Performance settings
    max_concurrent_requests: int = 10
    request_timeout: int = 120
    enable_caching: bool = True
    cache_ttl: int = 3600  # 1 hour
    
    # Fallback settings
    enable_fallback: bool = True
    fallback_order: List[LLMProvider] = [
        LLMProvider.OPENAI,
        LLMProvider.ANTHROPIC,
        LLMProvider.OLLAMA
    ]
```

### Base LLM Provider Interface

```python
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from typing import AsyncGenerator, List, Dict, Any

class BaseLLMProvider(ABC):
    """Base interface for LLM providers"""
    
    def __init__(self, config: LLMModel):
        self.config = config
    
    @abstractmethod
    async def get_llm(self) -> BaseLanguageModel:
        """Get configured LLM instance"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is healthy"""
        pass
    
    @abstractmethod
    async def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        pass
    
    async def invoke(
        self, 
        messages: List[BaseMessage], 
        **kwargs
    ) -> str:
        """Invoke LLM with messages"""
        llm = await self.get_llm()
        response = await llm.ainvoke(messages, **kwargs)
        return response.content if hasattr(response, 'content') else str(response)
    
    async def stream(
        self, 
        messages: List[BaseMessage], 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response"""
        llm = await self.get_llm()
        async for chunk in llm.astream(messages, **kwargs):
            if hasattr(chunk, 'content'):
                yield chunk.content
            else:
                yield str(chunk)
```

### OpenAI Provider Implementation

```python
from langchain_openai import ChatOpenAI
import openai
from typing import Dict, Any

class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation"""
    
    def __init__(self, config: LLMModel, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        
        # Configure OpenAI client
        self.client = openai.AsyncOpenAI(api_key=api_key)
    
    async def get_llm(self) -> ChatOpenAI:
        """Get OpenAI LLM instance"""
        return ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            top_p=self.config.top_p,
            frequency_penalty=self.config.frequency_penalty,
            presence_penalty=self.config.presence_penalty,
            timeout=self.config.timeout,
            max_retries=self.config.retry_attempts,
            api_key=self.api_key
        )
    
    async def health_check(self) -> bool:
        """Check OpenAI API health"""
        try:
            models = await self.client.models.list()
            return len(models.data) > 0
        except Exception:
            return False
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI model information"""
        try:
            models = await self.client.models.list()
            model_info = next(
                (m for m in models.data if m.id == self.config.model_name), 
                None
            )
            
            if model_info:
                return {
                    "id": model_info.id,
                    "object": model_info.object,
                    "created": model_info.created,
                    "owned_by": model_info.owned_by,
                    "permission": model_info.permission,
                    "context_window": self._get_context_window(model_info.id)
                }
            return {}
        except Exception:
            return {}
    
    def _get_context_window(self, model_name: str) -> int:
        """Get context window size for model"""
        context_windows = {
            "gpt-4": 8192,
            "gpt-4-turbo": 128000,
            "gpt-4-turbo-preview": 128000,
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384
        }
        return context_windows.get(model_name, 4096)
```

### Anthropic Provider Implementation

```python
from langchain_anthropic import ChatAnthropic
import anthropic
from typing import Dict, Any

class AnthropicProvider(BaseLLMProvider):
    """Anthropic provider implementation"""
    
    def __init__(self, config: LLMModel, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        
        # Configure Anthropic client
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
    
    async def get_llm(self) -> ChatAnthropic:
        """Get Anthropic LLM instance"""
        return ChatAnthropic(
            model=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
            max_retries=self.config.retry_attempts,
            api_key=self.api_key
        )
    
    async def health_check(self) -> bool:
        """Check Anthropic API health"""
        try:
            # Simple health check by listing models
            await self.client.models.list()
            return True
        except Exception:
            return False
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get Anthropic model information"""
        try:
            models = await self.client.models.list()
            model_info = next(
                (m for m in models if m.id == self.config.model_name), 
                None
            )
            
            if model_info:
                return {
                    "id": model_info.id,
                    "object": model_info.object,
                    "created": model_info.created,
                    "owned_by": "anthropic",
                    "context_window": self._get_context_window(model_info.id)
                }
            return {}
        except Exception:
            return {}
    
    def _get_context_window(self, model_name: str) -> int:
        """Get context window size for model"""
        context_windows = {
            "claude-3-opus-20240229": 200000,
            "claude-3-sonnet-20240229": 200000,
            "claude-3-haiku-20240307": 200000,
            "claude-2": 100000,
            "claude-2.1": 200000
        }
        return context_windows.get(model_name, 100000)
```

### Ollama Provider Implementation

```python
from langchain_community.llms import Ollama
import ollama
from typing import Dict, Any

class OllamaProvider(BaseLLMProvider):
    """Ollama provider implementation"""
    
    def __init__(self, config: LLMModel, base_url: str):
        super().__init__(config)
        self.base_url = base_url
        
        # Configure Ollama client
        self.client = ollama.AsyncClient(host=base_url)
    
    async def get_llm(self) -> Ollama:
        """Get Ollama LLM instance"""
        return Ollama(
            model=self.config.model_name,
            temperature=self.config.temperature,
            num_predict=self.config.max_tokens,
            top_p=self.config.top_p,
            timeout=self.config.timeout,
            base_url=self.base_url
        )
    
    async def health_check(self) -> bool:
        """Check Ollama server health"""
        try:
            await self.client.list()
            return True
        except Exception:
            return False
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get Ollama model information"""
        try:
            models = await self.client.list()
            model_info = next(
                (m for m in models['models'] if m['name'] == self.config.model_name), 
                None
            )
            
            if model_info:
                return {
                    "name": model_info["name"],
                    "modified_at": model_info["modified_at"],
                    "size": model_info["size"],
                    "digest": model_info["digest"],
                    "details": model_info.get("details", {}),
                    "context_window": self._get_context_window(model_info["name"])
                }
            return {}
        except Exception:
            return {}
    
    def _get_context_window(self, model_name: str) -> int:
        """Get context window size for model"""
        # Ollama models typically have 4096 context window
        # This can be overridden in model configuration
        return 4096
```

## LLM Manager

### Multi-Provider Manager

```python
import asyncio
from typing import Dict, List, Optional, Any
import time
import hashlib
import json

class LLMManager:
    """Manager for multiple LLM providers"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.providers: Dict[str, BaseLLMProvider] = {}
        self.cache: Dict[str, Any] = {}
        self.request_semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        
        # Initialize providers
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available LLM providers"""
        
        # Initialize OpenAI provider
        if self.config.openai_api_key:
            for model_name, model_config in self.config.models.items():
                if model_config.provider == LLMProvider.OPENAI:
                    provider = OpenAIProvider(model_config, self.config.openai_api_key)
                    self.providers[f"openai_{model_name}"] = provider
        
        # Initialize Anthropic provider
        if self.config.anthropic_api_key:
            for model_name, model_config in self.config.models.items():
                if model_config.provider == LLMProvider.ANTHROPIC:
                    provider = AnthropicProvider(model_config, self.config.anthropic_api_key)
                    self.providers[f"anthropic_{model_name}"] = provider
        
        # Initialize Ollama provider
        for model_name, model_config in self.config.models.items():
            if model_config.provider == LLMProvider.OLLAMA:
                provider = OllamaProvider(model_config, self.config.ollama_base_url)
                self.providers[f"ollama_{model_name}"] = provider
    
    async def get_llm(
        self, 
        provider: Optional[str] = None, 
        model: Optional[str] = None
    ) -> BaseLanguageModel:
        """
        Get LLM instance for specified provider and model
        
        Args:
            provider: LLM provider name
            model: Model name
            
        Returns:
            Configured LLM instance
        """
        # Use defaults if not specified
        provider = provider or self.config.default_provider.value
        model = model or self.config.default_model
        
        # Find provider
        provider_key = f"{provider}_{model}"
        if provider_key not in self.providers:
            raise ValueError(f"Provider {provider_key} not available")
        
        provider_instance = self.providers[provider_key]
        return await provider_instance.get_llm()
    
    async def invoke(
        self,
        messages: List[BaseMessage],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        use_cache: bool = True,
        **kwargs
    ) -> str:
        """
        Invoke LLM with messages
        
        Args:
            messages: List of messages
            provider: LLM provider
            model: Model name
            use_cache: Whether to use caching
            **kwargs: Additional parameters
            
        Returns:
            LLM response
        """
        # Generate cache key
        cache_key = None
        if use_cache and self.config.enable_caching:
            cache_key = self._generate_cache_key(messages, provider, model, kwargs)
            if cache_key in self.cache:
                return self.cache[cache_key]
        
        # Acquire semaphore for rate limiting
        async with self.request_semaphore:
            try:
                # Try primary provider
                provider_instance = await self._get_provider(provider, model)
                response = await provider_instance.invoke(messages, **kwargs)
                
                # Cache response
                if cache_key:
                    self.cache[cache_key] = response
                
                return response
                
            except Exception as e:
                # Try fallback providers
                if self.config.enable_fallback:
                    for fallback_provider in self.config.fallback_order:
                        if fallback_provider.value != provider:
                            try:
                                fallback_instance = await self._get_provider(
                                    fallback_provider.value, 
                                    self.config.default_model
                                )
                                response = await fallback_instance.invoke(messages, **kwargs)
                                
                                # Cache response
                                if cache_key:
                                    self.cache[cache_key] = response
                                
                                return response
                                
                            except Exception:
                                continue
                
                raise e
    
    async def stream(
        self,
        messages: List[BaseMessage],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ):
        """
        Stream LLM response
        
        Args:
            messages: List of messages
            provider: LLM provider
            model: Model name
            **kwargs: Additional parameters
            
        Yields:
            Response chunks
        """
        provider_instance = await self._get_provider(provider, model)
        
        async for chunk in provider_instance.stream(messages, **kwargs):
            yield chunk
    
    async def _get_provider(self, provider: str, model: str) -> BaseLLMProvider:
        """Get provider instance"""
        provider_key = f"{provider}_{model}"
        if provider_key not in self.providers:
            raise ValueError(f"Provider {provider_key} not available")
        return self.providers[provider_key]
    
    def _generate_cache_key(
        self, 
        messages: List[BaseMessage], 
        provider: str, 
        model: str, 
        kwargs: Dict[str, Any]
    ) -> str:
        """Generate cache key for request"""
        cache_data = {
            "messages": [{"type": msg.__class__.__name__, "content": msg.content} for msg in messages],
            "provider": provider,
            "model": model,
            "kwargs": kwargs
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all providers"""
        health_status = {}
        
        for provider_key, provider in self.providers.items():
            try:
                health_status[provider_key] = await provider.health_check()
            except Exception:
                health_status[provider_key] = False
        
        return health_status
    
    async def get_provider_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all providers"""
        provider_info = {}
        
        for provider_key, provider in self.providers.items():
            try:
                provider_info[provider_key] = await provider.get_model_info()
            except Exception:
                provider_info[provider_key] = {}
        
        return provider_info
    
    def clear_cache(self):
        """Clear response cache"""
        self.cache.clear()
```

## Prompt Engineering

### Prompt Templates

```python
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from typing import Dict, Any, List

class PromptTemplates:
    """Collection of prompt templates for different tasks"""
    
    @staticmethod
    def get_document_comparison_prompt() -> ChatPromptTemplate:
        """Get prompt template for document comparison"""
        
        system_prompt = SystemMessagePromptTemplate.from_template("""
        You are an expert construction architect reviewing construction documents. 
        Your task is to compare specification requirements with contractor submittals 
        and identify any discrepancies, inconsistencies, or issues.
        
        You will receive:
        1. Specification content with citations
        2. Submittal content with citations
        3. Extracted facts from both documents
        
        Please analyze the provided documents and return your findings in the following JSON format:
        {{
            "findings": [
                {{
                    "finding_type": "discrepancy|consistent|missing|additional|unclear",
                    "confidence": 0.0-1.0,
                    "title": "Brief title of the finding",
                    "description": "Detailed description of the finding",
                    "recommendation": "Recommended action to resolve the issue",
                    "citations": [
                        {{
                            "source": "specification|submittal",
                            "page": 1,
                            "section": "2.1.A",
                            "text": "Exact quote from document"
                        }}
                    ]
                }}
            ],
            "summary": "Overall summary of the comparison",
            "confidence_score": 0.0-1.0
        }}
        
        Focus on:
        1. Technical accuracy and compliance
        2. Material specifications and properties
        3. Installation requirements and procedures
        4. Testing and quality control requirements
        5. Safety and performance standards
        
        Be thorough but concise. Provide specific citations for all findings.
        """)
        
        human_prompt = HumanMessagePromptTemplate.from_template("""
        Please compare the following specification and submittal documents:
        
        {context_pack}
        
        Return your analysis in the specified JSON format.
        """)
        
        return ChatPromptTemplate.from_messages([system_prompt, human_prompt])
    
    @staticmethod
    def get_fact_extraction_prompt() -> ChatPromptTemplate:
        """Get prompt template for fact extraction"""
        
        system_prompt = SystemMessagePromptTemplate.from_template("""
        You are an expert at extracting structured facts from construction documents.
        
        Extract facts from the provided text and return them in the following JSON format:
        {{
            "facts": [
                {{
                    "topic": "Subject area (e.g., insulation, concrete, electrical)",
                    "attribute": "Property name (e.g., min_thickness_in, compressive_strength_psi)",
                    "operator": "Comparison operator (=, >=, <=, >, <, contains, etc.)",
                    "value": "Fact value",
                    "unit": "Unit of measurement (if applicable)",
                    "original_text": "Exact text from document",
                    "confidence": 0.0-1.0
                }}
            ]
        }}
        
        Focus on:
        1. Numerical specifications with units
        2. Material properties and requirements
        3. Installation procedures and methods
        4. Testing requirements and standards
        5. Quality control measures
        
        Be precise and include the exact text from the document.
        """)
        
        human_prompt = HumanMessagePromptTemplate.from_template("""
        Extract facts from the following text:
        
        {text}
        
        Return the extracted facts in the specified JSON format.
        """)
        
        return ChatPromptTemplate.from_messages([system_prompt, human_prompt])
    
    @staticmethod
    def get_verification_prompt() -> ChatPromptTemplate:
        """Get prompt template for verification"""
        
        system_prompt = SystemMessagePromptTemplate.from_template("""
        You are an expert construction architect performing a second-pass verification 
        of document comparison findings.
        
        Review the following findings and provide verification in the following format:
        {{
            "verified": true|false,
            "overall_quality": 1-10,
            "findings_review": [
                {{
                    "finding_id": "finding_id",
                    "verified": true|false,
                    "quality_score": 1-10,
                    "suggestions": "Improvement suggestions",
                    "missing_issues": ["List of missing issues"]
                }}
            ],
            "notes": "Overall verification notes"
        }}
        """)
        
        human_prompt = HumanMessagePromptTemplate.from_template("""
        Please verify the following findings from a construction document comparison:
        
        {findings}
        
        Provide your verification in the specified format.
        """)
        
        return ChatPromptTemplate.from_messages([system_prompt, human_prompt])
```

### Context Optimization

```python
class ContextOptimizer:
    """Optimize context for LLM processing"""
    
    def __init__(self, max_context_tokens: int = 100000):
        self.max_context_tokens = max_context_tokens
    
    def optimize_context_pack(
        self, 
        context_pack: Dict[str, Any],
        target_tokens: int = None
    ) -> Dict[str, Any]:
        """
        Optimize context pack to fit within token limits
        
        Args:
            context_pack: Original context pack
            target_tokens: Target token count (defaults to max_context_tokens)
            
        Returns:
            Optimized context pack
        """
        target_tokens = target_tokens or self.max_context_tokens
        
        # Calculate current token usage
        current_tokens = self._estimate_tokens(context_pack)
        
        if current_tokens <= target_tokens:
            return context_pack
        
        # Optimize by reducing content
        optimized_pack = context_pack.copy()
        
        # Sort passages by relevance score
        spec_passages = sorted(
            context_pack.get("specification_content", []),
            key=lambda x: x.get("score", 0),
            reverse=True
        )
        
        submittal_passages = sorted(
            context_pack.get("submittal_content", []),
            key=lambda x: x.get("score", 0),
            reverse=True
        )
        
        facts = sorted(
            context_pack.get("facts", []),
            key=lambda x: x.get("confidence", 0),
            reverse=True
        )
        
        # Reduce content until within limits
        optimized_pack["specification_content"] = []
        optimized_pack["submittal_content"] = []
        optimized_pack["facts"] = []
        
        current_tokens = 0
        reserved_tokens = 2000  # Reserve for prompt and response
        
        # Add specification passages
        for passage in spec_passages:
            passage_tokens = self._estimate_passage_tokens(passage)
            if current_tokens + passage_tokens <= target_tokens - reserved_tokens:
                optimized_pack["specification_content"].append(passage)
                current_tokens += passage_tokens
            else:
                break
        
        # Add submittal passages
        for passage in submittal_passages:
            passage_tokens = self._estimate_passage_tokens(passage)
            if current_tokens + passage_tokens <= target_tokens - reserved_tokens:
                optimized_pack["submittal_content"].append(passage)
                current_tokens += passage_tokens
            else:
                break
        
        # Add facts
        for fact in facts:
            fact_tokens = self._estimate_fact_tokens(fact)
            if current_tokens + fact_tokens <= target_tokens - reserved_tokens:
                optimized_pack["facts"].append(fact)
                current_tokens += fact_tokens
            else:
                break
        
        # Update metadata
        optimized_pack["metadata"]["total_tokens"] = current_tokens
        optimized_pack["metadata"]["passage_count"] = len(optimized_pack["specification_content"]) + len(optimized_pack["submittal_content"])
        optimized_pack["metadata"]["fact_count"] = len(optimized_pack["facts"])
        
        return optimized_pack
    
    def _estimate_tokens(self, context_pack: Dict[str, Any]) -> int:
        """Estimate total tokens in context pack"""
        total_tokens = 0
        
        # Estimate specification content tokens
        for passage in context_pack.get("specification_content", []):
            total_tokens += self._estimate_passage_tokens(passage)
        
        # Estimate submittal content tokens
        for passage in context_pack.get("submittal_content", []):
            total_tokens += self._estimate_passage_tokens(passage)
        
        # Estimate facts tokens
        for fact in context_pack.get("facts", []):
            total_tokens += self._estimate_fact_tokens(fact)
        
        return total_tokens
    
    def _estimate_passage_tokens(self, passage: Dict[str, Any]) -> int:
        """Estimate tokens in a passage"""
        text = passage.get("text", "")
        return len(text) // 4  # Rough estimation: 4 characters per token
    
    def _estimate_fact_tokens(self, fact: Dict[str, Any]) -> int:
        """Estimate tokens in a fact"""
        fact_text = json.dumps(fact)
        return len(fact_text) // 4  # Rough estimation: 4 characters per token
```

## Usage Examples

### Document Comparison with LLM

```python
async def compare_documents_with_llm(
    llm_manager: LLMManager,
    context_pack: Dict[str, Any],
    provider: str = "openai",
    model: str = "gpt-4-turbo"
) -> Dict[str, Any]:
    """Compare documents using LLM"""
    
    # Get prompt template
    prompt_template = PromptTemplates.get_document_comparison_prompt()
    
    # Format context pack for prompt
    context_formatter = ContextPackBuilder()
    formatted_context = await context_formatter.format_context_pack_for_llm(context_pack)
    
    # Create messages
    messages = prompt_template.format_messages(context_pack=formatted_context)
    
    # Invoke LLM
    response = await llm_manager.invoke(
        messages=messages,
        provider=provider,
        model=model
    )
    
    # Parse response
    try:
        result = json.loads(response)
        return result
    except json.JSONDecodeError:
        # Fallback parsing if JSON is malformed
        return {
            "findings": [],
            "summary": response,
            "confidence_score": 0.5,
            "error": "Failed to parse LLM response as JSON"
        }
```

### Fact Extraction with LLM

```python
async def extract_facts_with_llm(
    llm_manager: LLMManager,
    text: str,
    provider: str = "openai",
    model: str = "gpt-4-turbo"
) -> List[Dict[str, Any]]:
    """Extract facts from text using LLM"""
    
    # Get prompt template
    prompt_template = PromptTemplates.get_fact_extraction_prompt()
    
    # Create messages
    messages = prompt_template.format_messages(text=text)
    
    # Invoke LLM
    response = await llm_manager.invoke(
        messages=messages,
        provider=provider,
        model=model
    )
    
    # Parse response
    try:
        result = json.loads(response)
        return result.get("facts", [])
    except json.JSONDecodeError:
        return []
```

This LLM integration specification provides a comprehensive multi-provider system with configurable models, prompt engineering, and context optimization for the Architectural Submittal Reviewer.
