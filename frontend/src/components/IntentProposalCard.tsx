/**
 * Human-In-The-Loop (HITL) Confirmation Card.
 * The central financial safety component of BolKhata AI.
 * Displays authoritative server-staged proposals, prevents client tampering,
 * enforces stable idempotency keys, and blocks financial commits on read-only intents.
 */

import React, { useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  Check,
  X,
  Clock,
  User,
  ArrowUpRight,
  ArrowDownLeft,
  HelpCircle,
  Eye,
  AlertCircle,
  RotateCcw,
} from 'lucide-react';
import {
  CanonicalIntent,
  LedgerCommitResponse,
  PendingProposalResponse,
  TransactionProposal,
} from '../types/api';
import { apiClient, ApiError } from '../api/client';
import { useStore } from '../context/StoreContext';

interface IntentProposalCardProps {
  proposal: TransactionProposal;
  stagedProposal?: PendingProposalResponse | null;
  onCommitted: (result: LedgerCommitResponse) => void;
  onRejected: (proposalId: string) => void;
  onCancel: () => void;
  onAmbiguityDetected?: (customerName: string) => void;
}

export const IntentProposalCard: React.FC<IntentProposalCardProps> = ({
  proposal,
  stagedProposal,
  onCommitted,
  onRejected,
  onCancel,
  onAmbiguityDetected,
}) => {
  const { t, addToast, refreshSummary } = useStore();

  const [isCommitting, setIsCommitting] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [committedResult, setCommittedResult] = useState<LedgerCommitResponse | null>(null);
  const [isRejectedLocally, setIsRejectedLocally] = useState(false);

  // Maintain a stable idempotency key for this confirmation attempt
  const [stableIdempotencyKey] = useState<string>(
    () => `frontend_commit_${stagedProposal?.proposal_id || proposal.proposal_id}_${Date.now()}`
  );

  const intent = proposal.intent;
  const isAddCredit = intent === 'ADD_CREDIT';
  const isLogPayment = intent === 'LOG_PAYMENT' || intent === 'RECORD_PAYMENT';
  const isReadOnly = intent === 'QUERY_BALANCE' || intent === 'CHECK_BALANCE' || intent === 'LIST_DUES' || intent === 'LIST_RECENT_TRANSACTIONS';
  const isUnknown = intent === 'UNKNOWN' || proposal.requires_clarification;

  // Amount formatting
  const displayAmount = stagedProposal?.amount || proposal.amount || '0.00';
  const displayCustomer = stagedProposal?.customer_name || proposal.customer_name || 'Unknown Customer';

  // --- Confirm Action ---
  const handleConfirm = async () => {
    if (!stagedProposal) {
      setErrorMessage('Proposal must be staged on the server before confirming.');
      return;
    }

    if (isCommitting || committedResult) return;

    setIsCommitting(true);
    setErrorMessage(null);

    try {
      const commitRes = await apiClient.commitProposal({
        proposal_id: stagedProposal.proposal_id,
        confirmed: true,
        idempotency_key: stableIdempotencyKey,
        actor_type: 'merchant',
      });

      setCommittedResult(commitRes);
      onCommitted(commitRes);
      void refreshSummary();

      if (commitRes.is_duplicate) {
        addToast({
          type: 'info',
          title: t.proposal.replayNotice,
          message: `Transaction ${commitRes.transaction_id.slice(0, 8)} was already recorded. Replay returned safely.`,
        });
      } else {
        addToast({
          type: 'success',
          title: t.proposal.statusCommitted,
          message: `₹${commitRes.amount} ${commitRes.entry_type === 'CREDIT' ? 'credit added' : 'payment logged'} for ${commitRes.customer_name}. Resulting balance: ₹${commitRes.resulting_balance}`,
        });
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 409 && err.detail.toLowerCase().includes('multiple customers')) {
          if (onAmbiguityDetected) {
            onAmbiguityDetected(displayCustomer);
            return;
          }
        }
        setErrorMessage(err.detail);
        addToast({
          type: 'error',
          title: 'Commit Failed',
          message: err.detail,
        });
      } else {
        const msg = err instanceof Error ? err.message : 'Unknown commit failure';
        setErrorMessage(msg);
      }
    } finally {
      setIsCommitting(false);
    }
  };

  // --- Reject Action ---
  const handleReject = async () => {
    if (!stagedProposal) {
      onCancel();
      return;
    }

    if (isRejecting || committedResult) return;

    setIsRejecting(true);
    setErrorMessage(null);

    try {
      await apiClient.rejectProposal(stagedProposal.proposal_id, 'Rejected by merchant in frontend UI');
      setIsRejectedLocally(true);
      onRejected(stagedProposal.proposal_id);
      addToast({
        type: 'warning',
        title: t.proposal.statusRejected,
        message: `Proposal ${stagedProposal.proposal_id.slice(0, 8)} was canceled.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to reject proposal';
      setErrorMessage(msg);
    } finally {
      setIsRejecting(false);
    }
  };

  // --- Render Intent Badge ---
  const renderIntentBadge = (i: CanonicalIntent) => {
    if (i === 'ADD_CREDIT') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
          <ArrowUpRight className="h-3.5 w-3.5" />
          {t.customer.entryCredit} (Udhaar)
        </span>
      );
    }
    if (i === 'LOG_PAYMENT' || i === 'RECORD_PAYMENT') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-900 border border-emerald-300">
          <ArrowDownLeft className="h-3.5 w-3.5" />
          {t.customer.entryPayment} (Jama)
        </span>
      );
    }
    if (i === 'QUERY_BALANCE' || i === 'CHECK_BALANCE') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-sky-100 text-sky-900 border border-sky-300">
          <Eye className="h-3.5 w-3.5" />
          Check Balance
        </span>
      );
    }
    if (i === 'LIST_DUES' || i === 'LIST_RECENT_TRANSACTIONS') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-indigo-100 text-indigo-900 border border-indigo-300">
          <Eye className="h-3.5 w-3.5" />
          List Dues
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-900 border border-rose-300">
        <HelpCircle className="h-3.5 w-3.5" />
        Clarification Needed
      </span>
    );
  };

  return (
    <div
      role="region"
      aria-labelledby="proposal-card-title"
      className="bg-white border-2 border-stone-200/90 rounded-2xl p-5 sm:p-6 shadow-md transition-all space-y-5"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-stone-100 pb-4">
        <div className="flex items-center gap-2.5">
          <div
            className={`p-2 rounded-xl ${
              isAddCredit
                ? 'bg-amber-100 text-amber-800'
                : isLogPayment
                ? 'bg-emerald-100 text-emerald-800'
                : isReadOnly
                ? 'bg-sky-100 text-sky-800'
                : 'bg-rose-100 text-rose-800'
            }`}
          >
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <h2 id="proposal-card-title" className="text-lg font-bold text-stone-900">
              {t.proposal.title}
            </h2>
            <div className="flex items-center gap-2 mt-0.5">
              {renderIntentBadge(intent)}
              {stagedProposal?.expires_at && (
                <span className="text-[11px] text-stone-500 flex items-center gap-1 font-mono">
                  <Clock className="h-3 w-3" />
                  TTL 15m
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Status Pill */}
        <div>
          {committedResult ? (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-emerald-600 text-white shadow-xs">
              <Check className="h-3.5 w-3.5" />
              {t.proposal.statusCommitted}
            </span>
          ) : isRejectedLocally ? (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-rose-600 text-white">
              <X className="h-3.5 w-3.5" />
              {t.proposal.statusRejected}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-amber-500 text-white animate-pulse">
              <ShieldAlert className="h-3.5 w-3.5" />
              {t.proposal.statusPending}
            </span>
          )}
        </div>
      </div>

      {/* Primary Financial Details Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Customer Information */}
        <div className="bg-stone-50 p-4 rounded-xl border border-stone-200/60">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 flex items-center gap-1.5">
            <User className="h-3.5 w-3.5 text-stone-500" />
            {t.proposal.customer}
          </div>
          <div className="text-xl font-bold text-stone-900 mt-1 truncate">
            {displayCustomer}
          </div>
        </div>

        {/* Amount */}
        <div className="bg-stone-50 p-4 rounded-xl border border-stone-200/60">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500">
            {t.proposal.amount}
          </div>
          <div
            className={`text-2xl sm:text-3xl font-extrabold mt-1 tracking-tight ${
              isAddCredit
                ? 'text-amber-800'
                : isLogPayment
                ? 'text-emerald-700'
                : 'text-stone-900'
            }`}
          >
            {isReadOnly ? 'N/A (Query)' : `₹${displayAmount}`}
          </div>
        </div>
      </div>

      {/* Human Readable Summary */}
      <div className="p-3.5 bg-stone-50/80 rounded-xl border border-stone-200/70 text-sm">
        <span className="font-semibold text-stone-700">{t.proposal.actionSummary}: </span>
        <span className="text-stone-900 font-medium">
          {stagedProposal?.summary || proposal.summary}
        </span>
      </div>

      {/* Clarification prompt for UNKNOWN */}
      {isUnknown && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-950 text-sm space-y-2">
          <div className="font-bold flex items-center gap-1.5">
            <HelpCircle className="h-4 w-4 text-rose-600" />
            {proposal.clarification_question || t.proposal.clarificationPrompt}
          </div>
          <div className="text-xs text-rose-800">
            Reasoning: {proposal.reasoning_code}
          </div>
        </div>
      )}

      {/* Read-Only Notice for QUERY_BALANCE / LIST_DUES */}
      {isReadOnly && (
        <div className="p-4 bg-sky-50 border border-sky-200 rounded-xl text-sky-950 text-sm">
          <div className="font-bold flex items-center gap-1.5">
            <Eye className="h-4 w-4 text-sky-600" />
            {t.proposal.readOnlyNotice}
          </div>
          <div className="text-xs text-sky-800 mt-1">
            This query only inspects balances and does not perform any financial debit or credit.
          </div>
        </div>
      )}

      {/* Error Banner */}
      {errorMessage && (
        <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 text-sm flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Replay Notice */}
      {committedResult?.is_duplicate && (
        <div className="p-3.5 bg-blue-50 border border-blue-200 rounded-xl text-blue-900 text-sm flex items-center gap-2">
          <RotateCcw className="h-5 w-5 text-blue-600 shrink-0" />
          <div>
            <div className="font-bold">{t.proposal.replayNotice}</div>
            <div className="text-xs mt-0.5">
              Resulting balance remains ₹{committedResult.resulting_balance}.
            </div>
          </div>
        </div>
      )}

      {/* Post-Commit Summary */}
      {committedResult && !committedResult.is_duplicate && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-950 text-sm space-y-1">
          <div className="font-bold text-emerald-900 flex items-center gap-1.5">
            <Check className="h-4 w-4 text-emerald-600" />
            Transaction Committed to Immutable Ledger
          </div>
          <div className="text-xs text-emerald-800">
            Entry ID: <span className="font-mono">{committedResult.transaction_id}</span>
          </div>
          <div className="text-xs text-emerald-800">
            Updated Outstanding Balance: <span className="font-bold">₹{committedResult.resulting_balance}</span>
          </div>
        </div>
      )}

      {/* Merchant Actions Bar */}
      <div className="pt-2 flex flex-wrap items-center justify-between gap-3">
        {committedResult || isRejectedLocally ? (
          <button
            onClick={onCancel}
            className="w-full sm:w-auto px-5 py-2.5 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-sm font-semibold transition-colors"
          >
            {t.general.dismiss}
          </button>
        ) : isReadOnly || isUnknown ? (
          <button
            onClick={onCancel}
            className="w-full sm:w-auto px-5 py-2.5 bg-stone-200 hover:bg-stone-300 text-stone-900 rounded-xl text-sm font-semibold transition-colors"
          >
            {t.general.dismiss}
          </button>
        ) : (
          <>
            {/* Reject Button */}
            <button
              onClick={() => void handleReject()}
              disabled={isRejecting || isCommitting}
              className="px-4 py-2.5 border border-stone-300 hover:bg-rose-50 hover:border-rose-300 text-stone-700 hover:text-rose-700 rounded-xl text-sm font-semibold transition-colors disabled:opacity-50"
            >
              {isRejecting ? 'Rejecting...' : t.proposal.rejectButton}
            </button>

            {/* Confirm Button */}
            <button
              onClick={() => void handleConfirm()}
              disabled={isCommitting || isRejecting}
              className={`flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-bold text-white shadow-md transition-all disabled:opacity-50 min-h-[48px] ${
                isAddCredit
                  ? 'bg-amber-600 hover:bg-amber-700 shadow-amber-600/20'
                  : 'bg-emerald-600 hover:bg-emerald-700 shadow-emerald-600/20'
              }`}
            >
              {isCommitting ? (
                <>
                  <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>{t.proposal.confirming}</span>
                </>
              ) : (
                <>
                  <Check className="h-4 w-4 stroke-[3]" />
                  <span>{t.proposal.confirmButton}</span>
                </>
              )}
            </button>
          </>
        )}
      </div>
    </div>
  );
};
