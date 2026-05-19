# AI Market Intelligence OS — Architecture Design
# Project: trading-engine-mvp (based on KernelLex/trading-engine)
# Target repo: https://github.com/tfthushaar/trading-engine-mvp
# Date: 2026-05-19

## Existing Foundation Audit

| Component | Strength | Production Gap |
|---|---|---|
| 6-phase pipeline | Clean sequential flow | No event-driven / real-time capability |
| DuckDB storage | Fast local analytics | Not suited for multi-user concurrent writes |
| FinBERT sentiment | Domain-accurate NLP | Batch-only, no streaming |
| OpenAI research agent | LLM hypothesis gen | Single-agent, no orchestration |
| Strategy engine (5 modules) | Template-based logic | No no-code UI, no user-owned strategies |
| Custom backtester | Functional | No Monte Carlo, no portfolio-level testing |
| SHAP explainability | Decision attribution | Not surfaced well in UI |
| React dashboard (7 panels) | Data visible | Not AI-first, no user journeys |
| FastAPI backend | Solid | Limited routes, no auth, no WebSocket |

**Core philosophy:** Preserve all 6 phases. Extend them. Add 6 new layers around them. Migrate infrastructure upward.

---

## Project Folder Structure

```
trading-engine-mvp/
│
├── apps/
│   ├── api/                            # FastAPI (extended)
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── market_data.py
│   │   │   ├── intelligence.py
│   │   │   ├── trade_lab.py
│   │   │   ├── portfolio.py
│   │   │   ├── journal.py
│   │   │   ├── learning.py
│   │   │   ├── agents.py
│   │   │   └── watchlist.py
│   │   ├── websockets/
│   │   │   ├── price_feed.py
│   │   │   ├── alerts.py
│   │   │   └── market_events.py
│   │   └── middleware/
│   │       ├── auth.py
│   │       ├── rate_limit.py
│   │       └── audit.py
│   │
│   └── web/                            # Next.js 14 frontend (new)
│       ├── app/
│       │   ├── dashboard/page.tsx
│       │   ├── explore/page.tsx
│       │   ├── ticker/[symbol]/page.tsx
│       │   ├── trade-lab/page.tsx
│       │   ├── ai-analyst/page.tsx
│       │   ├── portfolio/page.tsx
│       │   ├── learn/page.tsx
│       │   └── journal/page.tsx
│       └── components/
│           ├── charts/
│           ├── intelligence/
│           ├── agents/
│           └── ui/
│
├── core/                               # PRESERVED — existing 6 phases
│   ├── data_ingestion/
│   │   ├── stock_collector.py          # extend: intraday + WS support
│   │   ├── news_collector.py           # extend: more sources
│   │   ├── macro_collector.py          # keep as-is
│   │   ├── social_collector.py         # extend: StockTwits
│   │   ├── options_collector.py        # NEW
│   │   ├── earnings_collector.py       # NEW
│   │   ├── institutional_collector.py  # NEW
│   │   ├── insider_collector.py        # NEW
│   │   └── watchlist_monitor.py        # NEW
│   ├── sentiment_engine/               # keep as-is
│   ├── research_agent/                 # extend: multi-agent
│   ├── strategy_engine/                # keep + expose via UI
│   ├── backtesting_engine/             # extend: Monte Carlo, portfolio
│   └── explainability_engine/          # keep as-is
│
├── intelligence/                       # NEW — AI interpretation
│   ├── base.py                         # BaseIntelligenceOutput + disclaimer
│   ├── news_intelligence/
│   │   ├── summarizer.py
│   │   ├── tone_detector.py
│   │   ├── impact_scorer.py
│   │   └── sector_classifier.py
│   ├── trade_quality/
│   │   ├── scorer.py
│   │   ├── risk_analyzer.py
│   │   ├── setup_matcher.py
│   │   └── conflict_detector.py
│   ├── market_narrative/
│   │   ├── briefing_generator.py
│   │   ├── sector_summarizer.py
│   │   └── flow_interpreter.py
│   └── watchlist_intelligence/
│       ├── anomaly_detector.py
│       ├── breakout_scanner.py
│       └── sentiment_monitor.py
│
├── agents/                             # NEW — LangGraph multi-agent
│   ├── orchestrator.py
│   ├── news_agent.py
│   ├── market_analyst_agent.py
│   ├── trade_reviewer_agent.py
│   ├── risk_agent.py
│   ├── portfolio_agent.py
│   └── educational_agent.py
│
├── ml/                                 # NEW — ML models
│   ├── feature_engineering.py
│   ├── regime_detector.py
│   ├── volatility_estimator.py
│   ├── forecasters/
│   │   ├── xgboost_model.py
│   │   ├── lstm_model.py
│   │   └── prophet_model.py
│   └── ensemble.py
│
├── portfolio/                          # NEW
│   ├── analyzer.py
│   ├── correlation.py
│   ├── risk_metrics.py
│   ├── monte_carlo.py
│   └── report_generator.py
│
├── behavioral/                         # NEW
│   ├── pattern_detector.py
│   ├── discipline_scorer.py
│   └── habit_analyzer.py
│
├── education/                          # NEW
│   ├── concept_explainer.py
│   ├── adaptive_engine.py
│   └── content_library.py
│
├── database/
│   ├── models/                         # SQLAlchemy ORM models
│   │   ├── market.py
│   │   ├── users.py
│   │   ├── journal.py
│   │   ├── portfolio.py
│   │   └── intelligence.py
│   ├── migrations/                     # Alembic
│   ├── schema.sql                      # extended (see DATABASE SCHEMA section)
│   └── db_manager.py                   # extended (PostgreSQL + DuckDB)
│
├── pipeline/
│   ├── data_pipeline.py               # existing, extend
│   ├── scheduler.py                   # upgrade to APScheduler
│   └── event_bus.py                   # NEW — Redis pub/sub wrapper
│
├── utils/
│   ├── config.py                      # extend with new settings
│   └── logger.py                      # keep
│
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.prod.yml
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   └── nginx/nginx.conf
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## Tech Stack

### Frontend
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui (component library)
- TradingView Lightweight Charts (charting)
- Recharts (analytics visualizations — keep from existing)
- Zustand (client state)
- React Query / TanStack Query (server state + WebSocket sync)

### Backend
- FastAPI (existing — extend)
- Uvicorn + Gunicorn (ASGI)
- WebSockets (FastAPI native)
- APScheduler (job scheduling — replaces schedule library)
- Celery + Redis (async task queue)
- SQLAlchemy 2.0 async (ORM for PostgreSQL)
- Alembic (migrations)
- Pydantic v2

### Databases
- PostgreSQL 16 — primary (replaces DuckDB for user/production data)
- Redis 7 — cache + pub/sub + Celery broker
- DuckDB — KEEP as analytics sidecar for fast aggregations
- ChromaDB (self-hosted) — vector database for RAG

### AI / ML
- Claude claude-sonnet-4-6 (Anthropic) — primary LLM for intelligence layer
- GPT-4o (OpenAI) — fallback, existing integration
- FinBERT (existing) — keep for sentiment
- spaCy 3.x — add for NER entity extraction
- XGBoost — regime classifier, direction model
- PyTorch — existing (FinBERT), extend for LSTM
- Prophet — trend decomposition
- arch library — GARCH volatility
- hmmlearn — HMM regime detection
- LangGraph — agent state machine
- LangChain — tool bindings, retrieval
- ChromaDB — embeddings store

### Infrastructure
- Docker Compose (development)
- Kubernetes (production)
- Prometheus + Grafana (metrics)
- Sentry (error tracking)
- GitHub Actions (CI/CD)

---

## Data Sources

| Data Type | Primary API | Fallback | Cost |
|---|---|---|---|
| OHLCV (free EOD) | Yahoo Finance (yfinance) | Alpha Vantage | Free |
| OHLCV (live intraday) | Polygon.io | Alpaca Markets | $29/mo |
| WebSocket price stream | Polygon.io WebSocket | Alpaca WS | Included |
| News feeds | NewsAPI (existing) + Benzinga | Finnhub | $0–$99/mo |
| Options chain | Unusual Whales / Tradier | Yahoo Finance | $30/mo |
| Earnings calendar | Earnings Whispers API | FMP | Free tier |
| Macro indicators | FRED (existing) | World Bank API | Free |
| Institutional / 13F | SEC EDGAR API | Whale Wisdom | Free |
| Insider trades | SEC EDGAR Form 4 | OpenInsider | Free |
| Social sentiment | Reddit (existing) + StockTwits API | Twitter API v2 | Free |
| Sector strength | SPDR ETF prices via yfinance | — | Free |

---

## Database Schema Extensions (PostgreSQL)

### New Tables (beyond existing 14 DuckDB tables)

```sql
-- User management
CREATE TABLE users (
    user_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    username    VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    tier        VARCHAR(20) DEFAULT 'free',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ
);

