"""
Online inference for the pretrained global ensemble.

The ensemble members were trained offline in PyTorch (research/train_global.py) on the panel
universe, then exported to the NumPy layer format. Here they run on the from-scratch engine
(backend.dl.nn). No PyTorch at runtime.
"""
from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np

from backend.dl import nn
from backend.dl.architectures import build_model
from backend.dl.panel import MARKET_SYMBOLS, UNIVERSE, sliding, standardize, symbol_frame
from backend.dl.train import predict
from backend.market import data as md

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
MANIFEST = WEIGHTS_DIR / "global_manifest.json"
_lock = threading.Lock()


class GlobalModelUnavailable(RuntimeError):
    pass


class NotScorable(md.MarketDataError):
    """The symbol has prices, but the model cannot produce a meaningful forecast for it."""


NO_VOLUME = "no trading volume"
SHORT_HISTORY = "too little history"
NO_DATA = "no price data"
REASONS = {
    NO_VOLUME: "The neural model doesn't cover this instrument: it has no trading volume and isn't a stock or ETF.",
    SHORT_HISTORY: "The neural model needs about six months of trading history, and this symbol doesn't have that yet.",
}


@lru_cache(maxsize=1)
def load() -> dict:
    """Load the manifest and rebuild every ensemble member with its exported weights."""
    if not MANIFEST.exists():
        raise GlobalModelUnavailable("pretrained weights not found; run research/train_global.py")
    manifest = json.loads(MANIFEST.read_text())
    arrays = np.load(WEIGHTS_DIR / manifest["weights_file"])
    members = []
    for m in manifest["members"]:
        nets = []  # one network per training seed; a member's probability is their average
        for seed in m.get("seeds") or [None]:
            prefix = m["id"] if seed is None else f"{m['id']}/s{seed}"
            net, _ = build_model(m["arch"], manifest["window"], len(manifest["features"]), m["params"], seed=0)
            params = net.parameters()
            if len(params) != m["n_tensors"]:
                raise GlobalModelUnavailable(f"weight layout mismatch for {prefix}")
            for i, p in enumerate(params):
                arr = arrays[f"{prefix}/{i}"]
                if arr.shape != p.value.shape:
                    raise GlobalModelUnavailable(f"shape mismatch in {prefix} tensor {i}: {arr.shape} vs {p.value.shape}")
                p.value[...] = arr
            # Dropout layers need their own generators for MC sampling
            for layer in nn.iter_layers(net):
                if isinstance(layer, nn.Dropout):
                    layer.rng = np.random.default_rng(1234 + (seed or 0))
            nets.append(net)
        members.append({"id": m["id"], "arch": m["arch"], "name": m["name"], "nets": nets})
    return {
        "manifest": manifest,
        "members": members,
        "mean": np.array(manifest["mean"]),
        "std": np.array(manifest["std"]),
    }


def card() -> dict:
    """Public model card (no weights)."""
    return load()["manifest"]


def _decile(manifest: dict, prob: float) -> dict | None:
    """Locate prob among the test-period confidence deciles; report what historically followed."""
    ds = manifest.get("deciles") or []
    if not ds:
        return None
    row = ds[0] if prob < ds[0]["hi"] else ds[-1]
    for d in ds:
        if d["lo"] <= prob < d["hi"]:
            row = d
            break
    return {
        "decile": row["decile"], "range": [row["lo"], row["hi"]], "n": row["n"],
        "historical_up_frequency": row["up_frequency"], "mean_fwd_return": row["mean_fwd_return"],
        "base_rate": manifest.get("test_base_rate"),
    }


def _signal(manifest: dict, prob: float) -> str:
    d = _decile(manifest, prob)
    if d is None:
        return "bullish" if prob >= 0.55 else "bearish" if prob <= 0.45 else "neutral"
    return "bullish" if d["decile"] >= 9 else "bearish" if d["decile"] <= 2 else "neutral"


