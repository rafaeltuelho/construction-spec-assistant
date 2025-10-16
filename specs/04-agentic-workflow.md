# Agentic Workflow Specification

## Overview

This specification defines the agentic workflow system using LangGraph to orchestrate the document comparison process, inspired by the LangGraph Open Deep Research project architecture.

## LangGraph Workflow Architecture

### Installation and Dependencies

```python
# requirements.txt
langgraph==0.0.62
langchain==0.1.0
langchain-core==0.1.0
langchain-openai==0.0.5
langchain-anthropic==0.1.0
pydantic==2.5.0
```

### Workflow State Definition

```python
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class WorkflowStatus(str, Enum):
    INITIALIZED = "initialized"
    DOCUMENTS_RETRIEVED = "documents_retrieved"
    CONTEXT_BUILT = "context_built"
    COMPARISON_COMPLETED = "comparison_completed"
    VERIFICATION_COMPLETED = "verification_completed"
    REVIEW_COMPLETED = "review_completed"
    FAILED = "failed"

class Finding(BaseModel):
    """Individual finding from document comparison"""
    id: str
    finding_type: str  # discrepancy, consistent, missing, additional, unclear
    confidence: float
    title: str
    description: str
    recommendation: Optional[str] = None
    specification_facts: List[str] = Field(default_factory=list)
    submittal_facts: List[str] = Field(default_factory=list)
    supporting_passages: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)

class ReviewResult(BaseModel):
    """Complete review result"""
    review_id: str
    status: WorkflowStatus
    findings: List[Finding] = Field(default_factory=list)
    summary: Optional[str] = None
    confidence_score: float = 0.0
    processing_time_seconds: Optional[float] = None
    error_message: Optional[str] = None

class WorkflowState(TypedDict):
    """State object for the LangGraph workflow"""
    
    # Input parameters
    specification_document_id: str
    submittal_document_id: str
    review_scope: List[str]  # CSI divisions
    llm_provider: str
    llm_model: str
    
    # Workflow state
    status: WorkflowStatus
    current_step: str
    error_message: Optional[str]
    
    # Messages for LLM communication
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Retrieved data
    specification_passages: List[Dict[str, Any]]
    submittal_passages: List[Dict[str, Any]]
    facts: List[Dict[str, Any]]
    
    # Context pack
    context_pack: Optional[Dict[str, Any]]
    context_pack_tokens: int
    
    # LLM results
    comparison_result: Optional[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    
    # Final results
    findings: List[Finding]
    review_result: Optional[ReviewResult]
    
    # Metadata
    start_time: datetime
    end_time: Optional[datetime]
    processing_times: Dict[str, float]
```

## Agent Definitions

### 1. Ingestor Agent

```python
from langchain_core.messages import SystemMessage
from typing import Dict, Any

class IngestorAgent:
    """Agent responsible for document ingestion and initial processing"""
    
    def __init__(self, document_processor, storage_manager):
        self.document_processor = document_processor
        self.storage_manager = storage_manager
    
    async def process_document(
        self, 
        state: WorkflowState
    ) -> Dict[str, Any]:
        """
        Process uploaded document and extract structured content
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with document processing results
        """
        try:
            # This would typically be called during document upload
            # For workflow purposes, we assume documents are already processed
            # and stored in the database
            
            return {
                "status": WorkflowStatus.INITIALIZED,
                "current_step": "document_processing_complete"
            }
            
        except Exception as e:
            return {
                "status": WorkflowStatus.FAILED,
                "error_message": f"Document processing failed: {str(e)}",
                "current_step": "document_processing_failed"
            }
```

### 2. Retriever Agent

