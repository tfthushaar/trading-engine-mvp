"""
Core building blocks of the from-scratch neural-network library.

Every layer implements:
    forward(x, training)  -> y        (caches whatever backward needs)
    backward(dy)          -> dx       (accumulates parameter gradients into Parameter.grad)
    parameters()          -> list[Parameter]

Tensors are NumPy float64 arrays. Sequence tensors are batch-first: (batch, time, features).
"""
from __future__ import annotations

import numpy as np

DTYPE = np.float64


class Parameter:
    """A trainable tensor and its accumulated gradient."""

    __slots__ = ("value", "grad", "name")

    def __init__(self, value: np.ndarray, name: str = ""):
        self.value = np.asarray(value, dtype=DTYPE)
        self.grad = np.zeros_like(self.value)
        self.name = name

    @property
    def size(self) -> int:
        return int(self.value.size)


class Layer:
    """Base class. Subclasses override forward/backward and, if trainable, parameters()."""

    def forward(self, x: np.ndarray, training: bool = False) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def backward(self, grad: np.ndarray) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def parameters(self) -> list[Parameter]:
        return []

    def zero_grad(self) -> None:
        for p in self.parameters():
            p.grad.fill(0.0)

    def describe(self) -> str:
        return type(self).__name__

    def children(self) -> list["Layer"]:
        return []

    def __call__(self, x: np.ndarray, training: bool = False) -> np.ndarray:
        return self.forward(x, training)


class Sequential(Layer):
    """Applies layers in order; backward runs them in reverse."""

    def __init__(self, layers: list[Layer]):
        self.layers = list(layers)
        self.output_shapes: list[tuple] = []

    def forward(self, x, training=False):
        shapes = []
        for layer in self.layers:
            x = layer.forward(x, training)
            shapes.append(tuple(x.shape))
        self.output_shapes = shapes
        return x

    def backward(self, grad):
        for layer in reversed(self.layers):
            grad = layer.backward(grad)
        return grad

    def parameters(self):
        params: list[Parameter] = []
        for layer in self.layers:
            params.extend(layer.parameters())
        return params

    def children(self):
        return self.layers

    def describe(self) -> str:
        return " -> ".join(layer.describe() for layer in self.layers)


class Residual(Layer):
    """y = x + f(x). The skip path passes the gradient through unchanged."""

    def __init__(self, inner: Layer):
        self.inner = inner

    def forward(self, x, training=False):
        return x + self.inner.forward(x, training)

    def backward(self, grad):
        return grad + self.inner.backward(grad)

    def parameters(self):
        return self.inner.parameters()

    def children(self):
        return [self.inner]

    def describe(self) -> str:
        return f"Residual({self.inner.describe()})"


def iter_layers(layer: Layer):
    """Depth-first traversal over a layer tree."""
    yield layer
    for child in layer.children():
        yield from iter_layers(child)


def count_parameters(layer: Layer) -> int:
    return sum(p.size for p in layer.parameters())
