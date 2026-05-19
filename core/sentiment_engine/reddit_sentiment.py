"""
Reddit sentiment processor.

Reads unprocessed posts from ``social_sentiment``, cleans the text
(strips URLs, markdown artifacts, excess whitespace), runs FinBERT on the
concatenation of title + cleaned selftext, computes an engagement-weighted
sentiment score, and writes results to ``social_sentiment_scores``.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from database.db_manager import DatabaseManager
from sentiment_engine.finbert_model import FinBERTAnalyzer
from utils.config import SENTIMENT_BATCH_SIZE
from utils.logger import get_logger

logger = get_logger(__name__)


class RedditSentimentProcessor:
    """Processes Reddit posts for sentiment with engagement weighting."""

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
        """Score all unprocessed Reddit posts and persist results.

        Returns the number of posts processed.
        """
        posts = self.db.fetch_unprocessed_social()
        if not posts:
            logger.info("No unprocessed Reddit posts found.")
            return 0

        logger.info(
            "Processing sentiment for %d Reddit posts …", len(posts)
        )

        # Build cleaned text for each post
        texts = [self._build_text(p) for p in posts]

        # Batch predict
        predictions = self.analyzer.predict_batch(
            texts, batch_size=SENTIMENT_BATCH_SIZE
        )

        # Build records for insertion
        records: list[dict[str, Any]] = []
        for post, (label, score) in zip(posts, predictions):
            full_text = self._build_text(post)
            tickers = self.analyzer.extract_tickers(full_text)
            engagement = self._compute_engagement(post)

            records.append(
                {
                    "post_id": post["post_id"],
                    "subreddit": post.get("subreddit"),
                    "timestamp": post.get("created_utc"),
                    "sentiment_label": label,
                    "sentiment_score": score,
                    "engagement_score": engagement,
                    "tickers_detected": json.dumps(tickers),
                }
            )

        inserted = self.db.insert_social_sentiment_scores(records)
        logger.info(
            "Reddit sentiment processing complete — %d posts scored.",
            inserted,
        )
        return inserted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_text(text: str) -> str:
        """Strip URLs, markdown syntax, and excess whitespace."""
        if not text:
            return ""
        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        # Remove markdown links [text](url)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Remove markdown bold/italic markers
        text = re.sub(r"[*_~`#>]+", " ", text)
        # Remove reddit-specific formatting
        text = re.sub(r"/?(r|u)/\w+", "", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _build_text(self, post: dict[str, Any]) -> str:
        """Concatenate title + cleaned selftext for analysis."""
        title = post.get("title") or ""
        selftext = self._clean_text(post.get("selftext") or "")
        combined = f"{title}. {selftext}".strip()
        # Cap length to avoid extremely long posts
        return combined[:2000]

    @staticmethod
    def _compute_engagement(post: dict[str, Any]) -> float:
        """Compute engagement score: ``score * log(1 + num_comments)``."""
        upvotes = post.get("score") or 0
        comments = post.get("num_comments") or 0
        return round(upvotes * math.log(1 + comments), 4)
