/**
 * AssetPredictor — Component 3
 * Asset Movement Predictor based on "Future Losses" logic.
 * Shows predicted financial impact across Short / Mid / Long time horizons.
 */
import { useEffect, useState } from 'react';
import { fetchAssets } from '../../utils/sentinelApi';

const HORIZON_LABEL = { SHORT: '0–7 Days', MID: '1–3 Months', LONG: '6+ Months' };
const HORIZON_ORDER = ['SHORT', 'MID', 'LONG'];

const ASSET_ICONS = {
  FOREX:                '💱',
  EQUITY_VOLATILITY:    '📊',
  GOLD:                 '🥇',
  ENERGY_FUTURES:       '⛽',
  SEMICONDUCTORS:       '🔲',
  FX_RESERVES:          '🏦',
  INFRASTRUCTURE_BONDS: '🏗️',
};

const DIR_CONFIG = {
  SPIKE:   { color: '#ef4444', bg: '#2d1010', arrow: '⬆⬆', label: 'SPIKE'   },
  RISE:    { color: '#f97316', bg: '#231808', arrow: '⬆',   label: 'RISE'    },
  NEUTRAL: { color: '#8b949e', bg: '#161b22', arrow: '→',   label: 'FLAT'    },
  FALL:    { color: '#3b82f6', bg: '#0d1829', arrow: '⬇',   label: 'FALL'    },
  CRASH:   { color: '#a78bfa', bg: '#1a1230', arrow: '⬇⬇', label: 'CRASH'   },
};

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100);
  const color = pct > 70 ? '#22c55e' : pct > 45 ? '#eab308' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 4, background: '#21262d', borderRadius: 2 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ color, fontSize: 9, minWidth: 28 }}>{pct}%</span>
    </div>
  );
}

function AssetRow({ impact }) {
  const dir = DIR_CONFIG[impact.direction] || DIR_CONFIG.NEUTRAL;
  const mag = Math.abs(impact.magnitude_pct);
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '28px 1fr 80px 70px 80px',
      gap: 8,
      alignItems: 'center',
      padding: '7px 10px',
      borderRadius: 6,
      background: dir.bg,
      marginBottom: 4,
    }}>
      {/* Icon */}
      <span style={{ fontSize: 14 }}>{ASSET_ICONS[impact.asset_class] || '📈'}</span>
      {/* Asset + driver */}
      <div>
        <div style={{ color: '#c9d1d9', fontSize: 11, fontWeight: 600 }}>
          {impact.asset_class.replace(/_/g, ' ')}
        </div>
        <div style={{ color: '#8b949e', fontSize: 9, marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 180 }}>
          {impact.driver}
        </div>
      </div>
      {/* Direction badge */}
      <div style={{
        textAlign: 'center', padding: '2px 6px', borderRadius: 4,
        background: dir.color + '22', color: dir.color,
        fontSize: 10, fontWeight: 700,
      }}>
        {dir.arrow} {dir.label}
      </div>
      {/* Magnitude */}
      <div style={{ textAlign: 'right', color: dir.color, fontSize: 12, fontWeight: 700, fontFamily: 'monospace' }}>
        {mag > 0 ? `~${mag.toFixed(1)}%` : '-'}
      </div>
      {/* Confidence */}
      <ConfidenceBar value={impact.confidence} />
    </div>
  );
}

function ScoreGauge({ label, value, color }) {
  return (
    <div style={{ flex: 1, background: '#161b22', border: '1px solid #21262d', borderRadius: 8, padding: '10px 14px' }}>
      <div style={{ color: '#8b949e', fontSize: 9, marginBottom: 6, letterSpacing: 1 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ flex: 1, height: 6, background: '#21262d', borderRadius: 3 }}>
          <div style={{ width: `${value}%`, height: '100%', background: color, borderRadius: 3,
            transition: 'width 0.8s ease' }} />
        </div>
        <span style={{ color, fontSize: 18, fontWeight: 800, fontFamily: 'monospace', minWidth: 42 }}>
          {value?.toFixed(0)}
        </span>
      </div>
    </div>
  );
}

export default function AssetPredictor() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const d = await fetchAssets();
      setData(d);
      setLastUpdated(new Date());
    } catch (e) {
      console.error('AssetPredictor load error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 120_000); // refresh every 2 min
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 12, padding: 20, minHeight: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ color: '#8b949e', fontSize: 12 }}>Computing asset impact predictions...</span>
      </div>
    );
  }

  const horizonMap = { SHORT: data?.short_term || [], MID: data?.mid_term || [], LONG: data?.long_term || [] };

  return (
    <div style={{ background: '#0d1117', border: '1px solid #21262d', borderRadius: 12, padding: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        <div>
          <div style={{ color: '#c9d1d9', fontSize: 14, fontWeight: 700 }}>Asset Movement Predictor</div>
          <div style={{ color: '#8b949e', fontSize: 11, marginTop: 2 }}>
            Future Losses model — Special Damages impact across time horizons
          </div>
        </div>
        {lastUpdated && (
          <span style={{ color: '#8b949e', fontSize: 9 }}>
            Updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Macro scores */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <ScoreGauge
          label="DE-DOLLARIZATION TREND"
          value={data?.de_dollarization_score ?? 0}
          color="#a78bfa"
        />
        <ScoreGauge
          label="ENERGY DISRUPTION RISK"
          value={data?.energy_disruption_score ?? 0}
          color="#f97316"
        />
      </div>

      {/* Asset tables by horizon */}
      {HORIZON_ORDER.map((horizon) => {
        const impacts = horizonMap[horizon];
        if (!impacts?.length) return null;
        return (
          <div key={horizon} style={{ marginBottom: 14 }}>
            <div style={{
              color: '#8b949e', fontSize: 10, marginBottom: 6,
              letterSpacing: 2, textTransform: 'uppercase',
              borderBottom: '1px solid #21262d', paddingBottom: 4,
            }}>
              {HORIZON_LABEL[horizon]}
            </div>
            {impacts.map((impact, i) => (
              <AssetRow key={i} impact={impact} />
            ))}
          </div>
        );
      })}

      {/* Refresh */}
      <button onClick={load} style={{
        marginTop: 6, width: '100%', padding: '6px 0',
        background: '#21262d', border: '1px solid #30363d',
        borderRadius: 6, color: '#8b949e', fontSize: 11, cursor: 'pointer',
      }}>
        ↻ Refresh Predictions
      </button>
    </div>
  );
}
