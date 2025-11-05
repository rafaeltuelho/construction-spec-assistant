import { useEffect, useState } from 'react';
import { getDocumentStatus, getFactExtractionStatus, getComparisonStatus } from '../services/api';
import type { ProcessingStats, DocumentType } from '../types/api';

interface ProcessingStatusProps {
  type: 'document' | 'fact_extraction' | 'comparison';
  id: string;
  onComplete?: () => void;
  onError?: (error: string) => void;
}

interface DocumentMetadata {
  filename: string;
  parse_time?: number;
  file_size: number;
  document_type: DocumentType;
}

export function ProcessingStatus({ type, id, onComplete, onError }: ProcessingStatusProps) {
  const [status, setStatus] = useState<string>('pending');
  const [progress, setProgress] = useState<number>(0);
  const [currentStage, setCurrentStage] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [processingStats, setProcessingStats] = useState<ProcessingStats | null>(null);
  const [documentMetadata, setDocumentMetadata] = useState<DocumentMetadata | null>(null);
  const [statsExpanded, setStatsExpanded] = useState(false);

  useEffect(() => {
    let intervalId: number;

    const pollStatus = async () => {
      try {
        if (type === 'document') {
          const response = await getDocumentStatus(id);
          setStatus(response.status);
          setProgress(response.progress?.percentage || 0);
          setCurrentStage(response.progress?.current_stage || '');

          if (response.status === 'completed') {
            // Capture processing statistics and metadata when completed
            if (response.processing_stats) {
              setProcessingStats(response.processing_stats);
            }
            if (response.metadata) {
              setDocumentMetadata({
                filename: response.metadata.filename,
                parse_time: response.metadata.parse_time,
                file_size: response.metadata.file_size,
                document_type: response.metadata.document_type,
              });
            }
            clearInterval(intervalId);
            onComplete?.();
          } else if (response.status === 'failed') {
            clearInterval(intervalId);
            setError('Document processing failed');
            onError?.('Document processing failed');
          }
        } else if (type === 'fact_extraction') {
          const response = await getFactExtractionStatus(id);
          setStatus(response.status);
          setProgress(response.progress?.percentage || 0);
          setCurrentStage(`Processing chunks: ${response.progress?.chunks_processed || 0}/${response.progress?.total_chunks || 0}`);

          if (response.status === 'completed') {
            clearInterval(intervalId);
            onComplete?.();
          } else if (response.status === 'failed') {
            clearInterval(intervalId);
            setError(response.error || 'Fact extraction failed');
            onError?.(response.error || 'Fact extraction failed');
          }
        } else if (type === 'comparison') {
          const response = await getComparisonStatus(id);
          setStatus(response.status);
          const progressPercent = response.total_facts > 0
            ? (response.completed_facts / response.total_facts) * 100
            : 0;
          setProgress(progressPercent);
          setCurrentStage(`Comparing facts: ${response.completed_facts}/${response.total_facts}`);

          if (response.status === 'completed') {
            clearInterval(intervalId);
            onComplete?.();
          } else if (response.status === 'failed') {
            clearInterval(intervalId);
            setError(response.error || 'Comparison failed');
            onError?.(response.error || 'Comparison failed');
          }
        }
      } catch (err) {
        console.error('Error polling status:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
        clearInterval(intervalId);
        onError?.(err instanceof Error ? err.message : 'Unknown error');
      }
    };

    // Poll immediately and then every 2 seconds
    pollStatus();
    intervalId = window.setInterval(pollStatus, 2000);

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [type, id, onComplete, onError]);

  const getStatusColor = () => {
    switch (status) {
      case 'completed':
        return 'text-green-600';
      case 'failed':
        return 'text-red-600';
      case 'processing':
        return 'text-blue-600';
      default:
        return 'text-gray-600';
    }
  };

  const getStatusLabel = () => {
    switch (status) {
      case 'pending':
        return 'Pending';
      case 'processing':
        return 'Processing';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      default:
        return status;
    }
  };

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
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
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className={`text-sm font-medium ${getStatusColor()}`}>
          {getStatusLabel()}
        </span>
        {status === 'processing' && (
          <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
        )}
      </div>

      {status === 'processing' && (
        <>
          <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
            <div
              className="bg-primary-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          {currentStage && (
            <p className="text-xs text-gray-600">{currentStage}</p>
          )}
        </>
      )}

      {status === 'completed' && (
        <div>
          <div className="flex items-center space-x-2 text-green-600 mb-3">
            <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <span className="text-sm font-medium">Processing complete</span>
          </div>

          {/* Display processing statistics - Collapsible */}
          {processingStats && documentMetadata && (
            <div className="mt-3 border border-gray-300 rounded-lg">
              {/* Collapsible Header */}
              <button
                onClick={() => setStatsExpanded(!statsExpanded)}
                className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors rounded-t-lg"
              >
                <div className="flex items-center space-x-2">
                  <svg
                    className="h-4 w-4 text-gray-600"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
                    <path
                      fillRule="evenodd"
                      d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span className="text-xs font-semibold text-gray-700">
                    Processing Details (Advanced)
                  </span>
                </div>
                <svg
                  className={`h-5 w-5 text-gray-500 transition-transform ${
                    statsExpanded ? 'transform rotate-180' : ''
                  }`}
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>

              {/* Collapsible Content */}
              {statsExpanded && (
                <div className="p-3 bg-white border-t border-gray-200">
                  {/* Document Metadata */}
                  <div className="mb-3 pb-3 border-b border-gray-200">
                    <h5 className="text-xs font-semibold text-gray-700 mb-2">Document Info</h5>
                    <div className="space-y-1 text-xs">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Filename:</span>
                        <span className="font-medium text-gray-900 truncate ml-2 max-w-xs" title={documentMetadata.filename}>
                          {documentMetadata.filename}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Document Type:</span>
                        <span className="font-medium text-gray-900 capitalize">
                          {documentMetadata.document_type.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">File Size:</span>
                        <span className="font-medium text-gray-900">
                          {(documentMetadata.file_size / 1024).toFixed(1)} KB
                        </span>
                      </div>
                      {documentMetadata.parse_time && (
                        <div className="flex justify-between">
                          <span className="text-gray-600">Parse Time:</span>
                          <span className="font-medium text-gray-900">
                            {documentMetadata.parse_time.toFixed(2)}s
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Processing Statistics */}
                  <div className="mb-3 pb-3 border-b border-gray-200">
                    <h5 className="text-xs font-semibold text-gray-700 mb-2">Processing Stats</h5>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Sections:</span>
                        <span className="font-medium text-gray-900">{processingStats.total_sections}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Chunks:</span>
                        <span className="font-medium text-gray-900">{processingStats.total_chunks}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Total Tokens:</span>
                        <span className="font-medium text-gray-900">{processingStats.total_tokens.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Avg Chunk Size:</span>
                        <span className="font-medium text-gray-900">{Math.round(processingStats.avg_chunk_tokens)} tokens</span>
                      </div>
                    </div>
                  </div>

                  {/* Display sections by level if available */}
                  {Object.keys(processingStats.sections_by_level).length > 0 && (
                    <div>
                      <h5 className="text-xs font-semibold text-gray-700 mb-2">Sections by Level</h5>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(processingStats.sections_by_level)
                          .sort(([a], [b]) => parseInt(a) - parseInt(b))
                          .map(([level, count]) => (
                            <span key={level} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                              Level {level}: {count}
                            </span>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

