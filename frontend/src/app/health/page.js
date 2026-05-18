"use client";
import { useEffect, useState } from 'react';
import { Activity, Server, Database, ShieldAlert, CheckCircle2, Clock } from 'lucide-react';

export default function BotHealth() {
  const [health, setHealth] = useState({ status: 'LOADING' });
  const [tradeState, setTradeState] = useState({});
  const [pulseCount, setPulseCount] = useState(0);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const apiUrl = (typeof window !== 'undefined' ? localStorage.getItem('API_BASE_URL') : null) || process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "";
        
        // 1. Fetch API Health
        try {
          const healthRes = await fetch(`${apiUrl}/api/health`);
          const healthData = await healthRes.json();
          setHealth(healthData);
        } catch {
          setHealth({ status: 'OFFLINE', message: 'Cannot connect to Python Backend' });
        }

        // 2. Fetch Trade State
        const stateRes = await fetch(`${apiUrl}/api/status`);
        const stateData = await stateRes.json();
        setTradeState(stateData);

        // 3. Fetch Pulse Count
        const pulseRes = await fetch(`${apiUrl}/api/pulses?limit=1000`);
        const pulseData = await pulseRes.json();
        setPulseCount(pulseData.length);
        
      } catch (error) {
        console.error("Error fetching health data:", error);
      }
    };
    
    fetchHealth();
    // Auto-refresh every 60 seconds
    const interval = setInterval(fetchHealth, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500 pb-10">
      
      {/* Header */}
      <div className="flex justify-between items-end border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight">System Health</h1>
          <p className="text-white/50 mt-2 font-mono text-sm flex items-center tracking-widest">
            <Activity size={14} className="text-cyber-green mr-2" />
            DIAGNOSTICS & TELEMETRY
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Core API Server */}
        <div className="glass-panel p-8 relative overflow-hidden group">
          <div className={`absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl transition-all ${health.status === 'ALIVE' ? 'bg-cyber-green/5 group-hover:bg-cyber-green/10' : 'bg-red-500/5 group-hover:bg-red-500/10'}`}></div>
          <div className="flex items-center mb-6">
            <Server className={`mr-3 ${health.status === 'ALIVE' ? 'text-cyber-green' : 'text-red-500'}`} size={24} />
            <h3 className="text-xl font-light tracking-wide">Python Backend</h3>
          </div>
          <div className="space-y-4">
            <div className="flex justify-between items-center pb-4 border-b border-white/5">
              <span className="text-white/60 font-mono text-sm">STATUS</span>
              {health.status === 'ALIVE' ? (
                <span className="px-3 py-1 bg-cyber-green/10 border border-cyber-green/30 rounded text-cyber-green font-mono text-sm flex items-center">
                  <div className="w-2 h-2 rounded-full bg-cyber-green mr-2 animate-pulse"></div> ONLINE
                </span>
              ) : (
                <span className="px-3 py-1 bg-red-500/10 border border-red-500/30 rounded text-red-500 font-mono text-sm flex items-center">
                  <div className="w-2 h-2 rounded-full bg-red-500 mr-2"></div> OFFLINE
                </span>
              )}
            </div>
            <div className="flex justify-between items-center pb-4 border-b border-white/5">
              <span className="text-white/60 font-mono text-sm">UPTIME RESPONSE</span>
              <span className="text-white font-mono text-sm truncate max-w-[200px]">{health.message || 'Waiting...'}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-white/60 font-mono text-sm">NETWORK BIND</span>
              <span className="text-white font-mono text-sm">0.0.0.0:8000</span>
            </div>
          </div>
        </div>

        {/* Database Telemetry */}
        <div className="glass-panel p-8 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl group-hover:bg-blue-500/10 transition-all"></div>
          <div className="flex items-center mb-6">
            <Database className="mr-3 text-blue-400" size={24} />
            <h3 className="text-xl font-light tracking-wide">Brain Storage</h3>
          </div>
          <div className="space-y-4">
            <div className="flex justify-between items-center pb-4 border-b border-white/5">
              <span className="text-white/60 font-mono text-sm">SQLITE EVENT ROWS</span>
              <span className="text-blue-400 font-mono text-sm">{pulseCount} Pulses Logged</span>
            </div>
            <div className="flex justify-between items-center pb-4 border-b border-white/5">
              <span className="text-white/60 font-mono text-sm">LAST PULSE TIMESTAMP</span>
              <span className="text-white font-mono text-sm">{tradeState.last_pulse_timestamp || '--'}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-white/60 font-mono text-sm">LAST DECISION MEMORY</span>
              <span className="text-white font-mono text-sm">{tradeState.last_decision || '--'}</span>
            </div>
          </div>
        </div>

        {/* Hard Shields Status */}
        <div className="glass-panel p-8 md:col-span-2 relative overflow-hidden">
          <div className="flex items-center mb-6">
            <ShieldAlert className="mr-3 text-purple-400" size={24} />
            <h3 className="text-xl font-light tracking-wide">Active Security Shields</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-black/40 border border-white/5 p-4 rounded-lg flex flex-col items-center justify-center text-center">
              <CheckCircle2 className="text-cyber-green mb-3" size={24} />
              <p className="text-white/80 font-medium mb-1">State Transition Guard</p>
              <p className="text-cyber-green/70 font-mono text-xs">ENFORCING RULES</p>
            </div>
            
            <div className="bg-black/40 border border-white/5 p-4 rounded-lg flex flex-col items-center justify-center text-center">
              <CheckCircle2 className="text-cyber-green mb-3" size={24} />
              <p className="text-white/80 font-medium mb-1">VIX Floor/Ceiling Guard</p>
              <p className="text-cyber-green/70 font-mono text-xs">ACTIVE</p>
            </div>
            
            <div className={`border p-4 rounded-lg flex flex-col items-center justify-center text-center transition-colors ${tradeState.earnings_blackout_active ? 'bg-red-500/10 border-red-500/30 shadow-[0_0_15px_rgba(239,68,68,0.2)]' : 'bg-black/40 border-white/5'}`}>
              {tradeState.earnings_blackout_active ? (
                <ShieldAlert className="text-red-500 mb-3 animate-pulse" size={24} />
              ) : (
                 <CheckCircle2 className="text-cyber-green mb-3" size={24} />
              )}
              <p className="text-white/80 font-medium mb-1">Earnings Blackout</p>
              <p className={`font-mono text-xs ${tradeState.earnings_blackout_active ? 'text-red-400 font-bold' : 'text-cyber-green/70'}`}>
                {tradeState.earnings_blackout_active ? 'RESTRICTING TRADES' : 'CLEAR'}
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
