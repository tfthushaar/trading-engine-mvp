"""
Strategy Discovery Engine — Phase 4.

Transforms research hypotheses into structured algorithmic trading
strategies with entry rules, exit rules, and risk management constraints.
"""

from strategy_engine.strategy_templates import StrategyTemplates
from strategy_engine.strategy_builder import StrategyBuilder
from strategy_engine.strategy_parser import StrategyParser
from strategy_engine.strategy_validator import StrategyValidator
from strategy_engine.strategy_ranker import StrategyRanker

__all__ = [
    "StrategyTemplates",
    "StrategyBuilder",
    "StrategyParser",
    "StrategyValidator",
    "StrategyRanker",
    "StrategyDiscoveryEngine",
]


class StrategyDiscoveryEngine:
    """Top-level orchestrator for the Strategy Discovery Engine.

    Pipeline:
    1. Fetch active hypotheses from research_hypotheses
    2. Match each hypothesis to a strategy template
    3. Build structured strategies via LLM
    4. Parse and normalise LLM output
    5. Validate strategies for logical consistency
    6. Rank strategies by robustness and clarity
    7. Persist validated strategies to trading_strategies
    """

    def __init__(self, db, api_key: str | None = None) -> None:
        from database.db_manager import DatabaseManager

        self.db: DatabaseManager = db
        self.templates = StrategyTemplates()
        self.builder = StrategyBuilder(api_key=api_key)
        self.parser = StrategyParser()
        self.validator = StrategyValidator()
        self.ranker = StrategyRanker()

    def run(self) -> dict:
        """Execute one strategy discovery cycle.

        Returns
        -------
        dict
            Summary with counts at each stage.
        """

        from datetime import datetime
        from utils.logger import get_logger
        from utils.config import MAX_STRATEGIES_PER_RUN

        logger = get_logger(__name__)
        start = datetime.utcnow()

        logger.info("=" * 60)
        logger.info(
            "Strategy discovery engine starting at %s", start.isoformat()
        )
        logger.info("=" * 60)

        # Ensure schema exists
        self.db.initialize()

        # 1 — Fetch active hypotheses not yet converted
        logger.info("[Strategy 1/6] Fetching active hypotheses …")
        hypotheses = self.db.fetch_active_hypotheses()
        if not hypotheses:
            logger.info("No unconverted hypotheses found. Nothing to do.")
            return {"hypotheses_found": 0, "strategies_created": 0}

        # 2 — Match templates and build strategies via LLM
        logger.info(
            "[Strategy 2/6] Building strategies for %d hypotheses …",
            len(hypotheses),
        )
        all_raw_strategies: list[dict] = []
        for h in hypotheses[:MAX_STRATEGIES_PER_RUN]:
            template_name = self.templates.match(h)
            template = self.templates.get_template(template_name)
            logger.debug(
                "Hypothesis '%s' matched template '%s'.",
                h.get("title", "")[:50], template_name,
            )
            raw_text = self.builder.build(h, template, template_name)
            if not raw_text:
                continue

            # 3 — Parse LLM output
            parsed = self.parser.parse(raw_text, h)
            all_raw_strategies.extend(parsed)

        logger.info(
            "[Strategy 3/6] Parsed %d raw strategies.", len(all_raw_strategies)
        )

        # 4 — Validate
        logger.info("[Strategy 4/6] Validating strategies …")
        validated = self.validator.validate(all_raw_strategies)

        # 5 — Rank
        logger.info(
            "[Strategy 5/6] Ranking %d validated strategies …",
            len(validated),
        )
        recent = self.db.fetch_recent_strategies(hours=48)
        ranked = self.ranker.rank(validated, recent)

        # 6 — Persist
        logger.info(
            "[Strategy 6/6] Persisting %d strategies …", len(ranked)
        )
        records = self._prepare_records(ranked)
        inserted = self.db.insert_trading_strategies(records)

        # Mark source hypotheses as 'tested'
        converted_ids = {
            r.get("hypothesis_id") for r in ranked if r.get("hypothesis_id")
        }
        for hid in converted_ids:
            self.db.update_hypothesis_status(hid, "tested")

        elapsed = (datetime.utcnow() - start).total_seconds()
        summary = {
            "hypotheses_found": len(hypotheses),
            "strategies_parsed": len(all_raw_strategies),
            "strategies_validated": len(validated),
            "strategies_ranked": len(ranked),
            "inserted": inserted,
            "elapsed_seconds": elapsed,
            "strategy_names": [s.get("strategy_name", "") for s in ranked],
        }

        logger.info("-" * 60)
        logger.info("Strategy discovery complete in %.1f s", elapsed)
        logger.info("  Hypotheses found:    %d", summary["hypotheses_found"])
        logger.info("  Strategies created:  %d", summary["inserted"])
        for name in summary["strategy_names"]:
            logger.info("    • %s", name)
        logger.info("=" * 60)

        return summary

    @staticmethod
    def _prepare_records(strategies: list[dict]) -> list[dict]:
        """Normalise strategy dicts for DB insertion."""
        import json

        records: list[dict] = []
        for s in strategies:
            # Ensure JSON fields are strings
            for field in (
                "entry_conditions", "exit_conditions", "risk_rules",
                "position_sizing", "volatility_filter",
            ):
                val = s.get(field, "")
                if isinstance(val, (dict, list)):
                    s[field] = json.dumps(val)

            records.append({
                "strategy_id": s["strategy_id"],
                "hypothesis_id": s.get("hypothesis_id"),
                "timestamp_created": s["timestamp_created"],
                "strategy_name": s["strategy_name"],
                "asset_scope": s.get("asset_scope"),
                "entry_conditions": s["entry_conditions"],
                "exit_conditions": s["exit_conditions"],
                "holding_period": s.get("holding_period"),
                "risk_rules": s.get("risk_rules"),
                "position_sizing": s.get("position_sizing"),
                "volatility_filter": s.get("volatility_filter"),
                "confidence_score": s.get("confidence_score"),
                "status": s.get("status", "validated"),
            })
        return records
