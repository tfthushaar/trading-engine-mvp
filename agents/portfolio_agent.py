"""Portfolio Agent — answers portfolio composition and diversification questions."""
import anthropic
from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()

SYSTEM_PROMPT = """You are a portfolio analysis AI.
Help users understand their portfolio's risk exposure, diversification quality, and correlation dynamics.
Explain portfolio concepts clearly with specific reference to their holdings where provided.
Never recommend specific stocks to buy/sell — focus on portfolio construction principles."""


async def answer_portfolio_query(query: str, user_id: str) -> str:
    portfolio_context = ""
    try:
        from portfolio.analyzer import analyze_portfolio
        analysis = await analyze_portfolio(user_id)
        if analysis:
            portfolio_context = f"Portfolio analysis: {analysis.get('ai_narrative', '')}"
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
        return f"Unable to process your portfolio query. Error: {exc}\n\n{MANDATORY_DISCLAIMER}"
