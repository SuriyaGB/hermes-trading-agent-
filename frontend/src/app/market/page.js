"use client";
import { useEffect, useState } from 'react';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { LineChart as LineChartIcon, BarChart2, Activity, Globe, Zap } from 'lucide-react';

export default function MarketView() {
  const [data, setData] = useState([]);
  const [chartType, setChartType] = useState('Area');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const apiUrl = (typeof window !== 'undefined' ? localStorage.getItem('API_BASE_URL') : null) || process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "";
        const res = await fetch(`${apiUrl}/api/pulses`);
        const json = await res.json();
        
        // Reverse array to put oldest on the left and newest on the right
        const formattedData = json.reverse().map(pulse => {
          const d = new Date(pulse.timestamp);
          return {
            time: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }), 
            fullTime: d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute:'2-digit' }), 
            price: pulse.aapl_price,
            vix: pulse.vix_level,
            delta: pulse.delta_current === '--' ? null : pulse.delta_current,
            dte: pulse.dte_current === '--' ? null : pulse.dte_current
          };
        });
        
        setData(formattedData);
      } catch (error) {
        console.error("Error fetching data:", error);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const fullTime = payload[0].payload.fullTime;
      return (
        <div className="bg-black/90 border border-white/20 p-4 rounded-lg shadow-2xl backdrop-blur-md">
          <p className="text-white/70 text-xs font-mono mb-3 pb-2 border-b border-white/10">{fullTime}</p>
          {payload.map((entry, index) => {
            // Format numbers based on metric type
            let displayValue = entry.value;
            if (entry.name === 'AAPL Price') displayValue = `$${entry.value.toFixed(2)}`;
            if (entry.name === 'Delta Greek') displayValue = entry.value.toFixed(4);
            if (entry.name === 'Days To Expiry') displayValue = `${entry.value} Days`;
            
            return (
              <p key={index} className="text-sm font-mono tracking-wider mb-1" style={{ color: entry.color }}>
                {entry.name.toUpperCase()}: {displayValue}
              </p>
            );
          })}
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
          <h1 className="text-4xl font-light tracking-tight">Market View</h1>
          <p className="text-white/50 mt-2 font-mono text-sm flex items-center tracking-widest">
            <Globe size={14} className="text-blue-400 mr-2" />
            LIVE MARKET CORRELATIONS & GREEKS
          </p>
        </div>
        
        {/* Chart Type Switcher */}
        <div className="flex space-x-2 bg-white/5 p-1 rounded-lg border border-white/5">
          <button 
            onClick={() => setChartType('Area')} 
            className={`px-4 py-2 rounded-md text-sm font-mono flex items-center transition-all ${chartType === 'Area' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.2)]' : 'text-white/50 hover:text-white'}`}
          >
            <Activity size={16} className="mr-2" /> Area
          </button>
          <button 
            onClick={() => setChartType('Line')} 
            className={`px-4 py-2 rounded-md text-sm font-mono flex items-center transition-all ${chartType === 'Line' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.2)]' : 'text-white/50 hover:text-white'}`}
          >
            <LineChartIcon size={16} className="mr-2" /> Line
          </button>
          <button 
            onClick={() => setChartType('Bar')} 
            className={`px-4 py-2 rounded-md text-sm font-mono flex items-center transition-all ${chartType === 'Bar' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.2)]' : 'text-white/50 hover:text-white'}`}
          >
            <BarChart2 size={16} className="mr-2" /> Bar
          </button>
        </div>
      </div>

      {/* Chart 1: Market Correlation */}
      <div className="glass-panel p-6 h-[500px] w-full relative">
         <h3 className="text-lg font-medium mb-6 absolute top-6 left-6 z-10 bg-black/40 px-3 py-1 rounded border border-white/5 flex items-center">
           <Globe size={16} className="mr-2 text-cyber-green" /> AAPL Price vs VIX Tracker
         </h3>
         
         {data.length > 0 ? (
           <ResponsiveContainer width="100%" height="100%" className="pt-12">
             {chartType === 'Area' ? (
               <AreaChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 0 }}>
                 <defs>
                   <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                     <stop offset="5%" stopColor="#00E676" stopOpacity={0.3}/>
                     <stop offset="95%" stopColor="#00E676" stopOpacity={0}/>
                   </linearGradient>
                   <linearGradient id="colorVix" x1="0" y1="0" x2="0" y2="1">
                     <stop offset="5%" stopColor="#FFEA00" stopOpacity={0.3}/>
                     <stop offset="95%" stopColor="#FFEA00" stopOpacity={0}/>
                   </linearGradient>
                 </defs>
                 <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                 <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
                 <YAxis yAxisId="left" stroke="rgba(255,255,255,0.3)" tick={{fill: '#00E676', fontSize: 12, fontFamily: 'monospace'}} domain={['auto', 'auto']} tickFormatter={(value) => `$${value}`} />
                 <YAxis yAxisId="right" orientation="right" stroke="rgba(255,255,255,0.3)" tick={{fill: '#FFEA00', fontSize: 12, fontFamily: 'monospace'}} domain={['auto', 'auto']} />
                 <Tooltip content={<CustomTooltip />} />
                 <Area yAxisId="left" type="monotone" dataKey="price" stroke="#00E676" fillOpacity={1} fill="url(#colorPrice)" strokeWidth={2} name="AAPL Price" />
                 <Area yAxisId="right" type="monotone" dataKey="vix" stroke="#FFEA00" fillOpacity={1} fill="url(#colorVix)" strokeWidth={2} name="VIX Level" />
               </AreaChart>
             ) : chartType === 'Line' ? (
               <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 0 }}>
                 <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                 <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
                 <YAxis yAxisId="left" stroke="rgba(255,255,255,0.3)" tick={{fill: '#00E676', fontSize: 12, fontFamily: 'monospace'}} domain={['auto', 'auto']} tickFormatter={(value) => `$${value}`} />
                 <YAxis yAxisId="right" orientation="right" stroke="rgba(255,255,255,0.3)" tick={{fill: '#FFEA00', fontSize: 12, fontFamily: 'monospace'}} domain={['auto', 'auto']} />
                 <Tooltip content={<CustomTooltip />} />
                 <Line yAxisId="left" type="monotone" dataKey="price" stroke="#00E676" strokeWidth={3} dot={false} name="AAPL Price" />
                 <Line yAxisId="right" type="monotone" dataKey="vix" stroke="#FFEA00" strokeWidth={2} dot={false} name="VIX Level" />
               </LineChart>
             ) : (
               <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 0 }}>
                 <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                 <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
                 <YAxis yAxisId="left" stroke="rgba(255,255,255,0.3)" tick={{fill: '#00E676', fontSize: 12, fontFamily: 'monospace'}} domain={['auto', 'auto']} tickFormatter={(value) => `$${value}`} />
                 <YAxis yAxisId="right" orientation="right" stroke="rgba(255,255,255,0.3)" tick={{fill: '#FFEA00', fontSize: 12, fontFamily: 'monospace'}} domain={['auto', 'auto']} />
                 <Tooltip content={<CustomTooltip />} />
                 <Bar yAxisId="left" dataKey="price" fill="#00E676" radius={[4, 4, 0, 0]} name="AAPL Price" />
                 <Bar yAxisId="right" dataKey="vix" fill="#FFEA00" radius={[4, 4, 0, 0]} name="VIX Level" />
               </BarChart>
             )}
           </ResponsiveContainer>
         ) : (
           <div className="h-full w-full flex items-center justify-center font-mono text-white/30 border border-white/5 border-dashed rounded-lg">
             LOADING MARKET DATA...
           </div>
         )}
      </div>

      {/* Chart 2: Greeks & Options Flow */}
      <div className="glass-panel p-6 h-[400px] w-full relative">
         <h3 className="text-lg font-medium mb-6 absolute top-6 left-6 z-10 bg-black/40 px-3 py-1 rounded border border-white/5 flex items-center">
           <Zap size={16} className="mr-2 text-purple-400" /> Options Greek Tracker (Delta & Time Decay)
         </h3>
         
         {data.length > 0 && data.some(d => d.delta !== null) ? (
           <ResponsiveContainer width="100%" height="100%" className="pt-12">
             <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 0 }}>
               <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
               <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
               <YAxis yAxisId="left" stroke="rgba(255,255,255,0.3)" tick={{fill: '#A855F7', fontSize: 12, fontFamily: 'monospace'}} domain={['auto', 'auto']} />
               <YAxis yAxisId="right" orientation="right" stroke="rgba(255,255,255,0.3)" tick={{fill: '#3B82F6', fontSize: 12, fontFamily: 'monospace'}} domain={['auto', 'auto']} />
               <Tooltip content={<CustomTooltip />} />
               <Line yAxisId="left" type="monotone" dataKey="delta" stroke="#A855F7" strokeWidth={3} dot={true} name="Delta Greek" />
               <Line yAxisId="right" type="monotone" dataKey="dte" stroke="#3B82F6" strokeWidth={2} strokeDasharray="5 5" dot={false} name="Days To Expiry" />
             </LineChart>
           </ResponsiveContainer>
         ) : (
           <div className="h-full w-full flex items-center justify-center font-mono text-white/30 border border-white/5 border-dashed rounded-lg">
             AWAITING OPTION CHAIN DATA...
           </div>
         )}
      </div>

    </div>
  );
}
