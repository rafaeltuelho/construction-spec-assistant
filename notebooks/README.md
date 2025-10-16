# Document Processing Prototype

This directory contains a Jupyter notebook for incremental development and testing of the document processing pipeline for construction specifications.

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r notebooks/requirements.txt
   ```

2. **Launch Jupyter**:
   ```bash
   jupyter notebook notebooks/document_processing_prototype.ipynb
   ```

3. **Run Cells Sequentially**:
   - Cell 1: Environment setup
   - Cell 2: Docling configuration  
   - Cell 3: File loading and metadata
   - Cell 4: Document parsing
   - Cell 5: Results visualization

## Notebook Structure

### Completed Phases ✅
- **Environment Setup**: Dependencies and path configuration
- **Docling Configuration**: Optimized for construction documents
- **File Loading**: PDF metadata extraction with PyMuPDF
- **Document Parsing**: Full document processing with Docling
- **Results Visualization**: Summary display and JSON export

### Ready for Implementation 🔄
- **CSI Classification**: Extract and validate CSI division codes
- **Fact Extraction**: Parse specifications into structured facts
- **Passage Chunking**: Prepare text for search and retrieval

## Sample Data

The notebook processes three sample construction documents:
- `Spec 14 24 00 - Hydraulic Elevators.pdf` - CSI specification
- `Architectural Drawings.pdf` - Large format CAD drawings  
- `Submittal and Product Description.pdf` - Manufacturer submittal

## Output Files

Parsing results are saved to `notebooks/parsing_results/`:
- Individual document JSON files
- Processing summary with timing data
- Structured data ready for further processing

## Development Workflow

1. **Incremental Development**: Add one processing phase at a time
2. **Validation**: Check results before proceeding to next phase
3. **Iteration**: Modify and rerun cells as needed
4. **Integration**: Extract working code for backend implementation

## Troubleshooting

- **Import Errors**: Ensure all dependencies are installed
- **File Not Found**: Verify `data/` directory contains PDF files
- **Memory Issues**: Process documents individually for large files
- **Parsing Failures**: Check PDF compatibility with Docling

This notebook serves as a development sandbox before implementing the full backend system.
