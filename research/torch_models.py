"""
PyTorch reference implementations that mirror backend/dl/architectures.py layer for layer.

Each module implements export(mode) which returns its tensors in the exact order and layout of the
NumPy engine's parameters():
    mode="value" -> weights (for exporting a trained model)
    mode="grad"  -> autograd gradients (for gradient parity tests)
"""
from __future__ import annotations

import math

import torch
import torch.nn as tnn
import torch.nn.functional as F

from backend.dl.architectures import resolve_params


def _t(x: torch.Tensor, mode: str) -> torch.Tensor:
    return (x.detach() if mode == "value" else x.grad).clone()


class Dense(tnn.Linear):
    def export(self, mode="value"):
        return [_t(self.weight, mode).T, _t(self.bias, mode)]


class LayerNorm(tnn.LayerNorm):
    def __init__(self, d):
        super().__init__(d, eps=1e-5)

    def export(self, mode="value"):
        return [_t(self.weight, mode), _t(self.bias, mode)]


class Act(tnn.Module):
    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    def forward(self, x):
        return {"relu": F.relu, "tanh": torch.tanh, "gelu": lambda v: F.gelu(v, approximate="tanh")}[self.kind](x)

    def export(self, mode="value"):
        return []


class Dropout(tnn.Dropout):
    def export(self, mode="value"):
        return []


class LSTM(tnn.Module):
    def __init__(self, cin, hidden, return_sequences):
        super().__init__()
        self.rnn = tnn.LSTM(cin, hidden, batch_first=True)
        self.seq = return_sequences

    def forward(self, x):
        out, (h, _) = self.rnn(x)
        return out if self.seq else h[-1]

    def export(self, mode="value"):
        r = self.rnn
        bias = (r.bias_ih_l0.detach() + r.bias_hh_l0.detach()) if mode == "value" else r.bias_ih_l0.grad.clone()
        return [_t(r.weight_ih_l0, mode).T, _t(r.weight_hh_l0, mode).T, bias]


class GRU(tnn.Module):
    def __init__(self, cin, hidden, return_sequences):
        super().__init__()
        self.rnn = tnn.GRU(cin, hidden, batch_first=True)
        self.seq = return_sequences

    def forward(self, x):
        out, h = self.rnn(x)
        return out if self.seq else h[-1]

    def export(self, mode="value"):
        r = self.rnn
        return [_t(r.weight_ih_l0, mode).T, _t(r.weight_hh_l0, mode).T, _t(r.bias_ih_l0, mode), _t(r.bias_hh_l0, mode)]


class CausalConv(tnn.Module):
    def __init__(self, cin, cout, k, dilation):
        super().__init__()
        self.conv = tnn.Conv1d(cin, cout, k, dilation=dilation)
        self.pad = (k - 1) * dilation

    def forward(self, x):  # (B, T, C)
        y = self.conv(F.pad(x.transpose(1, 2), (self.pad, 0)))
        return y.transpose(1, 2)

    def export(self, mode="value"):
        w = _t(self.conv.weight, mode)  # (out, in, k)
        cout, cin, k = w.shape
        return [w.permute(2, 1, 0).reshape(k * cin, cout), _t(self.conv.bias, mode)]


class PositionalEncoding(tnn.Module):
    def __init__(self, d, max_len):
        super().__init__()
        pos = torch.arange(max_len, dtype=torch.float64)[:, None]
        div = torch.exp(torch.arange(0, d, 2, dtype=torch.float64) * (-math.log(10000.0) / d))
        pe = torch.zeros(max_len, d, dtype=torch.float64)
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div[: d // 2])
        self.register_buffer("pe", pe)

    def forward(self, x):
        return x + self.pe[: x.shape[1]].to(x.dtype)

    def export(self, mode="value"):
        return []


class MHSA(tnn.Module):
    def __init__(self, d, heads):
        super().__init__()
        self.d, self.h, self.dh = d, heads, d // heads
        self.q, self.k, self.v, self.o = (tnn.Linear(d, d) for _ in range(4))

    def forward(self, x):
        B, T, _ = x.shape
        split = lambda t: t.view(B, T, self.h, self.dh).transpose(1, 2)  # noqa: E731
        q, k, v = split(self.q(x)), split(self.k(x)), split(self.v(x))
        a = torch.softmax(q @ k.transpose(-1, -2) / math.sqrt(self.dh), dim=-1)
        return self.o((a @ v).transpose(1, 2).reshape(B, T, self.d))

    def export(self, mode="value"):
        out = []
        for lin in (self.q, self.k, self.v, self.o):
            out += [_t(lin.weight, mode).T, _t(lin.bias, mode)]
        return out


class Seq(tnn.Module):
    def __init__(self, *mods):
        super().__init__()
        self.mods = tnn.ModuleList(mods)

    def forward(self, x):
        for m in self.mods:
            x = m(x)
        return x

    def export(self, mode="value"):
        out = []
        for m in self.mods:
            out += m.export(mode)
        return out


class Residual(tnn.Module):
    def __init__(self, inner):
        super().__init__()
        self.inner = inner

    def forward(self, x):
        return x + self.inner(x)

    def export(self, mode="value"):
        return self.inner.export(mode)


class Reduce(tnn.Module):
    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    def forward(self, x):
        return {"flatten": lambda v: v.reshape(v.shape[0], -1), "mean": lambda v: v.mean(dim=1), "last": lambda v: v[:, -1]}[self.kind](x)

    def export(self, mode="value"):
        return []


def build_torch(arch: str, window: int, n_features: int, params: dict | None = None) -> Seq:
    p = resolve_params(arch, params)
    drop = lambda: Dropout(p.get("dropout", 0.0))  # noqa: E731
    mods: list[tnn.Module] = []
    if arch == "linear":
        mods = [Reduce("flatten"), Dense(window * n_features, 1)]
    elif arch == "mlp":
        mods = [Reduce("flatten")]
        width = window * n_features
        for _ in range(p["layers"]):
            mods += [Dense(width, p["hidden"]), Act("relu"), drop()]
            width = p["hidden"]
        mods.append(Dense(width, 1))
    elif arch in ("lstm", "gru"):
        cell = LSTM if arch == "lstm" else GRU
        width = n_features
        for i in range(p["layers"]):
            mods += [cell(width, p["hidden"], return_sequences=i < p["layers"] - 1), drop()]
            width = p["hidden"]
        mods.append(Dense(width, 1))
    elif arch == "cnn":
        C, k = p["channels"], p["kernel"]
        mods = [CausalConv(n_features, C, k, 1), Act("relu"), drop()]
        for i in range(1, p["layers"]):
            mods.append(Residual(Seq(CausalConv(C, C, k, 2**i), Act("relu"), drop())))
        mods += [Reduce("last"), Dense(C, 1)]
    elif arch == "transformer":
        d = p["d_model"]
        mods = [Dense(n_features, d), PositionalEncoding(d, max(window, 8))]
        for _ in range(p["layers"]):
            mods.append(Residual(Seq(LayerNorm(d), MHSA(d, p["heads"]), drop())))
            mods.append(Residual(Seq(LayerNorm(d), Dense(d, p["ff"]), Act("gelu"), drop(), Dense(p["ff"], d), drop())))
        mods += [LayerNorm(d), Reduce("mean"), Dense(d, 1)]
    else:
        raise ValueError(arch)
    return Seq(*mods)
