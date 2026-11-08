"""Mini-batch training loop with early stopping, cosine LR schedule, gradient clipping and a time budget."""
from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass

import numpy as np

from backend.dl import nn
from backend.dl.data import Dataset


@dataclass
class TrainConfig:
    epochs: int = 60
    batch_size: int = 64
    lr: float = 1e-3
    optimizer: str = "adamw"
    weight_decay: float = 1e-4
    loss: str = "auto"          # auto -> bce (classification) / huber (regression)
    schedule: str = "cosine"    # cosine | constant
    warmup_epochs: int = 3
    patience: int = 12
    clip_norm: float = 1.0
    seed: int = 42
    time_budget_s: float = 20.0

    def clamp(self) -> "TrainConfig":
        self.epochs = int(min(max(self.epochs, 1), 300))
        self.batch_size = int(min(max(self.batch_size, 8), 512))
        self.lr = float(min(max(self.lr, 1e-5), 0.1))
        self.weight_decay = float(min(max(self.weight_decay, 0.0), 0.1))
        self.patience = int(min(max(self.patience, 2), 100))
        self.clip_norm = float(min(max(self.clip_norm, 0.0), 100.0))
        self.time_budget_s = float(min(max(self.time_budget_s, 2.0), 40.0))
        return self


def predict(model: nn.Layer, X: np.ndarray, training: bool = False, batch: int | None = None) -> np.ndarray:
    """Raw outputs (logits or scaled returns), shape (N,). Honours model.eval_batch when a model sets one."""
    if len(X) == 0:
        return np.zeros(0)
    batch = batch or getattr(model, "eval_batch", 128)
    outs = [model.forward(X[i : i + batch], training=training).reshape(-1) for i in range(0, len(X), batch)]
    return np.concatenate(outs)


def _lr_at(cfg: TrainConfig, epoch: int) -> float:
    if epoch < cfg.warmup_epochs:
        return cfg.lr * (epoch + 1) / cfg.warmup_epochs
    if cfg.schedule == "cosine":
        progress = (epoch - cfg.warmup_epochs) / max(1, cfg.epochs - cfg.warmup_epochs)
        return cfg.lr * (0.05 + 0.95 * 0.5 * (1 + math.cos(math.pi * progress)))
    return cfg.lr


def _metric(task: str, out: np.ndarray, y: np.ndarray) -> float:
    if task == "classification":
        return float(((out > 0).astype(float) == y).mean())
    return float((np.sign(out) == np.sign(y)).mean())


def train(model: nn.Layer, ds: Dataset, cfg: TrainConfig) -> dict:
    cfg.clamp()
    loss_name = cfg.loss if cfg.loss != "auto" else ("bce" if ds.task == "classification" else "huber")
    loss_fn = nn.LOSSES[loss_name]
    params = model.parameters()
    opt = nn.make_optimizer(cfg.optimizer, params, cfg.lr, cfg.weight_decay)
    rng = np.random.default_rng(cfg.seed)
    Xtr, ytr = ds.split("train")
    Xva, yva = ds.split("val")
    y_col = lambda v: v.reshape(-1, 1)  # noqa: E731

    history = {"epoch": [], "lr": [], "train_loss": [], "val_loss": [], "train_metric": [], "val_metric": [], "grad_norm": []}
    best_val, best_epoch, wait = math.inf, 0, 0
    best_state = [p.value.copy() for p in params]
    stopped = "max_epochs"
    t0 = time.perf_counter()

    for epoch in range(cfg.epochs):
        lr = _lr_at(cfg, epoch)
        opt.lr = lr
        perm = rng.permutation(len(Xtr))
        tot, cnt, hits, gn = 0.0, 0, 0.0, []
        for s in range(0, len(perm), cfg.batch_size):
            b = perm[s : s + cfg.batch_size]
            opt.zero_grad()
            out = model.forward(Xtr[b], training=True)
            loss, dout = loss_fn(out, y_col(ytr[b]))
            model.backward(dout)
            gn.append(nn.clip_grad_norm(params, cfg.clip_norm))
            opt.step()
            tot += loss * len(b)
            cnt += len(b)
            hits += _metric(ds.task, out.reshape(-1), ytr[b]) * len(b)  # running metric (train mode)
            if time.perf_counter() - t0 > cfg.time_budget_s:  # large models can spend many seconds in one epoch
                break

        out_va = predict(model, Xva)
        val_loss = loss_fn(out_va.reshape(-1, 1), y_col(yva))[0]
        history["epoch"].append(epoch + 1)
        history["lr"].append(lr)
        history["train_loss"].append(tot / max(cnt, 1))
        history["val_loss"].append(val_loss)
        history["train_metric"].append(hits / max(cnt, 1))
        history["val_metric"].append(_metric(ds.task, out_va, yva))
        history["grad_norm"].append(float(np.mean(gn)) if gn else 0.0)

        if not np.isfinite(val_loss):
            stopped = "diverged"
            break
        if val_loss < best_val - 1e-6:
            best_val, best_epoch, wait = val_loss, epoch + 1, 0
            best_state = [p.value.copy() for p in params]
        else:
            wait += 1
            if wait >= cfg.patience:
                stopped = "early_stopping"
                break
        if time.perf_counter() - t0 > cfg.time_budget_s:
            stopped = "time_budget"
            break

    for p, v in zip(params, best_state):
        p.value[...] = v
    return {
        "history": {k: [round(float(x), 6) for x in v] for k, v in history.items()},
        "best_epoch": best_epoch,
        "epochs_run": len(history["epoch"]),
        "stopped": stopped,
        "seconds": round(time.perf_counter() - t0, 3),
        "loss": loss_name,
        "config": asdict(cfg),
    }
