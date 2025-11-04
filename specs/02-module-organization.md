# Module Organization and Responsibilities

## Purpose

This document maps the experimental notebook code to the production backend structure, defining clear responsibilities for each module and providing guidance on code organization.

## Notebook-to-Backend Mapping

### 1. Token Counting (Lines 92-168)

**Notebook Location**: Cells with `count_tokens()`, `count_tokens_in_text()`, `analyze_document_token_limits()`

**Backend Location**: `backend/app/core/token_counter.py`

**Responsibilities**:
- Count tokens in text using tiktoken
- Analyze document token limits for LLM context windows
- Provide utilities for chunk size validation

**Key Functions**:
```python
def count_tokens(text: str, model: str = "gpt-4") -> int
def analyze_document_token_limits(doc: Document, model: str = "gpt-4") -> dict
def validate_chunk_size(chunk: str, max_tokens: int, model: str = "gpt-4") -> bool
```

---

### 2. Document Sectionizer (Lines 186-431)

**Notebook Location**: Cells with `Section`, `SectionChunk`, `sectionize_markdown()`, `chunk_sections()`

**Backend Location**: 
- Models: `backend/app/models/document.py`
- Logic: `backend/app/core/sectionizer.py` and `backend/app/core/chunker.py`

**Responsibilities**:

#### `models/document.py`:
- Define `Section` and `SectionChunk` Pydantic models
- Data validation and serialization

#### `core/sectionizer.py`:
- Parse Docling markdown into hierarchical sections
- CSI (Construction Specifications Institute) format awareness
- Section hierarchy management

#### `core/chunker.py`:
- Chunk sections with configurable overlap
- Respect token limits
- Maintain section context in chunks

**Key Classes/Functions**:
```python
# models/document.py
class Section(BaseModel):
    level: int
    title: str
    content: str
    children: List['Section']
    
class SectionChunk(BaseModel):
    section_path: str
    content: str
    chunk_index: int
    token_count: int

# core/sectionizer.py
def sectionize_markdown(markdown: str) -> List[Section]

# core/chunker.py
def chunk_sections(
    sections: List[Section],
    max_tokens: int = 500,
    overlap_tokens: int = 50
) -> List[SectionChunk]
```

---

### 3. Docling Integration (Lines 449-615)

**Notebook Location**: Cells with `create_docling_config()`, `parse_document_with_docling()`

**Backend Location**: `backend/app/core/docling_parser.py`

**Responsibilities**:
- Configure Docling pipeline with OCR options
- Parse PDF documents to markdown
- Handle OCR for scanned documents
- Extract document metadata

**Key Functions**:
```python
def create_docling_config(
    use_ocr: bool = True,
    ocr_engine: str = "easyocr"
) -> DocumentConverter

async def parse_document_with_docling(
    file_path: str,
    use_ocr: bool = True
) -> Tuple[str, dict]  # Returns (markdown, metadata)
```

---

### 4. Fact Extraction Models (Lines 779-1152)

**Notebook Location**: Cells with `Entity`, `Attribute`, `Value`, `Context`, `Fact` Pydantic models

**Backend Location**: `backend/app/models/fact.py`

**Responsibilities**:
- Define EAV (Entity-Attribute-Value) schema
- Fact validation and serialization
- Unit normalization integration

**Key Classes**:
```python
class Entity(BaseModel):
    raw: str
    normalized: Optional[str]
    type: Optional[str]

class Attribute(BaseModel):
    raw: str
    normalized: Optional[str]
    category: Optional[str]

class Value(BaseModel):
    raw: str
    normalized: Optional[str]
    unit: Optional[str]
    numeric: Optional[float]

class Context(BaseModel):
    source_document: str
    section_path: str
    chunk_id: str
    page_number: Optional[int]

class Fact(BaseModel):
    entity: Entity
    attribute: Attribute
    value: Value
    context: Context
    confidence: float
    extracted_at: datetime
```

---

### 4.1. Comparison Models

**Backend Location**: `backend/app/models/comparison.py`

**Responsibilities**:
- Define comparison result schema for MongoDB persistence
- Store complete comparison results with metadata
- Enable historical queries and cross-restart persistence

**Key Classes**:
```python
class ComparisonSummary(BaseModel):
    consistent: int
    inconsistent: int
    unclear: int

class RetrievedChunk(BaseModel):
    chunk_id: str
    content: str
    relevance_score: float

class ComparisonResult(BaseModel):
    comparison_id: str
    spec_fact: Dict[str, Any]
    submittal_document_id: str
    verdict: str  # consistent, inconsistent, unclear
    confidence: float
    submittal_evidence: str
    reasoning: str
    retrieved_chunks: List[RetrievedChunk]
    retrieval_strategy: str
    compared_at: datetime

class DocumentComparisonResult(BaseModel):
    job_id: str  # Used as MongoDB _id
    spec_document_id: str
    submittal_document_id: str
    total_facts: int
    completed_facts: int
    status: str  # pending, processing, completed, failed
    summary: Optional[ComparisonSummary]
    comparisons: List[ComparisonResult]
    error: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    retrieval_strategy: str
    top_k: int
```

