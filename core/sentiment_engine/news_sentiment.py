"""
News sentiment processor.

Reads unprocessed articles from ``news_articles``, runs FinBERT inference on
the concatenation of title + description, extracts tickers and entities, and
writes results to ``news_sentiment``.
"""

from __future__ import annotations

import json
from typing import Any

from database.db_manager import DatabaseManager
from sentiment_engine.finbert_model import FinBERTAnalyzer
from utils.config import SENTIMENT_BATCH_SIZE
from utils.logger import get_logger

logger = get_logger(__name__)


class NewsSentimentProcessor:
    """Processes news articles for sentiment, tickers, and entities."""

    def __init__(
        self,
        db: DatabaseManager,
        analyzer: FinBERTAnalyzer | None = None,
    ) -> None:
        self.db = db
        self.analyzer = analyzer or FinBERTAnalyzer()

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------
    def process_all(self) -> int:
        """Score all unprocessed news articles and persist results.

        Returns the number of articles processed.
        """
        articles = self.db.fetch_unprocessed_news()
        if not articles:
            logger.info("No unprocessed news articles found.")
            return 0

        logger.info(
            "Processing sentiment for %d news articles …", len(articles)
        )

        # Build text for each article: title + description
        texts = [
            self._build_text(a) for a in articles
        ]

        # Batch predict
        predictions = self.analyzer.predict_batch(
            texts, batch_size=SENTIMENT_BATCH_SIZE
        )

        # Build records for insertion
        records: list[dict[str, Any]] = []
        for article, (label, score) in zip(articles, predictions):
            full_text = self._build_text(article)
            tickers = self.analyzer.extract_tickers(full_text)
            entities = self.analyzer.extract_entities(full_text)

            records.append(
                {
                    "article_id": article["article_id"],
                    "timestamp": article.get("published_at"),
                    "headline": article.get("title", ""),
                    "sentiment_label": label,
                    "sentiment_score": score,
                    "entities_detected": json.dumps(entities),
                    "related_tickers": json.dumps(tickers),
                }
            )

        inserted = self.db.insert_news_sentiment(records)
        logger.info(
            "News sentiment processing complete — %d articles scored.",
            inserted,
        )
        return inserted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_text(article: dict[str, Any]) -> str:
        """Concatenate title and description for analysis."""
        title = article.get("title") or ""
        description = article.get("description") or ""
        return f"{title}. {description}".strip()
