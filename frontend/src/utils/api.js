export function getApiUrl() {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  }

  // 1. Check local storage override first
  const stored = localStorage.getItem('API_BASE_URL');
  if (stored && !stored.includes('localhost') && !stored.includes('127.0.0.1')) return stored;

  // 2. Check environment variables
  const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL;
  if (envUrl) return envUrl;

  // 3. Fallback automatically based on hostname
  const host = window.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1') {
    return "http://localhost:8000";
  } else if (host.startsWith('192.168.') || host.startsWith('10.')) {
    return `http://${host}:8000`;
  }

  return "https://create-bluish-excavate.ngrok-free.dev";
}

export function getThetaGangApiUrl() {
  if (typeof window === 'undefined') {
    return process.env.NEXT_PUBLIC_THETAGANG_API_URL || "http://127.0.0.1:8080";
  }

  const stored = localStorage.getItem('THETAGANG_API_URL');
  if (stored && !stored.includes('localhost') && !stored.includes('127.0.0.1')) return stored;

  const envUrl = process.env.NEXT_PUBLIC_THETAGANG_API_URL;
  if (envUrl) return envUrl;

  const host = window.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1') {
    return "http://localhost:8080";
  } else if (host.startsWith('192.168.') || host.startsWith('10.')) {
    return `http://${host}:8080`;
  }

  return "http://76.13.242.106:8080";
}

