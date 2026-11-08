"""Trade setup evaluator: scores an entry/stop/target plan from 0 to 100 with a letter grade."""
from __future__ import annotations

import numpy as np

from backend.market import data as md
from backend.market import indicators as ind


def _clip(x: float) -> float:
    return float(min(100.0, max(0.0, x)))


def evaluate(symbol: str, entry: float, stop: float, target: float, timeframe: str = "swing") -> dict:
    sym = md.normalize_symbol(symbol)
    if min(entry, stop, target) <= 0:
        raise ValueError("entry, stop and target must be positive prices")
    if target == entry:
        raise ValueError("the target must differ from the entry")
    direction = "long" if target > entry else "short"
    if (direction == "long" and stop >= entry) or (direction == "short" and stop <= entry):
        raise ValueError(f"for a {direction} trade the stop must be on the other side of the entry from the target")
    df = md.history(sym, period="2y")
    snap = ind.snapshot(df)
    c = df["Close"]
    atr = snap["atr_14"] or float((df["High"] - df["Low"]).tail(14).mean())
    last = snap["price"]
    risk, reward = abs(entry - stop), abs(target - entry)
    rr = reward / risk if risk else 0.0
    signals, warnings = [], []

    # 1. Risk/reward (30%)
    s_rr = _clip(rr / 3.0 * 100)
    if rr < 1.5:
        warnings.append(f"Reward-to-risk of {rr:.2f} is below 1.5; losses of the same frequency would outweigh wins.")
    else:
        signals.append(f"Reward-to-risk {rr:.2f}:1.")
    # 2. Trend alignment (25%)
    votes = [snap.get("above_sma_20"), snap.get("above_sma_50"), snap.get("above_sma_200")]
    aligned = sum(1 for v in votes if v is not None and (v if direction == "long" else not v))
    s_trend = aligned / 3 * 100
    if aligned == 3:
        signals.append(f"Price is {'above' if direction == 'long' else 'below'} its 20, 50 and 200-day averages, aligned with a {direction}.")
    elif aligned <= 1:
        warnings.append(f"The {direction} trade fights the prevailing trend ({aligned}/3 moving averages agree).")
    # 3. Momentum (15%)
    r = snap.get("rsi_14") or 50
    if direction == "long":
        s_mom = 90 if 45 <= r <= 65 else 70 if r < 45 else 25 if r > 75 else 50
        if r > 75:
            warnings.append(f"RSI {r:.0f} is overbought; late entries in extended moves carry pullback risk.")
    else:
        s_mom = 90 if 35 <= r <= 55 else 70 if r > 55 else 25 if r < 25 else 50
        if r < 25:
            warnings.append(f"RSI {r:.0f} is oversold; shorts into exhaustion often get squeezed.")
    # 4. Stop placement vs volatility (15%)
    stop_atr = risk / atr if atr else 0
    s_stop = 90 if 1.0 <= stop_atr <= 3.0 else 40 if stop_atr < 1.0 else 60
    if stop_atr < 1.0:
        warnings.append(f"The stop is {stop_atr:.1f} ATR away; normal daily noise ({atr:.2f}) can hit it.")
    else:
        signals.append(f"Stop sits {stop_atr:.1f} ATR from entry.")
    # 5. Target realism (10%): distance in ATR and vs 52-week range
    tgt_atr = reward / atr if atr else 0
    s_tgt = 85 if tgt_atr <= 6 else 55 if tgt_atr <= 12 else 25
    if direction == "long" and target > snap["high_52w"] * 1.05:
        warnings.append(f"Target is above the 52-week high ({snap['high_52w']:.2f}); it needs a breakout into new highs.")
        s_tgt -= 15
    # 6. Entry vs current price (5%)
    gap = abs(entry / last - 1)
    s_entry = 90 if gap <= 0.02 else 60 if gap <= 0.06 else 30
    if gap > 0.06:
        warnings.append(f"Entry is {gap * 100:.1f}% from the current price {last:.2f}; the setup may not trigger.")

    # Neural view: the ensemble's calibrated decile is a scored component
    neural = None
    s_neural = None
    try:
        from backend.dl import global_model

        d = global_model.symbol_detail(sym, lookback=20)
        neural = {k: d[k] for k in ("prob_up", "signal", "agreement", "calibrated", "horizon_days")}
        if d.get("calibrated"):
            dec = d["calibrated"]["decile"]
            s_neural = float(dec * 10 if direction == "long" else (11 - dec) * 10)
        agrees = (d["signal"] == "bullish" and direction == "long") or (d["signal"] == "bearish" and direction == "short")
        if agrees:
            signals.append(f"The neural ensemble leans the same way (P(up) {d['prob_up']:.2f}).")
        elif d["signal"] != "neutral":
            warnings.append(f"The neural ensemble leans the other way (P(up) {d['prob_up']:.2f}).")
    except Exception:
        warnings.append("The neural ensemble can't score this instrument, so the grade leaves it out.")

    parts = {"risk_reward": s_rr, "trend": s_trend, "momentum": s_mom, "stop_placement": s_stop, "target_realism": _clip(s_tgt), "entry_proximity": s_entry}
    weights = {"risk_reward": 0.25, "trend": 0.20, "momentum": 0.12, "stop_placement": 0.13, "target_realism": 0.10, "entry_proximity": 0.05}
    if s_neural is not None:
        parts["neural_agreement"] = s_neural
        weights["neural_agreement"] = 0.15
    norm = sum(weights.values())
    weights = {k: v / norm for k, v in weights.items()}
    score = round(sum(parts[k] * w for k, w in weights.items()), 1)
    grade = "A" if score >= 85 else "B" if score >= 72 else "C" if score >= 60 else "D" if score >= 48 else "F"
    vol = float(np.log(c).diff().tail(20).std())
    return {
        "symbol": sym, "direction": direction, "timeframe": timeframe, "score": score, "grade": grade,
        "components": [{"name": k.replace("_", " "), "score": round(v, 1), "weight": round(weights[k], 3)} for k, v in parts.items()],
        "risk_reward": {"risk_per_share": round(risk, 4), "reward_per_share": round(reward, 4), "ratio": round(rr, 2),
                        "risk_pct": round(risk / entry * 100, 2), "reward_pct": round(reward / entry * 100, 2),
                        "breakeven_win_rate": round(1 / (1 + rr), 3) if rr else None},
        "context": {"price": last, "atr_14": round(atr, 4), "stop_atr": round(stop_atr, 2), "target_atr": round(tgt_atr, 2), "rsi_14": snap.get("rsi_14"),
                    "trend": snap["trend"], "high_52w": snap["high_52w"], "low_52w": snap["low_52w"], "daily_vol": round(vol, 4)},
        "signals": signals, "warnings": warnings, "neural": neural,
    }
