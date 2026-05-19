"""
Hypothesis Ranker — scores each candidate hypothesis across five
dimensions and computes a weighted composite confidence score.

Scoring dimensions
------------------
| Dimension             | Weight | Source                           |
|-----------------------|--------|----------------------------------|
| Evidence strength     | 0.30   | Count of concrete signals cited  |
| Sentiment alignment   | 0.20   | Sentiment data corroboration     |
| Macro alignment       | 0.15   | Macro regime consistency         |
| Novelty               | 0.20   | Dissimilarity vs recent ideas    |
| Clarity & testability | 0.15   | Structural checks (direction, …)|
"""

from __future__ import annotations


import re
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

# Weight vector (must sum to 1.0)
_WEIGHTS = {
    "evidence_strength": 0.30,
    "sentiment_alignment": 0.20,
    "macro_alignment": 0.15,
    "novelty": 0.20,
    "clarity": 0.15,
}

# Direction keywords
_DIRECTION_KEYWORDS = {
    "bullish", "bearish", "relative outperformance", "mean reversion",
}

# Causal / conditional language markers
_CAUSAL_MARKERS = re.compile(
    r"\b(when|if|as|because|due to|driven by|given that|historically|tends to|"
    r"may|could|suggests|implies|correlat|leading to|following)\b",
    re.IGNORECASE,
)

# Signal evidence markers
_SIGNAL_MARKERS = re.compile(
    r"\b(sentiment|yield|CPI|inflation|rate|volatility|momentum|"
    r"earnings|revenue|EPS|GDP|FOMC|spread|correlation|volume|"
    r"outperform|underperform|beta|alpha|return|drawdown)\b",
    re.IGNORECASE,
)


class HypothesisRanker:
    """Scores and ranks candidate hypotheses."""

    def rank(
        self,
        candidates: list[dict[str, Any]],
        snapshot: dict[str, Any],
        recent_hypotheses: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Score each candidate and add ``confidence_score`` and
        ``_scores`` sub-dict.  Returns candidates sorted by descending
        confidence.

        Parameters
        ----------
        candidates
            Raw hypothesis dicts from the generator.
        snapshot
            MarketSnapshot (used for alignment checks).
        recent_hypotheses
            Previously stored hypotheses (for novelty scoring).
        """
        recent = recent_hypotheses or []

        for h in candidates:
            scores = {
                "evidence_strength": self._score_evidence(h),
                "sentiment_alignment": self._score_sentiment_alignment(
                    h, snapshot
                ),
                "macro_alignment": self._score_macro_alignment(h, snapshot),
                "novelty": self._score_novelty(h, recent),
                "clarity": self._score_clarity(h),
            }
            composite = sum(
                scores[dim] * _WEIGHTS[dim] for dim in _WEIGHTS
            )
            h["confidence_score"] = round(max(0.0, min(1.0, composite)), 4)
            h["_scores"] = scores

        # Sort descending by confidence
        candidates.sort(key=lambda x: x["confidence_score"], reverse=True)
        logger.info(
            "Ranked %d hypotheses (top score: %.3f).",
            len(candidates),
            candidates[0]["confidence_score"] if candidates else 0,
        )
        return candidates

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------
    def _score_evidence(self, h: dict) -> float:
        """Count concrete signal references in hypothesis text and
        supporting_signals."""
        text = (h.get("hypothesis_text", "") + " "
                + str(h.get("supporting_signals", "")))
        matches = _SIGNAL_MARKERS.findall(text)
        # 1 signal → 0.3, 3 → 0.6, 5+ → 1.0
        return min(len(matches) / 5.0, 1.0)

    def _score_sentiment_alignment(
        self, h: dict, snapshot: dict
    ) -> float:
        """Check whether the hypothesis direction aligns with the overall
        sentiment bias visible in the snapshot."""
        direction = (h.get("expected_direction") or "").lower()
        sentiment_text = snapshot.get("sentiment_summary", "")

        # Parse avg sentiment score from summary
        avg_score = self._extract_avg_sentiment(sentiment_text)
        if avg_score is None:
            return 0.5  # neutral if unknown

        if direction in ("bullish", "relative outperformance"):
            return min(max((avg_score + 1) / 2, 0.0), 1.0)
        elif direction == "bearish":
            return min(max((-avg_score + 1) / 2, 0.0), 1.0)
        else:
            return 0.5  # mean reversion is direction-agnostic

    def _score_macro_alignment(
        self, h: dict, snapshot: dict
    ) -> float:
        """Simple heuristic: check whether hypothesis text references
        macro indicators present in the snapshot."""
        macro_text = snapshot.get("macro_summary", "").lower()
        hyp_text = (h.get("hypothesis_text", "") + " "
                    + str(h.get("trigger_conditions", ""))).lower()

        macro_terms = ["rate", "cpi", "inflation", "gdp", "unemployment",
                       "fed", "fomc", "monetary", "fiscal"]
        hits = sum(1 for term in macro_terms
                   if term in hyp_text and term in macro_text)
        return min(hits / 3.0, 1.0)

    def _score_novelty(
        self, h: dict, recent: list[dict]
    ) -> float:
        """Measure dissimilarity from recent hypotheses using word overlap."""
        if not recent:
            return 0.9  # novel by definition if nothing to compare

        h_words = set(
            (h.get("hypothesis_text", "") + " " + h.get("title", ""))
            .lower().split()
        )
        if not h_words:
            return 0.5

        max_sim = 0.0
        for prev in recent:
            prev_words = set(
                (prev.get("hypothesis_text", "") + " " + prev.get("title", ""))
                .lower().split()
            )
            if not prev_words:
                continue
            intersection = h_words & prev_words
            union = h_words | prev_words
            jaccard = len(intersection) / len(union) if union else 0.0
            max_sim = max(max_sim, jaccard)

        return 1.0 - max_sim  # higher novelty = lower similarity

    def _score_clarity(self, h: dict) -> float:
        """Check structural quality: direction, holding period, causal
        language, and sufficient length."""
        score = 0.0
        text = h.get("hypothesis_text", "")

        # Has valid direction
        direction = (h.get("expected_direction") or "").lower()
        if direction in _DIRECTION_KEYWORDS:
            score += 0.25

        # Has holding period
        if h.get("holding_period"):
            score += 0.25

        # Contains causal / conditional language
        if _CAUSAL_MARKERS.search(text):
            score += 0.25

        # Sufficient length (≥ 50 chars)
        if len(text) >= 50:
            score += 0.25

        return score

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_avg_sentiment(summary_text: str) -> float | None:
        """Pull the 'Avg sentiment score: X.XXX' value from the
        sentiment summary string."""
        m = re.search(r"Avg sentiment score:\s*([-\d.]+)", summary_text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        return None
