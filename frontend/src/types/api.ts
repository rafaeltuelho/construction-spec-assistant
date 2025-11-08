// API Types for Construction Spec Assistant

export type DocumentType = 'specification' | 'submittal' | 'product_description';

export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type Verdict = 'consistent' | 'inconsistent' | 'unclear';

export type AnnotationType = 'disregard' | 'confirmed' | 'note';

// Configuration
export interface LLMInfoResponse {
  provider: string;
  model: string;
}

// Document Upload
export interface DocumentUploadRequest {
  file: File;
  document_type: DocumentType;
  use_ocr?: boolean;
  project_id?: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  document_type: DocumentType;
  status: DocumentStatus;
  created_at: string;
  processing_job_id: string;
  estimated_duration_seconds?: number;
}

// Document Status
export interface DocumentProgress {
  percentage: number;
  current_stage: string;
  stages: string[];
}

export interface DocumentMetadata {
  page_count: number;
  section_count: number;
  chunk_count: number;
  token_count: number;
}

export interface ProcessingStats {
  total_sections: number;
  sections_by_level: Record<string, number>;
  total_chunks: number;
  total_tokens: number;
  avg_chunk_tokens: number;
}

export interface DocumentStatusResponse {
  document_id: string;
  title: string;
  status: DocumentStatus;
  metadata: DocumentMetadata & {
    document_type: DocumentType;
    filename: string;
    file_size: number;
    mime_type: string;
    upload_timestamp: string;
    processing_timestamp?: string;
    used_ocr?: boolean;
    ocr_engine?: string;
    parse_time?: number;
  };
  processing_stats?: ProcessingStats;
  progress?: DocumentProgress;
  errors?: Array<{
    error_type: string;
    message: string;
    timestamp: string;
  }>;
  created_at: string;
  updated_at: string;
  processing_job_id?: string;
  estimated_duration_seconds?: number;
}

// Fact Extraction
export interface FactExtractionRequest {
  document_id: string;
  llm_model?: string;
  deduplicate?: boolean;
}

export interface FactExtractionResponse {
  document_id: string;
  extraction_job_id: string;
  status: JobStatus;
  started_at: string;
}

export interface FactExtractionProgress {
  percentage: number;
  chunks_processed: number;
  total_chunks: number;
}

export interface FactExtractionStatusResponse {
  job_id: string;
  document_id: string;
  status: JobStatus;
  progress?: FactExtractionProgress;
  started_at: string;
  completed_at?: string;
  facts_extracted?: number;
  facts_deduplicated?: number;
  error?: string;
}

// Comparison
export interface ComparisonRequest {
  spec_document_id: string;
  submittal_document_id: string;
  retrieval_strategy?: string;
  top_k?: number;
}

export interface ComparisonResponse {
  job_id: string;
  status: JobStatus;
  spec_document_id: string;
  submittal_document_id: string;
  total_facts: number;
  message: string;
}

export interface RetrievedChunk {
  chunk_id: string;
  content: string;
  relevance_score: number;
  page_start?: number | null;  // 0-indexed page number from Docling provenance
  page_end?: number | null;    // 0-indexed page number from Docling provenance
}

// Fact-related types
export interface Entity {
  type?: string | null;
  name?: string | null;
  manufacturer?: string | null;
}

export interface Attribute {
  raw: string;
  canonical?: string | null;
}

export interface Value {
  raw: string;
  type: string;
  num?: number | null;
  unit?: string | null;
  min?: number | null;
  max?: number | null;
}

export interface FactContext {
  doc_id: string;
  section_id: string;
  header_path: string[];
  source_span: string;
  confidence: number;
}

export interface Fact {
  id: string;
  entity: Entity;
  attribute: Attribute;
  value: Value;
  op: string;
  qualifiers?: Record<string, unknown> | null;
  context: FactContext;
}

export interface SpecFact {
  fact_id?: string;  // Added for context retrieval
  entity: Entity;
  attribute: Attribute;
  value: Value;
  op: string;
}

export interface DocumentSection {
  section_id: string;
  document_id: string;
  title: string;
  level: number;
  section_number?: string | null;
  content: string;
  parent_section_id?: string | null;
  order_index: number;
  header_path?: string[];      // Hierarchical path of section headers
  page_start?: number | null;  // 0-indexed page number from Docling provenance
  page_end?: number | null;    // 0-indexed page number from Docling provenance
}

export interface ComparisonResult {
  comparison_id: string;
  spec_fact: SpecFact;
  submittal_document_id: string;
  verdict: Verdict;
  confidence: number;
  submittal_evidence: string;
  reasoning: string;
  retrieved_chunks: RetrievedChunk[];
  retrieval_strategy: string;
  compared_at: string;
  user_annotation?: {
    comparison_id: string;
    annotation_type: AnnotationType;
    note_text?: string;
    annotated_by?: string;
    annotated_at: string;
  };
}

export interface ComparisonSummary {
  consistent: number;
  inconsistent: number;
  unclear: number;
}

export interface ComparisonStatusResponse {
  job_id: string;
  spec_document_id: string;
  submittal_document_id: string;
  total_facts: number;
  completed_facts: number;
  status: JobStatus;
  summary?: ComparisonSummary;
  comparisons: ComparisonResult[];
  created_at: string;
  completed_at?: string;
  error?: string;
}

// User Annotations
export interface UserAnnotation {
  comparison_id: string;
  annotation_type: AnnotationType;
  note_text?: string;
}

export interface SaveAnnotationsRequest {
  annotations: UserAnnotation[];
}

export interface SaveAnnotationsResponse {
  job_id: string;
  annotations_saved: number;
  message: string;
}

// Report Generation
export type ConclusionType =
  | 'reviewed'
  | 'reviewed_as_noted'
  | 'revise_and_resubmit'
  | 'rejected'
  | 'for_record_only';

export interface ReportAnnotation {
  comparison_id: string;
  note_text: string;
  annotated_at: string;
  spec_fact: SpecFact;
}

export interface ReportConclusion {
  conclusion_type: ConclusionType;
  conclusion_comment?: string;
  concluded_at: string;
  concluded_by?: string;
}

export interface ReportResponse {
  job_id: string;
  spec_document_id: string;
  submittal_document_id: string;
  annotations: ReportAnnotation[];
  report_generated_at: string;
  conclusion?: ReportConclusion;
}

export interface SaveReportRequest {
  conclusion_type: ConclusionType;
  conclusion_comment?: string;
}

export interface SaveReportResponse {
  success: boolean;
  message: string;
  conclusion?: ReportConclusion;
}

// Error Response
export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    timestamp: string;
    request_id?: string;
  };
}

