# SENTINEL-X V2 — Time-Series Geopolitical Alpha Engine

## Architecture

```
sentinel-x/
├── backend/                  # Python FastAPI
│   ├── main.py               # App entry point + APScheduler
│   ├── config.py             # Pydantic settings
│   ├── models/               # Pydantic data models
│   │   ├── signal.py         # GeopoliticalSignal, ActorBloc, SignalSeverity
│   │   ├── escalation.py     # LearnedHandComponents, EscalationResult
│   │   └── asset.py          # AssetImpact, FinancialPrediction
│   ├── scrapers/
│   │   ├── semantic_filter.py # Token-saving keyword filter (4 severity tiers)
│   │   ├── realtime.py        # MODE A: 60-second RSS polling
│   │   └── historical.py      # MODE B: 180-day Playwright back-crawl
│   ├── engines/
│   │   ├── learned_hand.py    # B < P*L formula engine
│   │   ├── comparative_fault.py # G7 vs BRICS fault allocation
│   │   └── asset_mapper.py    # Short/Mid/Long-term asset impact
│   ├── services/
│   │   ├── claude_service.py  # Claude claude-sonnet-4-6 + prompt caching
│   │   └── vector_summary.py  # Token-efficient signal compression
│   ├── api/
│   │   ├── routes.py          # REST API endpoints
│   │   └── websocket.py       # Real-time WS broadcast
│   └── db/
│       └── database.py        # Async SQLAlchemy + SQLite/PostgreSQL
└── frontend/                  # Next.js (shared with main app)
    ├── pages/sentinel.js      # War-Room Dashboard
    ├── components/sentinel/
    │   ├── EscalationMeter.jsx # SVG gauge + B<PL panel
    │   ├── TrendGraph.jsx      # 6-month Recharts line chart
    │   └── AssetPredictor.jsx  # Asset impact table
    └── utils/sentinelApi.js    # API + WebSocket client
```

## Running

```bash
# Backend
cd sentinel-x/backend
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # Add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000

# Frontend (existing Next.js)
cd frontend
npm install
npm run dev
# Visit http://localhost:3000/sentinel
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sentinel/status` | System status |
| GET | `/api/sentinel/signals` | Signal feed (with filters) |
| GET | `/api/sentinel/escalation` | Live B<PL escalation result |
| GET | `/api/sentinel/trend` | 6-month bloc trend data |
| GET | `/api/sentinel/assets` | Asset movement predictions |
| POST | `/api/sentinel/analysis` | Claude-powered full analysis |
| GET | `/api/sentinel/history` | Escalation index history |
| POST | `/api/sentinel/crawl/start` | Trigger 180-day back-crawl |
| WS | `/ws/sentinel` | Real-time escalation stream |

## Learned Hand Formula

```
B < P × L  →  Breach of Stability Duty

B = Economic/diplomatic cost of restraint (USD bn, 6-month window)
P = Probability of conflict (signal density ratio: realtime vs 180d baseline)
L = Magnitude of special damages (severity-weighted loss estimate, USD bn)
```

## Prompt Caching Strategy

Three-tier caching to minimize Claude API costs:
1. **System prompt** (ephemeral) — cached per session
2. **180-day historical baseline summary** (ephemeral) — cached after crawl
3. **Real-time signal window** — not cached (changes each 60s cycle)

Typical cache hit rate: ~75% token reduction on repeat analysis calls.
