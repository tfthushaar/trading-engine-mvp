"""Options chain collector using Tradier API (primary) with yfinance fallback."""
import os
import requests
import pandas as pd
from datetime import datetime
from typing import Optional

from apps.api.config import get_settings

settings = get_settings()


class OptionsCollector:
    TRADIER_BASE = "https://api.tradier.com/v1"

    def __init__(self):
        self.api_key = settings.tradier_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def get_options_chain(self, ticker: str, expiration: Optional[str] = None) -> dict:
        """Fetch full options chain. Returns put/call data with Greeks."""
        if not self.api_key:
            return self._yfinance_fallback(ticker)

        params = {"symbol": ticker, "greeks": "true"}
        if expiration:
            params["expiration"] = expiration

        try:
            resp = requests.get(
                f"{self.TRADIER_BASE}/markets/options/chains",
                headers=self.headers,
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            options = data.get("options", {}).get("option", [])
            if not isinstance(options, list):
                options = [options]
            return self._normalize_chain(ticker, options)
        except Exception as exc:
            print(f"[OptionsCollector] Tradier error for {ticker}: {exc}")
            return self._yfinance_fallback(ticker)

    def get_expirations(self, ticker: str) -> list[str]:
        """List available expiration dates."""
        if not self.api_key:
            return []
        try:
            resp = requests.get(
                f"{self.TRADIER_BASE}/markets/options/expirations",
                headers=self.headers,
                params={"symbol": ticker},
                timeout=10,
            )
            resp.raise_for_status()
            dates = resp.json().get("expirations", {}).get("date", [])
            return dates if isinstance(dates, list) else [dates]
        except Exception:
            return []

    def get_unusual_activity(self, ticker: str) -> dict:
        """Compute put/call ratio and flag unusual volume."""
        chain = self.get_options_chain(ticker)
        calls = [o for o in chain.get("options", []) if o["option_type"] == "call"]
        puts = [o for o in chain.get("options", []) if o["option_type"] == "put"]

        call_vol = sum(o.get("volume", 0) or 0 for o in calls)
        put_vol = sum(o.get("volume", 0) or 0 for o in puts)
        pc_ratio = round(put_vol / call_vol, 3) if call_vol > 0 else None

        # Flag if largest single contract volume is anomalous
        all_contracts = calls + puts
        max_vol = max((o.get("volume", 0) or 0 for o in all_contracts), default=0)
        avg_vol = (call_vol + put_vol) / max(len(all_contracts), 1)
        unusual = max_vol > avg_vol * 5

        return {
            "ticker": ticker,
            "put_call_ratio": pc_ratio,
            "call_volume": call_vol,
            "put_volume": put_vol,
            "unusual_activity": unusual,
            "net_bias": "bullish" if pc_ratio and pc_ratio < 0.7 else "bearish" if pc_ratio and pc_ratio > 1.3 else "neutral",
            "collected_at": datetime.utcnow().isoformat(),
        }

    def _normalize_chain(self, ticker: str, options: list) -> dict:
        normalized = []
        for o in options:
            normalized.append({
                "ticker": ticker,
                "option_type": o.get("option_type"),
                "strike": o.get("strike"),
                "expiration": o.get("expiration_date"),
                "bid": o.get("bid"),
                "ask": o.get("ask"),
                "volume": o.get("volume"),
                "open_interest": o.get("open_interest"),
                "implied_volatility": o.get("greeks", {}).get("smv_vol") if o.get("greeks") else None,
                "delta": o.get("greeks", {}).get("delta") if o.get("greeks") else None,
                "gamma": o.get("greeks", {}).get("gamma") if o.get("greeks") else None,
                "theta": o.get("greeks", {}).get("theta") if o.get("greeks") else None,
            })
        return {"ticker": ticker, "options": normalized}

    def _yfinance_fallback(self, ticker: str) -> dict:
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            exps = t.options
            if not exps:
                return {"ticker": ticker, "options": []}
            chain = t.option_chain(exps[0])
            options = []
            for _, row in chain.calls.iterrows():
                options.append({"ticker": ticker, "option_type": "call",
                                 "strike": row.get("strike"), "expiration": exps[0],
                                 "volume": row.get("volume"), "open_interest": row.get("openInterest"),
                                 "implied_volatility": row.get("impliedVolatility")})
            for _, row in chain.puts.iterrows():
                options.append({"ticker": ticker, "option_type": "put",
                                 "strike": row.get("strike"), "expiration": exps[0],
                                 "volume": row.get("volume"), "open_interest": row.get("openInterest"),
                                 "implied_volatility": row.get("impliedVolatility")})
            return {"ticker": ticker, "options": options}
        except Exception:
            return {"ticker": ticker, "options": []}
