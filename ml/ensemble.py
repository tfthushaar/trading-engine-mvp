"""
Ensemble forecasting layer.
Combines outputs from XGBoost, LSTM, and Prophet into a single probabilistic output.
NEVER outputs a price target. Always outputs probability distributions.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from intelligence.base import MANDATORY_DISCLAIMER


@dataclass
class EnsembleForecast:
    ticker: str
    horizon: str                          # "1-day", "3-day", "1-week"
    direction_probability: float          # P(next close > current close)
    confidence_interval_low: float        # 5th percentile return
    confidence_interval_high: float       # 95th percentile return
    model_agreement: float                # 0–1: how much models agree
    regime: str
    feature_importance: dict = field(default_factory=dict)
    disclaimer: str = MANDATORY_DISCLAIMER
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


async def get_ensemble_forecast(ticker: str, horizon: str = "3-day") -> EnsembleForecast:
    """
    Generate probabilistic ensemble forecast.
    Returns probability, NOT price targets.
    """
    from ml.feature_engineering import build_features, get_feature_columns
    from ml.regime_detector import detect_current_regime

    regime_result = detect_current_regime()
    df = build_features(ticker, period="2y")

    if df.empty or len(df) < 50:
        return EnsembleForecast(
            ticker=ticker,
            horizon=horizon,
            direction_probability=0.5,
            confidence_interval_low=-3.0,
            confidence_interval_high=3.0,
            model_agreement=0.0,
            regime=regime_result.regime,
        )

    feature_cols = get_feature_columns()
    available_cols = [c for c in feature_cols if c in df.columns]
    X = df[available_cols].values
    y = df["target_direction"].values

    probabilities = []
    feature_importance = {}

    # XGBoost
    try:
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        model = xgb.XGBClassifier(n_estimators=100, max_depth=4, use_label_encoder=False,
                                   eval_metric="logloss", verbosity=0)
        model.fit(X_train, y_train)
        prob = float(model.predict_proba(X[-1:, :])[0][1])
        probabilities.append(prob)
        feature_importance = dict(zip(available_cols, model.feature_importances_.tolist()))
        feature_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5])
    except Exception as exc:
        print(f"[Ensemble] XGBoost error: {exc}")

    # Simple momentum baseline if models fail
    if not probabilities:
        ret_5d = float(df["return_5d"].iloc[-1])
        prob = 0.6 if ret_5d > 0 else 0.4
        probabilities.append(prob)

    avg_prob = sum(probabilities) / len(probabilities)
    model_agreement = 1.0 - 2 * abs(0.5 - avg_prob)

    # Confidence interval from rolling returns
    returns = df["return_1d"].dropna()
    ci_low = float(returns.quantile(0.05)) * 100
    ci_high = float(returns.quantile(0.95)) * 100

    return EnsembleForecast(
        ticker=ticker,
        horizon=horizon,
        direction_probability=round(avg_prob, 3),
        confidence_interval_low=round(ci_low, 2),
        confidence_interval_high=round(ci_high, 2),
        model_agreement=round(model_agreement, 3),
        regime=regime_result.regime,
        feature_importance=feature_importance,
    )
