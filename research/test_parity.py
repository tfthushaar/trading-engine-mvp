"""
Parity between the from-scratch NumPy engine and the PyTorch reference.

For every architecture: copy PyTorch weights into the NumPy model, then require identical
forward outputs, identical parameter gradients and identical input gradients (float64).

Run:  .venv-research/Scripts/python -m pytest research/test_parity.py -q
"""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from backend.dl.architectures import ARCHITECTURES, build_model  # noqa: E402
from research.torch_models import build_torch  # noqa: E402

PARAMS = {"hidden": 7, "layers": 2, "channels": 6, "kernel": 3, "d_model": 8, "heads": 2, "ff": 12, "dropout": 0.0}
W, F, B = 9, 4, 5


@pytest.mark.parametrize("arch", list(ARCHITECTURES))
def test_forward_and_backward_parity(arch):
    torch.manual_seed(0)
    tm = build_torch(arch, W, F, PARAMS).double().eval()
    nm, _ = build_model(arch, W, F, PARAMS, seed=0)
    exported = [t.numpy() for t in tm.export("value")]
    params = nm.parameters()
    assert len(exported) == len(params)
    for p, a in zip(params, exported):
        assert p.value.shape == a.shape
        p.value[...] = a

    rng = np.random.default_rng(1)
    x = rng.standard_normal((B, W, F))
    R = rng.standard_normal((B, 1))

    xt = torch.tensor(x, requires_grad=True)
    yt = tm(xt)
    (yt * torch.tensor(R)).sum().backward()

    yn = nm.forward(x.copy(), training=False)
    nm.zero_grad()
    dxn = nm.backward(R)

    assert np.allclose(yn, yt.detach().numpy(), atol=1e-10), "forward mismatch"
    assert np.allclose(dxn, xt.grad.numpy(), atol=1e-10), "input-gradient mismatch"
    for i, (p, g) in enumerate(zip(params, tm.export("grad"))):
        assert np.allclose(p.grad, g.numpy(), atol=1e-10), f"parameter-gradient mismatch at tensor {i}"
