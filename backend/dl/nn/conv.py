"""Causal dilated 1-D convolution (the building block of temporal convolutional networks)."""
from __future__ import annotations

import numpy as np

from backend.dl.nn.core import DTYPE, Layer, Parameter
from backend.dl.nn.init import he_normal


class Conv1D(Layer):
    """
    Causal Conv1D on (B, T, C_in) -> (B, T, C_out).

    Left-pads by (kernel-1)*dilation so output step t only sees inputs <= t (no look-ahead).
    Implemented with im2col: patches (B, T, k*C_in) @ W (k*C_in, C_out).
    Weight row index is j*C_in + c, i.e. W[j*C_in + c, o] == torch_weight[o, c, j].
    """

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, rng: np.random.Generator, dilation: int = 1):
        self.cin, self.cout, self.k, self.d = in_channels, out_channels, kernel_size, dilation
        fan_in = kernel_size * in_channels
        self.W = Parameter(he_normal(rng, fan_in, (fan_in, out_channels)), "W")
        self.b = Parameter(np.zeros(out_channels, dtype=DTYPE), "b")

    @property
    def pad(self) -> int:
        return (self.k - 1) * self.d

    def forward(self, x, training=False):
        B, T, C = x.shape
        P = self.pad
        xp = np.concatenate([np.zeros((B, P, C), dtype=DTYPE), x], axis=1) if P else x
        patches = np.empty((B, T, self.k, C), dtype=DTYPE)
        for j in range(self.k):
            patches[:, :, j, :] = xp[:, j * self.d : j * self.d + T, :]
        self._patches = patches.reshape(B, T, self.k * C)
        self._shape = x.shape
        return self._patches @ self.W.value + self.b.value

    def backward(self, grad):
        B, T, C = self._shape
        P = self.pad
        self.W.grad += self._patches.reshape(-1, self.k * C).T @ grad.reshape(-1, self.cout)
        self.b.grad += grad.sum(axis=(0, 1))
        dpatches = (grad @ self.W.value.T).reshape(B, T, self.k, C)
        dxp = np.zeros((B, T + P, C), dtype=DTYPE)
        for j in range(self.k):
            dxp[:, j * self.d : j * self.d + T, :] += dpatches[:, :, j, :]
        return dxp[:, P:, :]

    def parameters(self):
        return [self.W, self.b]

    def describe(self):
        return f"Conv1D({self.cin}->{self.cout}, k={self.k}, d={self.d})"
