/**
 * Push-To-Talk Voice Assistant Component with Real-Time Streaming & HITL Confirmation.
 *
 * Implements:
 * - Real-time bidirectional streaming over WebSocket (/api/v1/voice/stream)
 * - 16kHz S16LE PCM microphone audio capture & downsampling
 * - Real-time partial transcript streaming as words are spoken
 * - Automatic Groq LLM intent parsing & proposal staging
 * - Immediate Gnani Timbre v3.0 localized TTS audio confirmation with interruption support
 * - HITL Proposal Card for explicit Merchant Confirmation before any ledger mutation
 * - Read-only query response card for balance checks with 0 ledger side-effects
 * - Clarification prompt cards for unknown or ambiguous intents
 * - Quick Indic voice command pills and text input fallback
 */

import React, { useState, useEffect } from 'react';
import {
  Mic,
  Square,
  Sparkles,
  Send,
  AlertCircle,
  Volume2,
  VolumeX,
  HelpCircle,
  CheckCircle2,
  Radio,
} from 'lucide-react';
import { useStore } from '../context/StoreContext';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { apiClient, ApiError } from '../api/client';
import {
  CustomerDisambiguationCandidate,
  LedgerCommitResponse,
  PendingProposalResponse,
  SupportedLanguage,
  TransactionProposal,
} from '../types/api';
import { TranscriptPreview } from './TranscriptPreview';
import { IntentProposalCard } from './IntentProposalCard';
import { CustomerDisambiguation } from './CustomerDisambiguation';

interface QuickExample {
  lang: string;
  label: string;
  text: string;
}

const LANG_CODE_MAP: Record<SupportedLanguage, string> = {
  kn: 'kn-IN',
  hi: 'hi-IN',
  en: 'en-IN',
};

