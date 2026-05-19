"""Adaptive learning engine — recommends the next topic based on user history."""
from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

LEARNING_CURRICULUM = {
    "beginner": [
        "support_resistance", "moving_average", "volume", "risk_reward",
        "candlestick_basics", "trend", "market_sessions",
    ],
    "intermediate": [
        "rsi", "macd", "bollinger_bands", "fibonacci", "options_basics",
        "market_regimes", "sector_rotation", "position_sizing",
    ],
    "advanced": [
        "options_greeks", "volatility_surface", "correlation", "macro_flows",
        "market_microstructure", "portfolio_construction", "behavioral_finance",
    ],
}


async def get_next_recommended_topic(user_id: str) -> dict:
    """Return the next concept for the user to learn based on their history."""
    level = "beginner"
    history_concepts = set()

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
                history = profile.learning_history or []
                history_concepts = {h["concept"] for h in history}
    except Exception:
        pass

    curriculum = LEARNING_CURRICULUM.get(level, LEARNING_CURRICULUM["beginner"])
    unlearned = [c for c in curriculum if c not in history_concepts]

    if not unlearned:
        # Graduate to next level
        levels = list(LEARNING_CURRICULUM.keys())
        current_idx = levels.index(level)
        if current_idx < len(levels) - 1:
            next_level = levels[current_idx + 1]
            unlearned = LEARNING_CURRICULUM[next_level]
            level = next_level
        else:
            return {
                "message": "Congratulations! You've completed all curriculum topics.",
                "level": level,
                "disclaimer": MANDATORY_DISCLAIMER,
            }

    next_topic = unlearned[0]

    return {
        "recommended_topic": next_topic,
        "topic_display": next_topic.replace("_", " ").title(),
        "user_level": level,
        "concepts_remaining_at_level": len(unlearned),
        "disclaimer": MANDATORY_DISCLAIMER,
    }
