import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getReport, saveReport } from '../services/api';
import type { ReportResponse, ConclusionType, SaveReportRequest } from '../types/api';

export function ReportPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [reportData, setReportData] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conclusionType, setConclusionType] = useState<ConclusionType | null>(null);
  const [conclusionComment, setConclusionComment] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const fetchReport = async () => {
      try {
        setLoading(true);
        const data = await getReport(jobId);
        setReportData(data);
        
        // Initialize conclusion fields if already saved
        if (data.conclusion) {
          setConclusionType(data.conclusion.conclusion_type);
          setConclusionComment(data.conclusion.conclusion_comment || '');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load report');
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [jobId]);

  const handleSaveReport = async () => {
    if (!jobId || !conclusionType) {
      setSaveError('Please select a conclusion type');
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const request: SaveReportRequest = {
        conclusion_type: conclusionType,
        conclusion_comment: conclusionComment || undefined,
      };

      await saveReport(jobId, request);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save report');
    } finally {
      setIsSaving(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getConclusionLabel = (type: ConclusionType): string => {
    const labels: Record<ConclusionType, string> = {
      reviewed: 'Reviewed',
      reviewed_as_noted: 'Reviewed as Noted',
      revise_and_resubmit: 'Revise and Resubmit',
      rejected: 'Rejected',
      for_record_only: 'For Record Only',
    };
    return labels[type];
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading report...</p>
        </div>
      </div>
    );
  }

  if (error || !reportData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <div className="text-red-600 text-center">
            <svg className="w-16 h-16 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="text-xl font-semibold mb-2">Error Loading Report</h2>
            <p className="text-gray-600">{error || 'Report not found'}</p>
            <button
              onClick={() => navigate(-1)}
              className="mt-4 btn-secondary"
            >
              Go Back
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 print:py-0">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header Actions */}
        <div className="mb-6 flex justify-between items-center print:hidden">
          <button
            onClick={() => navigate(-1)}
            className="btn-secondary"
          >
            ← Back to Results
          </button>
          <button
            onClick={() => window.print()}
            className="btn-secondary"
          >
            🖨️ Print Report
          </button>
        </div>

        {/* Report Container */}
        <div className="bg-white rounded-lg shadow-lg p-8 print:shadow-none">
          {/* Report Header */}
          <div className="border-b-2 border-gray-200 pb-6 mb-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-4">
              Comparison Report
            </h1>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-semibold text-gray-700">Job ID:</span>
                <span className="ml-2 text-gray-600">{reportData.job_id}</span>
              </div>
              <div>
                <span className="font-semibold text-gray-700">Generated:</span>
                <span className="ml-2 text-gray-600">{formatDate(reportData.report_generated_at)}</span>
              </div>
              <div>
                <span className="font-semibold text-gray-700">Specification Document:</span>
                <span className="ml-2 text-gray-600">{reportData.spec_document_id}</span>
              </div>
              <div>
                <span className="font-semibold text-gray-700">Submittal Document:</span>
                <span className="ml-2 text-gray-600">{reportData.submittal_document_id}</span>
              </div>
            </div>
          </div>

          {/* Annotations Table */}
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">
              Items Requiring Attention
            </h2>
            {reportData.annotations.length === 0 ? (
              <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
                <svg className="w-12 h-12 text-green-600 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="text-green-800 font-medium">No items noted for this comparison</p>
                <p className="text-green-600 text-sm mt-1">All comparisons have been reviewed without requiring special attention.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 border border-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">
                        #
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Specification Fact
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Note
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-40">
                        Annotated
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {reportData.annotations.map((annotation, index) => (
                      <tr key={annotation.comparison_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900 font-medium">
                          {index + 1}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700">
                          {annotation.spec_fact.fact_text || annotation.spec_fact.requirement || 'N/A'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700">
                          {annotation.note_text}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {formatDate(annotation.annotated_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Report Conclusion Section */}
          <div className="border-t-2 border-gray-200 pt-6">
            <h2 className="text-2xl font-semibold text-gray-900 mb-4">
              Report Conclusion
            </h2>

            {reportData.conclusion && (
              <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-800">
                  <span className="font-semibold">Saved Conclusion:</span> {getConclusionLabel(reportData.conclusion.conclusion_type)}
                  {reportData.conclusion.concluded_at && (
                    <span className="ml-2 text-blue-600">
                      (Saved on {formatDate(reportData.conclusion.concluded_at)})
                    </span>
                  )}
                </p>
              </div>
            )}

            <div className="space-y-4 print:hidden">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Select Conclusion Type <span className="text-red-500">*</span>
                </label>
                <div className="space-y-2">
                  {(['reviewed', 'reviewed_as_noted', 'revise_and_resubmit', 'rejected', 'for_record_only'] as ConclusionType[]).map((type) => (
                    <label key={type} className="flex items-center space-x-3 p-3 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer">
                      <input
                        type="radio"
                        name="conclusion"
                        value={type}
                        checked={conclusionType === type}
                        onChange={(e) => setConclusionType(e.target.value as ConclusionType)}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm font-medium text-gray-900">
                        {getConclusionLabel(type)}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label htmlFor="conclusion-comment" className="block text-sm font-medium text-gray-700 mb-2">
                  Conclusion Comments (Optional)
                </label>
                <textarea
                  id="conclusion-comment"
                  rows={4}
                  value={conclusionComment}
                  onChange={(e) => setConclusionComment(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Add any additional comments or notes about this comparison..."
                />
              </div>

              {saveError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-sm text-red-800">{saveError}</p>
                </div>
              )}

              {saveSuccess && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <p className="text-sm text-green-800">Report conclusion saved successfully!</p>
                </div>
              )}

              <div className="flex space-x-4">
                <button
                  onClick={handleSaveReport}
                  disabled={!conclusionType || isSaving}
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? 'Saving...' : 'Save Report'}
                </button>
                <button
                  onClick={() => navigate(-1)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </div>

            {/* Print-only conclusion display */}
            {reportData.conclusion && (
              <div className="hidden print:block mt-4">
                <div className="border-t border-gray-200 pt-4">
                  <p className="text-sm">
                    <span className="font-semibold">Conclusion:</span> {getConclusionLabel(reportData.conclusion.conclusion_type)}
                  </p>
                  {reportData.conclusion.conclusion_comment && (
                    <p className="text-sm mt-2">
                      <span className="font-semibold">Comments:</span> {reportData.conclusion.conclusion_comment}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