```python
class RetrieverAgent:
    """Agent responsible for retrieving relevant passages and facts"""
    
    def __init__(self, hybrid_retrieval_engine, facts_manager):
        self.retrieval_engine = hybrid_retrieval_engine
        self.facts_manager = facts_manager
    
    async def retrieve_relevant_content(
        self, 
        state: WorkflowState
    ) -> Dict[str, Any]:
        """
        Retrieve relevant passages and facts for comparison
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with retrieved content
        """
        try:
            import time
            start_time = time.time()
            
            # Build search queries based on review scope
            queries = self._build_search_queries(state["review_scope"])
            
            # Retrieve passages for each query
            spec_passages = []
            submittal_passages = []
            
            for query in queries:
                spec_results, submittal_results = await self.retrieval_engine.search_for_comparison(
                    specification_query=query,
                    submittal_query=query,
                    csi_divisions=state["review_scope"]
                )
                spec_passages.extend(spec_results)
                submittal_passages.extend(submittal_results)
            
            # Retrieve relevant facts
            facts = await self.facts_manager.get_related_facts(
                specification_document_id=state["specification_document_id"],
                submittal_document_id=state["submittal_document_id"],
                topics=state["review_scope"]
            )
            
            processing_time = time.time() - start_time
            
            return {
                "specification_passages": spec_passages,
                "submittal_passages": submittal_passages,
                "facts": facts,
                "status": WorkflowStatus.DOCUMENTS_RETRIEVED,
                "current_step": "content_retrieved",
                "processing_times": {
                    "retrieval_time": processing_time
                }
            }
            
        except Exception as e:
            return {
                "status": WorkflowStatus.FAILED,
                "error_message": f"Content retrieval failed: {str(e)}",
                "current_step": "retrieval_failed"
            }
    
    def _build_search_queries(self, review_scope: List[str]) -> List[str]:
        """Build search queries based on review scope"""
        queries = []
        
        # General queries for each CSI division
        for division in review_scope:
            queries.append(f"CSI division {division} specifications requirements")
            queries.append(f"{division} materials installation methods")
            queries.append(f"{division} testing quality control")
        
        # Add general construction queries
        queries.extend([
            "material specifications properties",
            "installation requirements procedures",
            "testing methods standards",
            "quality control inspection"
        ])
        
        return queries
```

### 3. Context Builder Agent

```python
class ContextBuilderAgent:
    """Agent responsible for building context packs for LLM processing"""
    
    def __init__(self, context_pack_builder):
        self.context_pack_builder = context_pack_builder
    
    async def build_context_pack(
        self, 
        state: WorkflowState
    ) -> Dict[str, Any]:
        """
        Build context pack from retrieved content
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with context pack
        """
        try:
            import time
            start_time = time.time()
            
            # Create comparison query
            query = self._create_comparison_query(state)
            
            # Build context pack
            context_pack = await self.context_pack_builder.build_context_pack(
                specification_passages=state["specification_passages"],
                submittal_passages=state["submittal_passages"],
                facts=state["facts"],
                query=query
            )
            
            # Format for LLM
            formatted_context = await self.context_pack_builder.format_context_pack_for_llm(
                context_pack
            )
            
            processing_time = time.time() - start_time
            
            return {
                "context_pack": context_pack,
                "context_pack_tokens": context_pack["metadata"]["total_tokens"],
                "status": WorkflowStatus.CONTEXT_BUILT,
                "current_step": "context_built",
                "messages": [HumanMessage(content=formatted_context)],
                "processing_times": {
                    **state.get("processing_times", {}),
                    "context_build_time": processing_time
                }
            }
            
        except Exception as e:
            return {
                "status": WorkflowStatus.FAILED,
                "error_message": f"Context pack building failed: {str(e)}",
                "current_step": "context_build_failed"
            }
    
    def _create_comparison_query(self, state: WorkflowState) -> str:
        """Create comparison query based on review scope"""
        scope_text = ", ".join(state["review_scope"]) if state["review_scope"] else "all sections"
        
        return f"""
        Compare the specification requirements with the contractor submittal for CSI divisions: {scope_text}.
        
        Please identify:
        1. Any discrepancies between what was specified and what was submitted
        2. Missing information in the submittal
        3. Additional information in the submittal not in the specification
        4. Areas where the submittal is consistent with the specification
        5. Any unclear or ambiguous information that needs clarification
        
        For each finding, provide:
        - A clear title describing the issue
        - A detailed description of the discrepancy or finding
        - A recommendation for resolution
        - Confidence level (0.0 to 1.0)
        - Specific citations from the documents
        """
```

