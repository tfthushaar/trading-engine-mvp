# status.md — project memory

Last updated: 2026-11-08

## What this is

Cloned from https://github.com/tfthushaar/trading-engine-mvp into `C:\Users\Admin\Desktop\projects\trading helper`.

Originally an "AI Market Intelligence OS": a FastAPI backend (`apps/api`) with Postgres, Redis, Celery,
ChromaDB, LangGraph agents and many LLM features, plus a Next.js 14 frontend (`apps/web`), a legacy Vite
dashboard (`dashboard/`) and a legacy DuckDB research pipeline (`core/`, `pipeline/`, `database/db_manager.py`).

**New direction (from the user):** this is a **deep learning / neural networks project**. Reshape it around
that, cut what isn't needed, and improve the rest. The UI should be **monochrome**, drawing on Apple and Google
design, with **no emojis**. It has to work and be hosted on **Vercel**.

## Hard constraints

- Vercel Python functions have a size limit (~250 MB unzipped), so torch, transformers, spacy, prophet and
  chromadb can't ship in the API. Neural-network inference and training in the API has to use NumPy, or use
  weights trained offline.
- No WebSockets, no long-running Celery worker and no Redis on Vercel. Anything that needs them must run
  inline or be dropped.
- The function filesystem is read-only except `/tmp`, so `utils/logger.py` can't write files there.
- Yahoo Finance (yfinance) can rate-limit requests from cloud IPs. Batch the requests, cache them, and have
  a fallback ready.

## Audit: bugs found in the original code (before any changes)

Backend
- `email-validator` is missing, so `EmailStr` breaks app import and the whole API fails to start.
- passlib 1.7.4 doesn't work with bcrypt>=4.1/5, so hashing crashes. Use `bcrypt` directly.
- `core/*/__init__.py` and 43 other imports still use the old top-level paths (`from strategy_engine...`),
  so anything that imports them fails, e.g. `/api/trade-lab/templates`.
- `utils/config.py` reads `NEWSAPI_KEY` but `.env.example` defines `NEWS_API_KEY`.
- `utils/logger.py` writes to `logs/`, which crashes on a read-only filesystem.
- Trade scorer returns `np.bool_` values, so JSON serialization gives a 500.
- Competition `profit_factor = inf` isn't valid JSON, so it gives a 500. The Sharpe ratio is annualized the
  wrong way (per trade times sqrt(252)).
- The backtest ignores the user's strategy rules (it's a hardcoded SMA20) and needs Celery.
- The journal AI review needs Celery. You can't close a trade, and there's no exit price field.
- The "52W high" uses 30 days or 3 months of data. EMA200 is computed from 6 months of data.
- Alert severity sorting is alphabetical, so the order is wrong.
- Pattern detector checks "anxiety", but the UI sends "anxious".
- Briefing "catalysts" are parsed from the section headers.
- Endpoints compare str user_id with UUID columns, and invalid UUIDs give a 500.
- `/register` with a duplicate username gives a 500 (IntegrityError).
- Market endpoints make 10–11 sequential yfinance calls (slow) and block the event loop.
- `database/schema.sql` is DuckDB DDL but gets mounted into Postgres init in docker-compose.

Frontend
- There's no `postcss.config.js`, so Tailwind never compiles and the whole UI renders unstyled.
- There's no `app/page.tsx`, so `/` returns 404. There's no `public/`, which the Dockerfile copies.
- Token refresh sends `refresh_token` as a query param, but the backend expects a JSON body.
- `/competition` is missing from the nav. `card-header` class is undefined. The palette mixes gray/blue
  with B&W.
- Watchlist WebSocket uses `localStorage.user_id`, which is never set (always "anon"). There are no
  WebSockets on Vercel anyway.
- Learn page makes an LLM call on every keystroke (ticker is in queryKey).
- Journal win rate divides by zero (NaN%). The dashboard "no alerts" fallback never shows.
- The API keys page says keys are never sent to the server, so they do nothing.
- 14 components in `components/` are never imported.
- Next 14.2.3 has known CVEs, so it needs upgrading.

## Decisions (from the user, 2026-11-08)

1. **DL approach: both.** From-scratch NumPy networks (hand-written backprop, gradient-checked) that train
   live in the app on Vercel, plus PyTorch reference implementations of the same architectures, trained
   offline, exported, and parity-checked against NumPy.
2. **Keep:** LLM features (briefing, analyst chat, learn hub) and rule strategies (5-strategy competition +
   no-code rule backtester, also used as baselines for the networks).
