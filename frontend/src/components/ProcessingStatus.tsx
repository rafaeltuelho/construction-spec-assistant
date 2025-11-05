import { useEffect, useState } from 'react';
import { getDocumentStatus, getFactExtractionStatus, getComparisonStatus } from '../services/api';
import type { ProcessingStats } from '../types/api';

interface ProcessingStatusProps {
  type: 'document' | 'fact_extraction' | 'comparison';
  id: string;
  onComplete?: () => void;
  onError?: (error: string) => void;
}

export function ProcessingStatus({ type, id, onComplete, onError }: ProcessingStatusProps) {
  const [status, setStatus] = useState<string>('pending');
  const [progress, setProgress] = useState<number>(0);
  const [currentStage, setCurrentStage] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [processingStats, setProcessingStats] = useState<ProcessingStats | null>(null);

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
            // Capture processing statistics when completed
            if (response.processing_stats) {
              setProcessingStats(response.processing_stats);
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

          {/* Display processing statistics */}
          {processingStats && (
            <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
              <h4 className="text-xs font-semibold text-green-900 mb-2">Processing Statistics</h4>
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

              {/* Display sections by level if available */}
              {Object.keys(processingStats.sections_by_level).length > 0 && (
                <div className="mt-2 pt-2 border-t border-green-200">
                  <p className="text-xs font-medium text-gray-700 mb-1">Sections by Level:</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(processingStats.sections_by_level)
                      .sort(([a], [b]) => parseInt(a) - parseInt(b))
                      .map(([level, count]) => (
                        <span key={level} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
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
  );
}

