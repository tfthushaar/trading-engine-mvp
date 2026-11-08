# Trading Engine

**Market intelligence powered by neural networks, built from first principles.**

Trading Engine is a public web platform that helps anyone understand what is happening in the markets and what the evidence suggests. An ensemble of four neural networks (LSTM, GRU, temporal CNN and Transformer) scores the next five trading days for any stock or ETF. Every forecast comes with its historical reliability, an uncertainty band and an explanation of which inputs drove it. Around that core sit TradingView-style charts, rule-based strategy baselines, portfolio and journal tools, and a plain-language AI analyst.

The deep-learning engine is written **from scratch in NumPy**: every layer, every backward pass and every optimiser. It is verified two ways: numerical gradient checks, and exact agreement with PyTorch reference implementations.

Live: https://trading-engine-mocha.vercel.app

> Research and education only. Nothing on the platform is financial advice.

---

## What you can do

| Area | What it offers |
|---|---|
| **Overview** | Macro strip (indices, VIX, yields, dollar, gold, oil, bitcoin), an AI market briefing grounded in the day's data, neural-ensemble breadth, a sector board with a rule-based regime, movers, your watchlists with model signals, and a live alert feed. |
| **Markets** | A sector heatmap you can colour by the day's move or by the neural model's tilt, plus macro and breadth. |
| **Signals** | A screener of the ensemble's 5-day outlook for 48 liquid US stocks and ETFs, your watchlist, or any symbols you enter. It shows the confidence decile, the historical hit rate of that decile, member agreement and Monte Carlo dropout uncertainty, next to a classic RSI and EMA rule baseline. You can export it to CSV. |
| **Symbol pages** | A TradingView-style chart with range presets from 1D to MAX, interval selection from 1 minute to 1 month, candles, line or area, SMA, EMA, Bollinger, VWAP, volume, RSI and MACD panes, and a **neural probability pane**. Alongside it: the ensemble forecast with gradient-based attribution ("why"), an AI read, news with sentiment and severity, technicals, a trade-plan evaluator and a five-strategy competition. |
| **Lab** | Train an LSTM, GRU, TCN, Transformer, MLP or linear model live on any symbol and timeframe (hourly, daily, weekly). You see learning curves, out-of-sample metrics against baselines, a confusion matrix, calibration, a backtest, saliency heatmaps, permutation importance, attention maps and an MC-dropout forecast. The **Arena** trains several architectures on the same split and ranks them against rule strategies. The **Model card** documents the pretrained ensemble. |
| **Strategies** | Five rule-based agents compete across a watchlist. A no-code rule builder lets you combine indicators with comparisons and crossovers, add stops and targets, and run a backtest with trade markers and a block-bootstrap Monte Carlo. The trade evaluator grades an entry, stop and target from 0 to 100. |
| **Portfolio** | P&L, sector exposure, value at risk and CVaR, beta, volatility, drawdown, a correlation heatmap, a health score with AI commentary, and the model's view on every holding. |
| **Journal** | Log trades with emotions and rule adherence. The model's reading at entry is saved with each trade, so you can see whether trades **with** the model beat trades **against** it. You also get behavioural pattern detection (revenge trading, overtrading, winner cutting, stops not honoured), a discipline score, AI post-trade reviews and monthly coaching. |
| **Analyst** | Ask in plain language. A router sends each question to one of nine specialists: market, news, symbol, neural model, strategy, trade review, risk, portfolio or education. The specialist gathers live data and model output before a language model writes the answer. |
| **Learn** | 23 concepts across deep learning and markets, explained at three levels. Explanations can use a live symbol's readings or your own Lab run as the example. The section includes an adaptive "next topic" and a full methodology write-up. |

There are no accounts. Watchlists, portfolio, journal, experiments and conversations stay in your browser, and the server analyses them without storing them.

---

## The deep-learning core

### A neural-network library written from scratch

`backend/dl/nn/` implements, with explicit forward and backward passes:

- **Layers:** Dense, ReLU, LeakyReLU, Tanh, Sigmoid, GELU, Dropout (inverted, and Monte Carlo at inference), LayerNorm, Flatten, global average pooling, last-timestep pooling
- **Sequence models:** LSTM and GRU with backpropagation through time. Gate layouts match PyTorch, so weights are interchangeable.
- **Convolution:** causal dilated Conv1D via im2col
- **Attention:** sinusoidal positional encoding and multi-head self-attention (optionally causal), with access to the attention weights
- **Composition:** Sequential and Residual containers
- **Training:** BCE-with-logits, MSE and Huber losses; SGD with momentum, Adam and AdamW; global-norm gradient clipping; cosine learning-rate schedule with warm-up; early stopping that restores the best weights; a wall-clock training budget

