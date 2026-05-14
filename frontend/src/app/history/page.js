"use client";
import { useEffect, useState } from 'react';
import { History, Terminal, Search } from 'lucide-react';

export default function PulseHistory() {
  const [pulses, setPulses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPulses = async () => {
      try {
        const apiUrl = (typeof window !== 'undefined' ? localStorage.getItem('API_BASE_URL') : null) || process.env.NEXT_PUBLIC_API_BASE_URL || "";
        const res = await fetch(`${apiUrl}/api/pulses?limit=100`);
        const data = await res.json();
        setPulses(data);
      } catch (error) {
        console.error("Error fetching pulse history:", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchPulses();
    // Refresh the table every 60 seconds
    const interval = setInterval(fetchPulses, 60000);
    return () => clearInterval(interval);
  }, []);

  const getDecisionColor = (decision) => {
    if (!decision) return 'bg-white/10 text-white/70 border-white/10';
    if (decision.includes('SELL')) return 'bg-cyber-green/20 text-cyber-green border-cyber-green/30';
    if (decision.includes('CLOSE')) return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    if (decision.includes('ABORT') || decision.includes('ERROR')) return 'bg-red-500/20 text-red-400 border-red-500/30';
    return 'bg-white/10 text-white/70 border-white/10'; // HOLD
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500 pb-10">
      
      {/* Header */}
      <div className="flex justify-between items-end border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight">Pulse History</h1>
          <p className="text-white/50 mt-2 font-mono text-sm flex items-center tracking-widest">
            <Terminal size={14} className="text-cyber-green mr-2" />
            AI MEMORY & AUDIT LOG
          </p>
        </div>
        
        <div className="flex items-center bg-black/40 border border-white/10 rounded-lg px-4 py-2">
          <Search size={16} className="text-white/40 mr-2" />
          <span className="font-mono text-sm text-white/40">{pulses.length} EVENTS LOGGED</span>
        </div>
      </div>

      {/* Terminal Log Table */}
      <div className="glass-panel overflow-hidden border border-white/10 rounded-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-black/60 border-b border-white/10 text-xs font-mono tracking-widest text-white/50">
                <th className="p-4 font-normal">TIMESTAMP</th>
                <th className="p-4 font-normal">PRICE</th>
                <th className="p-4 font-normal">VIX</th>
                <th className="p-4 font-normal">DECISION</th>
                <th className="p-4 font-normal w-1/2">REASONING</th>
              </tr>
            </thead>
            <tbody className="font-mono text-sm divide-y divide-white/5">
              {loading ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center text-white/30 border-dashed">LOADING MEMORY LOGS...</td>
                </tr>
              ) : (
                pulses.map((pulse, i) => (
                  <tr key={i} className="hover:bg-white/5 transition-colors group">
                    <td className="p-4 text-white/60 whitespace-nowrap">
                      {new Date(pulse.timestamp).toLocaleString('en-US', { month: 'short', day: '2-digit', hour: '2-digit', minute:'2-digit' })}
                    </td>
                    <td className="p-4 text-white">${pulse.aapl_price}</td>
                    <td className="p-4 text-yellow-500/80">{pulse.vix_level}</td>
                    <td className="p-4 whitespace-nowrap">
                      <span className={`px-2 py-1 rounded text-xs border ${getDecisionColor(pulse.ai_decision)}`}>
                        {pulse.ai_decision}
                      </span>
                    </td>
                    <td className="p-4 text-cyber-green/70 text-xs leading-relaxed max-w-xl group-hover:text-cyber-green transition-colors">
                      {pulse.ai_reasoning}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
