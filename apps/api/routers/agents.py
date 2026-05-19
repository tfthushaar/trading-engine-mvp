from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.middleware.auth import get_current_user

router = APIRouter()


class ChatMessage(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/chat")
async def chat_with_analyst(payload: ChatMessage, user=Depends(get_current_user)):
    """Natural language market research via multi-agent system."""
    from agents.orchestrator import route_query
    return await route_query(
        query=payload.message,
        user_id=str(user.user_id),
        conversation_id=payload.conversation_id,
    )


@router.get("/conversations")
async def list_conversations(user=Depends(get_current_user)):
    from apps.api.database import AsyncSessionLocal
    from database.models.users import AgentConversation
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentConversation)
            .where(AgentConversation.user_id == user.user_id)
            .order_by(AgentConversation.updated_at.desc())
            .limit(20)
        )
        convs = result.scalars().all()
    return [
        {
            "id": str(c.conversation_id),
            "agent_type": c.agent_type,
            "preview": (c.messages or [{}])[-1].get("content", "")[:100],
            "updated_at": str(c.updated_at),
        }
        for c in convs
    ]
