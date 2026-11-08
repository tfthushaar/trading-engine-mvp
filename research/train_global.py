"""
Train the global ensemble offline with PyTorch, export it to the NumPy engine format, and write a model card.

    .venv-research/Scripts/python -m research.train_global

Protocol (the 2024+ test period is used only for the final report):
  1. Train on data to 2021, validate on 2022-2023: choose the number of epochs for each architecture.
  2. Refit on all data to 2023 for that many epochs, once per random seed.
  3. Average seeds within an architecture and architectures within the ensemble, then score the test period.

Outputs (served by the API without PyTorch):
    backend/dl/weights/global_v1.npz         tensors, key "<member>/s<seed>/<i>" in NumPy parameter order
    backend/dl/weights/global_manifest.json  model card: data, splits, members, test metrics, calibration, backtest
"""
from __future__ import annotations

import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from backend.dl import evaluate as ev
from backend.dl.architectures import ARCHITECTURES, build_model, resolve_params
from backend.dl.global_model import WEIGHTS_DIR
from backend.dl.panel import EXTENDED_FEATURES, GLOBAL_FEATURES, MARKET_SYMBOLS, TRAIN_UNIVERSE, UNIVERSE, build_panel  # noqa: F401
from backend.dl.train import predict
from backend.market import data as md
from backend.strategies import engine
from research.torch_models import build_torch

# Chosen by research/experiments.py on walk-forward validation (see experiment_results.json)
CONFIG = {
    "features": GLOBAL_FEATURES,
    "extended_universe": True,
    "window": 30,
    "lr": 5e-4,
    "weight_decay": 1e-3,
    "dropout": None,          # None keeps each architecture's own value below
    "seeds": [0, 1, 2],
    "max_epochs": 12,
    "chosen": "more_symbols",
}
HORIZON = 5
YEARS = 15
TRAIN_END, VAL_END = "2021-12-31", "2023-12-31"
MEMBERS = [
    ("lstm", {"hidden": 48, "layers": 1, "dropout": 0.2}),
    ("gru", {"hidden": 48, "layers": 1, "dropout": 0.2}),
    ("cnn", {"channels": 32, "layers": 4, "kernel": 3, "dropout": 0.2}),
    ("transformer", {"d_model": 32, "heads": 4, "layers": 2, "ff": 64, "dropout": 0.1}),
]
RESULTS = Path(__file__).resolve().parent / "experiment_results.json"


def _forward(model, X, batch=2048):
    return torch.cat([model(X[i : i + batch]).squeeze(-1) for i in range(0, len(X), batch)])


def _run(arch, params, P, epochs, validate, seed=0, batch=512, patience=3):
    """One training run. With validate=True, stop early on the validation loss and keep the best weights."""
    torch.manual_seed(seed)
    tr, va = P["split"] == 0, P["split"] == 1
    Xtr, ytr = torch.tensor(P["X"][tr]), torch.tensor(P["y"][tr])
    Xva, yva = torch.tensor(P["X"][va]), torch.tensor(P["y"][va])
    model = build_torch(arch, CONFIG["window"], len(CONFIG["features"]), params).float()
    opt = torch.optim.AdamW(model.parameters(), lr=CONFIG["lr"], weight_decay=CONFIG["weight_decay"])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(epochs, 1), eta_min=CONFIG["lr"] * 0.05)
    lossf = torch.nn.BCEWithLogitsLoss()
    g = torch.Generator().manual_seed(seed)
    best, best_state, best_epoch, wait, hist = float("inf"), None, epochs, 0, []
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
        rec = {"epoch": ep + 1, "train_loss": round(tot / len(Xtr), 5)}
        if validate:
            model.eval()
            with torch.no_grad():
                vl = float(lossf(_forward(model, Xva), yva))
            rec["val_loss"] = round(vl, 5)
            if vl < best - 1e-5:
                best, best_epoch, wait = vl, ep + 1, 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                wait += 1
        hist.append(rec)
        print(f"  {arch:12s} seed {seed} epoch {ep + 1:2d} {rec} ({time.time() - t0:.1f}s)", flush=True)
        if validate and wait >= patience:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return model, hist, best, best_epoch


