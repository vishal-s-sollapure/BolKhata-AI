import React from 'react';
import { ArrowUpRight, ArrowDownLeft, Clock, CheckCircle2 } from 'lucide-react';
import { KhataEntryResponse } from '../types/api';
import { useStore } from '../context/StoreContext';

interface LedgerHistoryProps {
  entries: KhataEntryResponse[];
  loading?: boolean;
}

export const LedgerHistory: React.FC<LedgerHistoryProps> = ({ entries, loading }) => {
  const { t } = useStore();

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 bg-stone-100 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="text-center py-8 bg-stone-50 rounded-xl border border-dashed border-stone-200">
        <Clock className="h-8 w-8 text-stone-400 mx-auto mb-2" />
        <p className="text-sm text-stone-500 font-medium">{t.customer.noEntriesFound}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      {entries.map((entry) => {
        const isCredit = entry.entry_type === 'CREDIT';
        const formattedDate = new Date(entry.created_at).toLocaleString();

        return (
          <div
            key={entry.id}
            className="flex items-center justify-between p-3.5 bg-white border border-stone-200/80 rounded-xl hover:border-stone-300 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div
                className={`p-2 rounded-lg ${
                  isCredit
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-emerald-100 text-emerald-800'
                }`}
              >
                {isCredit ? (
                  <ArrowUpRight className="h-4 w-4" />
                ) : (
                  <ArrowDownLeft className="h-4 w-4" />
                )}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-bold px-2 py-0.5 rounded-md ${
                      isCredit
                        ? 'bg-amber-50 text-amber-900 border border-amber-200'
                        : 'bg-emerald-50 text-emerald-900 border border-emerald-200'
                    }`}
                  >
                    {isCredit ? t.customer.entryCredit : t.customer.entryPayment}
                  </span>
                  {entry.description && (
                    <span className="text-xs text-stone-600 truncate max-w-[150px]">
                      {entry.description}
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-stone-500 mt-1 flex items-center gap-2 font-mono">
                  <span>{formattedDate}</span>
                  <span>•</span>
                  <span>ID: {entry.id.slice(0, 8)}...</span>
                </div>
              </div>
            </div>

            <div className="text-right">
              <div
                className={`text-base font-extrabold tracking-tight ${
                  isCredit ? 'text-amber-800' : 'text-emerald-700'
                }`}
              >
                {isCredit ? `+₹${entry.amount}` : `-₹${entry.amount}`}
              </div>
              <div className="text-[10px] text-stone-600 font-mono flex items-center justify-end gap-1 mt-0.5">
                <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                <span>Immutable</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
