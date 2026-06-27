"use client";

import { useEffect, useState } from 'react';
import {
  ShieldCheck, Zap, Activity, Cpu, TrendingUp, Target,
  DollarSign, AlertTriangle, Calendar, BarChart2, Award,
  ChevronRight, Clock
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine
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
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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
  SELL_PUT: { color: '#38BDF8', label: 'SELL PUT', symbol: '▼' },
  SELL_CALL: { color: '#A78BFA', label: 'SELL CALL', symbol: '▼' },
  ROLL_PUT_CLOSE: { color: '#FB923C', label: 'ROLL ✕', symbol: '○' },
  ROLL_PUT_OPEN: { color: '#FB923C', label: 'ROLL ↺', symbol: '●' },
  CLOSE_FOR_PROFIT: { color: '#00E676', label: 'CLOSE ✓', symbol: '★' },
};

// Custom recharts tooltip
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: '#0d1117', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 8, padding: '10px 14px', fontFamily: 'monospace', fontSize: 11
      }}>
        <p style={{ color: 'rgba(255,255,255,0.5)', marginBottom: 6 }}>{label}</p>
        {payload.map((p, i) => (
          <p key={i} style={{ color: p.color, marginBottom: 2 }}>
            {p.name}: {p.name.includes('VIX') ? p.value?.toFixed(2) : fmt$(p.value)}
          </p>
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

  // Chart data — use full history if available, else the pulses API data
  const displayChart = (chartData.pulses && chartData.pulses.length > 0)
    ? chartData.pulses.map(p => ({
        timestamp: formatTs(p.timestamp),
        aapl_price: p.aapl_price,
        vix_level: p.vix_level,
        sma_200: p.sma_200,
        day_classification: p.day_classification,
      }))
    : pulses.map(p => ({
        timestamp: formatTs(p.timestamp),
        aapl_price: p.aapl_price,
        vix_level: p.vix_level,
        sma_200: null,
      }));

  const chartEvents = chartData.events || [];

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
          <span style={{ color: 'rgba(255,255,255,0.6)', fontFamily: 'monospace', fontSize: 11, letterSpacing: '0.14em' }}>LIVE POSITION GRID — ALL 4 SLOTS</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14 }}>
          {positions.length === 0 ? (
            <div className="glass-panel" style={{ gridColumn: '1/-1', padding: 40, textAlign: 'center', color: 'rgba(255,255,255,0.2)', fontFamily: 'monospace', fontSize: 12 }}>
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
              return (
                <div
                  key={i}
                  className="glass-panel"
                  style={{
                    padding: 18, cursor: 'pointer', transition: 'all 0.2s',
                    border: `1px solid ${activeSlot === i ? slotColor + '40' : 'rgba(255,255,255,0.05)'}`,
                    boxShadow: activeSlot === i ? `0 0 20px ${slotColor}15` : undefined
                  }}
                  onClick={() => setActiveSlot(activeSlot === i ? null : i)}
                >
                  {/* Slot header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: slotColor, boxShadow: `0 0 8px ${slotColor}`, display: 'inline-block' }} />
                      <span style={{ fontFamily: 'monospace', fontSize: 10, color: slotColor, letterSpacing: '0.12em' }}>{SLOT_LABELS[i]}</span>
                    </div>
                    <span style={{
                      background: pos.option_type === 'PUT' ? 'rgba(251,146,60,0.15)' : 'rgba(167,139,250,0.15)',
                      color: pos.option_type === 'PUT' ? '#FB923C' : '#A78BFA',
                      fontFamily: 'monospace', fontSize: 9, padding: '2px 7px', borderRadius: 4,
                      border: `1px solid ${pos.option_type === 'PUT' ? 'rgba(251,146,60,0.3)' : 'rgba(167,139,250,0.3)'}`
                    }}>{pos.option_type}</span>
                  </div>

                  {/* Contract identity */}
                  <div style={{ marginBottom: 14 }}>
                    <p style={{ fontSize: 22, fontWeight: 300, color: '#fff', fontFamily: 'monospace', letterSpacing: '-0.02em' }}>
                      {pos.symbol} {pos.strike}P
                    </p>
                    <p style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'monospace', fontSize: 10, marginTop: 2 }}>
                      Expires: {formatExpiry(pos.expiry)}
                    </p>
                  </div>

                  {/* Metrics grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
                    <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '8px 10px' }}>
                      <p style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'monospace', fontSize: 9, marginBottom: 4, letterSpacing: '0.1em' }}>DELTA Δ</p>
                      <p style={{ color: risk.color, fontFamily: 'monospace', fontSize: 14, fontWeight: 600 }}>{pos.delta || '--'}</p>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '8px 10px' }}>
                      <p style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'monospace', fontSize: 9, marginBottom: 4, letterSpacing: '0.1em' }}>DTE</p>
                      <p style={{ color: dte <= 15 ? '#FFEA00' : '#fff', fontFamily: 'monospace', fontSize: 14, fontWeight: 600 }}>{dte !== null ? `${dte}d` : '--'}</p>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '8px 10px' }}>
                      <p style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'monospace', fontSize: 9, marginBottom: 4, letterSpacing: '0.1em' }}>ENTRY</p>
                      <p style={{ color: '#fff', fontFamily: 'monospace', fontSize: 14 }}>{fmt$(pos.avg_cost)}</p>
                    </div>
                    <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '8px 10px' }}>
                      <p style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'monospace', fontSize: 9, marginBottom: 4, letterSpacing: '0.1em' }}>CURR PRICE</p>
                      <p style={{ color: '#fff', fontFamily: 'monospace', fontSize: 14 }}>{pos.current_price !== undefined ? fmt$(pos.current_price) : '--'}</p>
                    </div>
                  </div>

                  {/* Unrealized PnL bar */}
                  <div style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '10px 12px', marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'monospace', fontSize: 9, letterSpacing: '0.1em' }}>UNREALIZED P&L</span>
                      <span style={{ color: unrealized >= 0 ? '#00E676' : '#FF1744', fontFamily: 'monospace', fontSize: 11, fontWeight: 700 }}>
                        {unrealized !== undefined ? `${unrealized >= 0 ? '+' : ''}${fmt$(unrealized)} (${fmtPct(unrealizedPct)})` : '--'}
                      </span>
                    </div>
                    {unrealized !== undefined && (
                      <div style={{ height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                        <div style={{
                          height: '100%', borderRadius: 2,
                          width: `${Math.min(100, Math.abs(unrealizedPct || 0))}%`,
                          background: unrealized >= 0 ? '#00E676' : '#FF1744',
                          transition: 'width 0.5s ease'
                        }} />
                      </div>
                    )}
                  </div>

                  {/* Delta risk badge */}
                  <div style={{ background: risk.bg, border: `1px solid ${risk.color}30`, borderRadius: 6, padding: '5px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: risk.color, fontFamily: 'monospace', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em' }}>
                      {risk.label}
                    </span>
                    {isUnguided && (
                      <span style={{ color: '#FF1744', fontFamily: 'monospace', fontSize: 9, letterSpacing: '0.08em' }}>⚠ UNGUIDED ZONE</span>
                    )}
                  </div>

                  {/* Stale data badge */}
                  {pos.is_fallback_data && (
                    <div style={{ marginTop: 8, background: 'rgba(255,179,0,0.08)', border: '1px solid rgba(255,179,0,0.2)', borderRadius: 5, padding: '3px 8px' }}>
                      <span style={{ color: '#FFB300', fontFamily: 'monospace', fontSize: 9 }}>⚠ STALE DELTA DATA</span>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── MASTER MARKET CHART ─────────────────────────────────────── */}
      <div className="glass-panel" style={{ padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Activity size={14} color="#38BDF8" />
            <span style={{ color: 'rgba(255,255,255,0.6)', fontFamily: 'monospace', fontSize: 11, letterSpacing: '0.14em' }}>
              AAPL MARKET REGIME — FULL HISTORY ({displayChart.length} DATA POINTS)
            </span>
          </div>
          <div style={{ display: 'flex', gap: 16, fontFamily: 'monospace', fontSize: 10 }}>
            <span style={{ color: '#00E676' }}>● AAPL PRICE</span>
            <span style={{ color: '#38BDF8' }}>— 200 SMA</span>
            <span style={{ color: '#FFEA00' }}>● VIX</span>
          </div>
        </div>

        <div style={{ height: 320, position: 'relative' }}>
          <ResponsiveContainer width="100%" height="100%">
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
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
              <XAxis dataKey="timestamp" stroke="rgba(255,255,255,0.15)" tick={{ fill: 'rgba(255,255,255,0.35)', fontSize: 9, fontFamily: 'monospace' }} interval="preserveStartEnd" />
              <YAxis yAxisId="price" stroke="rgba(255,255,255,0.15)" tick={{ fill: '#00E676', fontSize: 9, fontFamily: 'monospace' }} tickFormatter={v => `$${v}`} domain={['auto','auto']} />
              <YAxis yAxisId="vix" orientation="right" stroke="rgba(255,255,255,0.15)" tick={{ fill: '#FFEA00', fontSize: 9, fontFamily: 'monospace' }} domain={['auto','auto']} />
              <Tooltip content={<CustomTooltip />} />
              {/* 200 SMA line overlay */}
              <Area yAxisId="price" type="monotone" dataKey="sma_200" stroke="#38BDF8" strokeWidth={1.5} strokeDasharray="4 4" fill="none" name="200 SMA" dot={false} />
              <Area yAxisId="price" type="monotone" dataKey="aapl_price" stroke="#00E676" strokeWidth={2} fill="url(#gAAPL)" name="AAPL" dot={false} />
              <Area yAxisId="vix" type="monotone" dataKey="vix_level" stroke="#FFEA00" strokeWidth={1.2} fill="url(#gVIX)" name="VIX" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Trade event legend strip below chart */}
        {chartEvents.length > 0 && (
          <div style={{ marginTop: 16, borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 14 }}>
            <p style={{ color: 'rgba(255,255,255,0.3)', fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.12em', marginBottom: 10 }}>TRADE EVENTS</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {chartEvents.slice(0, 20).map((ev, i) => {
                const cfg = EVENT_COLORS[ev.action] || { color: '#fff', label: ev.action, symbol: '·' };
                return (
                  <div key={i} title={`${ev.action}: ${ev.strike}P ${ev.expiry} @ $${ev.price}`} style={{
                    background: `${cfg.color}15`, border: `1px solid ${cfg.color}30`,
                    borderRadius: 5, padding: '3px 8px', display: 'flex', alignItems: 'center', gap: 5,
                    fontFamily: 'monospace', fontSize: 9, cursor: 'default', transition: 'all 0.15s'
                  }}>
                    <span style={{ color: cfg.color }}>{cfg.symbol}</span>
                    <span style={{ color: cfg.color }}>{cfg.label}</span>
                    <span style={{ color: 'rgba(255,255,255,0.4)' }}>{ev.strike}P</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── AI BRAIN FEED ───────────────────────────────────────────── */}
      <div className="glass-panel" style={{ padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Cpu size={14} color="#A78BFA" />
            <span style={{ color: 'rgba(255,255,255,0.6)', fontFamily: 'monospace', fontSize: 11, letterSpacing: '0.14em' }}>AI QUANTUM REASONING — LAST PULSE</span>
          </div>
          {lastPulse && (
            <span style={{ background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.2)', borderRadius: 5, padding: '3px 10px', fontFamily: 'monospace', fontSize: 10, color: '#A78BFA' }}>
              {lastPulse.ai_decision}
            </span>
          )}
        </div>
        {lastPulse ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                { label: 'TIMESTAMP', value: new Date(lastPulse.timestamp).toLocaleString() },
                { label: 'AAPL PRICE', value: fmt$(lastPulse.aapl_price) },
                { label: 'VIX LEVEL', value: lastPulse.vix_level?.toFixed(2) || '--' },
                { label: 'EARNINGS IN', value: lastPulse.earnings_days !== null ? `${lastPulse.earnings_days} days` : '--' },
              ].map((item, i) => (
                <div key={i} style={{ background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '8px 12px', display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'monospace', fontSize: 10 }}>{item.label}</span>
                  <span style={{ color: '#fff', fontFamily: 'monospace', fontSize: 10 }}>{item.value}</span>
                </div>
              ))}
            </div>
            <div style={{
              background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: 8, padding: 16, overflowY: 'auto', maxHeight: 200,
              fontFamily: 'monospace', fontSize: 11, color: 'rgba(0,230,118,0.85)',
              lineHeight: 1.7
            }}>
              {lastPulse.ai_reasoning || 'No reasoning recorded.'}
            </div>
          </div>
        ) : (
          <div style={{ padding: 40, textAlign: 'center', color: 'rgba(255,255,255,0.2)', fontFamily: 'monospace', fontSize: 12, border: '1px dashed rgba(255,255,255,0.08)', borderRadius: 8 }}>
            AWAITING PULSE REASONING FEED...
          </div>
        )}
      </div>

    </div>
  );
}
