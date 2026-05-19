"""
Macroeconomic indicator collector using the FRED API (via fredapi).

Requires a ``FRED_API_KEY`` in the environment.  Pulls key macro time-series
such as the Federal Funds Rate, CPI, Unemployment, and GDP.
"""

from __future__ import annotations

from typing import Any

from fredapi import Fred

from utils.config import FRED_API_KEY, FRED_SERIES
from utils.logger import get_logger

logger = get_logger(__name__)


class MacroCollector:
    """Collects macroeconomic indicator data from FRED."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or FRED_API_KEY
        self._fred: Fred | None = None

        if not self.api_key:
            logger.warning(
                "FRED_API_KEY not set — macro collection will be skipped."
            )

    @property
    def fred(self) -> Fred:
        if self._fred is None:
            self._fred = Fred(api_key=self.api_key)
        return self._fred

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_series(
        self,
        series_id: str,
        observation_start: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch a single FRED series and return normalised dicts.

        Parameters
        ----------
        series_id:
            FRED series identifier, e.g. ``"DFF"``.
        observation_start:
            Optional start date (ISO-8601).  Defaults to all available data.
        """
        if not self.api_key:
            return []

        indicator_name = FRED_SERIES.get(series_id, series_id)

        try:
            kwargs: dict[str, Any] = {}
            if observation_start:
                kwargs["observation_start"] = observation_start

            data = self.fred.get_series(series_id, **kwargs)

            records: list[dict[str, Any]] = []
            for dt, value in data.items():
                if value is None or (hasattr(value, "__float__") and str(value) == "nan"):
                    continue
                records.append(
                    {
                        "series_id": series_id,
                        "indicator_name": indicator_name,
                        "date": dt.date().isoformat() if hasattr(dt, "date") else str(dt),
                        "value": float(value),
                    }
                )
            logger.info(
                "Fetched %d observations for %s (%s).",
                len(records), series_id, indicator_name,
            )
            return records

        except Exception as exc:
            logger.error("FRED fetch failed for %s: %s", series_id, exc)
            return []

    def collect_all(
        self, observation_start: str | None = "2020-01-01"
    ) -> list[dict[str, Any]]:
        """Fetch all configured FRED series and return combined records.

        Parameters
        ----------
        observation_start:
            Start date for observations.  Defaults to ``"2020-01-01"`` to keep
            the dataset manageable.
        """
        all_records: list[dict[str, Any]] = []
        for series_id in FRED_SERIES:
            records = self.fetch_series(series_id, observation_start=observation_start)
            all_records.extend(records)

        logger.info(
            "Macro collection complete — %d total observations across %d series.",
            len(all_records),
            len(FRED_SERIES),
        )
        return all_records
