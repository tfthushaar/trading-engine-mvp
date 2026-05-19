from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional

from apps.api.middleware.auth import get_current_user

router = APIRouter()


@router.get("/explain/{concept}")
async def explain_concept(
    concept: str,
    context_ticker: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """AI contextual explanation of a trading concept."""
    from education.concept_explainer import explain
    return await explain(
        concept=concept,
        user_id=str(user.user_id),
        context_ticker=context_ticker,
    )


@router.get("/profile")
async def get_learning_profile(user=Depends(get_current_user)):
    from apps.api.database import AsyncSessionLocal
    from database.models.users import UserLearningProfile
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(UserLearningProfile).where(UserLearningProfile.user_id == user.user_id)
        )
        profile = result.scalar_one_or_none()
    if not profile:
        return {"level": "beginner", "concepts_mastered": [], "adaptive_score": 0.0}
    return {
        "level": profile.level,
        "concepts_mastered": profile.concepts_mastered or [],
        "adaptive_score": profile.adaptive_score,
    }


@router.get("/next-topic")
async def get_next_topic(user=Depends(get_current_user)):
    from education.adaptive_engine import get_next_recommended_topic
    return await get_next_recommended_topic(str(user.user_id))
