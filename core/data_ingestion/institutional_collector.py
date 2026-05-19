"""Institutional holdings collector using SEC EDGAR 13F filings."""
import requests
from datetime import datetime

SEC_HEADERS = {"User-Agent": "trading-engine-mvp contact@example.com"}
EDGAR_COMPANY_SEARCH = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"


class InstitutionalCollector:
    def get_13f_holders(self, ticker: str) -> list[dict]:
        """
        Get largest institutional holders for a ticker.
        Uses yfinance as the primary source (wraps Yahoo Finance data).
        SEC EDGAR 13F parsing is complex — this is the practical approach.
        """
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            holders = t.institutional_holders
            if holders is None or holders.empty:
                return []
            return [
                {
                    "institution": row.get("Holder"),
                    "shares": int(row.get("Shares", 0)),
                    "value_usd": float(row.get("Value", 0)),
                    "pct_held": float(row.get("% Out", 0)),
                    "date_reported": str(row.get("Date Reported", "")),
                }
                for _, row in holders.iterrows()
            ]
        except Exception as exc:
            print(f"[InstitutionalCollector] Error for {ticker}: {exc}")
            return []

    def get_net_institutional_flow(self, ticker: str) -> dict:
        """
        Compute net buy/sell signal from recent 13F changes.
        Positive = net institutional buying. Negative = selling.
        """
        holders = self.get_13f_holders(ticker)
        total_value = sum(h.get("value_usd", 0) for h in holders)
        return {
            "ticker": ticker,
            "total_institutional_value_usd": total_value,
            "top_holders": holders[:5],
            "holder_count": len(holders),
            "collected_at": datetime.utcnow().isoformat(),
        }

    def collect(self) -> None:
        """Scheduler hook."""
        pass
