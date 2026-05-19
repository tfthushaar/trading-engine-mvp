"""
Market-event detector.

Scans recent ``news_sentiment`` rows for keyword patterns that signal
important financial events (earnings, M&A, policy changes, interest-rate
decisions).  Assigns an event type, related tickers, and a confidence
score based on keyword density and sentiment extremity.

Results are stored in the ``market_events`` table.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from database.db_manager import DatabaseManager
from utils.config import EVENT_KEYWORDS
from utils.logger import get_logger

logger = get_logger(__name__)


class EventDetector:
    """Detects market events from news-sentiment data."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Core detection
    # ------------------------------------------------------------------
    def detect_events(self, lookback_hours: int = 24) -> int:
        """Scan recent news-sentiment rows and persist detected events.

        Returns the number of events detected.
        """
        articles = self.db.fetch_recent_news_sentiment(hours=lookback_hours)
        if not articles:
            logger.info("No recent news-sentiment data to scan for events.")
            return 0

        logger.info(
            "Scanning %d recent articles for market events …", len(articles)
        )

        records: list[dict[str, Any]] = []

        for article in articles:
            headline = (article.get("headline") or "").lower()
            entities = article.get("entities_detected") or "[]"
            # Combine headline with entities for broader matching
            full_text = f"{headline} {entities}".lower()

            for event_type, keywords in EVENT_KEYWORDS.items():
                matched_keywords = [
                    kw for kw in keywords if kw.lower() in full_text
                ]
                if not matched_keywords:
                    continue

                # Compute confidence based on keyword density + sentiment
                confidence = self._compute_confidence(
                    matched_count=len(matched_keywords),
                    total_keywords=len(keywords),
                    sentiment_score=article.get("sentiment_score", 0.0),
                )

                # Only record high-enough-confidence events
                if confidence < 0.3:
                    continue

                # Parse related tickers from the article
                tickers_raw = article.get("related_tickers") or "[]"
                try:
                    tickers = json.loads(tickers_raw)
                except (json.JSONDecodeError, TypeError):
                    tickers = []

                # Deterministic event ID to avoid duplicates
                event_id = self._make_event_id(
                    article["article_id"], event_type
                )

                records.append(
                    {
                        "event_id": event_id,
                        "timestamp": article.get("timestamp"),
                        "event_type": event_type,
                        "related_tickers": json.dumps(tickers),
                        "confidence_score": confidence,
                        "source_article_id": article["article_id"],
                    }
                )

        if not records:
            logger.info("No market events detected in this scan.")
            return 0

        inserted = self.db.insert_market_events(records)
        logger.info("Detected and stored %d market events.", inserted)
        return inserted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_confidence(
        matched_count: int,
        total_keywords: int,
        sentiment_score: float,
    ) -> float:
        """Confidence score [0, 1] from keyword density + sentiment extremity.

        - Keyword density contributes 60 % of the score.
        - Sentiment extremity (abs value) contributes 40 %.
        """
        keyword_density = min(matched_count / max(total_keywords * 0.3, 1), 1.0)
        sentiment_extremity = min(abs(sentiment_score), 1.0)
        confidence = 0.6 * keyword_density + 0.4 * sentiment_extremity
        return round(confidence, 4)

    @staticmethod
    def _make_event_id(article_id: str, event_type: str) -> str:
        """Deterministic event ID from article + event type."""
        raw = f"{article_id}:{event_type}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
