# AI Market Intelligence OS

**An AI-powered market analysis and trader decision-support platform.**

> For educational and informational purposes only. Not financial advice.  
> All trading involves significant risk of loss.

---

## What This Is

A complete platform that helps active traders understand markets, analyze trade setups, monitor risk, and improve trading discipline — through AI-assisted market interpretation, real-time alerts, and contextual learning.

**This is NOT:**
- An autonomous trading bot
- A "guaranteed prediction" system
- Financial advice

**This IS:**
- An AI co-pilot that reduces cognitive overload
- A contextual education system
- A trade quality evaluator
- A real-time market intelligence feed
- A behavioral coaching tool

---

## Features

### Dashboard
- AI-generated pre-market briefings (Claude claude-sonnet-4-6)
- Real-time macro instrument ticker bar (SPY, QQQ, VIX, DXY, 10Y)
- Sector heatmap with dynamic intensity coloring
- Top gainers/losers (click to navigate to ticker)
- Live watchlist alert feed

### Watchlist & Notifications
- Build watchlists from 20+ popular stocks or search any ticker
- Real-time WebSocket notifications per user (Redis pub/sub)
- AI-narrated alerts: volume spikes, breakouts, large price moves, options anomalies
- Buy/sell signal scanner (RSI + EMA based, with mandatory disclaimer)
- Notification center with unread count and severity levels

### AI Analyst (Multi-Agent Chat)
- Natural language market research
- LangGraph orchestration routes queries to the right specialist:
  - **News Agent** — news events and market-moving headlines
  - **Market Analyst Agent** — sector trends, macro, market regime
  - **Trade Reviewer Agent** — trade setup evaluation in natural language
  - **Risk Agent** — position sizing, portfolio risk
  - **Portfolio Agent** — diversification, correlation analysis
  - **Educational Agent** — explains any trading concept at your level
- Full conversation history with agent attribution

### Strategy Competition (Multi-Agent)
- 5 independent strategy agents compete on any ticker:
  1. RSI Mean Reversion
  2. EMA Trend Following
  3. Bollinger Band Breakout
  4. MACD Momentum
  5. Volume + Price Composite
- Concurrent backtesting with realistic commissions and slippage
- Ranked by risk-adjusted return (Sharpe ratio)
- AI coach interprets why the winner worked for that specific ticker
- Run on single ticker or entire watchlist at once

### Ticker Intelligence
- Live quote with price and change
- AI analysis summary (Claude claude-sonnet-4-6)
- 6-month custom SVG price chart
- News intelligence: AI-narrated sentiment, severity, affected sectors
- Trade setup evaluator with R:R, technical signals, risk warnings

### Trade Lab
- **Evaluator**: Input ticker + entry/stop/target → 0–100 score with letter grade
- **Strategy Builder**: No-code drag-and-drop strategy creator
- **Backtester**: Async Celery backtest with real commission modeling
- Monte Carlo simulation for strategy risk assessment

### Portfolio Brain
- Add positions and track real-time P&L
- Sector exposure bar chart
- Risk metrics: VaR (95%), CVaR, beta vs SPY, max drawdown, annual volatility
- Correlation matrix heatmap
- AI portfolio health assessment

### Trade Journal
- Log every trade with emotion tracking and rule adherence
- AI post-trade review (auto-generated after closing a position)
- Behavioral pattern detection: revenge trading, winner cutting, overtrading, FOMO entry
- Monthly discipline score (0–100) with AI coaching report

### Learning Hub
- Contextual AI explanations adapated to your level (beginner/intermediate/advanced)
- 7 core concepts with detailed breakdowns
- Optional ticker context: "explain RSI using current AAPL readings"
- Adaptive curriculum — recommends next topic based on history

### Explore
- Sector heatmap and top movers
- Search any ticker for quick quote
- Click any ticker to open full intelligence view

---

## Tech Stack

### Backend
| Component | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Database (user data) | PostgreSQL 16 + SQLAlchemy 2.0 (async) |
| Database (analytics) | DuckDB (existing pipeline) |
| Cache + Pub/Sub | Redis 7 |
| Task Queue | Celery |
| Scheduler | APScheduler (IST timezone) |
| Migrations | Alembic |
| Vector DB | ChromaDB |

