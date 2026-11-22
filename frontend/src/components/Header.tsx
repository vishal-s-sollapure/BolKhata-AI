import React from 'react';
import { Store, Activity, Globe, RefreshCw } from 'lucide-react';
import { useStore } from '../context/StoreContext';
import { SupportedLanguage } from '../types/api';

interface HeaderProps {
  onRefresh?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onRefresh }) => {
  const { language, setLanguage, t, health, healthLoading, checkHealth, storeId } = useStore();

  const handleLanguageChange = (lang: SupportedLanguage) => {
    setLanguage(lang);
  };

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-stone-200/90 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-3">
        {/* Brand & Store Info */}
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-amber-600 text-white flex items-center justify-center shadow-sm">
            <Store className="h-6 w-6" aria-hidden="true" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-stone-900 font-sans">
                {t.appName}
              </h1>
              <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-200">
                Kirana Khata
              </span>
            </div>
            <p className="text-xs text-stone-600 font-medium">
              {t.tagline}
            </p>
          </div>
        </div>

        {/* Controls: Health, Language & Store ID */}
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
          {/* Backend Status Pill */}
          <button
            onClick={() => void checkHealth()}
            disabled={healthLoading}
            title="Click to check backend connectivity"
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              health?.status === 'healthy'
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100'
                : 'bg-rose-50 text-rose-800 border-rose-200 hover:bg-rose-100'
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                health?.status === 'healthy' ? 'bg-emerald-600 animate-pulse' : 'bg-rose-600'
              }`}
            />
            <span>
              {healthLoading
                ? t.general.loading
                : health?.status === 'healthy'
                ? `${t.general.backendOnline} (v${health.version})`
                : t.general.backendOffline}
            </span>
          </button>

          {/* Refresh Action */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-1.5 text-stone-600 hover:text-stone-900 hover:bg-stone-100 rounded-lg border border-stone-200 transition-colors"
              title={t.nav.refresh}
              aria-label={t.nav.refresh}
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          )}

          {/* Language Selector */}
          <div className="inline-flex items-center bg-stone-100 p-0.5 rounded-lg border border-stone-200">
            <Globe className="h-3.5 w-3.5 text-stone-600 ml-1.5 mr-0.5" aria-hidden="true" />
            <button
              onClick={() => handleLanguageChange('kn')}
              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                language === 'kn'
                  ? 'bg-white text-stone-900 shadow-xs font-bold'
                  : 'text-stone-700 hover:text-stone-950'
              }`}
            >
              ಕನ್ನಡ
            </button>
            <button
              onClick={() => handleLanguageChange('hi')}
              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                language === 'hi'
                  ? 'bg-white text-stone-900 shadow-xs font-bold'
                  : 'text-stone-700 hover:text-stone-950'
              }`}
            >
              हिन्दी
            </button>
            <button
              onClick={() => handleLanguageChange('en')}
              className={`px-2 py-1 rounded text-xs font-medium transition-all ${
                language === 'en'
                  ? 'bg-white text-stone-900 shadow-xs font-bold'
                  : 'text-stone-700 hover:text-stone-950'
              }`}
            >
              English
            </button>
          </div>

          {/* Store Context Badge */}
          <div
            className="hidden lg:flex items-center gap-1 px-2.5 py-1 bg-stone-50 border border-stone-200 rounded-lg text-[11px] text-stone-600 font-mono"
            title={`Store Tenant UUID: ${storeId}`}
          >
            <Activity className="h-3 w-3 text-stone-600" />
            <span className="truncate max-w-[100px]">Store: {storeId.slice(0, 8)}...</span>
          </div>
        </div>
      </div>
    </header>
  );
};
