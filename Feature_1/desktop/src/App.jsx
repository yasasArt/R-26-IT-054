import React, { useState } from 'react';
import { Activity, Lock, BarChart2 } from 'lucide-react';
import LiveProduction from './views/LiveProduction';
import Analysis from './views/Analysis';

function App() {
  const [activeTab, setActiveTab] = useState('Live production');

  return (
    <div className="flex h-screen bg-canvas font-sans overflow-hidden">
      
      {/* Sidebar */}
      <div className="w-64 bg-sidebar text-white flex flex-col justify-between shrink-0">
        <div>
          <div className="p-6 flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-[#788EFF] to-[#24368F] rounded-xl flex items-center justify-center">
              <span className="text-xl font-bold">👕</span>
            </div>
            <div>
              <h1 className="font-bold text-sm leading-tight text-white">Garment Counter</h1>
              <p className="text-xs text-[#8691A4]">Workstation intelligence</p>
            </div>
          </div>

          <div className="px-6 mb-8">
            <div className="bg-sidebar-raised rounded-lg p-3 border border-slate-700/50 flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-[#5BCDA1]"></div>
              <div>
                <p className="text-sm font-semibold text-white">QC Workstation</p>
                <p className="text-xs text-[#8691A4]">Quality Checking Area</p>
              </div>
            </div>
          </div>

          <nav className="px-3 space-y-1">
            <p className="px-3 text-xs font-semibold text-[#5B6980] tracking-wider mb-2 mt-4">MONITOR</p>
            
            <button 
              onClick={() => setActiveTab('Live production')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'Live production' ? 'bg-accent-soft text-accent' : 'text-[#8691A4] hover:bg-sidebar-raised hover:text-white'}`}
            >
              <Activity size={18} />
              Live production
            </button>

            <button 
              onClick={() => setActiveTab('Analysis')}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'Analysis' ? 'bg-accent-soft text-accent' : 'text-[#8691A4] hover:bg-sidebar-raised hover:text-white'}`}
            >
              <BarChart2 size={18} />
              Analysis & Logs
            </button>
            
          </nav>
        </div>

        {/* Footer */}
        <div className="p-6">
          <div className="flex items-center gap-2 text-xs text-[#8691A4] mb-1">
            <Lock size={12} />
            <span>Offline-first architecture</span>
          </div>
          <p className="text-[10px] text-[#5B6980]">Production release · v1.0.1</p>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Top bar */}
        <header className="h-14 bg-surface border-b border-line flex items-center justify-between px-8 shrink-0">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-ink-soft">Workstation</span>
            <span className="text-line-soft">/</span>
            <span className="font-medium text-ink">{activeTab}</span>
          </div>
          <div className="flex gap-2">
            <span className="px-2 py-1 bg-canvas rounded text-xs font-medium text-ink-secondary">macOS</span>
            <span className="px-2 py-1 bg-[#E9F7F2] text-[#168768] rounded text-xs font-semibold">LOCAL</span>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-8">
          {/* මෙතනින් තමයි Unmount වෙන එක නතර කරලා Hide/Show කරන්නේ */}
          <div className={activeTab === 'Live production' ? 'block h-full' : 'hidden'}>
            <LiveProduction />
          </div>
          <div className={activeTab === 'Analysis' ? 'block h-full' : 'hidden'}>
            <Analysis />
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;