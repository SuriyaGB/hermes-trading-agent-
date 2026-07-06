"use client";
import { useEffect, useState } from 'react';
import { Terminal, Search, Filter, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

import { getApiUrl } from '../../utils/api';

export default function PulseHistory() {
  const [pulses, setPulses] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Excel-style filter and sort controls
  const [filterDecision, setFilterDecision] = useState('ALL');
  const [sortField, setSortField] = useState('timestamp');
  const [sortDirection, setSortDirection] = useState('desc');

  useEffect(() => {
    const fetchPulses = async () => {
      try {
        const apiUrl = getApiUrl();
        const res = await fetch(`${apiUrl}/api/pulses?limit=2000&t=${Date.now()}`, {
          headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            setPulses(data);
          }
        }
      } catch (error) {
        console.error("Error fetching pulse history:", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchPulses();
    const interval = setInterval(fetchPulses, 60000);
    return () => clearInterval(interval);
  }, []);

  const getDecisionColor = (decision) => {
    if (!decision) return 'bg-white/10 text-white/70 border-white/10';
    if (decision.includes('ROLL')) return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30';
    if (decision.includes('SELL') || decision.includes('OPEN')) return 'bg-cyber-green/20 text-cyber-green border-cyber-green/30';
    if (decision.includes('CLOSE') || decision.includes('BUY')) return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    if (decision.includes('ABORT') || decision.includes('ERROR')) return 'bg-red-500/20 text-red-400 border-red-500/30';
    return 'bg-white/10 text-white/70 border-white/10'; // HOLD
  };

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const filteredPulses = pulses.filter(pulse => {
    if (filterDecision === 'ALL') return true;
    const dec = pulse.ai_decision || '';
    if (filterDecision === 'EXECUTIONS') {
      return dec.includes('SELL') || dec.includes('BUY') || dec.includes('ROLL') || dec.includes('CLOSE') || dec.includes('OPEN');
    }
    if (filterDecision === 'HOLD') {
      return dec.includes('HOLD') && !dec.includes('SELL') && !dec.includes('BUY') && !dec.includes('ROLL') && !dec.includes('CLOSE');
    }
    return dec.includes(filterDecision);
  }).sort((a, b) => {
    if (sortField === 'timestamp') {
      const dateA = new Date((a.timestamp || '').replace(' ', 'T')).getTime() || 0;
      const dateB = new Date((b.timestamp || '').replace(' ', 'T')).getTime() || 0;
      return sortDirection === 'asc' ? dateA - dateB : dateB - dateA;
    }
    if (sortField === 'decision') {
      const decA = a.ai_decision || '';
      const decB = b.ai_decision || '';
      return sortDirection === 'asc' ? decA.localeCompare(decB) : decB.localeCompare(decA);
    }
    return 0;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500 pb-10">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:justify-between md:items-end gap-4 border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight">Pulse History</h1>
          <p className="text-white/50 mt-2 font-mono text-sm flex items-center tracking-widest">
            <Terminal size={14} className="text-cyber-green mr-2" />
            AI MEMORY & AUDIT LOG
          </p>
        </div>
        
        <div className="flex items-center bg-black/40 border border-white/10 rounded-lg px-4 py-2 self-start md:self-auto">
          <Search size={16} className="text-white/40 mr-2" />
          <span className="font-mono text-sm text-white/40">{filteredPulses.length} / {pulses.length} EVENTS</span>
        </div>
      </div>

      {/* Excel-Style Filter Controls Bar */}
      <div className="glass-panel p-4 rounded-xl border border-white/10 flex flex-wrap items-center justify-between gap-4 bg-white/[0.01]">
        <div className="flex items-center space-x-2 flex-wrap gap-y-2">
          <span className="text-xs font-mono text-white/40 flex items-center mr-2">
            <Filter size={14} className="mr-1.5 text-cyber-green" /> FILTER DECISIONS:
          </span>
          {['ALL', 'EXECUTIONS', 'HOLD', 'ROLL', 'SELL', 'CLOSE'].map((type) => (
            <button
              key={type}
              onClick={() => setFilterDecision(type)}
              className={`px-3 py-1.5 rounded-md text-xs font-mono transition-all ${
                filterDecision === type
                  ? 'bg-cyber-green/20 text-cyber-green border border-cyber-green/40 shadow-[0_0_10px_rgba(0,230,118,0.2)]'
                  : 'bg-white/5 text-white/60 hover:text-white border border-white/5'
              }`}
            >
              {type === 'EXECUTIONS' ? '⚡ ACTIVE TRADES ONLY' : type}
            </button>
          ))}
        </div>

        <div className="flex items-center space-x-3">
          <span className="text-xs font-mono text-white/40">SORT BY:</span>
          <button
            onClick={() => toggleSort('timestamp')}
            className={`px-3 py-1.5 rounded-md text-xs font-mono flex items-center border transition-all ${
              sortField === 'timestamp'
                ? 'bg-blue-500/20 text-blue-400 border-blue-500/40'
                : 'bg-white/5 text-white/60 border-white/5 hover:text-white'
            }`}
          >
            TIMESTAMP {sortField === 'timestamp' && (sortDirection === 'asc' ? <ArrowUp size={12} className="ml-1" /> : <ArrowDown size={12} className="ml-1" />)}
          </button>
          <button
            onClick={() => toggleSort('decision')}
            className={`px-3 py-1.5 rounded-md text-xs font-mono flex items-center border transition-all ${
              sortField === 'decision'
                ? 'bg-blue-500/20 text-blue-400 border-blue-500/40'
                : 'bg-white/5 text-white/60 border-white/5 hover:text-white'
            }`}
          >
            DECISION {sortField === 'decision' && (sortDirection === 'asc' ? <ArrowUp size={12} className="ml-1" /> : <ArrowDown size={12} className="ml-1" />)}
          </button>
        </div>
      </div>

      {/* Terminal Log Table */}
      <div className="glass-panel overflow-hidden border border-white/10 rounded-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-black/60 border-b border-white/10 text-xs font-mono tracking-widest text-white/50">
                <th 
                  onClick={() => toggleSort('timestamp')}
                  className="p-4 font-normal cursor-pointer hover:text-white transition-colors select-none flex items-center"
                >
                  TIMESTAMP {sortField === 'timestamp' ? (sortDirection === 'asc' ? '↑' : '↓') : <ArrowUpDown size={12} className="inline ml-1 opacity-30" />}
                </th>
                <th className="p-4 font-normal">PRICE</th>
                <th className="p-4 font-normal">VIX</th>
                <th 
                  onClick={() => toggleSort('decision')}
                  className="p-4 font-normal cursor-pointer hover:text-white transition-colors select-none"
                >
                  DECISION {sortField === 'decision' ? (sortDirection === 'asc' ? '↑' : '↓') : <ArrowUpDown size={12} className="inline ml-1 opacity-30" />}
                </th>
                <th className="p-4 font-normal w-1/2">REASONING</th>
              </tr>
            </thead>
            <tbody className="font-mono text-sm divide-y divide-white/5">
              {loading ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center text-white/30 border-dashed">LOADING MEMORY LOGS...</td>
                </tr>
              ) : filteredPulses.length === 0 ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center text-white/40 border-dashed">NO PULSE EVENTS MATCHING "{filterDecision}" FILTER</td>
                </tr>
              ) : (
                filteredPulses.map((pulse, i) => {
                  const decisions = Array.from(new Set((pulse.ai_decision || '').split(', ')));
                  const reasons = (pulse.ai_reasoning || '').split(' | ');
                  
                  return (
                    <tr key={i} className="hover:bg-white/5 transition-colors group">
                      <td className="p-4 text-white/60 whitespace-nowrap align-top">
                        {pulse.timestamp ? new Date(pulse.timestamp.replace(' ', 'T')).toLocaleString('en-US', { month: 'short', day: '2-digit', hour: '2-digit', minute:'2-digit' }) : '--'}
                      </td>
                      <td className="p-4 text-white align-top">${pulse.aapl_price}</td>
                      <td className="p-4 text-yellow-500/80 align-top">{pulse.vix_level}</td>
                      <td className="p-4 align-top">
                        <div className="flex flex-col gap-1 items-start">
                          {decisions.map((decision, idx) => (
                            <span key={idx} className={`px-2 py-1 rounded text-[10px] border ${getDecisionColor(decision)}`}>
                              {decision}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="p-4 text-cyber-green/70 text-xs leading-relaxed max-w-xl group-hover:text-cyber-green transition-colors align-top">
                        <div className="space-y-2">
                          {reasons.map((reason, idx) => (
                            <p key={idx} className="flex items-start">
                              <span className="text-white/20 mr-2 font-bold mt-px">›</span>
                              <span>{reason}</span>
                            </p>
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
