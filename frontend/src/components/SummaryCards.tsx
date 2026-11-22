import React from 'react';
import { ArrowUpRight, ArrowDownLeft, Users, Receipt, AlertCircle, RefreshCw } from 'lucide-react';
import { useStore } from '../context/StoreContext';

export const SummaryCards: React.FC = () => {
  const { summary, summaryLoading, summaryError, refreshSummary, t } = useStore();

  if (summaryLoading && !summary) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="bg-white p-5 rounded-2xl border border-stone-200 animate-pulse space-y-3"
          >
            <div className="h-4 bg-stone-200 rounded w-1/2"></div>
            <div className="h-8 bg-stone-200 rounded w-3/4"></div>
            <div className="h-3 bg-stone-100 rounded w-1/3"></div>
          </div>
        ))}
      </div>
    );
  }

  if (summaryError && !summary) {
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4 flex items-center justify-between text-rose-900">
        <div className="flex items-center gap-3">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
          <span className="text-sm font-medium">{summaryError}</span>
        </div>
        <button
          onClick={() => void refreshSummary()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-100 hover:bg-rose-200 text-rose-900 text-xs font-semibold rounded-lg transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          {t.general.retry}
        </button>
      </div>
    );
  }

  const outstanding = summary?.total_outstanding_balance ?? '0.00';
  const totalPayment = summary?.total_payment ?? '0.00';
  const activeCustomers = summary?.active_customers_count ?? 0;
  const totalTransactions = summary?.total_transactions_count ?? 0;

  // If outstanding is negative, it represents a customer advance payment (overpayment)
  const isAdvancePayment = parseFloat(outstanding) < 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Total Outstanding Udhaar (Credit) */}
      <div className="bg-white p-5 rounded-2xl border border-stone-200/90 shadow-xs hover:border-amber-300 transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
            {t.metrics.outstandingBalance}
          </span>
          <div className="p-2 rounded-xl bg-amber-50 text-amber-700">
            <ArrowUpRight className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl sm:text-3xl font-extrabold text-stone-900 tracking-tight">
            ₹{outstanding}
          </div>
          <div className="text-xs text-stone-500 mt-1 font-medium">
            {isAdvancePayment
              ? 'Merchant owes customers (Advance)'
              : 'Receivable credit from customers'}
          </div>
        </div>
      </div>

      {/* 2. Total Payments Received (Jama) */}
      <div className="bg-white p-5 rounded-2xl border border-stone-200/90 shadow-xs hover:border-emerald-300 transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
            {t.metrics.totalPayments}
          </span>
          <div className="p-2 rounded-xl bg-emerald-50 text-emerald-700">
            <ArrowDownLeft className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl sm:text-3xl font-extrabold text-emerald-700 tracking-tight">
            ₹{totalPayment}
          </div>
          <div className="text-xs text-stone-500 mt-1 font-medium">
            Total cash / UPI collected
          </div>
        </div>
      </div>

      {/* 3. Active Customers */}
      <div className="bg-white p-5 rounded-2xl border border-stone-200/90 shadow-xs hover:border-stone-300 transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
            {t.metrics.activeCustomers}
          </span>
          <div className="p-2 rounded-xl bg-stone-100 text-stone-700">
            <Users className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl sm:text-3xl font-extrabold text-stone-900 tracking-tight">
            {activeCustomers}
          </div>
          <div className="text-xs text-stone-500 mt-1 font-medium">
            Active khata accounts in store
          </div>
        </div>
      </div>

      {/* 4. Total Ledger Transactions */}
      <div className="bg-white p-5 rounded-2xl border border-stone-200/90 shadow-xs hover:border-stone-300 transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">
            {t.metrics.totalTransactions}
          </span>
          <div className="p-2 rounded-xl bg-stone-100 text-stone-700">
            <Receipt className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl sm:text-3xl font-extrabold text-stone-900 tracking-tight">
            {totalTransactions}
          </div>
          <div className="text-xs text-stone-500 mt-1 font-medium">
            Immutable entries in ledger
          </div>
        </div>
      </div>
    </div>
  );
};
