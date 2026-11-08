"""
Model selection for the global ensemble, using walk-forward validation only.

Price history is cut at the end of 2023 before anything else happens, so the 2024+ test period cannot
influence a decision. Each candidate is scored on two folds with different market regimes:
    train to 2019 -> validate 2020-2021      train to 2021 -> validate 2022-2023

    .venv-research/Scripts/python -m research.experiments
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from backend.dl import evaluate as ev
from backend.dl.panel import EXTENDED_FEATURES, GLOBAL_FEATURES, MARKET_SYMBOLS, TRAIN_UNIVERSE, UNIVERSE, build_panel
from backend.market import data as md
from research.torch_models import build_torch

CUTOFF = pd.Timestamp("2023-12-31")
FOLDS = [("2019-12-31", "2021-12-31"), ("2021-12-31", "2023-12-31")]
OUT = Path(__file__).resolve().parent / "experiment_results.json"
ARCHS = {"gru": {"hidden": 48, "layers": 1, "dropout": 0.2}, "cnn": {"channels": 32, "layers": 4, "kernel": 3, "dropout": 0.2}}


def fit_score(arch, params, P, window, n_features, lr, wd, epochs=8, patience=3, batch=512, seed=0):
    torch.manual_seed(seed)
    tr, va = P["split"] == 0, P["split"] == 1
    Xtr, ytr = torch.tensor(P["X"][tr]), torch.tensor(P["y"][tr])
    Xva, yva = torch.tensor(P["X"][va]), torch.tensor(P["y"][va])
    model = build_torch(arch, window, n_features, params).float()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=lr * 0.05)
    lossf = torch.nn.BCEWithLogitsLoss()
    g = torch.Generator().manual_seed(seed)
    best, wait, best_prob, best_epoch = float("inf"), 0, None, 0
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(Xtr), generator=g)
        for s in range(0, len(perm), batch):
            b = perm[s : s + batch]
            opt.zero_grad()
            lossf(model(Xtr[b]).squeeze(-1), ytr[b]).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sched.step()
        model.eval()
        with torch.no_grad():
            logits = torch.cat([model(Xva[i : i + 2048]).squeeze(-1) for i in range(0, len(Xva), 2048)])
        loss = float(lossf(logits, yva))
        if loss < best - 1e-5:
            best, wait, best_epoch, best_prob = loss, 0, ep + 1, torch.sigmoid(logits).numpy().astype(float)
        else:
            wait += 1
            if wait >= patience:
                break
    y = P["y"][va].astype(float)
    m = ev.classification_metrics(best_prob, y)
    top = best_prob >= np.quantile(best_prob, 0.9)
    return {"auc": m["auc"], "log_loss": m["log_loss"], "accuracy": m["accuracy"], "top_decile_up": round(float(y[top].mean()), 4), "base_up": round(float(y.mean()), 4), "epoch": best_epoch}


def main():
    torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
    extended = sorted(set(TRAIN_UNIVERSE) | set(UNIVERSE))
    raw = md.histories(extended + MARKET_SYMBOLS, period="15y")
    data = {s: df[df.index <= CUTOFF] for s, df in raw.items()}  # nothing after 2023 is visible from here on
    market = {s: data[s] for s in MARKET_SYMBOLS}
    u48 = {s: data[s] for s in UNIVERSE if s in data}
    uall = {s: data[s] for s in extended if s in data}
    base = {"features": GLOBAL_FEATURES, "universe": u48, "window": 30, "lr": 5e-4, "wd": 1e-3, "dropout": None}
    candidates = {
        "baseline": {},
        "more_features": {"features": EXTENDED_FEATURES},
        "more_symbols": {"universe": uall},
        "more_regularisation": {"wd": 1e-2, "dropout": 0.4},
        "longer_window": {"window": 60},
        "features+symbols": {"features": EXTENDED_FEATURES, "universe": uall},
        "features+symbols+reg": {"features": EXTENDED_FEATURES, "universe": uall, "wd": 1e-2, "dropout": 0.4},
        "lower_lr+features+symbols": {"features": EXTENDED_FEATURES, "universe": uall, "lr": 2e-4},
    }
    results = {}
    for name, change in candidates.items():
        c = {**base, **change}
        t0 = time.time()
        rows = []
        for train_end, val_end in FOLDS:
            P = build_panel(c["universe"], market, c["features"], c["window"], 5, train_end, val_end)
            for arch, params in ARCHS.items():
                p = dict(params)
                if c["dropout"] is not None:
                    p["dropout"] = c["dropout"]
                rows.append({"fold": val_end[:4], "arch": arch, **fit_score(arch, p, P, c["window"], len(c["features"]), c["lr"], c["wd"])})
            del P
        results[name] = {
            "mean_auc": round(float(np.mean([r["auc"] for r in rows])), 4),
            "min_fold_auc": round(float(min(np.mean([r["auc"] for r in rows if r["fold"] == f]) for f in {r["fold"] for r in rows})), 4),
            "mean_log_loss": round(float(np.mean([r["log_loss"] for r in rows])), 5),
            "mean_top_decile_up": round(float(np.mean([r["top_decile_up"] for r in rows])), 4),
            "symbols": len(c["universe"]), "n_features": len(c["features"]), "seconds": round(time.time() - t0), "detail": rows,
        }
        print(name, {k: v for k, v in results[name].items() if k != "detail"}, flush=True)
        OUT.write_text(json.dumps(results, indent=1))
    print("done", flush=True)


if __name__ == "__main__":
    main()
