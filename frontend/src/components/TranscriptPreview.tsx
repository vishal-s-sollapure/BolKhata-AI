import React from 'react';
import { FileText, Sparkles } from 'lucide-react';
import { useStore } from '../context/StoreContext';

interface TranscriptPreviewProps {
  transcript: string;
  language?: string | null;
  confidence?: number;
  onEdit?: (newTranscript: string) => void;
}

export const TranscriptPreview: React.FC<TranscriptPreviewProps> = ({
  transcript,
  language,
  confidence,
}) => {
  const { t } = useStore();

  return (
    <div className="bg-amber-50/70 border border-amber-200/90 rounded-2xl p-4 sm:p-5 shadow-xs">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-amber-700" />
          <span className="text-xs font-bold uppercase tracking-wider text-amber-900">
            Voice Transcript
          </span>
        </div>
        <div className="flex items-center gap-2">
          {language && (
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
              Lang: {language}
            </span>
          )}
          {confidence !== undefined && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
              <Sparkles className="h-3 w-3" />
              {Math.round(confidence * 100)}% Confidence
            </span>
          )}
        </div>
      </div>

      {/* Recognized text */}
      <blockquote className="text-base sm:text-lg font-semibold text-stone-900 italic border-l-4 border-amber-500 pl-3.5 my-2">
        "{transcript}"
      </blockquote>

      <p className="text-xs text-stone-500 mt-2 font-medium">
        {t.proposal.title} — Authoritative parsing performed by Groq AI.
      </p>
    </div>
  );
};
