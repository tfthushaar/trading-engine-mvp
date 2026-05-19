"""
Research Agent — top-level orchestrator for Phase 3.

Pipeline:
1. SignalSummarizer  → MarketSnapshot
2. HypothesisGenerator → candidate hypotheses (via OpenAI)
3. HypothesisRanker  → scored hypotheses
4. HypothesisFilter  → quality-gated hypotheses
5. DatabaseManager   → persist to research_hypotheses table

Exposes a single ``run()`` method suitable for scheduled execution.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from database.db_manager import DatabaseManager
from research_agent.signal_summarizer import SignalSummarizer
from research_agent.hypothesis_generator import HypothesisGenerator
from research_agent.hypothesis_ranker import HypothesisRanker
from research_agent.hypothesis_filter import HypothesisFilter
from utils.config import RESEARCH_LOOKBACK_HOURS, MAX_HYPOTHESES_PER_RUN
from utils.logger import get_logger

logger = get_logger(__name__)


class ResearchAgent:
    """End-to-end research hypothesis generation agent.

    Parameters
    ----------
    db : DatabaseManager, optional
        Shared database manager.  One is created if not provided.
    api_key : str, optional
        OpenAI API key (falls back to config / env).
    """

    def __init__(
        self,
        db: DatabaseManager | None = None,
        api_key: str | None = None,
    ) -> None:
        self.db = db or DatabaseManager()
        self.summarizer = SignalSummarizer(self.db)
        self.generator = HypothesisGenerator(api_key=api_key)
        self.ranker = HypothesisRanker()
        self.filter = HypothesisFilter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        lookback_hours: int | None = None,
        max_hypotheses: int | None = None,
    ) -> dict[str, Any]:
        """Execute one research cycle: summarise → generate → rank → filter → store.

        Returns
        -------
        dict
            Summary with counts at each stage and the list of accepted
            hypothesis titles.
        """
        hours = lookback_hours or RESEARCH_LOOKBACK_HOURS
        n = max_hypotheses or MAX_HYPOTHESES_PER_RUN
        start = datetime.utcnow()

        logger.info("=" * 60)
        logger.info(
            "Research agent starting (lookback=%dh, max=%d)", hours, n
        )
        logger.info("=" * 60)

        # Ensure schema exists
        self.db.initialize()

        # 1 — Summarise market signals
        logger.info("[Research 1/5] Summarising market signals …")
        snapshot = self.summarizer.summarize(lookback_hours=hours)

        # 2 — Generate candidate hypotheses via LLM
        logger.info("[Research 2/5] Generating hypotheses via LLM …")
        candidates = self.generator.generate(
            snapshot, max_hypotheses=n, lookback_hours=hours
        )

        # 3 — Fetch recent hypotheses for dedup
        recent = self.db.fetch_recent_hypotheses(hours=48)

        # 4 — Rank candidates
        logger.info("[Research 3/5] Ranking %d candidates …", len(candidates))
        ranked = self.ranker.rank(candidates, snapshot, recent)

        # 5 — Filter
        logger.info("[Research 4/5] Filtering hypotheses …")
        accepted = self.filter.filter(ranked, recent)

        # 6 — Prepare and persist
        logger.info("[Research 5/5] Persisting %d hypotheses …", len(accepted))
        records = self._prepare_records(accepted)
        inserted = self.db.insert_research_hypotheses(records)

        elapsed = (datetime.utcnow() - start).total_seconds()
        summary = {
            "candidates_generated": len(candidates),
            "candidates_after_ranking": len(ranked),
            "accepted": len(accepted),
            "inserted": inserted,
            "elapsed_seconds": elapsed,
            "titles": [h.get("title", "") for h in accepted],
        }

        logger.info("-" * 60)
        logger.info("Research cycle complete in %.1f s", elapsed)
        logger.info("  Generated:  %d", summary["candidates_generated"])
        logger.info("  Accepted:   %d", summary["accepted"])
        logger.info("  Inserted:   %d", summary["inserted"])
        for t in summary["titles"]:
            logger.info("    • %s", t)
        logger.info("=" * 60)

        return summary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_records(
        hypotheses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Normalise hypothesis dicts into the shape expected by
        ``DatabaseManager.insert_research_hypotheses``."""
        records: list[dict[str, Any]] = []
        for h in hypotheses:
            # Ensure trigger_conditions and supporting_signals are JSON strings
            trigger = h.get("trigger_conditions", "")
            if isinstance(trigger, (dict, list)):
                trigger = json.dumps(trigger)
            signals = h.get("supporting_signals", "")
            if isinstance(signals, (dict, list)):
                signals = json.dumps(signals)

            records.append({
                "hypothesis_id": h["hypothesis_id"],
                "timestamp": h["timestamp"],
                "title": h["title"],
                "hypothesis_text": h["hypothesis_text"],
                "asset_scope": h.get("asset_scope"),
                "sector": h.get("sector"),
                "trigger_conditions": trigger,
                "expected_direction": h.get("expected_direction"),
                "holding_period": h.get("holding_period"),
                "confidence_score": h.get("confidence_score"),
                "supporting_signals": signals,
                "status": h.get("status", "active"),
            })
        return records
