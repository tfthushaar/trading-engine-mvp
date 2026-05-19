"""
Sector-level sentiment aggregator.

Queries recent ``news_sentiment`` and ``social_sentiment_scores``, maps
detected tickers to sectors via ``SECTOR_MAPPING``, and computes aggregate
metrics per sector:

- ``avg_sentiment_score`` — weighted mean of news + social sentiment
- ``news_signal_strength`` — mean absolute sentiment from news
- ``social_signal_strength`` — mean absolute sentiment from social

Results are stored in the ``sector_sentiment`` table.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from database.db_manager import DatabaseManager
from utils.config import TICKER_TO_SECTOR
from utils.logger import get_logger

logger = get_logger(__name__)


class SectorAggregator:
    """Aggregates sentiment data at the sector level."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Core aggregation
    # ------------------------------------------------------------------
    def aggregate(self, lookback_hours: int = 24) -> int:
        """Compute and store sector-level sentiment aggregates.

        Returns the number of sector records written.
        """
        # Gather per-sector signal lists
        news_by_sector: dict[str, list[float]] = defaultdict(list)
        social_by_sector: dict[str, list[float]] = defaultdict(list)

        # --- News sentiment -------------------------------------------------
        news_rows = self.db.fetch_recent_news_sentiment(hours=lookback_hours)
        for row in news_rows:
            tickers = self._parse_tickers(row.get("related_tickers"))
            score = row.get("sentiment_score", 0.0)
            sectors = self._tickers_to_sectors(tickers)
            for sector in sectors:
                news_by_sector[sector].append(score)

        # --- Social sentiment ------------------------------------------------
        social_rows = self.db.fetch_recent_social_sentiment(
            hours=lookback_hours
        )
        for row in social_rows:
            tickers = self._parse_tickers(row.get("tickers_detected"))
            score = row.get("sentiment_score", 0.0)
            sectors = self._tickers_to_sectors(tickers)
            for sector in sectors:
                social_by_sector[sector].append(score)

        # --- Build aggregates ------------------------------------------------
        all_sectors = set(news_by_sector.keys()) | set(social_by_sector.keys())

        if not all_sectors:
            logger.info("No sector-level sentiment data to aggregate.")
            return 0

        now = datetime.utcnow().isoformat()
        records: list[dict[str, Any]] = []

        for sector in sorted(all_sectors):
            news_scores = news_by_sector.get(sector, [])
            social_scores = social_by_sector.get(sector, [])
            all_scores = news_scores + social_scores

            avg_sentiment = (
                round(sum(all_scores) / len(all_scores), 4)
                if all_scores
                else 0.0
            )
            news_strength = (
                round(
                    sum(abs(s) for s in news_scores) / len(news_scores), 4
                )
                if news_scores
                else 0.0
            )
            social_strength = (
                round(
                    sum(abs(s) for s in social_scores) / len(social_scores),
                    4,
                )
                if social_scores
                else 0.0
            )

            records.append(
                {
                    "sector": sector,
                    "timestamp": now,
                    "avg_sentiment_score": avg_sentiment,
                    "news_signal_strength": news_strength,
                    "social_signal_strength": social_strength,
                }
            )

        inserted = self.db.insert_sector_sentiment(records)
        logger.info(
            "Sector aggregation complete — %d sectors updated.", inserted
        )
        return inserted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_tickers(raw: Any) -> list[str]:
        """Parse a JSON string of tickers into a Python list."""
        if not raw:
            return []
        if isinstance(raw, list):
            return raw
        try:
            result = json.loads(raw)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def _tickers_to_sectors(tickers: list[str]) -> set[str]:
        """Map a list of tickers to their sectors."""
        sectors: set[str] = set()
        for ticker in tickers:
            sector = TICKER_TO_SECTOR.get(ticker)
            if sector:
                sectors.add(sector)
        return sectors
