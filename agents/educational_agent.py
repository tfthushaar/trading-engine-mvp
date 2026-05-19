"""Educational Agent — explains trading concepts contextually."""
import anthropic
from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()

SYSTEM_PROMPT = """You are an expert trading educator AI.
Explain financial and trading concepts clearly, at the right difficulty level for the user.
Use real market examples when possible. Cover: what it is, when it works, when it fails, common mistakes.
Make learning practical — connect theory to how traders actually use it."""


async def answer_education_query(query: str, user_id: str) -> str:
    # Get user level for adaptive response
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

    system_with_level = f"{SYSTEM_PROMPT}\n\nUser level: {level}. Adjust explanation complexity accordingly."

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=system_with_level,
            messages=[{"role": "user", "content": query}],
        )
        answer = response.content[0].text.strip()
        return f"{answer}\n\n---\n*{MANDATORY_DISCLAIMER}*"
    except Exception as exc:
        return f"Unable to process your question. Error: {exc}\n\n{MANDATORY_DISCLAIMER}"
