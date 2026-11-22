/**
 * Push-To-Talk Voice Assistant Component.
 * Implements browser microphone capture, audio playback preview, quick Indic voice utterances,
 * intent parsing via Groq LLM, server-side proposal staging, and HITL confirmation card display.
 */

import React, { useState } from 'react';
import {
  Mic,
  MicOff,
  Square,
  Play,
  RotateCcw,
  Sparkles,
  Info,
  Send,
  AlertCircle,
  Volume2,
} from 'lucide-react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { useStore } from '../context/StoreContext';
import { apiClient, ApiError } from '../api/client';
import {
  CustomerDisambiguationCandidate,
  LedgerCommitResponse,
  PendingProposalResponse,
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

export const VoiceAssistant: React.FC = () => {
  const { t, language, addToast } = useStore();
  const recorder = useAudioRecorder();

  const [customTranscript, setCustomTranscript] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeProposal, setActiveProposal] = useState<TransactionProposal | null>(null);
  const [stagedProposal, setStagedProposal] = useState<PendingProposalResponse | null>(null);
  const [lastParsedTranscript, setLastParsedTranscript] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Ambiguity state
  const [ambiguousCustomer, setAmbiguousCustomer] = useState<string | null>(null);
  const [disambiguationCandidates, setDisambiguationCandidates] = useState<CustomerDisambiguationCandidate[]>([]);

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

  // Filter examples based on current UI language
  const relevantExamples = quickExamples.filter(
    (ex) => ex.lang === language || ex.lang === 'en'
  );

  // Send a transcript to the backend intent parser and stage it
  const handleProcessTranscript = async (textToProcess: string) => {
    const cleanText = textToProcess.trim();
    if (!cleanText) {
      setErrorMessage('Please provide or speak a voice command.');
      return;
    }

    setIsProcessing(true);
    setErrorMessage(null);
    setActiveProposal(null);
    setStagedProposal(null);
    setAmbiguousCustomer(null);

    try {
      // 1. Authoritative Intent Parsing via Groq LLM
      const parseRes = await apiClient.parseIntent(cleanText, 'indic-auto');
      setLastParsedTranscript(cleanText);
      setActiveProposal(parseRes.proposal);

      const prop = parseRes.proposal;

      // 2. If proposal is executable financial intent (ADD_CREDIT or LOG_PAYMENT), stage it on the server
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
            // Check for customer ambiguity
            await checkCustomerAmbiguity(prop.customer_name);
          } else {
            const msg = stageErr instanceof Error ? stageErr.message : 'Failed to stage proposal';
            setErrorMessage(msg);
          }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Voice intent parsing failed';
      setErrorMessage(msg);
      addToast({
        type: 'error',
        title: 'Parsing Error',
        message: msg,
      });
    } finally {
      setIsProcessing(false);
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
    setIsProcessing(true);

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
      setErrorMessage(msg);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCreateNewCustomerForProposal = async (name: string, phone?: string) => {
    if (!activeProposal || !lastParsedTranscript) return;

    setIsProcessing(true);
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
      setErrorMessage(msg);
    } finally {
      setIsProcessing(false);
    }
  };

  // Mic Button Toggle
  const handleMicToggle = async () => {
    if (recorder.recordingState === 'RECORDING') {
      await recorder.stopRecording();
    } else {
      await recorder.startRecording();
    }
  };

  return (
    <div className="space-y-6">
      {/* Voice Assistant Hero Banner */}
      <div className="bg-white rounded-3xl border border-stone-200/90 p-6 sm:p-8 shadow-sm space-y-6">
        <div className="text-center max-w-xl mx-auto space-y-2">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-stone-900 tracking-tight">
            {t.voice.pressToTalk}
          </h2>
          <p className="text-sm text-stone-600">
            Record customer credit (udhaar) or payments (jama) with your voice in Kannada, Hindi, or English.
          </p>
        </div>

        {/* Central Push-To-Talk Button with Visual Feedback */}
        <div className="flex flex-col items-center justify-center py-4">
          <div className="relative">
            {/* Pulsating Radar Rings when RECORDING */}
            {recorder.recordingState === 'RECORDING' && (
              <>
                <span className="absolute -inset-4 rounded-full bg-rose-500/20 animate-ping" />
                <span className="absolute -inset-8 rounded-full bg-rose-500/10 animate-pulse" />
              </>
            )}

            <button
              onClick={() => void handleMicToggle()}
              disabled={isProcessing}
              aria-label={
                recorder.recordingState === 'RECORDING'
                  ? t.voice.releaseToStop
                  : t.voice.pressToTalk
              }
              className={`relative z-10 h-28 w-28 sm:h-32 sm:w-32 rounded-full flex flex-col items-center justify-center shadow-xl transition-all transform active:scale-95 focus:outline-none focus:ring-4 focus:ring-amber-500/40 ${
                recorder.recordingState === 'RECORDING'
                  ? 'bg-rose-600 hover:bg-rose-700 text-white shadow-rose-600/30'
                  : 'bg-amber-600 hover:bg-amber-700 text-white shadow-amber-600/30'
              }`}
            >
              {recorder.recordingState === 'RECORDING' ? (
                <>
                  <Square className="h-10 w-10 fill-current animate-pulse" />
                  <span className="text-[11px] font-bold uppercase tracking-wider mt-1.5">
                    {recorder.durationSeconds}s
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

          {/* Status announcement */}
          <div className="mt-4 text-center">
            {recorder.recordingState === 'RECORDING' && (
              <div className="inline-flex items-center gap-2 text-rose-600 font-bold text-sm animate-pulse">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-600" />
                <span>{t.voice.listening} ({recorder.durationSeconds}s)</span>
              </div>
            )}
            {recorder.recordingState === 'STOPPING' && (
              <span className="text-stone-600 text-sm font-medium">Stopping recording...</span>
            )}
            {recorder.recordingState === 'TRANSCRIPT_READY' && recorder.audioUrl && (
              <div className="flex flex-col items-center gap-2 mt-2">
                <span className="text-emerald-700 text-xs font-bold uppercase tracking-wider">
                  Audio Captured ({recorder.audioBlob ? (recorder.audioBlob.size / 1024).toFixed(1) : 0} KB)
                </span>
                {/* Audio playback preview */}
                <div className="flex items-center gap-2 bg-stone-100 p-2 rounded-xl border border-stone-200">
                  <Volume2 className="h-4 w-4 text-stone-600 ml-1" />
                  <audio controls src={recorder.audioUrl} className="h-8 max-w-[220px]" />
                  <button
                    onClick={recorder.cancelRecording}
                    className="p-1.5 text-stone-500 hover:text-stone-800 rounded-lg hover:bg-stone-200"
                    title={t.voice.discardAudio}
                  >
                    <RotateCcw className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
            {recorder.errorMessage && (
              <div className="mt-2 p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs sm:text-sm font-medium flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                <span>{recorder.errorMessage}</span>
              </div>
            )}
          </div>
        </div>

        {/* Phase 5 Audio Streaming Note */}
        <div className="bg-amber-50/60 border border-amber-200/80 rounded-2xl p-3.5 flex items-start gap-2.5 text-xs text-amber-900">
          <Info className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Phase 4 Voice Contract: </span>
            {t.voice.phase5Notice}
          </div>
        </div>

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
                disabled={isProcessing}
                className="inline-flex items-center gap-1.5 px-3 py-2 bg-stone-50 hover:bg-amber-50 hover:border-amber-300 text-stone-800 text-xs font-medium rounded-xl border border-stone-200/80 transition-all text-left"
              >
                <Sparkles className="h-3 w-3 text-amber-600 shrink-0" />
                <span>{ex.text}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Custom Text / Utterance Input */}
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
              disabled={isProcessing || !customTranscript.trim()}
              className="inline-flex items-center gap-2 px-5 py-3 bg-amber-600 hover:bg-amber-700 text-white text-sm font-bold rounded-xl shadow-sm transition-all disabled:opacity-50 min-h-[48px]"
            >
              {isProcessing ? (
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

        {/* Local Error Message */}
        {errorMessage && (
          <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs sm:text-sm font-medium flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
        )}
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
            // Leave card in committed state so merchant sees receipt
          }}
          onRejected={(_id: string) => {
            // Leave card in rejected state
          }}
          onCancel={() => {
            setActiveProposal(null);
            setStagedProposal(null);
            setLastParsedTranscript(null);
          }}
          onAmbiguityDetected={(custName) => void checkCustomerAmbiguity(custName)}
        />
      )}
    </div>
  );
};
