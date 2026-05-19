"""
Social sentiment collector using the Reddit API (via PRAW).

Monitors finance-related subreddits for recent posts.  This module is
**optional** — if Reddit credentials are not configured, collection is
silently skipped.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import praw

from utils.config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_SUBREDDITS,
    REDDIT_USER_AGENT,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class SocialCollector:
    """Collects posts from finance-related subreddits."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.client_id = client_id or REDDIT_CLIENT_ID
        self.client_secret = client_secret or REDDIT_CLIENT_SECRET
        self.user_agent = user_agent or REDDIT_USER_AGENT

        self._reddit: praw.Reddit | None = None
        self._available = bool(self.client_id and self.client_secret)

        if not self._available:
            logger.warning(
                "Reddit credentials not set — social-sentiment collection "
                "will be skipped."
            )

    @property
    def reddit(self) -> praw.Reddit:
        if self._reddit is None:
            self._reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
        return self._reddit

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_posts(
        self, subreddit_name: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch the latest *limit* hot posts from *subreddit_name*.

        Returns
        -------
        list[dict]
            Each dict: post_id, subreddit, title, selftext, score,
            num_comments, created_utc.
        """
        if not self._available:
            return []

        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts: list[dict[str, Any]] = []

            for submission in subreddit.hot(limit=limit):
                posts.append(
                    {
                        "post_id": submission.id,
                        "subreddit": subreddit_name,
                        "title": submission.title,
                        "selftext": (submission.selftext or "")[:5000],  # cap length
                        "score": submission.score,
                        "num_comments": submission.num_comments,
                        "created_utc": datetime.utcfromtimestamp(
                            submission.created_utc
                        ).isoformat(),
                    }
                )
            logger.info(
                "Fetched %d posts from r/%s.", len(posts), subreddit_name
            )
            return posts

        except Exception as exc:
            logger.error(
                "Reddit fetch failed for r/%s: %s", subreddit_name, exc
            )
            return []

    def collect_all(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch posts from all configured subreddits."""
        all_posts: list[dict[str, Any]] = []
        for sub in REDDIT_SUBREDDITS:
            posts = self.fetch_posts(sub, limit=limit)
            all_posts.extend(posts)

        logger.info(
            "Social collection complete — %d total posts from %d subreddits.",
            len(all_posts),
            len(REDDIT_SUBREDDITS),
        )
        return all_posts
