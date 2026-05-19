"""
Strategy Parser — parses the raw LLM JSON output into normalised
strategy dicts ready for validation and database storage.

Follows the same tolerance patterns as
``research_agent.hypothesis_generator._parse_response``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

# Required keys in the LLM-produced strategy JSON
_REQUIRED_KEYS = {
    "strategy_name",
    "entry_conditions",
    "exit_conditions",
}


class StrategyParser:
    """Parses and normalises LLM strategy output."""

    def parse(
        self,
        raw_text: str,
        hypothesis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Parse LLM output into strategy dicts.

        Parameters
        ----------
        raw_text
            Raw string from the LLM (expected JSON object or array).
        hypothesis
            Source hypothesis dict (used to carry over IDs).

        Returns
        -------
        list[dict]
            Parsed and normalised strategy dicts, each with a generated
            ``strategy_id`` and ``timestamp_created``.
        """
        text = raw_text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse strategy JSON: %s", exc)
            logger.debug("Raw output:\n%s", raw_text[:2000])
            return []

        # Accept single object or array
        if isinstance(parsed, dict):
            parsed = [parsed]
        elif not isinstance(parsed, list):
            logger.warning("Unexpected LLM output type: %s", type(parsed))
            return []

        # Validate and normalise each strategy
        strategies: list[dict[str, Any]] = []
        now = datetime.utcnow()

        for i, item in enumerate(parsed):
            if not isinstance(item, dict):
                logger.warning("Strategy %d is not a dict — skipping.", i)
                continue

            missing = _REQUIRED_KEYS - item.keys()
            if missing:
                logger.warning(
                    "Strategy %d missing keys %s — skipping.", i, missing
                )
                continue

            # Normalise JSON sub-fields to strings
            strategy = self._normalise(item)

            # Attach metadata
            strategy["strategy_id"] = str(uuid.uuid4())
            strategy["hypothesis_id"] = hypothesis.get("hypothesis_id")
            strategy["timestamp_created"] = now

            # Carry over fields from hypothesis if not set by LLM
            if not strategy.get("asset_scope"):
                strategy["asset_scope"] = hypothesis.get("asset_scope")
            if not strategy.get("holding_period"):
                strategy["holding_period"] = hypothesis.get("holding_period")

            # Default status
            strategy["status"] = "draft"

            strategies.append(strategy)

        logger.info(
            "Parsed %d strategies from LLM output (hypothesis '%s').",
            len(strategies),
            (hypothesis.get("title") or "")[:50],
        )
        return strategies

    @staticmethod
    def _normalise(strategy: dict[str, Any]) -> dict[str, Any]:
        """Ensure all structured sub-fields are JSON strings."""
        json_fields = [
            "entry_conditions", "exit_conditions", "risk_rules",
            "position_sizing", "volatility_filter",
        ]
        for field in json_fields:
            val = strategy.get(field)
            if isinstance(val, (dict, list)):
                strategy[field] = json.dumps(val)
            elif val is None:
                strategy[field] = ""
        return strategy