### 4. Comparator Agent

```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

class ComparisonResult(BaseModel):
    """Structured output for comparison results"""
    findings: List[Dict[str, Any]] = Field(description="List of comparison findings")
    summary: str = Field(description="Overall summary of the comparison")
    confidence_score: float = Field(description="Overall confidence in the comparison (0.0 to 1.0)")

class ComparatorAgent:
    """Agent responsible for performing document comparison using LLM"""
    
    def __init__(self, llm_provider_manager):
        self.llm_manager = llm_provider_manager
    
    async def compare_documents(
        self, 
        state: WorkflowState
    ) -> Dict[str, Any]:
        """
        Compare documents using LLM
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with comparison results
        """
        try:
            import time
            start_time = time.time()
            
            # Get LLM instance
            llm = await self.llm_manager.get_llm(
                provider=state["llm_provider"],
                model=state["llm_model"]
            )
            
            # Create comparison prompt
            system_prompt = self._create_system_prompt()
            user_prompt = state["messages"][-1].content  # Last message contains context
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", user_prompt)
            ])
            
            # Create output parser
            output_parser = JsonOutputParser(pydantic_object=ComparisonResult)
            
            # Create chain
            chain = prompt | llm | output_parser
            
            # Perform comparison
            result = await chain.ainvoke({})
            
            # Convert to Finding objects
            findings = []
            for finding_data in result["findings"]:
                finding = Finding(
                    id=f"finding_{len(findings) + 1}",
                    finding_type=finding_data.get("finding_type", "unclear"),
                    confidence=finding_data.get("confidence", 0.5),
                    title=finding_data.get("title", ""),
                    description=finding_data.get("description", ""),
                    recommendation=finding_data.get("recommendation"),
                    citations=finding_data.get("citations", [])
                )
                findings.append(finding)
            
            processing_time = time.time() - start_time
            
            return {
                "comparison_result": result,
                "findings": findings,
                "status": WorkflowStatus.COMPARISON_COMPLETED,
                "current_step": "comparison_completed",
                "messages": state["messages"] + [AIMessage(content=str(result))],
                "processing_times": {
                    **state.get("processing_times", {}),
                    "comparison_time": processing_time
                }
            }
            
        except Exception as e:
            return {
                "status": WorkflowStatus.FAILED,
                "error_message": f"Document comparison failed: {str(e)}",
                "current_step": "comparison_failed"
            }
    
    def _create_system_prompt(self) -> str:
        """Create system prompt for document comparison"""
        return """
        You are an expert construction architect reviewing construction documents. 
        Your task is to compare specification requirements with contractor submittals 
        and identify any discrepancies, inconsistencies, or issues.
        
        Please analyze the provided documents and return your findings in the following JSON format:
        {
            "findings": [
                {
                    "finding_type": "discrepancy|consistent|missing|additional|unclear",
                    "confidence": 0.0-1.0,
                    "title": "Brief title of the finding",
                    "description": "Detailed description of the finding",
                    "recommendation": "Recommended action to resolve the issue",
                    "citations": [
                        {
                            "source": "specification|submittal",
                            "page": 1,
                            "section": "2.1.A",
                            "text": "Exact quote from document"
                        }
                    ]
                }
            ],
            "summary": "Overall summary of the comparison",
            "confidence_score": 0.0-1.0
        }
        
        Focus on:
        1. Technical accuracy and compliance
        2. Material specifications and properties
        3. Installation requirements and procedures
        4. Testing and quality control requirements
        5. Safety and performance standards
        
        Be thorough but concise. Provide specific citations for all findings.
        """
```

### 5. Verifier Agent

