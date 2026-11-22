import React from 'react';
import { ArrowRight, Users, Sparkles } from 'lucide-react';
import { useStore } from '../context/StoreContext';
import { SummaryCards } from './SummaryCards';
import { VoiceAssistant } from './VoiceAssistant';

interface DashboardProps {
  onNavigateToCustomers: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onNavigateToCustomers }) => {
  const { t, summary } = useStore();

  const todayFormatted = new Intl.DateTimeFormat('en-IN', {
    weekday: 'long',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date());

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-stone-900 tracking-tight">
            {summary?.store_name || 'My Kirana Store'}
          </h2>
          <p className="text-xs sm:text-sm text-stone-500 mt-1 font-medium">
            {todayFormatted} • Digital voice ledger for udhaar and jama
          </p>
        </div>

        <button
          onClick={onNavigateToCustomers}
          className="inline-flex items-center gap-1.5 px-4 py-2 bg-white hover:bg-stone-50 border border-stone-200/90 text-stone-800 text-xs font-semibold rounded-xl shadow-xs transition-colors self-start sm:self-auto"
        >
          <Users className="h-4 w-4 text-amber-600" />
          <span>View All Customers ({summary?.active_customers_count ?? 0})</span>
          <ArrowRight className="h-3.5 w-3.5 text-stone-400" />
        </button>
      </div>

      {/* 4 Summary Cards */}
      <section aria-labelledby="metrics-heading">
        <h3 id="metrics-heading" className="sr-only">
          Store Financial Metrics
        </h3>
        <SummaryCards />
      </section>

      {/* Voice Assistant Section */}
      <section aria-labelledby="voice-assistant-heading" className="space-y-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-amber-600" />
          <h3 id="voice-assistant-heading" className="text-lg font-bold text-stone-900">
            {t.nav.voiceKhata} — Quick Voice Action
          </h3>
        </div>
        <VoiceAssistant />
      </section>
    </div>
  );
};
