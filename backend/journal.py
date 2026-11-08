"""Trade journal analytics (stateless: entries come from the visitor's browser)."""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

EMOTIONS = ["calm", "confident", "anxious", "fomo", "revenge", "bored"]


def _pnl_pct(e: dict) -> float | None:
    if e.get("exit_price") in (None, "") or not e.get("entry_price"):
        return None
    ep, xp = float(e["entry_price"]), float(e["exit_price"])
    r = (xp / ep - 1) * 100
    return -r if e.get("direction") == "short" else r


def analyze(entries: list[dict]) -> dict:
    rows = []
    for e in entries[:2000]:
        try:
            rows.append({**e, "entry_date": pd.Timestamp(e["entry_date"]), "exit_date": pd.Timestamp(e["exit_date"]) if e.get("exit_date") else None, "pnl_pct": _pnl_pct(e)})
        except Exception:
            continue
    if not rows:
        return {"score": None, "message": "Log trades to see your statistics and behavioural patterns."}
    df = pd.DataFrame(rows).sort_values("entry_date")
    closed = df[df["pnl_pct"].notna()]
    wins, losses = closed[closed["pnl_pct"] > 0], closed[closed["pnl_pct"] <= 0]
    stats = {
        "total": int(len(df)), "open": int(df["pnl_pct"].isna().sum()), "closed": int(len(closed)),
        "win_rate": round(float(len(wins) / len(closed)), 4) if len(closed) else None,
        "avg_win_pct": round(float(wins["pnl_pct"].mean()), 3) if len(wins) else None,
        "avg_loss_pct": round(float(losses["pnl_pct"].mean()), 3) if len(losses) else None,
        "expectancy_pct": round(float(closed["pnl_pct"].mean()), 3) if len(closed) else None,
        "profit_factor": round(float(wins["pnl_pct"].sum() / -losses["pnl_pct"].sum()), 3) if len(losses) and losses["pnl_pct"].sum() < 0 else None,
        "best_pct": round(float(closed["pnl_pct"].max()), 3) if len(closed) else None,
        "worst_pct": round(float(closed["pnl_pct"].min()), 3) if len(closed) else None,
    }
    patterns = []

    # Revenge trading: two or more new entries within 24h after a loss worse than -1.5%
    revenge = 0
    for _, row in closed[closed["pnl_pct"] < -1.5].iterrows():
        t0 = row["exit_date"] or row["entry_date"]
        later = df[(df["entry_date"] > t0) & (df["entry_date"] <= t0 + timedelta(hours=24))]
        if len(later) >= 2:
            revenge += 1
    if revenge:
        patterns.append({"pattern": "revenge_trading", "severity": "high" if revenge >= 3 else "medium", "count": revenge,
                         "description": f"{revenge} time(s) you opened two or more trades within a day of a loss larger than 1.5%."})
    # Overtrading: days with trade count > mean + 2 sd
    per_day = df.groupby(df["entry_date"].dt.date).size()
    if len(per_day) >= 5 and per_day.std() > 0:
        days = int((per_day > per_day.mean() + 2 * per_day.std()).sum())
        if days:
            patterns.append({"pattern": "overtrading", "severity": "medium", "count": days, "description": f"{days} day(s) with far more trades than your usual pace."})
    # Winner cutting: winners closed before reaching half the planned target
    cut = 0
    for _, row in wins.iterrows():
        try:
            planned = abs(float(row["target"]) - float(row["entry_price"]))
            got = abs(float(row["exit_price"]) - float(row["entry_price"]))
            if planned > 0 and got < 0.5 * planned:
                cut += 1
        except (TypeError, ValueError, KeyError):
            pass
    if cut:
        patterns.append({"pattern": "winner_cutting", "severity": "medium" if cut >= 3 else "low", "count": cut, "description": f"{cut} winner(s) closed before reaching half of the planned target."})
    # Stop not honoured: losses beyond the planned stop
    beyond = 0
    for _, row in losses.iterrows():
        try:
            sp, xp = float(row["stop_loss"]), float(row["exit_price"])
            if (row.get("direction") != "short" and xp < sp * 0.995) or (row.get("direction") == "short" and xp > sp * 1.005):
                beyond += 1
        except (TypeError, ValueError, KeyError):
            pass
    if beyond:
        patterns.append({"pattern": "stop_not_honored", "severity": "high" if beyond >= 2 else "medium", "count": beyond, "description": f"{beyond} loss(es) exited beyond the planned stop."})
    # Rule violations and emotional entries
    broke = int((df.get("rule_followed") == False).sum()) if "rule_followed" in df else 0  # noqa: E712
    if broke:
        patterns.append({"pattern": "rule_violation", "severity": "high" if broke >= 3 else "medium", "count": broke, "description": f"You marked {broke} trade(s) as not following your rules."})
    emo = df["emotion_entry"].isin(["fomo", "revenge", "anxious"]).sum() if "emotion_entry" in df else 0
    if emo >= 2:
        patterns.append({"pattern": "emotional_entry", "severity": "medium", "count": int(emo), "description": f"{int(emo)} entries were made feeling FOMO, revenge or anxiety."})

    # Emotion vs outcome table
    by_emotion = []
    if "emotion_entry" in closed:
        for emo_name, g in closed.groupby("emotion_entry"):
            by_emotion.append({"emotion": emo_name, "trades": int(len(g)), "win_rate": round(float((g["pnl_pct"] > 0).mean()), 3), "avg_pct": round(float(g["pnl_pct"].mean()), 3)})

    # Human vs neural model: did trades taken with the model's signal do better than trades against it?
    vs_model = []
    if "model_signal" in closed:
        def side(row):
            ms = row.get("model_signal")
            if ms not in ("bullish", "bearish"):
                return "model neutral"
            long = row.get("direction") != "short"
            return "with the model" if (ms == "bullish") == long else "against the model"

        tagged = closed[closed["model_signal"].notna()].copy()
        if len(tagged):
            tagged["side"] = tagged.apply(side, axis=1)
            for name, g in tagged.groupby("side"):
                vs_model.append({"group": name, "trades": int(len(g)), "win_rate": round(float((g["pnl_pct"] > 0).mean()), 3), "avg_pct": round(float(g["pnl_pct"].mean()), 3)})

    # Discipline score
    rated = df["rule_followed"].dropna() if "rule_followed" in df else pd.Series(dtype=float)
    adherence = float(rated.mean()) if len(rated) else 0.5
    score = 70 + (adherence - 0.5) * 30
    score -= sum(10 if p["severity"] == "high" else 5 if p["severity"] == "medium" else 2 for p in patterns)
    if stats["win_rate"] and stats["win_rate"] > 0.55:
        score += 5
    if stats["profit_factor"] and stats["profit_factor"] > 1.5:
        score += 5
    score = float(np.clip(score, 0, 100))
    monthly = []
    if len(closed):
        for m, g in closed.groupby(closed["entry_date"].dt.to_period("M")):
            monthly.append({"month": str(m), "trades": int(len(g)), "win_rate": round(float((g["pnl_pct"] > 0).mean()), 3), "return_pct": round(float(g["pnl_pct"].sum()), 3)})
    equity = closed.sort_values("exit_date" if closed["exit_date"].notna().all() else "entry_date")["pnl_pct"].cumsum().round(3).tolist()
    return {
        "score": round(score, 1), "grade": "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D",
        "rule_adherence": round(adherence, 3), "stats": stats, "patterns": patterns, "by_emotion": by_emotion,
        "monthly": monthly, "equity_pct": equity, "vs_model": vs_model,
    }
