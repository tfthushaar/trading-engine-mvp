"""
Recurrent layers with hand-written backpropagation through time (BPTT).

Gate layouts follow PyTorch so weights can be exchanged for parity checks:
    LSTM: [i, f, g, o]        GRU: [r, z, n] with b_hn inside the reset product.
Weights are stored as (in, k*H) so the forward pass is x @ W (PyTorch stores the transpose).
"""
from __future__ import annotations

import numpy as np

from backend.dl.nn.core import DTYPE, Layer, Parameter
from backend.dl.nn.init import glorot_uniform, orthogonal
from backend.dl.nn.layers import sigmoid


class LSTM(Layer):
    """Long Short-Term Memory layer over (B, T, F) inputs."""

    def __init__(self, in_features: int, hidden: int, rng: np.random.Generator, return_sequences: bool = False):
        self.in_features, self.hidden, self.return_sequences = in_features, hidden, return_sequences
        H = hidden
        self.W_ih = Parameter(glorot_uniform(rng, in_features, 4 * H, (in_features, 4 * H)), "W_ih")
        self.W_hh = Parameter(np.concatenate([orthogonal(rng, H, H) for _ in range(4)], axis=1), "W_hh")
        b = np.zeros(4 * H, dtype=DTYPE)
        b[H : 2 * H] = 1.0  # forget-gate bias of 1 helps gradients flow early in training
        self.b = Parameter(b, "b")

    def forward(self, x, training=False):
        B, T, _ = x.shape
        H = self.hidden
        self._x = x
        xz = x @ self.W_ih.value + self.b.value  # (B, T, 4H), input projection for all steps at once
        h = np.zeros((B, H), dtype=DTYPE)
        c = np.zeros((B, H), dtype=DTYPE)
        hs = np.empty((B, T, H), dtype=DTYPE)
        cache = []
        Whh = self.W_hh.value
        for t in range(T):
            z = xz[:, t] + h @ Whh
            s = sigmoid(z)  # one call for all gates; the g block is overwritten with tanh below
            i, f, o = s[:, :H], s[:, H : 2 * H], s[:, 3 * H :]
            g = np.tanh(z[:, 2 * H : 3 * H])
            c_prev, h_prev = c, h
            c = f * c_prev + i * g
            tc = np.tanh(c)
            h = o * tc
            hs[:, t] = h
            cache.append((h_prev, c_prev, i, f, g, o, tc))
        self._cache = cache
        return hs if self.return_sequences else h

    def backward(self, grad):
        x = self._x
        B, T, F = x.shape
        H = self.hidden
        if self.return_sequences:
            dH = grad
        else:
            dH = np.zeros((B, T, H), dtype=DTYPE)
            dH[:, -1] = grad
        Whh = self.W_hh.value
        dZ = np.empty((B, T, 4 * H), dtype=DTYPE)
        dh_next = np.zeros((B, H), dtype=DTYPE)
        dc_next = np.zeros((B, H), dtype=DTYPE)
        for t in reversed(range(T)):
            h_prev, c_prev, i, f, g, o, tc = self._cache[t]
            dh = dH[:, t] + dh_next
            do = dh * tc
            dc = dh * o * (1.0 - tc**2) + dc_next
            dz = np.concatenate(
                [dc * g * i * (1.0 - i), dc * c_prev * f * (1.0 - f), dc * i * (1.0 - g**2), do * o * (1.0 - o)],
                axis=1,
            )
            dZ[:, t] = dz
            self.W_hh.grad += h_prev.T @ dz
            dh_next = dz @ Whh.T
            dc_next = dc * f
        self.W_ih.grad += x.reshape(-1, F).T @ dZ.reshape(-1, 4 * H)
        self.b.grad += dZ.sum(axis=(0, 1))
        return dZ @ self.W_ih.value.T

    def parameters(self):
        return [self.W_ih, self.W_hh, self.b]

    def describe(self):
        return f"LSTM({self.in_features}->{self.hidden}{', seq' if self.return_sequences else ''})"


class GRU(Layer):
    """Gated Recurrent Unit (PyTorch formulation) over (B, T, F) inputs."""

    def __init__(self, in_features: int, hidden: int, rng: np.random.Generator, return_sequences: bool = False):
        self.in_features, self.hidden, self.return_sequences = in_features, hidden, return_sequences
        H = hidden
        self.W_ih = Parameter(glorot_uniform(rng, in_features, 3 * H, (in_features, 3 * H)), "W_ih")
        self.W_hh = Parameter(np.concatenate([orthogonal(rng, H, H) for _ in range(3)], axis=1), "W_hh")
        self.b_ih = Parameter(np.zeros(3 * H, dtype=DTYPE), "b_ih")
        self.b_hh = Parameter(np.zeros(3 * H, dtype=DTYPE), "b_hh")

    def forward(self, x, training=False):
        B, T, _ = x.shape
        H = self.hidden
        self._x = x
        gi_all = x @ self.W_ih.value + self.b_ih.value  # (B, T, 3H)
        h = np.zeros((B, H), dtype=DTYPE)
        hs = np.empty((B, T, H), dtype=DTYPE)
        cache = []
        Whh, bhh = self.W_hh.value, self.b_hh.value
        for t in range(T):
            gi = gi_all[:, t]
            gh = h @ Whh + bhh
            rz = sigmoid(gi[:, : 2 * H] + gh[:, : 2 * H])
            r, z = rz[:, :H], rz[:, H:]
            n = np.tanh(gi[:, 2 * H :] + r * gh[:, 2 * H :])
            h_prev = h
            h = (1.0 - z) * n + z * h_prev
            hs[:, t] = h
            cache.append((h_prev, r, z, n, gh[:, 2 * H :]))
        self._cache = cache
        return hs if self.return_sequences else h

    def backward(self, grad):
        x = self._x
        B, T, F = x.shape
        H = self.hidden
        if self.return_sequences:
            dH = grad
        else:
            dH = np.zeros((B, T, H), dtype=DTYPE)
            dH[:, -1] = grad
        Whh = self.W_hh.value
        dGI = np.empty((B, T, 3 * H), dtype=DTYPE)
        dh_next = np.zeros((B, H), dtype=DTYPE)
        for t in reversed(range(T)):
            h_prev, r, z, n, ghn = self._cache[t]
            dh = dH[:, t] + dh_next
            dn_pre = dh * (1.0 - z) * (1.0 - n**2)
            dz_pre = dh * (h_prev - n) * z * (1.0 - z)
            dr_pre = dn_pre * ghn * r * (1.0 - r)
            dgi = np.concatenate([dr_pre, dz_pre, dn_pre], axis=1)
            dgh = np.concatenate([dr_pre, dz_pre, dn_pre * r], axis=1)
            dGI[:, t] = dgi
            self.W_hh.grad += h_prev.T @ dgh
            self.b_hh.grad += dgh.sum(axis=0)
            dh_next = dh * z + dgh @ Whh.T
        self.W_ih.grad += x.reshape(-1, F).T @ dGI.reshape(-1, 3 * H)
        self.b_ih.grad += dGI.sum(axis=(0, 1))
        return dGI @ self.W_ih.value.T

    def parameters(self):
        return [self.W_ih, self.W_hh, self.b_ih, self.b_hh]

    def describe(self):
        return f"GRU({self.in_features}->{self.hidden}{', seq' if self.return_sequences else ''})"
