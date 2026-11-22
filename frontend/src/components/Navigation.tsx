import React from 'react';
import { LayoutDashboard, Mic, Users } from 'lucide-react';
import { useStore } from '../context/StoreContext';

export type ActiveTab = 'dashboard' | 'voice' | 'customers';

interface NavigationProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
}

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange }) => {
  const { t } = useStore();

  const navItems = [
    { id: 'dashboard' as ActiveTab, label: t.nav.dashboard, icon: LayoutDashboard },
    { id: 'voice' as ActiveTab, label: t.nav.voiceKhata, icon: Mic },
    { id: 'customers' as ActiveTab, label: t.nav.customers, icon: Users },
  ];

  return (
    <>
      {/* Desktop / Tablet Sub-Header Navigation */}
      <nav
        aria-label="Main Navigation"
        className="hidden md:block bg-stone-100/80 border-b border-stone-200"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-2 py-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onTabChange(item.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                    isActive
                      ? 'bg-white text-stone-900 shadow-xs border border-stone-200/90'
                      : 'text-stone-700 hover:text-stone-950 hover:bg-stone-200/60'
                  }`}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className={`h-4 w-4 ${isActive ? 'text-amber-600' : 'text-stone-600'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Mobile Bottom Navigation Bar */}
      <nav
        aria-label="Mobile Bottom Navigation"
        className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-stone-200 shadow-lg px-2 py-1"
      >
        <div className="grid grid-cols-3 max-w-md mx-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`flex flex-col items-center justify-center py-2 px-1 rounded-xl text-xs font-medium transition-colors min-h-[48px] ${
                  isActive
                    ? 'text-amber-700 font-bold'
                    : 'text-stone-600 hover:text-stone-900'
                }`}
                aria-current={isActive ? 'page' : undefined}
              >
                <div
                  className={`p-1 rounded-lg ${
                    isActive ? 'bg-amber-100 text-amber-800' : 'text-stone-500'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <span className="mt-0.5 truncate">{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </>
  );
};