3. **Remove:** accounts/login, database, portfolio, journal/behavioral, Redis, Celery, WebSockets,
   scheduler, the legacy DuckDB pipeline (`core/`, `pipeline/`, `database/`, `dashboard/`, mock scripts).
4. **General public platform:** no accounts and nothing tied to a single user. Anyone can see what's
   happening and what the models suggest. The neural networks run in the backend.
5. **UI:** monochrome only (no green/red), Apple/Google-inspired, dense ("no wasted space"), clean,
   minimal, no emojis (and no emoji-like symbols such as checkmarks or warning signs).

## Target architecture

One Vercel project serves both parts from the same origin (no CORS):
- Next.js app at the repo root (`app/`, `components/`, `lib/`).
- FastAPI at `api/index.py`, which imports `backend.app:app`. `next.config` rewrites `/api/*` to it in
  dev (uvicorn :8000).
- `backend/` (Python package):
  - `dl/nn/`: the NumPy NN library (Dense, activations, Dropout, LayerNorm, LSTM, GRU, Conv1D, MHSA,
    PositionalEncoding, pooling, Residual, Sequential, losses, SGD/Adam/AdamW, grad clipping, gradcheck,
    serialization)
  - `dl/data.py`: features, windowing, chronological split, train-only scaling (no leakage)
  - `dl/architectures.py`: linear, mlp, lstm, gru, cnn, transformer
  - `dl/train.py`, `dl/evaluate.py`: training loop (early stopping, time budget), metrics, baselines,
    MC dropout, saliency, attention
  - `dl/global_model.py`: loads the shipped pretrained ensemble (`backend/dl/weights/*.npz` + model
    card json) for instant inference
  - `market/`: yfinance with batch requests and TTL cache, indicators, regime
  - `strategies/`: the 5 rule strategies, rule DSL, one shared backtest engine (daily returns, costs),
    metrics, Monte Carlo
  - `ai/`: LLM client (Anthropic primary, key from env or the `X-Anthropic-Key` header), briefing, news,
    ticker narrative, agents, education
  - `routers/`: market, models, signals, strategies, intelligence, agents, learn, meta
- `research/`: offline PyTorch reference models, global-ensemble training/export, NumPy/PyTorch parity
  checks. Not deployed.
- `tests/`: gradient checks, layer tests, pipeline tests, API smoke tests.

## Plan

- [x] Get the user's decisions
- [ ] Remove the dropped features and legacy code, restructure folders
- [ ] Write the NumPy NN engine and its gradient-check tests
- [ ] Write the data/feature pipeline, trainer, evaluation, baselines, backtest
- [ ] Market data layer, rule strategies, LLM layer, routers
- [ ] Train the global ensemble offline (PyTorch), export, parity-test, ship weights
- [ ] Frontend rebuild: Overview, Signals, Ticker, Lab, Arena, Backtest, Analyst, Learn, Settings
- [ ] Local verification: pytest, ruff, `next build`, endpoint smoke tests
- [ ] Deploy to Vercel, smoke-test production
- [ ] README + methodology docs

## Done

- Cloned repo, read all backend/frontend code, audited bugs (list above)
- Vercel CLI logged in (device flow). gh logged in as tfthushaar.
- Removed legacy and dropped code with `git rm`. It's still in git history for reference.
- `backend/dl/nn/`: NumPy NN library. 30/30 gradient-check tests pass, including a negative control
  (a deliberately broken backward must fail). Gradcheck uses an atol floor because some gradients are 0
  by symmetry (the attention key bias).
- `backend/dl/{architectures,data,train,evaluate,pipeline}.py` run end-to-end on real SPY data (10y,
  2,431 samples).
- Perf: sigmoid via tanh, GELU without pow, running train metric. Per-epoch on SPY 10y: mlp 0.013s,
  lstm 0.22s, gru 0.17s, cnn 0.14s, transformer 0.72s.
- `backend/market/{data,indicators}.py`: batched yfinance, TTL cache, quotes, search, profile, news.
- `backend/strategies/engine.py`: the shared daily-returns backtest + metrics.
- Dropped langgraph/langchain to save about 25 MB; the analyst router is now a plain function.

## User requests to remember

- Rewrite the README at the end as a product and project description, not a dev log.
- UI: monochrome, dense, minimal, Apple/Google feel, no emojis.
- **Rename to "Trading Engine"** in GitHub, the local folder and Vercel.
  - GitHub rename was blocked: the gh token is a fine-grained PAT without Administration permission
    (HTTP 403). The user has to rename it in GitHub settings or re-auth gh.
  - Rename the local folder `trading helper` to `trading-engine` as the LAST step (the session, VS Code
    and the venvs are all inside it).
  - The Vercel project name is `trading-engine`.