```python
class VerifierAgent:
    """Agent responsible for verifying comparison results (optional second pass)"""
    
    def __init__(self, llm_provider_manager):
        self.llm_manager = llm_provider_manager
    
    async def verify_findings(
        self, 
        state: WorkflowState
    ) -> Dict[str, Any]:
        """
        Verify comparison findings with a second LLM pass
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with verification results
        """
        try:
            import time
            start_time = time.time()
            
            # Skip verification if not enabled or no findings
            if not state.get("findings") or len(state["findings"]) == 0:
                return {
                    "verification_result": {"verified": True, "notes": "No findings to verify"},
                    "status": WorkflowStatus.VERIFICATION_COMPLETED,
                    "current_step": "verification_skipped"
                }
            
            # Get different LLM for verification
            verification_llm = await self.llm_manager.get_llm(
                provider="anthropic",  # Use different provider for verification
                model="claude-3-sonnet-20240229"
            )
            
            # Create verification prompt
            verification_prompt = self._create_verification_prompt(state["findings"])
            
            # Perform verification
            verification_result = await verification_llm.ainvoke(verification_prompt)
            
            processing_time = time.time() - start_time
            
            return {
                "verification_result": verification_result.content,
                "status": WorkflowStatus.VERIFICATION_COMPLETED,
                "current_step": "verification_completed",
                "processing_times": {
                    **state.get("processing_times", {}),
                    "verification_time": processing_time
                }
            }
            
        except Exception as e:
            return {
                "status": WorkflowStatus.FAILED,
                "error_message": f"Verification failed: {str(e)}",
                "current_step": "verification_failed"
            }
    
    def _create_verification_prompt(self, findings: List[Finding]) -> str:
        """Create verification prompt for findings"""
        findings_text = "\n\n".join([
            f"Finding {i+1}: {finding.title}\n"
            f"Type: {finding.finding_type}\n"
            f"Description: {finding.description}\n"
            f"Confidence: {finding.confidence}\n"
            f"Recommendation: {finding.recommendation or 'None'}"
            for i, finding in enumerate(findings)
        ])
        
        return f"""
        Please verify the following findings from a construction document comparison:
        
        {findings_text}
        
        For each finding, please:
        1. Confirm if the finding is accurate and well-supported
        2. Suggest any improvements to the description or recommendation
        3. Rate the overall quality of the analysis (1-10)
        4. Identify any missing issues that should have been found
        
        Provide your verification in a clear, structured format.
        """
```

### 6. Reviewer Agent

```python
class ReviewerAgent:
    """Agent responsible for final review and result compilation"""
    
    async def compile_review_result(
        self, 
        state: WorkflowState
    ) -> Dict[str, Any]:
        """
        Compile final review result
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with final review result
        """
        try:
            import time
            end_time = time.time()
            
            # Calculate total processing time
            total_time = end_time - state["start_time"].timestamp()
            
            # Create review result
            review_result = ReviewResult(
                review_id=f"review_{state['specification_document_id']}_{state['submittal_document_id']}",
                status=WorkflowStatus.REVIEW_COMPLETED,
                findings=state["findings"],
                summary=state["comparison_result"].get("summary", "") if state.get("comparison_result") else "",
                confidence_score=state["comparison_result"].get("confidence_score", 0.0) if state.get("comparison_result") else 0.0,
                processing_time_seconds=total_time
            )
            
            return {
                "review_result": review_result,
                "status": WorkflowStatus.REVIEW_COMPLETED,
                "current_step": "review_completed",
                "end_time": datetime.fromtimestamp(end_time),
                "processing_times": {
                    **state.get("processing_times", {}),
                    "total_time": total_time
                }
            }
            
        except Exception as e:
            return {
                "status": WorkflowStatus.FAILED,
                "error_message": f"Review compilation failed: {str(e)}",
                "current_step": "review_compilation_failed"
            }
```

## Workflow Graph Definition

### LangGraph Workflow Implementation

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

