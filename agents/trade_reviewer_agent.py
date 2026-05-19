"""Trade Reviewer Agent — evaluates trade setups mentioned in natural language."""
import re
import anthropic
from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()

SYSTEM_PROMPT = """You are a professional trading coach AI.
When users describe a trade setup, evaluate it objectively: risk/reward, technical alignment, timing, and common pitfalls.
Be direct and honest — don't validate poor setups just to be encouraging.
Never promise profits or guarantee outcomes. Focus on the process, not the result."""


async def answer_trade_query(query: str, user_id: str) -> str:
    # Try to extract trade parameters from natural language
    ticker_match = re.search(r'\b([A-Z]{2,5})\b', query)
    price_matches = re.findall(r'\$?([\d,]+\.?\d*)', query)

    context = ""
    if ticker_match and len(price_matches) >= 2:
        ticker = ticker_match.group(1)
        prices = [float(p.replace(",", "")) for p in price_matches[:3]]
        context = f"Detected trade setup: ticker={ticker}, prices mentioned={prices}"

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"{context}\n\nUser Query: {query}"}
            ],
        )
        answer = response.content[0].text.strip()
        return f"{answer}\n\n---\n*{MANDATORY_DISCLAIMER}*"
    except Exception as exc:
        return f"Unable to process your trade query. Error: {exc}\n\n{MANDATORY_DISCLAIMER}"
