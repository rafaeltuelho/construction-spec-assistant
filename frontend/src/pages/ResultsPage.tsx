import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { ComparisonResultCard } from '../components/ComparisonResultCard';
import { getComparisonStatus, saveAnnotations } from '../services/api';
import type { ComparisonStatusResponse, ComparisonResult, UserAnnotation, AnnotationType } from '../types/api';

export function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [comparisonData, setComparisonData] = useState<ComparisonStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'inconsistent' | 'unclear' | 'consistent'>('all');
  const [annotations, setAnnotations] = useState<Map<string, UserAnnotation>>(new Map());
  const [isSavingAnnotations, setIsSavingAnnotations] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (!jobId) return;

    const fetchResults = async () => {
      try {
        setLoading(true);
        const data = await getComparisonStatus(jobId);
        setComparisonData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load results');
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [jobId]);

  const handleAnnotationChange = (
    comparisonId: string,
    annotationType: AnnotationType | null,
    noteText?: string
  ) => {
    const newAnnotations = new Map(annotations);

    if (annotationType === null) {
      newAnnotations.delete(comparisonId);
    } else {
      newAnnotations.set(comparisonId, {
        comparison_id: comparisonId,
        annotation_type: annotationType,
        note_text: noteText,
      });
    }

    setAnnotations(newAnnotations);
    setSaveSuccess(false);
  };

  const handleSaveAnnotations = async () => {
    if (!jobId || annotations.size === 0) return;

    setIsSavingAnnotations(true);
    setError(null);

    try {
      await saveAnnotations(jobId, {
        annotations: Array.from(annotations.values()),
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save annotations');
    } finally {
      setIsSavingAnnotations(false);
    }
  };

  const filterResults = (results: ComparisonResult[]) => {
    if (activeTab === 'all') return results;
    return results.filter((r) => r.verdict === activeTab);
  };

  const getTabCount = (verdict: 'consistent' | 'inconsistent' | 'unclear') => {
    return comparisonData?.summary?.[verdict] || 0;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading comparison results...</p>
        </div>
      </div>
    );
  }

  if (error && !comparisonData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <div className="flex items-center space-x-2 mb-2">
            <svg className="h-6 w-6 text-red-500" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            <h2 className="text-lg font-semibold text-red-800">Error</h2>
          </div>
          <p className="text-sm text-red-700">{error}</p>
        </div>
      </div>
    );
  }

  if (!comparisonData) return null;

  const filteredResults = filterResults(comparisonData.comparisons);

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Comparison Results</h1>
          <p className="mt-2 text-gray-600">
            Review the comparison analysis between specification and submittal documents
          </p>
        </div>

        {/* Summary Stats */}
        {comparisonData.summary && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-sm font-medium text-gray-500">Total Comparisons</div>
              <div className="mt-2 text-3xl font-bold text-gray-900">{comparisonData.total_facts}</div>
            </div>
            <div className="bg-green-50 rounded-lg shadow p-6 border border-green-200">
              <div className="text-sm font-medium text-green-700">Consistent</div>
              <div className="mt-2 text-3xl font-bold text-green-900">{comparisonData.summary.consistent}</div>
            </div>
            <div className="bg-red-50 rounded-lg shadow p-6 border border-red-200">
              <div className="text-sm font-medium text-red-700">Inconsistent</div>
              <div className="mt-2 text-3xl font-bold text-red-900">{comparisonData.summary.inconsistent}</div>
            </div>
            <div className="bg-yellow-50 rounded-lg shadow p-6 border border-yellow-200">
              <div className="text-sm font-medium text-yellow-700">Unclear</div>
              <div className="mt-2 text-3xl font-bold text-yellow-900">{comparisonData.summary.unclear}</div>
            </div>
          </div>
        )}

        {/* Save Annotations Button */}
        {annotations.size > 0 && (
          <div className="mb-6 bg-white rounded-lg shadow p-4 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <svg className="h-5 w-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
              </svg>
              <span className="text-sm font-medium text-gray-700">
                {annotations.size} annotation{annotations.size !== 1 ? 's' : ''} pending
              </span>
            </div>
            <button
              onClick={handleSaveAnnotations}
              disabled={isSavingAnnotations}
              className="btn-primary"
            >
              {isSavingAnnotations ? 'Saving...' : 'Save Annotations'}
            </button>
          </div>
        )}

        {saveSuccess && (
          <div className="mb-6 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center space-x-2">
              <svg className="h-5 w-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
              <span className="text-sm font-medium text-green-800">Annotations saved successfully</span>
            </div>
          </div>
        )}

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

        {/* Tabs */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              <button
                onClick={() => setActiveTab('all')}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'all'
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                All ({comparisonData.total_facts})
              </button>
              <button
                onClick={() => setActiveTab('inconsistent')}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'inconsistent'
                    ? 'border-red-600 text-red-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Inconsistent ({getTabCount('inconsistent')})
              </button>
              <button
                onClick={() => setActiveTab('unclear')}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'unclear'
                    ? 'border-yellow-600 text-yellow-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Unclear ({getTabCount('unclear')})
              </button>
              <button
                onClick={() => setActiveTab('consistent')}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'consistent'
                    ? 'border-green-600 text-green-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Consistent ({getTabCount('consistent')})
              </button>
            </nav>
          </div>
        </div>

        {/* Results Grid */}
        <div className="space-y-4">
          {filteredResults.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-12 text-center">
              <p className="text-gray-500">No results found for this category</p>
            </div>
          ) : (
            filteredResults.map((result) => (
              <ComparisonResultCard
                key={result.comparison_id}
                result={result}
                onAnnotationChange={handleAnnotationChange}
              />
            ))
          )}
        </div>

        {/* Generate Report Button (Placeholder) */}
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Generate Report</h2>
          <p className="text-sm text-gray-600 mb-4">
            Generate a comprehensive PDF report with all comparison results and your annotations.
          </p>
          <button
            disabled
            className="btn-primary opacity-50 cursor-not-allowed"
            title="Report generation coming soon"
          >
            Generate Report (Coming Soon)
          </button>
        </div>
      </div>
    </div>
  );
}