def _score_windows(windows: np.ndarray, mc_samples: int = 0) -> dict:
    g = load()
    probs, mc = [], []
    with _lock:  # layers cache activations, so forward passes are serialised per process
        for m in g["members"]:
            probs.append(np.mean([nn.sigmoid(predict(net, windows)) for net in m["nets"]], axis=0))
            if mc_samples:
                per_net = max(1, mc_samples // len(m["nets"]))  # keep total passes per member constant
                mc.append(np.stack([nn.sigmoid(predict(net, windows, training=True)) for net in m["nets"] for _ in range(per_net)]))
    probs = np.stack(probs)  # (M, N)
    out = {"members": probs, "ensemble": probs.mean(axis=0)}
    if mc_samples:
        allmc = np.concatenate(mc)  # (M*S, N)
        out["mc_std"] = allmc.std(axis=0)
        out["mc_p05"] = np.percentile(allmc, 5, axis=0)
        out["mc_p95"] = np.percentile(allmc, 95, axis=0)
    return out


def _attribution(window: np.ndarray) -> list[dict]:
    """
    Gradient x input on the latest window, summed over time, averaged over ensemble members.
    Positive values push the logit (and so P(up)) higher; negative values push it lower.
    """
    from backend.dl.data import FEATURES

    g = load()
    feats = g["manifest"]["features"]
    total = np.zeros(len(feats))
    with _lock:
        for m in g["members"]:
            for net in m["nets"]:
                net.forward(window, training=False)
                dx = net.backward(np.ones((len(window), 1)))
                net.zero_grad()
                total += (dx * window).sum(axis=1).mean(axis=0) / len(m["nets"])
    total /= len(g["members"])
    scale = np.abs(total).sum() or 1.0
    rows = [{"feature": f, "label": FEATURES.get(f, f), "contribution": round(float(v), 5), "share": round(float(abs(v) / scale), 4)} for f, v in zip(feats, total)]
    return sorted(rows, key=lambda r: abs(r["contribution"]), reverse=True)


def _frames(symbols: list[str], period: str = "1y") -> tuple[dict, list[dict]]:
    """Feature frames for the symbols the model can score, plus the rest with the reason for each."""
    g = load()
    feats = g["manifest"]["features"]
    window = g["manifest"]["window"]
    data = md.histories(list(symbols) + MARKET_SYMBOLS, period=period)
    market = {s: data[s] for s in MARKET_SYMBOLS if s in data}
    if len(market) < len(MARKET_SYMBOLS):
        raise md.MarketDataError("market data request failed: S&P 500 or VIX history is unavailable right now")
    frames, skipped = {}, []
    for s in symbols:
        df = data.get(s)
        if df is None or df.empty:
            skipped.append({"symbol": s, "reason": NO_DATA})
        elif float(df["Volume"].tail(60).sum()) == 0:
            skipped.append({"symbol": s, "reason": NO_VOLUME})
        else:
            f = symbol_frame(df, market, feats) if len(df) >= window + 60 else None
            if f is not None and len(f) >= window:
                frames[s] = (df, f)
            else:
                skipped.append({"symbol": s, "reason": SHORT_HISTORY})
    return frames, skipped


def scan(symbols: list[str] | None = None, mc_samples: int = 8) -> dict:
    """Score the latest window of every symbol. Returns rows sorted by ensemble probability."""
    g = load()
    man = g["manifest"]
    W = man["window"]
    syms = md.valid_symbols(symbols or list(UNIVERSE))
    frames, skipped = _frames(syms)
    if not frames:
        if all(x["reason"] == NO_DATA for x in skipped):
            raise md.MarketDataError("no price data for the requested symbols")
        return {
            "horizon_days": man["horizon"], "as_of": None,
            "model": {"version": man["version"], "trained_at": man["trained_at"], "members": [m["name"] for m in g["members"]]},
            "breadth": {"bullish": 0, "neutral": 0, "bearish": 0, "mean_prob_up": None, "base_rate": man.get("test_base_rate")},
            "signal_rule": man.get("signal_rule"), "rows": [], "skipped": skipped,
        }
    order = list(frames)
    batch = np.stack([standardize(f.to_numpy()[-W:], g["mean"], g["std"]) for _, f in frames.values()])
    sc = _score_windows(batch, mc_samples=mc_samples)
    rows = []
    for i, s in enumerate(order):
        df, f = frames[s]
        p = float(sc["ensemble"][i])
        member = {m["id"]: round(float(sc["members"][k, i]), 4) for k, m in enumerate(g["members"])}
        close = df["Close"]
        rows.append({
            "symbol": s,
            "name": UNIVERSE.get(s, (s, None))[0],
            "sector": UNIVERSE.get(s, (None, None))[1],
            "as_of": f.index[-1].strftime("%Y-%m-%d"),
            "price": round(float(close.iloc[-1]), 4),
            "change_pct": round(float(close.iloc[-1] / close.iloc[-2] - 1) * 100, 3) if len(close) > 1 else None,
            "return_1m": round(float(close.iloc[-1] / close.iloc[-22] - 1) * 100, 3) if len(close) > 22 else None,
            "prob_up": round(p, 4),
            "signal": _signal(man, p),
            "agreement": round(float((sc["members"][:, i] > 0.5).mean()), 3),
            "uncertainty": round(float(sc["mc_std"][i]), 4) if mc_samples else None,
            "members": member,
            "calibrated": _decile(man, p),
        })
    rows.sort(key=lambda r: r["prob_up"], reverse=True)
    probs = np.array([r["prob_up"] for r in rows])
    signals = [r["signal"] for r in rows]
    return {
        "horizon_days": man["horizon"],
        "as_of": max(r["as_of"] for r in rows),
        "model": {"version": man["version"], "trained_at": man["trained_at"], "members": [m["name"] for m in g["members"]]},
        "breadth": {
            "bullish": signals.count("bullish"),
            "neutral": signals.count("neutral"),
            "bearish": signals.count("bearish"),
            "mean_prob_up": round(float(probs.mean()), 4),
            "base_rate": man.get("test_base_rate"),
        },
        "signal_rule": man.get("signal_rule"),
        "rows": rows,
        "skipped": skipped,
    }


def symbol_detail(symbol: str, lookback: int = 120) -> dict:
    """Ensemble probability over the last `lookback` days plus the current forecast with MC-dropout bands."""
    g = load()
    man = g["manifest"]
    W = man["window"]
    sym = md.normalize_symbol(symbol)
    frames, skipped = _frames([sym], period="2y")
    if sym not in frames:
        reason = skipped[0]["reason"]
        if reason == NO_DATA:
            raise md.MarketDataError(f"no price data for {sym}")
        raise NotScorable(REASONS[reason])
    df, f = frames[sym]
    z = standardize(f.to_numpy(), g["mean"], g["std"])
    wins = sliding(z, W)[-lookback:]
    dates = [d.strftime("%Y-%m-%d") for d in f.index[W - 1 :][-lookback:]]
    hist = _score_windows(wins)
    now = _score_windows(wins[-1:], mc_samples=25)
    p = float(now["ensemble"][0])
    close = df["Close"].reindex(f.index[W - 1 :][-lookback:])
    return {
        "symbol": sym,
        "horizon_days": man["horizon"],
        "as_of": dates[-1],
        "prob_up": round(p, 4),
        "signal": _signal(man, p),
        "agreement": round(float((now["members"][:, 0] > 0.5).mean()), 3),
        "uncertainty": {"std": round(float(now["mc_std"][0]), 4), "p05": round(float(now["mc_p05"][0]), 4), "p95": round(float(now["mc_p95"][0]), 4)},
        "members": [{"id": m["id"], "name": m["name"], "prob_up": round(float(now["members"][k, 0]), 4)} for k, m in enumerate(g["members"])],
        "calibrated": _decile(man, p),
        "attribution": _attribution(wins[-1:]),
        "history": {"dates": dates, "prob_up": md.to_float_list(hist["ensemble"], 4), "close": md.to_float_list(close.to_numpy(), 4)},
        "in_universe": sym in UNIVERSE,
    }
