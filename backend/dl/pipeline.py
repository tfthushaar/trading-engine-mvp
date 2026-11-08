"""End-to-end experiment: data -> model -> training -> evaluation vs baselines -> backtest -> forecast."""
from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

import numpy as np

from backend.dl import evaluate as ev
from backend.dl.architectures import ARCHITECTURES, build_model, receptive_field, summarize
from backend.dl.data import MARKET_FEATURES, Dataset, build_dataset, split_summary
from backend.dl.nn import sigmoid
from backend.dl.train import TrainConfig, predict, train
from backend.market import data as md
from backend.strategies import engine

DISCLAIMER = (
    "Research output from statistical models trained on historical prices. Not financial advice. "
    "Past performance does not predict future results."
)


def signal_from_prob(p: float) -> str:
    return "bullish" if p >= 0.55 else "bearish" if p <= 0.45 else "neutral"


# Bar sizes the Lab supports and the longest history Yahoo serves for each
LAB_INTERVALS = {
    "1h": {"label": "1 hour", "periods": ["1mo", "3mo", "6mo", "1y", "2y"]},
    "1d": {"label": "1 day", "periods": ["2y", "5y", "10y", "15y", "max"]},
    "1wk": {"label": "1 week", "periods": ["10y", "15y", "20y", "max"]},
}


def load_dataset(symbol: str, period: str, window: int, horizon: int, task: str, features: list[str] | None, interval: str = "1d") -> Dataset:
    if interval not in LAB_INTERVALS:
        raise ValueError(f"interval must be one of {', '.join(LAB_INTERVALS)}")
    if period not in LAB_INTERVALS[interval]["periods"]:
        period = LAB_INTERVALS[interval]["periods"][-1 if interval == "1h" else 2]
    df = md.history(symbol, period=period, interval=interval)
    market = None
    if features and MARKET_FEATURES.intersection(features):
        market = md.histories(["SPY", "^VIX"], period=period, interval=interval)
    return build_dataset(df, features, window=window, horizon=horizon, task=task, market=market)


def _outputs_to_scores(task: str, out: np.ndarray, ds: Dataset) -> np.ndarray:
    """Probability of an up move (classification) or predicted forward log return (regression)."""
    return sigmoid(out) if task == "classification" else out * ds.y_scale


def _positions(task: str, scores: np.ndarray, threshold: float, long_short: bool) -> np.ndarray:
    if task == "classification":
        long = scores >= threshold
        short = scores < (1 - threshold) if long_short else np.zeros_like(long)
    else:
        long = scores > 0
        short = scores < 0 if long_short else np.zeros_like(long)
    return long.astype(float) - short.astype(float)


def _test_metrics(task: str, scores: np.ndarray, ds: Dataset, idx: np.ndarray) -> dict:
    if task == "classification":
        return ev.classification_metrics(scores, ds.y[idx])
    return ev.regression_metrics(scores, ds.fwd_ret[idx])


