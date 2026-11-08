"""Self-attention components for the Transformer encoder."""
from __future__ import annotations

import numpy as np

from backend.dl.nn.core import DTYPE, Layer, Parameter
from backend.dl.nn.init import glorot_uniform


class PositionalEncoding(Layer):
    """Adds fixed sinusoidal position signals (Vaswani et al., 2017). No parameters."""

    def __init__(self, d_model: int, max_len: int = 512):
        pos = np.arange(max_len)[:, None]
        div = np.exp(np.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))
        pe = np.zeros((max_len, d_model), dtype=DTYPE)
        pe[:, 0::2] = np.sin(pos * div)
        pe[:, 1::2] = np.cos(pos * div[: d_model // 2])
        self.pe = pe
        self.d_model = d_model

    def forward(self, x, training=False):
        return x + self.pe[: x.shape[1]]

    def backward(self, grad):
        return grad

    def describe(self):
        return "PositionalEncoding"


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    z = x - x.max(axis=axis, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=axis, keepdims=True)


class MultiHeadSelfAttention(Layer):
    """
    Scaled dot-product multi-head self-attention.

        Q, K, V = xWq, xWk, xWv        split into h heads of size d/h
        A = softmax(QK^T / sqrt(d_h))  (optionally causal-masked)
        y = concat_h(A V) Wo
    The attention weights of the last forward pass are kept in `last_attention` (B, h, T, T).
    """

    def __init__(self, d_model: int, n_heads: int, rng: np.random.Generator, causal: bool = False):
        if d_model % n_heads:
            raise ValueError("d_model must be divisible by n_heads")
        self.d, self.h, self.causal = d_model, n_heads, causal
        self.dh = d_model // n_heads
        for name in ("q", "k", "v", "o"):
            setattr(self, f"W{name}", Parameter(glorot_uniform(rng, d_model, d_model, (d_model, d_model)), f"W{name}"))
            setattr(self, f"b{name}", Parameter(np.zeros(d_model, dtype=DTYPE), f"b{name}"))
        self.last_attention: np.ndarray | None = None

    def _split(self, t: np.ndarray) -> np.ndarray:
        B, T, _ = t.shape
        return t.reshape(B, T, self.h, self.dh).transpose(0, 2, 1, 3)  # (B, h, T, dh)

    def _merge(self, t: np.ndarray) -> np.ndarray:
        B, _, T, _ = t.shape
        return t.transpose(0, 2, 1, 3).reshape(B, T, self.d)

    def forward(self, x, training=False):
        self._x = x
        q = self._split(x @ self.Wq.value + self.bq.value)
        k = self._split(x @ self.Wk.value + self.bk.value)
        v = self._split(x @ self.Wv.value + self.bv.value)
        scores = q @ k.transpose(0, 1, 3, 2) / np.sqrt(self.dh)
        if self.causal:
            T = x.shape[1]
            scores = np.where(np.triu(np.ones((T, T), dtype=bool), 1), -1e9, scores)
        a = softmax(scores, axis=-1)
        o = self._merge(a @ v)
        self._q, self._k, self._v, self._a, self._o = q, k, v, a, o
        self.last_attention = a
        return o @ self.Wo.value + self.bo.value

    def backward(self, grad):
        x, q, k, v, a, o = self._x, self._q, self._k, self._v, self._a, self._o
        d = self.d
        self.Wo.grad += o.reshape(-1, d).T @ grad.reshape(-1, d)
        self.bo.grad += grad.sum(axis=(0, 1))
        do = self._split(grad @ self.Wo.value.T)
        da = do @ v.transpose(0, 1, 3, 2)
        dv = a.transpose(0, 1, 3, 2) @ do
        ds = a * (da - (da * a).sum(axis=-1, keepdims=True)) / np.sqrt(self.dh)
        dq = ds @ k
        dk = ds.transpose(0, 1, 3, 2) @ q
        dx = np.zeros_like(x)
        x2 = x.reshape(-1, d)
        for W, b, dt in ((self.Wq, self.bq, dq), (self.Wk, self.bk, dk), (self.Wv, self.bv, dv)):
            g = self._merge(dt)
            W.grad += x2.T @ g.reshape(-1, d)
            b.grad += g.sum(axis=(0, 1))
            dx += g @ W.value.T
        return dx

    def parameters(self):
        return [self.Wq, self.bq, self.Wk, self.bk, self.Wv, self.bv, self.Wo, self.bo]

    def describe(self):
        return f"MultiHeadSelfAttention(d={self.d}, heads={self.h}{', causal' if self.causal else ''})"
