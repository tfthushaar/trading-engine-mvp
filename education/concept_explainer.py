"""
Contextual AI concept explainer.
Adapts explanation depth to user level. Triggered by UI interactions.
"""
import json
from typing import Optional
import anthropic
import yfinance as yf

from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()

CONCEPT_LIBRARY = {
    "rsi": {
        "full_name": "Relative Strength Index",
        "category": "momentum",
        "common_mistakes": ["treating RSI 70 as an automatic sell signal", "using RSI alone without trend context"],
        "works_best": "trending markets with clear momentum",
        "fails": "strong trending markets where RSI stays overbought/oversold for extended periods",
    },
    "macd": {
        "full_name": "Moving Average Convergence Divergence",
        "category": "momentum",
        "common_mistakes": ["chasing MACD crossovers in choppy markets", "not considering the histogram direction"],
        "works_best": "trending markets with clear directional momentum",
        "fails": "sideways, range-bound markets — generates many false signals",
    },
    "moving_average": {
        "full_name": "Moving Average (EMA/SMA)",
        "category": "trend",
        "common_mistakes": ["using a single MA without context", "ignoring that MA is lagging"],
        "works_best": "trending markets to identify direction and dynamic support/resistance",
        "fails": "choppy, sideways markets — price whipsaws through MA repeatedly",
    },
    "support_resistance": {
        "full_name": "Support and Resistance Levels",
        "category": "price_action",
        "common_mistakes": ["treating levels as exact prices rather than zones", "ignoring volume at levels"],
        "works_best": "all market conditions — fundamental price action concept",
        "fails": "during high-volatility events (earnings, Fed announcements) where levels are ignored",
    },
    "volume": {
        "full_name": "Trading Volume",
        "category": "confirmation",
        "common_mistakes": ["ignoring volume entirely", "not comparing to average volume"],
        "works_best": "confirming breakouts and trend strength",
        "fails": "cannot predict direction alone — only confirms or questions moves",
    },
    "risk_reward": {
        "full_name": "Risk/Reward Ratio",
        "category": "risk_management",
        "common_mistakes": ["ignoring R:R and only focusing on win rate", "calculating R:R after entry"],
        "works_best": "pre-trade planning — determines if a setup is worth taking",
        "fails": "nothing — this is always relevant and should be calculated before every trade",
    },
    "bollinger_bands": {
        "full_name": "Bollinger Bands",
        "category": "volatility",
        "common_mistakes": ["assuming price always returns to the middle band", "trading every band touch"],
        "works_best": "identifying volatility squeezes and potential breakouts",
        "fails": "strong trending markets where price rides the upper/lower band",
    },
}


async def explain(concept: str, user_id: str, context_ticker: Optional[str] = None) -> dict:
    """Generate contextual explanation for a trading concept."""
    # Get user level
    level = "intermediate"
    try:
        from apps.api.database import AsyncSessionLocal
        from database.models.users import UserLearningProfile
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserLearningProfile).where(UserLearningProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                level = profile.level
    except Exception:
        pass

    # Get concept library metadata
    concept_key = concept.lower().replace(" ", "_").replace("-", "_")
    meta = CONCEPT_LIBRARY.get(concept_key, {})

    # Build context from live ticker data if available
    ticker_context = ""
    if context_ticker:
        try:
            t = yf.Ticker(context_ticker)
            hist = t.history(period="3mo", interval="1d")
            close = hist["Close"]
            # RSI calculation for context
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rsi = (100 - 100 / (1 + gain / loss)).iloc[-1]
            current_price = t.fast_info.last_price
            ema50 = close.ewm(span=50).mean().iloc[-1]

            ticker_context = (
                f"\nCurrent {context_ticker} context: "
                f"Price=${current_price:.2f}, RSI(14)={rsi:.1f}, "
                f"vs 50 EMA ${ema50:.2f} ({'above' if current_price > ema50 else 'below'})"
            )
        except Exception:
            pass

    prompt = f"""You are a trading educator explaining '{concept}' to a {level}-level trader.
{ticker_context}

Provide a structured explanation with these sections:

1. WHAT IT IS (adapted to {level} level — 2-3 sentences)
2. HOW TRADERS USE IT (practical application)
3. WHEN IT WORKS BEST ({meta.get('works_best', 'trending conditions')})
4. WHEN IT FAILS ({meta.get('fails', 'certain market conditions')})
5. COMMON MISTAKES ({', '.join(meta.get('common_mistakes', ['misuse in wrong conditions']))})
6. WHAT TO COMBINE IT WITH (2 complementary tools)

{"Mention the current " + context_ticker + " reading above and what it means right now." if ticker_context else ""}

Keep it educational, practical, and honest about limitations."""

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        explanation = response.content[0].text.strip()
    except Exception:
        explanation = f"Explanation for {concept} is temporarily unavailable."

    # Update learning profile
    await _update_learning_history(user_id, concept_key)

    return {
        "concept": concept,
        "full_name": meta.get("full_name", concept.title()),
        "category": meta.get("category", "technical"),
        "user_level": level,
        "context_ticker": context_ticker,
        "explanation": explanation,
        "disclaimer": MANDATORY_DISCLAIMER,
    }


async def _update_learning_history(user_id: str, concept: str):
    try:
        from apps.api.database import AsyncSessionLocal
        from database.models.users import UserLearningProfile
        from sqlalchemy import select
        from datetime import datetime, timezone
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserLearningProfile).where(UserLearningProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                history = profile.learning_history or []
                history.append({"concept": concept, "viewed_at": datetime.now(timezone.utc).isoformat()})
                profile.learning_history = history[-50:]  # keep last 50
                profile.last_updated = datetime.now(timezone.utc)
            else:
                profile = UserLearningProfile(
                    user_id=user_id,
                    level="beginner",
                    learning_history=[{"concept": concept, "viewed_at": datetime.now(timezone.utc).isoformat()}],
                )
                db.add(profile)
            await db.commit()
    except Exception:
        pass
