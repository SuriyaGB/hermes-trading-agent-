"use client";

import { useEffect, useState } from 'react';
import { 
  ArrowUpRight, 
  ShieldCheck, 
  Zap, 
  Activity, 
  Cpu, 
  TrendingUp, 
  Target, 
  Calendar, 
  DollarSign, 
  AlertTriangle,
  Info
} from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';

import { getApiUrl } from '../utils/api';

export default function CommandCentre() {
  const [portfolio, setPortfolio] = useState({ total_cash: 0, realized_pnl: 0, positions: [] });
  const [status, setStatus] = useState({ current_phase: 'LOADING' });
  const [pulses, setPulses] = useState([]);
  const [lastPulse, setLastPulse] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch data from our Python FastAPI backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        const apiUrl = getApiUrl();        
        
        // 1. Fetch Portfolio
        const portRes = await fetch(`/api/proxy?url=${encodeURIComponent(`${apiUrl}/api/portfolio?t=${Date.now()}`)}`);
        if (portRes.ok) {
          const portData = await portRes.json();
          if (portData && typeof portData.total_cash === 'number') {
            setPortfolio(portData);
          }
        }

        // 2. Fetch Status
        const statRes = await fetch(`/api/proxy?url=${encodeURIComponent(`${apiUrl}/api/status?t=${Date.now()}`)}`);
        if (statRes.ok) {
          const statData = await statRes.json();
          setStatus(statData);
        }

        // 3. Fetch Last 20 Pulses for the chart
        const pulseRes = await fetch(`/api/proxy?url=${encodeURIComponent(`${apiUrl}/api/pulses?limit=20&t=${Date.now()}`)}`);
        if (pulseRes.ok) {
          const pulseData = await pulseRes.json();
          if (Array.isArray(pulseData) && pulseData.length > 0) {
            setLastPulse(pulseData[0]);
            // Reverse so oldest is on left, newest is on right
            setPulses([...pulseData].reverse());
          }
        }
      } catch (error) {
        console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  const activePosition = portfolio.positions?.[0] || null;
  const currentDelta = lastPulse ? lastPulse.delta_current : '--';
  const currentDte = lastPulse ? lastPulse.dte_current : '--';

  // Wheel Phase Node Coordinates for the SVG Visualizer
  const phaseNodes = [
    { id: 'CASH_ONLY', label: '1. CASH ONLY', x: 200, y: 50, color: '#3B82F6', desc: 'Selling Put Options' },
    { id: 'CSP_ACTIVE', label: '2. PUT SOLD', x: 350, y: 150, color: '#00E676', desc: 'Cash Secured Put active' },
    { id: 'SHARES_ASSIGNED', label: '3. ASSIGNED', x: 200, y: 250, color: '#FFEA00', desc: 'Stock shares assigned' },
    { id: 'CC_ACTIVE', label: '4. CALL SOLD', x: 50, y: 150, color: '#A855F7', desc: 'Covered Call active' }
  ];

  // Helper to format date strings for chart X-axis
  const formatChartDate = (timestamp) => {
    if (!timestamp) return '';
    const d = new Date(timestamp);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Helper to format option expiry date YYYYMMDD to human-readable
  const formatExpiryDate = (dateStr) => {
    if (!dateStr) return '--';
    const dateStrClean = String(dateStr).trim();
    if (dateStrClean.length === 8) {
      const year = dateStrClean.substring(0, 4);
      const month = dateStrClean.substring(4, 6);
      const day = dateStrClean.substring(6, 8);
      
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      const monthIdx = parseInt(month, 10) - 1;
      if (monthIdx >= 0 && monthIdx < 12) {
        return `${months[monthIdx]} ${parseInt(day, 10)}, ${year}`;
      }
      return `${year}-${month}-${day}`;
    }
    return dateStr;
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500 pb-10">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight bg-gradient-to-r from-white via-white/90 to-white/50 bg-clip-text text-transparent">Command Centre</h1>
          <p className="text-white/50 mt-2 font-mono text-xs flex items-center tracking-widest">
            <Zap size={12} className="text-cyber-green mr-2 animate-pulse" />
            HERMES QUANTUM RUNNING
          </p>
        </div>
        <div className="hidden sm:flex items-center space-x-2 text-xs font-mono bg-black/40 px-3 py-1.5 rounded-lg border border-white/5">
          <span className="w-2 h-2 rounded-full bg-cyber-green animate-pulse"></span>
          <span className="text-white/40">FEED DELAY: </span>
          <span className="text-white/80">REALTIME</span>
        </div>
      </div>

      {/* Top HUD Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="glass-panel p-6 relative overflow-hidden group transition-all duration-300 hover:border-white/10">
          <div className="absolute -top-10 -right-10 w-24 h-24 bg-blue-500/5 rounded-full blur-2xl group-hover:bg-blue-500/10 transition-all"></div>
          <div className="flex items-center space-x-2 text-white/40 font-mono text-xs mb-2 tracking-widest">
            <DollarSign size={12} />
            <span>ACCOUNT EQUITY (NET LIQ)</span>
          </div>
          <h2 className="text-3xl font-light tracking-tight">
            ${((portfolio?.total_cash || 250000) - (portfolio?.positions || []).reduce((acc, pos) => {
              if (pos.type === 'Option') {
                const price = pos.current_price !== undefined ? pos.current_price : (pos.avg_cost || 0);
                const qty = Math.abs(pos.quantity || 1);
                return acc + (price * qty * 100);
              }
              return acc;
            }, 0)).toLocaleString('en-US', {minimumFractionDigits: 2})}
          </h2>
        </div>
        
        <div className="glass-panel p-6 relative overflow-hidden group transition-all duration-300 hover:border-white/10">
          <div className="absolute -top-10 -right-10 w-24 h-24 bg-cyber-green/5 rounded-full blur-2xl group-hover:bg-cyber-green/10 transition-all"></div>
          <div className="flex items-center space-x-2 text-white/40 font-mono text-xs mb-2 tracking-widest">
            <TrendingUp size={12} className="text-cyber-green" />
            <span>REALIZED PREMIUM</span>
          </div>
          <div className="flex items-baseline space-x-1">
            <h2 className="text-3xl font-light text-cyber-green">
              ${(portfolio?.realized_pnl ?? 0).toLocaleString('en-US', {minimumFractionDigits: 2})}
            </h2>
            <span className="text-[10px] text-cyber-green/50 font-mono">USD</span>
          </div>
        </div>

        <div className="glass-panel p-6 relative overflow-hidden group transition-all duration-300 hover:border-white/10">
          <div className="absolute -top-10 -right-10 w-24 h-24 bg-yellow-500/5 rounded-full blur-2xl group-hover:bg-yellow-500/10 transition-all"></div>
          <div className="flex items-center space-x-2 text-white/40 font-mono text-xs mb-2 tracking-widest">
            <Activity size={12} className="text-yellow-500" />
            <span>LIQUID CASH</span>
          </div>
          <h2 className="text-3xl font-light">
            ${(portfolio?.total_cash ?? 250000).toLocaleString('en-US', {minimumFractionDigits: 2})}
          </h2>
        </div>
        
        <div className="glass-panel p-6 relative overflow-hidden group transition-all duration-300 hover:border-white/10">
          <div className="absolute -top-10 -right-10 w-24 h-24 bg-purple-500/5 rounded-full blur-2xl group-hover:bg-purple-500/10 transition-all"></div>
          <div className="flex items-center space-x-2 text-white/40 font-mono text-xs mb-2 tracking-widest">
            <Cpu size={12} className="text-purple-400" />
            <span>ACTIVE STRATEGY</span>
          </div>
          <div className="flex items-center space-x-2 mt-1">
            <span className="w-2 h-2 rounded-full bg-cyber-green animate-pulse"></span>
            <span className="text-lg font-mono tracking-wider text-white">{status?.current_phase || 'LOADING'}</span>
          </div>
        </div>
      </div>

      {/* Interactive Visualizer Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column: Visual State Machine (SVG Diagram) */}
        <div className="glass-panel p-6 col-span-1 lg:col-span-5 flex flex-col items-center justify-center text-center min-h-[380px]">
          <h3 className="text-sm font-mono text-white/60 tracking-wider mb-6 flex items-center self-start">
            <Activity size={14} className="mr-2 text-cyber-green" /> WHEEL STATE FLOWMAP
          </h3>

          <div className="relative w-full max-w-[360px] aspect-[4/3] flex items-center justify-center">
            <svg viewBox="0 0 400 300" className="w-full h-full">
              {/* Connecting Curved Lines */}
              <path d="M 200,50 Q 300,50 350,150" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="2" />
              <path d="M 350,150 Q 350,250 200,250" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="2" />
              <path d="M 200,250 Q 100,250 50,150" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="2" />
              <path d="M 50,150 Q 100,50 200,50" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="2" />

              {/* Glowing active arrow */}
              {status?.current_phase === 'CASH_ONLY' && (
                <path d="M 50,150 Q 100,50 200,50" fill="none" stroke="#3B82F6" strokeWidth="3" className="animate-pulse" />
              )}
              {status?.current_phase === 'CSP_ACTIVE' && (
                <path d="M 200,50 Q 300,50 350,150" fill="none" stroke="#00E676" strokeWidth="3" className="animate-pulse" />
              )}
              {status?.current_phase === 'SHARES_ASSIGNED' && (
                <path d="M 350,150 Q 350,250 200,250" fill="none" stroke="#FFEA00" strokeWidth="3" className="animate-pulse" />
              )}
              {status?.current_phase === 'CC_ACTIVE' && (
                <path d="M 200,250 Q 100,250 50,150" fill="none" stroke="#A855F7" strokeWidth="3" className="animate-pulse" />
              )}

              {/* Render Nodes */}
              {phaseNodes.map((node) => {
                const isActive = status?.current_phase === node.id;
                return (
                  <g key={node.id}>
                    {/* Pulsing Backlight for Active Node */}
                    {isActive && (
                      <circle 
                        cx={node.x} 
                        cy={node.y} 
                        r="32" 
                        fill={node.color} 
                        opacity="0.15" 
                        className="animate-ping" 
                        style={{ transformOrigin: `${node.x}px ${node.y}px` }} 
                      />
                    )}
                    {/* Node Core */}
                    <circle 
                      cx={node.x} 
                      cy={node.y} 
                      r="20" 
                      fill={isActive ? node.color : '#161b22'} 
                      stroke={isActive ? '#ffffff' : 'rgba(255,255,255,0.1)'} 
                      strokeWidth={isActive ? 3 : 1}
                      style={{ transition: 'all 0.5s ease', filter: isActive ? `drop-shadow(0 0 10px ${node.color})` : 'none' }}
                    />
                    {/* Node Dot */}
                    <circle cx={node.x} cy={node.y} r="6" fill={isActive ? '#000' : '#8b949e'} />
                    
                    {/* Node Label Text */}
                    <text 
                      x={node.x} 
                      y={node.y - 30} 
                      textAnchor="middle" 
                      fill={isActive ? '#ffffff' : 'rgba(255,255,255,0.4)'} 
                      fontSize="10" 
                      fontFamily="monospace"
                      fontWeight={isActive ? 'bold' : 'normal'}
                    >
                      {node.label}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          
          {/* Active Phase details panel */}
          <div className="mt-4 px-4 py-2 bg-white/5 border border-white/5 rounded-lg w-full">
            {phaseNodes.map((n) => {
              if (status?.current_phase === n.id) {
                return (
                  <div key={n.id} className="animate-in fade-in duration-300">
                    <p className="text-xs font-mono text-white/50 tracking-wider">ACTIVE STATE DESCRIPTION</p>
                    <p className="text-sm font-medium mt-1" style={{ color: n.color }}>{n.desc}</p>
                  </div>
                );
              }
              return null;
            })}
          </div>
        </div>

        {/* Right Column: Live Position Card */}
        <div className="glass-panel p-6 col-span-1 lg:col-span-7 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-mono text-white/60 tracking-wider mb-6 flex items-center justify-between">
              <span className="flex items-center"><Target size={14} className="mr-2 text-cyber-green" /> ACTIVE WHEEL POSITION</span>
              <span className="text-xs opacity-50 font-normal">100 SHARES BIND</span>
            </h3>

            {activePosition ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in duration-500">
                {/* Visual Position Card */}
                <div className="relative p-6 rounded-xl border border-white/10 overflow-hidden" 
                     style={{
                       background: 'linear-gradient(135deg, rgba(25,25,35,0.6) 0%, rgba(10,10,15,0.8) 100%)',
                       boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
                     }}>
                  {/* Glowing background badge */}
                  <div className="absolute -bottom-8 -right-8 w-24 h-24 bg-cyber-green/5 rounded-full blur-xl"></div>
                  
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <span className="text-[10px] font-mono bg-cyber-green/20 text-cyber-green px-2 py-0.5 rounded border border-cyber-green/30">
                        {activePosition.option_type || 'STOCK'}
                      </span>
                      <h4 className="text-3xl font-light mt-1 tracking-tight">{activePosition.symbol || 'AAPL'}</h4>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] font-mono text-white/40">STRIKE</p>
                      <p className="text-xl font-mono text-white">${activePosition.strike || '--'}</p>
                    </div>
                  </div>

                  <div className="space-y-3 font-mono mt-6">
                    <div className="flex justify-between text-xs pb-2 border-b border-white/5">
                      <span className="text-white/40">Entry Price</span>
                      <span className="text-white">${activePosition.avg_cost ? activePosition.avg_cost.toFixed(2) : '--'}</span>
                    </div>
                    <div className="flex justify-between text-xs pb-2 border-b border-white/5">
                      <span className="text-white/40">Current Option Price</span>
                      <span className="text-white">${activePosition.current_price !== undefined ? activePosition.current_price.toFixed(2) : '--'}</span>
                    </div>
                    <div className="flex justify-between text-xs pb-2 border-b border-white/5">
                      <span className="text-white/40">Unrealized P&L</span>
                      <span className={activePosition.unrealized_pnl >= 0 ? "text-cyber-green" : "text-red-500"}>
                        {activePosition.unrealized_pnl !== undefined
                          ? `${activePosition.unrealized_pnl >= 0 ? '+' : ''}$${activePosition.unrealized_pnl.toFixed(2)} (${activePosition.unrealized_pnl_percent >= 0 ? '+' : ''}${activePosition.unrealized_pnl_percent.toFixed(1)}%)`
                          : '--'}
                      </span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-white/40">Contract Expiry</span>
                      <span className="text-white">{formatExpiryDate(activePosition.expiry)}</span>
                    </div>
                  </div>
                </div>

                {/* Metrics Breakdown Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-black/30 border border-white/5 p-4 rounded-lg flex flex-col justify-center">
                    <p className="text-[10px] font-mono text-white/40 mb-1">CONTRACT DELTA</p>
                    <p className="text-xl font-mono text-purple-400">{currentDelta}</p>
                    <span className="text-[9px] font-mono text-white/30 mt-1">Bound: ±0.20</span>
                  </div>

                  <div className="bg-black/30 border border-white/5 p-4 rounded-lg flex flex-col justify-center">
                    <p className="text-[10px] font-mono text-white/40 mb-1">DAYS TO EXPIRY</p>
                    <p className="text-xl font-mono text-yellow-500">{currentDte !== '--' ? `${currentDte} Days` : '--'}</p>
                    <span className="text-[9px] font-mono text-white/30 mt-1">Roll limit: 21</span>
                  </div>

                  <div className="bg-black/30 border border-white/5 p-4 rounded-lg flex flex-col justify-center col-span-2">
                    <p className="text-[10px] font-mono text-white/40 mb-1">YIELD AT RISK CAP</p>
                    <div className="flex justify-between items-baseline mt-1">
                      <p className="text-lg font-mono text-cyber-green">+$328.00</p>
                      <span className="text-[10px] font-mono text-cyber-green/60">+1.31% return</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center border border-white/5 border-dashed rounded-xl p-12 text-center text-white/30 font-mono text-sm">
                <AlertTriangle size={28} className="text-white/20 mb-3" />
                NO ACTIVE POSITION DEPLOYED
                <span className="text-[10px] text-white/20 mt-1">Waiting for entry threshold triggers...</span>
              </div>
            )}
          </div>

          {/* Quick Shields status summary */}
          <div className="grid grid-cols-3 gap-3 border-t border-white/5 pt-4 mt-6">
            <div className="flex items-center space-x-2 text-xs">
              <ShieldCheck size={14} className="text-cyber-green" />
              <span className="text-white/60">VIX: {lastPulse ? lastPulse.vix_level : '--'}</span>
            </div>
            <div className="flex items-center space-x-2 text-xs">
              <ShieldCheck size={14} className="text-cyber-green" />
              <span className="text-white/60">EARNINGS: {lastPulse ? `${lastPulse.earnings_days}d` : '--'}</span>
            </div>
            <div className="flex items-center space-x-2 text-xs">
              <ShieldCheck size={14} className="text-cyber-green" />
              <span className="text-white/60">AUTO-CRON: OK</span>
            </div>
          </div>
        </div>

      </div>

      {/* Live Market Chart & AI Brain Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column: Mini Chart */}
        <div className="glass-panel p-6 col-span-1 lg:col-span-7 h-[420px] flex flex-col relative">
          <h3 className="text-sm font-mono text-white/60 tracking-wider mb-6 flex items-center">
            <Calendar size={14} className="mr-2 text-blue-400" /> CORRELATION TIMELINE (AAPL VS VIX)
          </h3>

          {pulses.length > 0 ? (
            <div className="flex-1 w-full relative">
              <ResponsiveContainer width="100%" height="90%">
                <AreaChart data={pulses} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00E676" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#00E676" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorVix" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#FFEA00" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#FFEA00" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                  <XAxis dataKey="timestamp" stroke="rgba(255,255,255,0.2)" tick={{fill: 'rgba(255,255,255,0.4)', fontSize: 10, fontFamily: 'monospace'}} tickFormatter={formatChartDate} />
                  <YAxis yAxisId="left" stroke="rgba(255,255,255,0.2)" tick={{fill: '#00E676', fontSize: 10, fontFamily: 'monospace'}} domain={['auto', 'auto']} tickFormatter={(v) => `$${v}`} />
                  <YAxis yAxisId="right" orientation="right" stroke="rgba(255,255,255,0.2)" tick={{fill: '#FFEA00', fontSize: 10, fontFamily: 'monospace'}} domain={['auto', 'auto']} />
                  <Tooltip 
                    contentStyle={{ background: '#0d1117', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                    labelStyle={{ color: 'rgba(255,255,255,0.5)', fontFamily: 'monospace', fontSize: '11px' }}
                    itemStyle={{ fontFamily: 'monospace', fontSize: '12px' }}
                  />
                  <Area yAxisId="left" type="monotone" dataKey="aapl_price" stroke="#00E676" fillOpacity={1} fill="url(#colorPrice)" strokeWidth={2} name="AAPL" />
                  <Area yAxisId="right" type="monotone" dataKey="vix_level" stroke="#FFEA00" fillOpacity={1} fill="url(#colorVix)" strokeWidth={1.5} name="VIX" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex-grow flex items-center justify-center font-mono text-white/30 border border-white/5 border-dashed rounded-lg">
              LOADING TRACKER TIMELINE...
            </div>
          )}
        </div>

        {/* Right Column: AI Brain feed */}
        <div className="glass-panel p-6 col-span-1 lg:col-span-5 h-[420px] flex flex-col">
          <h3 className="text-sm font-mono text-white/60 tracking-wider mb-6 flex items-center justify-between">
            <span className="flex items-center"><Cpu size={14} className="mr-2 text-purple-400" /> AI QUANTUM REASONING</span>
            <span className="text-[10px] font-mono text-purple-400/70 bg-purple-500/10 px-2 py-0.5 border border-purple-500/20 rounded">LLM LOG</span>
          </h3>

          {lastPulse ? (
            <div className="flex-grow flex flex-col justify-between overflow-hidden">
              <div className="flex justify-between items-center bg-white/5 px-4 py-2.5 rounded-lg border border-white/5 mb-4">
                <span className="text-[10px] font-mono text-white/40">{new Date(lastPulse.timestamp).toLocaleString()}</span>
                <span className="text-xs font-mono text-cyber-green">{lastPulse.ai_decision}</span>
              </div>
              
              <div className="flex-1 bg-black/40 border border-white/5 p-4 rounded-lg overflow-y-auto leading-relaxed text-xs font-mono text-cyber-green/80 hover:text-cyber-green transition-colors">
                {lastPulse.ai_reasoning}
              </div>
            </div>
          ) : (
            <div className="flex-grow flex items-center justify-center text-white/30 font-mono text-sm border border-white/5 border-dashed rounded-lg p-12">
              AWAITING PULSE REASONING FEED...
            </div>
          )}
        </div>

      </div>

    </div>
  );
}