### Verified two independent ways

1. **Numerical gradient checks.** Every layer and every full architecture is checked against central finite differences. A negative control (a backward pass that is deliberately off by 1%) must fail. See `tests/test_nn_gradients.py`.
2. **Parity with PyTorch.** `research/torch_models.py` re-implements all six architectures in PyTorch. Given the same weights, the NumPy engine and PyTorch autograd agree on outputs, input gradients and every parameter gradient to 1e-10. See `research/test_parity.py`.

### Architectures

| Model | Family | Idea |
|---|---|---|
| Linear | Baseline | Logistic or linear regression on the flattened window. The bar every network must clear. |
| MLP | Feed-forward | Stacked dense layers with dropout. |
| LSTM / GRU | Recurrent | Gated memory across the input window. |
| TCN | Convolutional | Causal convolutions with dilations 1, 2, 4, 8 and residual blocks. |
| Transformer | Attention | Pre-norm encoder blocks with multi-head self-attention. |

### Data pipeline without look-ahead

- Features are scale-free: log returns over 1, 5 and 20 bars, intraday range and body, a volume z-score, RSI, MACD histogram, distance from moving averages, realised volatility, ATR, Bollinger position, and optionally S&P 500 momentum and the VIX level.
- Splits are chronological: train, then validation, then test. Nothing is shuffled across time.
- Standardisation statistics are fitted on training rows only.
- An **embargo** removes samples whose forward-looking labels would overlap the next split.

### The pretrained ensemble

An LSTM, GRU, TCN and Transformer were trained offline in PyTorch on a panel of 48 liquid US stocks and ETFs, exported to the NumPy format, and are served by the from-scratch engine. PyTorch is not used at runtime.

| | Period | Samples |
|---|---|---|
| Train | Mar 2012 to Dec 2021 | 118,523 |
| Validation | Jan 2022 to Dec 2023 | 23,808 |
| Test (held out) | Jan 2024 to Oct 2026 | 34,128 |

Held-out test results for predicting whether the close is higher in five trading days:

| Model | Params | Accuracy | ROC AUC | Log loss | NumPy vs PyTorch |
|---|---|---|---|---|---|
| LSTM | 12,145 | 55.2% | 0.523 | 0.6878 | 7e-8 |
| GRU | 9,265 | 55.2% | 0.520 | 0.6877 | 6e-8 |
| TCN | 10,721 | 55.0% | 0.525 | 0.6870 | 7e-8 |
| Transformer | 17,665 | 55.1% | 0.530 | 0.6881 | 8e-8 |
| **Ensemble** | | **55.2%** | **0.529** | **0.6870** | |
| Base rate (always "up") | | 55.1% | 0.500 | 0.6888 | |

Accuracy barely beats always guessing "up", because the market rose in 55% of five-day windows. The useful information is in the **ranking**. Readings in the top confidence decile were followed by a rise **61.3%** of the time, with an average five-day return of **+0.70%**. The bottom decile rose 52.8% of the time, averaging +0.06%. Calibration error (ECE) is 0.020. The product therefore labels signals by decile and always shows the historical hit rate next to the base rate, instead of presenting raw probabilities as predictions.

As an equal-weight portfolio rule over the test period (hold a stock only when its ensemble probability is at least 0.55), the model had a Sharpe ratio of 1.38 with a −17.0% maximum drawdown and 12.3% volatility. Buy-and-hold had a Sharpe of 1.46, a −18.8% drawdown and 14.4% volatility. In other words, the model gave slightly smoother returns and slightly lower risk-adjusted returns in a strong bull market. That is an honest result, and it is reported as such.

### What was tried to improve it

Eight alternatives were compared by walk-forward validation on data cut off at the end of 2023: more features, more training symbols, stronger regularisation, a longer window and combinations of these (`research/experiments.py`). Differences were small, about 0.003 AUC around a 0.517 baseline. The best all-round candidate (100 training symbols, refit through 2023, three seeds per architecture) was then scored once on the test period:

| | Shipped | Candidate |
|---|---|---|
| Accuracy | 55.2% | 54.3% |
| ROC AUC | 0.529 | 0.520 |
| Top two vs bottom two decile spread | 6.9 points | 3.8 points |
| Backtest Sharpe | 1.38 | 1.12 |
| Calibration error (lower is better) | 0.020 | 0.009 |

It was better calibrated but worse at ranking, so it was not shipped. The test period had already been seen once when the shipped model was reported, so these figures are slightly optimistic for both models. Price and volume features alone appear to be close to their limit here; further gains would most likely need different information, such as earnings, fundamentals or news.

### Interpretability

- **Gradient × input attribution:** for today's forecast on every symbol page, and as a time-by-feature saliency map in the Lab.
- **Permutation importance:** the rise in test loss when one feature is shuffled.
- **Attention maps:** for Transformer runs.
- **Uncertainty:** Monte Carlo dropout bands and agreement between ensemble members.

---

## Language models

Narratives (briefings, symbol reads, news classification, alert narration, coaching, the analyst and explanations) are written by a language model that only describes the data and model output passed to it. A block of authoritative facts keeps prices, moves and dates correct, and every feature has a deterministic fallback, so the platform works without any key.

- **Default:** a shared Groq key (`openai/gpt-oss-120b`), rate limited per visitor and per instance.
- **Bring your own key:** Groq, Google Gemini or Anthropic Claude, set in Settings. The key is stored in your browser and sent only with your own requests. The server uses it for that request and never stores or logs it.

---

## Architecture

```
Browser (Next.js 16, React 19, Tailwind 4, TradingView Lightweight Charts)
   |  same origin: /api/*
   v
Vercel Python function  api/index.py  ->  FastAPI  backend/app.py
   |-- backend/dl/          NumPy neural networks, data pipeline, training, evaluation, pretrained ensemble
   |-- backend/market/      Yahoo Finance access with batching and caching, indicators, regime, scanners
   |-- backend/strategies/  backtest engine, rule strategies and rule language, Monte Carlo, trade evaluator
   |-- backend/ai/          multi-provider LLM client, briefings, analyst agents, education
   |-- backend/portfolio.py, backend/journal.py   stateless analytics
   '-- backend/routers/     HTTP endpoints (OpenAPI docs at /api/docs)

research/  (offline, not deployed)
   PyTorch reference models, ensemble training and export, parity tests
```

Everything is stateless on the server, so it runs on serverless infrastructure with no database. Rate limits protect the shared AI key and the training endpoints.

---

## Running locally

Requirements: Python 3.12 and Node.js 20 or later.

```bash
# Backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt      # macOS/Linux: .venv/bin/pip
cp .env.example .env                                    # add GROQ_API_KEY (optional)

# Frontend
npm install

# Run both (Next.js on :3000 proxies /api to FastAPI on :8000)
npm run dev
```

On macOS or Linux, change the `api` script in `package.json` to use `.venv/bin/python`.

Tests:

```bash
.venv/Scripts/python -m pytest -q                       # gradient checks and core logic (49 tests)
# Research environment (PyTorch CPU) for parity tests and retraining:
python -m venv .venv-research
.venv-research/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv-research/Scripts/pip install -r research/requirements.txt
.venv-research/Scripts/python -m pytest research/test_parity.py -q
.venv-research/Scripts/python -m research.train_global --epochs 12 --years 15   # about 2-3 minutes on CPU
```

## Deploying

The repository deploys to Vercel as a single project: Next.js for the interface and a Python function for the API. Set `GROQ_API_KEY` (and optionally `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`) in the project's environment variables, then run:

```bash
vercel deploy --prod
```

## Project structure

```
app/            pages: overview, markets, signals, symbol/[symbol], lab, strategies, portfolio, journal, analyst, learn, settings
components/     UI kit, SVG charts, TradingView price chart, app shell (search, alerts, theme)
lib/            API client, local storage, formatting, indicator math
api/index.py    Vercel entry point
backend/        FastAPI application and all analytics (see Architecture)
research/       PyTorch reference implementation, training and export, parity tests
tests/          gradient checks and unit tests
```

## Limitations

- Results come from one historical period. Market behaviour changes, and the edge is small.
- Free market data can be delayed, revised or briefly unavailable.
- Backtests ignore taxes, borrow costs and market impact.
- Language-model narratives can still be wrong; the numbers on the page are the source of truth.

## Credits

Market data from Yahoo Finance via yfinance. Charts by [TradingView Lightweight Charts](https://www.tradingview.com/lightweight-charts/).

## License

MIT
