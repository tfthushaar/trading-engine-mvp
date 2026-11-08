"""Loss functions. Each returns (loss, dloss/dprediction)."""
from __future__ import annotations

import numpy as np

from backend.dl.nn.layers import sigmoid


def bce_with_logits(logits: np.ndarray, y: np.ndarray, weights: np.ndarray | None = None):
    """Binary cross-entropy computed on logits (stable): max(z,0) - z*y + log(1 + e^-|z|)."""
    z = logits.reshape(-1)
    y = y.reshape(-1)
    w = np.ones_like(z) if weights is None else weights.reshape(-1)
    per = np.maximum(z, 0) - z * y + np.log1p(np.exp(-np.abs(z)))
    norm = w.sum()
    loss = float((w * per).sum() / norm)
    grad = (w * (sigmoid(z) - y) / norm).reshape(logits.shape)
    return loss, grad


def mse(pred: np.ndarray, y: np.ndarray, weights: np.ndarray | None = None):
    p = pred.reshape(-1)
    y = y.reshape(-1)
    w = np.ones_like(p) if weights is None else weights.reshape(-1)
    norm = w.sum()
    diff = p - y
    loss = float((w * diff**2).sum() / norm)
    grad = (2.0 * w * diff / norm).reshape(pred.shape)
    return loss, grad


def huber(pred: np.ndarray, y: np.ndarray, delta: float = 1.0, weights: np.ndarray | None = None):
    """Quadratic near zero, linear in the tails. Robust to the fat tails of return distributions."""
    p = pred.reshape(-1)
    y = y.reshape(-1)
    w = np.ones_like(p) if weights is None else weights.reshape(-1)
    norm = w.sum()
    diff = p - y
    absd = np.abs(diff)
    quad = absd <= delta
    per = np.where(quad, 0.5 * diff**2, delta * (absd - 0.5 * delta))
    loss = float((w * per).sum() / norm)
    grad = (w * np.where(quad, diff, delta * np.sign(diff)) / norm).reshape(pred.shape)
    return loss, grad


LOSSES = {"bce": bce_with_logits, "mse": mse, "huber": huber}