def run_experiment(cfg: dict[str, Any]) -> dict:
    t_start = time.perf_counter()
    symbol = md.normalize_symbol(cfg.get("symbol", "SPY"))
    task = cfg.get("task", "classification")
    arch = cfg.get("arch", "lstm")
    if arch not in ARCHITECTURES:
        raise ValueError(f"unknown architecture {arch!r}")
    window = int(min(max(cfg.get("window", 30), 5), 120))
    horizon = int(min(max(cfg.get("horizon", 5), 1), 20))
    threshold = float(min(max(cfg.get("threshold", 0.5), 0.5), 0.7))
    cost_bps = float(min(max(cfg.get("cost_bps", 5.0), 0.0), 50.0))
    long_short = bool(cfg.get("long_short", False))
    tcfg = TrainConfig(**{k: v for k, v in (cfg.get("train") or {}).items() if k in TrainConfig.__dataclass_fields__}).clamp()

    interval = cfg.get("interval", "1d")
    ds = load_dataset(symbol, cfg.get("period", "10y"), window, horizon, task, cfg.get("features"), interval)
    ppy = engine.periods_per_year(interval)
    F = len(ds.features)

    model, arch_params = build_model(arch, window, F, cfg.get("arch_params"), seed=tcfg.seed)
    summary = summarize(model, window, F)
    fit = train(model, ds, tcfg)

    Xte = ds.X[ds.test]
    scores = _outputs_to_scores(task, predict(model, Xte), ds)
    metrics = _test_metrics(task, scores, ds, ds.test)

    # ---- Baselines -------------------------------------------------------------------------
    baselines: dict[str, dict] = {}
    y_te = ds.y[ds.test]
    if task == "classification":
        majority = float(ds.y[ds.train].mean() >= 0.5)
        baselines["majority_class"] = ev.classification_metrics(np.full(len(y_te), 0.75 if majority else 0.25), y_te)
        baselines["train_base_rate"] = ev.classification_metrics(np.full(len(y_te), float(ds.y[ds.train].mean())), y_te)
    else:
        baselines["zero_return"] = ev.regression_metrics(np.zeros(len(y_te)) + 1e-12, ds.fwd_ret[ds.test])
        baselines["train_mean"] = ev.regression_metrics(np.full(len(y_te), float(ds.fwd_ret[ds.train].mean())), ds.fwd_ret[ds.test])
    linear_scores = None
    if arch != "linear" and cfg.get("baseline", True):
        lin, _ = build_model("linear", window, F, seed=tcfg.seed)
        train(lin, ds, replace(tcfg, time_budget_s=min(4.0, tcfg.time_budget_s / 3)))
        linear_scores = _outputs_to_scores(task, predict(lin, Xte), ds)
        baselines["linear"] = _test_metrics(task, linear_scores, ds, ds.test)

    # ---- Backtest on the test window ---------------------------------------------------------
    rn = ds.next_ret[ds.test]
    pos = _positions(task, scores, threshold, long_short)
    bt_model = engine.run_positions(rn, pos, cost_bps, ppy)
    bt_hold = engine.buy_and_hold(rn, ppy)
    backtest = {
        "dates": ds.dates[ds.test].tolist(),
        "rule": (f"long when P(up) >= {threshold:.2f}" if task == "classification" else "long when predicted return > 0")
        + (", short on the opposite signal" if long_short else ", otherwise flat"),
        "cost_bps": cost_bps,
        "equity": {"model": md.to_float_list(bt_model["equity"]), "buy_hold": md.to_float_list(bt_hold["equity"])},
        "position": pos.astype(int).tolist(),
        "metrics": {
            "model": {**bt_model["metrics"], "trades": bt_model["n_trades"], "trade_win_rate": bt_model["win_rate"], "profit_factor": bt_model["profit_factor"]},
            "buy_hold": bt_hold["metrics"],
        },
    }
    if linear_scores is not None:
        bt_lin = engine.run_positions(rn, _positions(task, linear_scores, threshold, long_short), cost_bps, ppy)
        backtest["equity"]["linear"] = md.to_float_list(bt_lin["equity"])
        backtest["metrics"]["linear"] = {**bt_lin["metrics"], "trades": bt_lin["n_trades"]}

    # ---- Interpretability ---------------------------------------------------------------------
    sal = ev.saliency(model, Xte)
    perm = ev.permutation_importance(model, Xte, ds.y[ds.test], task, seed=tcfg.seed)
    sal_feat = sal.sum(axis=0)
    sal_feat = sal_feat / (sal_feat.sum() or 1.0)
    importance = sorted(
        [{"feature": f, "saliency": round(float(s), 5), "permutation": round(float(p), 6)} for f, s, p in zip(ds.features, sal_feat, perm)],
        key=lambda r: r["permutation"], reverse=True,
    )
    interp = {
        "saliency": np.round(sal / (sal.max() or 1.0), 4).tolist(),  # (W, F), normalised to [0, 1]
        "feature_importance": importance,
        "attention": ev.attention_maps(model, Xte),
    }

    # ---- Forecast with MC-dropout uncertainty -----------------------------------------------
    point = float(_outputs_to_scores(task, predict(model, ds.latest_X), ds)[0])
    mc = None
    if ev.has_dropout(model):
        draws = _outputs_to_scores(task, ev.mc_dropout(model, ds.latest_X, samples=int(cfg.get("mc_samples", 50)))[:, 0], ds)
        mc = {
            "mean": round(float(draws.mean()), 5), "std": round(float(draws.std()), 5),
            "p05": round(float(np.percentile(draws, 5)), 5), "p95": round(float(np.percentile(draws, 95)), 5),
            "samples": int(len(draws)),
        }
    forecast = {
        "as_of": ds.latest_date,
        "close": round(ds.latest_close, 4),
        "horizon_bars": horizon,
        "interval": interval,
        "uncertainty": mc,
    }
    if task == "classification":
        forecast["prob_up"] = round(point, 5)
        forecast["signal"] = signal_from_prob(point)
    else:
        forecast["expected_log_return"] = round(point, 6)
        forecast["signal"] = "bullish" if point > 0.25 * ds.y_scale else "bearish" if point < -0.25 * ds.y_scale else "neutral"

    series = {
        "dates": ds.dates[ds.test].tolist(),
        "score": md.to_float_list(scores),
        "actual": (ds.y[ds.test].astype(int).tolist() if task == "classification" else md.to_float_list(ds.fwd_ret[ds.test])),
        "close": md.to_float_list(ds.close[ds.test], 4),
    }
    return {
        "symbol": symbol,
        "interval": interval,
        "task": task,
        "window": window,
        "horizon": horizon,
        "features": ds.features,
        "data": {**ds.meta, "splits": split_summary(ds), "y_scale": round(ds.y_scale, 6)},
        "model": {
            "arch": arch, **{k: ARCHITECTURES[arch][k] for k in ("name", "family", "summary")},
            "params": arch_params, "summary": summary,
            "receptive_field": receptive_field(arch, window, arch_params),
        },
        "training": fit,
        "test": {
            "metrics": metrics,
            "baselines": baselines,
            "calibration": ev.calibration(scores, ds.y[ds.test]) if task == "classification" else None,
            "series": series,
        },
        "backtest": backtest,
        "interpretability": interp,
        "forecast": forecast,
        "seconds": round(time.perf_counter() - t_start, 3),
        "disclaimer": DISCLAIMER,
    }
