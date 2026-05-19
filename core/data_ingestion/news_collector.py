"""
Financial news collector using the NewsAPI free tier.

Requires a ``NEWSAPI_KEY`` in the environment.  Searches for financial
keywords and deduplicates articles by a SHA-256 hash of the URL.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

import requests

from utils.config import NEWSAPI_KEY, NEWS_QUERIES
from utils.logger import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://newsapi.org/v2/everything"


class NewsCollector:
    """Collects financial news articles from NewsAPI."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or NEWSAPI_KEY
        if not self.api_key:
            logger.warning(
                "NEWSAPI_KEY not set — news collection will be skipped."
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _hash_url(url: str) -> str:
        """Deterministic article ID from URL."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_articles(
        self,
        query: str,
        from_date: str | None = None,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Search NewsAPI for *query* and return normalised article dicts.

        Parameters
        ----------
        query:
            Free-text search term, e.g. ``"stock market"``.
        from_date:
            ISO-8601 date string.  Defaults to 7 days ago.
        page_size:
            Max articles per request (NewsAPI free-tier cap is 100).
        """
        if not self.api_key:
            return []

        if from_date is None:
            from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

        params = {
            "q": query,
            "from": from_date,
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "language": "en",
            "apiKey": self.api_key,
        }

        try:
            resp = requests.get(_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            articles: list[dict[str, Any]] = []
            for art in data.get("articles", []):
                url = art.get("url", "")
                if not url:
                    continue
                articles.append(
                    {
                        "article_id": self._hash_url(url),
                        "title": art.get("title"),
                        "description": art.get("description"),
                        "source_name": (art.get("source") or {}).get("name"),
                        "url": url,
                        "published_at": art.get("publishedAt"),
                    }
                )
            logger.info(
                "Fetched %d articles for query '%s'.", len(articles), query
            )
            return articles

        except requests.RequestException as exc:
            logger.error("NewsAPI request failed for '%s': %s", query, exc)
            return []

    def collect_all(self) -> list[dict[str, Any]]:
        """Run all configured queries and return deduplicated articles."""
        seen_ids: set[str] = set()
        all_articles: list[dict[str, Any]] = []

        for query in NEWS_QUERIES:
            for article in self.fetch_articles(query):
                if article["article_id"] not in seen_ids:
                    seen_ids.add(article["article_id"])
                    all_articles.append(article)

        logger.info(
            "News collection complete — %d unique articles from %d queries.",
            len(all_articles),
            len(NEWS_QUERIES),
        )
        return all_articles
