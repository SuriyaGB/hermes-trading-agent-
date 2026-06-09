"use client";

import { useEffect, useState } from 'react';
import {
  GitCompare,
  TrendingUp,
  Activity,
  Cpu,
  DollarSign,
  ShieldCheck,
  AlertTriangle,
  ArrowUpRight,
  TrendingDown,
  RefreshCw,
  Terminal,
  Server
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

import { getApiUrl, getThetaGangApiUrl } from '../../utils/api';

export default function AgentComparison() {
  const [hermesData, setHermesData] = useState({
    portfolio: { total_cash: 0, realized_pnl: 0, positions: [] },
    status: { current_phase: 'LOADING' },
    pulses: [],
    health: { status: 'LOADING' },
    incomeHistory: []
  });

  const [thetaData, setThetaData] = useState({
    live: null,
    loading: true,
    error: null
  });

  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const hermesApi = getApiUrl();
      const thetaApi = getThetaGangApiUrl();

      // 1. Fetch Hermes Data
      try {
        const portRes = await fetch(`/api/proxy?url=${encodeURIComponent(`${hermesApi}/api/portfolio?t=${Date.now()}`)}`);
        const statRes = await fetch(`/api/proxy?url=${encodeURIComponent(`${hermesApi}/api/status?t=${Date.now()}`)}`);
        const pulseRes = await fetch(`/api/proxy?url=${encodeURIComponent(`${hermesApi}/api/pulses?limit=30&t=${Date.now()}`)}`);
        const healthRes = await fetch(`/api/proxy?url=${encodeURIComponent(`${hermesApi}/api/health?t=${Date.now()}`)}`);
        const incomeRes = await fetch(`/api/proxy?url=${encodeURIComponent(`${hermesApi}/api/income_history?t=${Date.now()}`)}`);

        let portfolio = { total_cash: 250000, realized_pnl: 0, positions: [] };
        let status = { current_phase: 'UNKNOWN' };
        let pulses = [];
        let health = { status: 'OFFLINE' };
        let incomeHistory = [];

        if (portRes.ok) portfolio = await portRes.json();
        if (statRes.ok) status = await statRes.json();
        if (pulseRes.ok) pulses = await pulseRes.json();
        if (healthRes.ok) health = await healthRes.json();
        if (incomeRes.ok) incomeHistory = await incomeRes.json();

        setHermesData({ portfolio, status, pulses, health, incomeHistory });
      } catch (err) {
        console.error("Error loading Hermes data", err);
        setHermesData(prev => ({ ...prev, health: { status: 'OFFLINE' } }));
      }

      // 2. Fetch ThetaGang Data
      try {
        const targetUrl = thetaApi.includes('vercel.app')
          ? `${thetaApi}/data.json?t=${Date.now()}`
          : `${thetaApi}/api/data?t=${Date.now()}`;
        const proxyUrl = `/api/proxy?url=${encodeURIComponent(targetUrl)}`;
        const thetaRes = await fetch(proxyUrl);
        if (thetaRes.ok) {
          const live = await thetaRes.json();
          setThetaData({ live, loading: false, error: null });
        } else {
          setThetaData({ live: null, loading: false, error: 'API returned error code' });
        }
      } catch (err) {
        console.error("Error loading ThetaGang data", err);
        setThetaData({ live: null, loading: false, error: 'Cannot connect to backend' });
      }

      setLoading(false);
    };

    fetchData();
  }, [refreshKey]);

  // Derived Metrics for Hermes
  const hermesCash = hermesData.portfolio?.total_cash || 250000;
  const hermesPositions = hermesData.portfolio?.positions || [];
  let hermesLiability = 0;
  let hermesCollateral = 0;
  let hermesPremium = 0;
  let hermesUnrealized = 0;
  
  hermesPositions.forEach(pos => {
    if (pos.type === 'Option') {
      const price = pos.current_price || pos.avg_cost || 0;
      const qty = Math.abs(pos.quantity || 1);
      hermesLiability += price * qty * 100;
      hermesCollateral += (pos.strike || 0) * qty * 100;
      hermesPremium += (pos.avg_cost || 0) * qty * 100;
      hermesUnrealized += (pos.unrealized_pnl || 0);
    }
  });
  
  const hermesNetLiq = hermesCash - hermesLiability;
  const hermesRealized = hermesData.portfolio?.realized_pnl || 0;
  const hermesInterest = hermesCash - 250000 - hermesPremium - hermesRealized;

  // Derived Metrics for ThetaGang
  const thetaLive = thetaData.live;
  const thetaNetLiq = thetaLive?.summary?.totalValue !== undefined ? thetaLive.summary.totalValue : 250000;
  const thetaCash = thetaLive?.summary?.totalCash !== undefined ? thetaLive.summary.totalCash : 250000;
  const thetaAvailable = thetaLive?.summary?.availableCash !== undefined ? thetaLive.summary.availableCash : 250000;
  const thetaPositions = thetaLive?.positions || [];
  
  let thetaCollateral = 0;
  let thetaPremium = 0;
  let thetaUnrealized = 0;
  
  thetaPositions.forEach(pos => {
    if (pos.secType === 'OPT') {
      thetaCollateral += (pos.strike || 0) * Math.abs(pos.quantity) * 100;
      thetaPremium += (pos.entryPrice || 0) * Math.abs(pos.quantity) * 100;
      thetaUnrealized += (pos.pnl || 0);
    }
  });
  
  // Realized PnL is confirmed 0 from IBKR; remainder is interest
  const thetaInterest = thetaCash - 250000 - thetaPremium;

  // Reconstruct Combined Performance History
  const combineHistoryData = () => {
    // If we don't have performance arrays, return mock data
    if (!thetaLive?.performance && !hermesData.pulses) return [];

    const dataMap = {};

    // Process ThetaGang History
    if (thetaLive?.performance) {
      thetaLive.performance.forEach(pt => {
        // Parse time to YYYY-MM-DD
        const dateStr = pt.fullTime ? pt.fullTime.split(' ')[0] : '';
        if (dateStr) {
          if (!dataMap[dateStr]) dataMap[dateStr] = {};
          dataMap[dateStr].theta = pt.value;
        }
      });
    }

    // Process Hermes history (Real Balance History)
    if (hermesData.incomeHistory) {
      hermesData.incomeHistory.forEach(item => {
        const dateStr = item.timestamp ? item.timestamp.split(' ')[0] : '';
        if (dateStr) {
          if (!dataMap[dateStr]) dataMap[dateStr] = {};
          dataMap[dateStr].hermes = item.balance;
        }
      });
    }

    // Sort dates chronologically and build points
    const sortedDates = Object.keys(dataMap).filter(date => date >= '2026-05-27').sort();

    // Fill in starting values for clean chart visualization
    let lastHermes = 250000;
    let lastTheta = 250000;

    return sortedDates.map(date => {
      const hVal = dataMap[date].hermes || lastHermes;
      const tVal = dataMap[date].theta || lastTheta;
      lastHermes = hVal;
      lastTheta = tVal;

      const parts = date.split('-');
      const formattedDate = parts.length === 3 ? `${parts[1]}/${parts[2]}` : date;

      return {
        date: formattedDate,
        "Hermes Net Liq": hVal,
        "ThetaGang Net Liq": tVal
      };
    });
  };

  const chartData = combineHistoryData();

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500 pb-10">

      {/* Page Header */}
      <div className="flex justify-between items-end border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight flex items-center gap-3">
            <GitCompare className="text-cyber-green" size={32} />
            Agent Comparison
          </h1>
          <p className="text-white/50 mt-2 font-mono text-xs flex items-center tracking-widest">
            <Activity size={12} className="text-cyber-green mr-2 animate-pulse" />
            SIDE-BY-SIDE VPS AUDIT & METRICS
          </p>
        </div>
        <button
          onClick={() => setRefreshKey(prev => prev + 1)}
          disabled={loading}
          className="flex items-center gap-2 text-xs font-mono bg-white/5 border border-white/10 px-4 py-2 rounded-lg hover:bg-white/10 hover:text-white transition-all text-white/70"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          REFRESH SYSTEMS
        </button>
      </div>

      {/* Online Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Hermes Status Panel */}
        <div className="glass-panel p-5 flex items-center justify-between border-l-4 border-l-cyber-green">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-cyber-green/10 flex items-center justify-center border border-cyber-green/20">
              <Cpu className="text-cyber-green" size={20} />
            </div>
            <div>
              <h3 className="font-semibold text-white">Hermes Custom Agent</h3>
              <p className="text-xs text-white/40 font-mono">VPS: 76.13.242.106 | PM2 Active</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-white/50">SYSTEM:</span>
            {hermesData.health?.status === 'ALIVE' ? (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-cyber-green/10 border border-cyber-green/30 text-cyber-green flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-cyber-green animate-pulse"></span> ONLINE
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-red-500/10 border border-red-500/30 text-red-500 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span> OFFLINE
              </span>
            )}
          </div>
        </div>

        {/* ThetaGang Status Panel */}
        <div className="glass-panel p-5 flex items-center justify-between border-l-4 border-l-cyan-400">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-cyan-400/10 flex items-center justify-center border border-cyan-400/20">
              <Server className="text-cyan-400" size={20} />
            </div>
            <div>
              <h3 className="font-semibold text-white">ThetaGang Core</h3>
              <p className="text-xs text-white/40 font-mono">VPS Port 8080 | SQLite Active</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-white/50">SYSTEM:</span>
            {!thetaData.error && thetaLive ? (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-cyan-400/10 border border-cyan-400/30 text-cyan-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span> ONLINE
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-red-500/10 border border-red-500/30 text-red-500 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span> OFFLINE
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Side-by-Side Balance Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

        {/* Hermes Agent Metrics */}
        <div className="space-y-4">
          <h3 className="text-sm font-mono text-cyber-green tracking-widest uppercase flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyber-green"></span>
            Hermes Financial Summary
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="glass-panel p-5 bg-white/[0.02]">
              <p className="text-xs text-white/40 font-mono tracking-wider flex justify-between">
                <span>NET LIQ (REAL)</span>
              </p>
              <p className="text-xl sm:text-2xl font-light text-white mt-1">
                ${hermesNetLiq.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            <div className="glass-panel p-5 bg-white/[0.02] border border-cyber-green/20 relative">
              <p className="text-xs text-white/40 font-mono tracking-wider">TOTAL CASH</p>
              <p className="text-xl sm:text-2xl font-light text-cyber-green mt-1">
                ${hermesCash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
              <div className="mt-2 text-[10px] font-mono text-white/50 flex justify-between">
                <span>Premium: ${hermesPremium.toLocaleString()}</span>
                <span>Interest: ${Math.max(0, hermesInterest).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
              </div>
            </div>
            <div className="glass-panel p-5 bg-white/[0.02]">
              <p className="text-xs text-white/40 font-mono tracking-wider">UNREALIZED P&L</p>
              <p className={`text-xl sm:text-2xl font-light mt-1 ${hermesUnrealized >= 0 ? 'text-cyber-green' : 'text-red-400'}`}>
                {hermesUnrealized >= 0 ? '+' : ''}${hermesUnrealized.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            <div className="glass-panel p-5 bg-white/[0.02]">
              <p className="text-xs text-white/40 font-mono tracking-wider">REALIZED PROFIT</p>
              <p className="text-xl sm:text-2xl font-light text-white mt-1">
                ${hermesRealized.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>
        </div>

        {/* ThetaGang Agent Metrics */}
        <div className="space-y-4">
          <h3 className="text-sm font-mono text-cyan-400 tracking-widest uppercase flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
            ThetaGang Financial Summary
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="glass-panel p-5 bg-white/[0.02] relative">
              <p className="text-xs text-white/40 font-mono tracking-wider flex justify-between">
                <span>NET LIQ (REPORTED)</span>
                <AlertTriangle size={14} className="text-yellow-500" title="API pricing may be stale" />
              </p>
              <p className="text-xl sm:text-2xl font-light text-white mt-1">
                ${thetaNetLiq.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            <div className="glass-panel p-5 bg-white/[0.02] border border-cyan-400/20 relative">
              <p className="text-xs text-white/40 font-mono tracking-wider">TOTAL CASH</p>
              <p className="text-xl sm:text-2xl font-light text-cyan-400 mt-1">
                ${thetaCash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
              <div className="mt-2 text-[10px] font-mono text-white/50 flex justify-between">
                <span>Premium: ${thetaPremium.toLocaleString()}</span>
                <span className="text-yellow-400">Interest: ${Math.max(0, thetaInterest).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
              </div>
            </div>
            <div className="glass-panel p-5 bg-white/[0.02] relative">
              <p className="text-xs text-white/40 font-mono tracking-wider flex justify-between">
                <span>UNREALIZED P&L</span>
                <AlertTriangle size={14} className="text-yellow-500" title="API pricing may be stale" />
              </p>
              <p className={`text-xl sm:text-2xl font-light mt-1 ${thetaUnrealized >= 0 ? 'text-cyan-400' : 'text-red-400'}`}>
                {thetaUnrealized >= 0 ? '+' : ''}${thetaUnrealized.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            <div className="glass-panel p-5 bg-white/[0.02]">
              <p className="text-xs text-white/40 font-mono tracking-wider">REALIZED PROFIT</p>
              <p className="text-xl sm:text-2xl font-light text-white mt-1">
                $0.00 <span className="text-[10px] text-white/30 ml-1">(IBKR Verified)</span>
              </p>
            </div>
          </div>
        </div>

      </div>

      {/* Net Liquidation Progress Chart */}
      {chartData.length > 0 && (
        <div className="glass-panel p-6">
          <h3 className="text-sm font-mono text-white/60 tracking-wider mb-6 flex items-center gap-2">
            <TrendingUp size={16} className="text-cyber-green" />
            EQUITY COMPARISON TIMELINE (NET LIQ IN USD)
          </h3>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorHermes" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00E676" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#00E676" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorTheta" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00D6FF" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#00D6FF" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" stroke="rgba(255,255,255,0.4)" fontSize={10} fontStyle="monospace" />
                <YAxis
                  stroke="rgba(255,255,255,0.4)"
                  fontSize={10}
                  fontStyle="monospace"
                  domain={['dataMin - 1000', 'dataMax + 1000']}
                  tickFormatter={(val) => `$${val.toLocaleString()}`}
                />
                <Tooltip
                  contentStyle={{ background: '#0d1117', borderColor: 'rgba(255,255,255,0.1)', color: '#fff', fontSize: '12px', fontFamily: 'monospace' }}
                  formatter={(value) => [`$${value.toLocaleString()}`]}
                />
                <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }} />
                <Area type="monotone" dataKey="Hermes Net Liq" stroke="#00E676" fillOpacity={1} fill="url(#colorHermes)" strokeWidth={2} />
                <Area type="monotone" dataKey="ThetaGang Net Liq" stroke="#00D6FF" fillOpacity={1} fill="url(#colorTheta)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Side-by-Side Position Boards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Hermes Positions */}
        <div className="glass-panel p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-mono text-cyber-green tracking-wider mb-6 flex items-center justify-between">
              <span>HERMES ACTIVE POSITIONS ({hermesPositions.length})</span>
              <span className="text-[10px] text-white/30 font-mono">COLLATERAL: ${hermesCollateral.toLocaleString()}</span>
            </h3>

            {hermesPositions.length > 0 ? (
              <div className="space-y-4">
                {hermesPositions.map((pos, idx) => {
                  const isProfit = (pos.unrealized_pnl || 0) >= 0;
                  return (
                    <div
                      key={idx}
                      className="p-4 rounded-xl border border-white/5 relative overflow-hidden bg-white/[0.01]"
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-cyber-green/10 text-cyber-green border border-cyber-green/20">
                              {pos.symbol}
                            </span>
                            <span className="text-[10px] text-white/50 font-mono">
                              {pos.strike ? `Strike $${pos.strike}` : 'STOCK'}
                            </span>
                          </div>
                          <p className="text-[10px] text-white/30 font-mono mt-2">
                            EXP: {pos.expiry || '--'} | QTY: {pos.quantity}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-[10px] text-white/40 font-mono">UNREALIZED P&L</p>
                          <p className={`text-sm font-semibold font-mono ${isProfit ? 'text-cyber-green' : 'text-red-400'}`}>
                            {isProfit ? '+' : ''}{pos.unrealized_pnl ? `$${pos.unrealized_pnl.toFixed(2)}` : '--'}
                            <span className="text-[10px] opacity-60 ml-1">
                              ({pos.unrealized_pnl_percent ? `${pos.unrealized_pnl_percent.toFixed(1)}%` : '--'})
                            </span>
                          </p>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 mt-3 pt-3 border-t border-white/5 text-[10px] font-mono">
                        <div>
                          <span className="text-white/30">Entry Avg: </span>
                          <span className="text-white/80">${pos.avg_cost ? pos.avg_cost.toFixed(2) : '--'}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-white/30">Market Mid: </span>
                          <span className="text-white/80">${pos.current_price ? pos.current_price.toFixed(2) : '--'}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="p-8 text-center border border-dashed border-white/10 rounded-xl text-white/40 text-xs font-mono">
                No active option positions. (CASH ONLY PHASE)
              </div>
            )}
          </div>
        </div>

        {/* ThetaGang Positions */}
        <div className="glass-panel p-6 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-mono text-cyan-400 tracking-wider mb-6 flex items-center justify-between">
              <span>THETAGANG ACTIVE POSITIONS ({thetaPositions.reduce((acc, pos) => acc + Math.abs(pos.quantity || 0), 0)})</span>
              <span className="text-[10px] text-white/30 font-mono">COLLATERAL: ${thetaCollateral.toLocaleString()}</span>
            </h3>

            {thetaPositions.length > 0 ? (
              <div className="space-y-4">
                {thetaPositions.map((pos, idx) => {
                  const isProfit = (pos.pnl || 0) >= 0;
                  return (
                    <div
                      key={idx}
                      className="p-4 rounded-xl border border-white/5 relative overflow-hidden bg-white/[0.01]"
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-cyan-400/10 text-cyan-400 border border-cyan-400/20">
                              {pos.symbol}
                            </span>
                          </div>
                          <p className="text-[10px] text-white/30 font-mono mt-2">
                            TYPE: {pos.type} | QTY: {pos.quantity}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-[10px] text-white/40 font-mono">UNREALIZED P&L</p>
                          <p className={`text-sm font-semibold font-mono ${isProfit ? 'text-cyan-400' : 'text-red-400'}`}>
                            {isProfit ? '+' : ''}${pos.pnl ? pos.pnl.toFixed(2) : '0.00'}
                            <span className="text-[10px] opacity-60 ml-1">
                              ({pos.pnlPercent ? `${pos.pnlPercent.toFixed(1)}%` : '0%'})
                            </span>
                          </p>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 mt-3 pt-3 border-t border-white/5 text-[10px] font-mono">
                        <div>
                          <span className="text-white/30">Entry Avg: </span>
                          <span className="text-white/80">${pos.entryPrice ? pos.entryPrice.toFixed(2) : '0.00'}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-white/30">Market Price: </span>
                          <span className="text-white/80">${pos.marketPrice ? pos.marketPrice.toFixed(2) : '0.00'}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="p-8 text-center border border-dashed border-white/10 rounded-xl text-white/40 text-xs font-mono">
                No active option positions. (CASH ONLY)
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Live Decisions Comparison logs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Hermes Decision Log */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-mono text-cyber-green tracking-wider mb-4 flex items-center gap-2">
            <Terminal size={14} />
            HERMES DECISION PULSES (LATEST)
          </h3>
          <div className="max-h-80 overflow-y-auto space-y-3 pr-2 scrollbar-thin">
            {hermesData.pulses && hermesData.pulses.length > 0 ? (
              hermesData.pulses
                .filter(p => p.timestamp && p.timestamp >= '2026-05-27')
                .slice(0, 8)
                .map((pulse, idx) => (
                <div key={idx} className="p-3 bg-white/[0.01] border border-white/5 rounded-lg text-xs font-mono space-y-1">
                  <div className="flex justify-between items-center text-[10px] text-white/40">
                    <span>{pulse.timestamp}</span>
                    <span className="text-cyber-green uppercase font-semibold">{pulse.ai_decision}</span>
                  </div>
                  <p className="text-white/80 font-normal leading-relaxed">{pulse.ai_reasoning}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-white/30 font-mono py-4 text-center">No pulse history found.</p>
            )}
          </div>
        </div>

        {/* ThetaGang Decision Log */}
        <div className="glass-panel p-6">
          <h3 className="text-sm font-mono text-cyan-400 tracking-wider mb-4 flex items-center gap-2">
            <Terminal size={14} />
            THETAGANG EXECUTION DECISIONS (LATEST)
          </h3>
          <div className="max-h-80 overflow-y-auto space-y-3 pr-2 scrollbar-thin">
            {thetaLive?.shoppingList && thetaLive.shoppingList.length > 0 ? (
              thetaLive.shoppingList.slice(0, 8).map((dec, idx) => {
                const isWrite = dec.action === 'Write';
                return (
                  <div key={idx} className="p-3 bg-white/[0.01] border border-white/5 rounded-lg text-xs font-mono space-y-1">
                    <div className="flex justify-between items-center text-[10px] text-white/40">
                      <span>{dec.time}</span>
                      <span className={`uppercase font-semibold ${isWrite ? 'text-cyan-400' : 'text-white/50'}`}>
                        {dec.action} ({dec.symbol})
                      </span>
                    </div>
                    <p className="text-white/80 font-normal leading-relaxed">{dec.detail}</p>
                    {dec.contract && (
                      <p className="text-[10px] text-yellow-400/80 bg-yellow-400/5 px-2 py-0.5 rounded inline-block mt-1 border border-yellow-400/10">
                        {dec.contract}
                      </p>
                    )}
                  </div>
                );
              })
            ) : (
              <p className="text-xs text-white/30 font-mono py-4 text-center">No decision records found.</p>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
