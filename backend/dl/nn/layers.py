"""Feed-forward layers, activations, regularisation, normalisation and pooling."""
from __future__ import annotations

import numpy as np

from backend.dl.nn.core import DTYPE, Layer, Parameter
from backend.dl.nn.init import glorot_uniform, he_normal


class Dense(Layer):
    """Affine map over the last axis: y = x @ W + b. Works on (B, F) and (B, T, F)."""

    def __init__(self, in_features: int, out_features: int, rng: np.random.Generator, init: str = "glorot"):
        self.in_features, self.out_features = in_features, out_features
        if init == "he":
            w = he_normal(rng, in_features, (in_features, out_features))
        else:
            w = glorot_uniform(rng, in_features, out_features, (in_features, out_features))
        self.W = Parameter(w, "W")
        self.b = Parameter(np.zeros(out_features, dtype=DTYPE), "b")
        self._x: np.ndarray | None = None

    def forward(self, x, training=False):
        self._x = x
        return x @ self.W.value + self.b.value

    def backward(self, grad):
        x = self._x
        x2 = x.reshape(-1, self.in_features)
        g2 = grad.reshape(-1, self.out_features)
        self.W.grad += x2.T @ g2
        self.b.grad += g2.sum(axis=0)
        return grad @ self.W.value.T

    def parameters(self):
        return [self.W, self.b]

    def describe(self):
        return f"Dense({self.in_features}->{self.out_features})"


class ReLU(Layer):
    def forward(self, x, training=False):
        self._mask = x > 0
        return x * self._mask

    def backward(self, grad):
        return grad * self._mask


class LeakyReLU(Layer):
    def __init__(self, alpha: float = 0.01):
        self.alpha = alpha

    def forward(self, x, training=False):
        self._x = x
        return np.where(x > 0, x, self.alpha * x)

    def backward(self, grad):
        return grad * np.where(self._x > 0, 1.0, self.alpha)


class Tanh(Layer):
    def forward(self, x, training=False):
        self._y = np.tanh(x)
        return self._y

    def backward(self, grad):
        return grad * (1.0 - self._y**2)


def sigmoid(x: np.ndarray) -> np.ndarray:
    """Logistic function via the identity sigma(x) = (1 + tanh(x/2)) / 2: stable and a single ufunc."""
    return 0.5 * (1.0 + np.tanh(0.5 * x))


class Sigmoid(Layer):
    def forward(self, x, training=False):
        self._y = sigmoid(x)
        return self._y

    def backward(self, grad):
        return grad * self._y * (1.0 - self._y)


_GELU_C = np.sqrt(2.0 / np.pi)


class GELU(Layer):
    """GELU, tanh approximation (as used in BERT/GPT)."""

    def forward(self, x, training=False):
        self._x = x
        self._x2 = x * x
        self._t = np.tanh(_GELU_C * x * (1.0 + 0.044715 * self._x2))
        return 0.5 * x * (1.0 + self._t)

    def backward(self, grad):
        x, x2, t = self._x, self._x2, self._t
        dt = (1.0 - t * t) * _GELU_C * (1.0 + 3 * 0.044715 * x2)
        return grad * (0.5 * (1.0 + t) + 0.5 * x * dt)


class Dropout(Layer):
    """Inverted dropout. Active only when training=True (also used for Monte Carlo dropout)."""

    def __init__(self, p: float, rng: np.random.Generator):
        if not 0.0 <= p < 1.0:
            raise ValueError("dropout p must be in [0, 1)")
        self.p = p
        self.rng = rng
        self._mask: np.ndarray | None = None

    def forward(self, x, training=False):
        if not training or self.p == 0.0:
            self._mask = None
            return x
        self._mask = (self.rng.random(x.shape) >= self.p) / (1.0 - self.p)
        return x * self._mask

    def backward(self, grad):
        return grad if self._mask is None else grad * self._mask

    def describe(self):
        return f"Dropout({self.p:g})"


class LayerNorm(Layer):
    """Normalises the last axis to zero mean / unit variance, then applies a learned scale and shift."""

    def __init__(self, dim: int, eps: float = 1e-5):
        self.dim, self.eps = dim, eps
        self.gamma = Parameter(np.ones(dim, dtype=DTYPE), "gamma")
        self.beta = Parameter(np.zeros(dim, dtype=DTYPE), "beta")

    def forward(self, x, training=False):
        mu = x.mean(axis=-1, keepdims=True)
        var = x.var(axis=-1, keepdims=True)
        self._inv = 1.0 / np.sqrt(var + self.eps)
        self._xhat = (x - mu) * self._inv
        return self.gamma.value * self._xhat + self.beta.value

    def backward(self, grad):
        xhat, inv, n = self._xhat, self._inv, self.dim
        axes = tuple(range(grad.ndim - 1))
        self.gamma.grad += (grad * xhat).sum(axis=axes)
        self.beta.grad += grad.sum(axis=axes)
        dxhat = grad * self.gamma.value
        return (inv / n) * (
            n * dxhat - dxhat.sum(axis=-1, keepdims=True) - xhat * (dxhat * xhat).sum(axis=-1, keepdims=True)
        )

    def parameters(self):
        return [self.gamma, self.beta]

    def describe(self):
        return f"LayerNorm({self.dim})"


class Flatten(Layer):
    """(B, T, F) -> (B, T*F)."""

    def forward(self, x, training=False):
        self._shape = x.shape
        return x.reshape(x.shape[0], -1)

    def backward(self, grad):
        return grad.reshape(self._shape)


class GlobalAvgPool1D(Layer):
    """Mean over the time axis: (B, T, F) -> (B, F)."""

    def forward(self, x, training=False):
        self._T = x.shape[1]
        return x.mean(axis=1)

    def backward(self, grad):
        return np.repeat(grad[:, None, :] / self._T, self._T, axis=1)


class LastTimestep(Layer):
    """Selects the final time step: (B, T, F) -> (B, F)."""

    def forward(self, x, training=False):
        self._shape = x.shape
        return x[:, -1, :]

    def backward(self, grad):
        dx = np.zeros(self._shape, dtype=DTYPE)
        dx[:, -1, :] = grad
        return dx
