"""
Train the global ensemble offline with PyTorch, export it to the NumPy engine format, and write a model card.

    .venv-research/Scripts/python -m research.train_global [--epochs 25] [--years 15]

Outputs (committed to the repo, served by the API without PyTorch):
    backend/dl/weights/global_v1.npz         exported tensors, key "<member>/<i>" in NumPy parameter order
    backend/dl/weights/global_manifest.json  model card: data, splits, members, test metrics, calibration, backtest
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch

from backend.dl import evaluate as ev
from backend.dl.architectures import ARCHITECTURES, build_model, resolve_params
from backend.dl.global_model import WEIGHTS_DIR
from backend.dl.panel import GLOBAL_FEATURES, MARKET_SYMBOLS, UNIVERSE, build_panel
from backend.dl.train import predict
from backend.market import data as md
from backend.strategies import engine
from research.torch_models import build_torch

WINDOW, HORIZON = 30, 5
TRAIN_END, VAL_END = "2021-12-31", "2023-12-31"
MEMBERS = [
    ("lstm", {"hidden": 48, "layers": 1, "dropout": 0.2}),
    ("gru", {"hidden": 48, "layers": 1, "dropout": 0.2}),
    ("cnn", {"channels": 32, "layers": 4, "kernel": 3, "dropout": 0.2}),
    ("transformer", {"d_model": 32, "heads": 4, "layers": 2, "ff": 64, "dropout": 0.1}),
]


def fit(arch, params, P, epochs, seed=0, batch=512, lr=5e-4, wd=1e-3, patience=3):
    torch.manual_seed(seed)
    tr, va = P["split"] == 0, P["split"] == 1
    Xtr, ytr = torch.tensor(P["X"][tr]), torch.tensor(P["y"][tr])
    Xva, yva = torch.tensor(P["X"][va]), torch.tensor(P["y"][va])
    model = build_torch(arch, WINDOW, len(GLOBAL_FEATURES), params).float()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=lr * 0.05)
    lossf = torch.nn.BCEWithLogitsLoss()
    best, best_state, wait, hist = float("inf"), None, 0, []
    g = torch.Generator().manual_seed(seed)
    for ep in range(epochs):
        t0 = time.time()
        model.train()
        perm = torch.randperm(len(Xtr), generator=g)
        tot = 0.0
        for s in range(0, len(perm), batch):
            b = perm[s : s + batch]
            opt.zero_grad()
            loss = lossf(model(Xtr[b]).squeeze(-1), ytr[b])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tot += float(loss) * len(b)
        sched.step()
        model.eval()
        with torch.no_grad():
            vl = float(lossf(model(Xva).squeeze(-1), yva))
        hist.append({"epoch": ep + 1, "train_loss": round(tot / len(Xtr), 5), "val_loss": round(vl, 5)})
        print(f"  {arch:12s} epoch {ep + 1:2d}  train {tot / len(Xtr):.5f}  val {vl:.5f}  ({time.time() - t0:.1f}s)", flush=True)
        if vl < best - 1e-5:
            best, wait = vl, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            wait += 1
            if wait >= patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    return model, hist, best


def portfolio_backtest(P, prob, test_mask, threshold=0.55, cost_bps=5.0):
    """Equal-weight across symbols each day: long the symbols the model is bullish on vs holding all."""
    df = pd.DataFrame({"date": P["date"][test_mask], "sym": P["sym"][test_mask], "nxt": P["nxt"][test_mask], "p": prob})
    df = df.dropna(subset=["nxt"])
    out = {}
    for name, posf in {"model": lambda p: (p >= threshold).astype(float), "buy_hold": lambda p: np.ones_like(p)}.items():
        rets = []
        for sym, g in df.groupby("sym"):
            g = g.sort_values("date")
            r = engine.run_positions(g["nxt"].to_numpy(), posf(g["p"].to_numpy()), cost_bps if name == "model" else 0.0)
            rets.append(pd.Series(r["returns"], index=g["date"].to_numpy(), name=sym))
        daily = pd.concat(rets, axis=1).mean(axis=1).sort_index()
        out[name] = {"metrics": engine.performance(daily.to_numpy()), "equity": np.round(np.cumprod(1 + daily.to_numpy()), 5).tolist(), "dates": list(daily.index)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--years", type=int, default=15)
    args = ap.parse_args()
    torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))

    t_all = time.time()
    symbols = list(UNIVERSE)
    print(f"downloading {len(symbols)} symbols + market ({args.years}y)...", flush=True)
    data = md.histories(symbols + MARKET_SYMBOLS, period=f"{args.years}y")
    market = {s: data[s] for s in MARKET_SYMBOLS}
    dfs = {s: data[s] for s in symbols if s in data}
    P = build_panel(dfs, market, GLOBAL_FEATURES, WINDOW, HORIZON, TRAIN_END, VAL_END)
    counts = {k: int((P["split"] == i).sum()) for i, k in enumerate(["train", "val", "test"])}
    print(f"panel: {len(P['y'])} samples {counts} from {len(P['symbols'])} symbols", flush=True)

    te = P["split"] == 2
    Xte, yte = P["X"][te], P["y"][te].astype(float)
    arrays, members, member_probs = {}, [], []
    for arch, params in MEMBERS:
        model, hist, best_val = fit(arch, params, P, args.epochs)
        with torch.no_grad():
            prob_t = torch.sigmoid(model(torch.tensor(Xte)).squeeze(-1)).numpy().astype(float)
        exported = [t.numpy().astype(np.float32) for t in model.export("value")]
        # Parity on real test windows: NumPy engine vs PyTorch, same exported weights
        nm, _ = build_model(arch, WINDOW, len(GLOBAL_FEATURES), params, seed=0)
        for p, a in zip(nm.parameters(), exported):
            p.value[...] = a
        prob_n = 1 / (1 + np.exp(-predict(nm, Xte[:2000].astype(float))))
        parity = float(np.abs(prob_n - prob_t[:2000]).max())
        mid = f"{arch}"
        for i, a in enumerate(exported):
            arrays[f"{mid}/{i}"] = a
        m = ev.classification_metrics(prob_t, yte)
        members.append({
            "id": mid, "arch": arch, "name": ARCHITECTURES[arch]["name"], "params": resolve_params(arch, params),
            "n_tensors": len(exported), "n_params": int(sum(a.size for a in exported)),
            "best_val_loss": round(best_val, 5), "epochs": len(hist), "history": hist,
            "test": m, "parity_max_abs_diff": parity,
        })
        member_probs.append(prob_t)
        print(f"  {arch}: test acc {m['accuracy']} auc {m['auc']} logloss {m['log_loss']}  parity {parity:.2e}", flush=True)

    ens = np.mean(member_probs, axis=0)
    base_rate = float(P["y"][P["split"] == 0].mean())
    # Confidence deciles on held-out test data: how often each band of model probability was followed by a rise
    edges = np.quantile(ens, np.linspace(0, 1, 11))
    fwd = P["ret"][te]
    deciles = []
    for i in range(10):
        m = (ens >= edges[i]) & ((ens <= edges[i + 1]) if i == 9 else (ens < edges[i + 1]))
        deciles.append({
            "decile": i + 1, "lo": round(float(edges[i]), 5), "hi": round(float(edges[i + 1]), 5), "n": int(m.sum()),
            "up_frequency": round(float(yte[m].mean()), 4), "mean_fwd_return": round(float(fwd[m].mean()), 6),
        })
    bt = portfolio_backtest(P, ens, te)
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(WEIGHTS_DIR / "global_v1.npz", **arrays)
    split_dates = {}
    for i, k in enumerate(["train", "val", "test"]):
        d = P["date"][P["split"] == i]
        split_dates[k] = {"start": min(d.tolist()), "end": max(d.tolist()), "n": int(len(d))}
    manifest = {
        "version": "global-v1",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "weights_file": "global_v1.npz",
        "task": "classification",
        "target": f"P(close in {HORIZON} trading days > close today)",
        "window": WINDOW,
        "horizon": HORIZON,
        "features": GLOBAL_FEATURES,
        "mean": [float(x) for x in P["mean"]],
        "std": [float(x) for x in P["std"]],
        "universe": P["symbols"],
        "splits": split_dates,
        "members": members,
        "ensemble": {
            "method": "mean of member probabilities",
            "test": ev.classification_metrics(ens, yte),
            "baseline_train_base_rate": ev.classification_metrics(np.full(len(yte), base_rate), yte),
            "test_up_rate": round(float(yte.mean()), 4),
        },
        "calibration": ev.calibration(ens, yte, bins=8),
        "deciles": deciles,
        "test_base_rate": round(float(yte.mean()), 4),
        "signal_rule": "bullish = top two confidence deciles, bearish = bottom two, neutral otherwise (deciles from the test period)",
        "backtest": {
            "rule": "per symbol: long when ensemble P(up) >= 0.55, else flat; 5 bps per change; equal-weight across symbols",
            "metrics": {k: v["metrics"] for k, v in bt.items()},
            "dates": bt["model"]["dates"][::5],
            "equity": {k: v["equity"][::5] for k, v in bt.items()},
        },
        "training": {"framework": f"PyTorch {torch.__version__}", "optimizer": "AdamW(lr=5e-4, wd=1e-3), cosine, clip 1.0, batch 512, early stop on val loss (patience 3)", "python": platform.python_version(), "seconds": round(time.time() - t_all, 1)},
    }
    (WEIGHTS_DIR / "global_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps({"ensemble": manifest["ensemble"], "backtest": manifest["backtest"]["metrics"]}, indent=1))
    print(f"done in {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main()
