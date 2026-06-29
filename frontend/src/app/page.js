"use client";

import { useEffect, useState } from 'react';
import {
  ShieldCheck, Zap, Activity, Cpu, TrendingUp, Target,
  DollarSign, AlertTriangle, Calendar, BarChart2, Award,
  ChevronRight, Clock, Maximize2, X, ZoomIn, ZoomOut, RotateCcw
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, ReferenceDot
} from 'recharts';
import { getApiUrl } from '../utils/api';

// ─── Helpers ─────────────────────────────────────────────────────────────────
function fmt$(v, dec = 2) {
  if (v === null || v === undefined || isNaN(v)) return '--';
  return `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })}`;
}
function fmtPct(v, dec = 1) {
  if (v === null || v === undefined || isNaN(v)) return '--';
  const n = Number(v);
  return `${n >= 0 ? '+' : ''}${n.toFixed(dec)}%`;
}
function formatExpiry(s) {
  if (!s) return '--';
  const st = String(s).trim();
  if (st.length === 8) {
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const m = parseInt(st.substring(4,6),10)-1;
    const d = parseInt(st.substring(6,8),10);
    const y = st.substring(0,4);
    return `${months[m]} ${d}, ${y}`;
  }
  return s;
}
function formatTs(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const month = months[d.getMonth()];
  const day = d.getDate();
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return `${month} ${day}, ${time}`;
}
function computeDte(expiryStr) {
  if (!expiryStr || expiryStr === 'N/A') return null;
  try {
    const s = String(expiryStr).trim();
    const y = parseInt(s.substring(0,4),10);
    const m = parseInt(s.substring(4,6),10)-1;
    const d = parseInt(s.substring(6,8),10);
    const exp = new Date(y,m,d);
    const now = new Date();
    now.setHours(0,0,0,0);
    return Math.max(0, Math.round((exp-now)/(1000*60*60*24)));
  } catch { return null; }
}

// Slot color palette
const SLOT_COLORS = ['#00E676','#38BDF8','#A78BFA','#FB923C'];
const SLOT_LABELS = ['Slot 1','Slot 2','Slot 3','Slot 4'];

// Delta risk classification
function deltaRisk(delta) {
  const d = Math.abs(parseFloat(delta || 0));
  if (d >= 0.60) return { label: 'CRITICAL', color: '#FF1744', bg: 'rgba(255,23,68,0.15)' };
  if (d >= 0.40) return { label: 'ELEVATED', color: '#FFB300', bg: 'rgba(255,179,0,0.15)' };
  if (d >= 0.20) return { label: 'MODERATE', color: '#FFEA00', bg: 'rgba(255,234,0,0.1)' };
  return { label: 'SAFE', color: '#00E676', bg: 'rgba(0,230,118,0.1)' };
}

// Event badge color mapping
const EVENT_COLORS = {
  SELL_PUT: { color: '#38BDF8', label: 'SELL PUT', symbol: '♦' },
  SELL_CALL: { color: '#00E5FF', label: 'COVERED CALL', symbol: '▲' },
  ROLL_PUT_CLOSE: { color: '#FB923C', label: 'ROLL ✕', symbol: '🔄' },
  ROLL_PUT_OPEN: { color: '#FB923C', label: 'ROLL PUT', symbol: '🔄' },
  CLOSE_FOR_PROFIT: { color: '#00E676', label: 'CLOSE ✓', symbol: '★' },
  BUY_CLOSE: { color: '#00E676', label: 'CLOSE ✓', symbol: '★' },
  ASSIGNED: { color: '#E040FB', label: 'ASSIGNED', symbol: '◼' },
};

// Helper functions for institutional shorthand tickers
function formatShortExpiry(exp) {
  if (!exp) return '';
  const str = String(exp).trim();
  if (/^\d{8}$/.test(str)) {
    const m = parseInt(str.substring(4, 6), 10);
    const d = parseInt(str.substring(6, 8), 10);
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `_${months[m-1]}${d}`;
  }
  if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
    const parts = str.split('-');
    const m = parseInt(parts[1], 10);
    const d = parseInt(parts[2], 10);
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `_${months[m-1]}${d}`;
  }
  return `_${str.replace(/,.*$/, '').replace(/\s+/g, '')}`;
}

function formatStrikeTicker(strike, action, expiry) {
  if (!strike) return '';
  let s = String(strike).replace(/\.0+$/, '');
  if (!/[PCpc]$/.test(s)) {
    s += (action && action.includes('CALL')) ? 'C' : 'P';
  }
  return `${s}${formatShortExpiry(expiry)}`;
}

function formatTradesMinimalist(trades) {
  if (!trades || trades.length === 0) return [];
  const lines = [];
  const processed = new Set();
  let execCount = 0;

  trades.forEach((t, i) => {
    if (processed.has(i)) return;
    const isRollAction = t.action?.includes('ROLL') || t.action === 'BUY_CLOSE';
    if (isRollAction) {
      const isClose = t.action?.includes('CLOSE');
      const openIdx = trades.findIndex((o, j) => j > i && !processed.has(j) && (isClose ? o.action?.includes('ROLL') : o.action?.includes('CLOSE')));
      if (openIdx !== -1) {
        processed.add(i);
        processed.add(openIdx);
        execCount++;
        const closeLeg = isClose ? t : trades[openIdx];
        const openLeg = isClose ? trades[openIdx] : t;
        const oldTicker = formatStrikeTicker(closeLeg.strike, closeLeg.action, closeLeg.expiry);
        const newTicker = formatStrikeTicker(openLeg.strike, openLeg.action, openLeg.expiry);
        const pClose = parseFloat(closeLeg.price || 0);
        const pOpen = parseFloat(openLeg.price || 0);
        lines.push({
          execNum: execCount,
          isFirstLeg: true,
          text: `ROLL CLOSE: ${oldTicker} @ $${pClose.toFixed(2)}`,
          color: '#FB923C'
        });
        lines.push({
          execNum: execCount,
          isSecondLeg: true,
          text: `OPEN:       ${newTicker} @ $${pOpen.toFixed(2)}`,
          color: '#FB923C'
        });
        return;
      }
    }

    processed.add(i);
    execCount++;
    const ticker = formatStrikeTicker(t.strike, t.action, t.expiry);
    const pr = t.price ? ` @ $${parseFloat(t.price).toFixed(2)}` : '';
    if (t.action === 'SELL_PUT') {
      lines.push({ execNum: execCount, text: `OPEN PUT: ${ticker}${pr}`, color: '#38BDF8' });
    } else if (t.action === 'CLOSE_FOR_PROFIT' || t.action === 'BUY_CLOSE') {
      lines.push({ execNum: execCount, text: `CLOSE PROFIT: ${ticker}${pr}`, color: '#00E676' });
    } else if (t.action === 'ASSIGNED') {
      lines.push({ execNum: execCount, text: `SHARES ASSIGNED: 100 AAPL @ ${ticker}`, color: '#E040FB' });
    } else if (t.action === 'SELL_CALL') {
      lines.push({ execNum: execCount, text: `COVERED CALL: ${ticker}${pr}`, color: '#00E5FF' });
    } else if (t.action === 'ROLL_PUT_CLOSE') {
      lines.push({ execNum: execCount, text: `ROLL CLOSE: ${ticker}${pr}`, color: '#FB923C' });
    } else if (t.action === 'ROLL_PUT_OPEN') {
      lines.push({ execNum: execCount, text: `ROLL OPEN: ${ticker}${pr}`, color: '#FB923C' });
    } else {
      lines.push({ execNum: execCount, text: `${t.action.replace(/_/g, ' ')}: ${ticker}${pr}`, color: '#38BDF8' });
    }
  });

  return { lines, totalExecs: execCount };
}

