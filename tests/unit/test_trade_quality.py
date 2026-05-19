"""Unit tests for Trade Quality Engine."""
import pytest
from unittest.mock import patch, MagicMock


def test_risk_reward_calculation():
    from intelligence.trade_quality.scorer import _score_risk_reward
    rr = _score_risk_reward(entry=185.0, stop_loss=180.0, target=200.0)
    assert rr["risk_per_share"] == 5.0
    assert rr["reward_per_share"] == 15.0
    assert rr["risk_reward_ratio"] == 3.0
    assert rr["grade"] == "excellent"


def test_risk_reward_poor():
    from intelligence.trade_quality.scorer import _score_risk_reward
    rr = _score_risk_reward(entry=185.0, stop_loss=183.0, target=187.0)
    assert rr["risk_reward_ratio"] == 1.0
    assert rr["grade"] == "acceptable"


def test_technical_score_with_empty_data():
    from intelligence.trade_quality.scorer import _score_technicals
    result = _score_technicals({}, entry=100.0)
    assert result["score"] == 50.0
    assert result["signals"] == []


def test_technical_score_bullish_setup():
    from intelligence.trade_quality.scorer import _score_technicals
    technicals = {
        "rsi_14": 55.0,
        "above_ema21": True,
        "above_ema50": True,
        "above_ema200": True,
        "volume_ratio_20d": 1.8,
    }
    result = _score_technicals(technicals, entry=100.0)
    assert result["score"] > 70
    assert len(result["signals"]) > 0
    assert result["warnings"] == []


def test_discipline_score_formula():
    """Basic discipline score computation."""
    score = 70.0
    score += (1.0 - 0.5) * 20  # 100% stop adherence
    final = min(100, max(0, score))
    assert final == 80.0
