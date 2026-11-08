"""A small neural-network library written from scratch in NumPy (forward and backward passes by hand)."""
from backend.dl.nn.attention import MultiHeadSelfAttention, PositionalEncoding, softmax
from backend.dl.nn.conv import Conv1D
from backend.dl.nn.core import DTYPE, Layer, Parameter, Residual, Sequential, count_parameters, iter_layers
from backend.dl.nn.gradcheck import gradcheck
from backend.dl.nn.layers import (
    GELU,
    Dense,
    Dropout,
    Flatten,
    GlobalAvgPool1D,
    LastTimestep,
    LayerNorm,
    LeakyReLU,
    ReLU,
    Sigmoid,
    Tanh,
    sigmoid,
)
from backend.dl.nn.losses import LOSSES, bce_with_logits, huber, mse
from backend.dl.nn.optim import SGD, Adam, clip_grad_norm, make_optimizer
from backend.dl.nn.recurrent import GRU, LSTM

__all__ = [
    "DTYPE", "Layer", "Parameter", "Sequential", "Residual", "count_parameters", "iter_layers",
    "Dense", "ReLU", "LeakyReLU", "Tanh", "Sigmoid", "GELU", "Dropout", "LayerNorm", "Flatten",
    "GlobalAvgPool1D", "LastTimestep", "sigmoid", "LSTM", "GRU", "Conv1D", "PositionalEncoding",
    "MultiHeadSelfAttention", "softmax", "LOSSES", "bce_with_logits", "mse", "huber",
    "SGD", "Adam", "make_optimizer", "clip_grad_norm", "gradcheck",
]
