"""Concept library (deep learning + markets) and contextual explanations."""
from __future__ import annotations

import json

from backend.ai import llm
from backend.market import data as md
from backend.market import indicators as ind

CONCEPTS: dict[str, dict] = {
    # ---- Deep learning --------------------------------------------------------------------
    "neural_network": {"title": "Neural networks", "category": "Deep learning",
        "summary": "A neural network is a stack of differentiable layers that maps inputs to outputs. Each layer applies a learned linear transform followed by a non-linearity, and training adjusts the weights to reduce a loss on examples.",
        "in_app": "Every model in the Lab is built from layers written from scratch in NumPy (backend/dl/nn)."},
    "backpropagation": {"title": "Backpropagation", "category": "Deep learning",
        "summary": "Backpropagation applies the chain rule from the loss back to every weight, giving the gradient that the optimiser follows. Each layer only needs its local derivative.",
        "in_app": "Each layer has a hand-written backward pass, verified against finite differences and against PyTorch autograd to 1e-10."},
    "gradient_check": {"title": "Gradient checking", "category": "Deep learning",
        "summary": "Numerical gradient checking compares analytic gradients with central finite differences (f(w+e) - f(w-e)) / 2e. Agreement to about 1e-7 relative error means the backward pass is correct.",
        "in_app": "tests/test_nn_gradients.py checks every layer and every full architecture, including a deliberately broken layer that must fail."},
    "lstm": {"title": "LSTM", "category": "Deep learning",
        "summary": "A Long Short-Term Memory cell keeps a separate cell state controlled by input, forget and output gates. The additive cell update lets gradients flow across many time steps.",
        "in_app": "LSTM is one of the four members of the global ensemble and an architecture in the Lab."},
    "gru": {"title": "GRU", "category": "Deep learning",
        "summary": "The Gated Recurrent Unit merges the LSTM's gates into reset and update gates and drops the separate cell state. It has fewer parameters and often trains faster.",
        "in_app": "GRU is an ensemble member and a Lab architecture."},
    "tcn": {"title": "Temporal convolution", "category": "Deep learning",
        "summary": "A temporal convolutional network uses causal 1-D convolutions (no look-ahead) with exponentially growing dilation, so a few layers cover a long history. Residual connections keep deep stacks trainable.",
        "in_app": "The TCN member uses dilations 1, 2, 4, 8 with kernel 3, a 31-day receptive field."},
    "attention": {"title": "Self-attention and Transformers", "category": "Deep learning",
        "summary": "Self-attention lets every time step weigh every other step by the similarity of learned queries and keys. A Transformer stacks attention and feed-forward blocks with residual connections and layer normalisation.",
        "in_app": "The Lab shows the learned attention matrix of each Transformer layer."},
    "dropout": {"title": "Dropout and MC dropout", "category": "Deep learning",
        "summary": "Dropout randomly zeroes activations during training to reduce co-adaptation. Keeping it on at inference and averaging many passes (Monte Carlo dropout) gives an approximate measure of model uncertainty.",
        "in_app": "Forecast uncertainty bands come from MC dropout."},
    "overfitting": {"title": "Overfitting and early stopping", "category": "Deep learning",
        "summary": "A model overfits when it memorises noise in the training set, so its validation loss rises while training loss keeps falling. Early stopping keeps the weights from the epoch with the best validation loss.",
        "in_app": "Training curves in the Lab show both losses and the restored best epoch."},
    "calibration": {"title": "Calibration", "category": "Deep learning",
        "summary": "A classifier is calibrated when events it gives 60% probability happen about 60% of the time. Reliability diagrams and expected calibration error measure this.",
        "in_app": "Signals show the historical up-frequency for their probability band, measured on held-out test data."},
    "leakage": {"title": "Look-ahead bias and leakage", "category": "Deep learning",
        "summary": "Leakage happens when information from the future reaches training, for example by shuffling time series, fitting scalers on all data, or overlapping labels across splits. It makes backtests look far better than reality.",
        "in_app": "Splits are chronological, scalers are fitted on training rows only, and an embargo drops samples whose labels cross a split."},
    "saliency": {"title": "Saliency and feature importance", "category": "Deep learning",
        "summary": "Gradient x input saliency measures how sensitive the output is to each input value. Permutation importance measures how much the loss worsens when one feature is shuffled.",
        "in_app": "The Lab shows a time x feature saliency map and permutation importance for each run."},
    "ensemble": {"title": "Ensembles", "category": "Deep learning",
        "summary": "Averaging the predictions of different models reduces variance when their errors are not perfectly correlated. Disagreement between members is also a useful uncertainty signal.",
        "in_app": "Signals average an LSTM, GRU, TCN and Transformer and report how many members agree."},
    # ---- Markets ----------------------------------------------------------------------------
    "rsi": {"title": "RSI", "category": "Markets",
        "summary": "The Relative Strength Index compares average gains to average losses over 14 periods on a 0-100 scale. Readings above 70 are called overbought and below 30 oversold, but strong trends can stay there for weeks.",
        "in_app": "RSI is a model feature, a chart pane, and a rule-strategy building block."},
    "macd": {"title": "MACD", "category": "Markets",
        "summary": "MACD is the difference between a 12- and a 26-period EMA; its signal line is a 9-period EMA of that difference. The histogram shows momentum turning before price does, with many false signals in ranges.",
        "in_app": "MACD histogram is a model feature, a chart pane and a rule strategy."},
    "moving_averages": {"title": "Moving averages", "category": "Markets",
        "summary": "Simple and exponential moving averages smooth price to show trend. The 50- and 200-day averages are widely watched; price above both is commonly read as an uptrend.",
        "in_app": "Chart overlays and the trend label on every symbol."},
    "bollinger": {"title": "Bollinger Bands", "category": "Markets",
        "summary": "Bands two standard deviations around a 20-period average. Narrow bands mark low volatility that often precedes larger moves; touching a band is not a signal by itself.",
        "in_app": "Chart overlay, a model feature (band position) and the breakout rule strategy."},
    "volatility": {"title": "Volatility and ATR", "category": "Markets",
        "summary": "Volatility is the dispersion of returns, usually annualised. Average True Range measures typical bar range in price units and is useful for sizing stops.",
        "in_app": "Realised volatility and ATR are model features; volatility drives risk notes."},
    "sharpe": {"title": "Sharpe ratio", "category": "Markets",
        "summary": "Average return divided by its standard deviation, annualised. It rewards consistency, not just size of return. Above 1 is good for a strategy; high values on short tests are often luck.",
        "in_app": "All backtests annualise Sharpe from per-bar returns for the selected timeframe."},
    "drawdown": {"title": "Drawdown", "category": "Markets",
        "summary": "The fall from a running peak of the equity curve. Maximum drawdown is the worst such fall and tells you how painful a strategy is to hold.",
        "in_app": "Every backtest and Monte Carlo simulation reports drawdown."},
    "position_sizing": {"title": "Position sizing", "category": "Markets",
        "summary": "Choosing how much to risk per trade, commonly a fixed fraction of capital (for example 0.5-1%) divided by the distance to the stop. Sizing usually matters more than entry timing.",
        "in_app": "The analyst can work through sizing using a symbol's ATR."},
    "regime": {"title": "Market regime", "category": "Markets",
        "summary": "Markets alternate between trending, ranging and high-volatility phases. Strategies that work in one regime often fail in another.",
        "in_app": "The Overview shows a transparent rule-based regime from S&P 500 trend and the VIX."},
}

