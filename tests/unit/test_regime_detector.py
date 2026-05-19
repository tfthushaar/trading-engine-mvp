"""Unit tests for market regime detector."""
import pytest
from ml.regime_detector import _rule_based_regime, REGIME_IMPLICATIONS


def test_bull_trending_regime():
    features = {"vix_level": 15, "spy_return_20d": 0.05, "above_200ma": True}
    regime, confidence, desc = _rule_based_regime(features)
    assert regime == "bull_trending"
    assert confidence > 0.5
    assert len(desc) > 0


def test_bear_trending_regime():
    features = {"vix_level": 20, "spy_return_20d": -0.06, "above_200ma": False}
    regime, confidence, desc = _rule_based_regime(features)
    assert regime == "bear_trending"


def test_high_volatility_regime():
    features = {"vix_level": 35, "spy_return_20d": -0.02, "above_200ma": True}
    regime, confidence, desc = _rule_based_regime(features)
    assert regime == "high_volatility"
    assert confidence >= 0.8


def test_all_regimes_have_implications():
    from ml.regime_detector import RegimeLabel
    regimes = ["bull_trending", "bull_choppy", "bear_trending",
               "bear_choppy", "high_volatility", "range_bound"]
    for regime in regimes:
        assert regime in REGIME_IMPLICATIONS
        assert len(REGIME_IMPLICATIONS[regime]) > 0


def test_disclaimer_in_result():
    from ml.regime_detector import RegimeResult
    from intelligence.base import MANDATORY_DISCLAIMER
    result = RegimeResult(
        regime="bull_trending",
        confidence=0.75,
        description="test",
        implications="test",
    )
    assert result.disclaimer == MANDATORY_DISCLAIMER
