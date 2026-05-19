"""
Strategy Explainer.

Coordinates the explainability workflow. Reconstructs features, applies
SHAP analysis, attributes signals, ranks explanation confidence, and
generates human-readable explanation texts.
"""

from __future__ import annotations

import uuid
import json
from datetime import datetime
from typing import Any

from explainability_engine.feature_builder import FeatureBuilder
from explainability_engine.shap_analyzer import ShapAnalyzer
from explainability_engine.signal_attribution import SignalAttributor
from explainability_engine.explanation_ranker import ExplanationRanker
from utils.logger import get_logger

logger = get_logger(__name__)


class StrategyExplainer:
    """End-to-end explainability pipeline for a backtested strategy."""

    def __init__(self, db: Any) -> None:
        self.db = db
        self.feature_builder = FeatureBuilder(db)
        self.shap_analyzer = ShapAnalyzer()
        self.attributor = SignalAttributor()
        self.ranker = ExplanationRanker()

    def generate_explanation(
        self, backtest_result: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run the explainability pipeline on a backtest result.

        Parameters
        ----------
        backtest_result : dict
            The complete backtest output dictionary including 'trades'.

        Returns
        -------
        dict | None
            A strategy_explanations record ready for database insertion,
            or None if explanation fails.
        """
        sid = backtest_result.get("strategy_id")
        bid = backtest_result.get("backtest_id")
        start_date = backtest_result.get("start_date")
        end_date = backtest_result.get("end_date")
        trades = backtest_result.get("trades", [])

        if not trades:
            logger.warning("No trades found in backtest %s. Cannot explain.", bid)
            return None

        # Just grab the asset from the first trade
        asset = trades[0].get("asset", "unknown")

        logger.info("Generating explanation for Strategy '%s' (backtest %s)", sid, bid)

        # 1. Build features
        X, y = self.feature_builder.build(trades, asset, start_date, end_date)
        if X.empty or y.empty:
            logger.warning("Feature building failed for %s", bid)
            return None

        # 2. Applies SHAP analysis
        shap_res = self.shap_analyzer.analyze(X, y)
        shap_values = shap_res.get("shap_values", {})
        feature_importance = shap_res.get("feature_importance", {})

        # 3. Attribute signals
        attr_res = self.attributor.attribute(shap_values)
        signal_attribution = attr_res.get("signal_attribution", {})
        dominant_factors = attr_res.get("dominant_market_factors", {})

        # 4. Rank Explanation (Confidence Score)
        confidence = self.ranker.rank(X, y, shap_values)

        # 5. Generate human-readable text
        text = self._generate_text(
            signal_attribution=signal_attribution,
            dominant_factors=dominant_factors,
            shap_values=shap_values,
            trades_count=len(trades),
            pnl=sum(y)
        )

        return {
            "explanation_id": str(uuid.uuid4()),
            "strategy_id": sid,
            "backtest_id": bid,
            "timestamp": datetime.utcnow().isoformat(),
            "key_signals": json.dumps(list(signal_attribution.keys())[:3]),
            "feature_importance": json.dumps(feature_importance),
            "shap_values": json.dumps(shap_values),
            "dominant_market_factors": json.dumps(dominant_factors),
            "explanation_text": text,
            "confidence_score": confidence
        }

    def _generate_text(
        self,
        signal_attribution: dict[str, float],
        dominant_factors: dict[str, float],
        shap_values: dict[str, float],
        trades_count: int,
        pnl: float
    ) -> str:
        """Constructs a narrative explaining the strategy's performance."""
        if not shap_values:
            return "Insufficient data to generate a meaningful explanation."

        top_factors = list(dominant_factors.keys())[:2]
        top_factor_1 = top_factors[0] if len(top_factors) > 0 else "unknown"
        top_factor_2 = top_factors[1] if len(top_factors) > 1 else None

        top_features = list(shap_values.keys())[:2]
        f1 = top_features[0].replace("_", " ") if len(top_features) > 0 else ""
        f2 = top_features[1].replace("_", " ") if len(top_features) > 1 else ""

        pnl_desc = "profitable" if pnl >= 0 else "unprofitable"

        text = (
            f"Over {trades_count} trades, this strategy was generally {pnl_desc}. "
            f"Its performance was primarily driven by {top_factor_1.replace('_', ' ')}"
        )
        if top_factor_2:
            text += f" and {top_factor_2.replace('_', ' ')}."
        else:
            text += "."

        text += (
            f" SHAP analysis indicates that {f1} provided the strongest predictive power"
        )
        if f2:
            text += f", followed by {f2}."
        else:
            text += "."

        return text
