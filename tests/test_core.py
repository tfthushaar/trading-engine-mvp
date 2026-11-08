"""Offline tests for the data pipeline, backtest engine, rule language, analytics and HTTP helpers."""
import math

import numpy as np
import pandas as pd
import pytest

from backend import journal
from backend.dl.architectures import build_model
from backend.dl.data import build_dataset
from backend.dl.train import TrainConfig, predict, train
from backend.http import sanitize
from backend.strategies import engine, montecarlo, rules


def synthetic_ohlcv(n=900, seed=0):
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0004, 0.012, n)
    close = 100 * np.exp(np.cumsum(r))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.004, n)))
    vol = rng.integers(1_000_000, 3_000_000, n).astype(float)
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def test_dataset_splits_are_chronological_with_embargo():
    ds = build_dataset(synthetic_ohlcv(), window=20, horizon=5)
    assert ds.X.shape[1:] == (20, len(ds.features))
    assert ds.train.max() < ds.val.min() < ds.val.max() < ds.test.min()
    # embargo: at least `horizon` samples are dropped between splits
    assert ds.val.min() - ds.train.max() > ds.horizon
    assert ds.test.min() - ds.val.max() > ds.horizon
    assert ds.dates[ds.train[-1]] < ds.dates[ds.val[0]] < ds.dates[ds.test[0]]


def test_scaler_uses_training_rows_only():
    df = synthetic_ohlcv()
    ds = build_dataset(df, window=20, horizon=5)
    # changing the future (test period) must not change the training windows
    df2 = df.copy()
    df2.iloc[-100:, :4] *= 3.0
    ds2 = build_dataset(df2, window=20, horizon=5)
    assert np.allclose(ds.X[ds.train], ds2.X[ds2.train])


def test_labels_match_forward_returns():
    ds = build_dataset(synthetic_ohlcv(), window=20, horizon=3)
    assert np.array_equal(ds.y, (ds.fwd_ret > 0).astype(float))


def test_training_learns_a_learnable_signal():
    """A sequence model must beat chance on a synthetic task whose label is visible in the window."""
    df = synthetic_ohlcv(1200, seed=3)
    ds = build_dataset(df, features=["ret_1", "ret_5"], window=10, horizon=1)
    # replace labels with a deterministic function of the last input value
    ds.y = (ds.X[:, -1, 0] > 0).astype(float)
    model, _ = build_model("gru", 10, 2, {"hidden": 8, "dropout": 0.0}, seed=0)
    train(model, ds, TrainConfig(epochs=25, lr=0.01, time_budget_s=30, patience=25))
    acc = ((predict(model, ds.X[ds.test]) > 0) == (ds.y[ds.test] == 1)).mean()
    assert acc > 0.9


def test_engine_costs_and_metrics():
    rn = np.array([0.01, -0.02, 0.03, 0.0, 0.01])
    pos = np.array([1, 1, 0, 1, 1])
    res = engine.run_positions(rn, pos, cost_bps=10)
    # two entries (t=0, t=3) and one exit (t=2) -> three changes at 10 bps
    expected = pos * rn - np.abs(pos - np.r_[0, pos[:-1]]) * 0.001
    assert np.allclose(res["returns"], expected)
    assert res["n_trades"] == 2
    m = engine.performance(res["returns"])
    assert m["max_drawdown"] <= 0
    assert engine.performance(np.full(252, 0.001))["sharpe"] == 0.0  # zero volatility


def test_annualisation_depends_on_bar_frequency():
    r = np.random.default_rng(0).normal(0.0005, 0.01, 500)
    assert engine.performance(r, ppy=52)["sharpe"] < engine.performance(r, ppy=252)["sharpe"]


def test_rule_language_and_stops():
    df = synthetic_ohlcv()
    entry = [{"left": {"kind": "price"}, "op": "crosses_above", "right": {"kind": "sma", "period": 20}}]
    exit_ = [{"left": {"kind": "rsi", "period": 14}, "op": ">", "right": {"kind": "value", "value": 70}}]
    pos = rules.rule_positions(df, entry, exit_, stop_loss_pct=3)
    assert set(np.unique(pos)) <= {0.0, 1.0}
    assert pos.sum() > 0
    with pytest.raises(ValueError):
        rules.rule_positions(df, [], exit_)
    for sid, (_, _, fn) in rules.STRATEGIES.items():
        p = fn(df)
        assert len(p) == len(df), sid


def test_montecarlo_shapes():
    r = np.random.default_rng(1).normal(0.0005, 0.01, 300)
    mc = montecarlo.bootstrap(r, n_sims=500, horizon=100)
    assert len(mc["bands"]["p50"]) == 101
    assert 0 <= mc["prob_loss"] <= 1


def test_journal_patterns_and_model_alignment():
    entries = [
        {"symbol": "A", "direction": "long", "entry_price": 100, "exit_price": 95, "stop_loss": 97, "target": 110, "entry_date": "2026-01-01T10:00", "exit_date": "2026-01-01T15:00", "emotion_entry": "fomo", "rule_followed": False, "model_signal": "bearish"},
        {"symbol": "B", "direction": "long", "entry_price": 50, "exit_price": 52, "stop_loss": 48, "target": 60, "entry_date": "2026-01-01T16:00", "exit_date": "2026-01-03T10:00", "emotion_entry": "revenge", "rule_followed": True, "model_signal": "bullish"},
        {"symbol": "C", "direction": "short", "entry_price": 80, "exit_price": 76, "stop_loss": 84, "target": 70, "entry_date": "2026-01-01T17:00", "exit_date": "2026-01-04T10:00", "emotion_entry": "calm", "rule_followed": True, "model_signal": "bearish"},
    ]
    r = journal.analyze(entries)
    names = {p["pattern"] for p in r["patterns"]}
    assert {"revenge_trading", "stop_not_honored", "rule_violation", "winner_cutting"} <= names
    groups = {g["group"]: g for g in r["vs_model"]}
    assert groups["with the model"]["win_rate"] == 1.0
    assert groups["against the model"]["win_rate"] == 0.0
    assert 0 <= r["score"] <= 100


def test_sanitize_handles_numpy_and_nan():
    out = sanitize({"a": np.float64("nan"), "b": np.bool_(True), "c": np.arange(3), "d": float("inf"), "e": np.int64(4)})
    assert out == {"a": None, "b": True, "c": [0, 1, 2], "d": None, "e": 4}
    assert not any(isinstance(v, float) and math.isnan(v) for v in out.values() if v is not None)
