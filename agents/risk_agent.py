"""Risk Agent — answers risk management questions."""
import anthropic
from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()

SYSTEM_PROMPT = """You are a risk management specialist AI.
Help traders understand position sizing, portfolio risk, drawdown management, and risk/reward principles.
Focus on the mathematics and logic of risk — never promise that following any rule guarantees profits.
Be precise and educational."""


async def answer_risk_query(query: str, user_id: str) -> str:
    # Get portfolio context if available
    portfolio_context = ""
    try:
        from portfolio.risk_metrics import compute_risk_metrics
        risk_data = await compute_risk_metrics(user_id)
        if risk_data:
            portfolio_context = f"User portfolio context: beta={risk_data.get('beta', 'N/A')}, health_score={risk_data.get('health_score', 'N/A')}"
    except Exception:
        pass

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"{portfolio_context}\n\nUser Question: {query}"}
            ],
        )
        answer = response.content[0].text.strip()
        return f"{answer}\n\n---\n*{MANDATORY_DISCLAIMER}*"
    except Exception as exc:
        return f"Unable to process your risk query. Error: {exc}\n\n{MANDATORY_DISCLAIMER}"