def portfolio_backtest(frame, threshold=0.55, cost_bps=5.0):
    """Equal-weight across symbols each day: long the symbols the model is bullish on vs holding all."""
    df = frame.dropna(subset=["nxt"])
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
    torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
    t_all = time.time()
    feats, W = CONFIG["features"], CONFIG["window"]
    symbols = sorted(set(UNIVERSE) | (set(TRAIN_UNIVERSE) if CONFIG["extended_universe"] else set()))
    print(f"downloading {len(symbols)} symbols ({YEARS}y)...", flush=True)
    data = md.histories(symbols + MARKET_SYMBOLS, period=f"{YEARS}y")
    market = {s: data[s] for s in MARKET_SYMBOLS}
    dfs = {s: data[s] for s in symbols if s in data}

    # Step 1: choose epochs on validation (2024+ rows are split 2 and are not touched here)
    A = build_panel(dfs, market, feats, W, HORIZON, TRAIN_END, VAL_END)
    val_dates = A["date"][A["split"] == 1].tolist()
    splits = {"val": {"start": min(val_dates), "end": max(val_dates), "n": len(val_dates)}}
    chosen = {}
    for arch, params in MEMBERS:
        p = {**params, **({"dropout": CONFIG["dropout"]} if CONFIG["dropout"] is not None else {})}
        _, hist, best, best_epoch = _run(arch, p, A, CONFIG["max_epochs"], validate=True)
        chosen[arch] = {"params": p, "history": hist, "best_val_loss": best, "epochs": max(best_epoch, 2)}
    del A

    # Step 2: refit on everything to 2023
    P = build_panel(dfs, market, feats, W, HORIZON, VAL_END, VAL_END)
    train_dates = P["date"][P["split"] == 0].tolist()
    splits["train"] = {"start": min(train_dates), "end": max(train_dates), "n": len(train_dates)}
    te = (P["split"] == 2) & np.isin(P["sym"], list(UNIVERSE))  # report on the 48 symbols the product displays
    test_dates = P["date"][te].tolist()
    splits["test"] = {"start": min(test_dates), "end": max(test_dates), "n": len(test_dates)}
    Xte, yte = P["X"][te], P["y"][te].astype(float)
    arrays, members, member_probs = {}, [], []
    for arch, _ in MEMBERS:
        c = chosen[arch]
        seed_probs, parity, exported = [], 0.0, []
        for seed in CONFIG["seeds"]:
            model, _, _, _ = _run(arch, c["params"], P, c["epochs"], validate=False, seed=seed)
            with torch.no_grad():
                prob_t = torch.sigmoid(_forward(model, torch.tensor(Xte))).numpy().astype(float)
            exported = [t.numpy().astype(np.float32) for t in model.export("value")]
            nm, _ = build_model(arch, W, len(feats), c["params"], seed=0)
            for q, a in zip(nm.parameters(), exported):
                q.value[...] = a
            prob_n = 1 / (1 + np.exp(-predict(nm, Xte[:1000].astype(float))))
            parity = max(parity, float(np.abs(prob_n - prob_t[:1000]).max()))
            for i, a in enumerate(exported):
                arrays[f"{arch}/s{seed}/{i}"] = a
            seed_probs.append(prob_t)
        prob = np.mean(seed_probs, axis=0)
        m = ev.classification_metrics(prob, yte)
        members.append({
            "id": arch, "arch": arch, "name": ARCHITECTURES[arch]["name"], "params": resolve_params(arch, c["params"]), "seeds": CONFIG["seeds"],
            "n_tensors": len(exported), "n_params": int(sum(a.size for a in exported)), "best_val_loss": round(c["best_val_loss"], 5),
            "epochs": c["epochs"], "history": c["history"], "test": m, "parity_max_abs_diff": parity,
        })
        member_probs.append(prob)
        print(f"  {arch}: test acc {m['accuracy']} auc {m['auc']} logloss {m['log_loss']} parity {parity:.2e}", flush=True)

    ens = np.mean(member_probs, axis=0)
    base_rate = float(P["y"][P["split"] == 0].mean())
    edges = np.quantile(ens, np.linspace(0, 1, 11))
    fwd = P["ret"][te]
    deciles = []
    for i in range(10):
        q = (ens >= edges[i]) & ((ens <= edges[i + 1]) if i == 9 else (ens < edges[i + 1]))
        deciles.append({"decile": i + 1, "lo": round(float(edges[i]), 5), "hi": round(float(edges[i + 1]), 5), "n": int(q.sum()),
                        "up_frequency": round(float(yte[q].mean()), 4), "mean_fwd_return": round(float(fwd[q].mean()), 6)})
    frame = pd.DataFrame({"date": P["date"][te], "sym": P["sym"][te], "nxt": P["nxt"][te], "p": ens})
    bt = portfolio_backtest(frame, threshold=0.55)
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(WEIGHTS_DIR / "global_v1.npz", **arrays)
    selection = None
    if RESULTS.exists():
        selection = {k: {x: v[x] for x in ("mean_auc", "min_fold_auc", "mean_log_loss", "mean_top_decile_up", "symbols", "n_features")} for k, v in json.loads(RESULTS.read_text()).items()}
    manifest = {
        "version": "global-v2",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "weights_file": "global_v1.npz",
        "task": "classification",
        "target": f"P(close in {HORIZON} trading days > close today)",
        "window": W, "horizon": HORIZON, "features": feats,
        "mean": [float(x) for x in P["mean"]], "std": [float(x) for x in P["std"]],
        "universe": P["symbols"], "splits": splits, "members": members,
        "ensemble": {
            "method": f"mean over {len(MEMBERS)} architectures, {len(CONFIG['seeds'])} seeds each",
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
            "dates": bt["model"]["dates"][::5], "equity": {k: v["equity"][::5] for k, v in bt.items()},
        },
        "selection": {"method": "walk-forward validation on data to 2023 only", "chosen": CONFIG["chosen"], "candidates": selection},
        "training": {"framework": f"PyTorch {torch.__version__}", "optimizer": f"AdamW(lr={CONFIG['lr']}, wd={CONFIG['weight_decay']}), cosine, clip 1.0, batch 512; epochs chosen on validation, then refit through 2023",
                     "python": platform.python_version(), "seconds": round(time.time() - t_all, 1)},
    }
    (WEIGHTS_DIR / "global_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps({"ensemble": manifest["ensemble"], "backtest": manifest["backtest"]["metrics"], "top": deciles[-1], "bottom": deciles[0]}, indent=1))
    print(f"done in {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main()
