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


def test_valid_symbols_drops_malformed_entries():
    from backend.market import data as md

    assert md.valid_symbols(["aapl", "BAD!!", "AAPL", " msft ", "", "^VIX", "GC=F"]) == ["AAPL", "MSFT", "^VIX", "GC=F"]


def test_failed_lookups_are_not_cached():
    from backend.market import data as md

    calls = []

    def flaky():
        calls.append(1)
        return {} if len(calls) == 1 else {"AAPL": 1}

    assert md.cached("test:flaky", 300, flaky) == {}
    assert md.cached("test:flaky", 300, flaky) == {"AAPL": 1}
    assert md.cached("test:flaky", 300, flaky) == {"AAPL": 1}
    assert len(calls) == 2


def test_train_config_rejects_bad_types_with_a_clear_message():
    from backend.dl.pipeline import train_config

    assert train_config({"epochs": "12", "lr": 0.01, "unknown": 1, "seed": None}).epochs == 12
    with pytest.raises(ValueError, match="epochs"):
        train_config({"epochs": "abc"})
    with pytest.raises(ValueError, match="loss"):
        train_config({"loss": "nope"})


def test_time_budget_stops_inside_an_epoch(monkeypatch):
    """A fake clock jumps 1s per reading, so a 2s budget must end the very first epoch after a few batches."""
    import types

    import backend.dl.train as train_module

    ticks = iter(range(100000))
    monkeypatch.setattr(train_module, "time", types.SimpleNamespace(perf_counter=lambda: float(next(ticks))))
    ds = build_dataset(synthetic_ohlcv(1200), window=20, horizon=1)
    model, _ = build_model("mlp", 20, len(ds.features), {"hidden": 8}, seed=0)
    fit = train(model, ds, TrainConfig(epochs=50, batch_size=8, patience=50, time_budget_s=2.0))
    assert fit["stopped"] == "time_budget"
    assert fit["epochs_run"] == 1


def test_trade_return_includes_the_exit_cost():
    res = engine.run_positions(np.array([0.10, 0.0, 0.0]), np.array([1, 0, 0]), cost_bps=100)
    assert res["n_trades"] == 1
    assert res["trade_returns"][0] == pytest.approx(0.10 * 0.99 + 0.10 * -0.01 - 0.01 + 0.0, abs=0.02)
    assert res["trade_returns"][0] < (1.10 - 0.01) - 1  # strictly worse than charging the entry only


def test_rule_values_must_be_numbers():
    df = synthetic_ohlcv()
    bad = [{"left": {"kind": "price"}, "op": ">", "right": {"kind": "value", "value": None}}]
    with pytest.raises(ValueError, match="number"):
        rules.rule_positions(df, bad, [])


def test_intraday_dataset_keeps_time_of_day():
    df = synthetic_ohlcv(1000)
    df.index = pd.date_range("2025-01-02 09:30", periods=1000, freq="h")
    ds = build_dataset(df, window=20, horizon=2)
    assert " " in ds.dates[0] and len(set(ds.dates)) == len(ds.dates)


def test_journal_ignores_missing_stop_and_target():
    e = {"symbol": "A", "direction": "long", "entry_price": 100, "exit_price": 101, "stop_loss": 0, "target": 0, "entry_date": "2026-01-01T10:00", "exit_date": "2026-01-02T10:00"}
    assert journal.analyze([e])["patterns"] == []


def test_portfolio_rejects_short_positions():
    from backend import portfolio

    with pytest.raises(ValueError, match="positive"):
        portfolio.analyze([{"symbol": "AAPL", "quantity": -5, "avg_cost": 100}])


def _market_with(symbol, frame):
    return {symbol: frame, "SPY": synthetic_ohlcv(seed=1), "^VIX": synthetic_ohlcv(seed=2)}


def test_zero_volume_instrument_is_reported_as_unsupported(monkeypatch):
    from backend.dl import global_model

    df = synthetic_ohlcv()
    df["Volume"] = 0.0
    monkeypatch.setattr(global_model.md, "histories", lambda *a, **k: _market_with("^TNX", df))
    with pytest.raises(global_model.NotScorable, match="no trading volume"):
        global_model.symbol_detail("^TNX")
    scan = global_model.scan(["^TNX"], mc_samples=0)
    assert scan["rows"] == [] and scan["skipped"] == [{"symbol": "^TNX", "reason": "no trading volume"}]


def test_short_history_and_unknown_symbols_get_accurate_errors(monkeypatch):
    from backend.dl import global_model
    from backend.market.data import MarketDataError

    monkeypatch.setattr(global_model.md, "histories", lambda *a, **k: _market_with("NEW", synthetic_ohlcv(40)))
    with pytest.raises(global_model.NotScorable, match="six months"):
        global_model.symbol_detail("NEW")
    monkeypatch.setattr(global_model.md, "histories", lambda *a, **k: _market_with("OTHER", synthetic_ohlcv()))
    with pytest.raises(MarketDataError, match="no price data"):
        global_model.symbol_detail("ZZZZZZ")


def test_lab_names_the_missing_volume_feature():
    df = synthetic_ohlcv()
    df["Volume"] = 0.0
    with pytest.raises(ValueError, match="volume_z"):
        build_dataset(df, window=20, horizon=5)
    assert build_dataset(df, features=["ret_1", "ret_5"], window=20, horizon=5).X.shape[2] == 2


def test_strategy_that_never_traded_cannot_outrank_one_that_lost():
    from backend.routers import strategies as router

    router_df = synthetic_ohlcv(seed=4)
    router_df["Volume"] = 0.0
    original = router._load
    router._load = lambda *a, **k: router_df
    try:
        result = router._compare(router.CompareRequest(symbol="SPY", period="2y"))
    finally:
        router._load = original
    assert result["note"] == rules.NO_VOLUME_NOTE
    trades = [s["trades"] for s in result["strategies"]]
    assert trades == sorted(trades, key=lambda t: t > 0, reverse=True)
    assert result["strategies"][-1]["trades"] == 0


def test_invalid_portfolio_symbol_stays_visible(monkeypatch):
    from backend import portfolio

    monkeypatch.setattr(portfolio.md, "histories", lambda *a, **k: {"AAPL": synthetic_ohlcv(), "SPY": synthetic_ohlcv(seed=1)})
    res = portfolio.analyze([{"symbol": "AAPL", "quantity": 1, "avg_cost": 50}, {"symbol": "BAD!!", "quantity": 1, "avg_cost": 50}])
    assert [p.get("error") for p in res["positions"] if p["symbol"] == "BAD!!"] == ["invalid symbol"]


def test_profile_replaces_a_zero_52_week_low(monkeypatch):
    import yfinance

    from backend.market import data as md

    class Ticker:
        def __init__(self, symbol):
            pass

        def get_info(self):
            return {"longName": "Yield index", "fiftyTwoWeekHigh": 5.4, "fiftyTwoWeekLow": 0.0}

    frame = synthetic_ohlcv()
    monkeypatch.setattr(yfinance, "Ticker", Ticker)
    monkeypatch.setattr(md, "history", lambda *a, **k: frame)
    profile = md.profile("ZEROLOW")
    assert profile["low_52w"] == float(frame["Low"].min()) and profile["high_52w"] == float(frame["High"].max())
