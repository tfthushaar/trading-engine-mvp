"""
SHAP Analyzer.

Uses SHAP (SHapley Additive exPlanations) to identify the contribution
of each feature to strategy performance. Fits a surrogate model (like
RandomForestRegressor) on the feature matrix vs PnL to derive SHAP values.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Any
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    import shap
    from sklearn.ensemble import RandomForestRegressor
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("shap or scikit-learn not available. Falling back to mocked SHAP analysis.")


class ShapAnalyzer:
    """Calculates feature importance using SHAP values and a surrogate model."""

    def analyze(self, X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
        """Run SHAP analysis on the given feature matrix and targets.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix for the strategy's trades.
        y : pd.Series
            Target values (e.g., PnL per trade).

        Returns
        -------
        dict
            Contains two keys: 'shap_values' and 'feature_importance'.
            Both are dicts mapping feature names to numerical values.
        """
        if X.empty or y.empty or len(X) < 5:
            logger.info("Insufficient data for SHAP analysis. Returning empty results.")
            return {"shap_values": {}, "feature_importance": {}}

        if not SHAP_AVAILABLE:
            return self._mock_analyze(X, y)

        try:
            # Fit a surrogate model
            model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
            model.fit(X, y)

            # Compute SHAP values
            explainer = shap.TreeExplainer(model)
            shap_values_matrix = explainer.shap_values(X)

            # Average absolute SHAP values across all samples
            # Output is a single value per feature representing overall importance
            mean_abs_shap = np.abs(shap_values_matrix).mean(axis=0)

            shap_dict = dict(zip(X.columns, mean_abs_shap.tolist()))
            
            # For traditional feature importance
            importance_dict = dict(zip(X.columns, model.feature_importances_.tolist()))

            # Sort both dicts descending
            shap_dict = {k: v for k, v in sorted(shap_dict.items(), key=lambda item: item[1], reverse=True)}
            importance_dict = {k: v for k, v in sorted(importance_dict.items(), key=lambda item: item[1], reverse=True)}

            return {
                "shap_values": shap_dict,
                "feature_importance": importance_dict
            }
        except Exception as e:
            logger.error(f"Error during SHAP analysis: {e}. Falling back to mock.")
            return self._mock_analyze(X, y)

    def _mock_analyze(self, X: pd.DataFrame, y: pd.Series) -> dict[str, Any]:
        """Fallback when shap is not available or errors out."""
        # Just use absolute correlation as a naive proxy for importance
        corrs = {}
        for col in X.columns:
            if X[col].nunique() > 1:
                corr = X[col].corr(y)
                corrs[col] = abs(corr) if not pd.isna(corr) else 0.0
            else:
                corrs[col] = 0.0
        
        # Normalize to look like feature importances (sum to 1)
        total = sum(corrs.values())
        if total > 0:
            corrs = {k: v / total for k, v in corrs.items()}
        
        corrs = {k: v for k, v in sorted(corrs.items(), key=lambda i: i[1], reverse=True)}
        
        return {
            "shap_values": corrs,  # Mocked
            "feature_importance": corrs
        }
