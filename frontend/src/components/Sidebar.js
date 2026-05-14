"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, TrendingUp, History, LineChart, Activity, Settings } from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();

  const links = [
    { href: '/', icon: LayoutDashboard, label: 'Command Centre' },
    { href: '/income', icon: TrendingUp, label: 'Income Tracker' },
    { href: '/history', icon: History, label: 'Pulse History' },
    { href: '/market', icon: LineChart, label: 'Market View' },
    { href: '/health', icon: Activity, label: 'Bot Health' },
  ];

  const handleSettingsClick = () => {
    const currentUrl = typeof window !== 'undefined' ? localStorage.getItem('API_BASE_URL') || '' : '';
    const newUrl = window.prompt("Enter your Cloudflare Tunnel or Backend API URL:", currentUrl);
    if (newUrl !== null) {
      localStorage.setItem('API_BASE_URL', newUrl.trim().replace(/\/$/, ""));
      window.location.reload();
    }
  };

  return (
    <div className="w-64 glass-panel border-r border-white/5 flex flex-col h-screen fixed left-0 top-0 p-4 rounded-none">
      <div className="mb-8 px-2 mt-2">
        <h1 className="text-2xl font-bold tracking-wider text-white">HERMES</h1>
        <p className="text-xs text-cyber-green font-mono mt-1 tracking-widest">QUANTUM ANALYTICS</p>
      </div>
      
      <nav className="flex flex-col space-y-2 flex-grow">
        {links.map((link) => {
          const isActive = pathname === link.href;
          const Icon = link.icon;
          
          return (
            <Link 
              key={link.href}
              href={link.href} 
              className={`flex items-center space-x-3 px-3 py-3 rounded-lg transition-all duration-300 ${
                isActive 
                  ? 'bg-white/10 text-white border-l-2 border-cyber-green' 
                  : 'text-white/60 hover:text-white hover:bg-white/5 border-l-2 border-transparent'
              }`}
            >
              <Icon size={20} className={isActive ? 'text-cyber-green' : ''} />
              <span className="font-medium">{link.label}</span>
            </Link>
          );
        })}
      </nav>
      
      <div className="mt-auto px-2 py-4 border-t border-white/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 rounded-full bg-cyber-green animate-pulse" style={{boxShadow: '0 0 8px #00E676'}}></div>
            <span className="text-xs text-white/50 font-mono">SYSTEM ONLINE</span>
          </div>
          <button onClick={handleSettingsClick} className="text-white/50 hover:text-white transition-colors" title="Configure API URL">
            <Settings size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