export const VoiceAssistant: React.FC = () => {
  const { t, language, storeId, addToast } = useStore();
  const langCode = LANG_CODE_MAP[language] || 'kn-IN';

  // Initialize real-time WebSocket streaming hook
  const voiceWs = useVoiceWebSocket({
    storeId,
    language: langCode,
    autoConnect: false,
  });

  const [customTranscript, setCustomTranscript] = useState('');
  const [isProcessingManual, setIsProcessingManual] = useState(false);
  const [activeProposal, setActiveProposal] = useState<TransactionProposal | null>(null);
  const [stagedProposal, setStagedProposal] = useState<PendingProposalResponse | null>(null);
  const [lastParsedTranscript, setLastParsedTranscript] = useState<string | null>(null);
  const [manualErrorMessage, setManualErrorMessage] = useState<string | null>(null);

  // Ambiguity state
  const [ambiguousCustomer, setAmbiguousCustomer] = useState<string | null>(null);
  const [disambiguationCandidates, setDisambiguationCandidates] = useState<CustomerDisambiguationCandidate[]>([]);

  // Synchronize WebSocket events to active proposal state
  useEffect(() => {
    if (voiceWs.proposalReady) {
      setActiveProposal(voiceWs.proposalReady.proposal);
      setStagedProposal(voiceWs.proposalReady.staged_proposal);
      setLastParsedTranscript(voiceWs.finalTranscript || voiceWs.proposalReady.proposal.summary);
      setAmbiguousCustomer(null);
    }
  }, [voiceWs.proposalReady, voiceWs.finalTranscript]);

  // Indic sample utterances
  const quickExamples: QuickExample[] = [
    {
      lang: 'kn',
      label: 'ಉದಾರ್ (+ ₹340)',
      text: 'ರಮೇಶ್ ಗೆ 340 ರೂಪಾಯಿ ಉದಾರ್ ಬರೆಯಿರಿ.',
    },
    {
      lang: 'kn',
      label: 'ಜಮಾ (- ₹100)',
      text: 'ರಮೇಶ್ 100 ರೂಪಾಯಿ ಜಮಾ ಕೊಟ್ಟಿದ್ದಾರೆ.',
    },
    {
      lang: 'hi',
      label: 'उधार (+ ₹340)',
      text: 'रमेश के नाम 340 रुपये उधार लिखो।',
    },
    {
      lang: 'hi',
      label: 'जमा (- ₹100)',
      text: 'सुरेश ने 100 रुपये जमा किए।',
    },
    {
      lang: 'en',
      label: 'Credit (+ ₹340)',
      text: 'Add 340 rupees credit for Ramesh.',
    },
    {
      lang: 'en',
      label: 'Payment (- ₹500)',
      text: 'Log payment of 500 rupees from Ramesh.',
    },
    {
      lang: 'en',
      label: 'Check Balance',
      text: 'Check balance of Ramesh Kumar.',
    },
  ];

  const relevantExamples = quickExamples.filter(
    (ex) => ex.lang === language || ex.lang === 'en'
  );

  // Send a manual transcript or example pill to backend
  const handleProcessTranscript = async (textToProcess: string) => {
    const cleanText = textToProcess.trim();
    if (!cleanText) {
      setManualErrorMessage('Please provide or speak a voice command.');
      return;
    }

    setIsProcessingManual(true);
    setManualErrorMessage(null);
    voiceWs.clearProposal();
    setActiveProposal(null);
    setStagedProposal(null);
    setAmbiguousCustomer(null);

    try {
      const parseRes = await apiClient.parseIntent(cleanText, langCode);
      setLastParsedTranscript(cleanText);
      setActiveProposal(parseRes.proposal);

      const prop = parseRes.proposal;

      if (
        (prop.intent === 'ADD_CREDIT' || prop.intent === 'LOG_PAYMENT' || prop.intent === 'RECORD_PAYMENT') &&
        prop.customer_name &&
        prop.amount
      ) {
        try {
          const staged = await apiClient.stageProposal({
            customer_name: prop.customer_name,
            intent: prop.intent,
            amount: prop.amount,
            currency: prop.currency,
            summary: prop.summary,
            raw_transcript: cleanText,
            proposal_id: prop.proposal_id,
          });
          setStagedProposal(staged);
        } catch (stageErr: unknown) {
          if (stageErr instanceof ApiError && stageErr.status === 409) {
            await checkCustomerAmbiguity(prop.customer_name);
          } else {
            const msg = stageErr instanceof Error ? stageErr.message : 'Failed to stage proposal';
            setManualErrorMessage(msg);
          }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Voice intent parsing failed';
      setManualErrorMessage(msg);
      addToast({
        type: 'error',
        title: 'Parsing Error',
        message: msg,
      });
    } finally {
      setIsProcessingManual(false);
    }
  };

  const checkCustomerAmbiguity = async (name: string) => {
    try {
      const res = await apiClient.listCustomers(name);
      if (res.customers.length > 1) {
        setAmbiguousCustomer(name);
        setDisambiguationCandidates(
          res.customers.map((c) => ({
            id: c.id,
            customer_name: c.customer_name,
            phone_number: c.phone_number,
            created_at: c.created_at,
          }))
        );
      }
    } catch {
      // Ignore
    }
  };

  const handleSelectAmbiguousCustomer = async (cand: CustomerDisambiguationCandidate) => {
    if (!activeProposal || !lastParsedTranscript) return;

    setAmbiguousCustomer(null);
    setIsProcessingManual(true);

    try {
      const staged = await apiClient.stageProposal({
        customer_name: cand.customer_name,
        customer_id: cand.id,
        intent: activeProposal.intent,
        amount: activeProposal.amount || '0.00',
        currency: activeProposal.currency,
        summary: activeProposal.summary,
        raw_transcript: lastParsedTranscript,
        proposal_id: activeProposal.proposal_id,
      });
      setStagedProposal(staged);
      addToast({
        type: 'success',
        title: 'Customer Disambiguated',
        message: `Linked to ${cand.customer_name} (${cand.phone_number || cand.id.slice(0, 8)})`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to stage proposal';
      setManualErrorMessage(msg);
    } finally {
      setIsProcessingManual(false);
    }
  };

  const handleCreateNewCustomerForProposal = async (name: string, phone?: string) => {
    if (!activeProposal || !lastParsedTranscript) return;

    setIsProcessingManual(true);
    setAmbiguousCustomer(null);

    try {
      const newCust = await apiClient.createCustomer({
        customer_name: name,
        phone_number: phone,
      });

      const staged = await apiClient.stageProposal({
        customer_name: newCust.customer_name,
        customer_id: newCust.id,
        intent: activeProposal.intent,
        amount: activeProposal.amount || '0.00',
        currency: activeProposal.currency,
        summary: activeProposal.summary,
        raw_transcript: lastParsedTranscript,
        proposal_id: activeProposal.proposal_id,
      });
      setStagedProposal(staged);
      addToast({
        type: 'success',
        title: 'New Customer Created',
        message: `Registered ${newCust.customer_name} and staged proposal.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create customer';
      setManualErrorMessage(msg);
    } finally {
      setIsProcessingManual(false);
    }
  };

  // Push-To-Talk Handlers (Click or Hold)
  const isStreamingRecording = voiceWs.status === 'recording';
  const isStreamingProcessing = voiceWs.status === 'processing';
  const isGlobalProcessing = isProcessingManual || isStreamingProcessing;

  const handleMicMouseDown = async () => {
    if (isStreamingRecording) {
      voiceWs.stopStreaming();
    } else {
      await voiceWs.startStreaming();
    }
  };

  return (
    <div className="space-y-6">
      {/* Voice Assistant Hero Banner */}
      <div className="bg-white rounded-3xl border border-stone-200/90 p-6 sm:p-8 shadow-sm space-y-6">
        <div className="text-center max-w-xl mx-auto space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-50 border border-amber-200 rounded-full text-xs font-bold text-amber-800">
            <Radio className="h-3.5 w-3.5 text-amber-600 animate-pulse" />
            <span>Real-time Voice Streaming (Gnani Prisma v3.0)</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-stone-900 tracking-tight">
            {t.voice.pressToTalk}
          </h2>
          <p className="text-sm text-stone-600">
            Hold or tap the microphone to speak your transaction in Kannada, Hindi, or English.
          </p>
        </div>

        {/* Central Push-To-Talk Button with Live Visual Feedback */}
        <div className="flex flex-col items-center justify-center py-4">
          <div className="relative">
            {/* Pulsating Radar Rings when RECORDING */}
            {isStreamingRecording && (
              <>
                <span className="absolute -inset-4 rounded-full bg-rose-500/25 animate-ping" />
                <span className="absolute -inset-8 rounded-full bg-rose-500/15 animate-pulse" />
              </>
            )}

            <button
              onClick={() => void handleMicMouseDown()}
              disabled={isGlobalProcessing}
              aria-label={
                isStreamingRecording
                  ? t.voice.releaseToStop
                  : t.voice.pressToTalk
              }
              className={`relative z-10 h-28 w-28 sm:h-32 sm:w-32 rounded-full flex flex-col items-center justify-center shadow-xl transition-all transform active:scale-95 focus:outline-none focus:ring-4 focus:ring-amber-500/40 ${
                isStreamingRecording
                  ? 'bg-rose-600 hover:bg-rose-700 text-white shadow-rose-600/40'
                  : 'bg-amber-600 hover:bg-amber-700 text-white shadow-amber-600/30'
              }`}
            >
              {isStreamingRecording ? (
                <>
                  <Square className="h-10 w-10 fill-current animate-pulse" />
                  <span className="text-[11px] font-bold uppercase tracking-wider mt-1.5">
                    Streaming
                  </span>
                </>
              ) : isStreamingProcessing ? (
                <>
                  <div className="h-8 w-8 border-3 border-white border-t-transparent rounded-full animate-spin" />
                  <span className="text-[10px] font-bold uppercase tracking-wider mt-1.5">
                    Parsing
                  </span>
                </>
              ) : (
                <>
                  <Mic className="h-11 w-11" />
                  <span className="text-[11px] font-bold uppercase tracking-wider mt-1">
                    {t.voice.tapToRecord}
                  </span>
                </>
              )}
            </button>
          </div>

          {/* Status announcement and Live Partial Transcript */}
          <div className="mt-4 text-center max-w-lg">
            {isStreamingRecording && (
              <div className="space-y-1.5">
                <div className="inline-flex items-center gap-2 text-rose-600 font-bold text-sm animate-pulse">
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-600" />
                  <span>Listening... (16 kHz Linear PCM)</span>
                </div>
                {voiceWs.partialTranscript && (
                  <p className="text-stone-800 text-base font-semibold italic bg-stone-50 px-4 py-2 rounded-xl border border-stone-200">
                    "{voiceWs.partialTranscript}"
                  </p>
                )}
              </div>
            )}

            {isStreamingProcessing && (
              <div className="inline-flex items-center gap-2 text-amber-700 font-medium text-sm">
                <div className="h-3 w-3 border-2 border-amber-600 border-t-transparent rounded-full animate-spin" />
                <span>Processing utterance through Groq Intent Engine...</span>
              </div>
            )}

            {/* TTS Audio Playback Indicator with Interruption Button */}
            {voiceWs.isPlayingTTS && (
              <div className="mt-2 inline-flex items-center gap-3 px-4 py-2 bg-emerald-50 border border-emerald-200 rounded-full text-emerald-800 text-xs font-semibold shadow-sm animate-pulse">
                <Volume2 className="h-4 w-4 text-emerald-600 shrink-0" />
                <span>Speaking Confirmation (Timbre v3.0)...</span>
                <button
                  onClick={voiceWs.stopAudioPlayback}
                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-white border border-emerald-300 hover:bg-emerald-100 rounded-md text-[11px] text-emerald-900 transition-colors"
                  title="Interrupt speech playback"
                >
                  <VolumeX className="h-3 w-3" />
                  <span>Stop</span>
                </button>
              </div>
            )}

            {/* Error notifications */}
            {(voiceWs.errorMessage || manualErrorMessage) && (
              <div className="mt-2 p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs sm:text-sm font-medium flex items-center gap-2 text-left">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                <span>{voiceWs.errorMessage || manualErrorMessage}</span>
              </div>
            )}
          </div>
        </div>

        {/* Read-Only Query Response (QUERY_BALANCE) */}
        {voiceWs.readOnlyResponse && (
          <div className="bg-sky-50 border border-sky-200 rounded-2xl p-4 sm:p-5 text-sky-900 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-sky-600" />
                <span className="font-bold text-sm">Customer Balance Inquiry (Read-Only)</span>
              </div>
              <span className="text-[11px] font-bold px-2.5 py-0.5 bg-sky-200 text-sky-800 rounded-full">
                0 Database Mutations
              </span>
            </div>
            <p className="text-base font-semibold text-stone-900">
              {voiceWs.readOnlyResponse.spoken_response}
            </p>
            {voiceWs.readOnlyResponse.data?.outstanding_balance && (
              <div className="text-2xl font-black text-sky-800 mt-1">
                ₹{Number(voiceWs.readOnlyResponse.data.outstanding_balance).toFixed(2)}
              </div>
            )}
          </div>
        )}

        {/* Clarification Required Card (UNKNOWN or Incomplete Intent) */}
        {voiceWs.clarification && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 sm:p-5 text-amber-900 space-y-2">
            <div className="flex items-center gap-2">
              <HelpCircle className="h-5 w-5 text-amber-600" />
              <span className="font-bold text-sm">Clarification Required</span>
            </div>
            <p className="text-sm font-medium text-stone-800">
              {voiceWs.clarification.spoken_response}
            </p>
          </div>
        )}

        {/* Quick Voice Command Pills */}
        <div className="space-y-2.5 pt-2 border-t border-stone-100">
          <div className="text-xs font-bold uppercase tracking-wider text-stone-500">
            {t.voice.quickExamples}
          </div>
          <div className="flex flex-wrap gap-2">
            {relevantExamples.map((ex, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setCustomTranscript(ex.text);
                  void handleProcessTranscript(ex.text);
                }}
                disabled={isGlobalProcessing}
                className="inline-flex items-center gap-1.5 px-3 py-2 bg-stone-50 hover:bg-amber-50 hover:border-amber-300 text-stone-800 text-xs font-medium rounded-xl border border-stone-200/80 transition-all text-left"
              >
                <Sparkles className="h-3 w-3 text-amber-600 shrink-0" />
                <span>{ex.text}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Custom Text / Utterance Input Fallback */}
        <div className="pt-2">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void handleProcessTranscript(customTranscript);
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={customTranscript}
              onChange={(e) => setCustomTranscript(e.target.value)}
              placeholder={t.voice.customUtterancePlaceholder}
              className="flex-1 px-4 py-3 bg-stone-50 border border-stone-300 rounded-xl text-sm text-stone-900 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:bg-white transition-all"
            />
            <button
              type="submit"
              disabled={isGlobalProcessing || !customTranscript.trim()}
              className="inline-flex items-center gap-2 px-5 py-3 bg-amber-600 hover:bg-amber-700 text-white text-sm font-bold rounded-xl shadow-sm transition-all disabled:opacity-50 min-h-[48px]"
            >
              {isProcessingManual ? (
                <>
                  <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  <span>{t.voice.parseButton}</span>
                </>
              )}
            </button>
          </form>
        </div>
      </div>

      {/* Customer Disambiguation Prompt (if multiple customers match) */}
      {ambiguousCustomer && disambiguationCandidates.length > 0 && (
        <CustomerDisambiguation
          customerName={ambiguousCustomer}
          candidates={disambiguationCandidates}
          onSelectCustomer={(cand) => void handleSelectAmbiguousCustomer(cand)}
          onCreateNewCustomer={(name, phone) => void handleCreateNewCustomerForProposal(name, phone)}
          onCancel={() => setAmbiguousCustomer(null)}
        />
      )}

      {/* Recognized Transcript Preview */}
      {lastParsedTranscript && activeProposal && (
        <TranscriptPreview
          transcript={lastParsedTranscript}
          language={activeProposal.language}
          confidence={activeProposal.confidence}
        />
      )}

      {/* HITL Confirmation Proposal Card */}
      {activeProposal && (
        <IntentProposalCard
          proposal={activeProposal}
          stagedProposal={stagedProposal}
          onCommitted={(_res: LedgerCommitResponse) => {
            // Keep receipt visible for merchant audit
          }}
          onRejected={(_id: string) => {
            // Keep card in rejected state
          }}
          onCancel={() => {
            setActiveProposal(null);
            setStagedProposal(null);
            setLastParsedTranscript(null);
            voiceWs.clearProposal();
          }}
          onAmbiguityDetected={(custName) => void checkCustomerAmbiguity(custName)}
        />
      )}
    </div>
  );
};
