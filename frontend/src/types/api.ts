/**
 * Strongly typed TypeScript definitions for BolKhata AI.
 * Perfectly mapped to backend Pydantic models in Phase 2, 3, and 3.1.
 */

export type CanonicalIntent =
  | 'ADD_CREDIT'
  | 'LOG_PAYMENT'
  | 'RECORD_PAYMENT' // Alias for backward compatibility
  | 'QUERY_BALANCE'
  | 'CHECK_BALANCE'
  | 'LIST_DUES'
  | 'LIST_RECENT_TRANSACTIONS'
  | 'UNKNOWN';

export type EntryType = 'CREDIT' | 'PAYMENT';

export type ProposalStatus = 'PENDING' | 'COMMITTED' | 'REJECTED' | 'EXPIRED';

export type SupportedLanguage = 'kn' | 'hi' | 'en';

export type AudioRecordingState =
  | 'IDLE'
  | 'RECORDING'
  | 'STOPPING'
  | 'PROCESSING'
  | 'TRANSCRIPT_READY'
  | 'ERROR';

export interface BackendHealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp?: string;
  environment?: string;
  languages_supported?: string[];
}

export interface TransactionProposal {
  proposal_id: string;
  intent: CanonicalIntent;
  customer_name?: string | null;
  amount?: string | null; // Formatted as Decimal string e.g. "340.00"
  currency: string; // Must be "INR"
  language?: string | null;
  confidence: number;
  requires_clarification: boolean;
  requires_confirmation: boolean;
  clarification_question?: string | null;
  summary: string;
  reasoning_code: string;
}

export interface ParseIntentResponse {
  success: boolean;
  original_transcript: string;
  proposal: TransactionProposal;
  error?: string | null;
}

export interface StageProposalRequest {
  customer_name: string;
  intent: CanonicalIntent;
  amount: string; // Positive decimal string e.g. "340.00"
  currency?: string;
  customer_id?: string | null;
  phone_number?: string | null;
  summary?: string | null;
  raw_transcript?: string | null;
  proposal_id?: string | null;
}

export interface PendingProposalResponse {
  proposal_id: string;
  store_id: string;
  customer_name: string;
  intent: string;
  amount: string;
  currency: string;
  summary: string;
  status: ProposalStatus;
  requires_confirmation: boolean;
  created_at: string;
  expires_at: string;
}

export interface CommitProposalRequest {
  proposal_id: string;
  confirmed: boolean;
  idempotency_key?: string;
  actor_type?: string;
  actor_id?: string | null;
  notes?: string | null;
}

export interface LedgerCommitResponse {
  transaction_id: string;
  store_id: string;
  customer_id: string;
  customer_name: string;
  entry_type: EntryType;
  amount: string;
  currency: string;
  resulting_balance: string;
  total_credit: string;
  total_payment: string;
  created_at: string;
  is_duplicate: boolean;
  proposal_id?: string | null;
  idempotency_key: string;
}

export interface Customer {
  id: string;
  store_id: string;
  customer_name: string;
  normalized_name: string;
  phone_number?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerListResponse {
  customers: Customer[];
  total: number;
}

export interface CustomerCreateRequest {
  customer_name: string;
  phone_number?: string | null;
}

export interface CustomerBalanceResponse {
  customer_id: string;
  customer_name: string;
  currency: string;
  total_credit: string;
  total_payment: string;
  outstanding_balance: string;
}

export interface KhataEntryResponse {
  id: string;
  store_id: string;
  customer_id: string;
  entry_type: EntryType;
  amount: string;
  currency: string;
  description?: string | null;
  idempotency_key: string;
  proposal_id?: string | null;
  created_at: string;
  created_by: string;
}

export interface CustomerEntriesResponse {
  customer_id: string;
  customer_name: string;
  currency: string;
  entries: KhataEntryResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface StoreSummaryResponse {
  store_id: string;
  store_name: string;
  currency: string;
  total_credit: string;
  total_payment: string;
  total_outstanding_balance: string;
  active_customers_count: number;
  total_transactions_count: number;
}

export interface CustomerDisambiguationCandidate {
  id: string;
  customer_name: string;
  phone_number?: string | null;
  created_at: string;
}

export interface CustomerDisambiguationResponse {
  message: string;
  candidates: CustomerDisambiguationCandidate[];
}

export type VoiceStreamStatus =
  | 'disconnected'
  | 'connecting'
  | 'ready'
  | 'recording'
  | 'processing'
  | 'playing_tts'
  | 'error';

export interface VoiceStreamStartedEvent {
  event: 'SESSION_STARTED';
  session_id: string;
  store_id: string;
  sample_rate: number;
  format: string;
  channels: number;
  language: string;
}

export interface VoicePartialTranscriptEvent {
  event: 'PARTIAL_TRANSCRIPT';
  session_id: string;
  transcript: string;
  is_final: false;
  language?: string;
}

export interface VoiceFinalTranscriptEvent {
  event: 'FINAL_TRANSCRIPT';
  session_id: string;
  transcript: string;
  is_final: true;
  language?: string;
  confidence?: number;
}

export interface VoiceProcessingEvent {
  event: 'PROCESSING';
  session_id: string;
  status: string;
}

export interface VoiceProposalReadyEvent {
  event: 'PROPOSAL_READY';
  session_id: string;
  proposal: TransactionProposal;
  staged_proposal: PendingProposalResponse;
  spoken_response: string;
  audio_b64?: string | null;
  audio_format: string;
}

export interface VoiceReadOnlyResponseEvent {
  event: 'READ_ONLY_RESPONSE';
  session_id: string;
  intent: string;
  data: Record<string, any>;
  spoken_response: string;
  audio_b64?: string | null;
  audio_format: string;
}

export interface VoiceClarificationRequiredEvent {
  event: 'CLARIFICATION_REQUIRED';
  session_id: string;
  transcript: string;
  spoken_response: string;
  audio_b64?: string | null;
  audio_format: string;
}

export interface VoiceTTSAudioEvent {
  event: 'TTS_AUDIO';
  session_id: string;
  audio_b64: string;
  audio_format: string;
  text?: string;
}

export interface VoiceErrorEvent {
  event: 'ERROR';
  session_id?: string;
  code: string;
  message: string;
}

export type VoiceServerEvent =
  | VoiceStreamStartedEvent
  | VoicePartialTranscriptEvent
  | VoiceFinalTranscriptEvent
  | VoiceProcessingEvent
  | VoiceProposalReadyEvent
  | VoiceReadOnlyResponseEvent
  | VoiceClarificationRequiredEvent
  | VoiceTTSAudioEvent
  | VoiceErrorEvent;

