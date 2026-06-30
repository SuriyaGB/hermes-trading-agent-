"use client";

import { useEffect, useState } from 'react';
import { FileText, TrendingDown, TrendingUp, RefreshCw, ChevronDown, ChevronUp, DollarSign } from 'lucide-react';
import { getApiUrl } from '../../utils/api';

function fmt$(v, dec=2) {
  if (v===null||v===undefined||isNaN(v)) return '--';
  return `$${Number(v).toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec})}`;
}
function formatExpiry(s) {
  if (!s) return '--';
  const st = String(s).trim();
  if (st.length === 8) {
    const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[parseInt(st.substring(4,6),10)-1]} ${parseInt(st.substring(6,8),10)}, ${st.substring(0,4)}`;
  }
  return s;
}
function formatTs(ts) {
  if (!ts) return '--';
  return new Date(ts).toLocaleString('en-US',{month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'});
}

const ACTION_CONFIG = {
  SELL_PUT:       { label:'SELL PUT',        color:'#38BDF8', bg:'rgba(56,189,248,0.12)', icon:TrendingDown, cashSign:+1 },
  SELL_CALL:      { label:'SELL CALL',       color:'#A78BFA', bg:'rgba(167,139,250,0.12)', icon:TrendingDown, cashSign:+1 },
  ROLL_PUT_CLOSE: { label:'ROLL — CLOSE ✕', color:'#FB923C', bg:'rgba(251,146,60,0.1)', icon:RefreshCw, cashSign:-1 },
  ROLL_PUT_OPEN:  { label:'ROLL — OPEN ↺',  color:'#FB923C', bg:'rgba(251,146,60,0.1)', icon:RefreshCw, cashSign:+1 },
  CLOSE_FOR_PROFIT:{label:'CLOSE FOR PROFIT ✓',color:'#00E676',bg:'rgba(0,230,118,0.12)',icon:TrendingUp, cashSign:-1 },
  BUY_CLOSE:      { label:'BUY CLOSE',      color:'#F87171', bg:'rgba(248,113,113,0.1)', icon:TrendingUp, cashSign:-1 },
};

export default function LedgerPage() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    const load = async () => {
      try {
        const base = getApiUrl();
        const res = await fetch(`/api/proxy?url=${encodeURIComponent(`${base}/api/trades?t=${Date.now()}`)}`);
        if (res.ok) {
          const data = await res.json();
          setTrades(data);
        }
      } catch(e) { console.error(e); }
      finally { setLoading(false); }
    };
    load();
  }, []);

  const FILTER_OPTIONS = ['ALL','SELL_PUT','ROLL_PUT_CLOSE','ROLL_PUT_OPEN','CLOSE_FOR_PROFIT'];

  // Group roll pairs by same timestamp for bracket display
  const groupedTrades = [];
  const seenTs = new Set();
  trades.forEach((t, idx) => {
    const key = `${t.timestamp}::${t.action}::${t.strike}`;
    if (seenTs.has(key)) return;
    seenTs.add(key);
    groupedTrades.push({ ...t, _idx: idx });
  });

  const filtered = filter === 'ALL' ? groupedTrades : groupedTrades.filter(t => t.action === filter);

  // Compute running cash balance
  let runnningCash = 250000;
  const withBalance = groupedTrades.map(t => {
    const price = parseFloat(t.price || 0);
    const cfg = ACTION_CONFIG[t.action] || { cashSign: 0 };
    const impact = price * 100 * cfg.cashSign;
    runnningCash += impact;
    return { ...t, cash_after: runnningCash, cash_impact: impact };
  });

  // Find pairs for roll brackets
  const rollPairs = {};
  groupedTrades.forEach(t => {
    if (t.action === 'ROLL_PUT_CLOSE') {
      const pairTs = t.timestamp;
      if (!rollPairs[pairTs]) rollPairs[pairTs] = { close: null, open: null };
      rollPairs[pairTs].close = t;
    }
    if (t.action === 'ROLL_PUT_OPEN') {
      const pairTs = t.timestamp;
      if (!rollPairs[pairTs]) rollPairs[pairTs] = { close: null, open: null };
      rollPairs[pairTs].open = t;
    }
  });

  const toggleExpand = (idx) => setExpanded(prev => ({ ...prev, [idx]: !prev[idx] }));

  return (
    <div className="max-w-screen-xl mx-auto space-y-6 pb-12 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-white/10 pb-5">
        <div>
          <h1 style={{ fontSize:28, fontWeight:300, letterSpacing:'-0.02em', color:'#fff' }}>Transaction Ledger</h1>
          <p style={{ color:'rgba(255,255,255,0.4)', marginTop:4, fontFamily:'monospace', fontSize:11, letterSpacing:'0.12em' }}>
            <FileText size={11} style={{ display:'inline', marginRight:6 }} />
            COMPLETE CASH FLOW HISTORY — {trades.length} TRANSACTIONS
          </p>
        </div>
        <div style={{ display:'flex', gap:8, fontFamily:'monospace', fontSize:10 }}>
          {FILTER_OPTIONS.map(f => (
            <button key={f} onClick={() => setFilter(f)} style={{
              padding:'5px 12px', borderRadius:5, cursor:'pointer', transition:'all 0.15s',
              background: filter===f ? 'rgba(0,230,118,0.15)' : 'rgba(255,255,255,0.05)',
              color: filter===f ? '#00E676' : 'rgba(255,255,255,0.5)',
              border: filter===f ? '1px solid rgba(0,230,118,0.3)' : '1px solid rgba(255,255,255,0.08)',
            }}>
              {f === 'ALL' ? 'ALL' : (ACTION_CONFIG[f]?.label || f)}
            </button>
          ))}
        </div>
      </div>

      {/* Summary bar */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12 }}>
        {[
          { label:'STARTING CAPITAL', value:fmt$(250000), color:'rgba(255,255,255,0.7)' },
          { label:'GROSS PREMIUM COLLECTED', value:fmt$(groupedTrades.filter(t=>['SELL_PUT','SELL_CALL','ROLL_PUT_OPEN'].includes(t.action)).reduce((a,t)=>a+parseFloat(t.price||0)*100,0)), color:'#00E676' },
          { label:'TOTAL ROLL DEBITS PAID', value:fmt$(groupedTrades.filter(t=>t.action==='ROLL_PUT_CLOSE').reduce((a,t)=>a+parseFloat(t.price||0)*100,0)), color:'#FB923C' },
          { label:'FINAL RUNNING BALANCE', value:fmt$(runnningCash), color:'#38BDF8' },
        ].map((item,i) => (
          <div key={i} className="glass-panel" style={{ padding:'14px 18px' }}>
            <p style={{ color:'rgba(255,255,255,0.35)', fontFamily:'monospace', fontSize:10, letterSpacing:'0.1em', marginBottom:6 }}>{item.label}</p>
            <p style={{ color:item.color, fontFamily:'monospace', fontSize:18, fontWeight:300 }}>{item.value}</p>
          </div>
        ))}
      </div>

      {/* Ledger table */}
      {loading ? (
        <div style={{ textAlign:'center', padding:60, color:'rgba(255,255,255,0.3)', fontFamily:'monospace' }}>LOADING LEDGER...</div>
      ) : (
        <div className="glass-panel" style={{ overflow:'hidden' }}>
          {/* Table header */}
          <div style={{
            display:'grid', gridTemplateColumns:'180px 150px 100px 100px 120px 110px 120px 40px',
            gap:0, padding:'10px 20px', background:'rgba(0,0,0,0.4)',
            borderBottom:'1px solid rgba(255,255,255,0.06)',
            fontFamily:'monospace', fontSize:10, color:'rgba(255,255,255,0.35)', letterSpacing:'0.1em'
          }}>
            <span>TIMESTAMP</span><span>ACTION</span><span>STRIKE</span><span>EXPIRY</span>
            <span>PRICE/SHARE</span><span>CASH IMPACT</span><span>RUNNING BALANCE</span><span/>
          </div>

          {/* Rows */}
          {(filter==='ALL' ? withBalance : withBalance.filter(t=>t.action===filter)).map((trade, i) => {
            const cfg = ACTION_CONFIG[trade.action] || { label:trade.action, color:'#fff', bg:'rgba(255,255,255,0.05)' };
            const impact = trade.cash_impact;
            const isOpen = expanded[i];
            // Roll pair math
            const isRollClose = trade.action === 'ROLL_PUT_CLOSE';
            const rollPair = isRollClose ? rollPairs[trade.timestamp] : null;
            const netCredit = rollPair?.close && rollPair?.open
              ? (parseFloat(rollPair.open.price||0) - parseFloat(rollPair.close.price||0)) * 100
              : null;

            return (
              <div key={i} style={{ borderBottom:'1px solid rgba(255,255,255,0.04)' }}>
                <div
                  style={{
                    display:'grid', gridTemplateColumns:'180px 150px 100px 100px 120px 110px 120px 40px',
                    gap:0, padding:'12px 20px', alignItems:'center',
                    background: i%2===0 ? 'transparent' : 'rgba(0,0,0,0.15)',
                    cursor:'pointer', transition:'background 0.15s'
                  }}
                  onClick={() => toggleExpand(i)}
                  onMouseEnter={e => e.currentTarget.style.background='rgba(255,255,255,0.03)'}
                  onMouseLeave={e => e.currentTarget.style.background= i%2===0?'transparent':'rgba(0,0,0,0.15)'}
                >
                  <span style={{ color:'rgba(255,255,255,0.5)', fontFamily:'monospace', fontSize:11 }}>{formatTs(trade.timestamp)}</span>
                  <span style={{
                    background:cfg.bg, color:cfg.color,
                    fontFamily:'monospace', fontSize:10, padding:'3px 8px',
                    borderRadius:4, display:'inline-block', letterSpacing:'0.06em'
                  }}>{cfg.label}</span>
                  <span style={{ color:'#fff', fontFamily:'monospace', fontSize:13 }}>{trade.strike}P</span>
                  <span style={{ color:'rgba(255,255,255,0.6)', fontFamily:'monospace', fontSize:11 }}>{formatExpiry(trade.expiry)}</span>
                  <span style={{ color:'#fff', fontFamily:'monospace', fontSize:13 }}>{fmt$(trade.price)}</span>
                  <span style={{
                    fontFamily:'monospace', fontSize:13, fontWeight:600,
                    color: impact > 0 ? '#00E676' : '#FB923C'
                  }}>
                    {impact > 0 ? '+' : ''}{fmt$(impact)}
                  </span>
                  <span style={{ color:'rgba(255,255,255,0.8)', fontFamily:'monospace', fontSize:13 }}>{fmt$(trade.cash_after)}</span>
                  <span style={{ color:'rgba(255,255,255,0.3)' }}>{isOpen ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}</span>
                </div>

                {/* Expanded roll bracket detail */}
                {isOpen && (
                  <div style={{
                    padding:'12px 24px 16px', background:'rgba(251,146,60,0.04)',
                    borderLeft:'3px solid rgba(251,146,60,0.4)'
                  }}>
                    {netCredit !== null ? (
                      <div style={{ fontFamily:'monospace', fontSize:11 }}>
                        <p style={{ color:'rgba(255,255,255,0.4)', marginBottom:8, fontSize:10, letterSpacing:'0.1em' }}>ROLL PAIR ECONOMICS</p>
                        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:12 }}>
                          <div style={{ background:'rgba(0,0,0,0.3)', borderRadius:6, padding:'10px 14px' }}>
                            <p style={{ color:'rgba(255,255,255,0.35)', fontSize:9, marginBottom:4 }}>CLOSED CONTRACT</p>
                            <p style={{ color:'#FB923C' }}>{rollPair.close?.strike}P {formatExpiry(rollPair.close?.expiry)}</p>
                            <p style={{ color:'#fff', marginTop:4 }}>Paid: {fmt$(parseFloat(rollPair.close?.price||0)*100)}</p>
                          </div>
                          <div style={{ background:'rgba(0,0,0,0.3)', borderRadius:6, padding:'10px 14px' }}>
                            <p style={{ color:'rgba(255,255,255,0.35)', fontSize:9, marginBottom:4 }}>OPENED CONTRACT</p>
                            <p style={{ color:'#38BDF8' }}>{rollPair.open?.strike}P {formatExpiry(rollPair.open?.expiry)}</p>
                            <p style={{ color:'#fff', marginTop:4 }}>Collected: {fmt$(parseFloat(rollPair.open?.price||0)*100)}</p>
                          </div>
                          <div style={{ background: netCredit>=0 ? 'rgba(0,230,118,0.08)':'rgba(255,23,68,0.08)', borderRadius:6, padding:'10px 14px', border:`1px solid ${netCredit>=0?'rgba(0,230,118,0.2)':'rgba(255,23,68,0.2)'}` }}>
                            <p style={{ color:'rgba(255,255,255,0.35)', fontSize:9, marginBottom:4 }}>NET CREDIT / DEBIT</p>
                            <p style={{ color: netCredit>=0?'#00E676':'#FF1744', fontSize:18, fontWeight:700 }}>{netCredit>=0?'+':''}{fmt$(netCredit)}</p>
                            <p style={{ color:'rgba(255,255,255,0.3)', fontSize:9, marginTop:4 }}>{netCredit>=0?'Profitable roll':'Defensive roll cost'}</p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ fontFamily:'monospace', fontSize:11, color:'rgba(255,255,255,0.4)' }}>
                        <p>Strike: {trade.strike}P | Expiry: {formatExpiry(trade.expiry)} | Price: {fmt$(trade.price)}/share | Total: {fmt$(parseFloat(trade.price||0)*100)}</p>
                        {trade.pnl_realized && parseFloat(trade.pnl_realized)!==0 && (
                          <p style={{ marginTop:6, color: parseFloat(trade.pnl_realized)>=0?'#00E676':'#FF1744' }}>
                            Realized P&L: {parseFloat(trade.pnl_realized)>=0?'+':''}{fmt$(trade.pnl_realized)}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
