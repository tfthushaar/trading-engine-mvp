"""
Stock-market data collector using Yahoo Finance (yfinance).

No API key required.  Fetches historical and latest-day OHLCV data for a
configurable list of tickers and indices.
"""

from __future__ import annotations


from typing import Any

import yfinance as yf

from utils.config import DEFAULT_TICKERS
from utils.logger import get_logger

logger = get_logger(__name__)


class StockCollector:
    """Collects OHLCV price data from Yahoo Finance."""

    def __init__(self, tickers: list[str] | None = None) -> None:
        self.tickers = tickers or DEFAULT_TICKERS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_historical(
        self, ticker: str, period: str = "1y"
    ) -> list[dict[str, Any]]:
        """Download *period* of daily OHLCV for a single *ticker*.

        Parameters
        ----------
        ticker:
            Yahoo Finance symbol, e.g. ``"AAPL"`` or ``"^GSPC"``.
        period:
            Look-back window accepted by ``yfinance`` (``"1d"``, ``"5d"``,
            ``"1mo"``, ``"3mo"``, ``"6mo"``, ``"1y"``, ``"2y"``, ``"5y"``,
            ``"10y"``, ``"ytd"``, ``"max"``).

        Returns
        -------
        list[dict]
            Each dict has keys: ticker, date, open, high, low, close, volume.
        """
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)

            if df.empty:
                logger.warning("No data returned for %s (period=%s).", ticker, period)
                return []

            records: list[dict[str, Any]] = []
            for idx, row in df.iterrows():
                records.append(
                    {
                        "ticker": ticker,
                        "date": idx.date().isoformat(),
                        "open": round(row["Open"], 4),
                        "high": round(row["High"], 4),
                        "low": round(row["Low"], 4),
                        "close": round(row["Close"], 4),
                        "volume": int(row["Volume"]),
                    }
                )
            logger.info(
                "Fetched %d records for %s (period=%s).", len(records), ticker, period
            )
            return records

        except Exception as exc:
            logger.error("Failed to fetch data for %s: %s", ticker, exc)
            return []

    def fetch_latest(self, ticker: str) -> list[dict[str, Any]]:
        """Fetch only the most recent trading day's data."""
        return self.fetch_historical(ticker, period="1d")

    def collect_all(self, period: str = "1y") -> list[dict[str, Any]]:
        """Iterate over all configured tickers and return combined records."""
        all_records: list[dict[str, Any]] = []
        for ticker in self.tickers:
            records = self.fetch_historical(ticker, period=period)
            all_records.extend(records)
        logger.info(
            "Stock collection complete — %d total records across %d tickers.",
            len(all_records),
            len(self.tickers),
        )
        return all_records
