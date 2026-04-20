/**
 * SENTINEL-X V2 — War-Room Dashboard
 * Main page: real-time geopolitical risk intelligence
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import Head from 'next/head';
import dynamic from 'next/dynamic';
import { createWebSocket, fetchEscalation, fetchSignals, runAnalysis, startCrawl } from '../utils/sentinelApi';

// Dynamic imports to prevent SSR issues with recharts
const EscalationMeter = dynamic(() => import('../components/sentinel/EscalationMeter'), { ssr: false });
const TrendGraph      = dynamic(() => import('../components/sentinel/TrendGraph'),      { ssr: false });
const AssetPredictor  = dynamic(() => import('../components/sentinel/AssetPredictor'),  { ssr: false });

const SEVERITY_COLORS = { 1: '#8b949e', 2: '#eab308', 3: '#f97316', 4: '#ef4444' };
const SEVERITY_LABELS = { 1: 'LOW', 2: 'MEDIUM', 3: 'HIGH', 4: 'CRITICAL' };

function AlertTicker({ alerts }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    let pos = ref.current.scrollWidth;
    const timer = setInterval(() => {
      pos -= 1;
      if (pos < -ref.current.offsetWidth) pos = ref.current.scrollWidth;
      ref.current.style.transform = `translateX(${pos}px)`;
    }, 20);
    return () => clearInterval(timer);
  }, [alerts]);

  if (!alerts?.length) return (
    <div style={{ height: 28, background: '#0d1117', borderBottom: '1px solid #21262d', display: 'flex', alignItems: 'center', paddingLeft: 12 }}>
      <span style={{ color: '#8b949e', fontSize: 10 }}>No active alerts — monitoring all feeds</span>
    </div>
  );

  return (
    <div style={{ height: 28, background: '#0d1117', borderBottom: '1px solid #21262d', overflow: 'hidden', position: 'relative' }}>
      <div ref={ref} style={{ position: 'absolute', whiteSpace: 'nowrap', top: 5 }}>
        {alerts.map((a, i) => (
          <span key={i} style={{ marginRight: 60, color: SEVERITY_COLORS[a.severity] || '#8b949e', fontSize: 10 }}>
            [{SEVERITY_LABELS[a.severity] || a.severity}] {a.actor && <strong>{a.actor}: </strong>}{a.headline}
          </span>
        ))}
      </div>
    </div>
  );
}

function SignalFeed({ signals }) {
  return (
    <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 12, padding: 16, height: '100%' }}>
      <div style={{ color: '#8b949e', fontSize: 10, letterSpacing: 2, marginBottom: 10 }}>
        LIVE SIGNAL FEED
      </div>
      <div style={{ overflowY: 'auto', maxHeight: 320 }}>
        {signals.length === 0 ? (
          <div style={{ color: '#8b949e', fontSize: 11, padding: '20px 0', textAlign: 'center' }}>
            Awaiting signals...
          </div>
        ) : signals.map((s, i) => (
          <div key={s.id || i} style={{
            padding: '7px 0',
            borderBottom: '1px solid #21262d',
            display: 'flex', gap: 8, alignItems: 'flex-start',
          }}>
            <span style={{
              fontSize: 9, padding: '2px 6px', borderRadius: 3,
              background: (SEVERITY_COLORS[s.severity] || '#8b949e') + '22',
              color: SEVERITY_COLORS[s.severity] || '#8b949e',
              minWidth: 52, textAlign: 'center', flexShrink: 0, marginTop: 1,
            }}>
              {SEVERITY_LABELS[s.severity] || s.severity}
            </span>
            <div>
              <div style={{ color: '#c9d1d9', fontSize: 10, lineHeight: 1.4 }}>
                {s.headline?.slice(0, 140)}
              </div>
              <div style={{ color: '#8b949e', fontSize: 9, marginTop: 2 }}>
                {s.actor_bloc} · {s.source} · {new Date(s.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ComparativeFaultBar({ fault }) {
  if (!fault?.allocation) return null;
  const blocs = Object.entries(fault.allocation).sort((a, b) => b[1] - a[1]);
  const COLORS = { G7: '#3b82f6', BRICS: '#f97316', NATO: '#22c55e', OTHER: '#8b949e', SCO: '#a78bfa' };

  return (
    <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 12, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ color: '#8b949e', fontSize: 10, letterSpacing: 2 }}>COMPARATIVE FAULT</span>
        {fault.primary_aggressor && (
          <span style={{ color: '#ef4444', fontSize: 10 }}>
            Primary: {fault.primary_aggressor}
          </span>
        )}
      </div>
      {/* Stacked bar */}
      <div style={{ display: 'flex', height: 14, borderRadius: 4, overflow: 'hidden', marginBottom: 10 }}>
        {blocs.map(([bloc, pct]) => (
          <div key={bloc} style={{
            width: `${pct}%`, background: COLORS[bloc] || '#8b949e',
            transition: 'width 0.8s ease',
          }} title={`${bloc}: ${pct}%`} />
        ))}
      </div>
      {/* Legend */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {blocs.map(([bloc, pct]) => (
          <div key={bloc} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: COLORS[bloc] || '#8b949e' }} />
            <span style={{ color: COLORS[bloc] || '#8b949e', fontSize: 10 }}>{bloc}: {pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SentinelDashboard() {
  const [escalation, setEscalation] = useState(null);
  const [signals, setSignals] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [crawlStatus, setCrawlStatus] = useState(null);
  const wsRef = useRef(null);

  const loadInitialData = useCallback(async () => {
    try {
      const [esc, sigs] = await Promise.all([
        fetchEscalation(),
        fetchSignals({ days: 3, limit: 30 }),
      ]);
      setEscalation(esc);
      setSignals(sigs.signals || []);
    } catch (e) {
      console.error('Initial load error:', e);
    }
  }, []);

  useEffect(() => {
    loadInitialData();

    // WebSocket for real-time updates
    const ws = createWebSocket(
      (msg) => {
        if (msg.type === 'ESCALATION_UPDATE') {
          setEscalation((prev) => ({
            ...prev,
            ...msg.data,
            components: {
              B: msg.data.b, P: msg.data.p, L: msg.data.l,
              PL: msg.data.p * msg.data.l,
            },
            threshold_breached: msg.data.b < msg.data.p * msg.data.l,
          }));
        } else if (msg.type === 'NEW_SIGNAL') {
          const sig = msg.data;
          setAlerts((prev) => [sig, ...prev].slice(0, 20));
          setSignals((prev) => [sig, ...prev].slice(0, 60));
        }
      },
      () => setWsStatus('connected'),
      () => setWsStatus('disconnected'),
    );
    wsRef.current = ws;

    // Poll escalation every 5 minutes as fallback
    const poll = setInterval(loadInitialData, 300_000);
    return () => {
      ws.close();
      clearInterval(poll);
    };
  }, [loadInitialData]);

  const handleRunAnalysis = async () => {
    setAnalysisLoading(true);
    try {
      const result = await runAnalysis();
      setAnalysisResult(result);
    } catch (e) {
      console.error('Analysis error:', e);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleStartCrawl = async () => {
    try {
      const r = await startCrawl();
      setCrawlStatus(r.message);
      setTimeout(() => setCrawlStatus(null), 8000);
    } catch (e) {
      setCrawlStatus('Crawl error: ' + e.message);
    }
  };

  const tier = escalation?.risk_tier || 'STABLE';
  const tierColor = { STABLE: '#22c55e', ELEVATED: '#eab308', CRITICAL: '#f97316', BREACH: '#ef4444' }[tier] || '#8b949e';

  return (
    <>
      <Head>
        <title>SENTINEL-X V2 — Geopolitical Alpha Engine</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div style={{ fontFamily: "'Courier New', monospace", background: '#010409', minHeight: '100vh', color: '#c9d1d9' }}>

        {/* Alert ticker */}
        <AlertTicker alerts={alerts} />

        {/* Header */}
        <div style={{
          background: '#0d1117', borderBottom: '1px solid #21262d',
          padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444', boxShadow: '0 0 8px #ef4444' }} />
              <span style={{ color: '#ef4444', fontSize: 16, fontWeight: 800, letterSpacing: 3 }}>SENTINEL-X</span>
              <span style={{ color: '#8b949e', fontSize: 11 }}>V2</span>
            </div>
            <span style={{ color: '#8b949e', fontSize: 10 }}>TIME-SERIES GEOPOLITICAL ALPHA ENGINE</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* Risk tier badge */}
            <div style={{
              padding: '4px 14px', borderRadius: 4,
              background: tierColor + '22', border: `1px solid ${tierColor}44`,
              color: tierColor, fontSize: 12, fontWeight: 700, letterSpacing: 2,
            }}>
              {tier}
            </div>
            {/* WS status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10 }}>
              <div style={{
                width: 7, height: 7, borderRadius: '50%',
                background: wsStatus === 'connected' ? '#22c55e' : '#ef4444',
                boxShadow: wsStatus === 'connected' ? '0 0 6px #22c55e' : 'none',
              }} />
              <span style={{ color: '#8b949e' }}>
                {wsStatus === 'connected' ? 'LIVE' : 'POLLING'}
              </span>
            </div>
            {/* Actions */}
            <button onClick={handleRunAnalysis} disabled={analysisLoading} style={{
              padding: '5px 14px', borderRadius: 4,
              background: analysisLoading ? '#21262d' : '#1f6feb22',
              border: '1px solid #1f6feb',
              color: analysisLoading ? '#8b949e' : '#58a6ff',
              fontSize: 10, cursor: analysisLoading ? 'default' : 'pointer',
            }}>
              {analysisLoading ? '⟳ Analyzing...' : '⚡ Run Analysis'}
            </button>
            <button onClick={handleStartCrawl} style={{
              padding: '5px 14px', borderRadius: 4,
              background: '#21262d', border: '1px solid #30363d',
              color: '#8b949e', fontSize: 10, cursor: 'pointer',
            }}>
              ⬇ Deep Crawl
            </button>
          </div>
        </div>

        {crawlStatus && (
          <div style={{ background: '#1c2128', padding: '8px 20px', fontSize: 10, color: '#58a6ff', borderBottom: '1px solid #21262d' }}>
            {crawlStatus}
          </div>
        )}

        {/* Main grid */}
        <div style={{ padding: 20, display: 'grid', gridTemplateColumns: '280px 1fr 300px', gap: 16, maxWidth: 1400, margin: '0 auto' }}>

          {/* Col 1: Escalation Meter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <EscalationMeter
              data={escalation}
              isLive={wsStatus === 'connected'}
            />
            <ComparativeFaultBar fault={escalation?.comparative_fault} />
          </div>

          {/* Col 2: Trend Graph + Asset Predictor */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <TrendGraph bloc="G7" comparisonBloc="BRICS" />
            <AssetPredictor />
          </div>

          {/* Col 3: Signal feed + Analysis */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <SignalFeed signals={signals} />

            {/* Claude strategy brief */}
            {analysisResult && (
              <div style={{
                background: '#0d1117', border: '1px solid #1f6feb44',
                borderRadius: 12, padding: 16,
              }}>
                <div style={{ color: '#58a6ff', fontSize: 10, letterSpacing: 2, marginBottom: 8 }}>
                  CLAUDE ANALYSIS
                </div>
                <div style={{
                  color: '#c9d1d9', fontSize: 10, lineHeight: 1.6,
                  maxHeight: 300, overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                }}>
                  {analysisResult.strategy_brief || analysisResult.claude_analysis?.analysis || 'No analysis available.'}
                </div>
                {analysisResult.claude_analysis?._cache_stats && (
                  <div style={{ color: '#8b949e', fontSize: 9, marginTop: 8, borderTop: '1px solid #21262d', paddingTop: 6 }}>
                    Cache: {analysisResult.claude_analysis._cache_stats.cache_read_tokens || 0} tokens read from cache |{' '}
                    {analysisResult.claude_analysis._cache_stats.input_tokens} input tokens
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div style={{
          textAlign: 'center', padding: '12px 0',
          color: '#8b949e', fontSize: 9, letterSpacing: 1,
          borderTop: '1px solid #21262d', marginTop: 10,
        }}>
          SENTINEL-X V2 · Learned Hand B&lt;P×L Engine · Claude claude-sonnet-4-6 · Real-time geopolitical alpha
        </div>
      </div>
    </>
  );
}
