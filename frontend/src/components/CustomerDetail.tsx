import React, { useEffect, useState, useCallback } from 'react';
import { ArrowLeft, User, Phone, Calendar, RefreshCw, AlertCircle } from 'lucide-react';
import { Customer, CustomerBalanceResponse, KhataEntryResponse } from '../types/api';
import { apiClient } from '../api/client';
import { useStore } from '../context/StoreContext';
import { LedgerHistory } from './LedgerHistory';

interface CustomerDetailProps {
  customer: Customer;
  onBack: () => void;
}

export const CustomerDetail: React.FC<CustomerDetailProps> = ({ customer, onBack }) => {
  const { t } = useStore();

  const [balance, setBalance] = useState<CustomerBalanceResponse | null>(null);
  const [entries, setEntries] = useState<KhataEntryResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchCustomerData = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const [balRes, entriesRes] = await Promise.all([
        apiClient.getCustomerBalance(customer.id),
        apiClient.getCustomerEntries(customer.id, 50, 0),
      ]);
      setBalance(balRes);
      setEntries(entriesRes.entries);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load customer ledger';
      setErrorMessage(msg);
    } finally {
      setLoading(false);
    }
  }, [customer.id]);

  useEffect(() => {
    void fetchCustomerData();
  }, [fetchCustomerData]);

  const outstanding = balance?.outstanding_balance || '0.00';
  const isAdvance = parseFloat(outstanding) < 0;

  return (
    <div className="space-y-6">
      {/* Top Bar with Back Navigation */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-stone-100 text-stone-700 text-sm font-semibold rounded-xl border border-stone-200 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Customers</span>
        </button>

        <button
          onClick={() => void fetchCustomerData()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-stone-100 hover:bg-stone-200 text-stone-800 text-xs font-semibold rounded-lg transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>{t.nav.refresh}</span>
        </button>
      </div>

      {/* Customer Header Card */}
      <div className="bg-white border border-stone-200/90 rounded-2xl p-5 sm:p-6 shadow-sm space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3.5">
            <div className="h-14 w-14 rounded-2xl bg-amber-100 text-amber-800 flex items-center justify-center font-bold text-2xl shadow-xs">
              {customer.customer_name.charAt(0).toUpperCase()}
            </div>
            <div>
              <h2 className="text-xl sm:text-2xl font-bold text-stone-900">
                {customer.customer_name}
              </h2>
              <div className="flex items-center gap-3 text-xs text-stone-500 mt-1 flex-wrap font-medium">
                {customer.phone_number && (
                  <span className="flex items-center gap-1">
                    <Phone className="h-3.5 w-3.5" />
                    {customer.phone_number}
                  </span>
                )}
                <span className="flex items-center gap-1 font-mono">
                  <Calendar className="h-3.5 w-3.5" />
                  Added {new Date(customer.created_at).toLocaleDateString()}
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                  Active Khata
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 3 Metric Summary Boxes */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 border-t border-stone-100">
          <div className="bg-stone-50 p-3.5 rounded-xl border border-stone-200/60">
            <span className="text-xs font-semibold uppercase text-stone-500">
              {t.customer.currentBalance}
            </span>
            <div
              className={`text-2xl font-extrabold mt-1 tracking-tight ${
                isAdvance ? 'text-emerald-700' : 'text-stone-900'
              }`}
            >
              ₹{outstanding}
            </div>
            <div className="text-[11px] text-stone-500 mt-0.5">
              {isAdvance ? 'Advance payment (Credit balance)' : 'Receivable credit'}
            </div>
          </div>

          <div className="bg-stone-50 p-3.5 rounded-xl border border-stone-200/60">
            <span className="text-xs font-semibold uppercase text-stone-500">
              {t.customer.totalCredit}
            </span>
            <div className="text-2xl font-extrabold text-amber-800 mt-1 tracking-tight">
              ₹{balance?.total_credit || '0.00'}
            </div>
            <div className="text-[11px] text-stone-500 mt-0.5">Total credit given</div>
          </div>

          <div className="bg-stone-50 p-3.5 rounded-xl border border-stone-200/60">
            <span className="text-xs font-semibold uppercase text-stone-500">
              {t.customer.totalPayment}
            </span>
            <div className="text-2xl font-extrabold text-emerald-700 mt-1 tracking-tight">
              ₹{balance?.total_payment || '0.00'}
            </div>
            <div className="text-[11px] text-stone-500 mt-0.5">Total payments collected</div>
          </div>
        </div>
      </div>

      {/* Error Notice */}
      {errorMessage && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 text-sm flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Ledger Entries Section */}
      <div className="bg-white border border-stone-200/90 rounded-2xl p-5 sm:p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-stone-100 pb-3">
          <h3 className="text-base font-bold text-stone-900">
            {t.customer.ledgerHistory} ({entries.length})
          </h3>
          <span className="text-xs text-stone-500">
            Append-only immutable entries
          </span>
        </div>

        <LedgerHistory entries={entries} loading={loading} />
      </div>
    </div>
  );
};
