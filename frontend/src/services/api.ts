import type {
  DocumentUploadResponse,
  DocumentStatusResponse,
  FactExtractionRequest,
  FactExtractionResponse,
  FactExtractionStatusResponse,
  ComparisonRequest,
  ComparisonResponse,
  ComparisonStatusResponse,
  SaveAnnotationsRequest,
  SaveAnnotationsResponse,
  ReportResponse,
  SaveReportRequest,
  SaveReportResponse,
  ErrorResponse,
  Fact,
  DocumentSection,
  LLMInfoResponse,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

class ApiError extends Error {
  statusCode: number;
  errorResponse?: ErrorResponse;

  constructor(
    message: string,
    statusCode: number,
    errorResponse?: ErrorResponse
  ) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.errorResponse = errorResponse;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData: ErrorResponse | undefined;
    try {
      errorData = await response.json();
    } catch {
      // If JSON parsing fails, use status text
    }
    
    const message = errorData?.error?.message || response.statusText || 'An error occurred';
    throw new ApiError(message, response.status, errorData);
  }
  
  return response.json();
}

// Document Upload
export async function uploadDocument(
  file: File,
  documentType: 'specification' | 'submittal' | 'product_description',
  useOcr: boolean = true
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', documentType);
  formData.append('use_ocr', String(useOcr));
  
  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: 'POST',
    body: formData,
  });
  
  return handleResponse<DocumentUploadResponse>(response);
}

// Document Status
export async function getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`);
  return handleResponse<DocumentStatusResponse>(response);
}

// Fact Extraction
export async function extractFacts(request: FactExtractionRequest): Promise<FactExtractionResponse> {
  const response = await fetch(`${API_BASE_URL}/facts/extract`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  return handleResponse<FactExtractionResponse>(response);
}

export async function getFactExtractionStatus(jobId: string): Promise<FactExtractionStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/facts/extraction/${jobId}`);
  return handleResponse<FactExtractionStatusResponse>(response);
}

// Get individual fact by ID
export async function getFactById(factId: string): Promise<Fact> {
  const response = await fetch(`${API_BASE_URL}/facts/${factId}`);
  return handleResponse<Fact>(response);
}

// Get individual section by ID
export async function getSectionById(sectionId: string): Promise<DocumentSection> {
  const response = await fetch(`${API_BASE_URL}/documents/sections/${sectionId}`);
  return handleResponse<DocumentSection>(response);
}

// Comparison
export async function compareDocuments(request: ComparisonRequest): Promise<ComparisonResponse> {
  const response = await fetch(`${API_BASE_URL}/comparison/compare-document`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  return handleResponse<ComparisonResponse>(response);
}

export async function getComparisonStatus(
  jobId: string,
  limit?: number,
  offset?: number,
  verdictFilter?: 'consistent' | 'inconsistent' | 'unclear'
): Promise<ComparisonStatusResponse> {
  const params = new URLSearchParams();
  if (limit) params.append('limit', String(limit));
  if (offset) params.append('offset', String(offset));
  if (verdictFilter) params.append('verdict_filter', verdictFilter);
  
  const queryString = params.toString();
  const url = `${API_BASE_URL}/comparison/compare-document/${jobId}${queryString ? `?${queryString}` : ''}`;
  
  const response = await fetch(url);
  return handleResponse<ComparisonStatusResponse>(response);
}

// User Annotations
export async function saveAnnotations(
  jobId: string,
  request: SaveAnnotationsRequest
): Promise<SaveAnnotationsResponse> {
  const response = await fetch(`${API_BASE_URL}/comparison/${jobId}/annotations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  
  return handleResponse<SaveAnnotationsResponse>(response);
}

// Report Generation
export async function getReport(jobId: string): Promise<ReportResponse> {
  const response = await fetch(`${API_BASE_URL}/comparison/${jobId}/report`);
  return handleResponse<ReportResponse>(response);
}

export async function saveReport(
  jobId: string,
  request: SaveReportRequest
): Promise<SaveReportResponse> {
  const response = await fetch(`${API_BASE_URL}/comparison/${jobId}/report`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  return handleResponse<SaveReportResponse>(response);
}

// Health Check
export async function healthCheck(): Promise<{ status: string; version: string; timestamp: string }> {
  const response = await fetch(`${API_BASE_URL.replace('/api/v1', '')}/health`);
  return handleResponse(response);
}

// Configuration
export async function getLLMInfo(): Promise<LLMInfoResponse> {
  const response = await fetch(`${API_BASE_URL}/config/llm`);
  return handleResponse<LLMInfoResponse>(response);
}

export { ApiError };

