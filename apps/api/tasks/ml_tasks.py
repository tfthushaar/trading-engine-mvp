"""Celery tasks for ML model refresh and behavioral scoring."""
import asyncio
from apps.api.celery_app import celery_app


@celery_app.task(name="apps.api.tasks.ml_tasks.refresh_regime_model")
def refresh_regime_model() -> dict:
    """Retrain regime detector on latest data (weekly)."""
    try:
        from ml.regime_detector import detect_current_regime
        result = detect_current_regime()
        return {
            "status": "ok",
            "regime": result.regime,
            "confidence": result.confidence,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@celery_app.task(name="apps.api.tasks.ml_tasks.compute_behavioral_scores")
def compute_behavioral_scores() -> dict:
    """Nightly: compute behavioral scores for all active users."""
    try:
        result = asyncio.run(_async_behavioral_scores())
        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


async def _async_behavioral_scores() -> dict:
    from apps.api.database import AsyncSessionLocal
    from database.models.users import User, BehavioralScore
    from behavioral.discipline_scorer import compute_discipline_score
    from sqlalchemy import select
    from datetime import datetime, timezone, timedelta

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.last_active >= datetime.now(timezone.utc) - timedelta(days=30))
        )
        users = result.scalars().all()

    scored = 0
    for user in users:
        try:
            score_data = await compute_discipline_score(str(user.user_id), days=30)
            if score_data.get("score") is not None:
                async with AsyncSessionLocal() as db:
                    entry = BehavioralScore(
                        user_id=user.user_id,
                        period_start=(datetime.now(timezone.utc) - timedelta(days=30)).date(),
                        period_end=datetime.now(timezone.utc).date(),
                        discipline_score=score_data["score"],
                        stop_adherence_rate=score_data.get("stop_adherence_rate"),
                        target_achievement_rate=score_data.get("win_rate"),
                    )
                    db.add(entry)
                    await db.commit()
                    scored += 1
        except Exception:
            pass

    return {"status": "ok", "users_scored": scored}