-- User watchlists
CREATE TABLE watchlists (
    watchlist_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(user_id) ON DELETE CASCADE,
    name         VARCHAR(100),
    tickers      JSONB,
    alerts_config JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- User-owned strategies
CREATE TABLE user_strategies (
    user_strategy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES users(user_id),
    strategy_name    VARCHAR(255),
    based_on_template VARCHAR(100),
    entry_conditions  JSONB,
    exit_conditions   JSONB,
    risk_rules        JSONB,
    asset_scope       JSONB,
    is_public         BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Trade journal
CREATE TABLE trade_journal (
    journal_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID REFERENCES users(user_id),
    ticker        VARCHAR(20) NOT NULL,
    direction     VARCHAR(10),
    entry_price   NUMERIC(12,4),
    exit_price    NUMERIC(12,4),
    position_size NUMERIC(12,4),
    entry_date    TIMESTAMPTZ,
    exit_date     TIMESTAMPTZ,
    stop_loss     NUMERIC(12,4),
    target        NUMERIC(12,4),
    actual_pnl    NUMERIC(12,4),
    pnl_percent   NUMERIC(8,4),
    emotion_entry VARCHAR(50),
    emotion_exit  VARCHAR(50),
    rule_followed BOOLEAN,
    notes         TEXT,
    screenshot_url VARCHAR(500),
    ai_review     JSONB,
    behavioral_flags JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Portfolio positions
CREATE TABLE portfolio_positions (
    position_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID REFERENCES users(user_id),
    ticker        VARCHAR(20),
    quantity      NUMERIC(12,4),
    avg_cost      NUMERIC(12,4),
    current_price NUMERIC(12,4),
    last_updated  TIMESTAMPTZ
);

-- Portfolio risk snapshots
CREATE TABLE portfolio_risk_snapshots (
    snapshot_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID REFERENCES users(user_id),
    snapshot_date DATE,
    total_value   NUMERIC(15,2),
    beta          NUMERIC(8,4),
    var_95        NUMERIC(8,4),
    sector_weights JSONB,
    correlation_risk JSONB,
    health_score  NUMERIC(5,2),
    ai_summary    TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- AI narrative cache
CREATE TABLE ai_narratives (
    narrative_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    narrative_type VARCHAR(50),
    scope         VARCHAR(100),
    content       TEXT,
    model_used    VARCHAR(100),
    tokens_used   INTEGER,
    generated_at  TIMESTAMPTZ,
    valid_until   TIMESTAMPTZ,
    metadata      JSONB
);

-- Behavioral scores
CREATE TABLE behavioral_scores (
    score_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID REFERENCES users(user_id),
    period_start  DATE,
    period_end    DATE,
    discipline_score NUMERIC(5,2),
    stop_adherence_rate NUMERIC(5,4),
    target_achievement_rate NUMERIC(5,4),
    overtrading_score NUMERIC(5,2),
    revenge_trading_count INTEGER,
    early_exit_count INTEGER,
    ai_report     TEXT,
    computed_at   TIMESTAMPTZ DEFAULT NOW()
);

-- User learning profiles
CREATE TABLE user_learning_profiles (
    user_id       UUID PRIMARY KEY REFERENCES users(user_id),
    level         VARCHAR(20) DEFAULT 'beginner',
    concepts_mastered JSONB,
    learning_history JSONB,
    adaptive_score NUMERIC(5,2),
    last_updated  TIMESTAMPTZ
);

-- Agent conversations
CREATE TABLE agent_conversations (
    conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(user_id),
    agent_type      VARCHAR(50),
    messages        JSONB,
    context_used    JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Alert log
CREATE TABLE alert_log (
    alert_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID REFERENCES users(user_id),
    alert_type    VARCHAR(50),
    ticker        VARCHAR(20),
    trigger_value NUMERIC,
    ai_narration  TEXT,
    fired_at      TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ
);
```

---

## Implementation Roadmap

### Phase 0 — Infrastructure Migration (Week 1–2)
- Clone repo, add Docker Compose (postgres, redis, api, worker)
- Migrate DuckDB schema to PostgreSQL via Alembic
- Keep DuckDB as analytics sidecar
- Add JWT auth to FastAPI
- Setup GitHub Actions CI

### Phase 1 — Market Data Extension (Week 3–4)
- Add options, earnings, insider, institutional collectors
- WebSocket price streaming (Polygon.io)
- Redis pub/sub event bus
- APScheduler with pre-market/intraday/EOD jobs

### Phase 2 — Intelligence Layer (Week 5–7)
- News Intelligence Engine (7-step pipeline)
- Trade Quality Engine (input ticker/entry/SL/target → report)
- Market Narrative Engine (pre-market briefing, intraday update, EOD debrief)
- Watchlist Intelligence (anomaly detection, AI narration)
- Claude claude-sonnet-4-6 as primary LLM
- Mandatory disclaimer enforcement at base class

### Phase 3 — Frontend Rebuild (Week 8–10)
- Scaffold Next.js 14 in apps/web/
- 8-section navigation shell
- AI Market Dashboard, Ticker Intelligence, Trade Evaluator
- TradingView chart integration
- WebSocket live price updates
- Mobile responsive

### Phase 4 — ML Layer (Week 11–13)
- Feature engineering pipeline
- Regime detector (XGBoost)
- Volatility estimator (GARCH)
- Prophet trend decomposition
- Ensemble layer
- Probabilistic output only — no price targets

### Phase 5 — Agent System (Week 14–16)
- LangGraph + LangChain setup
- ChromaDB vector store
- News, Market Analyst, Trade Reviewer, Educational agents
- AI Analyst chat UI
- Conversation history persistence

### Phase 6 — Trade Lab + Portfolio Brain (Week 17–19)
- No-code strategy builder UI (expose existing strategy_engine)
- Extended backtester (walk-forward, portfolio, transaction costs)
- Monte Carlo simulation
- Portfolio risk metrics (correlation, VaR, beta)

### Phase 7 — Journal + Behavioral + Education (Week 20–22)
- Trade Journal with full entry flow
- Behavioral pattern detector (6 patterns)
- Discipline scorer
- Contextual education explainer
- Adaptive difficulty engine

### Phase 8 — Production Hardening (Week 23–24)
- Rate limiting, audit logging, Sentry, Prometheus/Grafana
- Security audit (OWASP checklist)
- DPDP Act compliance, TOS, financial disclaimers
- Production Kubernetes deployment

---

## Security + Compliance

### Financial Disclaimer (mandatory on ALL AI outputs)
```
This analysis is generated by an AI system for educational and 
informational purposes only. It does not constitute financial advice, 
investment recommendations, or solicitation to buy or sell any security. 
Past performance is not indicative of future results. All trading 
involves significant risk of loss. Please consult a registered financial 
advisor before making investment decisions.
```

### SEBI Considerations
- Platform provides analysis, NOT personalized investment advice
- All outputs framed as "historical analysis", "statistical context", "educational information"
- No price targets presented as forward-looking specific recommendations
- DPDP Act 2023 compliance for user data (India)
- User consent at registration: "I understand this is not financial advice"

### API Security
- JWT auth (15min access tokens, 7-day refresh, httpOnly cookies)
- Rate limiting: Free 100 req/hr, Pro 1000 req/hr, Premium 10000 req/hr
- AI queries: Free 5/day, Pro 50/day, Premium unlimited
- Pydantic v2 input validation on all endpoints
- SQLAlchemy ORM — no raw SQL (SQL injection protected)
- Audit log table: append-only, 90-day retention

---

## Key Design Decisions

| Decision | Why |
|---|---|
| Keep DuckDB for analytics | Zero migration risk; blazing fast aggregations for backtesting |
| PostgreSQL for user data | Multi-user concurrent writes; ACID compliance |
| Next.js over Vite+React | SSR performance; easier production deployment |
| Claude as primary LLM | Better instruction following for financial disclaimers; structured outputs |
| LangGraph over raw LangChain | Explicit state machine; predictable agent flows; easier debugging |
| ChromaDB self-hosted | No per-query costs; data sovereignty |
| APScheduler over Celery Beat | Simpler for scheduling; Celery reserved for heavy async tasks |
| shadcn/ui | Unstyled composable components; Tailwind native |

---

## What Is NOT Being Built

- Auto-trading / execution engine
- "AI predicts price" claims
- Guaranteed profit systems
- Signal selling / copy trading
- High-frequency trading infrastructure
- Broker API integration
- Cryptocurrency trading