class DocumentComparisonWorkflow:
    """Main workflow for document comparison using LangGraph"""
    
    def __init__(
        self,
        retriever_agent: RetrieverAgent,
        context_builder_agent: ContextBuilderAgent,
        comparator_agent: ComparatorAgent,
        verifier_agent: VerifierAgent,
        reviewer_agent: ReviewerAgent
    ):
        self.retriever_agent = retriever_agent
        self.context_builder_agent = context_builder_agent
        self.comparator_agent = comparator_agent
        self.verifier_agent = verifier_agent
        self.reviewer_agent = reviewer_agent
        
        # Create workflow graph
        self.graph = self._create_workflow_graph()
    
    def _create_workflow_graph(self) -> StateGraph:
        """Create the LangGraph workflow"""
        
        # Create state graph
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("retriever", self.retriever_agent.retrieve_relevant_content)
        workflow.add_node("context_builder", self.context_builder_agent.build_context_pack)
        workflow.add_node("comparator", self.comparator_agent.compare_documents)
        workflow.add_node("verifier", self.verifier_agent.verify_findings)
        workflow.add_node("reviewer", self.reviewer_agent.compile_review_result)
        
        # Define workflow edges
        workflow.set_entry_point("retriever")
        
        workflow.add_edge("retriever", "context_builder")
        workflow.add_edge("context_builder", "comparator")
        
        # Conditional edge for verification
        workflow.add_conditional_edges(
            "comparator",
            self._should_verify,
            {
                "verify": "verifier",
                "skip_verification": "reviewer"
            }
        )
        
        workflow.add_edge("verifier", "reviewer")
        workflow.add_edge("reviewer", END)
        
        # Add error handling
        workflow.add_edge("retriever", END)  # Will be handled by error checking
        workflow.add_edge("context_builder", END)  # Will be handled by error checking
        workflow.add_edge("comparator", END)  # Will be handled by error checking
        workflow.add_edge("verifier", END)  # Will be handled by error checking
        
        return workflow.compile(checkpointer=MemorySaver())
    
    def _should_verify(self, state: WorkflowState) -> str:
        """Determine if verification step should be performed"""
        # Skip verification if workflow failed or no findings
        if state.get("status") == WorkflowStatus.FAILED:
            return "skip_verification"
        
        if not state.get("findings") or len(state["findings"]) == 0:
            return "skip_verification"
        
        # Skip verification for low-confidence findings only
        low_confidence_count = sum(1 for f in state["findings"] if f.confidence < 0.7)
        if low_confidence_count == 0:
            return "skip_verification"
        
        return "verify"
    
    async def run_workflow(
        self,
        specification_document_id: str,
        submittal_document_id: str,
        review_scope: List[str] = None,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4-turbo"
    ) -> ReviewResult:
        """
        Run the document comparison workflow
        
        Args:
            specification_document_id: ID of specification document
            submittal_document_id: ID of submittal document
            review_scope: List of CSI divisions to review
            llm_provider: LLM provider to use
            llm_model: LLM model to use
            
        Returns:
            Review result with findings
        """
        # Initialize workflow state
        initial_state = WorkflowState(
            specification_document_id=specification_document_id,
            submittal_document_id=submittal_document_id,
            review_scope=review_scope or [],
            llm_provider=llm_provider,
            llm_model=llm_model,
            status=WorkflowStatus.INITIALIZED,
            current_step="initialized",
            messages=[],
            specification_passages=[],
            submittal_passages=[],
            facts=[],
            context_pack=None,
            context_pack_tokens=0,
            comparison_result=None,
            verification_result=None,
            findings=[],
            review_result=None,
            start_time=datetime.now(),
            end_time=None,
            processing_times={}
        )
        
        # Run workflow
        final_state = await self.graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": f"review_{specification_document_id}_{submittal_document_id}"}}
        )
        
        # Return final result
        if final_state.get("review_result"):
            return final_state["review_result"]
        else:
            # Return error result
            return ReviewResult(
                review_id=f"review_{specification_document_id}_{submittal_document_id}",
                status=WorkflowStatus.FAILED,
                error_message=final_state.get("error_message", "Unknown error"),
                processing_time_seconds=final_state.get("processing_times", {}).get("total_time", 0)
            )
