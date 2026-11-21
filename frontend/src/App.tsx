import { useState, useEffect } from 'react';
import { 
  Mic, 
  Store, 
  ShieldCheck, 
  Server, 
  Languages, 
  CheckCircle2, 
  Database,
  Cpu,
  Radio,
  Volume2
} from 'lucide-react';

interface BackendHealth {
  status: string;
  service: string;
  version: string;
  timestamp?: string;
  environment?: string;
  languages_supported?: string[];
}

export default function App() {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedLang, setSelectedLang] = useState<string>('kannada');
  const [isPressing, setIsPressing] = useState<boolean>(false);

  useEffect(() => {
    checkHealth();
  }, []);

  const checkHealth = async () => {
    try {
      setLoading(true);
      const res = await fetch('/health');
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      } else {
        setHealth(null);
      }
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  const languages = [
    { id: 'kannada', label: 'ಕನ್ನಡ (Kannada)', code: 'kn' },
    { id: 'hindi', label: 'हिन्दी (Hindi)', code: 'hi' },
    { id: 'english', label: 'English', code: 'en' },
    { id: 'mixed', label: 'Code-Mixed (Kanglish / Hinglish)', code: 'mix' },
  ];

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-[#0d1424]/90 backdrop-blur sticky top-0 z-50 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-amber-600 to-orange-500 flex items-center justify-center shadow-lg shadow-orange-500/20">
              <Store className="h-6 w-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold tracking-tight text-white">BolKhata AI</h1>
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                  Phase 0 MVP
                </span>
              </div>
              <p className="text-xs text-slate-400">Your Kirana Store. Your Voice. Your Digital Khata.</p>
            </div>
          </div>

          {/* Backend Health Badge */}
          <div className="flex items-center gap-3">
            <button
              onClick={checkHealth}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                health?.status === 'healthy'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/30 hover:bg-rose-500/20'
              }`}
              title="Click to re-verify backend connectivity"
            >
              <span className={`h-2 w-2 rounded-full ${health?.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
              {loading ? (
                <span>Checking...</span>
              ) : health?.status === 'healthy' ? (
                <span>Backend Connected (v{health.version})</span>
              ) : (
                <span>Backend Offline (Run :8000)</span>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 space-y-8">
        {/* Hero Section */}
        <div className="text-center max-w-2xl mx-auto pt-4 space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400 text-xs font-semibold uppercase tracking-wider">
            <Languages className="w-3.5 h-3.5" /> Multilingual Kirana Voice Ledger
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Manage Khata with your <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-amber-300">Natural Voice</span>
          </h2>
          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            Record customer udhaar, credit repayments, and daily balances in Kannada, Hindi, and English with zero manual bookkeeping.
          </p>
        </div>

        {/* Language Selection */}
        <div className="flex flex-wrap items-center justify-center gap-2.5">
          {languages.map((lang) => (
            <button
              key={lang.id}
              onClick={() => setSelectedLang(lang.id)}
              className={`px-4 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all ${
                selectedLang === lang.id
                  ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/25 ring-2 ring-orange-400/50'
                  : 'bg-slate-800/80 hover:bg-slate-800 text-slate-300 border border-slate-700/60'
              }`}
            >
              {lang.label}
            </button>
          ))}
        </div>

        {/* Push-To-Talk Voice Interface Sandbox */}
        <div className="bg-gradient-to-b from-[#111827] to-[#0f172a] rounded-3xl border border-slate-800 p-8 shadow-xl text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-orange-500/5 via-transparent to-amber-500/5 pointer-events-none" />

          <div className="relative z-10 max-w-md mx-auto space-y-6">
            <p className="text-xs uppercase tracking-widest text-slate-400 font-semibold">
              Voice Interface (Push-to-Talk)
            </p>

            {/* Mic Push-to-Talk Button */}
            <div className="flex justify-center py-4">
              <button
                onMouseDown={() => setIsPressing(true)}
                onMouseUp={() => setIsPressing(false)}
                onTouchStart={() => setIsPressing(true)}
                onTouchEnd={() => setIsPressing(false)}
                className={`relative group w-32 h-32 rounded-full flex flex-col items-center justify-center transition-all transform active:scale-95 shadow-2xl ${
                  isPressing
                    ? 'bg-gradient-to-tr from-rose-600 to-orange-500 ring-8 ring-orange-500/30'
                    : 'bg-gradient-to-tr from-orange-600 to-amber-500 hover:ring-8 hover:ring-orange-500/20'
                }`}
              >
                <Mic className={`w-12 h-12 text-white transition-transform ${isPressing ? 'scale-110 animate-bounce' : 'group-hover:scale-105'}`} />
                <span className="text-[11px] font-semibold text-white/90 mt-1 uppercase tracking-wider">
                  {isPressing ? 'Listening...' : 'Hold to Speak'}
                </span>
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 text-xs text-slate-400 leading-relaxed">
              <span className="text-amber-400 font-semibold">Phase 0 Foundation Note:</span> Voice engine integration with 
              <span className="text-slate-200"> Gnani Prisma v3.0</span> (WebSocket STT) and 
              <span className="text-slate-200"> Gnani Timbre v3.0</span> (WebSocket TTS) will stream audio directly through the Pipecat pipeline in subsequent phases.
            </div>
          </div>
        </div>

        {/* Critical Transaction Safety Architecture Card */}
        <div className="bg-[#0e1628] rounded-2xl border border-slate-800 p-6 space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Critical Transaction Safety Guarantee</h3>
              <p className="text-xs text-slate-400">Deterministic balance calculations with Human-In-The-Loop confirmation</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-2 text-xs">
            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1.5">
              <div className="flex items-center gap-1.5 font-semibold text-orange-400">
                <Radio className="w-4 h-4" /> 1. Voice Ingestion
              </div>
              <p className="text-slate-400">
                Merchant speaks in Kannada/Hindi/English. Streamed via Gnani Prisma v3.0 WebSocket STT.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1.5">
              <div className="flex items-center gap-1.5 font-semibold text-sky-400">
                <Cpu className="w-4 h-4" /> 2. Intent Parsing (Groq)
              </div>
              <p className="text-slate-400">
                LLM extracts Customer, Amount, and Udhaar type into a TransactionProposal. <em>Never modifies DB.</em>
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1.5">
              <div className="flex items-center gap-1.5 font-semibold text-amber-400">
                <CheckCircle2 className="w-4 h-4" /> 3. Merchant Confirm
              </div>
              <p className="text-slate-400">
                Shopkeeper visually checks proposal card on screen and gives confirmation before committing.
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1.5">
              <div className="flex items-center gap-1.5 font-semibold text-emerald-400">
                <Database className="w-4 h-4" /> 4. Deterministic Ledger
              </div>
              <p className="text-slate-400">
                Only the Ledger service calculates balance with idempotency UUID and writes to SQLite audit trail.
              </p>
            </div>
          </div>
        </div>

        {/* Tech Stack Specs Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 flex items-start gap-3">
            <Server className="w-5 h-5 text-indigo-400 mt-0.5" />
            <div>
              <h4 className="text-xs font-semibold text-slate-200">Backend API</h4>
              <p className="text-xs text-slate-400 mt-0.5">FastAPI + Python 3.12 + Pipecat async streaming pipeline</p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 flex items-start gap-3">
            <Cpu className="w-5 h-5 text-amber-400 mt-0.5" />
            <div>
              <h4 className="text-xs font-semibold text-slate-200">AI Reasoning</h4>
              <p className="text-xs text-slate-400 mt-0.5">Groq Llama 3.3 70B for intent parsing & structured proposals</p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 flex items-start gap-3">
            <Volume2 className="w-5 h-5 text-rose-400 mt-0.5" />
            <div>
              <h4 className="text-xs font-semibold text-slate-200">Voice Pipeline</h4>
              <p className="text-xs text-slate-400 mt-0.5">Gnani Prisma v3.0 (STT) & Timbre v3.0 (TTS) WebSocket</p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 px-6 text-center text-xs text-slate-400">
        BolKhata AI &copy; 2026 &bull; Production-minded Hackathon MVP &bull; Built with FastAPI, React, Groq &amp; Gnani
      </footer>
    </div>
  );
}
