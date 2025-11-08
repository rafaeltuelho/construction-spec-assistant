import { useEffect, useState } from 'react';
import { getLLMInfo } from '../services/api';
import type { LLMInfoResponse } from '../types/api';

interface LLMBadgeProps {
  className?: string;
}

export function LLMBadge({ className = '' }: LLMBadgeProps) {
  const [llmInfo, setLlmInfo] = useState<LLMInfoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchLLMInfo = async () => {
      try {
        setLoading(true);
        setError(null);
        const info = await getLLMInfo();
        setLlmInfo(info);
      } catch (err) {
        console.error('Failed to fetch LLM info:', err);
        setError('LLM: Unknown');
      } finally {
        setLoading(false);
      }
    };

    fetchLLMInfo();
  }, []);

  if (loading) {
    return (
      <div className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600 ${className}`}>
        <span className="animate-pulse">Loading...</span>
      </div>
    );
  }

  if (error || !llmInfo) {
    return (
      <div className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600 ${className}`}>
        {error || 'LLM: Unknown'}
      </div>
    );
  }

  // Format provider name (capitalize first letter)
  const formattedProvider = llmInfo.provider.charAt(0).toUpperCase() + llmInfo.provider.slice(1);
  
  // Truncate model name if it's too long
  const displayModel = llmInfo.model.length > 30 
    ? llmInfo.model.substring(0, 27) + '...' 
    : llmInfo.model;

  return (
    <div className={`inline-flex items-center space-x-1 px-3 py-1.5 rounded-full text-xs font-medium bg-blue-50 border border-blue-200 text-blue-700 ${className}`}>
      <svg
        className="h-3.5 w-3.5 text-blue-500"
        fill="currentColor"
        viewBox="0 0 20 20"
      >
        <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM15.657 14.243a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM11 17a1 1 0 102 0v-1a1 1 0 10-2 0v1zM5.757 15.657a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM2 10a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.757 4.343a1 1 0 00-1.414 1.414l.707.707a1 1 0 001.414-1.414l-.707-.707z" />
      </svg>
      <span title={`${formattedProvider}: ${llmInfo.model}`}>
        {formattedProvider}: {displayModel}
      </span>
    </div>
  );
}

