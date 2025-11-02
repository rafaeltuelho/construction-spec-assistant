# Evaluation Code Exclusion Specification

## Purpose

This document identifies code from the notebook that should **NOT** be included in the production backend and specifies where this experimental/evaluation code should live instead.

---

## Overview

The notebook contains significant evaluation and experimentation code using the **RAGAS framework** to assess retriever performance. This code was essential for selecting the best retrieval strategy during development but is **NOT part of the production workflow**.

---

## Code to Exclude from Backend

### 1. RAGAS Framework Integration

#### Notebook Location
- **Lines**: 1573+ (multiple cells)
- **Key Imports**: 
  ```python
  from ragas import evaluate
  from ragas.metrics import context_precision, context_recall, faithfulness, answer_relevancy
  from ragas.llms import LangchainLLMWrapper
  from ragas.embeddings import LangchainEmbeddingsWrapper
  from ragas.testset import TestsetGenerator
  from ragas.testset.synthesizers import (
      SingleHopSpecificQuerySynthesizer,
      MultiHopAbstractQuerySynthesizer,
  )
  ```

#### What It Does
- Generates synthetic test datasets for retriever evaluation
- Evaluates retriever performance using metrics:
  - **Context Precision**: How relevant are retrieved chunks?
  - **Context Recall**: Are all relevant chunks retrieved?
  - **Faithfulness**: Is the answer faithful to retrieved context?
  - **Answer Relevancy**: Is the answer relevant to the question?

#### Why Exclude
- **Not production functionality**: Only used for offline evaluation
- **Expensive**: Requires many LLM calls for evaluation
- **Experimental**: Used to compare retriever strategies
- **Dependencies**: Adds RAGAS as a dependency unnecessarily

---

### 2. Test Dataset Generation

#### Notebook Location
- **Lines**: 2838-2863
- **Key Functions**:
  ```python
  generator = TestsetGenerator(llm=generator_llm, embedding_model=generator_embeddings)
  
  sdg_ds = generator.generate_with_langchain_docs(
      spec_langchain_docs,
      testset_size=50,
      query_distribution=query_distribution
  )
  ```

#### What It Does
- Generates synthetic questions and ground truth answers from specification documents
- Creates test datasets for evaluating retrieval quality

#### Why Exclude
- **Offline activity**: Only needed during development
- **Not user-facing**: No API endpoint should trigger this
- **Resource-intensive**: Generates 50+ synthetic questions per document

---

### 3. Retriever Evaluation Pipeline

#### Notebook Location
- **Lines**: 3600-3829
- **Key Functions**:
  ```python
  def run_pipeline(chain_name, chain, submittal_dataset_item)
  def verdict_accuracy(df: list[dict]) -> float
  def evaluate_chain(chain_name: str, chain, golden_submittal_dataset: list[dict])
  def build_ragas_dataset(rows: List[Dict[str, Any]], include_reference=False) -> Dataset
  ```

#### What It Does
- Runs multiple retriever strategies (naive, BM25, ensemble, etc.)
- Compares their performance using RAGAS metrics
- Generates accuracy scores and visualizations

#### Why Exclude
- **Comparative analysis**: Only needed to select best retriever
- **Not production logic**: Backend should use the **chosen** retriever (ensemble)
- **Evaluation-specific**: Uses golden datasets that don't exist in production

---

### 4. Evaluation Results Visualization

#### Notebook Location
- **Lines**: 3840-3870
- **Key Code**:
  ```python
  print("📊 RAGAS Metrics Comparison Across Retrievers")
  # DataFrame comparison of retriever metrics
  # Matplotlib visualizations
  ```

#### What It Does
- Displays comparison tables of retriever performance
- Generates charts showing metric scores

#### Why Exclude
- **Analysis output**: Only for human review during development
- **No production use**: Backend doesn't need to visualize metrics

---

### 5. Golden Dataset Creation

#### Notebook Location
- Throughout evaluation cells
- **Key Concept**: `golden_submittal_dataset` with ground truth verdicts

#### What It Does
- Manually curated dataset with:
  - Specification facts
  - Submittal contexts
  - Ground truth verdicts (consistent/inconsistent/unclear)
- Used to measure retriever accuracy

#### Why Exclude
- **Test data**: Only for evaluation, not production
- **Static dataset**: Doesn't change during runtime
- **Evaluation-specific**: Production doesn't have "ground truth" verdicts

---

## Where Evaluation Code Should Live

### Recommended Structure

```
construction-spec-assistant/
├── backend/                    # Production backend (NO evaluation code)
│   └── app/
│       ├── api/
│       ├── services/
│       ├── models/
│       └── ...
│
├── evaluation/                 # Evaluation and experimentation
│   ├── README.md              # Evaluation documentation
│   ├── requirements.txt       # Evaluation-specific dependencies (ragas, etc.)
│   │
│   ├── datasets/              # Test datasets
│   │   ├── golden_submittal_dataset.json
│   │   └── synthetic_questions.json
│   │
│   ├── scripts/               # Evaluation scripts
│   │   ├── generate_test_data.py
│   │   ├── evaluate_retrievers.py
│   │   └── compare_metrics.py
│   │
│   ├── notebooks/             # Evaluation notebooks
│   │   ├── retriever_comparison.ipynb
│   │   └── metric_analysis.ipynb
│   │
│   └── results/               # Evaluation results
│       ├── retriever_metrics.csv
│       └── visualizations/
│
└── notebooks/                 # Original experimentation notebooks
    └── document_processing_new_pipeline.ipynb
```