- **Timeframes like TradingView:** range presets plus interval selection, candles/line/area,
  overlays, volume/RSI/MACD panes, crosshair legend. Use `lightweight-charts` (TradingView's OSS lib).
  Lab and backtests support interval choice (1h/1d/1wk) and annualize per bar frequency.
- **It must feel like a complete product, not a demo:** ⌘K search, watchlist (localStorage), screener,
  model card page, URL state, light/dark, export, empty/error/loading states, responsive.

- `research/`: PyTorch mirrors of every architecture. `test_parity.py`: all 6 archs match NumPy on
  forward, input-grad and param-grad to 1e-10.
- **Global ensemble trained** (`research/train_global.py`, about 140s on CPU):
  - Data: 48 symbols, 176k samples. Train 2012–2021, val 2022–2023, test 2024-01 to 2026-10.
  - Members: LSTM48, GRU48, TCN32x4, Transformer d32x2. Export parity about 1e-7.
  - Weights live in `backend/dl/weights/` (about 200 KB).
  - Test AUC: ensemble 0.529, members 0.52–0.53. Log loss 0.6870 vs 0.6888 base.
  - Deciles (held out): top decile 61.3% up and +0.70% 5d vs bottom 52.8% and +0.06%. Base 55.1%.
  - Signal rule: top two deciles = bullish, bottom two = bearish.
  - Retrain: `.venv-research/Scripts/python -m research.train_global --epochs 12 --years 15`
- LLM: multi-provider `backend/ai/llm.py`.
  - Groq is the default via the server key `GROQ_API_KEY` (in `.env` locally and a Vercel env var,
    NEVER committed). Model `openai/gpt-oss-120b`.
  - Visitors can bring their own key for any provider (`X-LLM-Provider`, `X-LLM-Key`, `X-LLM-Model`
    headers).
  - Anthropic via the official SDK (claude-opus-5-5, effort low, server fallbacks "default").
  - Gemini via its OpenAI-compatible endpoint (`gemini-flash-latest`).
  - Shared-key budgets: 5/min, 600/day per instance, 8 per 10min per IP. The Groq key itself allows
    1000 req/day and 8000 TPM.
- AI features: `backend/ai/{insights,agents,education}.py`. All have deterministic fallbacks.
  The analyst uses a keyword router, so each message is one LLM call.
- Market: `backend/market/overview.py` (macro, sectors, movers, rule-based regime).
- Strategies: `backend/strategies/{rules,montecarlo}.py`. The rule DSL compares two operands with
  > / < / crosses.
- The engine annualizes by bar frequency (`periods_per_year`). The Lab supports 1h/1d/1wk.

## Restore features from the original list (user request, 2026-11-08)

Keep every original feature that works without accounts. Remove only infrastructure: Redis, Celery,
WebSockets, LangGraph, accounts. Personal tools keep their data in localStorage and the server
analyzes it statelessly.

Backend:
- [ ] Alerts (volume spike, breakout/breakdown, large move, RSI extreme, neural extreme, options
  anomaly) with batched AI narration
- [ ] Technical RSI+EMA scanner
- [ ] Trade evaluator (0–100 score and grade, R:R, signals, warnings, neural view, AI)
- [ ] Strategy competition for a watchlist (slippage, AI coach)
- [ ] Portfolio analyze (P&L, sectors, VaR/CVaR/beta/DD/vol, correlation, neural per holding, AI health)
- [ ] Journal analyze (patterns, discipline score, coaching) and single-trade review
- [ ] Analyst: add news, trade_reviewer and portfolio agents
- [ ] News: add severity and affected_sectors
- [ ] Markets heatmap endpoint

Frontend nav: Overview · Markets · Signals · Lab (train/arena/model) · Strategies
(competition/builder/evaluator) · Portfolio · Journal · Analyst · Learn. Plus a notification bell,
multiple watchlists, ⌘K and Settings.

## Progress (2026-11-08, later)

- [x] All restored and reframed backend features built and smoke-tested: alerts, technical scan,
  evaluator (with a neural component), portfolio lens, model-aware journal, competition, the
  news/trade/portfolio agents, heatmap with neural tilt, attribution on `/api/signals/{sym}`.
- [x] Frontend at the repo root (Next 16.4.5, React 19.3, Tailwind 4.3, lightweight-charts 5.2.1).
  - Pages: Overview, Markets, Signals, Symbol, Lab (Train/Arena/Model card), Strategies
    (Competition/Builder/Evaluator), Portfolio, Journal, Analyst, Learn, Settings, 404, error.
  - `next build` passes and tsc is clean.
  - Browser-verified with Playwright: every page and every main flow, light and dark themes.
  - Fixed during verification: dev hydration via `allowedDevOrigins`, the scrollIntoView
    Promise returned from an effect, sticky table headers hiding under the nav, SVG text scaling,
    masonry heatmap, signals layout.
- [x] Tests: 40 pytest (gradcheck plus core) and 6 torch parity. Ruff clean. A zero-vol Sharpe bug
  was found and fixed.
- [x] Deployed to Vercel, project `trading-engine`: https://trading-engine-mocha.vercel.app
  (the bare `trading-engine.vercel.app` alias was not assigned). Production env vars set:
  GROQ_API_KEY, DEFAULT_LLM_PROVIDER, ENVIRONMENT. Preview env vars were NOT set (the CLI wanted a
  git branch).
- [x] Production verified in a real browser: 9 pages and 7 flows, light and dark, no console errors
  and no failed API calls. Yahoo Finance works from Vercel. A full LSTM Lab run takes about 22s
  (limit 60s).
- [x] Briefing and ticker narration grounded with an authoritative FACTS block, after the model took
  an old headline's move as today's.
- [x] README rewritten as a product/project description. LICENSE (MIT) added.

## What's left

- [ ] Local folder rename `trading helper` -> `trading-engine` (attempted last; see final note below
  if it is still pending).
- [ ] GitHub repo rename: blocked (HTTP 403). The gh token lacks Administration permission. The user
  can rename it under GitHub > Settings > Repository name, or re-auth gh. Then run
  `git remote set-url origin https://github.com/tfthushaar/trading-engine.git`.
- [x] Pushed to `main` on 2026-11-08 (76b62c3). Git has no identity configured on this machine, so
  the commit used the GitHub noreply address for tfthushaar through one-off `-c` flags.
- Vercel is not connected to the GitHub repo. Pushes do not deploy; run `vercel deploy --prod`.
- [ ] Shared Groq key limits are per serverless instance, so they are soft caps.
- [ ] The Groq key was pasted into a chat, so rotating it later is sensible. If rotated, update
  `.env` and the Vercel env var, then redeploy.
- [ ] The ensemble needs periodic retraining; weights were trained on data through Oct 2026.

## Bug pass (2026-11-08)

Fixed, with regression tests where testable (49 pytest):
- One malformed symbol failed whole lists (quotes, scan, alerts, competition).
- 500s on wrong-typed training options and rule values; negative portfolio quantities accepted.
- Failed Yahoo lookups were cached (5 min, profiles 1 day); quotes up to 5 min stale.
- CDN cached data-only fallbacks; alert polling spent shared AI quota; repeat prompts now reuse answers.
- Lab: time budget now checked per batch (limit 40s, function 90s); Transformer memory capped;
  hourly dates keep their time; the arbitrary "majority class" log loss removed.
- Backtest trade returns now include exit costs. Trade reviewer now receives the user's plan.
- Frontend: useApi notifies all subscribers (pages could hang on skeletons after navigating); chart
  keeps zoom across refreshes; add-symbol no longer toggles; cancel/duplicate watchlist fixed;
  label-wrapped segmented controls; RSI O(n^2); Arena curves aligned by date; phone-width overflow.
- Branding removed per user: no TE mark, no favicon, no TradingView chart logo (the license needs
  attribution, so the footer links to TradingView).

Checked and fine: yfinance 1.8 `download` uses a per-call context, so concurrent calls are safe.

## Model improvement (in progress)

`research/experiments.py` compares candidates by walk-forward validation on data cut at 2023.
The 2024+ test set has already been seen once (the v1 report), so it is not fully virgin; do not
tune against it. v1 backup is kept outside the repo during the work.

## Notes for later work

- `next dev` writes `AGENTS.md`, which says to read `node_modules/next/dist/docs/` before changing
  Next.js code, because this version differs from older ones.

Verification scripts (scratchpad, not in the repo): `shots.py` (page screenshots) and `flows.py`
(interactive flows). Run them with `.venv-research` (Playwright installed there). Use
`MSYS_NO_PATHCONV=1` in Git Bash.

## Findings

- First SPY run: the models barely beat the base rate, which is expected for daily equity returns. The
  UI must show the baselines next to every model result. Be honest about this.

## Environment notes

- Windows 11. Python 3.12.10, Node 24.16, npm 11.13, Vercel CLI 54.9.1, gh 2.93.
- Don't push to GitHub unless the user asks. Deploy via `vercel` CLI.