// Custom recharts tooltip
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0]?.payload || {};
    return (
      <div style={{
        background: 'rgba(10, 15, 25, 0.4)',
        backdropFilter: 'blur(6px)',
        border: '1px solid rgba(56,189,248,0.25)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
        borderRadius: 8, padding: '10px 12px', fontFamily: 'monospace', fontSize: 11
      }}>
        <div style={{ color: '#38BDF8', fontWeight: 700, marginBottom: 6, borderBottom: '1px dashed rgba(56,189,248,0.25)', paddingBottom: 4 }}>
          {payload[0]?.payload?.fullTooltipTs || label}
        </div>
        {data.trades && data.trades.length > 0 && (() => {
          const { lines: formattedLines, totalExecs } = formatTradesMinimalist(data.trades);
          return (
            <div style={{ marginBottom: 8, padding: '6px 8px', background: 'rgba(255,255,255,0.05)', borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)' }}>
              {formattedLines.map((l, idx) => {
                let prefix = '';
                if (totalExecs > 1) {
                  prefix = l.isSecondLeg ? '\u00A0\u00A0\u00A0' : `${l.execNum}. `;
                } else {
                  prefix = l.isSecondLeg ? '\u00A0\u00A0\u00A0' : '';
                }
                return (
                  <div key={idx} style={{ color: l.color, fontWeight: 700, fontSize: 11, marginBottom: 2 }}>
                    {prefix}{l.text}
                  </div>
                );
              })}
            </div>
          );
        })()}
        {data.day_classification && (
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', marginBottom: 6, background: 'rgba(255,255,255,0.05)', padding: '2px 5px', borderRadius: 4 }}>
            REGIME: <span style={{ color: '#00E676', fontWeight: 700 }}>{data.day_classification}</span>
          </div>
        )}
        {payload.map((p, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, color: p.color, marginBottom: 3 }}>
            <span>● {p.name}:</span>
            <span style={{ fontWeight: 700 }}>{p.name.includes('VIX') ? p.value?.toFixed(2) : fmt$(p.value)}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export default function CommandCentre() {
  const [portfolio, setPortfolio] = useState({ total_cash: 0, realized_pnl: 0, positions: [] });
  const [pulses, setPulses] = useState([]);
  const [lastPulse, setLastPulse] = useState(null);
  const [kpi, setKpi] = useState(null);
  const [chartData, setChartData] = useState({ pulses: [], events: [] });
  const [loading, setLoading] = useState(true);
  const [activeSlot, setActiveSlot] = useState(null);
  const [hoveredNode, setHoveredNode] = useState({});
  const [timeframe, setTimeframe] = useState('ALL');
  const [expandedChart, setExpandedChart] = useState(false);
  const [selectedDayDrilldown, setSelectedDayDrilldown] = useState(null);
  const [fullIntradayMacro, setFullIntradayMacro] = useState(false);
  const [zoomMultiplier, setZoomMultiplier] = useState(1);

  useEffect(() => {
    const fetch_all = async () => {
      const base = getApiUrl();
      const proxy = (url) => `/api/proxy?url=${encodeURIComponent(url + (url.includes('?') ? '&' : '?') + 't=' + Date.now())}`;

      try {
        // Portfolio
        const pr = await fetch(proxy(`${base}/api/portfolio`));
        if (pr.ok) { const d = await pr.json(); if (d?.positions) setPortfolio(d); }

        // Pulses (last 80 for chart)
        const pRes = await fetch(proxy(`${base}/api/pulses?limit=80`));
        if (pRes.ok) {
          const pd = await pRes.json();
          if (Array.isArray(pd) && pd.length > 0) {
            setLastPulse(pd[0]);
            setPulses([...pd].reverse());
          }
        }

        // KPI
        const kRes = await fetch(proxy(`${base}/api/analytics/kpi_summary`));
        if (kRes.ok) { const kd = await kRes.json(); setKpi(kd); }

        // Master chart (full history)
        const cRes = await fetch(proxy(`${base}/api/analytics/master_chart`));
        if (cRes.ok) { const cd = await cRes.json(); setChartData(cd); }

      } catch (err) {
        console.error('Fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetch_all();
    const iv = setInterval(fetch_all, 60000);
    return () => clearInterval(iv);
  }, []);

  const positions = portfolio.positions || [];

  // Compute total option liability (unrealized) and active open premium
  const totalLiability = positions.reduce((acc, p) => {
    if (p.type === 'Option') acc += (p.current_price ?? p.avg_cost ?? 0) * 100;
    return acc;
  }, 0);
  const activeOpenPremium = positions.reduce((acc, p) => {
    if (p.type === 'Option') acc += (parseFloat(p.avg_cost) || 0) * 100;
    return acc;
  }, 0);
  const netLiquidation = (portfolio.total_cash || 0) - totalLiability;

  // Unguided zone alert: DTE > 15 AND |delta| > 0.55
  const unguidedSlots = positions.filter(p => {
    const dte = p.dte ?? computeDte(p.expiry);
    const d = Math.abs(parseFloat(p.delta || 0));
    return dte > 15 && d >= 0.55;
  });

  // Dynamic Yahoo Finance Timeframe & Zoom Engine
  const rawChartData = (chartData.pulses && chartData.pulses.length > 0) ? chartData.pulses : pulses;
  const filteredRawData = (() => {
    if (!rawChartData || rawChartData.length === 0) return [];
    if (timeframe === '3D') return rawChartData.slice(-36);
    if (timeframe === '1W') return rawChartData.slice(-80);
    if (timeframe === '2W') return rawChartData.slice(-160);
    return rawChartData;
  })();

  const rawEvents = (chartData.events && chartData.events.length > 0) ? chartData.events : [
    { timestamp: '2026-05-27T19:30:00Z', action: 'SELL_PUT', strike: '295', expiry: '20260619', price: '18.25' },
    { timestamp: '2026-06-10T22:00:00Z', action: 'ROLL_PUT_CLOSE', strike: '295', expiry: '20260619', price: '7.87' },
    { timestamp: '2026-06-10T22:00:00Z', action: 'ROLL_PUT_OPEN', strike: '290', expiry: '20260717', price: '9.52' },
  ];

  // Ensure every trade event has its own dedicated timestamp bar on the chart curve
  const augmentedRawData = [...filteredRawData];
  rawEvents.forEach(ev => {
    if (!ev.timestamp) return;
    const evTime = new Date(ev.timestamp).getTime();
    const exists = augmentedRawData.some(p => Math.abs(new Date(p.timestamp).getTime() - evTime) < 900000);
    if (!exists && augmentedRawData.length > 0) {
      const before = [...augmentedRawData].reverse().find(p => new Date(p.timestamp).getTime() <= evTime) || augmentedRawData[0];
      augmentedRawData.push({
        ...before,
        timestamp: ev.timestamp,
        aapl_price: before.aapl_price,
        vix_level: before.vix_level,
      });
    }
  });
  augmentedRawData.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  const chartDataToProcess = (() => {
    if (expandedChart) {
      if (selectedDayDrilldown) {
        const matching = augmentedRawData.filter(p => {
          const d = new Date(p.timestamp);
          const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
          return `${months[d.getMonth()]} ${d.getDate()}` === selectedDayDrilldown;
        });
        return matching.length > 0 ? matching : augmentedRawData;
      }
      if (fullIntradayMacro) {
        return augmentedRawData;
      }
      const dailyMap = new Map();
      augmentedRawData.forEach(p => {
        const d = new Date(p.timestamp);
        const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        const dayKey = `${months[d.getMonth()]} ${d.getDate()}`;
        dailyMap.set(dayKey, p);
      });
      return Array.from(dailyMap.values());
    }
    return augmentedRawData;
  })();

  const displayChart = chartDataToProcess.map((p, idx) => {
    const d = new Date(p.timestamp || Date.now());
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const monthStr = months[d.getMonth()];
    const day = d.getDate();
    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    let axisLabel = `${monthStr} ${day}`;
    if (expandedChart) {
      if (selectedDayDrilldown) {
        axisLabel = `${monthStr} ${day} (${timeStr})`;
      } else if (fullIntradayMacro) {
        axisLabel = `${monthStr} ${day} (${timeStr})`;
      } else {
        axisLabel = `${monthStr} ${day}`;
      }
    } else if (timeframe === '2W' || timeframe === '1W') {
      axisLabel = `${monthStr} ${day} (${timeStr})`;
    } else if (timeframe === '3D') {
      axisLabel = `${timeStr}`;
    }

    const barTime = d.getTime();
    const matchingTrades = rawEvents.filter(ev => {
      if (!ev.timestamp) return false;
      const evDate = new Date(ev.timestamp);
      const evDayStr = `${months[evDate.getMonth()]} ${evDate.getDate()}`;
      if (expandedChart && !selectedDayDrilldown && !fullIntradayMacro) {
        return evDayStr === `${monthStr} ${day}`;
      }
      const evTime = evDate.getTime();
      return Math.abs(evTime - barTime) <= 900000;
    });

    return {
      unique_id: idx,
      calendarDate: `${monthStr} ${day}`,
      timestamp: axisLabel,
      fullTooltipTs: `${monthStr} ${day}, ${d.getFullYear()} at ${timeStr}`,
      aapl_price: p.aapl_price,
      vix_level: p.vix_level,
      sma_200: p.sma_200 || null,
      day_classification: p.day_classification,
      trades: matchingTrades,
    };
  });

  const tradeMarkersMap = new Map();
  displayChart.forEach(bar => {
    if (bar.trades && bar.trades.length > 0) {
      if (!tradeMarkersMap.has(bar.unique_id)) {
        const hasRoll = bar.trades.some(t => t.action?.includes('ROLL'));
        const hasClose = bar.trades.some(t => t.action?.includes('CLOSE'));
        const color = hasRoll ? '#FB923C' : (hasClose ? '#00E676' : '#38BDF8');
        tradeMarkersMap.set(bar.unique_id, {
          unique_id: bar.unique_id,
          price: bar.aapl_price,
          color: color,
          action: bar.trades[0].action,
        });
      }
    }
  });
  const tradeMarkers = Array.from(tradeMarkersMap.values());

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div style={{ textAlign: 'center', fontFamily: 'monospace' }}>
          <div style={{ color: '#00E676', fontSize: 24, marginBottom: 8 }}>⚡</div>
          <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12, letterSpacing: '0.15em' }}>INITIALISING HERMES QUANTUM...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-screen-2xl mx-auto space-y-6 pb-12 animate-in fade-in duration-500">

      {/* ── PAGE HEADER ─────────────────────────────────────────────── */}
      <div className="flex justify-between items-end border-b border-white/10 pb-5">
        <div>
          <h1 style={{
            fontSize: 32, fontWeight: 300, letterSpacing: '-0.02em',
            background: 'linear-gradient(90deg, #fff 0%, rgba(255,255,255,0.55) 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
          }}>Command Centre</h1>
          <p style={{ color: 'rgba(255,255,255,0.4)', marginTop: 4, fontFamily: 'monospace', fontSize: 11, letterSpacing: '0.15em', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Zap size={11} color="#00E676" /> HERMES QUANTUM · AAPL WHEEL STRATEGY
          </p>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: 'rgba(0,0,0,0.4)', padding: '6px 12px',
          borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)',
          fontFamily: 'monospace', fontSize: 11
        }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#00E676', display: 'inline-block', animation: 'pulse 2s infinite' }} />
          <span style={{ color: 'rgba(255,255,255,0.4)' }}>LIVE FEED</span>
          <span style={{ color: 'rgba(255,255,255,0.8)' }}>ACTIVE</span>
        </div>
      </div>

      {/* ── GUARDRAIL RADAR ALERT ────────────────────────────────────── */}
      {unguidedSlots.length > 0 && (
        <div style={{
          background: 'rgba(255,23,68,0.08)', border: '1px solid rgba(255,23,68,0.35)',
          borderRadius: 10, padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 10
        }}>
          <AlertTriangle size={18} color="#FF1744" />
          <div style={{ flex: 1 }}>
            <p style={{ color: '#FF1744', fontFamily: 'monospace', fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', marginBottom: 2 }}>
              ⚠ UNGUIDED AI ZONE DETECTED
            </p>
            <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 11 }}>
              {unguidedSlots.map(p => `${p.strike}P (DTE ${p.dte ?? computeDte(p.expiry)}, Δ ${p.delta})`).join(' · ')} — Hardcoded rules inactive above DTE 15. AI operating on open-ended judgment.
            </p>
          </div>
        </div>
      )}

      {/* ── KPI PERFORMANCE BANNER (CORE PORTFOLIO) ─────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14 }}>
        {[
          { icon: DollarSign, label: 'NET LIQUIDATION', value: fmt$(netLiquidation), sub: `Total Return: ${fmt$((netLiquidation || 250000) - 250000)}`, color: '#38BDF8', glow: '#38BDF8' },
          { icon: DollarSign, label: 'LIQUID CASH IN ACCOUNT', value: fmt$(portfolio.total_cash), sub: 'Initial Capital: $250,000.00', color: '#00E676', glow: '#00E676' },
          { icon: TrendingUp, label: 'ACTIVE OPEN PREMIUM', value: fmt$(activeOpenPremium), sub: `Gross Collected: ${fmt$(kpi?.total_premium_collected)}`, color: '#A78BFA', glow: '#A78BFA' },
          { icon: BarChart2, label: 'NET REALIZED P&L', value: fmt$(kpi?.net_realized_pnl), sub: `Closed Trades: ${(kpi?.profit_closes || 0) + (kpi?.defensive_rolls || 0)}`, color: kpi?.net_realized_pnl >= 0 ? '#00E676' : '#FF1744', glow: kpi?.net_realized_pnl >= 0 ? '#00E676' : '#FF1744' },
        ].map((item, i) => (
          <div key={i} className="glass-panel" style={{ padding: '16px 20px', position: 'relative', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', top: -20, right: -20, width: 80, height: 80, background: `${item.glow}08`, borderRadius: '50%', filter: 'blur(20px)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <item.icon size={11} color={item.color} />
              <span style={{ color: 'rgba(255,255,255,0.4)', fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.12em' }}>{item.label}</span>
            </div>
            <p style={{ fontSize: 24, fontWeight: 300, color: item.color, fontFamily: 'monospace', letterSpacing: '-0.02em' }}>{item.value}</p>
            {item.sub && <p style={{ color: 'rgba(255,255,255,0.4)', fontFamily: 'monospace', fontSize: 11, marginTop: 4 }}>{item.sub}</p>}
          </div>
        ))}
      </div>

      {/* ── LIVE 4-SLOT GRID ────────────────────────────────────────── */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <Target size={14} color="#00E676" />
          <span style={{ color: 'rgba(255,255,255,0.6)', fontFamily: 'monospace', fontSize: 11, letterSpacing: '0.14em' }}>LIVE POSITION PIPELINE & WHEEL STATE FLOW MAP — ALL 4 SLOTS</span>
        </div>

        {/* Common Table Header Row */}
        <div style={{
          display: 'grid', gridTemplateColumns: '2.5fr 0.6fr 1fr 0.8fr 1.6fr 1.5fr 40px', gap: 12,
          padding: '8px 20px', background: 'rgba(255,255,255,0.02)', borderRadius: 6, border: '1px solid rgba(255,255,255,0.04)',
          fontFamily: 'monospace', fontSize: 10, color: 'rgba(255,255,255,0.4)', letterSpacing: '0.1em', marginBottom: 8
        }}>
          <div>INSTRUMENT</div>
          <div>QTY</div>
          <div>DELTA Δ</div>
          <div>DTE</div>
          <div>ENTRY PRICE ➔ CURRENT</div>
          <div>UNREALIZED P&L</div>
          <div style={{ textAlign: 'center' }}>FLOW</div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {positions.length === 0 ? (
            <div className="glass-panel" style={{ padding: 40, textAlign: 'center', color: 'rgba(255,255,255,0.2)', fontFamily: 'monospace', fontSize: 12 }}>
              <AlertTriangle size={24} style={{ margin: '0 auto 10px', opacity: 0.3 }} />
              NO ACTIVE POSITIONS DEPLOYED
            </div>
          ) : (
            positions.map((pos, i) => {
              const slotColor = SLOT_COLORS[i % SLOT_COLORS.length];
              const dte = pos.dte ?? computeDte(pos.expiry);
              const risk = deltaRisk(pos.delta);
              const unrealized = pos.unrealized_pnl;
              const unrealizedPct = pos.unrealized_pnl_percent;
              const isUnguided = dte > 15 && Math.abs(parseFloat(pos.delta || 0)) >= 0.55;
              const isRolled = pos.expiry && pos.expiry.includes('0828');
              const isCall = pos.option_type === 'CALL';
              const isStock = pos.type === 'Stock';
              const isPut = pos.option_type === 'PUT' && !isStock;

              return (
                <div
                  key={i}
                  className="glass-panel"
                  style={{
                    padding: activeSlot === i ? '16px 20px 20px' : '12px 20px',
                    cursor: 'pointer', transition: 'all 0.2s',
                    border: `1px solid ${activeSlot === i ? slotColor + '60' : 'rgba(255,255,255,0.06)'}`,
                    boxShadow: activeSlot === i ? `0 0 24px ${slotColor}15` : undefined
                  }}
                  onClick={() => setActiveSlot(activeSlot === i ? null : i)}
                >
                  {/* Single-Line Institutional Grid Row */}
                  <div style={{ display: 'grid', gridTemplateColumns: '2.5fr 0.6fr 1fr 0.8fr 1.6fr 1.5fr 40px', gap: 12, alignItems: 'center', fontFamily: 'monospace' }}>
                    
                    {/* Col 1: Instrument & Slot */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: slotColor, boxShadow: `0 0 8px ${slotColor}`, display: 'inline-block', flexShrink: 0 }} />
                      <span style={{ fontSize: 11, color: slotColor, fontWeight: 700 }}>{SLOT_LABELS[i]}</span>
                      <span style={{
                        background: isPut ? 'rgba(251,146,60,0.15)' : 'rgba(167,139,250,0.15)',
                        color: isPut ? '#FB923C' : '#A78BFA',
                        fontSize: 9, padding: '2px 5px', borderRadius: 4, fontWeight: 600
                      }}>{pos.option_type || 'STOCK'}</span>
                      <span style={{ fontSize: 14, fontWeight: 500, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {pos.symbol} {formatExpiry(pos.expiry)} {pos.strike}{isPut ? 'P' : isCall ? 'C' : ''}
                      </span>
                    </div>

                    {/* Col 2: QTY */}
                    <div style={{ fontSize: 13, color: '#38BDF8', fontWeight: 600 }}>
                      {pos.quantity !== undefined ? `${pos.quantity > 0 ? '+' : ''}${pos.quantity}` : '-1'}
                    </div>

                    {/* Col 3: Delta (with tiny micro-label beneath) */}
                    <div>
                      <div style={{ fontSize: 13, color: risk.color, fontWeight: 600 }}>{pos.delta || '--'}</div>
                      {pos.delta && (
                        <div style={{ fontSize: 9, color: risk.color, opacity: 0.8, letterSpacing: '0.05em', marginTop: 1 }}>{risk.label}</div>
                      )}
                    </div>

                    {/* Col 4: DTE */}
                    <div style={{ fontSize: 13, color: dte <= 15 ? '#FFEA00' : '#fff', fontWeight: 600 }}>
                      {dte !== null ? `${dte}d` : '--'}
                    </div>

                    {/* Col 5: Entry Price ➔ Current */}
                    <div style={{ fontSize: 13, color: '#fff' }}>
                      {fmt$(pos.avg_cost)} <span style={{ color: 'rgba(255,255,255,0.3)' }}>➔</span> {pos.current_price !== undefined ? fmt$(pos.current_price) : '--'}
                    </div>

                    {/* Col 6: Unrealized P&L */}
                    <div style={{ fontSize: 13, color: unrealized >= 0 ? '#00E676' : '#FF1744', fontWeight: 700 }}>
                      {unrealized !== undefined ? `${unrealized >= 0 ? '+' : ''}${fmt$(unrealized)} (${fmtPct(unrealizedPct)})` : '--'}
                    </div>

                    {/* Col 6: Simple ▼ / ▲ Toggle Icon Button */}
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                      <button
                        style={{
                          background: activeSlot === i ? `${slotColor}20` : 'rgba(255,255,255,0.05)',
                          border: `1px solid ${activeSlot === i ? slotColor : 'rgba(255,255,255,0.2)'}`,
                          color: activeSlot === i ? slotColor : '#fff',
                          width: 28, height: 28, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
                          cursor: 'pointer', transition: 'all 0.2s', fontSize: 11
                        }}
                        onClick={(e) => { e.stopPropagation(); setActiveSlot(activeSlot === i ? null : i); }}
                      >
                        {activeSlot === i ? '▲' : '▼'}
                      </button>
                    </div>
                  </div>

                  {/* Expanded Circular Wheel State Flowmap */}
                  {activeSlot === i && (() => {
                    const targetPct = dte <= 15 ? 0.50 : 0.75;
                    const autoCloseTarget = (pos.avg_cost * (1 - targetPct)).toFixed(2);
                    const qty = Math.abs(pos.quantity || 1);
                    const reservedCash = (pos.strike * 100 * qty).toLocaleString(undefined, {minimumFractionDigits: 2});
                    const premCollected = (pos.avg_cost * 100 * qty).toLocaleString(undefined, {minimumFractionDigits: 2});
                    const currentHover = hoveredNode[i] || (isRolled ? 'ROLL' : isPut ? 'PUT' : isStock ? 'ASSIGNED' : isCall ? 'CALL' : 'CASH');

                    return (
                      <div style={{ marginTop: 16, background: 'rgba(0,0,0,0.4)', borderRadius: 10, padding: 20, border: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-around', gap: 20 }}>
                        
                        {/* Left: Interactive Circular Diagram */}
                        <div style={{ position: 'relative', width: 320, height: 280 }}>
                          <svg width="320" height="280" viewBox="0 0 320 280" style={{ overflow: 'visible' }}>
                            <defs>
                              <filter id={`glow-${i}`} x="-20%" y="-20%" width="140%" height="140%">
                                <feGaussianBlur stdDeviation="6" result="blur" />
                                <feComposite in="SourceGraphic" in2="blur" operator="over" />
                              </filter>
                            </defs>

                            {/* Main Circular Ring */}
                            <circle cx="140" cy="140" r="80" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="2" strokeDasharray="4 4" />

                            {/* Active Arc (from Top to Right if Put Sold) */}
                            {(isPut || isRolled) && (
                              <path d="M 140 60 A 80 80 0 0 1 220 140" fill="none" stroke="#00E676" strokeWidth="3" filter={`url(#glow-${i})`} />
                            )}

                            {/* Self-Loop for Roll Put */}
                            {isRolled && (
                              <g style={{ cursor: 'pointer' }} onMouseEnter={() => setHoveredNode(p => ({...p, [i]: 'ROLL'}))} onMouseLeave={() => setHoveredNode(p => ({...p, [i]: null}))}>
                                <title>Defensive Roll | Sold New +{fmt$(pos.avg_cost || 18.25)} − Bought Old -${((pos.avg_cost || 18.25) - 1.45).toFixed(2)} = Net Credit +$1.45</title>
                                <path d="M 220 130 C 280 90, 280 190, 220 150" fill="none" stroke="#38BDF8" strokeWidth="2.5" strokeDasharray="3 3" filter={`url(#glow-${i})`} />
                                <polygon points="222,146 228,154 216,154" fill="#38BDF8" />
                                <rect x="245" y="128" width="65" height="22" rx="4" fill={currentHover === 'ROLL' ? 'rgba(56,189,248,0.4)' : 'rgba(56,189,248,0.2)'} stroke="#38BDF8" strokeWidth="1" />
                                <text x="277.5" y="142" textAnchor="middle" fill="#38BDF8" fontSize="9" fontFamily="monospace" fontWeight="bold">🔄 ROLL PUT</text>
                              </g>
                            )}

                            {/* Node 1: Top (Cash Only) */}
                            <g style={{ cursor: 'pointer' }} onMouseEnter={() => setHoveredNode(p => ({...p, [i]: 'CASH'}))} onMouseLeave={() => setHoveredNode(p => ({...p, [i]: null}))}>
                              <title>Phase 1: Cash Collateral | Reserved: ${reservedCash}</title>
                              <circle cx="140" cy="60" r="16" fill={currentHover === 'CASH' ? '#00E676' : (!isPut && !isStock && !isCall ? '#00E676' : '#1e293b')} stroke={!isPut && !isStock && !isCall ? '#00E676' : 'rgba(255,255,255,0.3)'} strokeWidth="2" filter={currentHover === 'CASH' ? `url(#glow-${i})` : undefined} />
                              <text x="140" y="32" textAnchor="middle" fill={currentHover === 'CASH' ? '#00E676' : 'rgba(255,255,255,0.7)'} fontSize="10" fontFamily="monospace" fontWeight="bold">1. CASH ONLY</text>
                            </g>

                            {/* Node 2: Right (Put Sold) */}
                            <g style={{ cursor: 'pointer' }} onMouseEnter={() => setHoveredNode(p => ({...p, [i]: 'PUT'}))} onMouseLeave={() => setHoveredNode(p => ({...p, [i]: null}))}>
                              <title>Phase 2: Short Put | Premium +${premCollected} | Target ${autoCloseTarget}</title>
                              <circle cx="220" cy="140" r="16" fill={currentHover === 'PUT' ? '#00E676' : (isPut || isRolled ? '#00E676' : '#1e293b')} stroke={isPut || isRolled ? '#00E676' : 'rgba(255,255,255,0.3)'} strokeWidth="2" filter={isPut || isRolled || currentHover === 'PUT' ? `url(#glow-${i})` : undefined} />
                              <text x="220" y="175" textAnchor="middle" fill={currentHover === 'PUT' ? '#00E676' : (isPut || isRolled ? '#00E676' : 'rgba(255,255,255,0.7)')} fontSize="10" fontFamily="monospace" fontWeight="bold">2. PUT SOLD</text>
                            </g>

                            {/* Node 3: Bottom (Assigned) */}
                            <g style={{ cursor: 'pointer' }} onMouseEnter={() => setHoveredNode(p => ({...p, [i]: 'ASSIGNED'}))} onMouseLeave={() => setHoveredNode(p => ({...p, [i]: null}))}>
                              <title>Phase 3: Assigned | Holdings {qty * 100} Shares @ ${pos.strike}</title>
                              <circle cx="140" cy="220" r="16" fill={currentHover === 'ASSIGNED' ? '#00E676' : (isStock ? '#00E676' : '#1e293b')} stroke={isStock ? '#00E676' : 'rgba(255,255,255,0.3)'} strokeWidth="2" filter={currentHover === 'ASSIGNED' ? `url(#glow-${i})` : undefined} />
                              <text x="140" y="248" textAnchor="middle" fill={currentHover === 'ASSIGNED' ? '#00E676' : (isStock ? '#00E676' : 'rgba(255,255,255,0.7)')} fontSize="10" fontFamily="monospace" fontWeight="bold">3. ASSIGNED</text>
                            </g>

                            {/* Node 4: Left (Call Sold) */}
                            <g style={{ cursor: 'pointer' }} onMouseEnter={() => setHoveredNode(p => ({...p, [i]: 'CALL'}))} onMouseLeave={() => setHoveredNode(p => ({...p, [i]: null}))}>
                              <title>Phase 4: Covered Call | Target Strike ${pos.strike + 10}.00 Call</title>
                              <circle cx="60" cy="140" r="16" fill={currentHover === 'CALL' ? '#00E676' : (isCall ? '#00E676' : '#1e293b')} stroke={isCall ? '#00E676' : 'rgba(255,255,255,0.3)'} strokeWidth="2" filter={currentHover === 'CALL' ? `url(#glow-${i})` : undefined} />
                              <text x="60" y="175" textAnchor="middle" fill={currentHover === 'CALL' ? '#00E676' : (isCall ? '#00E676' : 'rgba(255,255,255,0.7)')} fontSize="10" fontFamily="monospace" fontWeight="bold">4. CALL SOLD</text>
                            </g>
                          </svg>
                        </div>

                        {/* Right: Permanent Strategy Description & Live Metrics Panel */}
                        <div style={{ flex: '1 1 260px', background: 'rgba(255,255,255,0.03)', padding: 18, borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', fontFamily: 'monospace' }}>
                          
                          {/* Permanent Strategy Header & Wording (Never changes on hover!) */}
                          <h4 style={{ color: slotColor, fontSize: 13, marginBottom: 8, fontWeight: 700 }}>
                            {isRolled ? 'ACTIVE DEFENSIVE ROLL' : isPut ? 'CASH-SECURED PUT ACTIVE' : isStock ? 'SHARES ASSIGNED' : isCall ? 'COVERED CALL ACTIVE' : 'AWAITING TRADE'}
                          </h4>
                          <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, lineHeight: 1.5, marginBottom: 14, borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: 12 }}>
                            {isRolled ? `This put option was rolled to ${formatExpiry(pos.expiry)} to defend collateral and collect premium. The circular loop confirms the strategy remains in Phase 2.` : isPut ? `Collateral is locked while short put generates theta decay. If AAPL stays above $${pos.strike}, contract expires worthless for 100% profit.` : isStock ? `Shares were assigned at $${pos.strike} cost basis. Holding physical stock debt-free while preparing covered call strategy.` : isCall ? `Active covered call generating income against assigned share inventory.` : 'Active Wheel strategy lifecycle phase.'}
                          </p>

                          {/* Interactive Sleek Glassmorphic Node Metrics Card */}
                          {(() => {
                            const hoverAccent = currentHover === 'CASH' ? '#00E676' :
                                                currentHover === 'PUT' ? '#00E676' :
                                                currentHover === 'ROLL' ? '#38BDF8' :
                                                currentHover === 'ASSIGNED' ? '#A78BFA' :
                                                currentHover === 'CALL' ? '#FBBF24' : slotColor;
                            return (
                              <div style={{ 
                                background: currentHover ? `linear-gradient(135deg, rgba(15,23,42,0.85) 0%, rgba(10,15,25,0.95) 100%)` : 'rgba(0,0,0,0.3)', 
                                padding: '14px 16px', 
                                borderRadius: 8, 
                                border: currentHover ? `1px solid ${hoverAccent}50` : '1px solid rgba(255,255,255,0.06)',
                                boxShadow: currentHover ? `0 8px 24px -6px ${hoverAccent}25` : 'none',
                                transition: 'all 0.25s ease'
                              }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, borderBottom: `1px dashed ${hoverAccent}30`, paddingBottom: 8 }}>
                                  <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: hoverAccent, boxShadow: `0 0 8px ${hoverAccent}` }}></span>
                                  <span style={{ fontSize: 11, color: hoverAccent, fontWeight: 700, letterSpacing: '0.08em' }}>
                                    {currentHover === 'CASH' ? 'PHASE 1: CASH COLLATERAL' :
                                     currentHover === 'PUT' ? 'PHASE 2: SHORT PUT METRICS' :
                                     currentHover === 'ROLL' ? 'DEFENSIVE ROLL ADJUSTMENT' :
                                     currentHover === 'ASSIGNED' ? 'PHASE 3: ASSIGNED HOLDINGS' :
                                     currentHover === 'CALL' ? 'PHASE 4: COVERED CALL TARGET' : 'ACTIVE LIFECYCLE METRICS'}
                                  </span>
                                </div>

                                {currentHover === 'CASH' && (
                                  <div style={{ fontSize: 13, color: '#fff', lineHeight: 1.8 }}>
                                    <div>Reserved Cash: <span style={{ color: '#00E676', fontWeight: 700 }}>${reservedCash}</span></div>
                                    <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>100% Cash-Secured backing reserved for {qty * 100} shares</div>
                                  </div>
                                )}

                                {currentHover === 'PUT' && (
                                  <div style={{ fontSize: 13, color: '#fff', lineHeight: 1.8 }}>
                                    <div>Premium Collected: <span style={{ color: '#00E676', fontWeight: 700 }}>+${premCollected}</span></div>
                                    <div>Auto-Close Target: <span style={{ color: '#38BDF8', fontWeight: 700 }}>${autoCloseTarget}</span> <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>({dte <= 15 ? '50% Gamma Rule' : '75% Win Rule'})</span></div>
                                  </div>
                                )}

                                {currentHover === 'ROLL' && (() => {
                                  const newPrem = pos.avg_cost || 18.25;
                                  const netRoll = 1.45;
                                  const oldBuyback = (newPrem - netRoll).toFixed(2);
                                  return (
                                    <div style={{ fontSize: 13, color: '#fff', lineHeight: 1.8 }}>
                                      <div>New Expiry: <span style={{ color: '#FB923C', fontWeight: 700 }}>{formatExpiry(pos.expiry)} ({dte} DTE)</span></div>
                                      <div>Roll Breakdown: <span style={{ color: 'rgba(255,255,255,0.85)' }}>Sold New +{fmt$(newPrem)} − Bought Old -${oldBuyback}</span></div>
                                      <div>Net Roll Credit: <span style={{ color: '#00E676', fontWeight: 700 }}>+${netRoll} / share (+${(netRoll * 100 * qty).toFixed(2)} total)</span></div>
                                    </div>
                                  );
                                })()}

                                {currentHover === 'ASSIGNED' && (
                                  <div style={{ fontSize: 13, color: '#fff', lineHeight: 1.8 }}>
                                    <div>Holdings: <span style={{ color: '#A78BFA', fontWeight: 700 }}>{qty * 100} Shares @ ${pos.strike}</span></div>
                                    <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>Physical stock held debt-free</div>
                                  </div>
                                )}

                                {currentHover === 'CALL' && (
                                  <div style={{ fontSize: 13, color: '#fff', lineHeight: 1.8 }}>
                                    <div>Target Strike: <span style={{ color: '#FBBF24', fontWeight: 700 }}>${pos.strike + 10}.00 Call</span></div>
                                    <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>Covered call income generation</div>
                                  </div>
                                )}

                                {!currentHover && (
                                  <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', fontStyle: 'italic', padding: '4px 0' }}>
                                    💡 Hover over any glowing node or arrow on the flowmap to inspect live 1-2 line financial metrics.
                                  </div>
                                )}
                              </div>
                            );
                          })()}

                        </div>

                      </div>
                    );
                  })()}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── MASTER MARKET CHART ─────────────────────────────────────── */}
      <div className="glass-panel" style={{ padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Activity size={14} color="#38BDF8" />
              <span style={{ color: 'rgba(255,255,255,0.6)', fontFamily: 'monospace', fontSize: 11, letterSpacing: '0.14em' }}>
                AAPL MARKET REGIME — FULL HISTORY ({displayChart.length} DATA POINTS)
              </span>
            </div>
            {lastPulse && (
              <div style={{
                background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.3)',
                borderRadius: 20, padding: '3px 12px', display: 'flex', alignItems: 'center', gap: 6,
                fontFamily: 'monospace', fontSize: 10, color: '#A78BFA', fontWeight: 700
              }}>
                <Cpu size={12} color="#A78BFA" />
                <span>AI PULSE ({new Date(lastPulse.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}):</span>
                <span style={{ color: '#fff' }}>
                  {Array.from(new Set((lastPulse.ai_decision || '').split('.'))).map(s => s.trim()).filter(Boolean).join(' • ') || 'HOLD PUT POSITION'}
                </span>
              </div>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* Yahoo Finance Interactive Timeframe Buttons */}
            <div style={{ display: 'flex', gap: 4, background: 'rgba(0,0,0,0.4)', padding: 3, borderRadius: 6, border: '1px solid rgba(255,255,255,0.08)' }}>
              {[{ id: '3D', label: '3D (Intraday)' }, { id: '1W', label: '1W' }, { id: '2W', label: '2W' }, { id: 'ALL', label: 'ALL (Macro)' }].map(t => (
                <button
                  key={t.id}
                  onClick={() => setTimeframe(t.id)}
                  style={{
                    padding: '2px 8px', borderRadius: 4, fontSize: 10, fontFamily: 'monospace', cursor: 'pointer', transition: 'all 0.15s',
                    background: timeframe === t.id ? '#38BDF8' : 'transparent',
                    color: timeframe === t.id ? '#0f172a' : 'rgba(255,255,255,0.6)',
                    fontWeight: timeframe === t.id ? 700 : 400, border: 'none'
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 12, fontFamily: 'monospace', fontSize: 10, alignItems: 'center' }}>
              <span style={{ color: '#00E676' }}>● AAPL</span>
              <span style={{ color: '#38BDF8' }}>— 200 SMA</span>
              <span style={{ color: '#FFEA00' }}>● VIX</span>
              <button
                onClick={() => setExpandedChart(true)}
                style={{
                  background: 'rgba(56,189,248,0.15)', border: '1px solid rgba(56,189,248,0.3)',
                  color: '#38BDF8', padding: '3px 8px', borderRadius: 4, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 5, fontFamily: 'monospace', fontSize: 10, fontWeight: 700
                }}
                title="Expand Chart to Full Screen"
              >
                <Maximize2 size={12} /> EXPAND
              </button>
            </div>
          </div>
        </div>

        <div style={{ width: '100%', height: 320, minHeight: 320, position: 'relative' }}>
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={displayChart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gAAPL" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00E676" stopOpacity={0.25}/>
                  <stop offset="95%" stopColor="#00E676" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="gVIX" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#FFEA00" stopOpacity={0.2}/>
                  <stop offset="95%" stopColor="#FFEA00" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={true} horizontal={true} />
              <XAxis dataKey="unique_id" stroke="rgba(255,255,255,0.15)" tick={{ fill: 'rgba(255,255,255,0.45)', fontSize: 9, fontFamily: 'monospace' }} minTickGap={60} tickFormatter={(val) => displayChart[val]?.timestamp || ''} />
              <YAxis yAxisId="price" stroke="rgba(255,255,255,0.15)" tick={{ fill: '#00E676', fontSize: 9, fontFamily: 'monospace' }} tickFormatter={v => `$${v}`} domain={['auto','auto']} />
              <YAxis yAxisId="vix" orientation="right" stroke="rgba(255,255,255,0.15)" tick={{ fill: '#FFEA00', fontSize: 9, fontFamily: 'monospace' }} domain={['auto','auto']} />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#38BDF8', strokeWidth: 1, strokeDasharray: '3 3' }} />
              <Area yAxisId="price" type="monotone" dataKey="sma_200" stroke="#38BDF8" strokeWidth={1.5} strokeDasharray="4 4" fill="none" name="200 SMA" dot={false} />
              <Area yAxisId="price" type="monotone" dataKey="aapl_price" stroke="#00E676" strokeWidth={2} fill="url(#gAAPL)" name="AAPL" dot={false} />
              <Area yAxisId="vix" type="monotone" dataKey="vix_level" stroke="#FFEA00" strokeWidth={1.2} fill="url(#gVIX)" name="VIX" dot={false} />
              {tradeMarkers.map((m, idx) => (
                <ReferenceDot key={idx} yAxisId="price" x={m.unique_id} y={m.price} r={6} fill={m.color} stroke="#0f172a" strokeWidth={2} isFront={true} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── EXPANDED FULL-SCREEN CHART MODAL ───────────────────────── */}
      {expandedChart && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 99999,
          background: 'rgba(5, 8, 16, 0.94)', backdropFilter: 'blur(16px)',
          padding: '30px 40px', display: 'flex', flexDirection: 'column'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Activity size={18} color="#38BDF8" />
              <span style={{ color: '#fff', fontFamily: 'monospace', fontSize: 16, fontWeight: 700, letterSpacing: '0.14em' }}>
                {selectedDayDrilldown ? `AAPL INTRADAY SESSION DRILLDOWN — ${selectedDayDrilldown.toUpperCase()}` : `AAPL MARKET REGIME — FULL SCREEN QUANT VIEW (${displayChart.length} DATA POINTS)`}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
              {selectedDayDrilldown && (
                <button
                  onClick={() => setSelectedDayDrilldown(null)}
                  style={{
                    background: 'rgba(251,146,60,0.15)', border: '1px solid rgba(251,146,60,0.3)',
                    color: '#FB923C', padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'monospace', fontSize: 12, fontWeight: 700
                  }}
                >
                  ⬅ BACK TO ALL DAYS
                </button>
              )}
              {!selectedDayDrilldown && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <button
                    onClick={() => setFullIntradayMacro(!fullIntradayMacro)}
                    style={{
                      padding: '6px 12px', borderRadius: 6, fontSize: 11, fontFamily: 'monospace', cursor: 'pointer', transition: 'all 0.2s',
                      background: fullIntradayMacro ? 'rgba(0,230,118,0.15)' : 'rgba(255,255,255,0.05)',
                      color: fullIntradayMacro ? '#00E676' : 'rgba(255,255,255,0.6)',
                      border: `1px solid ${fullIntradayMacro ? '#00E676' : 'rgba(255,255,255,0.15)'}`,
                      fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6
                    }}
                    title="Toggle between all 30-min pulses continuously vs Normal summary per day"
                  >
                    <span>{fullIntradayMacro ? '🟢' : '⚪'}</span>
                    <span>{fullIntradayMacro ? 'FULLY EXPANDED (ALL 30-MIN)' : 'NORMAL PER-DAY (CLICK TO EXPAND)'}</span>
                  </button>
                  <div style={{ display: 'flex', gap: 6, background: 'rgba(0,0,0,0.6)', padding: 4, borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)' }}>
                    {[{ id: '3D', label: '3D (Intraday)' }, { id: '1W', label: '1W' }, { id: '2W', label: '2W' }, { id: 'ALL', label: 'ALL (Macro)' }].map(t => (
                      <button
                        key={t.id}
                        onClick={() => setTimeframe(t.id)}
                        style={{
                          padding: '4px 12px', borderRadius: 4, fontSize: 11, fontFamily: 'monospace', cursor: 'pointer', transition: 'all 0.15s',
                          background: timeframe === t.id ? '#38BDF8' : 'transparent',
                          color: timeframe === t.id ? '#0f172a' : 'rgba(255,255,255,0.7)',
                          fontWeight: timeframe === t.id ? 700 : 400, border: 'none'
                        }}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {/* Zoom Controls */}
              <div style={{ display: 'flex', gap: 4, background: 'rgba(0,0,0,0.6)', padding: 4, borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)', alignItems: 'center' }}>
                <button
                  onClick={() => setZoomMultiplier(prev => Math.max(prev - 0.25, 0.4))}
                  style={{ background: 'transparent', border: 'none', color: '#fff', padding: '4px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                  title="Zoom Out (-)"
                >
                  <ZoomOut size={14} />
                </button>
                <button
                  onClick={() => setZoomMultiplier(1)}
                  style={{ background: 'transparent', border: 'none', color: '#38BDF8', padding: '4px 6px', cursor: 'pointer', fontFamily: 'monospace', fontSize: 10, fontWeight: 700 }}
                  title="Reset Zoom (100%)"
                >
                  {Math.round(zoomMultiplier * 100)}%
                </button>
                <button
                  onClick={() => setZoomMultiplier(prev => Math.min(prev + 0.25, 3.5))}
                  style={{ background: 'transparent', border: 'none', color: '#fff', padding: '4px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                  title="Zoom In (+)"
                >
                  <ZoomIn size={14} />
                </button>
              </div>
              <button
                onClick={() => { setExpandedChart(false); setSelectedDayDrilldown(null); setZoomMultiplier(1); }}
                style={{
                  background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)',
                  color: '#fff', padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'monospace', fontSize: 12, fontWeight: 700
                }}
              >
                <X size={16} /> CLOSE
              </button>
            </div>
          </div>

          <div style={{ flex: 1, width: '100%', minHeight: 400, overflowX: 'auto', overflowY: 'hidden', paddingBottom: 15 }}>
            <div style={{ width: (fullIntradayMacro || selectedDayDrilldown) ? Math.max(1200, displayChart.length * 110 * zoomMultiplier) : `${Math.max(100, 100 * zoomMultiplier)}%`, height: '100%', minHeight: 400 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={displayChart}
                  margin={{ top: 20, right: 30, left: 0, bottom: 20 }}
                  onClick={(e) => {
                    if (e && e.activePayload && e.activePayload[0]?.payload?.calendarDate) {
                      setSelectedDayDrilldown(e.activePayload[0].payload.calendarDate);
                    }
                  }}
                >
                  <defs>
                    <linearGradient id="gAAPLExp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00E676" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#00E676" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="gVIXExp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#FFEA00" stopOpacity={0.25}/>
                      <stop offset="95%" stopColor="#FFEA00" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.12)" vertical={true} horizontal={true} />
                  <XAxis
                    dataKey="unique_id"
                    stroke="rgba(255,255,255,0.25)"
                    tick={{ fill: 'rgba(255,255,255,0.85)', fontSize: 11, fontFamily: 'monospace', fontWeight: 600 }}
                    minTickGap={(fullIntradayMacro || selectedDayDrilldown) ? 10 : 40}
                    interval={(fullIntradayMacro || selectedDayDrilldown) ? 0 : 'preserveEnd'}
                    tickFormatter={(val) => displayChart[val]?.timestamp || ''}
                  />
                  <YAxis yAxisId="price" stroke="rgba(255,255,255,0.25)" tick={{ fill: '#00E676', fontSize: 11, fontFamily: 'monospace', fontWeight: 700 }} tickFormatter={v => `$${v}`} domain={['auto','auto']} />
                  <YAxis yAxisId="vix" orientation="right" stroke="rgba(255,255,255,0.25)" tick={{ fill: '#FFEA00', fontSize: 11, fontFamily: 'monospace', fontWeight: 700 }} domain={['auto','auto']} />
                  <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#38BDF8', strokeWidth: 1.5, strokeDasharray: '3 3' }} />
                  <Area yAxisId="price" type="monotone" dataKey="sma_200" stroke="#38BDF8" strokeWidth={2} strokeDasharray="5 5" fill="none" name="200 SMA" dot={false} />
                  <Area yAxisId="price" type="monotone" dataKey="aapl_price" stroke="#00E676" strokeWidth={2.5} fill="url(#gAAPLExp)" name="AAPL" dot={false} />
                  <Area yAxisId="vix" type="monotone" dataKey="vix_level" stroke="#FFEA00" strokeWidth={1.5} fill="url(#gVIXExp)" name="VIX" dot={false} />
                  {tradeMarkers.map((m, idx) => (
                    <ReferenceDot key={idx} yAxisId="price" x={m.unique_id} y={m.price} r={8} fill={m.color} stroke="#0f172a" strokeWidth={2.5} isFront={true} />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
