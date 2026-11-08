"""Optimisers and gradient utilities."""
from __future__ import annotations

import numpy as np

from backend.dl.nn.core import Parameter


def clip_grad_norm(params: list[Parameter], max_norm: float) -> float:
    """Rescale all gradients so their joint L2 norm is at most max_norm. Returns the pre-clip norm."""
    total = float(np.sqrt(sum(float((p.grad**2).sum()) for p in params)))
    if max_norm > 0 and total > max_norm:
        scale = max_norm / (total + 1e-12)
        for p in params:
            p.grad *= scale
    return total


class Optimizer:
    def __init__(self, params: list[Parameter], lr: float):
        self.params = params
        self.lr = lr

    def zero_grad(self) -> None:
        for p in self.params:
            p.grad.fill(0.0)

    def step(self) -> None:  # pragma: no cover
        raise NotImplementedError


class SGD(Optimizer):
    """Stochastic gradient descent with (optional) momentum and L2 weight decay."""

    def __init__(self, params, lr=0.01, momentum=0.9, weight_decay=0.0):
        super().__init__(params, lr)
        self.momentum, self.wd = momentum, weight_decay
        self.v = [np.zeros_like(p.value) for p in params]

    def step(self):
        for p, v in zip(self.params, self.v):
            g = p.grad + self.wd * p.value if self.wd else p.grad
            v *= self.momentum
            v += g
            p.value -= self.lr * v


class Adam(Optimizer):
    """
    Adam (Kingma & Ba, 2015). With decoupled=True this is AdamW (Loshchilov & Hutter, 2019):
    weight decay is applied directly to the weights instead of being added to the gradient.
    """

    def __init__(self, params, lr=1e-3, betas=(0.9, 0.999), eps=1e-8, weight_decay=0.0, decoupled=False):
        super().__init__(params, lr)
        self.b1, self.b2 = betas
        self.eps, self.wd, self.decoupled = eps, weight_decay, decoupled
        self.m = [np.zeros_like(p.value) for p in params]
        self.v = [np.zeros_like(p.value) for p in params]
        self.t = 0

    def step(self):
        self.t += 1
        bc1 = 1.0 - self.b1**self.t
        bc2 = 1.0 - self.b2**self.t
        for p, m, v in zip(self.params, self.m, self.v):
            g = p.grad
            if self.wd and not self.decoupled:
                g = g + self.wd * p.value
            m *= self.b1
            m += (1.0 - self.b1) * g
            v *= self.b2
            v += (1.0 - self.b2) * g * g
            if self.wd and self.decoupled:
                p.value -= self.lr * self.wd * p.value
            p.value -= self.lr * (m / bc1) / (np.sqrt(v / bc2) + self.eps)


def make_optimizer(name: str, params, lr: float, weight_decay: float = 0.0) -> Optimizer:
    name = name.lower()
    if name == "sgd":
        return SGD(params, lr=lr, momentum=0.9, weight_decay=weight_decay)
    if name == "adam":
        return Adam(params, lr=lr, weight_decay=weight_decay)
    if name == "adamw":
        return Adam(params, lr=lr, weight_decay=weight_decay, decoupled=True)
    raise ValueError(f"unknown optimizer {name!r}")
