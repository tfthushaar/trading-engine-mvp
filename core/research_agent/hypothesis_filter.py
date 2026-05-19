"""
Hypothesis Filter — rejects low-quality, vague, or duplicate hypotheses
before they are persisted to the database.

Rejection criteria
------------------
1. confidence_score below HYPOTHESIS_MIN_CONFIDENCE
2. Missing required fields (direction, holding_period, asset_scope)
3. hypothesis_text too short (< 50 chars) or lacks ticker/sector reference
4. Near-duplicate of a recent hypothesis (Jaccard > 0.85)
5. Purely descriptive (no causal / conditional language)
"""

from __future__ import annotations

import re
from typing import Any

from utils.config import HYPOTHESIS_MIN_CONFIDENCE, KNOWN_TICKERS, SECTOR_MAPPING
from utils.logger import get_logger

logger = get_logger(__name__)

# Causal / conditional language markers
_CAUSAL_MARKERS = re.compile(
    r"\b(when|if|as|because|due to|driven by|given that|historically|tends to|"
    r"may|could|suggests|implies|correlat|leading to|following)\b",
    re.IGNORECASE,
)

_VALID_DIRECTIONS = {
    "bullish", "bearish", "relative outperformance", "mean reversion",
}

_SECTOR_NAMES = {s.lower() for s in SECTOR_MAPPING}


class HypothesisFilter:
    """Filters candidate hypotheses, returning only high-quality ones."""

    def filter(
        self,
        candidates: list[dict[str, Any]],
        recent_hypotheses: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply all quality gates and return accepted hypotheses.

        Parameters
        ----------
        candidates
            Scored hypothesis dicts (with ``confidence_score``).
        recent_hypotheses
            Recent hypotheses from DB for deduplication.

        Returns
        -------
        list[dict]
            Hypotheses that pass all filters.
        """
        recent = recent_hypotheses or []
        accepted: list[dict[str, Any]] = []

        for h in candidates:
            reason = self._check(h, recent, accepted)
            if reason:
                logger.info(
                    "Rejected hypothesis '%s': %s",
                    (h.get("title") or "")[:60], reason,
                )
                continue
            accepted.append(h)

        logger.info(
            "Filter passed %d / %d candidates.",
            len(accepted), len(candidates),
        )
        return accepted

    # ------------------------------------------------------------------
    # Gate logic
    # ------------------------------------------------------------------
    def _check(
        self,
        h: dict[str, Any],
        recent: list[dict[str, Any]],
        already_accepted: list[dict[str, Any]],
    ) -> str | None:
        """Return a rejection reason, or ``None`` if the hypothesis passes."""

        text = h.get("hypothesis_text", "")
        title = h.get("title", "")

        # 1. Confidence floor
        score = h.get("confidence_score", 0)
        if score < HYPOTHESIS_MIN_CONFIDENCE:
            return f"confidence {score:.3f} < {HYPOTHESIS_MIN_CONFIDENCE}"

        # 2. Required fields
        direction = (h.get("expected_direction") or "").lower()
        if direction not in _VALID_DIRECTIONS:
            return f"invalid direction: '{direction}'"

        if not h.get("holding_period"):
            return "missing holding_period"

        if not h.get("asset_scope"):
            return "missing asset_scope"

        # 3. Minimum text quality
        if len(text) < 50:
            return f"hypothesis_text too short ({len(text)} chars)"

        if not self._has_asset_reference(text + " " + title):
            return "no ticker or sector reference found"

        # 4. Must contain causal / conditional language
        if not _CAUSAL_MARKERS.search(text):
            return "purely descriptive — no causal/conditional language"

        # 5. Near-duplicate check against recent + already-accepted
        pool = recent + already_accepted
        if self._is_duplicate(h, pool):
            return "near-duplicate of a recent hypothesis"

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _has_asset_reference(text: str) -> bool:
        """Check whether text references at least one known ticker or
        sector name."""
        upper = text.upper()
        for ticker in KNOWN_TICKERS:
            # Word-boundary check to avoid false positives
            if re.search(r"\b" + re.escape(ticker) + r"\b", upper):
                return True
        lower = text.lower()
        for sector in _SECTOR_NAMES:
            if sector in lower:
                return True
        # Also accept generic asset classes
        for term in ("s&p", "treasury", "bond", "gold", "crude",
                     "index", "etf", "sector"):
            if term in lower:
                return True
        return False

    @staticmethod
    def _is_duplicate(
        h: dict, pool: list[dict], threshold: float = 0.85
    ) -> bool:
        """Return True if Jaccard similarity with any pooled hypothesis
        exceeds *threshold*."""
        h_words = set(
            (h.get("hypothesis_text", "") + " " + h.get("title", ""))
            .lower().split()
        )
        if not h_words:
            return False

        for prev in pool:
            prev_words = set(
                (prev.get("hypothesis_text", "") + " " + prev.get("title", ""))
                .lower().split()
            )
            if not prev_words:
                continue
            intersection = h_words & prev_words
            union = h_words | prev_words
            jaccard = len(intersection) / len(union) if union else 0.0
            if jaccard > threshold:
                return True
        return False