### AI / ML
| Component | Technology |
|---|---|
| Primary LLM | Claude claude-sonnet-4-6 (Anthropic) |
| Fallback LLM | GPT-4o (OpenAI) |
| Fast routing | Claude Haiku (low-latency agent routing) |
| NLP Sentiment | FinBERT (ProsusAI) |
| Entity extraction | spaCy |
| Agent orchestration | LangGraph + LangChain |
| ML models | XGBoost, PyTorch (LSTM), Prophet, GARCH |
| Explainability | SHAP |

### Frontend
| Component | Technology |
|---|---|
| Framework | Next.js 14 (App Router) |
| Styling | Tailwind CSS (custom B&W design system) |
| State (server) | TanStack Query |
| Charts | Custom SVG (price) + Recharts (analytics) |
| Icons | Lucide React |
| Fonts | Inter + JetBrains Mono |

### Infrastructure
| Component | Technology |
|---|---|
| Containers | Docker + Docker Compose |
| Reverse Proxy | Nginx |
| CI/CD | GitHub Actions |
| Monitoring | Prometheus + Grafana + Sentry |

---

## Data Sources

| Type | Source | Cost |
|---|---|---|
| Live prices + WebSocket | Polygon.io | $29/mo |
| EOD prices | Yahoo Finance (yfinance) | Free |
| News | NewsAPI + Benzinga | Free – $99/mo |
| Options chain | Tradier | $30/mo |
| Earnings calendar | Financial Modeling Prep | Free tier |
| Macro indicators | FRED (Federal Reserve) | Free |
| Institutional holdings | SEC EDGAR 13F | Free |
| Insider trades | SEC EDGAR Form 4 | Free |
| Social sentiment | Reddit + StockTwits | Free |
| Sector ETFs | Yahoo Finance | Free |

---

## Project Structure

```
trading-engine-mvp/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── routers/            # 10 route groups
│   │   ├── websockets/         # WebSocket: prices, alerts
│   │   ├── middleware/         # auth, rate limiting, audit
│   │   └── tasks/              # Celery tasks (5 modules)
│   └── web/                    # Next.js 14 frontend
│       ├── app/                # 10 pages (App Router)
│       └── components/         # Shared UI + intelligence components
│
├── core/                       # Preserved original 6-phase pipeline
│   ├── data_ingestion/         # 9 collectors (stock, news, macro, social,
│   │                           #   options, earnings, insider, institutional, watchlist)
│   ├── sentiment_engine/       # FinBERT NLP
│   ├── research_agent/         # LLM hypothesis generation
│   ├── strategy_engine/        # 5-template strategy builder
│   ├── backtesting_engine/     # Custom Python backtester
│   └── explainability_engine/  # SHAP decision attribution
│
├── intelligence/               # AI interpretation layer (NEW)
│   ├── news_intelligence/      # 7-step news pipeline
│   ├── trade_quality/          # Trade scorer (0-100)
│   ├── market_narrative/       # Daily briefings, sector summaries
│   └── watchlist_intelligence/ # Real-time anomaly detection
│
├── agents/                     # Multi-agent system (NEW)
│   ├── orchestrator.py         # LangGraph routing
│   ├── *_agent.py              # 6 specialist agents
│   └── strategy_competition/   # 5-strategy competition engine
│       ├── strategies.py       # Strategy signal functions
│       └── competition_runner.py # Parallel backtest orchestrator
│
├── ml/                         # ML models (NEW)
│   ├── feature_engineering.py  # 20+ technical features
│   ├── regime_detector.py      # XGBoost market regime classifier
│   ├── ensemble.py             # Probabilistic ensemble forecaster
│   └── forecasters/            # XGBoost, LSTM, Prophet
│
├── portfolio/                  # Portfolio brain (NEW)
├── behavioral/                 # Behavioral intelligence (NEW)
├── education/                  # Contextual learning (NEW)
├── pipeline/                   # Scheduler + event bus (NEW)
├── database/                   # SQLAlchemy models + Alembic migrations
└── infra/                      # Docker, Nginx configs
```

---

## Quick Start

### 1. Clone and setup

```bash
git clone https://github.com/tfthushaar/trading-engine-mvp.git
cd trading-engine-mvp
cp .env.example .env
# Fill in your API keys in .env
```

### 2. Required API Keys

