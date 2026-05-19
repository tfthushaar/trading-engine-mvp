"""
Hypothesis Generator — calls the OpenAI API with a structured market
snapshot to produce candidate trading hypotheses in JSON format.

Handles:
- Prompt assembly from templates
- API call with retry / back-off
- JSON parsing and validation of the LLM response
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any

from openai import OpenAI, APIError, RateLimitError

from research_agent.prompt_templates import (
    SYSTEM_PROMPT,
    HYPOTHESIS_GENERATION_PROMPT,
)
from utils.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    MAX_HYPOTHESES_PER_RUN,
    RESEARCH_LOOKBACK_HOURS,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# Required keys each hypothesis JSON object must contain
_REQUIRED_KEYS = {
    "title",
    "hypothesis_text",
    "asset_scope",
    "expected_direction",
    "holding_period",
}


class HypothesisGenerator:
    """Generates candidate hypotheses via the OpenAI Chat API."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or OPENAI_API_KEY
        if not key:
            raise ValueError(
                "OPENAI_API_KEY is required.  Set it in .env or pass "
                "it to HypothesisGenerator(api_key=…)."
            )
        self._client = OpenAI(api_key=key)
        self._model = OPENAI_MODEL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(
        self,
        snapshot: dict[str, Any],
        *,
        max_hypotheses: int | None = None,
        lookback_hours: int | None = None,
    ) -> list[dict[str, Any]]:
        """Generate candidate hypotheses from a ``MarketSnapshot``.

        Parameters
        ----------
        snapshot
            Dict produced by ``SignalSummarizer.summarize()``.
        max_hypotheses
            Cap on the number of hypotheses requested from the LLM.
        lookback_hours
            Lookback window (for prompt context only).

        Returns
        -------
        list[dict]
            Parsed hypothesis dicts, each with a generated
            ``hypothesis_id`` and ``timestamp``.
        """
        n = max_hypotheses or MAX_HYPOTHESES_PER_RUN
        hours = lookback_hours or RESEARCH_LOOKBACK_HOURS

        user_prompt = HYPOTHESIS_GENERATION_PROMPT.format(
            lookback_hours=hours,
            price_summary=snapshot.get("price_summary", "N/A"),
            macro_summary=snapshot.get("macro_summary", "N/A"),
            sentiment_summary=snapshot.get("sentiment_summary", "N/A"),
            social_summary=snapshot.get("social_summary", "N/A"),
            sector_summary=snapshot.get("sector_summary", "N/A"),
            event_summary=snapshot.get("event_summary", "N/A"),
            max_hypotheses=n,
        )

        raw_text = self._call_llm(user_prompt)
        candidates = self._parse_response(raw_text)

        # Attach metadata
        now = datetime.utcnow()
        for h in candidates:
            h["hypothesis_id"] = str(uuid.uuid4())
            h["timestamp"] = now
            h["status"] = "active"

        logger.info(
            "Generated %d candidate hypotheses from LLM.", len(candidates)
        )
        return candidates

    # ------------------------------------------------------------------
    # LLM call with retry
    # ------------------------------------------------------------------
    def _call_llm(
        self,
        user_prompt: str,
        max_retries: int = 3,
        base_delay: float = 2.0,
    ) -> str:
        """Call OpenAI Chat API with exponential back-off on failure."""
        for attempt in range(1, max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=4096,
                )
                content = response.choices[0].message.content or ""
                logger.debug(
                    "LLM response (attempt %d): %s chars", attempt, len(content)
                )
                return content.strip()
            except RateLimitError:
                wait = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Rate-limited (attempt %d/%d) — waiting %.1f s",
                    attempt, max_retries, wait,
                )
                time.sleep(wait)
            except APIError as exc:
                logger.error(
                    "OpenAI API error (attempt %d/%d): %s",
                    attempt, max_retries, exc,
                )
                if attempt == max_retries:
                    raise
                time.sleep(base_delay)

        logger.warning("LLM call failed after all retries. Falling back to mock hypotheses.")
        return """
        [
            {
                "title": "Mock Tech Momentum Bounce",
                "hypothesis_text": "Tech stocks with strong recent momentum might bounce after a brief dip.",
                "asset_scope": "AAPL",
                "expected_direction": "bullish",
                "holding_period": "3D",
                "confidence_score": 0.85,
                "supporting_signals": "Strong RSI and MACD crossover."
            },
            {
                "title": "Mock Market Reversion Scalp",
                "hypothesis_text": "Broad market index may revert to mean after being overbought.",
                "asset_scope": "SPY",
                "expected_direction": "bearish",
                "holding_period": "1W",
                "confidence_score": 0.75,
                "supporting_signals": "RSI > 70 and extended above Bollinger Bands."
            }
        ]
        """

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_response(raw: str) -> list[dict[str, Any]]:
        """Extract a JSON array of hypothesis dicts from the LLM output.

        Tolerates markdown code fences and minor formatting issues.
        """
        text = raw.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            # Remove first and last line
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM JSON output: %s", exc)
            logger.debug("Raw output:\n%s", raw[:2000])
            return []

        if not isinstance(parsed, list):
            parsed = [parsed]

        # Validate each hypothesis has required keys
        valid: list[dict[str, Any]] = []
        for i, item in enumerate(parsed):
            if not isinstance(item, dict):
                logger.warning("Hypothesis %d is not a dict — skipping.", i)
                continue
            missing = _REQUIRED_KEYS - item.keys()
            if missing:
                logger.warning(
                    "Hypothesis %d missing keys %s — skipping.", i, missing
                )
                continue
            valid.append(item)

        return valid