```

## Error Handling and Recovery

### Workflow Error Handling

```python
from typing import Callable, Any

class WorkflowErrorHandler:
    """Handle errors and recovery in the workflow"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
    
    async def execute_with_retry(
        self,
        func: Callable,
        state: WorkflowState,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Execute function with retry logic
        
        Args:
            func: Function to execute
            state: Current workflow state
            retry_count: Current retry count
            
        Returns:
            Function result or error state
        """
        try:
            return await func(state)
        except Exception as e:
            if retry_count < self.max_retries:
                # Log error and retry
                print(f"Error in workflow step: {e}. Retrying... ({retry_count + 1}/{self.max_retries})")
                
                # Add delay before retry
                import asyncio
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                
                return await self.execute_with_retry(func, state, retry_count + 1)
            else:
                # Max retries exceeded, return error state
                return {
                    "status": WorkflowStatus.FAILED,
                    "error_message": f"Max retries exceeded. Last error: {str(e)}",
                    "current_step": "max_retries_exceeded"
                }
    
    def should_continue_workflow(self, state: WorkflowState) -> bool:
        """Determine if workflow should continue after error"""
        if state.get("status") == WorkflowStatus.FAILED:
            return False
        
        # Check for critical errors that should stop the workflow
        critical_errors = [
            "document_not_found",
            "llm_provider_unavailable",
            "database_connection_failed"
        ]
        
        error_message = state.get("error_message", "").lower()
        for critical_error in critical_errors:
            if critical_error in error_message:
                return False
        
        return True
```

## Workflow Monitoring and Metrics

### Performance Monitoring

```python
import time
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class WorkflowMetrics:
    """Metrics for workflow performance monitoring"""
    workflow_id: str
    start_time: float
    end_time: Optional[float] = None
    step_times: Dict[str, float] = None
    total_tokens_used: int = 0
    llm_calls: int = 0
    retrieval_queries: int = 0
    error_count: int = 0
    
    def __post_init__(self):
        if self.step_times is None:
            self.step_times = {}
    
    @property
    def total_time(self) -> float:
        """Calculate total workflow time"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def add_step_time(self, step_name: str, duration: float):
        """Add timing for a workflow step"""
        self.step_times[step_name] = duration
    
    def increment_llm_calls(self):
        """Increment LLM call counter"""
        self.llm_calls += 1
    
    def increment_retrieval_queries(self):
        """Increment retrieval query counter"""
        self.retrieval_queries += 1
    
    def increment_errors(self):
        """Increment error counter"""
        self.error_count += 1

class WorkflowMonitor:
    """Monitor workflow execution and collect metrics"""
    
    def __init__(self):
        self.active_workflows: Dict[str, WorkflowMetrics] = {}
    
    def start_workflow(self, workflow_id: str) -> WorkflowMetrics:
        """Start monitoring a workflow"""
        metrics = WorkflowMetrics(
            workflow_id=workflow_id,
            start_time=time.time()
        )
        self.active_workflows[workflow_id] = metrics
        return metrics
    
    def end_workflow(self, workflow_id: str):
        """End monitoring a workflow"""
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id].end_time = time.time()
    
    def get_metrics(self, workflow_id: str) -> Optional[WorkflowMetrics]:
        """Get metrics for a workflow"""
        return self.active_workflows.get(workflow_id)
    
    def get_all_metrics(self) -> Dict[str, WorkflowMetrics]:
        """Get all workflow metrics"""
        return self.active_workflows.copy()
```

This agentic workflow specification provides a comprehensive LangGraph-based system for orchestrating document comparison tasks with robust error handling, monitoring, and recovery mechanisms.