| Key | Get From | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com | Yes (AI features) |
| `NEWS_API_KEY` | newsapi.org | Yes (news feed) |
| `FRED_API_KEY` | fred.stlouisfed.org | Yes (macro data) |
| `OPENAI_API_KEY` | platform.openai.com | Optional (fallback) |
| `POLYGON_API_KEY` | polygon.io | Optional (live prices) |
| `TRADIER_API_KEY` | developer.tradier.com | Optional (options) |
| `FMP_API_KEY` | financialmodelingprep.com | Optional (earnings) |

**Tip:** You can also enter API keys directly in the browser at `/settings/api-keys` — they're stored locally and never sent to the server.

### 3. Start with Docker

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API + Swagger | http://localhost:8000/api/docs |
| ChromaDB | http://localhost:8001 |

### 4. Start without Docker (development)

```bash
# Backend
pip install -r requirements.txt
uvicorn apps.api.main:app --reload

# Frontend
cd apps/web
npm install
npm run dev

# Worker (optional — for backtesting)
celery -A apps.api.celery_app worker --loglevel=info

# Scheduler (optional — for automated data collection)
python -m pipeline.scheduler
```

---

## Pages

| Route | Feature |
|---|---|
| `/dashboard` | AI briefing, macro bar, sector heatmap, alerts |
| `/explore` | Search tickers, top movers, sector overview |
| `/watchlist` | Build watchlists, real-time notifications, signal scanner |
| `/ticker/[symbol]` | Intelligence, chart, news, trade evaluator |
| `/ai-analyst` | Natural language market research chat |
| `/trade-lab` | Trade evaluator, strategy builder, backtester |
| `/competition` | 5-agent strategy competition on any ticker |
| `/portfolio` | Portfolio analysis, risk metrics, correlation |
| `/learn` | Contextual AI explanations, adaptive curriculum |
| `/journal` | Trade journal, behavioral analysis, discipline score |
| `/settings/api-keys` | Enter API keys (stored in browser) |
| `/login` | Authentication |
| `/register` | Create account + disclaimer acknowledgment |

---

## API Endpoints

Full interactive documentation at `/api/docs` (Swagger UI).

Key endpoint groups:
- `GET /api/market/*` — live quotes, history, sector data, movers
- `POST /api/intelligence/trade/evaluate` — trade quality scorer
- `GET /api/intelligence/briefing/daily` — AI pre-market briefing
- `POST /api/agents/chat` — multi-agent natural language chat
- `POST /api/competition/run/{ticker}` — strategy competition
- `POST /api/competition/run-watchlist` — watchlist competition
- `POST /api/watchlist/alerts/signals` — buy/sell signal scanner
- `GET /api/portfolio/analysis` — AI portfolio report
- `GET /api/journal/behavioral-report` — behavioral coaching report
- `GET /api/learn/explain/{concept}` — contextual education

---

## Security

- JWT authentication (15-minute access tokens, 7-day refresh)
- Redis-backed rate limiting (100/1000/10000 req/hr by tier)
- Audit logging on all requests
- API keys stored in browser localStorage only (never sent to server)
- All AI outputs include mandatory financial disclaimer

---

## Compliance

This platform provides AI-generated market analysis for **educational and informational purposes only**.

- Does not constitute financial advice or investment recommendations
- Does not facilitate order execution or broker connectivity
- Users must acknowledge disclaimer at registration
- All AI outputs carry mandatory disclaimer text
- Position sizing and trade decisions remain entirely with the user

---

## Roadmap

- [ ] Phase 4: ML model training pipeline (XGBoost regime, LSTM price patterns)
- [ ] Phase 5: LangGraph agent memory persistence (ChromaDB RAG)
- [ ] Phase 6: Mobile-responsive PWA
- [ ] Phase 7: Broker API integration (paper trading only)
- [ ] Phase 8: Options chain visualization and Greeks analysis
- [ ] Phase 9: Multi-user collaboration and shared watchlists
- [ ] Phase 10: Production Kubernetes deployment on AWS/GCP

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Commit with conventional commits (`feat:`, `fix:`, `docs:`)
4. Open a pull request

---

## License

MIT License — See `LICENSE` file.

---

*Built on top of the original [KernelLex/trading-engine](https://github.com/KernelLex/trading-engine) research platform.*
