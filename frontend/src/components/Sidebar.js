"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, TrendingUp, History, LineChart, Activity, Settings, X, Check, Link2, GitCompare } from 'lucide-react';
import { useState, useEffect } from 'react';

import { getApiUrl, getThetaGangApiUrl } from '../utils/api';

export default function Sidebar() {
  const pathname = usePathname();
  const [showModal, setShowModal] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [thetaUrlInput, setThetaUrlInput] = useState('');
  const [savedUrl, setSavedUrl] = useState('');
  const [savedThetaUrl, setSavedThetaUrl] = useState('');

  useEffect(() => {
    const resolvedUrl = getApiUrl();
    const resolvedThetaUrl = getThetaGangApiUrl();
    const stored = localStorage.getItem('API_BASE_URL') || '';
    const storedTheta = localStorage.getItem('THETAGANG_API_URL') || '';
    setSavedUrl(resolvedUrl);
    setSavedThetaUrl(resolvedThetaUrl);
    setUrlInput(stored);
    setThetaUrlInput(storedTheta);
  }, []);

  const links = [
    { href: '/', icon: LayoutDashboard, label: 'Command Centre' },
    { href: '/comparison', icon: GitCompare, label: 'Agent Comparison' },
    { href: '/income', icon: TrendingUp, label: 'Income Tracker' },
    { href: '/history', icon: History, label: 'Pulse History' },
    { href: '/market', icon: LineChart, label: 'Market View' },
    { href: '/health', icon: Activity, label: 'Bot Health' },
  ];

  const handleSave = () => {
    const cleaned = urlInput.trim().replace(/\/$/, '');
    const cleanedTheta = thetaUrlInput.trim().replace(/\/$/, '');
    localStorage.setItem('API_BASE_URL', cleaned);
    localStorage.setItem('THETAGANG_API_URL', cleanedTheta);
    setSavedUrl(cleaned);
    setSavedThetaUrl(cleanedTheta);
    setShowModal(false);
    window.location.reload();
  };

  const handleOpen = () => {
    const stored = localStorage.getItem('API_BASE_URL') || '';
    const storedTheta = localStorage.getItem('THETAGANG_API_URL') || '';
    setUrlInput(stored);
    setThetaUrlInput(storedTheta);
    setShowModal(true);
  };

  return (
    <>
      {/* Cloudflare URL Modal */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowModal(false); }}
        >
          <div
            className="w-full max-w-md mx-4 rounded-2xl border p-6 shadow-2xl"
            style={{
              background: 'linear-gradient(135deg, #0d1117 0%, #161b22 100%)',
              borderColor: 'rgba(255,255,255,0.1)',
              boxShadow: '0 0 40px rgba(0,230,118,0.08), 0 25px 50px rgba(0,0,0,0.5)'
            }}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center space-x-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: 'rgba(0,230,118,0.1)', border: '1px solid rgba(0,230,118,0.3)' }}>
                  <Link2 size={18} style={{ color: '#00E676' }} />
                </div>
                <div>
                  <h2 className="text-white font-semibold text-base">Backend API URL</h2>
                  <p className="text-xs font-mono" style={{ color: 'rgba(255,255,255,0.4)' }}>Cloudflare Tunnel / VPS</p>
                </div>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="rounded-lg p-1.5 transition-colors"
                style={{ color: 'rgba(255,255,255,0.4)' }}
                onMouseEnter={e => e.currentTarget.style.color = '#fff'}
                onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.4)'}
              >
                <X size={18} />
              </button>
            </div>

            {/* Inputs */}
            <div className="space-y-4 mb-5">
              <div>
                <label className="block text-xs font-mono mb-2" style={{ color: 'rgba(255,255,255,0.5)', letterSpacing: '0.1em' }}>
                  HERMES API BASE URL
                </label>
                <input
                  type="text"
                  value={urlInput}
                  onChange={e => setUrlInput(e.target.value)}
                  placeholder="https://xxxx-xxxx.trycloudflare.com"
                  className="w-full rounded-lg px-4 py-2.5 text-sm font-mono outline-none transition-all"
                  style={{
                    background: 'rgba(0,0,0,0.5)',
                    border: '1px solid rgba(0,230,118,0.3)',
                    color: '#fff',
                    caretColor: '#00E676'
                  }}
                  onFocus={e => e.target.style.borderColor = 'rgba(0,230,118,0.6)'}
                  onBlur={e => e.target.style.borderColor = 'rgba(0,230,118,0.3)'}
                />
              </div>

              <div>
                <label className="block text-xs font-mono mb-2" style={{ color: 'rgba(255,255,255,0.5)', letterSpacing: '0.1em' }}>
                  THETAGANG API BASE URL
                </label>
                <input
                  type="text"
                  value={thetaUrlInput}
                  onChange={e => setThetaUrlInput(e.target.value)}
                  placeholder="http://127.0.0.1:8080 or https://..."
                  className="w-full rounded-lg px-4 py-2.5 text-sm font-mono outline-none transition-all"
                  style={{
                    background: 'rgba(0,0,0,0.5)',
                    border: '1px solid rgba(0,230,118,0.3)',
                    color: '#fff',
                    caretColor: '#00E676'
                  }}
                  onFocus={e => e.target.style.borderColor = 'rgba(0,230,118,0.6)'}
                  onBlur={e => e.target.style.borderColor = 'rgba(0,230,118,0.3)'}
                />
              </div>
            </div>
            <p className="text-xs mb-5" style={{ color: 'rgba(255,255,255,0.3)', fontFamily: 'monospace' }}>
              No trailing slash. Saved in browser localStorage.
            </p>

            {/* Buttons */}
            <div className="flex space-x-3">
              <button
                onClick={() => setShowModal(false)}
                className="flex-1 py-2.5 rounded-lg text-sm font-medium transition-all"
                style={{ background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.6)', border: '1px solid rgba(255,255,255,0.08)' }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.1)'; e.currentTarget.style.color = '#fff'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.color = 'rgba(255,255,255,0.6)'; }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="flex-1 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center space-x-2 transition-all"
                style={{ background: 'linear-gradient(135deg, #00E676, #00b894)', color: '#000', boxShadow: '0 4px 15px rgba(0,230,118,0.3)' }}
                onMouseEnter={e => e.currentTarget.style.boxShadow = '0 4px 20px rgba(0,230,118,0.5)'}
                onMouseLeave={e => e.currentTarget.style.boxShadow = '0 4px 15px rgba(0,230,118,0.3)'}
              >
                <Check size={16} />
                <span>Save & Reload</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sidebar */}
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
        
        <div className="mt-auto px-2 py-4 border-t border-white/5 space-y-2">
          {/* Active URL badges */}
          {savedUrl && (
            <div className="px-2 py-1.5 rounded-lg flex items-center space-x-2 overflow-hidden" style={{ background: 'rgba(0,230,118,0.05)', border: '1px solid rgba(0,230,118,0.1)' }}>
              <div className="w-1.5 h-1.5 rounded-full animate-pulse flex-shrink-0" style={{ background: '#00E676' }}></div>
              <span className="text-[10px] font-mono truncate text-white/40">
                H: <span style={{ color: 'rgba(0,230,118,0.7)' }}>{savedUrl.replace('https://', '').replace('http://', '')}</span>
              </span>
            </div>
          )}
          {savedThetaUrl && (
            <div className="px-2 py-1.5 rounded-lg flex items-center space-x-2 overflow-hidden" style={{ background: 'rgba(0,230,118,0.05)', border: '1px solid rgba(0,230,118,0.1)' }}>
              <div className="w-1.5 h-1.5 rounded-full animate-pulse flex-shrink-0" style={{ background: '#00D6FF' }}></div>
              <span className="text-[10px] font-mono truncate text-white/40">
                T: <span style={{ color: 'rgba(0,214,255,0.7)' }}>{savedThetaUrl.replace('https://', '').replace('http://', '')}</span>
              </span>
            </div>
          )}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 rounded-full bg-cyber-green animate-pulse" style={{boxShadow: '0 0 8px #00E676'}}></div>
              <span className="text-xs text-white/50 font-mono">SYSTEM ONLINE</span>
            </div>
            <button 
              onClick={handleOpen} 
              className="text-white/50 hover:text-cyber-green transition-colors p-1 rounded" 
              title="Configure API URL"
            >
              <Settings size={16} />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
