"use client";
import { useEffect, useState } from 'react';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, BarChart2, Activity } from 'lucide-react';

export default function IncomeTracker() {
  const [data, setData] = useState([]);
  const [chartType, setChartType] = useState('Area');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL ;
        const res = await fetch(`${apiUrl}/api/income_history`);
        const json = await res.json();
        
        // Format the dynamically reconstructed account balance data
        const formattedData = json.map(point => {
          const d = new Date(point.timestamp);
          return {
            time: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }), // For X-axis (e.g. "May 7")
            fullTime: d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute:'2-digit' }), // For Tooltip
            balance: point.balance
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
      // Find the fullTime string from the active payload payload[0].payload
      const fullTime = payload[0].payload.fullTime;
      return (
        <div className="bg-black/90 border border-white/20 p-4 rounded-lg shadow-2xl backdrop-blur-md">
          <p className="text-white/70 text-xs font-mono mb-3 pb-2 border-b border-white/10">{fullTime}</p>
          <p className="text-xl font-light text-cyber-green">
            ${payload[0].value.toLocaleString('en-US', {minimumFractionDigits: 2})}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* Header */}
      <div className="flex justify-between items-end border-b border-white/10 pb-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight">Income Tracker</h1>
          <p className="text-white/50 mt-2 font-mono text-sm flex items-center tracking-widest">
            <TrendingUp size={14} className="text-cyber-green mr-2" />
            LIVE ACCOUNT BALANCE GROWTH
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
                   <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                     <stop offset="5%" stopColor="#00E676" stopOpacity={0.4}/>
                     <stop offset="95%" stopColor="#00E676" stopOpacity={0.01}/>
                   </linearGradient>
                 </defs>
                 <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                 <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
                 <YAxis stroke="rgba(255,255,255,0.3)" tick={{fill: '#00E676', fontSize: 12, fontFamily: 'monospace'}} domain={['dataMin - 100', 'dataMax + 100']} tickFormatter={(value) => `$${value.toLocaleString()}`} />
                 <Tooltip content={<CustomTooltip />} />
                 <Area type="stepAfter" dataKey="balance" stroke="#00E676" fillOpacity={1} fill="url(#colorBalance)" strokeWidth={3} name="Account Balance" />
               </AreaChart>
             ) : chartType === 'Line' ? (
               <LineChart data={data} margin={{ top: 20, right: 30, left: 40, bottom: 0 }}>
                 <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                 <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
                 <YAxis stroke="rgba(255,255,255,0.3)" tick={{fill: '#00E676', fontSize: 12, fontFamily: 'monospace'}} domain={['dataMin - 100', 'dataMax + 100']} tickFormatter={(value) => `$${value.toLocaleString()}`} />
                 <Tooltip content={<CustomTooltip />} />
                 <Line type="stepAfter" dataKey="balance" stroke="#00E676" strokeWidth={4} dot={false} name="Account Balance" />
               </LineChart>
             ) : (
               <BarChart data={data} margin={{ top: 20, right: 30, left: 40, bottom: 0 }}>
                 <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                 <XAxis dataKey="time" stroke="rgba(255,255,255,0.3)" tick={{fill: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'monospace'}} />
                 <YAxis stroke="rgba(255,255,255,0.3)" tick={{fill: '#00E676', fontSize: 12, fontFamily: 'monospace'}} domain={['dataMin - 100', 'dataMax + 100']} tickFormatter={(value) => `$${value.toLocaleString()}`} />
                 <Tooltip content={<CustomTooltip />} />
                 <Bar dataKey="balance" fill="#00E676" radius={[4, 4, 0, 0]} name="Account Balance" />
               </BarChart>
             )}
           </ResponsiveContainer>
         ) : (
           <div className="h-full w-full flex items-center justify-center font-mono text-white/30 border border-white/5 border-dashed rounded-lg">
             LOADING INCOME DATA...
           </div>
         )}
      </div>
    </div>
  );
}
