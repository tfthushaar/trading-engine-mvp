"""Weight initialisers."""
from __future__ import annotations

import numpy as np

from backend.dl.nn.core import DTYPE


def glorot_uniform(rng: np.random.Generator, fan_in: int, fan_out: int, shape: tuple) -> np.ndarray:
    """Xavier/Glorot uniform. Good default for tanh/sigmoid and linear layers."""
    limit = np.sqrt(6.0 / (fan_in + fan_out))
    return rng.uniform(-limit, limit, size=shape).astype(DTYPE)


def he_normal(rng: np.random.Generator, fan_in: int, shape: tuple) -> np.ndarray:
    """Kaiming/He normal. Keeps activation variance stable through ReLU layers."""
    return (rng.standard_normal(shape) * np.sqrt(2.0 / fan_in)).astype(DTYPE)


def orthogonal(rng: np.random.Generator, rows: int, cols: int) -> np.ndarray:
    """Orthogonal matrix. Standard choice for recurrent weights (preserves gradient norm)."""
    a = rng.standard_normal((max(rows, cols), min(rows, cols)))
    q, r = np.linalg.qr(a)
    q = q * np.sign(np.diag(r))
    if rows < cols:
        q = q.T
    return q[:rows, :cols].astype(DTYPE)
