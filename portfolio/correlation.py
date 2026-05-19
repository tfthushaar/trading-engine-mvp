"""Portfolio correlation — re-exports from risk_metrics to keep import paths clean."""
from portfolio.risk_metrics import compute_correlation_matrix

__all__ = ["compute_correlation_matrix"]
