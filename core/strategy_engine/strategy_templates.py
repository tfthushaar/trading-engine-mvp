"""
Strategy Templates — defines five canonical strategy archetypes and a
heuristic matcher that selects the best template for a given hypothesis.

Templates
---------
1. Momentum         — enter on price momentum + sentiment confirmation
2. Mean Reversion   — enter on oversold/overbought + divergence
3. Event-Driven     — enter around detected market events
4. Macro Regime     — enter on macro indicator shifts
5. Sentiment Divergence — enter when sentiment diverges from price
"""

from __future__ import annotations


import re
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

# ======================================================================
# Template definitions
# ======================================================================

TEMPLATES: dict[str, dict[str, Any]] = {
    "momentum": {
        "description": "Enter on sustained price momentum confirmed by sentiment signals.",
        "default_entry_conditions": [
            {
                "type": "price_momentum",
                "rule": "Asset shows >= 2% directional move over lookback window",
                "parameter": "lookback_days: 5",
            },
            {
                "type": "sentiment_confirmation",
                "rule": "News sentiment score aligns with price direction (> 0.3 or < -0.3)",
                "parameter": "threshold: 0.3",
            },
        ],
        "default_exit_conditions": [
            {
                "type": "sentiment_reversal",
                "rule": "Sentiment flips sign for 2+ consecutive periods",
            },
            {
                "type": "time_stop",
                "rule": "Close position after holding period expires",
            },
            {
                "type": "stop_loss",
                "rule": "Close if price moves against entry by stop_loss_pct",
                "parameter": "stop_loss_pct: 3.0",
            },
        ],
        "default_risk_rules": {
            "stop_loss_pct": 3.0,
            "max_portfolio_exposure_pct": 10.0,
            "max_single_position_pct": 5.0,
        },
        "default_position_sizing": {
            "method": "volatility_adjusted",
            "target_volatility_pct": 15.0,
            "max_position_pct": 5.0,
        },
        "default_volatility_filter": {
            "rule": "Skip if 20-day realized vol > 60% annualized",
            "max_vol_annualized": 60.0,
        },
    },
    "mean_reversion": {
        "description": "Enter on oversold/overbought signals with expectation of reversion.",
        "default_entry_conditions": [
            {
                "type": "price_deviation",
                "rule": "Price deviates >= 2 standard deviations from 20-day moving average",
                "parameter": "z_score_threshold: 2.0",
            },
            {
                "type": "sentiment_divergence",
                "rule": "Sentiment direction opposes recent price move (contrarian signal)",
            },
        ],
        "default_exit_conditions": [
            {
                "type": "mean_reversion_target",
                "rule": "Close when price returns within 0.5 std dev of moving average",
            },
            {
                "type": "time_stop",
                "rule": "Close position after holding period expires",
            },
            {
                "type": "stop_loss",
                "rule": "Close if price extends further against position",
                "parameter": "stop_loss_pct: 4.0",
            },
        ],
        "default_risk_rules": {
            "stop_loss_pct": 4.0,
            "max_portfolio_exposure_pct": 8.0,
            "max_single_position_pct": 4.0,
        },
        "default_position_sizing": {
            "method": "equal_weight",
            "max_position_pct": 4.0,
        },
        "default_volatility_filter": {
            "rule": "Prefer elevated vol environments (20-day vol > 15% annualized)",
            "min_vol_annualized": 15.0,
        },
    },
    "event_driven": {
        "description": "Enter around detected market events with time-bounded risk.",
        "default_entry_conditions": [
            {
                "type": "event_trigger",
                "rule": "Market event detected (earnings, M&A, policy, rate decision)",
                "parameter": "min_event_confidence: 0.6",
            },
            {
                "type": "sentiment_spike",
                "rule": "Sentiment magnitude > 0.5 within 24h of event",
            },
        ],
        "default_exit_conditions": [
            {
                "type": "time_decay",
                "rule": "Close position within fixed window post-event",
                "parameter": "max_days_post_event: 5",
            },
            {
                "type": "stop_loss",
                "rule": "Close if price moves against entry by stop_loss_pct",
                "parameter": "stop_loss_pct: 5.0",
            },
        ],
        "default_risk_rules": {
            "stop_loss_pct": 5.0,
            "max_portfolio_exposure_pct": 6.0,
            "max_single_position_pct": 3.0,
        },
        "default_position_sizing": {
            "method": "fixed_fractional",
            "risk_per_trade_pct": 1.0,
        },
        "default_volatility_filter": {
            "rule": "Accept higher vol around events (no upper limit)",
            "max_vol_annualized": 100.0,
        },
    },
    "macro_regime": {
        "description": "Enter on macro indicator regime shifts (rate changes, CPI, GDP).",
        "default_entry_conditions": [
            {
                "type": "macro_shift",
                "rule": "Key macro indicator shows significant change vs prior period",
                "parameter": "indicators: [DFF, CPIAUCSL, UNRATE, GDP]",
            },
            {
                "type": "cross_asset_confirmation",
                "rule": "Bond/equity/commodity signals align with macro thesis",
            },
        ],
        "default_exit_conditions": [
            {
                "type": "macro_regime_change",
                "rule": "Close when macro indicator reverses or new data contradicts thesis",
            },
            {
                "type": "time_stop",
                "rule": "Close position after holding period expires",
            },
            {
                "type": "stop_loss",
                "rule": "Close if position drawdown exceeds threshold",
                "parameter": "stop_loss_pct: 5.0",
            },
        ],
        "default_risk_rules": {
            "stop_loss_pct": 5.0,
            "max_portfolio_exposure_pct": 15.0,
            "max_single_position_pct": 7.0,
        },
        "default_position_sizing": {
            "method": "conviction_weighted",
            "base_position_pct": 5.0,
            "conviction_multiplier_range": [0.5, 1.5],
        },
        "default_volatility_filter": {
            "rule": "Flag extreme vol regimes but do not auto-skip",
            "alert_vol_annualized": 50.0,
        },
    },
    "sentiment_divergence": {
        "description": "Enter when news/social sentiment diverges from price action.",
        "default_entry_conditions": [
            {
                "type": "sentiment_price_divergence",
                "rule": "Aggregate sentiment direction opposes 5-day price trend",
            },
            {
                "type": "engagement_confirmation",
                "rule": "Social engagement score above median for the asset",
            },
        ],
        "default_exit_conditions": [
            {
                "type": "convergence",
                "rule": "Close when sentiment and price realign",
            },
            {
                "type": "time_stop",
                "rule": "Close position after holding period expires",
            },
            {
                "type": "stop_loss",
                "rule": "Close if drawdown exceeds threshold",
                "parameter": "stop_loss_pct: 3.5",
            },
        ],
        "default_risk_rules": {
            "stop_loss_pct": 3.5,
            "max_portfolio_exposure_pct": 8.0,
            "max_single_position_pct": 4.0,
        },
        "default_position_sizing": {
            "method": "signal_strength_weighted",
            "base_position_pct": 3.0,
        },
        "default_volatility_filter": {
            "rule": "Skip if 20-day realized vol < 8% annualized (too quiet)",
            "min_vol_annualized": 8.0,
        },
    },
}


