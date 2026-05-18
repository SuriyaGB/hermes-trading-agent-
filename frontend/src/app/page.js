"use client";

import { useEffect, useState } from 'react';
import { ArrowUpRight, ShieldCheck, Zap } from 'lucide-react';

export default function CommandCentre() {
  const [portfolio, setPortfolio] = useState({ total_cash: 0, realized_pnl: 0 });
  const [status, setStatus] = useState({ current_phase: 'LOADING' });
  const [lastPulse, setLastPulse] = useState(null);

  // Fetch data from our Python FastAPI backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Dynamically get the IP address you are viewing the dashboard from
	const apiUrl = (typeof window !== 'undefined' ? localStorage.getItem('API_BASE_URL') : null) || process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "";        
        const portRes = await fetch(`${apiUrl}/api/portfolio`, {
          headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const portData = await portRes.json();
        setPortfolio(portData);

        const statRes = await fetch(`${apiUrl}/api/status`, {
          headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const statData = await statRes.json();
        setStatus(statData);

        const pulseRes = await fetch(`${apiUrl}/api/pulses?limit=1`, {
          headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const pulseData = await pulseRes.json();
        if (pulseData && pulseData.length > 0) {
          setLastPulse(pulseData[0]);
        }
      } catch (error) {
        console.error("Error fetching data:", error);
      }
    };
    
    fetchData();
    // Auto-refresh every 60 seconds
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight">Command Centre</h1>
          <p className="text-white/50 mt-2 font-mono text-sm flex items-center">
            <Zap size={14} className="text-cyber-green mr-2" />
            LIVE MARKET CONNECTION
          </p>
        </div>
      </div>

      {/* Top HUD Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="glass-panel p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-cyber-green/5 rounded-full blur-3xl group-hover:bg-cyber-green/10 transition-all"></div>
          <p className="text-white/50 text-xs font-mono mb-2 tracking-widest">AVAILABLE CASH</p>
          <h2 className="text-4xl font-light">${portfolio.total_cash.toLocaleString('en-US', {minimumFractionDigits: 2})}</h2>
        </div>
        
        <div className="glass-panel p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-cyber-green/5 rounded-full blur-3xl group-hover:bg-cyber-green/10 transition-all"></div>
          <p className="text-white/50 text-xs font-mono mb-2 tracking-widest">PREMIUM COLLECTED</p>
          <div className="flex items-center">
            <h2 className="text-4xl font-light text-cyber-green">${portfolio.realized_pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}</h2>
            <ArrowUpRight className="text-cyber-green ml-2 opacity-50" />
          </div>
        </div>
        
        <div className="glass-panel p-6 md:col-span-2 relative overflow-hidden">
           <p className="text-white/50 text-xs font-mono mb-2 tracking-widest">CURRENT PHASE</p>
           <div className="flex items-center space-x-4 mt-2">
              <div className="px-4 py-2 bg-cyber-green/10 border border-cyber-green/30 rounded-full text-cyber-green font-mono text-sm flex items-center">
                <div className="w-2 h-2 rounded-full bg-cyber-green mr-2 animate-pulse" style={{boxShadow: '0 0 8px #00E676'}}></div>
                {status.current_phase}
              </div>
           </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Shield Status */}
        <div className="glass-panel p-6 col-span-1 flex flex-col">
          <div className="flex items-center space-x-3 mb-6">
            <ShieldCheck className="text-cyber-green" />
            <h3 className="text-lg font-medium">Shield Status</h3>
          </div>
          
          <div className="space-y-6 flex-grow">
            <div className="flex justify-between items-center pb-3 border-b border-white/5">
              <span className="text-white/60 text-sm">VIX Guard</span>
              <span className="text-cyber-green font-mono text-sm">{lastPulse ? lastPulse.vix_level : '--'} <span className="text-xs opacity-50 ml-1">(SAFE)</span></span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-white/5">
              <span className="text-white/60 text-sm">Delta Guard</span>
              <span className="text-cyber-green font-mono text-sm">{lastPulse ? lastPulse.delta_current : '--'} <span className="text-xs opacity-50 ml-1">(TARGET)</span></span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-white/5">
              <span className="text-white/60 text-sm">AAPL Price</span>
              <span className="text-white font-mono text-sm">${lastPulse ? lastPulse.aapl_price : '--'}</span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-white/5">
              <span className="text-white/60 text-sm">Days to Expiry (DTE)</span>
              <span className="text-white font-mono text-sm">{lastPulse ? lastPulse.dte_current : '--'}</span>
            </div>
          </div>
        </div>

        {/* Right Column: AI Brain Feed */}
        <div className="glass-panel p-6 col-span-1 lg:col-span-2 flex flex-col">
          <h3 className="text-lg font-medium mb-6">Latest AI Reasoning</h3>
          
          {lastPulse ? (
            <div className="flex-1 bg-black/40 rounded-lg border border-white/5 p-6 font-mono text-sm text-cyber-green leading-relaxed overflow-y-auto">
              <div className="mb-4 flex justify-between items-center border-b border-white/10 pb-4">
                <span className="text-white/40 text-xs">PULSE: {lastPulse.timestamp}</span>
                <span className="bg-white/10 px-3 py-1 rounded text-white text-xs">{lastPulse.ai_decision}</span>
              </div>
              <p className="mt-4 opacity-90">{lastPulse.ai_reasoning}</p>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-white/30 font-mono text-sm border border-white/5 border-dashed rounded-lg p-12">
              WAITING FOR PULSE DATA...
            </div>
          )}
        </div>
        
      </div>
    </div>
  );
}
