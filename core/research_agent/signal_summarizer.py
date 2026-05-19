"""
Signal Summariser — pulls recent data from DuckDB and distils it into a
structured ``MarketSnapshot`` dict for the research agent's LLM prompt.

Derived features computed:
- Per-ticker momentum (5-day and 20-day returns)
- Per-ticker realised volatility (rolling 5-day std of returns)
- Sentiment shift (current vs prior period average)
- Sector strength ranking
- Macro regime flags (rate direction, inflation trend)
"""

from __future__ import annotations

import json
from collections import defaultdict

from typing import Any

from database.db_manager import DatabaseManager
from utils.config import RESEARCH_LOOKBACK_HOURS
from utils.logger import get_logger

logger = get_logger(__name__)

# Type alias
MarketSnapshot = dict[str, Any]


class SignalSummarizer:
    """Reads the six input tables and produces a concise market snapshot."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def summarize(
        self, lookback_hours: int | None = None
    ) -> MarketSnapshot:
        """Return a structured snapshot of recent market signals.

        The snapshot has six top-level keys:
        ``price_summary``, ``macro_summary``, ``sentiment_summary``,
        ``social_summary``, ``sector_summary``, ``event_summary``.
        Each value is a plain string suitable for insertion into the
        LLM prompt.
        """
        hours = lookback_hours or RESEARCH_LOOKBACK_HOURS
        raw = self.db.fetch_signal_data(hours)

        snapshot: MarketSnapshot = {
            "price_summary": self._summarize_prices(raw["stock_prices"]),
            "macro_summary": self._summarize_macro(raw["macro_indicators"]),
            "sentiment_summary": self._summarize_news_sentiment(
                raw["news_sentiment"]
            ),
            "social_summary": self._summarize_social_sentiment(
                raw["social_sentiment_scores"]
            ),
            "sector_summary": self._summarize_sectors(
                raw["sector_sentiment"]
            ),
            "event_summary": self._summarize_events(raw["market_events"]),
            # Keep raw data for the ranker
            "_raw": raw,
        }
        logger.info("Market snapshot built (%d hours lookback).", hours)
        return snapshot

    # ------------------------------------------------------------------
    # Price action
    # ------------------------------------------------------------------
    def _summarize_prices(
        self, rows: list[dict[str, Any]]
    ) -> str:
        if not rows:
            return "No recent price data available."

        # Group by ticker
        by_ticker: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_ticker[r["ticker"]].append(r)

        lines: list[str] = []
        for ticker, prices in sorted(by_ticker.items()):
            prices.sort(key=lambda x: str(x["date"]))
            if len(prices) < 2:
                continue

            closes = [p["close"] for p in prices if p["close"] is not None]
            if len(closes) < 2:
                continue

            latest = closes[-1]
            # 5-day return
            ret_5d = (
                (latest / closes[-6] - 1) * 100
                if len(closes) >= 6
                else None
            )
            # 20-day return
            ret_20d = (
                (latest / closes[0] - 1) * 100
                if len(closes) >= 2
                else None
            )
            # Realised vol (5-day)
            if len(closes) >= 6:
                daily_rets = [
                    closes[i] / closes[i - 1] - 1
                    for i in range(max(len(closes) - 5, 1), len(closes))
                ]
                vol = (
                    (sum((r_ - sum(daily_rets) / len(daily_rets)) ** 2
                         for r_ in daily_rets) / len(daily_rets)) ** 0.5
                    * 100
                )
            else:
                vol = None

            parts = [f"{ticker}: last={latest:.2f}"]
            if ret_5d is not None:
                parts.append(f"5d_ret={ret_5d:+.2f}%")
            if ret_20d is not None:
                parts.append(f"20d_ret={ret_20d:+.2f}%")
            if vol is not None:
                parts.append(f"5d_vol={vol:.2f}%")
            lines.append(", ".join(parts))

        return "\n".join(lines) if lines else "No sufficient price data."

    # ------------------------------------------------------------------
    # Macro indicators
    # ------------------------------------------------------------------
    def _summarize_macro(
        self, rows: list[dict[str, Any]]
    ) -> str:
        if not rows:
            return "No recent macro data available."

        by_series: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_series[r["series_id"]].append(r)

        lines: list[str] = []
        for series_id, data in sorted(by_series.items()):
            data.sort(key=lambda x: str(x["date"]))
            name = data[0].get("indicator_name") or series_id
            values = [d["value"] for d in data if d["value"] is not None]
            if not values:
                continue
            latest = values[-1]
            direction = ""
            if len(values) >= 2:
                delta = latest - values[-2]
                direction = f" (Δ={delta:+.4f})"
            lines.append(f"{name} ({series_id}): {latest:.4f}{direction}")

        return "\n".join(lines) if lines else "No macro observations."

    # ------------------------------------------------------------------
    # News sentiment
    # ------------------------------------------------------------------
    def _summarize_news_sentiment(
        self, rows: list[dict[str, Any]]
    ) -> str:
        if not rows:
            return "No recent news sentiment data available."

        # Aggregate stats
        scores = [r["sentiment_score"] for r in rows
                  if r.get("sentiment_score") is not None]
        label_counts: dict[str, int] = defaultdict(int)
        for r in rows:
            label = r.get("sentiment_label", "unknown")
            label_counts[label] += 1

        avg = sum(scores) / len(scores) if scores else 0.0
        lines = [
            f"Total articles scored: {len(rows)}",
            f"Avg sentiment score: {avg:.3f}",
            f"Label distribution: {dict(label_counts)}",
        ]

        # Top 5 most extreme headlines
        sorted_rows = sorted(
            rows,
            key=lambda x: abs(x.get("sentiment_score", 0) or 0),
            reverse=True,
        )[:5]
        if sorted_rows:
            lines.append("Notable headlines:")
            for r in sorted_rows:
                headline = (r.get("headline") or "")[:100]
                score = r.get("sentiment_score", 0)
                label = r.get("sentiment_label", "?")
                tickers = r.get("related_tickers", "")
                lines.append(
                    f"  [{label} {score:+.2f}] {headline}"
                    + (f"  tickers={tickers}" if tickers else "")
                )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Social sentiment
    # ------------------------------------------------------------------
    def _summarize_social_sentiment(
        self, rows: list[dict[str, Any]]
    ) -> str:
        if not rows:
            return "No recent social sentiment data available."

        scores = [r["sentiment_score"] for r in rows
                  if r.get("sentiment_score") is not None]
        avg = sum(scores) / len(scores) if scores else 0.0
        total_engagement = sum(
            r.get("engagement_score", 0) or 0 for r in rows
        )

        label_counts: dict[str, int] = defaultdict(int)
        for r in rows:
            label_counts[r.get("sentiment_label", "unknown")] += 1

        lines = [
            f"Total social posts scored: {len(rows)}",
            f"Avg sentiment score: {avg:.3f}",
            f"Total engagement score: {total_engagement:.1f}",
            f"Label distribution: {dict(label_counts)}",
        ]

        # Top tickers mentioned
        ticker_counts: dict[str, int] = defaultdict(int)
        for r in rows:
            tickers_str = r.get("tickers_detected", "")
            if tickers_str:
                try:
                    tickers = json.loads(tickers_str)
                    for t in tickers:
                        ticker_counts[t] += 1
                except (json.JSONDecodeError, TypeError):
                    pass
        if ticker_counts:
            top = sorted(ticker_counts.items(), key=lambda x: x[1],
                         reverse=True)[:10]
            lines.append(
                f"Top mentioned tickers: "
                + ", ".join(f"{t}({c})" for t, c in top)
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Sector sentiment
    # ------------------------------------------------------------------
    def _summarize_sectors(
        self, rows: list[dict[str, Any]]
    ) -> str:
        if not rows:
            return "No recent sector sentiment data available."

        # Latest reading per sector
        latest: dict[str, dict] = {}
        for r in rows:
            sector = r.get("sector", "Unknown")
            if sector not in latest:
                latest[sector] = r

        lines: list[str] = []
        for sector, r in sorted(
            latest.items(),
            key=lambda x: x[1].get("avg_sentiment_score", 0) or 0,
            reverse=True,
        ):
            avg = r.get("avg_sentiment_score", 0) or 0
            news_str = r.get("news_signal_strength", 0) or 0
            social_str = r.get("social_signal_strength", 0) or 0
            lines.append(
                f"{sector}: avg_sent={avg:.3f}, "
                f"news_strength={news_str:.3f}, "
                f"social_strength={social_str:.3f}"
            )

        return "\n".join(lines) if lines else "No sector signals."

    # ------------------------------------------------------------------
    # Market events
    # ------------------------------------------------------------------
    def _summarize_events(
        self, rows: list[dict[str, Any]]
    ) -> str:
        if not rows:
            return "No recent market events detected."

        lines: list[str] = []
        for r in rows[:20]:  # cap at 20 events
            etype = r.get("event_type", "unknown")
            tickers = r.get("related_tickers", "")
            conf = r.get("confidence_score", 0)
            ts = r.get("timestamp", "")
            lines.append(
                f"[{etype}] tickers={tickers}, "
                f"confidence={conf:.2f}, time={ts}"
            )

        return "\n".join(lines)
