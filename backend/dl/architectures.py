"""
Model zoo. Every builder maps an input window (B, T, F) to one output per sample (B, 1):
a logit for direction classification, or a scaled return for regression.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from backend.dl import nn

ARCHITECTURES: dict[str, dict[str, Any]] = {
    "linear": {
        "name": "Linear",
        "family": "Baseline",
        "summary": "Logistic/linear regression on the flattened window. A single affine layer with no hidden units.",
        "defaults": {},
        "limits": {},
    },
    "mlp": {
        "name": "MLP",
        "family": "Feed-forward",
        "summary": "Multilayer perceptron on the flattened window with ReLU and dropout. Has no notion of time order.",
        "defaults": {"hidden": 64, "layers": 2, "dropout": 0.2},
        "limits": {"hidden": [8, 256], "layers": [1, 4], "dropout": [0.0, 0.6]},
    },
    "lstm": {
        "name": "LSTM",
        "family": "Recurrent",
        "summary": "Long Short-Term Memory. Gated cell state carries information across time steps (Hochreiter & Schmidhuber, 1997).",
        "defaults": {"hidden": 32, "layers": 1, "dropout": 0.2},
        "limits": {"hidden": [4, 128], "layers": [1, 3], "dropout": [0.0, 0.6]},
    },
    "gru": {
        "name": "GRU",
        "family": "Recurrent",
        "summary": "Gated Recurrent Unit. A lighter LSTM variant with reset and update gates (Cho et al., 2014).",
        "defaults": {"hidden": 32, "layers": 1, "dropout": 0.2},
        "limits": {"hidden": [4, 128], "layers": [1, 3], "dropout": [0.0, 0.6]},
    },
    "cnn": {
        "name": "TCN",
        "family": "Convolutional",
        "summary": "Temporal convolutional network: causal dilated 1-D convolutions with residual blocks (Bai et al., 2018).",
        "defaults": {"channels": 32, "layers": 3, "kernel": 3, "dropout": 0.2},
        "limits": {"channels": [4, 128], "layers": [1, 5], "kernel": [2, 5], "dropout": [0.0, 0.6]},
    },
    "transformer": {
        "name": "Transformer",
        "family": "Attention",
        "summary": "Pre-norm Transformer encoder with sinusoidal positions and multi-head self-attention (Vaswani et al., 2017).",
        "defaults": {"d_model": 32, "heads": 4, "layers": 2, "ff": 64, "dropout": 0.1},
        "limits": {"d_model": [8, 96], "heads": [1, 8], "layers": [1, 4], "ff": [16, 256], "dropout": [0.0, 0.6]},
    },
}


def resolve_params(arch: str, params: dict | None) -> dict:
    if arch not in ARCHITECTURES:
        raise ValueError(f"unknown architecture {arch!r}")
    spec = ARCHITECTURES[arch]
    out = dict(spec["defaults"])
    for k, v in (params or {}).items():
        if k in out and v is not None:
            out[k] = v
    for k, (lo, hi) in spec["limits"].items():
        cast = float if isinstance(out[k], float) or k == "dropout" else int
        out[k] = cast(min(max(cast(out[k]), lo), hi))
    if arch == "transformer" and out["d_model"] % out["heads"]:
        out["heads"] = max(h for h in range(1, out["heads"] + 1) if out["d_model"] % h == 0)
    return out


def build_model(arch: str, window: int, n_features: int, params: dict | None = None, seed: int = 0) -> tuple[nn.Sequential, dict]:
    """Return (network, resolved_params)."""
    p = resolve_params(arch, params)
    rng = np.random.default_rng(seed)
    drop = lambda: nn.Dropout(p.get("dropout", 0.0), rng)  # noqa: E731
    layers: list[nn.Layer] = []

    if arch == "linear":
        layers = [nn.Flatten(), nn.Dense(window * n_features, 1, rng)]

    elif arch == "mlp":
        layers = [nn.Flatten()]
        width = window * n_features
        for _ in range(p["layers"]):
            layers += [nn.Dense(width, p["hidden"], rng, init="he"), nn.ReLU(), drop()]
            width = p["hidden"]
        layers.append(nn.Dense(width, 1, rng))

    elif arch in ("lstm", "gru"):
        cell = nn.LSTM if arch == "lstm" else nn.GRU
        width = n_features
        for i in range(p["layers"]):
            last = i == p["layers"] - 1
            layers += [cell(width, p["hidden"], rng, return_sequences=not last), drop()]
            width = p["hidden"]
        layers.append(nn.Dense(width, 1, rng))

    elif arch == "cnn":
        C, k = p["channels"], p["kernel"]
        layers = [nn.Conv1D(n_features, C, k, rng, dilation=1), nn.ReLU(), drop()]
        for i in range(1, p["layers"]):
            layers.append(nn.Residual(nn.Sequential([nn.Conv1D(C, C, k, rng, dilation=2**i), nn.ReLU(), drop()])))
        layers += [nn.LastTimestep(), nn.Dense(C, 1, rng)]

    elif arch == "transformer":
        d = p["d_model"]
        layers = [nn.Dense(n_features, d, rng), nn.PositionalEncoding(d, max_len=max(window, 8))]
        for _ in range(p["layers"]):
            layers.append(nn.Residual(nn.Sequential([nn.LayerNorm(d), nn.MultiHeadSelfAttention(d, p["heads"], rng), drop()])))
            layers.append(
                nn.Residual(nn.Sequential([nn.LayerNorm(d), nn.Dense(d, p["ff"], rng, init="he"), nn.GELU(), drop(), nn.Dense(p["ff"], d, rng), drop()]))
            )
        layers += [nn.LayerNorm(d), nn.GlobalAvgPool1D(), nn.Dense(d, 1, rng)]

    return nn.Sequential(layers), p


def receptive_field(arch: str, window: int, params: dict) -> int:
    if arch == "cnn":
        return min(window, 1 + (params["kernel"] - 1) * sum(2**i for i in range(params["layers"])))
    return window


def summarize(model: nn.Sequential, window: int, n_features: int) -> dict:
    """Layer table (name, output shape, parameter count) from a dummy forward pass."""
    model.forward(np.zeros((1, window, n_features)), training=False)
    rows = []
    for layer, shape in zip(model.layers, model.output_shapes):
        rows.append({"layer": layer.describe(), "output": list(shape[1:]), "params": nn.count_parameters(layer)})
    return {"layers": rows, "total_params": nn.count_parameters(model)}
