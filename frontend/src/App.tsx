import React, { useState } from 'react';
import { StoreProvider, useStore } from './context/StoreContext';
import { Header } from './components/Header';
import { Navigation, ActiveTab } from './components/Navigation';
import { Dashboard } from './components/Dashboard';
import { VoiceAssistant } from './components/VoiceAssistant';
import { CustomerList } from './components/CustomerList';
import { ToastContainer } from './components/Toast';

const MainLayout: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('dashboard');
  const { refreshSummary } = useStore();

  return (
    <div className="min-h-screen bg-[#FAF7F2] text-stone-900 flex flex-col font-sans selection:bg-amber-200">
      {/* Top Header */}
      <Header onRefresh={() => void refreshSummary()} />

      {/* Primary Navigation */}
      <Navigation activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24 md:pb-12">
        {activeTab === 'dashboard' && (
          <Dashboard onNavigateToCustomers={() => setActiveTab('customers')} />
        )}
        {activeTab === 'voice' && (
          <div className="max-w-3xl mx-auto space-y-6">
            <VoiceAssistant />
          </div>
        )}
        {activeTab === 'customers' && <CustomerList />}
      </main>

      {/* Floating Notifications */}
      <ToastContainer />
    </div>
  );
};

export default function App() {
  return (
    <StoreProvider>
      <MainLayout />
    </StoreProvider>
  );
}
