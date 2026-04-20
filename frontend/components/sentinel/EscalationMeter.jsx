/**
 * EscalationMeter — Component 1
 * Visualizes the Learned Hand B < P×L formula as an animated circular gauge.
 * Real-time updates via WebSocket.
 */
import { useEffect, useRef, useState } from 'react';

const TIER_CONFIG = {
  STABLE:   { color: '#22c55e', bg: '#052e16', label: 'STABLE',   glow: '0 0 20px #22c55e55' },
  ELEVATED: { color: '#eab308', bg: '#1c1a06', label: 'ELEVATED', glow: '0 0 20px #eab30855' },
  CRITICAL: { color: '#f97316', bg: '#1c0a06', label: 'CRITICAL', glow: '0 0 20px #f9731655' },
  BREACH:   { color: '#ef4444', bg: '#1c0606', label: '⚠ BREACH', glow: '0 0 30px #ef444488' },
};

function Arc({ cx, cy, r, startAngle, endAngle, stroke, strokeWidth = 12 }) {
  const toRad = (d) => (d * Math.PI) / 180;
  const x1 = cx + r * Math.cos(toRad(startAngle));
  const y1 = cy + r * Math.sin(toRad(startAngle));
  const x2 = cx + r * Math.cos(toRad(endAngle));
  const y2 = cy + r * Math.sin(toRad(endAngle));
  const large = endAngle - startAngle > 180 ? 1 : 0;
  return (
    <path
      d={`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`}
      fill="none"
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
    />
  );
}

export default function EscalationMeter({ data, isLive = false }) {
  const [animated, setAnimated] = useState(0);
  const animRef = useRef(null);
  const targetRef = useRef(0);

  const index = data?.escalation_index ?? 0;
  const tier  = data?.risk_tier ?? 'STABLE';
  const b     = data?.components?.B ?? 0;
  const p     = data?.components?.P ?? 0;
  const l     = data?.components?.L ?? 0;
  const pl    = data?.components?.PL ?? 0;
  const breached = data?.threshold_breached ?? false;

  const cfg = TIER_CONFIG[tier] || TIER_CONFIG.STABLE;

  // Smooth animation toward target index
  useEffect(() => {
    targetRef.current = index;
    const step = () => {
      setAnimated((prev) => {
        const diff = targetRef.current - prev;
        if (Math.abs(diff) < 0.2) return targetRef.current;
        return prev + diff * 0.08;
      });
      animRef.current = requestAnimationFrame(step);
    };
    animRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animRef.current);
  }, [index]);

  // Gauge: 220° arc from -200° to 20° (bottom-left to bottom-right)
  const START_DEG = 145;
  const SWEEP = 250;
  const fill_deg = START_DEG + (animated / 100) * SWEEP;
  const cx = 110, cy = 110, r = 80;

  return (
    <div style={{
      background: '#0d1117',
      border: `1px solid ${cfg.color}44`,
      borderRadius: 12,
      padding: 20,
      boxShadow: cfg.glow,
      minWidth: 260,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ color: '#8b949e', fontSize: 11, letterSpacing: 2, textTransform: 'uppercase' }}>
          Escalation Index
        </span>
        <span style={{
          fontSize: 10, padding: '2px 8px', borderRadius: 4,
          background: cfg.color + '22', color: cfg.color, fontWeight: 700,
          letterSpacing: 1,
        }}>
          {isLive ? '● LIVE' : '○ CACHED'}
        </span>
      </div>

      {/* SVG Gauge */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <svg width={220} height={160} viewBox="0 0 220 160">
          {/* Background arc */}
          <Arc cx={cx} cy={cy} r={r} startAngle={START_DEG} endAngle={START_DEG + SWEEP}
            stroke="#1e2430" strokeWidth={14} />
          {/* Colored fill arc */}
          {animated > 0.5 && (
            <Arc cx={cx} cy={cy} r={r} startAngle={START_DEG} endAngle={fill_deg}
              stroke={cfg.color} strokeWidth={14} />
          )}
          {/* Center display */}
          <text x={cx} y={cy - 8} textAnchor="middle" fill={cfg.color}
            style={{ fontSize: 32, fontWeight: 800, fontFamily: 'monospace' }}>
            {Math.round(animated)}
          </text>
          <text x={cx} y={cy + 14} textAnchor="middle" fill={cfg.color}
            style={{ fontSize: 11, letterSpacing: 2, fontFamily: 'monospace' }}>
            {cfg.label}
          </text>
          {/* Scale labels */}
          {[0, 25, 50, 75, 100].map((val) => {
            const angle = START_DEG + (val / 100) * SWEEP;
            const rad = (angle * Math.PI) / 180;
            const tx = cx + (r + 20) * Math.cos(rad);
            const ty = cy + (r + 20) * Math.sin(rad);
            return (
              <text key={val} x={tx} y={ty} textAnchor="middle" fill="#444d56"
                style={{ fontSize: 9 }}>{val}</text>
            );
          })}
        </svg>
      </div>

      {/* B < P×L Panel */}
      <div style={{
        background: breached ? '#ef444411' : '#ffffff06',
        border: `1px solid ${breached ? '#ef4444' : '#30363d'}`,
        borderRadius: 8, padding: '10px 14px', marginTop: 4,
      }}>
        <div style={{ color: '#8b949e', fontSize: 10, marginBottom: 6, letterSpacing: 1 }}>
          LEARNED HAND  B {'<'} P×L
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
          {[
            { label: 'B (Restraint)', val: `$${b.toFixed(1)}bn`, sub: 'Cost of de-escalation' },
            { label: 'P (Probability)', val: `${(p * 100).toFixed(1)}%`, sub: 'Conflict likelihood' },
            { label: 'L (Loss)', val: `$${l.toFixed(0)}bn`, sub: 'Special damages' },
          ].map(({ label, val, sub }) => (
            <div key={label} style={{ textAlign: 'center' }}>
              <div style={{ color: cfg.color, fontSize: 15, fontWeight: 700, fontFamily: 'monospace' }}>
                {val}
              </div>
              <div style={{ color: '#8b949e', fontSize: 9 }}>{label}</div>
            </div>
          ))}
        </div>
        <div style={{
          marginTop: 8, textAlign: 'center',
          color: breached ? '#ef4444' : '#22c55e',
          fontSize: 11, fontWeight: 700, letterSpacing: 1,
        }}>
          {breached
            ? `⚠ BREACH — P×L ($${pl.toFixed(1)}bn) EXCEEDS B ($${b.toFixed(1)}bn)`
            : `✓ STABLE — B ($${b.toFixed(1)}bn) covers P×L ($${pl.toFixed(1)}bn)`}
        </div>
      </div>

      {/* Dominant signals */}
      {data?.dominant_signals?.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ color: '#8b949e', fontSize: 10, marginBottom: 4, letterSpacing: 1 }}>
            DOMINANT SIGNALS
          </div>
          {data.dominant_signals.slice(0, 2).map((s, i) => (
            <div key={i} style={{
              color: '#c9d1d9', fontSize: 10, padding: '4px 0',
              borderBottom: '1px solid #21262d',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              › {s}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
