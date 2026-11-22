/**
 * Global Store & UI context for BolKhata AI merchant frontend.
 * Manages store tenancy, UI language, store ledger summaries, and notifications.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  BackendHealthResponse,
  StoreSummaryResponse,
  SupportedLanguage,
} from '../types/api';
import { apiClient, DEFAULT_DEV_STORE_ID } from '../api/client';
import { translations, TranslationDictionary } from '../i18n/translations';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title?: string;
  message: string;
}

interface StoreContextValue {
  language: SupportedLanguage;
  setLanguage: (lang: SupportedLanguage) => void;
  t: TranslationDictionary;
  storeId: string;
  setStoreId: (id: string) => void;
  summary: StoreSummaryResponse | null;
  summaryLoading: boolean;
  summaryError: string | null;
  refreshSummary: () => Promise<void>;
  health: BackendHealthResponse | null;
  healthLoading: boolean;
  checkHealth: () => Promise<void>;
  toasts: ToastMessage[];
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
}

const StoreContext = createContext<StoreContextValue | undefined>(undefined);

export const StoreProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<SupportedLanguage>(() => {
    const saved = localStorage.getItem('bolkhata_lang');
    return (saved as SupportedLanguage) || 'kn'; // Default to Kannada for Kirana shopkeepers
  });

  const [storeId, setStoreIdState] = useState<string>(() => {
    const saved = localStorage.getItem('bolkhata_store_id');
    return saved || DEFAULT_DEV_STORE_ID;
  });

  const [summary, setSummary] = useState<StoreSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState<boolean>(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [health, setHealth] = useState<BackendHealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(false);

  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const t = translations[language];

  const setLanguage = (lang: SupportedLanguage) => {
    setLanguageState(lang);
    localStorage.setItem('bolkhata_lang', lang);
  };

  const setStoreId = (id: string) => {
    setStoreIdState(id);
    apiClient.setStoreId(id);
    localStorage.setItem('bolkhata_store_id', id);
    void refreshSummary();
  };

  const addToast = useCallback((toast: Omit<ToastMessage, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newToast: ToastMessage = { ...toast, id };
    setToasts((prev) => [...prev, newToast]);
    setTimeout(() => {
      removeToast(id);
    }, 5000);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const checkHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const res = await apiClient.getHealth();
      setHealth(res);
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  const refreshSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const res = await apiClient.getStoreSummary();
      setSummary(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch store ledger summary';
      setSummaryError(msg);
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  useEffect(() => {
    apiClient.setStoreId(storeId);
    void checkHealth();
    void refreshSummary();
  }, [storeId, checkHealth, refreshSummary]);

  return (
    <StoreContext.Provider
      value={{
        language,
        setLanguage,
        t,
        storeId,
        setStoreId,
        summary,
        summaryLoading,
        summaryError,
        refreshSummary,
        health,
        healthLoading,
        checkHealth,
        toasts,
        addToast,
        removeToast,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
};

export const useStore = (): StoreContextValue => {
  const context = useContext(StoreContext);
  if (!context) {
    throw new Error('useStore must be used within a StoreProvider');
  }
  return context;
};
