import { useState, useEffect } from 'react';
import type { ComparisonResult, AnnotationType, Fact, DocumentSection } from '../types/api';
import { getFactById, getSectionById } from '../services/api';

/**
 * Helper function to format page numbers for display
 * Converts 0-indexed backend page numbers to 1-indexed user-friendly format
 * @param pageStart - Starting page number (0-indexed)
 * @param pageEnd - Ending page number (0-indexed)
 * @returns Formatted page string (e.g., "Page 5" or "Page 5-7") or null if no page numbers
 */
const formatPageNumber = (pageStart: number | null | undefined, pageEnd: number | null | undefined): string | null => {
  if (pageStart === null || pageStart === undefined) return null;

  // Convert from 0-indexed to 1-indexed for display
  const start = pageStart + 1;

  if (pageEnd !== null && pageEnd !== undefined && pageEnd !== pageStart) {
    const end = pageEnd + 1;
    return `Page ${start}-${end}`;
  }

  return `Page ${start}`;
};

interface ComparisonResultCardProps {
  result: ComparisonResult;
  onAnnotationChange: (comparisonId: string, annotationType: AnnotationType | null, noteText?: string) => void;
  initialAnnotation?: AnnotationType | null;
  initialNoteText?: string;
}

export function ComparisonResultCard({
  result,
  onAnnotationChange,
  initialAnnotation = null,
  initialNoteText = ''
}: ComparisonResultCardProps) {
  const [selectedAnnotation, setSelectedAnnotation] = useState<AnnotationType | null>(initialAnnotation);
  const [noteText, setNoteText] = useState(initialNoteText);
  const [showNoteInput, setShowNoteInput] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);

  // Context data state
  const [factData, setFactData] = useState<Fact | null>(null);
  const [sectionData, setSectionData] = useState<DocumentSection | null>(null);
  const [loadingContext, setLoadingContext] = useState(false);
  const [contextExpanded, setContextExpanded] = useState(false);
  const [contextError, setContextError] = useState<string | null>(null);

  // Contextual Findings (chunks) expansion state
  const [chunksExpanded, setChunksExpanded] = useState(false);

  // Update state when initial values change (e.g., when navigating between tabs)
  useEffect(() => {
    setSelectedAnnotation(initialAnnotation);
    setNoteText(initialNoteText);
  }, [initialAnnotation, initialNoteText]);

  const handleAnnotationClick = async (type: AnnotationType) => {
    if (type === 'note') {
      // Fetch context data if not already loaded
      if (!factData && !loadingContext && result.spec_fact.fact_id) {
        await fetchContextData();
      }

      // Populate note text with source_span if available and note is empty
      if (!noteText && factData?.context?.source_span) {
        setNoteText(factData.context.source_span);
      }

      setShowNoteInput(true);
      setSelectedAnnotation(type);
    } else {
      if (selectedAnnotation === type) {
        // Deselect if clicking the same annotation - expand card
        setSelectedAnnotation(null);
        onAnnotationChange(result.comparison_id, null);
        setIsExpanded(true);
      } else {
        setSelectedAnnotation(type);
        onAnnotationChange(result.comparison_id, type);
        // Auto-fold card for disregard and confirmed
        if (type === 'disregard' || type === 'confirmed') {
          setIsExpanded(false);
        }
      }
    }
  };

  const handleNoteSave = () => {
    if (noteText.trim()) {
      setSelectedAnnotation('note');
      onAnnotationChange(result.comparison_id, 'note', noteText);
      setShowNoteInput(false);
      // Fold card after saving note
      setIsExpanded(false);
    }
  };

  const handleNoteCancel = () => {
    setShowNoteInput(false);
    if (!noteText) {
      setSelectedAnnotation(null);
    }
    // Don't fold on cancel - keep expanded
  };

  // Fetch context data (fact and section)
  const fetchContextData = async () => {
    if (!result.spec_fact.fact_id || factData) {
      // No fact_id available or already loaded
      return;
    }

    setLoadingContext(true);
    setContextError(null);

    try {
      // Fetch fact details using centralized API service
      const fact = await getFactById(result.spec_fact.fact_id);
      setFactData(fact);

      // Fetch section details using section_id from fact context
      if (fact.context?.section_id) {
        try {
          const section = await getSectionById(fact.context.section_id);
          setSectionData(section);
        } catch (sectionError) {
          // Log warning but don't fail the entire operation if section fetch fails
          console.warn('Failed to fetch section:', sectionError);
        }
      }
    } catch (error) {
      console.error('Failed to fetch context data:', error);
      setContextError(error instanceof Error ? error.message : 'Failed to load context');
    } finally {
      setLoadingContext(false);
    }
  };

  const getVerdictColor = () => {
    switch (result.verdict) {
      case 'consistent':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'inconsistent':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'unclear':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    }
  };

  const getVerdictIcon = () => {
    switch (result.verdict) {
      case 'consistent':
        return (
          <svg className="h-5 w-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
              clipRule="evenodd"
            />
          </svg>
        );
      case 'inconsistent':
        return (
          <svg className="h-5 w-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clipRule="evenodd"
            />
          </svg>
        );
      case 'unclear':
        return (
          <svg className="h-5 w-5 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
        );
    }
  };

  const formatSpecFact = () => {
    const { entity, attribute, value, op } = result.spec_fact;

    // Helper to extract non-null values from an object (for entity only)
    const extractNonNull = (obj: unknown): string => {
      if (!obj || typeof obj !== 'object') return String(obj || 'N/A');

      const values = Object.values(obj)
        .filter(v => v !== null && v !== undefined)
        .map(v => {
          if (typeof v === 'object') {
            return extractNonNull(v);
          }
          return String(v);
        })
        .filter(v => v && v !== 'N/A');

      return values.length > 0 ? values.join(' ') : 'N/A';
    };

    // Entity: use extractNonNull to get all non-null values
    const entityStr = extractNonNull(entity);

    // Attribute: use only the 'raw' field
    const attributeStr = attribute?.raw || 'N/A';

    // Value: format based on type
    let valueStr = value?.raw || 'N/A';

    // Only append type information if it's NOT 'text' or 'string'
    if (value?.type && value.type !== 'text' && value.type !== 'string') {
      valueStr = `${valueStr} (type: ${value.type})`;
    }

    // Add unit if present
    if (value?.unit) {
      valueStr = `${valueStr} ${value.unit}`;
    }

    // Add range if present
    if (value?.min !== null && value?.min !== undefined && value?.max !== null && value?.max !== undefined) {
      valueStr = `${valueStr} [${value.min}-${value.max}]`;
    }

    const opStr = op || '=';

    return `${entityStr} - ${attributeStr}: ${opStr} ${valueStr}`;
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow">
      {/* Header with Verdict - Always visible */}
      <div
        className="flex items-start justify-between p-6 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center space-x-2 flex-1">
          {getVerdictIcon()}
          <span className={`px-3 py-1 rounded-full text-sm font-medium border ${getVerdictColor()}`}>
            {result.verdict.charAt(0).toUpperCase() + result.verdict.slice(1)}
          </span>
          <span className="text-sm text-gray-500">
            Confidence: {(result.confidence * 100).toFixed(0)}%
          </span>
          {/* Show annotation badge when collapsed */}
          {!isExpanded && selectedAnnotation && (
            <span className="text-xs text-gray-500 ml-2">
              ({selectedAnnotation === 'disregard' ? 'Disregarded' :
                selectedAnnotation === 'confirmed' ? 'Confirmed' :
                'Has Note'})
            </span>
          )}
        </div>
        {/* Expand/Collapse Icon */}
        <button className="text-gray-400 hover:text-gray-600 ml-2">
          <svg
            className={`h-5 w-5 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
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
      </div>

      {/* Collapsible Content */}
      {isExpanded && (
        <div className="px-6 pb-6 border-t border-gray-100">{/* Add top border when expanded */}

      {/* Spec Fact */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Specification Requirement</h3>
        <p className="text-sm text-gray-900">{formatSpecFact()}</p>
      </div>

      {/* Spec Provenance Section - MOVED BEFORE Submittal Evidence */}
      {result.spec_fact.fact_id && (
        <div className="mb-4 border-t border-gray-200 pt-4">
          <button
            onClick={() => {
              if (!factData && !loadingContext) {
                fetchContextData();
              }
              setContextExpanded(!contextExpanded);
            }}
            className="flex items-center justify-between w-full text-left hover:bg-gray-50 p-2 rounded transition-colors"
          >
            <h3 className="text-sm font-semibold text-gray-700">Specification Provenance</h3>
            <svg
              className={`h-4 w-4 transform transition-transform ${contextExpanded ? 'rotate-180' : ''}`}
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

          {contextExpanded && (
            <div className="mt-3 pl-2">
              {loadingContext ? (
                <p className="text-sm text-gray-500">Loading context...</p>
              ) : contextError ? (
                <p className="text-sm text-red-600">Error: {contextError}</p>
              ) : factData ? (
                <>
                  {/* Header path breadcrumb */}
                  {factData.context?.header_path && factData.context.header_path.length > 0 && (
                    <div className="mb-3">
                      <p className="text-xs text-gray-500 mb-1">Section Path:</p>
                      <div className="flex items-center flex-wrap gap-1 text-xs text-gray-700 bg-gray-50 p-2 rounded border border-gray-200">
                        {factData.context.header_path.map((header, idx) => (
                          <div key={idx} className="flex items-center">
                            {idx > 0 && <span className="text-gray-400 mx-1">›</span>}
                            <span className="font-medium">{header}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Source span */}
                  {factData.context?.source_span && (
                    <div className="mb-3">
                      <p className="text-xs text-gray-500 mb-1">Source Text:</p>
                      <p className="text-sm text-gray-700 italic bg-blue-50 p-2 rounded border border-blue-200">
                        "{factData.context.source_span}"
                      </p>
                    </div>
                  )}

                  {/* Section content */}
                  {sectionData && (
                    <div className="mt-3 p-3 bg-gray-50 rounded border border-gray-200">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-medium text-gray-700">
                          {sectionData.section_number && `${sectionData.section_number} - `}
                          {sectionData.title}
                        </p>
                        {/* Page number badge */}
                        {formatPageNumber(sectionData.page_start, sectionData.page_end) && (
                          <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded font-medium whitespace-nowrap ml-2">
                            {formatPageNumber(sectionData.page_start, sectionData.page_end)}
                          </span>
                        )}
                      </div>
                      <details className="text-sm text-gray-600">
                        <summary className="cursor-pointer text-primary-600 hover:text-primary-700 font-medium">
                          View full section content
                        </summary>
                        <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed max-h-64 overflow-y-auto">
                          {sectionData.content}
                        </p>
                      </details>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-gray-500">Context information not available</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Submittal Evidence */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Submittal Evidence</h3>
        <p className="text-sm text-gray-700 italic bg-gray-50 p-3 rounded border border-gray-200">
          "{result.submittal_evidence}"
        </p>
      </div>

      {/* Reasoning */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Analysis</h3>
        <p className="text-sm text-gray-700">{result.reasoning}</p>
      </div>

      {/* Contextual Findings Section - Collapsible */}
      {result.retrieved_chunks && result.retrieved_chunks.length > 0 && (
        <div className="mb-4 border-t border-gray-200 pt-4">
          <button
            onClick={() => setChunksExpanded(!chunksExpanded)}
            className="flex items-center justify-between w-full text-left hover:bg-gray-50 p-2 rounded transition-colors"
          >
            <h3 className="text-sm font-semibold text-gray-700">
              Contextual Findings in the Submittal ({result.retrieved_chunks.length} text chunks)
            </h3>
            <svg
              className={`h-4 w-4 transform transition-transform ${chunksExpanded ? 'rotate-180' : ''}`}
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

          {chunksExpanded && (
            <div className="mt-3 space-y-2">
              {result.retrieved_chunks.map((chunk, idx) => (
                <div key={idx} className="p-3 bg-gray-50 rounded border border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-gray-600">
                        Text Chunk {idx + 1}
                      </span>
                      {/* Page number badge - will display when backend adds page_start/page_end */}
                      {formatPageNumber(chunk.page_start, chunk.page_end) && (
                        <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded font-medium">
                          {formatPageNumber(chunk.page_start, chunk.page_end)}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-500">
                      Relevance Score: {chunk.relevance_score.toFixed(3)}
                    </span>
                  </div>
                  <p className="text-xs text-gray-700 whitespace-pre-wrap">
                    {chunk.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Annotation Badges */}
      <div className="flex items-center space-x-2 pt-4 border-t border-gray-200">
        <span className="text-sm font-medium text-gray-700">Actions:</span>
        <button
          onClick={() => handleAnnotationClick('disregard')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            selectedAnnotation === 'disregard'
              ? 'bg-gray-700 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          Disregard
        </button>
        <button
          onClick={() => handleAnnotationClick('confirmed')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            selectedAnnotation === 'confirmed'
              ? 'bg-primary-600 text-white'
              : 'bg-primary-100 text-primary-700 hover:bg-primary-200'
          }`}
        >
          Confirmed
        </button>
        <button
          onClick={() => handleAnnotationClick('note')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            selectedAnnotation === 'note'
              ? 'bg-yellow-400 text-yellow-700'
              : 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
          }`}
        >
          Add Note
        </button>
      </div>

      {/* Note Input */}
      {showNoteInput && (
        <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <label className="block text-sm font-medium text-gray-700 mb-2">Add your note:</label>
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            rows={3}
            placeholder="Enter your notes here..."
          />
          <div className="flex justify-end space-x-2 mt-2">
            <button onClick={handleNoteCancel} className="btn-secondary text-sm">
              Cancel
            </button>
            <button onClick={handleNoteSave} className="btn-primary text-sm">
              Save Note
            </button>
          </div>
        </div>
      )}

      {/* Display saved note */}
      {selectedAnnotation === 'note' && noteText && !showNoteInput && (
        <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm font-medium text-blue-900 mb-1">Your Note:</p>
              <p className="text-sm text-blue-800">{noteText}</p>
            </div>
            <button
              onClick={() => setShowNoteInput(true)}
              className="text-blue-600 hover:text-blue-800 text-sm"
            >
              Edit
            </button>
          </div>
        </div>
      )}
        </div>
      )}
    </div>
  );
}