---

## Evaluation Folder Contents

### 1. `evaluation/README.md`

Document the evaluation process:

```markdown
# Retriever Evaluation

This folder contains code and datasets for evaluating retriever performance.

## Purpose
- Compare different retrieval strategies (dense, sparse, ensemble)
- Measure retrieval quality using RAGAS metrics
- Select the best retriever for production

## Metrics
- **Context Precision**: Relevance of retrieved chunks
- **Context Recall**: Coverage of relevant information
- **Faithfulness**: Accuracy of generated answers
- **Answer Relevancy**: Relevance to query

## Results
The ensemble retriever (dense + sparse) was selected for production based on:
- Highest context recall (0.52)
- Balanced precision and relevancy
- Best overall performance across metrics

## Running Evaluation
```bash
cd evaluation
pip install -r requirements.txt
python scripts/evaluate_retrievers.py
```
```

---

### 2. `evaluation/requirements.txt`

Evaluation-specific dependencies:

```
ragas>=0.1.0
datasets>=2.14.0
matplotlib>=3.7.0
seaborn>=0.12.0
jupyter>=1.0.0
```

---

### 3. `evaluation/scripts/evaluate_retrievers.py`

Standalone script to evaluate retrievers:

```python
"""
Evaluate retriever performance using RAGAS metrics.

This script:
1. Loads golden test dataset
2. Runs multiple retriever strategies
3. Computes RAGAS metrics
4. Saves results to CSV
"""

import asyncio
from ragas import evaluate
from ragas.metrics import context_precision, context_recall, faithfulness, answer_relevancy
# ... rest of evaluation logic from notebook
```

---

### 4. `evaluation/datasets/golden_submittal_dataset.json`

Store test datasets:

```json
[
  {
    "spec_fact": {
      "entity": "Elevator",
      "attribute": "capacity",
      "value": "2500 lbs",
      "operator": ">="
    },
    "contexts": ["Submittal chunk 1", "Submittal chunk 2"],
    "ground_truth": "consistent",
    "question": "What is the elevator capacity?"
  }
]
```

---

## Backend Testing vs. Evaluation

### Backend Testing (INCLUDE in backend)

**Purpose**: Ensure production code works correctly

**Location**: `backend/tests/`

**Examples**:
- Unit tests for sectionizer, chunker, token counter
- Integration tests for services
- API endpoint tests
- Mock LLM responses for deterministic testing

**Tools**: pytest, FastAPI TestClient

---

### Evaluation (EXCLUDE from backend)

**Purpose**: Compare strategies and measure quality

**Location**: `evaluation/`

**Examples**:
- Retriever comparison using RAGAS
- Metric analysis and visualization
- Golden dataset generation
- Performance benchmarking

**Tools**: RAGAS, matplotlib, jupyter

---

## Migration Checklist

When migrating notebook code to backend:

- [ ] ✅ **Include**: Document processing (Docling, sectionizer, chunker)
- [ ] ✅ **Include**: Fact extraction (LLM, Pydantic models, unit normalization)
- [ ] ✅ **Include**: RAG retrievers (dense, sparse, ensemble)
- [ ] ✅ **Include**: LangGraph comparison agent
- [ ] ✅ **Include**: API endpoints and services
- [ ] ✅ **Include**: Database clients (MongoDB, Qdrant)
- [ ] ❌ **Exclude**: RAGAS framework integration
- [ ] ❌ **Exclude**: Test dataset generation
- [ ] ❌ **Exclude**: Retriever evaluation pipeline
- [ ] ❌ **Exclude**: Metric visualization
- [ ] ❌ **Exclude**: Golden dataset creation

---

## Key Takeaways

1. **Production backend should NOT include RAGAS or evaluation code**
2. **Evaluation code belongs in a separate `evaluation/` folder**
3. **Backend testing (pytest) is different from evaluation (RAGAS)**
4. **The ensemble retriever was selected based on evaluation results**
5. **Evaluation is an offline, one-time activity during development**

---

## Future Evaluation

If you need to re-evaluate retrievers in the future:

1. Use the `evaluation/` folder structure
2. Generate new test datasets if needed
3. Run evaluation scripts against production backend API
4. Compare new strategies against current ensemble retriever
5. Update production backend only if a better strategy is found

---

## Summary

**What to exclude from backend**:
- RAGAS framework and metrics
- Test dataset generation
- Retriever comparison logic
- Evaluation visualizations
- Golden datasets

**Where it should live**:
- `evaluation/` folder with separate dependencies
- Standalone scripts and notebooks
- Documented evaluation process
- Archived results for reference

**Why**:
- Keeps production backend lean and focused
- Separates concerns (production vs. experimentation)
- Avoids unnecessary dependencies
- Makes evaluation reproducible and maintainable

