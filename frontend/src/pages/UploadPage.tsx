import { useState } from 'react';
import { DocumentUpload } from '../components/DocumentUpload';
import { ProcessingStatus } from '../components/ProcessingStatus';
import { uploadDocument, extractFacts, compareDocuments, getComparisonStatus } from '../services/api';
import type { DocumentType, ComparisonSummary } from '../types/api';

interface UploadedDocument {
  documentId: string;
  filename: string;
  type: DocumentType;
  processingJobId: string;
  processingComplete: boolean;
  extractionJobId?: string;
  extractionComplete?: boolean;
}

export function UploadPage() {
  const [specDocument, setSpecDocument] = useState<UploadedDocument | null>(null);
  const [submittalDocument, setSubmittalDocument] = useState<UploadedDocument | null>(null);
  const [isUploading, setIsUploading] = useState<{ spec: boolean; submittal: boolean }>({
    spec: false,
    submittal: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [comparisonJobId, setComparisonJobId] = useState<string | null>(null);
  const [isComparing, setIsComparing] = useState(false);
  const [comparisonSummary, setComparisonSummary] = useState<ComparisonSummary | null>(null);
  const [showSummary, setShowSummary] = useState(false);

  const handleUpload = async (type: 'spec' | 'submittal', file: File, documentType: DocumentType) => {
    setError(null);
    setIsUploading((prev) => ({ ...prev, [type]: true }));

    try {
      const response = await uploadDocument(file, documentType, true);

      const uploadedDoc: UploadedDocument = {
        documentId: response.document_id,
        filename: response.filename,
        type: documentType,
        processingJobId: response.processing_job_id,
        processingComplete: false,
      };

      if (type === 'spec') {
        setSpecDocument(uploadedDoc);
      } else {
        setSubmittalDocument(uploadedDoc);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading((prev) => ({ ...prev, [type]: false }));
    }
  };

  const handleDocumentProcessingComplete = async (type: 'spec' | 'submittal') => {
    const doc = type === 'spec' ? specDocument : submittalDocument;
    if (!doc) return;

    // Mark processing as complete
    const updatedDoc = { ...doc, processingComplete: true };

    // For specification documents, automatically trigger fact extraction
    if (type === 'spec') {
      try {
        const extractionResponse = await extractFacts({
          document_id: doc.documentId,
          llm_model: 'gpt-4o-mini',
          deduplicate: true,
        });

        updatedDoc.extractionJobId = extractionResponse.extraction_job_id;
        updatedDoc.extractionComplete = false;
        setSpecDocument(updatedDoc);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Fact extraction failed');
      }
    } else {
      setSubmittalDocument(updatedDoc);
    }
  };

  const handleFactExtractionComplete = () => {
    if (specDocument) {
      setSpecDocument({ ...specDocument, extractionComplete: true });
    }
  };

  const handleStartComparison = async () => {
    if (!specDocument || !submittalDocument) return;

    setError(null);
    setIsComparing(true);

    try {
      const response = await compareDocuments({
        spec_document_id: specDocument.documentId,
        submittal_document_id: submittalDocument.documentId,
        retrieval_strategy: 'ensemble',
        top_k: 5,
      });

      setComparisonJobId(response.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Comparison failed');
      setIsComparing(false);
    }
  };

  const handleComparisonComplete = async () => {
    setIsComparing(false);

    // Fetch comparison summary
    if (comparisonJobId) {
      try {
        const status = await getComparisonStatus(comparisonJobId);
        if (status.summary) {
          setComparisonSummary(status.summary);
          setShowSummary(true);

          // Auto-navigate after 5 seconds
          setTimeout(() => {
            window.location.href = `/results/${comparisonJobId}`;
          }, 5000);
        } else {
          // Navigate immediately if no summary
          window.location.href = `/results/${comparisonJobId}`;
        }
      } catch (err) {
        console.error('Failed to fetch comparison summary:', err);
        // Navigate anyway
        window.location.href = `/results/${comparisonJobId}`;
      }
    }
  };

  const canStartComparison =
    specDocument?.processingComplete &&
    specDocument?.extractionComplete &&
    submittalDocument?.processingComplete &&
    !isComparing &&
    !comparisonJobId;

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Construction Specification Assistant</h1>
          <p className="mt-2 text-gray-600">
            Upload your specification and submittal documents to compare and analyze compliance
          </p>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <svg className="h-5 w-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-sm font-medium text-red-800">{error}</span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Specification Upload */}
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">1. Upload Specification</h2>
            <DocumentUpload
              documentType="specification"
              onUploadError={(error) => setError(error)}
            />

            {!specDocument && (
              <button
                onClick={() => {
                  const fileInput = document.querySelector<HTMLInputElement>(
                    'input[type="file"][accept=".pdf"]'
                  );
                  const file = fileInput?.files?.[0];
                  if (file) {
                    handleUpload('spec', file, 'specification');
                  }
                }}
                disabled={isUploading.spec}
                className="mt-4 w-full btn-primary"
              >
                {isUploading.spec ? 'Uploading...' : 'Upload Specification'}
              </button>
            )}

            {specDocument && (
              <div className="mt-4">
                <ProcessingStatus
                  type="document"
                  id={specDocument.documentId}
                  onComplete={() => handleDocumentProcessingComplete('spec')}
                  onError={(err) => setError(err)}
                />
              </div>
            )}

            {specDocument?.extractionJobId && (
              <div className="mt-4">
                <h3 className="text-sm font-medium text-gray-700 mb-2">Extracting Facts</h3>
                <ProcessingStatus
                  type="fact_extraction"
                  id={specDocument.extractionJobId}
                  onComplete={handleFactExtractionComplete}
                  onError={(err) => setError(err)}
                />
              </div>
            )}
          </div>

          {/* Submittal Upload */}
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">2. Upload Submittal</h2>
            <DocumentUpload
              documentType="submittal"
              onUploadError={(error) => setError(error)}
            />

            {!submittalDocument && (
              <button
                onClick={() => {
                  const fileInputs = document.querySelectorAll<HTMLInputElement>(
                    'input[type="file"][accept=".pdf"]'
                  );
                  const file = fileInputs[1]?.files?.[0];
                  if (file) {
                    handleUpload('submittal', file, 'submittal');
                  }
                }}
                disabled={isUploading.submittal}
                className="mt-4 w-full btn-primary"
              >
                {isUploading.submittal ? 'Uploading...' : 'Upload Submittal'}
              </button>
            )}

            {submittalDocument && (
              <div className="mt-4">
                <ProcessingStatus
                  type="document"
                  id={submittalDocument.documentId}
                  onComplete={() => handleDocumentProcessingComplete('submittal')}
                  onError={(err) => setError(err)}
                />
              </div>
            )}
          </div>
        </div>

        {/* Comparison Section */}
        <div className="card">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">3. Compare Documents</h2>
          <p className="text-sm text-gray-600 mb-4">
            Once both documents are processed, click the button below to start the comparison analysis.
          </p>

          <button
            onClick={handleStartComparison}
            disabled={!canStartComparison}
            className="w-full btn-primary"
          >
            {isComparing ? 'Comparing...' : 'Start Comparison'}
          </button>

          {comparisonJobId && (
            <div className="mt-4">
              <ProcessingStatus
                type="comparison"
                id={comparisonJobId}
                onComplete={handleComparisonComplete}
                onError={(err) => setError(err)}
              />
            </div>
          )}

          {/* Comparison Summary */}
          {showSummary && comparisonSummary && (
            <div className="mt-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-lg p-6 shadow-lg">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">Comparison Complete! 🎉</h3>
                <span className="text-sm text-gray-600">Redirecting in 5 seconds...</span>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white rounded-lg p-4 text-center shadow-sm">
                  <div className="text-3xl font-bold text-green-600">
                    {comparisonSummary.consistent}
                  </div>
                  <div className="text-sm text-gray-600 mt-1">Consistent</div>
                </div>

                <div className="bg-white rounded-lg p-4 text-center shadow-sm">
                  <div className="text-3xl font-bold text-red-600">
                    {comparisonSummary.inconsistent}
                  </div>
                  <div className="text-sm text-gray-600 mt-1">Inconsistent</div>
                </div>

                <div className="bg-white rounded-lg p-4 text-center shadow-sm">
                  <div className="text-3xl font-bold text-yellow-600">
                    {comparisonSummary.unclear}
                  </div>
                  <div className="text-sm text-gray-600 mt-1">Unclear</div>
                </div>
              </div>

              <div className="mt-4 text-center">
                <button
                  onClick={() => window.location.href = `/results/${comparisonJobId}`}
                  className="btn-primary"
                >
                  View Detailed Results Now
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

