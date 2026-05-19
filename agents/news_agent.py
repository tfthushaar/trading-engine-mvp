"""News Agent — answers news and event-driven questions."""
import anthropic
from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()

SYSTEM_PROMPT = """You are a financial news analyst AI.
You help traders understand the significance and market impact of news events.
Explain events clearly, provide historical context where relevant, and identify which assets/sectors are most affected.
Never make specific buy/sell recommendations. Always note that this is educational analysis."""


async def answer_news_query(query: str, user_id: str) -> str:
    # Extract ticker mentions for context
    import re
    tickers = re.findall(r'\b[A-Z]{2,5}\b', query)

    articles_context = ""
    if tickers:
        try:
            from intelligence.news_intelligence.summarizer import get_ticker_news_intelligence
            news_data = await get_ticker_news_intelligence(tickers[0])
            if news_data.get("articles"):
                articles_context = "\n".join(
                    f"- {a['title']} ({a.get('published_at', '')})"
                    for a in news_data["articles"][:5]
                )
        except Exception:
            pass

    context = f"Recent News Articles:\n{articles_context}" if articles_context else ""

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"{context}\n\nUser Question: {query}"}
            ],
        )
        answer = response.content[0].text.strip()
        return f"{answer}\n\n---\n*{MANDATORY_DISCLAIMER}*"
    except Exception as exc:
        return f"Unable to process your news query. Error: {exc}\n\n{MANDATORY_DISCLAIMER}"
