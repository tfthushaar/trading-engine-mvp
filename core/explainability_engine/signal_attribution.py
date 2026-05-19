"""
Signal Attribution.

Categorizes and aggregates SHAP feature importances into broader signal
categories (momentum, macro, sentiment, events) to determine the
dominant market factors driving the strategy.
"""

from __future__ import annotations

from typing import Any
from utils.logger import get_logger

logger = get_logger(__name__)


class SignalAttributor:
    """Aggregates feature-level importances into category-level drivers."""

    def __init__(self) -> None:
        self.category_mapping = {
            "price_momentum_5d": "price_momentum",
            "price_momentum_20d": "price_momentum",
            "volatility_20d": "price_momentum",
            "sma_50_ratio": "price_momentum",
            "macro_indicator_change": "macro_indicators",
            "news_sentiment_score": "news_sentiment",
            "social_sentiment_score": "social_sentiment",
            "sector_sentiment_score": "sector_sentiment",
            "event_impact_score": "market_events"
        }

        self.super_categories = {
            "price_momentum": "momentum",
            "macro_indicators": "macro_environment",
            "news_sentiment": "sentiment_shifts",
            "social_sentiment": "sentiment_shifts",
            "sector_sentiment": "sector_rotation",
            "market_events": "event_driven"
        }

    def attribute(self, shap_values: dict[str, float]) -> dict[str, Any]:
        """Aggregate SHAP values into signal categories and market factors.

        Parameters
        ----------
        shap_values : dict
            Mapping of feature names to their SHAP importance scores.

        Returns
        -------
        dict
            Contains 'signal_attribution' (fine-grained) and 
            'dominant_market_factors' (high-level drivers).
        """
        signal_attribution: dict[str, float] = {}
        dominant_factors: dict[str, float] = {}

        total_importance = sum(shap_values.values())
        if total_importance == 0:
            total_importance = 1.0  # Avoid division by zero

        for feature, score in shap_values.items():
            category = self.category_mapping.get(feature, "other")
            normalized_score = score / total_importance

            # Fine-grained attribution
            signal_attribution[category] = signal_attribution.get(category, 0.0) + normalized_score

            # High-level factor attribution
            factor = self.super_categories.get(category, "other")
            dominant_factors[factor] = dominant_factors.get(factor, 0.0) + normalized_score

        # Sort both by importance
        signal_attribution = {k: v for k, v in sorted(signal_attribution.items(), key=lambda i: i[1], reverse=True)}
        dominant_factors = {k: v for k, v in sorted(dominant_factors.items(), key=lambda i: i[1], reverse=True)}

        return {
            "signal_attribution": signal_attribution,
            "dominant_market_factors": dominant_factors
        }
