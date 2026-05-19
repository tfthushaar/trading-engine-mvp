"""
Explanation Ranker.

Assigns a confidence score to explanations based on signal strength,
consistency across trades, and statistical significance.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)


class ExplanationRanker:
    """Scores explanations to convey confidence in the insights."""

    def rank(
        self,
        features: pd.DataFrame,
        targets: pd.Series,
        shap_values: dict[str, float]
    ) -> float:
        """Calculate a single confidence score for the explanation.

        Parameters
        ----------
        features : pd.DataFrame
            Feature matrix (X) used for SHAP analysis.
        targets : pd.Series
            Target values (y) (e.g., PnL).
        shap_values : dict
            Dictionary of SHAP importance scores.

        Returns
        -------
        float
            Confidence score between 0.0 and 1.0.
        """
        if features.empty or targets.empty or not shap_values:
            logger.warning("Empty data provided to ExplanationRanker.")
            return 0.0

        # We base confidence on three proxies:
        # 1. Signal strength: Do the top features clearly dominate the others?
        # 2. Consistency: Variance of model targets (simulated R^2 or correlation strength)
        # 3. Sample size: More trades = higher confidence

        scores = list(shap_values.values())
        if sum(scores) == 0:
            return 0.0

        # 1. Signal strength (Domination of top 3 features)
        scores.sort(reverse=True)
        top_3_sum = sum(scores[:3])
        total_sum = sum(scores)
        signal_strength = top_3_sum / total_sum if total_sum > 0 else 0.0

        # 2. Consistency (Naive correlation of top feature with target)
        top_feature = max(shap_values, key=shap_values.get)
        if top_feature in features.columns and features[top_feature].nunique() > 1:
            try:
                corr = features[top_feature].corr(targets)
                consistency = abs(corr) if not pd.isna(corr) else 0.0
            except:
                consistency = 0.0
        else:
            consistency = 0.0

        # 3. Sample size score (Logistic scaling: 0 at 0 trades, ~0.9 at 100 trades)
        n_trades = len(features)
        sample_size_score = 1.0 - np.exp(-n_trades / 30.0)

        # Composite score
        # 40% strength, 40% consistency, 20% sample size
        confidence = (0.4 * signal_strength) + (0.4 * consistency) + (0.2 * sample_size_score)

        return float(np.clip(confidence, 0.0, 1.0))
