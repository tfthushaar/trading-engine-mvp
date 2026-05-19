"""
Multi-agent orchestrator using LangGraph.

Routes user queries to the appropriate specialist agent:
  - News/events → News Agent
  - Market analysis → Market Analyst Agent
  - Trade review/scoring → Trade Reviewer Agent
  - Risk questions → Risk Agent
  - Portfolio → Portfolio Agent
  - Learning/explaining → Educational Agent
"""
import uuid
import re
from datetime import datetime, timezone
from typing import Annotated, TypedDict

import anthropic
from langgraph.graph import StateGraph, END

from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()


class AgentState(TypedDict):
    query: str
    user_id: str
    conversation_id: str
    agent_selected: str
    response: str
    context: dict


ROUTING_PROMPT = """You are a query router for a financial intelligence platform.
Classify this user query into ONE category:

- news_agent: questions about news, events, market-moving headlines
- market_analyst: questions about market trends, sectors, macro, "what's happening"
- trade_reviewer: questions about evaluating a trade, entry/exit, stop loss, risk/reward
- risk_agent: questions about risk management, portfolio risk, drawdowns
- portfolio_agent: questions about portfolio composition, correlation, diversification
- educational_agent: questions asking "what is X", "explain Y", "how does Z work"

Query: {query}

Respond with ONLY the category name, nothing else."""


async def _route_query(state: AgentState) -> AgentState:
    """Use Claude to classify the query and select the right agent."""
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",  # fast routing model
            max_tokens=20,
            messages=[{
                "role": "user",
                "content": ROUTING_PROMPT.format(query=state["query"])
            }],
        )
        agent = response.content[0].text.strip().lower()
        valid_agents = ["news_agent", "market_analyst", "trade_reviewer",
                        "risk_agent", "portfolio_agent", "educational_agent"]
        state["agent_selected"] = agent if agent in valid_agents else "market_analyst"
    except Exception:
        state["agent_selected"] = "market_analyst"
    return state


async def _run_news_agent(state: AgentState) -> AgentState:
    from agents.news_agent import answer_news_query
    state["response"] = await answer_news_query(state["query"], state["user_id"])
    return state


async def _run_market_analyst(state: AgentState) -> AgentState:
    from agents.market_analyst_agent import answer_market_query
    state["response"] = await answer_market_query(state["query"], state["user_id"])
    return state


async def _run_trade_reviewer(state: AgentState) -> AgentState:
    from agents.trade_reviewer_agent import answer_trade_query
    state["response"] = await answer_trade_query(state["query"], state["user_id"])
    return state


async def _run_risk_agent(state: AgentState) -> AgentState:
    from agents.risk_agent import answer_risk_query
    state["response"] = await answer_risk_query(state["query"], state["user_id"])
    return state


async def _run_portfolio_agent(state: AgentState) -> AgentState:
    from agents.portfolio_agent import answer_portfolio_query
    state["response"] = await answer_portfolio_query(state["query"], state["user_id"])
    return state


async def _run_educational_agent(state: AgentState) -> AgentState:
    from agents.educational_agent import answer_education_query
    state["response"] = await answer_education_query(state["query"], state["user_id"])
    return state


def _select_agent_node(state: AgentState) -> str:
    return state["agent_selected"]


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("router", _route_query)
    graph.add_node("news_agent", _run_news_agent)
    graph.add_node("market_analyst", _run_market_analyst)
    graph.add_node("trade_reviewer", _run_trade_reviewer)
    graph.add_node("risk_agent", _run_risk_agent)
    graph.add_node("portfolio_agent", _run_portfolio_agent)
    graph.add_node("educational_agent", _run_educational_agent)

    graph.set_entry_point("router")
    graph.add_conditional_edges("router", _select_agent_node, {
        "news_agent": "news_agent",
        "market_analyst": "market_analyst",
        "trade_reviewer": "trade_reviewer",
        "risk_agent": "risk_agent",
        "portfolio_agent": "portfolio_agent",
        "educational_agent": "educational_agent",
    })
    for node in ["news_agent", "market_analyst", "trade_reviewer",
                 "risk_agent", "portfolio_agent", "educational_agent"]:
        graph.add_edge(node, END)

    return graph.compile()


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def route_query(query: str, user_id: str, conversation_id: str | None = None) -> dict:
    """Main entry point — route a user query to the right agent."""
    conv_id = conversation_id or str(uuid.uuid4())
    graph = _get_graph()

    initial_state = AgentState(
        query=query,
        user_id=user_id,
        conversation_id=conv_id,
        agent_selected="market_analyst",
        response="",
        context={},
    )

    result = await graph.ainvoke(initial_state)

    # Persist conversation
    await _save_conversation(user_id, conv_id, query, result["response"], result["agent_selected"])

    return {
        "conversation_id": conv_id,
        "agent_used": result["agent_selected"],
        "response": result["response"],
        "disclaimer": MANDATORY_DISCLAIMER,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _save_conversation(user_id: str, conv_id: str, query: str, response: str, agent: str):
    try:
        from apps.api.database import AsyncSessionLocal
        from database.models.users import AgentConversation
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentConversation).where(AgentConversation.conversation_id == conv_id)
            )
            conv = result.scalar_one_or_none()
            if conv:
                messages = conv.messages or []
                messages.append({"role": "user", "content": query})
                messages.append({"role": "assistant", "content": response, "agent": agent})
                conv.messages = messages
                conv.updated_at = datetime.now(timezone.utc)
            else:
                conv = AgentConversation(
                    conversation_id=uuid.UUID(conv_id),
                    user_id=uuid.UUID(user_id),
                    agent_type=agent,
                    messages=[
                        {"role": "user", "content": query},
                        {"role": "assistant", "content": response, "agent": agent},
                    ],
                )
                db.add(conv)
            await db.commit()
    except Exception as exc:
        print(f"[Orchestrator] Failed to save conversation: {exc}")
