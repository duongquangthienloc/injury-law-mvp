const BASE = process.env.NEXT_PUBLIC_SENTINEL_API || 'http://localhost:8000';

export async function fetchEscalation(params = {}) {
  const q = new URLSearchParams({ realtime_days: 7, historical_days: 180, ...params });
  const res = await fetch(`${BASE}/api/sentinel/escalation?${q}`);
  if (!res.ok) throw new Error(`Escalation fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchTrend(bloc = 'G7', bucketDays = 7, totalDays = 180) {
  const q = new URLSearchParams({ bloc, bucket_days: bucketDays, total_days: totalDays });
  const res = await fetch(`${BASE}/api/sentinel/trend?${q}`);
  if (!res.ok) throw new Error(`Trend fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchAssets() {
  const res = await fetch(`${BASE}/api/sentinel/assets`);
  if (!res.ok) throw new Error(`Assets fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchSignals(params = {}) {
  const q = new URLSearchParams({ days: 7, limit: 50, ...params });
  const res = await fetch(`${BASE}/api/sentinel/signals?${q}`);
  if (!res.ok) throw new Error(`Signals fetch failed: ${res.status}`);
  return res.json();
}

export async function runAnalysis() {
  const res = await fetch(`${BASE}/api/sentinel/analysis`, { method: 'POST' });
  if (!res.ok) throw new Error(`Analysis failed: ${res.status}`);
  return res.json();
}

export async function startCrawl() {
  const res = await fetch(`${BASE}/api/sentinel/crawl/start`, { method: 'POST' });
  if (!res.ok) throw new Error(`Crawl start failed: ${res.status}`);
  return res.json();
}

export function createWebSocket(onMessage, onOpen, onClose) {
  const wsBase = BASE.replace(/^http/, 'ws');
  const ws = new WebSocket(`${wsBase}/ws/sentinel`);

  ws.onopen = () => {
    if (onOpen) onOpen();
    // Send periodic pings to keep alive
    ws._pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 25000);
  };

  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (onMessage) onMessage(data);
    } catch (_) {}
  };

  ws.onclose = () => {
    clearInterval(ws._pingInterval);
    if (onClose) onClose();
  };

  ws.onerror = (err) => console.error('[SENTINEL-X WS]', err);

  return ws;
}
