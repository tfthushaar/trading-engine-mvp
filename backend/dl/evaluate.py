"""Evaluation: metrics, calibration, uncertainty (MC dropout) and interpretability (saliency, permutation, attention)."""
from __future__ import annotations

import numpy as np

from backend.dl import nn
from backend.dl.train import predict


def _auc(scores: np.ndarray, y: np.ndarray) -> float | None:
    """ROC AUC via the Mann-Whitney U statistic (average ranks handle ties)."""
    pos, neg = y == 1, y == 0
    if pos.sum() == 0 or neg.sum() == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores))
    s_sorted = scores[order]
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * neg.sum()))


def classification_metrics(prob: np.ndarray, y: np.ndarray, threshold: float = 0.5) -> dict:
    p = np.clip(prob, 1e-7, 1 - 1e-7)
    pred = (prob >= threshold).astype(float)
    tp = float(((pred == 1) & (y == 1)).sum())
    tn = float(((pred == 0) & (y == 0)).sum())
    fp = float(((pred == 1) & (y == 0)).sum())
    fn = float(((pred == 0) & (y == 1)).sum())
    tpr = tp / (tp + fn) if tp + fn else 0.0
    tnr = tn / (tn + fp) if tn + fp else 0.0
    return {
        "accuracy": round(float((pred == y).mean()), 4),
        "balanced_accuracy": round((tpr + tnr) / 2, 4),
        "auc": None if (a := _auc(prob, y)) is None else round(a, 4),
        "log_loss": round(float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()), 5),
        "brier": round(float(((prob - y) ** 2).mean()), 5),
        "precision_up": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall_up": round(tpr, 4),
        "predicted_up_rate": round(float(pred.mean()), 4),
        "confusion": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }


def regression_metrics(pred_ret: np.ndarray, true_ret: np.ndarray) -> dict:
    err = pred_ret - true_ret
    ss_res = float((err**2).sum())
    ss_zero = float((true_ret**2).sum())
    ic = float(np.corrcoef(pred_ret, true_ret)[0, 1]) if pred_ret.std() > 0 and true_ret.std() > 0 else 0.0
    rank_ic = float(np.corrcoef(np.argsort(np.argsort(pred_ret)), np.argsort(np.argsort(true_ret)))[0, 1]) if len(pred_ret) > 2 else 0.0
    return {
        "rmse": round(float(np.sqrt((err**2).mean())), 6),
        "mae": round(float(np.abs(err).mean()), 6),
        "r2_vs_zero": round(1.0 - ss_res / ss_zero, 5) if ss_zero > 0 else None,
        "directional_accuracy": round(float((np.sign(pred_ret) == np.sign(true_ret)).mean()), 4),
        "ic": round(ic, 4),
        "rank_ic": round(rank_ic, 4),
    }


def calibration(prob: np.ndarray, y: np.ndarray, bins: int = 8) -> dict:
    """Reliability diagram data and expected calibration error."""
    edges = np.linspace(0, 1, bins + 1)
    rows, ece = [], 0.0
    for i in range(bins):
        m = (prob >= edges[i]) & (prob < edges[i + 1] if i < bins - 1 else prob <= edges[i + 1])
        if m.sum() == 0:
            continue
        conf, acc = float(prob[m].mean()), float(y[m].mean())
        ece += m.mean() * abs(conf - acc)
        rows.append({"bin": [round(edges[i], 3), round(edges[i + 1], 3)], "n": int(m.sum()), "mean_prob": round(conf, 4), "frequency": round(acc, 4)})
    return {"bins": rows, "ece": round(float(ece), 5)}


def mc_dropout(model: nn.Layer, X: np.ndarray, samples: int = 50) -> np.ndarray:
    """Monte Carlo dropout (Gal & Ghahramani, 2016): keep dropout active at inference. Returns (samples, N)."""
    return np.stack([predict(model, X, training=True) for _ in range(samples)])


def has_dropout(model: nn.Layer) -> bool:
    return any(isinstance(layer, nn.Dropout) and layer.p > 0 for layer in nn.iter_layers(model))


def saliency(model: nn.Layer, X: np.ndarray, max_samples: int = 256) -> np.ndarray:
    """Gradient x input attribution averaged over samples: |d output / d x| * |x|, shape (W, F)."""
    Xs = X[-max_samples:]
    model.forward(Xs, training=False)
    dx = model.backward(np.ones((len(Xs), 1)))
    model.zero_grad()
    return np.abs(dx * Xs).mean(axis=0)


def permutation_importance(model: nn.Layer, X: np.ndarray, y: np.ndarray, task: str, seed: int = 0, repeats: int = 3) -> list[float]:
    """Increase in loss when one feature is shuffled across samples (time order inside each window kept)."""
    rng = np.random.default_rng(seed)
    loss_fn = nn.bce_with_logits if task == "classification" else nn.mse

    def loss(Xe):
        return loss_fn(predict(model, Xe).reshape(-1, 1), y.reshape(-1, 1))[0]

    base = loss(X)
    scores = []
    for f in range(X.shape[2]):
        deltas = []
        for _ in range(repeats):
            Xp = X.copy()
            Xp[:, :, f] = Xp[rng.permutation(len(X)), :, f]
            deltas.append(loss(Xp) - base)
        scores.append(float(np.mean(deltas)))
    return scores


def attention_maps(model: nn.Layer, X: np.ndarray, max_samples: int = 128) -> list[list[list[float]]]:
    """Average attention matrix (T x T) for each attention layer, averaged over samples and heads."""
    layers = [layer for layer in nn.iter_layers(model) if isinstance(layer, nn.MultiHeadSelfAttention)]
    if not layers:
        return []
    model.forward(X[-max_samples:], training=False)
    return [np.round(layer.last_attention.mean(axis=(0, 1)), 5).tolist() for layer in layers]
