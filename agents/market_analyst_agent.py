"""Market Analyst Agent — answers broad market questions with data context."""
import anthropic
from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER
from intelligence.market_narrative.briefing_generator import _get_macro_snapshot, _get_sector_snapshot

settings = get_settings()

SYSTEM_PROMPT = """You are a professional market analyst AI assistant.
Your role is to help traders understand market conditions, trends, and dynamics.
You provide factual, educational market analysis — you NEVER give personalized investment advice.
Always be clear that your analysis is for educational purposes only.
Base your responses on the market data provided."""


async def answer_market_query(query: str, user_id: str) -> str:
    macro = _get_macro_snapshot()
    sectors = _get_sector_snapshot()

    macro_text = "; ".join(
        f"{k}: {v['price']} ({v['change_pct']:+.2f}%)"
        for k, v in macro.items() if v["price"]
    )
    sector_text = "; ".join(
        f"{k}: {v['change_pct']:+.2f}%"
        for k, v in sectors.items() if v["change_pct"] is not None
    )

    try:
        from ml.regime_detector import detect_current_regime
        regime = detect_current_regime()
        regime_text = f"Current market regime: {regime.regime} (confidence: {regime.confidence:.0%})"
    except Exception:
        regime_text = ""

    context = f"""Current Market Data:
{macro_text}

Sector Performance:
{sector_text}

{regime_text}"""

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Market Context:\n{context}\n\nUser Question: {query}"}
            ],
        )
        answer = response.content[0].text.strip()
        return f"{answer}\n\n---\n*{MANDATORY_DISCLAIMER}*"
    except Exception as exc:
        return f"Unable to process your query at this time. Error: {exc}\n\n{MANDATORY_DISCLAIMER}"
