import React, { useEffect, useState, useCallback } from 'react';
import { Users, Search, UserPlus, Phone, ArrowRight, X, AlertCircle } from 'lucide-react';
import { Customer } from '../types/api';
import { apiClient, ApiError } from '../api/client';
import { useStore } from '../context/StoreContext';
import { CustomerDetail } from './CustomerDetail';

export const CustomerList: React.FC = () => {
  const { t, addToast, refreshSummary } = useStore();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Selected customer for detail view
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);

  // Add Customer Modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [newName, setNewName] = useState<string>('');
  const [newPhone, setNewPhone] = useState<string>('');
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchCustomers = useCallback(async (query?: string) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const res = await apiClient.listCustomers(query, 50, 0);
      setCustomers(res.customers);
      setTotalCount(res.total);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load customers';
      setErrorMessage(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCustomers(searchQuery);
  }, [searchQuery, fetchCustomers]);

  const handleCreateCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    setIsCreating(true);
    setCreateError(null);

    try {
      const created = await apiClient.createCustomer({
        customer_name: newName.trim(),
        phone_number: newPhone.trim() || undefined,
      });

      addToast({
        type: 'success',
        title: 'Customer Added',
        message: `Registered ${created.customer_name} into store ledger.`,
      });

      setIsAddModalOpen(false);
      setNewName('');
      setNewPhone('');
      void fetchCustomers();
      void refreshSummary();
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.detail : 'Failed to register customer';
      setCreateError(msg);
    } finally {
      setIsCreating(false);
    }
  };

  if (selectedCustomer) {
    return (
      <CustomerDetail
        customer={selectedCustomer}
        onBack={() => {
          setSelectedCustomer(null);
          void fetchCustomers(searchQuery);
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Search and Action Bar */}
      <div className="bg-white rounded-2xl border border-stone-200/90 p-4 sm:p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-stone-900">
              {t.customer.title} ({totalCount})
            </h2>
            <p className="text-xs text-stone-500 mt-0.5">
              Manage kirana store customer ledger accounts
            </p>
          </div>

          <button
            onClick={() => setIsAddModalOpen(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-bold rounded-xl shadow-xs transition-colors min-h-[44px]"
          >
            <UserPlus className="h-4 w-4" />
            <span>{t.customer.addCustomer}</span>
          </button>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="h-4 w-4 text-stone-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t.customer.searchPlaceholder}
            className="w-full pl-10 pr-4 py-2.5 bg-stone-50 border border-stone-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:bg-white transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Error Notice */}
      {errorMessage && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 text-sm flex items-center gap-2">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Customer Cards Grid / List */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="bg-white p-5 rounded-2xl border border-stone-200 animate-pulse h-28"
            />
          ))}
        </div>
      ) : customers.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-2xl border border-dashed border-stone-200">
          <Users className="h-10 w-10 text-stone-300 mx-auto mb-2" />
          <p className="text-stone-600 font-medium text-sm">{t.customer.noCustomersFound}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {customers.map((cust) => (
            <div
              key={cust.id}
              onClick={() => setSelectedCustomer(cust)}
              className="bg-white border border-stone-200/90 hover:border-amber-400 rounded-2xl p-4 sm:p-5 shadow-xs hover:shadow-md transition-all cursor-pointer flex flex-col justify-between group"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-stone-100 group-hover:bg-amber-100 group-hover:text-amber-900 text-stone-700 font-bold flex items-center justify-center transition-colors">
                    {cust.customer_name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-stone-900 group-hover:text-amber-900 transition-colors">
                      {cust.customer_name}
                    </h3>
                    {cust.phone_number ? (
                      <div className="text-xs text-stone-500 flex items-center gap-1 mt-0.5">
                        <Phone className="h-3 w-3" />
                        <span>{cust.phone_number}</span>
                      </div>
                    ) : (
                      <span className="text-xs text-stone-400">No phone</span>
                    )}
                  </div>
                </div>

                <div className="p-1 rounded-lg text-stone-400 group-hover:text-amber-600 group-hover:translate-x-0.5 transition-all">
                  <ArrowRight className="h-4 w-4" />
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-stone-100 flex items-center justify-between text-xs text-stone-500 font-mono">
                <span>ID: {cust.id.slice(0, 8)}...</span>
                <span className="font-sans font-semibold text-amber-700">
                  {t.customer.viewHistory}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Customer Modal */}
      {isAddModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4"
        >
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-stone-200 space-y-4">
            <div className="flex items-center justify-between border-b border-stone-100 pb-3">
              <h3 className="text-lg font-bold text-stone-900 flex items-center gap-2">
                <UserPlus className="h-5 w-5 text-amber-600" />
                <span>{t.customer.addCustomer}</span>
              </h3>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="p-1 rounded-lg hover:bg-stone-100 text-stone-500 hover:text-stone-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {createError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-900 text-xs rounded-xl flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-rose-600 shrink-0" />
                <span>{createError}</span>
              </div>
            )}

            <form onSubmit={handleCreateCustomer} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-stone-600 mb-1">
                  {t.customer.customerName} *
                </label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Ramesh Kumar"
                  className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-stone-600 mb-1">
                  {t.customer.phoneNumber} (Optional)
                </label>
                <input
                  type="tel"
                  value={newPhone}
                  onChange={(e) => setNewPhone(e.target.value)}
                  placeholder="e.g. 9876543210"
                  className="w-full px-3.5 py-2.5 border border-stone-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 text-sm text-stone-600 hover:bg-stone-100 rounded-xl transition-colors"
                >
                  {t.customer.cancel}
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !newName.trim()}
                  className="px-5 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-bold rounded-xl shadow-xs transition-colors disabled:opacity-50"
                >
                  {isCreating ? 'Saving...' : t.customer.save}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
