"""Portfolio analysis (stateless: positions come from the visitor's browser)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.dl.panel import UNIVERSE
from backend.market import data as md
from backend.strategies import engine

DISCLAIMER = "Educational risk analysis of the positions you entered. Not financial advice."


def _sector(sym: str) -> str:
    if sym in UNIVERSE:
        return UNIVERSE[sym][1]
    try:
        return md.profile(sym).get("sector") or "Other"
    except Exception:
        return "Other"


def analyze(positions: list[dict]) -> dict:
    pos = []
    for p in positions[:40]:
        try:
            sym = md.normalize_symbol(str(p.get("symbol", "")))
        except md.MarketDataError:
            continue
        qty = float(p.get("quantity") or 0)
        cost = float(p.get("avg_cost") or 0)
        if qty and cost >= 0:
            pos.append({"symbol": sym, "quantity": qty, "avg_cost": cost})
    if not pos:
        raise ValueError("add at least one position with a quantity")
    syms = sorted({p["symbol"] for p in pos})
    data = md.histories(syms + ["SPY"], period="1y")
    rows, total_value, total_cost = [], 0.0, 0.0
    for p in pos:
        df = data.get(p["symbol"])
        if df is None or df.empty:
            rows.append({**p, "error": "no price data"})
            continue
        last = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2]) if len(df) > 1 else last
        value, basis = last * p["quantity"], p["avg_cost"] * p["quantity"]
        total_value += value
        total_cost += basis
        rows.append({**p, "price": last, "value": value, "cost_basis": basis, "pnl": value - basis,
                     "pnl_pct": (value / basis - 1) * 100 if basis else None, "day_change_pct": (last / prev - 1) * 100, "day_pnl": (last - prev) * p["quantity"],
                     "sector": _sector(p["symbol"])})
    valid = [r for r in rows if "value" in r]
    for r in valid:
        r["weight"] = r["value"] / total_value if total_value else 0
    sectors: dict[str, float] = {}
    for r in valid:
        sectors[r["sector"]] = sectors.get(r["sector"], 0) + r["weight"]

    # Risk from value-weighted daily returns over the past year
    closes = pd.DataFrame({r["symbol"]: data[r["symbol"]]["Close"] for r in valid if r["symbol"] in data}).dropna()
    rets = closes.pct_change().dropna()
    w = np.array([sum(r["weight"] for r in valid if r["symbol"] == s) for s in closes.columns])
    risk, corr = {}, None
    if len(rets) > 30 and w.sum() > 0:
        pr = rets.to_numpy() @ (w / w.sum())
        perf = engine.performance(pr)
        var95 = float(np.percentile(pr, 5))
        cvar95 = float(pr[pr <= var95].mean())
        spy = data["SPY"]["Close"].pct_change().reindex(rets.index).dropna()
        aligned = pd.concat([pd.Series(pr, index=rets.index), spy], axis=1).dropna()
        beta = float(np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1] / aligned.iloc[:, 1].var()) if len(aligned) > 30 else None
        risk = {"var_95_1d": var95, "cvar_95_1d": cvar95, "var_95_1d_value": var95 * total_value, "beta_vs_spy": beta,
                "ann_vol": perf["ann_vol"], "max_drawdown_1y": perf["max_drawdown"], "sharpe_1y": perf["sharpe"], "return_1y": perf["total_return"]}
        if len(closes.columns) >= 2:
            cm = rets.corr()
            pairs = [(a, b, float(cm.loc[a, b])) for i, a in enumerate(cm.columns) for b in cm.columns[i + 1 :]]
            top = max(pairs, key=lambda x: abs(x[2]))
            corr = {"symbols": list(cm.columns), "matrix": np.round(cm.to_numpy(), 3).tolist(), "avg_pairwise": round(float(np.mean([p[2] for p in pairs])), 3),
                    "highest": {"pair": [top[0], top[1]], "corr": round(top[2], 3)}}

    # Neural signals per holding
    try:
        from backend.dl import global_model

        neural = {r["symbol"]: {k: r[k] for k in ("prob_up", "signal", "agreement", "calibrated")} for r in global_model.scan(syms, mc_samples=0)["rows"]}
    except Exception:
        neural = {}
    for r in valid:
        r["neural"] = neural.get(r["symbol"])

    # Health score: concentration, diversification, volatility
    hhi = float(sum(r["weight"] ** 2 for r in valid))
    top_sector = max(sectors.items(), key=lambda kv: kv[1]) if sectors else ("--", 0)
    score = 100.0
    notes = []
    if hhi > 0.25:
        score -= min(30, (hhi - 0.25) * 80)
        notes.append(f"Concentrated: effective number of positions is {1 / hhi:.1f}.")
    if top_sector[1] > 0.5:
        score -= 15
        notes.append(f"{top_sector[0]} is {top_sector[1] * 100:.0f}% of the portfolio.")
    if corr and corr["avg_pairwise"] > 0.6:
        score -= 15
        notes.append(f"Holdings move together (average correlation {corr['avg_pairwise']:.2f}).")
    if risk.get("ann_vol") and risk["ann_vol"] > 0.35:
        score -= 10
        notes.append(f"High volatility ({risk['ann_vol'] * 100:.0f}% annualised).")
    if len(valid) < 4:
        score -= 10
        notes.append("Fewer than four positions.")
    bull = sum(1 for r in valid if (r.get("neural") or {}).get("signal") == "bullish")
    bear = sum(1 for r in valid if (r.get("neural") or {}).get("signal") == "bearish")
    return {
        "positions": rows, "total_value": total_value, "total_cost": total_cost, "total_pnl": total_value - total_cost,
        "total_pnl_pct": (total_value / total_cost - 1) * 100 if total_cost else None,
        "day_pnl": sum(r.get("day_pnl", 0) for r in valid),
        "sectors": dict(sorted(sectors.items(), key=lambda kv: -kv[1])), "risk": risk, "correlation": corr,
        "concentration": {"hhi": round(hhi, 4), "effective_positions": round(1 / hhi, 2) if hhi else None},
        "health": {"score": round(max(0, score), 1), "notes": notes},
        "neural_summary": {"bullish": bull, "bearish": bear, "neutral": len(valid) - bull - bear},
        "disclaimer": DISCLAIMER,
    }
