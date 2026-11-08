"""
Gradient checks for every layer and every full architecture.

The analytic gradients from the hand-written backward passes must match central finite differences.
"""
import numpy as np
import pytest

from backend.dl import nn
from backend.dl.architectures import ARCHITECTURES, build_model

TOL = 1e-5


def _check(layer, x, **kw):
    errs = nn.gradcheck(layer, x, **kw)
    bad = {k: v for k, v in errs.items() if v > TOL}
    assert not bad, f"{layer.describe()}: {bad}"


@pytest.fixture
def rng():
    return np.random.default_rng(7)


def test_dense_2d_and_3d(rng):
    _check(nn.Dense(5, 3, rng), rng.standard_normal((4, 5)))
    _check(nn.Dense(5, 3, rng), rng.standard_normal((2, 6, 5)))


@pytest.mark.parametrize("act", [nn.Tanh, nn.Sigmoid, nn.GELU, nn.LeakyReLU])
def test_smooth_activations(act, rng):
    _check(act(), rng.standard_normal((3, 4, 5)))


def test_relu(rng):
    x = rng.standard_normal((4, 6))
    x[np.abs(x) < 1e-3] = 0.5  # stay away from the kink
    _check(nn.ReLU(), x)


def test_layernorm(rng):
    ln = nn.LayerNorm(6)
    ln.gamma.value = rng.standard_normal(6)
    ln.beta.value = rng.standard_normal(6)
    _check(ln, rng.standard_normal((3, 4, 6)))


@pytest.mark.parametrize("cell", [nn.LSTM, nn.GRU])
@pytest.mark.parametrize("seq", [False, True])
def test_recurrent(cell, seq, rng):
    layer = cell(4, 5, rng, return_sequences=seq)
    for p in layer.parameters():
        p.value = p.value + 0.1 * rng.standard_normal(p.value.shape)
    _check(layer, rng.standard_normal((3, 7, 4)))


@pytest.mark.parametrize("k,d", [(1, 1), (3, 1), (3, 2), (2, 4)])
def test_conv1d(k, d, rng):
    layer = nn.Conv1D(3, 4, k, rng, dilation=d)
    layer.b.value = rng.standard_normal(4)
    _check(layer, rng.standard_normal((2, 9, 3)))


def test_conv1d_is_causal(rng):
    layer = nn.Conv1D(2, 3, 3, rng, dilation=2)
    x = rng.standard_normal((1, 10, 2))
    y1 = layer.forward(x.copy())
    x2 = x.copy()
    x2[:, 6:] += 5.0  # change the future
    y2 = layer.forward(x2)
    assert np.allclose(y1[:, :6], y2[:, :6])


@pytest.mark.parametrize("causal", [False, True])
def test_attention(causal, rng):
    layer = nn.MultiHeadSelfAttention(8, 2, rng, causal=causal)
    for p in layer.parameters():
        p.value = p.value + 0.1 * rng.standard_normal(p.value.shape)
    _check(layer, rng.standard_normal((2, 5, 8)))
    a = layer.last_attention
    assert np.allclose(a.sum(-1), 1.0)
    if causal:
        assert np.allclose(np.triu(a[0, 0], 1), 0.0)


def test_pooling_and_flatten(rng):
    _check(nn.GlobalAvgPool1D(), rng.standard_normal((2, 5, 3)))
    _check(nn.LastTimestep(), rng.standard_normal((2, 5, 3)))
    _check(nn.Flatten(), rng.standard_normal((2, 5, 3)))


@pytest.mark.parametrize("arch", list(ARCHITECTURES))
def test_full_architectures(arch, rng):
    model, _ = build_model(arch, window=8, n_features=4, params={"hidden": 6, "channels": 6, "d_model": 8, "heads": 2, "ff": 12, "layers": 2}, seed=1)
    _check(model, rng.standard_normal((3, 8, 4)), max_checks=12)


@pytest.mark.parametrize("name", list(nn.LOSSES))
def test_losses(name, rng):
    fn = nn.LOSSES[name]
    pred = rng.standard_normal((6, 1))
    y = (rng.random((6, 1)) > 0.5).astype(float) if name == "bce" else rng.standard_normal((6, 1))
    _, g = fn(pred, y)
    eps = 1e-6
    num = np.zeros_like(pred)
    for i in range(pred.shape[0]):
        p1, p2 = pred.copy(), pred.copy()
        p1[i] += eps
        p2[i] -= eps
        num[i] = (fn(p1, y)[0] - fn(p2, y)[0]) / (2 * eps)
    assert np.allclose(num, g, atol=1e-7)


def test_dropout_scaling_and_eval(rng):
    d = nn.Dropout(0.5, rng)
    x = np.ones((2000, 10))
    assert np.allclose(d.forward(x, training=False), x)
    y = d.forward(x, training=True)
    assert abs(y.mean() - 1.0) < 0.05  # inverted dropout keeps the expectation
    g = d.backward(np.ones_like(x))
    assert np.array_equal(g, d._mask)


def test_gradcheck_detects_a_wrong_backward(rng):
    """Negative control: a backward pass that is off by 1% must be caught."""

    class BrokenDense(nn.Dense):
        def backward(self, grad):
            dx = super().backward(grad)
            self.W.grad *= 1.01
            return dx

    errs = nn.gradcheck(BrokenDense(5, 3, rng), rng.standard_normal((4, 5)))
    assert errs["0:W"] > 1e-3
    assert errs["input"] < TOL