# ======================================================================
# Keyword patterns for template matching
# ======================================================================
_MOMENTUM_KEYWORDS = re.compile(
    r"\b(momentum|trend|breakout|rally|surge|run-up|uptrend|downtrend"
    r"|continuation|follow.?through)\b",
    re.IGNORECASE,
)
_MEAN_REVERSION_KEYWORDS = re.compile(
    r"\b(mean.?reversion|revert|oversold|overbought|contrarian|pullback"
    r"|correction|bounce|snap.?back|deviation)\b",
    re.IGNORECASE,
)
_EVENT_KEYWORDS = re.compile(
    r"\b(earnings|merger|acquisition|M&A|takeover|IPO|FDA|FOMC"
    r"|rate.?decision|policy.?change|event|announcement)\b",
    re.IGNORECASE,
)
_MACRO_KEYWORDS = re.compile(
    r"\b(macro|CPI|inflation|GDP|unemployment|interest.?rate|fed"
    r"|monetary|fiscal|yield.?curve|regime)\b",
    re.IGNORECASE,
)
_SENTIMENT_KEYWORDS = re.compile(
    r"\b(sentiment|divergence|social.?media|Reddit|news.?flow"
    r"|bullish.?sentiment|bearish.?sentiment|fear|greed)\b",
    re.IGNORECASE,
)


class StrategyTemplates:
    """Provides template matching and retrieval for hypothesis-to-strategy
    conversion."""

    def match(self, hypothesis: dict[str, Any]) -> str:
        """Select the best strategy template for a hypothesis.

        Uses keyword matching on hypothesis_text, trigger_conditions,
        and expected_direction.

        Returns
        -------
        str
            Template name (one of the TEMPLATES keys).
        """
        text = " ".join([
            hypothesis.get("hypothesis_text", ""),
            str(hypothesis.get("trigger_conditions", "")),
            hypothesis.get("expected_direction", ""),
            hypothesis.get("title", ""),
        ])

        scores: dict[str, int] = {
            "momentum": len(_MOMENTUM_KEYWORDS.findall(text)),
            "mean_reversion": len(_MEAN_REVERSION_KEYWORDS.findall(text)),
            "event_driven": len(_EVENT_KEYWORDS.findall(text)),
            "macro_regime": len(_MACRO_KEYWORDS.findall(text)),
            "sentiment_divergence": len(_SENTIMENT_KEYWORDS.findall(text)),
        }

        # Boost by expected_direction
        direction = (hypothesis.get("expected_direction") or "").lower()
        if direction == "mean reversion":
            scores["mean_reversion"] += 3
        elif direction in ("bullish", "bearish"):
            scores["momentum"] += 1

        best = max(scores, key=scores.get)      # type: ignore[arg-type]
        if scores[best] == 0:
            # Default to momentum if nothing matched
            best = "momentum"

        logger.debug(
            "Template match scores: %s → selected '%s'",
            scores, best,
        )
        return best

    @staticmethod
    def get_template(name: str) -> dict[str, Any]:
        """Return the template definition for ``name``."""
        return TEMPLATES.get(name, TEMPLATES["momentum"])

    @staticmethod
    def list_templates() -> list[str]:
        """Return all available template names."""
        return list(TEMPLATES.keys())
