import React, { useState } from 'react';
import { UserCheck, Plus, Phone, AlertTriangle } from 'lucide-react';
import { CustomerDisambiguationCandidate } from '../types/api';
import { useStore } from '../context/StoreContext';

interface CustomerDisambiguationProps {
  customerName: string;
  candidates: CustomerDisambiguationCandidate[];
  onSelectCustomer: (candidate: CustomerDisambiguationCandidate) => void;
  onCreateNewCustomer: (name: string, phone?: string) => void;
  onCancel: () => void;
}

export const CustomerDisambiguation: React.FC<CustomerDisambiguationProps> = ({
  customerName,
  candidates,
  onSelectCustomer,
  onCreateNewCustomer,
  onCancel,
}) => {
  const { t } = useStore();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [phone, setPhone] = useState('');

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreateNewCustomer(customerName, phone.trim() || undefined);
  };

  return (
    <div
      role="dialog"
      aria-labelledby="disambiguation-title"
      aria-modal="true"
      className="bg-white border-2 border-amber-300 rounded-2xl p-5 shadow-lg space-y-4"
    >
      <div className="flex items-start gap-3">
        <div className="p-2.5 bg-amber-100 text-amber-800 rounded-xl shrink-0">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <div>
          <h3 id="disambiguation-title" className="text-lg font-bold text-stone-900">
            {t.disambiguation.title}
          </h3>
          <p className="text-sm text-stone-600 mt-0.5">
            {t.disambiguation.subtitle}
          </p>
        </div>
      </div>

      <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">
        Matching Accounts for: <span className="text-stone-900 font-bold">{customerName}</span>
      </div>

      {/* Candidate List */}
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {candidates.map((cand) => (
          <div
            key={cand.id}
            className="flex items-center justify-between p-3.5 rounded-xl border border-stone-200 hover:border-amber-400 bg-stone-50/60 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-full bg-stone-200 flex items-center justify-center text-stone-700 font-bold text-sm">
                {cand.customer_name.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="text-sm font-bold text-stone-900">{cand.customer_name}</div>
                <div className="text-xs text-stone-500 flex items-center gap-1.5 mt-0.5">
                  <Phone className="h-3 w-3" />
                  <span>{cand.phone_number || 'No phone registered'}</span>
                  <span>•</span>
                  <span>ID: {cand.id.slice(0, 8)}...</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => onSelectCustomer(cand)}
              className="inline-flex items-center gap-1 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-semibold transition-colors"
            >
              <UserCheck className="h-3.5 w-3.5" />
              {t.disambiguation.selectButton}
            </button>
          </div>
        ))}
      </div>

      {/* Create Separate New Customer */}
      {!showCreateForm ? (
        <div className="pt-2 border-t border-stone-100 flex items-center justify-between">
          <button
            onClick={() => setShowCreateForm(true)}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-stone-700 hover:text-stone-900 underline"
          >
            <Plus className="h-3.5 w-3.5" />
            {t.disambiguation.createNewPrompt} (with distinct phone)
          </button>
          <button
            onClick={onCancel}
            className="px-3 py-1 text-xs text-stone-500 hover:text-stone-700"
          >
            {t.customer.cancel}
          </button>
        </div>
      ) : (
        <form onSubmit={handleCreateSubmit} className="pt-3 border-t border-stone-100 space-y-3">
          <div className="text-xs font-semibold text-stone-800">
            Register new distinct customer: {customerName}
          </div>
          <div>
            <label className="block text-xs text-stone-600 mb-1">
              Phone Number (Required for disambiguation)
            </label>
            <input
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="e.g. 9876543210"
              className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
            >
              {t.customer.cancel}
            </button>
            <button
              type="submit"
              className="px-3 py-1.5 bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold rounded-lg"
            >
              {t.customer.save}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
