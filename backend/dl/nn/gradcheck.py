"""
Numerical gradient checking.

Compares the analytic gradients from backward() against central finite differences
    dL/dw ~ (L(w + eps) - L(w - eps)) / (2 eps)
for every parameter (sampled) and for the input. This is how the hand-written backprop is verified.
"""
from __future__ import annotations

import numpy as np

from backend.dl.nn.core import Layer


def _rel_error(a: np.ndarray, b: np.ndarray, atol: float = 1e-8) -> float:
    """Max relative error, ignoring entries whose absolute difference is below finite-difference noise.

    Some gradients are exactly zero by symmetry (e.g. the attention key bias: softmax is invariant to a
    per-row constant), where a pure relative error would just measure numerical noise.
    """
    diff = np.abs(a - b)
    rel = diff / np.maximum(1e-12, np.abs(a) + np.abs(b))
    return float(np.max(np.where(diff < atol, 0.0, rel)))


def gradcheck(layer: Layer, x: np.ndarray, loss_fn=None, eps: float = 1e-6, max_checks: int = 25, seed: int = 0) -> dict:
    """
    Returns {"input": rel_err, "<param>": rel_err, ...}. Uses loss = sum(y * R) with a fixed random R
    unless loss_fn(y) -> (loss, dloss/dy) is given. Run with dropout disabled (training=False).
    """
    rng = np.random.default_rng(seed)
    y = layer.forward(x, training=False)
    R = rng.standard_normal(y.shape)

    def loss_and_grad(out):
        if loss_fn is not None:
            return loss_fn(out)
        return float((out * R).sum()), R

    def loss_only() -> float:
        return loss_and_grad(layer.forward(x, training=False))[0]

    layer.zero_grad()
    _, dy = loss_and_grad(layer.forward(x, training=False))
    dx = layer.backward(dy)

    errors: dict[str, float] = {}
    # Input gradient
    idx = [tuple(rng.integers(0, s) for s in x.shape) for _ in range(max_checks)]
    num, ana = [], []
    for i in idx:
        old = x[i]
        x[i] = old + eps
        lp = loss_only()
        x[i] = old - eps
        lm = loss_only()
        x[i] = old
        num.append((lp - lm) / (2 * eps))
        ana.append(dx[i])
    errors["input"] = _rel_error(np.array(num), np.array(ana))

    for k, p in enumerate(layer.parameters()):
        analytic = p.grad.copy()
        num, ana = [], []
        for _ in range(min(max_checks, p.size)):
            i = tuple(rng.integers(0, s) for s in p.value.shape)
            old = p.value[i]
            p.value[i] = old + eps
            lp = loss_only()
            p.value[i] = old - eps
            lm = loss_only()
            p.value[i] = old
            num.append((lp - lm) / (2 * eps))
            ana.append(analytic[i])
        errors[f"{k}:{p.name}"] = _rel_error(np.array(num), np.array(ana))
    return errors