**Persistence Strategy**:
- Results stored in MongoDB `document_comparison_results` collection
- In-memory cache for active jobs (`_document_jobs` dict)
- GET endpoint checks memory first, falls back to MongoDB
- Enables retrieval after server restarts

---

### 5. Fact Extraction Service (Lines 779-1152)

**Notebook Location**: Cells with `FACT_EXTRACTOR_SYSTEM_PROMPT`, `extract_facts_from_chunk()`, `normalize_units()`, `dedupe_facts()`, `harvest_facts_for_doc()`

**Backend Location**: `backend/app/services/fact_extraction.py`

**Responsibilities**:
- Orchestrate fact extraction from document chunks
- Call LLM for structured fact extraction
- Normalize units using pint
- Deduplicate extracted facts
- Store facts in MongoDB

**Key Functions**:
```python
async def extract_facts_from_chunk(
    chunk: SectionChunk,
    llm_client: ChatOpenAI
) -> List[Fact]

async def normalize_units(fact: Fact) -> Fact

async def dedupe_facts(facts: List[Fact]) -> List[Fact]

async def harvest_facts_for_doc(
    document_id: str,
    chunks: List[SectionChunk],
    llm_client: ChatOpenAI
) -> List[Fact]
```

---

### 6. Unit Normalization (Lines 779-1152)

**Notebook Location**: Cells using `pint` library for unit conversion

**Backend Location**: `backend/app/core/unit_normalizer.py`

**Responsibilities**:
- Parse unit strings
- Convert to standard units
- Handle construction-specific units (e.g., "inches", "feet", "PSI")

**Key Functions**:
```python
def normalize_unit(value_str: str, unit_str: str) -> Tuple[float, str]
def parse_value_with_unit(raw_value: str) -> Tuple[Optional[float], Optional[str]]
```

---

### 7. LLM Prompts (Lines 779-1152)

**Notebook Location**: `FACT_EXTRACTOR_SYSTEM_PROMPT` and other prompts

**Backend Location**: `backend/app/agents/prompts.py`

**Responsibilities**:
- Store all LLM prompts as constants
- Version control for prompts
- Prompt templates with variable substitution

**Key Constants**:
```python
FACT_EXTRACTOR_SYSTEM_PROMPT: str
COMPARISON_SYSTEM_PROMPT: str
QUERY_GENERATION_PROMPT: str
```

---

### 8. RAG Retrievers (Lines 1246+)

**Notebook Location**: Cells with Qdrant setup, ensemble retriever, BM25, dense retrieval

**Backend Location**: `backend/app/retrievers/`

**Responsibilities**:

#### `retrievers/base.py`:
- Base retriever interface
- Common retriever utilities

#### `retrievers/dense.py`:
- Dense vector retrieval using embeddings
- Qdrant integration

#### `retrievers/sparse.py`:
- BM25 sparse retrieval
- Keyword-based search

#### `retrievers/ensemble.py`:
- Combine dense + sparse retrievers
- Weighted scoring
- Reranking (Cohere)

#### `retrievers/query_builder.py`:
- Build queries from facts
- Generate dense and sparse query representations

**Key Classes**:
```python
class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(self, query: str, top_k: int) -> List[Document]

class DenseRetriever(BaseRetriever):
    async def retrieve(self, query: str, top_k: int) -> List[Document]

class SparseRetriever(BaseRetriever):
    async def retrieve(self, query: str, top_k: int) -> List[Document]

class EnsembleRetriever(BaseRetriever):
    async def retrieve(self, query: str, top_k: int) -> List[Document]
```

---

### 9. LangGraph Comparison Agent (Lines 1246+)

**Notebook Location**: Cells with LangGraph state machine, comparison workflow

**Backend Location**: `backend/app/agents/`

**Responsibilities**:

#### `agents/comparison_graph.py`:
- Define LangGraph state machine
- Orchestrate comparison workflow
- State transitions

#### `agents/nodes.py`:
- Individual agent nodes (retrieve, compare, validate)
- Node logic implementation

**Key Components**:
```python
class ComparisonState(TypedDict):
    spec_fact: dict
    query: str
    retrieved_docs: List[Document]
    result: dict
    
def create_comparison_graph() -> StateGraph:
    # Build LangGraph state machine
    pass

# Node functions
async def retrieve_node(state: ComparisonState) -> ComparisonState
async def compare_node(state: ComparisonState) -> ComparisonState
async def validate_node(state: ComparisonState) -> ComparisonState
```

