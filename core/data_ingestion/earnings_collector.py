"""Earnings calendar and surprise data collector using FMP API."""
import requests
from datetime import datetime, timedelta
from typing import Optional

from apps.api.config import get_settings

settings = get_settings()

FMP_BASE = "https://financialmodelingprep.com/api/v3"


class EarningsCollector:
    def __init__(self):
        self.api_key = settings.fmp_api_key

    def get_earnings_calendar(self, days_ahead: int = 7) -> list[dict]:
        """Upcoming earnings for the next N days."""
        today = datetime.utcnow().date()
        end = today + timedelta(days=days_ahead)
        url = f"{FMP_BASE}/earning_calendar"
        params = {"from": str(today), "to": str(end), "apikey": self.api_key}
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return [
                {
                    "ticker": e.get("symbol"),
                    "report_date": e.get("date"),
                    "eps_estimate": e.get("epsEstimated"),
                    "revenue_estimate": e.get("revenueEstimated"),
                    "time": e.get("time"),  # bmo | amc
                }
                for e in resp.json()
            ]
        except Exception as exc:
            print(f"[EarningsCollector] Error: {exc}")
            return []

    def get_earnings_surprise(self, ticker: str, limit: int = 8) -> list[dict]:
        """Historical EPS surprises for a ticker."""
        url = f"{FMP_BASE}/earnings-surprises/{ticker}"
        params = {"apikey": self.api_key}
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()[:limit]
            return [
                {
                    "ticker": ticker,
                    "date": e.get("date"),
                    "actual_eps": e.get("actualEarningResult"),
                    "estimated_eps": e.get("estimatedEarning"),
                    "surprise_pct": round(
                        (e.get("actualEarningResult", 0) - e.get("estimatedEarning", 0))
                        / abs(e.get("estimatedEarning", 1)) * 100, 2
                    ) if e.get("estimatedEarning") else None,
                }
                for e in data
            ]
        except Exception as exc:
            print(f"[EarningsCollector] Surprise error for {ticker}: {exc}")
            return []

    def collect(self):
        """Called by scheduler — stores upcoming earnings to DB."""
        events = self.get_earnings_calendar(days_ahead=7)
        print(f"[EarningsCollector] Collected {len(events)} upcoming earnings events")
        return events