LEVELS = ("beginner", "intermediate", "advanced")


def catalog() -> list[dict]:
    return [{"id": k, "title": v["title"], "category": v["category"], "summary": v["summary"]} for k, v in CONCEPTS.items()]


def _symbol_context(sym: str) -> dict | None:
    try:
        return ind.snapshot(md.history(sym, period="2y"))
    except Exception:
        return None


async def explain(concept: str, level: str = "intermediate", symbol: str | None = None, experiment: dict | None = None) -> dict:
    key = concept.lower().replace(" ", "_").replace("-", "_")
    meta = CONCEPTS.get(key, {"title": concept.replace("_", " ").title(), "category": "General", "summary": "", "in_app": ""})
    level = level if level in LEVELS else "intermediate"
    ctx = {"concept": meta["title"], "reference": meta.get("summary"), "how_this_product_uses_it": meta.get("in_app")}
    if symbol:
        snap = _symbol_context(md.normalize_symbol(symbol))
        if snap:
            ctx["live_example"] = {"symbol": symbol.upper(), **{k: snap.get(k) for k in ("price", "rsi_14", "sma_50", "sma_200", "macd_hist", "volatility_20d_ann", "trend")}}
    if experiment:
        ctx["experiment"] = {k: experiment.get(k) for k in ("arch", "symbol", "interval", "window", "horizon", "test_metrics", "baselines", "best_epoch", "epochs_run", "stopped")}
    prompt = (
        f"Explain {meta['title']} to a {level} reader.\n\nContext JSON:\n{json.dumps(ctx, default=str)}\n\n"
        "Use markdown with these short sections: What it is, How it works, When it helps, Where it fails, In this product"
        + (", Live example" if "live_example" in ctx else "")
        + (", Your experiment" if "experiment" in ctx else "")
        + ". Be concrete, keep it under 350 words, no emojis."
    )
    fallback = f"**{meta['title']}**\n\n{meta.get('summary', '')}\n\n**In this product.** {meta.get('in_app', '')}"
    text, source = await llm.complete_or(fallback, prompt, system="You are a precise teacher of quantitative finance and deep learning.", effort="low", max_tokens=1400)
    return {
        "id": key, "title": meta["title"], "category": meta["category"], "level": level, "symbol": symbol,
        "markdown": text, "source": "ai" if source == "ai" else "library", "note": None if source in ("ai", "fallback") else source,
    }
