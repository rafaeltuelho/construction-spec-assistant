import { useState } from 'react';
import type { ComparisonResult, AnnotationType } from '../types/api';

interface ComparisonResultCardProps {
  result: ComparisonResult;
  onAnnotationChange: (comparisonId: string, annotationType: AnnotationType | null, noteText?: string) => void;
}

export function ComparisonResultCard({ result, onAnnotationChange }: ComparisonResultCardProps) {
  const [selectedAnnotation, setSelectedAnnotation] = useState<AnnotationType | null>(null);
  const [noteText, setNoteText] = useState('');
  const [showNoteInput, setShowNoteInput] = useState(false);

  const handleAnnotationClick = (type: AnnotationType) => {
    if (type === 'note') {
      setShowNoteInput(true);
      setSelectedAnnotation(type);
    } else {
      if (selectedAnnotation === type) {
        // Deselect if clicking the same annotation
        setSelectedAnnotation(null);
        onAnnotationChange(result.comparison_id, null);
      } else {
        setSelectedAnnotation(type);
        onAnnotationChange(result.comparison_id, type);
      }
    }
  };

  const handleNoteSave = () => {
    if (noteText.trim()) {
      setSelectedAnnotation('note');
      onAnnotationChange(result.comparison_id, 'note', noteText);
      setShowNoteInput(false);
    }
  };

  const handleNoteCancel = () => {
    setShowNoteInput(false);
    if (!noteText) {
      setSelectedAnnotation(null);
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
    return `${entity || 'N/A'} - ${attribute || 'N/A'}: ${op || '='} ${value || 'N/A'}`;
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
      {/* Header with Verdict */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-2">
          {getVerdictIcon()}
          <span className={`px-3 py-1 rounded-full text-sm font-medium border ${getVerdictColor()}`}>
            {result.verdict.charAt(0).toUpperCase() + result.verdict.slice(1)}
          </span>
          <span className="text-sm text-gray-500">
            Confidence: {(result.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Spec Fact */}
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Specification Requirement</h3>
        <p className="text-sm text-gray-900">{formatSpecFact()}</p>
      </div>

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
              ? 'bg-blue-600 text-white'
              : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
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
  );
}