---

### 10. Database Clients (Throughout notebook)

**Notebook Location**: MongoDB and Qdrant usage throughout

**Backend Location**: `backend/app/db/`

**Responsibilities**:

#### `db/mongodb.py`:
- MongoDB connection management
- CRUD operations for facts, documents, and comparison results
- Async operations
- Persistence for job results

#### `db/qdrant.py`:
- Qdrant client setup
- Vector indexing
- Hybrid search configuration

**Key Functions**:
```python
# mongodb.py
async def get_mongodb_client() -> AsyncIOMotorClient
async def store_fact(fact: Fact) -> str
async def get_facts_by_document(document_id: str) -> List[Fact]
async def store_document_comparison_result(result: DocumentComparisonResult) -> str
async def get_document_comparison_result(job_id: str) -> Optional[DocumentComparisonResult]
async def get_document_comparison_results_by_spec(spec_document_id: str) -> List[DocumentComparisonResult]
async def get_document_comparison_results_by_submittal(submittal_document_id: str) -> List[DocumentComparisonResult]

# qdrant.py
async def get_qdrant_client() -> QdrantClient
async def index_chunks(chunks: List[SectionChunk], collection_name: str)
async def search_vectors(query: str, collection_name: str, top_k: int) -> List[Document]
```

**MongoDB Collections**:
- `documents`: Document metadata and processing status
- `sections`: Document sections (hierarchical structure)
- `chunks`: Document chunks for retrieval
- `facts`: Extracted facts (EAV schema)
- `document_comparison_results`: Comparison job results (persistent storage)

---

### 11. Document Processing Service (Orchestration)

**Notebook Location**: Cells orchestrating the full pipeline

**Backend Location**: `backend/app/services/document_processing.py`

**Responsibilities**:
- Orchestrate end-to-end document processing
- Call Docling parser
- Call sectionizer and chunker
- Store results

**Key Functions**:
```python
async def process_document(
    file_path: str,
    document_id: str,
    use_ocr: bool = True
) -> dict:
    # 1. Parse with Docling
    # 2. Sectionize markdown
    # 3. Chunk sections
    # 4. Store in database
    # 5. Return processing result
    pass
```

---

### 12. Comparison Service (Orchestration)

**Notebook Location**: Cells running comparison workflow

**Backend Location**: `backend/app/services/comparison_agent.py`

**Responsibilities**:
- Orchestrate comparison workflow
- Build queries from spec facts
- Call LangGraph agent
- Return comparison results

**Key Functions**:
```python
async def compare_spec_to_submittal(
    spec_fact: dict,
    submittal_document_id: str
) -> dict:
    # 1. Build query from spec fact
    # 2. Invoke LangGraph comparison agent
    # 3. Return verdict and evidence
    pass
```

---

## Module Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                           │
│  (documents.py, facts.py, comparison.py)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                          │
│  (document_processing.py, fact_extraction.py,               │
│   comparison_agent.py, retrieval.py)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌────────────┐  ┌────────────┐  ┌────────────┐
│   Models   │  │    Core    │  │   Agents   │
│  (Pydantic)│  │ (Utilities)│  │ (LangGraph)│
└────────────┘  └────────────┘  └────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                     │
│  (db/, retrievers/, external APIs)                          │
└─────────────────────────────────────────────────────────────┘
```

## Import Guidelines

### Allowed Imports
- **API → Services**: ✅ API endpoints can import services
- **Services → Models**: ✅ Services can import domain models
- **Services → Core**: ✅ Services can use core utilities
- **Services → Agents**: ✅ Services can orchestrate agents
- **Services → DB**: ✅ Services can access database layer
- **Agents → Retrievers**: ✅ Agents can use retrievers
- **Core → Models**: ✅ Core utilities can use models

### Prohibited Imports
- **Models → Services**: ❌ Models should not import services
- **Core → Services**: ❌ Core utilities should not import services
- **DB → Services**: ❌ Database layer should not import services
- **API → DB**: ❌ API should not directly access database (use services)

## Testing Strategy

### Unit Tests
- **Core utilities**: Test sectionizer, chunker, token counter, unit normalizer in isolation
- **Models**: Test Pydantic validation and serialization
- **Retrievers**: Test retrieval logic with mock data

### Integration Tests
- **Services**: Test service orchestration with mocked dependencies
- **Agents**: Test LangGraph workflows with mock LLM responses

### API Tests
- **Endpoints**: Test API contracts with FastAPI TestClient
- **End-to-end**: Test full workflows from API to database

## Next Steps

Refer to the following specification documents for detailed implementation:

1. **03-api-design.md**: API endpoint specifications
2. **04-document-processing-pipeline.md**: Document processing details
3. **05-fact-extraction.md**: Fact extraction implementation
4. **06-rag-and-agents.md**: RAG and agent architecture

