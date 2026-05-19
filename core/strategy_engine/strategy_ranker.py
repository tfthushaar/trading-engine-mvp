"""
Strategy Ranker — scores each validated strategy across five dimensions
and computes a weighted composite confidence score.

Scoring dimensions
------------------
| Dimension           | Weight | Heuristic                              |
|---------------------|--------|----------------------------------------|
| Signal strength     | 0.25   | Count of concrete signal references    |
| Clarity of rules    | 0.25   | Structural completeness checks         |
| Macro alignment     | 0.20   | Macro regime keywords present          |
| Sentiment alignment | 0.15   | Sentiment corroboration with direction |
| Novelty             | 0.15   | Jaccard dissimilarity vs recent strats |
"""

from __future__ import annotations


import re
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

# Weight vector (must sum to 1.0)
_WEIGHTS = {
    "signal_strength": 0.25,
    "clarity_of_rules": 0.25,
    "macro_alignment": 0.20,
    "sentiment_alignment": 0.15,
    "novelty": 0.15,
}

# Signal evidence markers
_SIGNAL_MARKERS = re.compile(
    r"\b(sentiment|yield|CPI|inflation|rate|volatility|momentum|"
    r"earnings|revenue|EPS|GDP|FOMC|spread|correlation|volume|"
    r"outperform|underperform|beta|alpha|return|drawdown|"
    r"moving.?average|RSI|MACD|bollinger|z.?score|standard.?deviation|"
    r"stop.?loss|breakout|reversion|divergence)\b",
    re.IGNORECASE,
)

# Macro keywords
_MACRO_MARKERS = re.compile(
    r"\b(rate|CPI|inflation|GDP|unemployment|fed|FOMC|monetary|"
    r"fiscal|yield|treasury|bond|macro|regime)\b",
    re.IGNORECASE,
)

# Sentiment keywords
_SENTIMENT_MARKERS = re.compile(
    r"\b(sentiment|bullish|bearish|positive|negative|fear|greed|"
    r"social|engagement|news.?flow|FinBERT)\b",
    re.IGNORECASE,
)


class StrategyRanker:
    """Scores and ranks validated strategies."""

    def rank(
        self,
        strategies: list[dict[str, Any]],
        recent_strategies: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Score each strategy and sort by descending confidence.

        Parameters
        ----------
        strategies
            Validated strategy dicts.
        recent_strategies
            Recent strategies from DB (for novelty scoring).

        Returns
        -------
        list[dict]
            Strategies sorted by ``confidence_score`` (descending).
        """
        recent = recent_strategies or []

        for s in strategies:
            scores = {
                "signal_strength": self._score_signal_strength(s),
                "clarity_of_rules": self._score_clarity(s),
                "macro_alignment": self._score_macro(s),
                "sentiment_alignment": self._score_sentiment(s),
                "novelty": self._score_novelty(s, recent),
            }
            composite = sum(
                scores[dim] * _WEIGHTS[dim] for dim in _WEIGHTS
            )
            s["confidence_score"] = round(max(0.0, min(1.0, composite)), 4)
            s["_scores"] = scores

        strategies.sort(key=lambda x: x["confidence_score"], reverse=True)
        logger.info(
            "Ranked %d strategies (top score: %.3f).",
            len(strategies),
            strategies[0]["confidence_score"] if strategies else 0,
        )
        return strategies

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------
    def _score_signal_strength(self, s: dict) -> float:
        """Count concrete signal references across all strategy fields."""
        text = " ".join([
            str(s.get("entry_conditions", "")),
            str(s.get("exit_conditions", "")),
            str(s.get("risk_rules", "")),
            s.get("strategy_name", ""),
        ])
        matches = _SIGNAL_MARKERS.findall(text)
        # 2 signals → 0.33, 4 → 0.67, 6+ → 1.0
        return min(len(matches) / 6.0, 1.0)

    def _score_clarity(self, s: dict) -> float:
        """Check structural completeness of the strategy."""
        score = 0.0

        # Has entry conditions with content
        entry = s.get("entry_conditions", "")
        if self._has_content(entry):
            score += 0.2

        # Has exit conditions with content
        exit_c = s.get("exit_conditions", "")
        if self._has_content(exit_c):
            score += 0.2

        # Has stop loss
        risk = str(s.get("risk_rules", "")).lower()
        if "stop" in risk and re.search(r"\d", risk):
            score += 0.2

        # Has position sizing
        sizing = str(s.get("position_sizing", "")).lower()
        if sizing and sizing not in ("", "null", "none", '""'):
            score += 0.2

        # Has explicit holding period
        if s.get("holding_period"):
            score += 0.2

        return score

    def _score_macro(self, s: dict) -> float:
        """Check whether strategy references macro indicators."""
        text = " ".join([
            str(s.get("entry_conditions", "")),
            str(s.get("exit_conditions", "")),
            s.get("strategy_name", ""),
        ])
        matches = _MACRO_MARKERS.findall(text)
        return min(len(matches) / 3.0, 1.0)

    def _score_sentiment(self, s: dict) -> float:
        """Check whether strategy leverages sentiment data."""
        text = " ".join([
            str(s.get("entry_conditions", "")),
            str(s.get("exit_conditions", "")),
            s.get("strategy_name", ""),
        ])
        matches = _SENTIMENT_MARKERS.findall(text)
        return min(len(matches) / 3.0, 1.0)

    def _score_novelty(
        self, s: dict, recent: list[dict]
    ) -> float:
        """Measure dissimilarity from recent strategies using word overlap."""
        if not recent:
            return 0.9

        s_words = set(self._text_for_novelty(s).lower().split())
        if not s_words:
            return 0.5

        max_sim = 0.0
        for prev in recent:
            prev_words = set(self._text_for_novelty(prev).lower().split())
            if not prev_words:
                continue
            intersection = s_words & prev_words
            union = s_words | prev_words
            jaccard = len(intersection) / len(union) if union else 0.0
            max_sim = max(max_sim, jaccard)

        return 1.0 - max_sim

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _has_content(value: Any) -> bool:
        """Check whether a field has meaningful content."""
        if not value:
            return False
        s = str(value).strip()
        return s not in ("", "[]", "{}", '""', "null", "None")

    @staticmethod
    def _text_for_novelty(s: dict) -> str:
        """Combine key fields into a single string for Jaccard comparison."""
        return " ".join([
            s.get("strategy_name", ""),
            str(s.get("entry_conditions", "")),
            str(s.get("exit_conditions", "")),
            s.get("asset_scope", ""),
        ])
