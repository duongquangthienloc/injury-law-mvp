/**
 * TrendGraph — Component 2
 * 6-Month Intent vs Action comparison across G7 and BRICS blocs.
 * Intent = diplomatic language signals (LOW/MEDIUM severity)
 * Action = military/economic moves (HIGH/CRITICAL severity)
 */
import { useEffect, useState, useCallback } from 'react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts';
import { fetchTrend } from '../../utils/sentinelApi';

const BLOC_COLORS = {
  G7:    { intent: '#3b82f6', action: '#ef4444' },
  BRICS: { intent: '#a78bfa', action: '#f97316' },
};

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#161b22', border: '1px solid #30363d',
      borderRadius: 6, padding: '10px 14px', fontSize: 11,
    }}>
      <div style={{ color: '#8b949e', marginBottom: 6 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color, marginBottom: 2 }}>
          {p.name}: <strong>{p.value?.toFixed(2)}</strong>
        </div>
      ))}
    </div>
  );
}

export default function TrendGraph({ bloc = 'G7', comparisonBloc = 'BRICS' }) {
  const [data, setData] = useState([]);
  const [compData, setCompData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeBloc, setActiveBloc] = useState(bloc);

  const loadTrend = useCallback(async (selectedBloc) => {
    setLoading(true);
    try {
      const [main, comp] = await Promise.all([
        fetchTrend(selectedBloc, 7, 180),
        fetchTrend(comparisonBloc, 7, 180),
      ]);

      // Merge by date
      const dateMap = {};
      (main.trend || []).forEach((d) => {
        dateMap[d.date] = {
          date: d.date,
          [`${selectedBloc}_intent`]: d.intent,
          [`${selectedBloc}_action`]: d.action,
        };
      });
      (comp.trend || []).forEach((d) => {
        if (!dateMap[d.date]) dateMap[d.date] = { date: d.date };
        dateMap[d.date][`${comparisonBloc}_intent`] = d.intent;
        dateMap[d.date][`${comparisonBloc}_action`] = d.action;
      });

      const merged = Object.values(dateMap).sort((a, b) =>
        a.date.localeCompare(b.date)
      );
      setData(merged);
    } catch (e) {
      console.error('TrendGraph load error:', e);
    } finally {
      setLoading(false);
    }
  }, [comparisonBloc]);

  useEffect(() => { loadTrend(activeBloc); }, [activeBloc, loadTrend]);

  const mainColors = BLOC_COLORS[activeBloc] || BLOC_COLORS.G7;
  const compColors = BLOC_COLORS[comparisonBloc] || BLOC_COLORS.BRICS;

  return (
    <div style={{
      background: '#0d1117', border: '1px solid #21262d',
      borderRadius: 12, padding: 20,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <div style={{ color: '#c9d1d9', fontSize: 14, fontWeight: 700 }}>
            6-Month Intent vs. Action
          </div>
          <div style={{ color: '#8b949e', fontSize: 11, marginTop: 2 }}>
            Signal density comparison — Breach of Stability Duty baseline
          </div>
        </div>
        {/* Bloc selector */}
        <div style={{ display: 'flex', gap: 6 }}>
          {Object.keys(BLOC_COLORS).filter(b => b !== comparisonBloc).map((b) => (
            <button key={b} onClick={() => setActiveBloc(b)} style={{
              padding: '4px 12px', borderRadius: 4, fontSize: 11,
              cursor: 'pointer', border: '1px solid',
              borderColor: activeBloc === b ? BLOC_COLORS[b].intent : '#30363d',
              background: activeBloc === b ? BLOC_COLORS[b].intent + '22' : 'transparent',
              color: activeBloc === b ? BLOC_COLORS[b].intent : '#8b949e',
            }}>
              {b}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#8b949e', fontSize: 12 }}>
          Loading 180-day trend data...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
            <XAxis
              dataKey="date"
              tick={{ fill: '#8b949e', fontSize: 9 }}
              tickFormatter={(d) => d.slice(5)}
              interval="preserveStartEnd"
            />
            <YAxis tick={{ fill: '#8b949e', fontSize: 9 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              formatter={(v) => <span style={{ color: '#8b949e', fontSize: 10 }}>{v}</span>}
            />
            {/* Main bloc */}
            <Line
              type="monotone"
              dataKey={`${activeBloc}_intent`}
              name={`${activeBloc} Intent`}
              stroke={mainColors.intent}
              strokeWidth={2}
              dot={false}
              strokeDasharray="4 2"
            />
            <Line
              type="monotone"
              dataKey={`${activeBloc}_action`}
              name={`${activeBloc} Action`}
              stroke={mainColors.action}
              strokeWidth={2.5}
              dot={false}
            />
            {/* Comparison bloc */}
            <Line
              type="monotone"
              dataKey={`${comparisonBloc}_intent`}
              name={`${comparisonBloc} Intent`}
              stroke={compColors.intent}
              strokeWidth={2}
              dot={false}
              strokeDasharray="4 2"
              opacity={0.7}
            />
            <Line
              type="monotone"
              dataKey={`${comparisonBloc}_action`}
              name={`${comparisonBloc} Action`}
              stroke={compColors.action}
              strokeWidth={2.5}
              dot={false}
              opacity={0.7}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {/* Legend explanation */}
      <div style={{ display: 'flex', gap: 20, marginTop: 10, flexWrap: 'wrap' }}>
        {[
          { color: '#8b949e', dash: true, label: 'Dashed = Intent (diplomatic language)' },
          { color: '#8b949e', dash: false, label: 'Solid = Action (military / economic moves)' },
        ].map(({ color, dash, label }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: '#8b949e' }}>
            <svg width={24} height={4}>
              <line x1={0} y1={2} x2={24} y2={2} stroke={color}
                strokeWidth={2} strokeDasharray={dash ? '4 2' : undefined} />
            </svg>
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
