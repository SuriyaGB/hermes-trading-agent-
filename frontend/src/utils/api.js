export function getApiUrl() {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "https://create-bluish-excavate.ngrok-free.dev";
  }
  
  // 1. Check local storage override first
  const stored = localStorage.getItem('API_BASE_URL');
  if (stored) return stored;
  
  // 2. Check environment variables
  const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) return envUrl;
  
  // 3. Fallback automatically based on hostname
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return "http://127.0.0.1:8000";
  }
  
  return "https://create-bluish-excavate.ngrok-free.dev";
}
