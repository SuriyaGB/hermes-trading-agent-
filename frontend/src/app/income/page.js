"use client";
import { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { TrendingUp, BarChart2, Activity } from 'lucide-react';

import { getApiUrl, getThetaGangApiUrl } from '../../utils/api';

export default function IncomeTracker() {
  const [data, setData] = useState([]);
  const [chartType, setChartType] = useState('Area');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const hermesApi = getApiUrl();
        const thetaApi = getThetaGangApiUrl();

        // 1. Fetch Hermes Income History
        const hermesRes = await fetch(`/api/proxy?url=${encodeURIComponent(`${hermesApi}/api/income_history?t=${Date.now()}`)}`);
        let hermesJson = [];
        if (hermesRes.ok) {
          hermesJson = await hermesRes.json();
        }

        // 2. Fetch ThetaGang Data
        let thetaJson = null;
        try {
          const targetUrl = thetaApi.includes('vercel.app')
            ? `${thetaApi}/data.json?t=${Date.now()}`
            : `${thetaApi}/api/data?t=${Date.now()}`;
          const proxyUrl = `/api/proxy?url=${encodeURIComponent(targetUrl)}`;
          const thetaRes = await fetch(proxyUrl);
          if (thetaRes.ok) {
            thetaJson = await thetaRes.json();
          }
        } catch (err) {
          console.error("Error loading ThetaGang data", err);
        }

        // 3. Combine both data sets by date
        const dataMap = {};

        // Process Hermes History
        if (Array.isArray(hermesJson)) {
          hermesJson.forEach(point => {
            const dateStr = point.timestamp ? point.timestamp.split(' ')[0] : '';
            if (dateStr) {
              if (!dataMap[dateStr]) dataMap[dateStr] = {};
              dataMap[dateStr].hermes = point.balance;
            }
          });
        }

        // Process ThetaGang History
        if (thetaJson?.performance) {
          thetaJson.performance.forEach(pt => {
            const dateStr = pt.fullTime ? pt.fullTime.split(' ')[0] : '';
            if (dateStr) {
              if (!dataMap[dateStr]) dataMap[dateStr] = {};
              dataMap[dateStr].theta = pt.value;
            }
          });
        }

        // Sort dates chronologically and build combined points
        const sortedDates = Object.keys(dataMap).filter(date => date >= '2026-05-27').sort();

        let lastHermes = 250000;
        let lastTheta = 250000;

        const combined = sortedDates.map(date => {
          const hVal = dataMap[date].hermes || lastHermes;
          const tVal = dataMap[date].theta || lastTheta;
          lastHermes = hVal;
          lastTheta = tVal;

          const parts = date.split('-');
          const formattedDate = parts.length === 3 ? `${parts[1]}/${parts[2]}` : date;

          return {
            time: formattedDate,
            fullTime: date,
            "Hermes Balance": hVal,
            "ThetaGang Balance": tVal
          };
        });

        setData(combined);
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

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const fullTime = payload[0].payload.fullTime || '';
      return (
        <div className="bg-black/90 border border-white/20 p-4 rounded-lg shadow-2xl backdrop-blur-md font-mono text-xs space-y-2">
          <p className="text-white/70 pb-2 border-b border-white/10">{fullTime}</p>
          {payload.map((item, idx) => (
            <div key={idx} className="flex justify-between items-center gap-6">
              <span style={{ color: item.color }} className="capitalize">{item.name}:</span>
              <span className="font-semibold text-white">
                ${(item.value ?? 0).toLocaleString('en-US', {minimumFractionDigits: 2})}
               </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500 pb-10">
      
      {/* Header */}
      <div className="flex justify-between items-end border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight">Income Tracker</h1>
          <p className="text-white/50 mt-2 font-mono text-sm flex items-center tracking-widest">
            <TrendingUp size={14} className="text-cyber-green mr-2 animate-pulse" />
            LIVE ACCOUNT BALANCE COMPARISON GROWTH
          </p>
        </div>
        
        {/* Chart Type Switcher */}
        <div className="flex space-x-2 bg-white/5 p-1 rounded-lg border border-white/5">
          <button 
            onClick={() => setChartType('Area')} 
            className={`px-4 py-2 rounded-md text-sm font-mono flex items-center transition-all ${chartType === 'Area' ? 'bg-cyber-green/20 text-cyber-green border border-cyber-green/30 shadow-[0_0_15px_rgba(0,230,118,0.2)]' : 'text-white/50 hover:text-white'}`}
          >
            <Activity size={16} className="mr-2" /> Area
          </button>
          <button 
            onClick={() => setChartType('Line')} 
            className={`px-4 py-2 rounded-md text-sm font-mono flex items-center transition-all ${chartType === 'Line' ? 'bg-cyber-green/20 text-cyber-green border border-cyber-green/30 shadow-[0_0_15px_rgba(0,230,118,0.2)]' : 'text-white/50 hover:text-white'}`}
          >
            <TrendingUp size={16} className="mr-2" /> Line
          </button>
          <button 
            onClick={() => setChartType('Bar')} 
            className={`px-4 py-2 rounded-md text-sm font-mono flex items-center transition-all ${chartType === 'Bar' ? 'bg-cyber-green/20 text-cyber-green border border-cyber-green/30 shadow-[0_0_15px_rgba(0,230,118,0.2)]' : 'text-white/50 hover:text-white'}`}
          >
            <BarChart2 size={16} className="mr-2" /> Bar
          </button>
        </div>
      </div>

      {/* Recharts Graph Area */}
      <div className="glass-panel p-6 h-[600px] w-full relative">
         <h3 className="text-lg font-medium mb-6 absolute top-6 left-6 z-10 bg-black/40 px-3 py-1 rounded border border-white/5">Total Cash Balance</h3>
         
         {data.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%" className="pt-12">
              {chartType === 'Area' ? (
                <AreaChart data={data} margin={{ top: 20, right: 30, left: 40, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorHermes" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00E676" stopOpacity={0.15}/>
                      <stop offset="95%" stopColor="#00E676" stopOpacity={0.0}/>
                    </linearGradient>
                    <linearGradient id="colorTheta" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00D6FF" stopOpacity={0.15}/>
                      <stop offset="95%" stopColor="#00D6FF" stopOpacity={0.0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
                  <YAxis stroke="rgba(255,255,255,0.3)" tick={{fill: '#00E676', fontSize: 12, fontFamily: 'monospace'}} domain={['dataMin - 1000', 'dataMax + 1000']} tickFormatter={(value) => `$${value.toLocaleString()}`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }} />
                  <Area type="monotone" dataKey="Hermes Balance" stroke="#00E676" fillOpacity={1} fill="url(#colorHermes)" strokeWidth={3} />
                  <Area type="monotone" dataKey="ThetaGang Balance" stroke="#00D6FF" fillOpacity={1} fill="url(#colorTheta)" strokeWidth={3} />
                </AreaChart>
              ) : chartType === 'Line' ? (
                <LineChart data={data} margin={{ top: 20, right: 30, left: 40, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
                  <YAxis stroke="rgba(255,255,255,0.3)" tick={{fill: '#00E676', fontSize: 12, fontFamily: 'monospace'}} domain={['dataMin - 1000', 'dataMax + 1000']} tickFormatter={(value) => `$${value.toLocaleString()}`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }} />
                  <Line type="monotone" dataKey="Hermes Balance" stroke="#00E676" strokeWidth={4} dot={false} />
                  <Line type="monotone" dataKey="ThetaGang Balance" stroke="#00D6FF" strokeWidth={4} dot={false} />
                </LineChart>
              ) : (
                <BarChart data={data} margin={{ top: 20, right: 30, left: 40, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
                  <YAxis stroke="rgba(255,255,255,0.3)" tick={{fill: '#00E676', fontSize: 12, fontFamily: 'monospace'}} domain={['dataMin - 1000', 'dataMax + 1000']} tickFormatter={(value) => `$${value.toLocaleString()}`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }} />
                  <Bar dataKey="Hermes Balance" fill="#00E676" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="ThetaGang Balance" fill="#00D6FF" radius={[4, 4, 0, 0]} />
                </BarChart>
              )}
            </ResponsiveContainer>
         ) : (
            <div className="h-full w-full flex items-center justify-center font-mono text-white/30 border border-white/5 border-dashed rounded-lg">
              {loading ? "LOADING INCOME COMPARISON DATA..." : "NO DATA FOUND"}
            </div>
         )}
      </div>
    </div>
  );
}
