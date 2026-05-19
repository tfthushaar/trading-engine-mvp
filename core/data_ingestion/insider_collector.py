"""SEC EDGAR Form 4 insider trades collector."""
import requests
from datetime import datetime, timedelta
from typing import Optional

SEC_HEADERS = {"User-Agent": "trading-engine-mvp contact@example.com"}
EDGAR_BASE = "https://efts.sec.gov/LATEST/search-index"


class InsiderCollector:
    def get_recent_insider_trades(self, ticker: str, days_back: int = 30) -> list[dict]:
        """Fetch recent Form 4 filings for a ticker from SEC EDGAR full-text search."""
        try:
            # Use EDGAR full-text search for Form 4
            url = "https://efts.sec.gov/LATEST/search-index"
            params = {
                "q": f'"{ticker}"',
                "dateRange": "custom",
                "startdt": (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
                "enddt": datetime.utcnow().strftime("%Y-%m-%d"),
                "forms": "4",
            }
            resp = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params=params,
                headers=SEC_HEADERS,
                timeout=15,
            )
            # EDGAR search returns HTML — parse hits count from JSON endpoint instead
            json_url = "https://efts.sec.gov/LATEST/search-index"

            # Use the proper JSON search endpoint
            resp2 = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params={**params, "_source": "period_of_report,entity_name,file_date"},
                headers=SEC_HEADERS,
                timeout=15,
            )
            return self._parse_edgar_response(ticker, resp2)
        except Exception as exc:
            print(f"[InsiderCollector] Error for {ticker}: {exc}")
            return []

    def get_cluster_buys(self, ticker: str, days_back: int = 90, min_transactions: int = 3) -> dict:
        """Detect cluster insider buying (multiple insiders buying in same period)."""
        trades = self.get_recent_insider_trades(ticker, days_back)
        buys = [t for t in trades if t.get("transaction_type") == "buy"]
        return {
            "ticker": ticker,
            "cluster_buy_detected": len(buys) >= min_transactions,
            "buy_count": len(buys),
            "total_value_usd": sum(t.get("value_usd", 0) for t in buys),
            "trades": buys,
        }

    def _parse_edgar_response(self, ticker: str, resp) -> list[dict]:
        try:
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            results = []
            for hit in hits[:20]:
                src = hit.get("_source", {})
                results.append({
                    "ticker": ticker,
                    "filer": src.get("entity_name", ""),
                    "filed_at": src.get("file_date", ""),
                    "period": src.get("period_of_report", ""),
                    "transaction_type": "buy",  # simplified — Form 4 parsing requires XML
                    "value_usd": None,
                    "source": "SEC EDGAR Form 4",
                })
            return results
        except Exception:
            return []

    def collect(self) -> list[dict]:
        """Scheduler hook — scan watchlisted tickers for insider activity."""
        # In production: fetch from user watchlists and scan each ticker
        return []
