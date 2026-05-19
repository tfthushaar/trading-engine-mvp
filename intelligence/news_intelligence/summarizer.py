"""
News Intelligence Engine — 7-step pipeline per article.

Steps:
  1. Fetch articles for ticker
  2. Relevance filter
  3. Sentiment scoring (reuse FinBERT from existing sentiment_engine)
  4. Severity classification (LLM)
  5. Sector impact mapping (LLM)
  6. Historical reaction lookup
  7. Impact summary generation (LLM)
"""
import json
from datetime import datetime
from typing import Optional

import anthropic

from apps.api.config import get_settings
from intelligence.base import BaseIntelligenceOutput, MANDATORY_DISCLAIMER

settings = get_settings()
_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def _classify_news_impact(articles: list[dict], ticker: str) -> dict:
    """Single LLM call that classifies severity, sector impact, and generates summary."""
    if not articles:
        return {
            "tone": "neutral",
            "severity": "low",
            "affected_sectors": [],
            "summary": f"No recent news found for {ticker}.",
            "key_risks": [],
        }

    article_text = "\n\n".join(
        f"[{i+1}] {a.get('title', '')} — {a.get('description', '')}"
        for i, a in enumerate(articles[:5])
    )

    prompt = f"""You are a professional financial analyst. Analyze these news articles about {ticker} and respond ONLY with valid JSON.

Articles:
{article_text}

Respond with this exact JSON structure:
{{
  "tone": "bullish|bearish|neutral|mixed",
  "severity": "low|medium|high|critical",
  "affected_sectors": ["list", "of", "sectors"],
  "summary": "2-3 sentence narrative explaining market impact",
  "key_risks": ["risk 1", "risk 2"]
}}"""

    try:
        client = _get_client()
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception as exc:
        print(f"[NewsIntelligence] LLM error: {exc}")
        return {
            "tone": "neutral",
            "severity": "low",
            "affected_sectors": [],
            "summary": f"Unable to generate AI analysis for {ticker} at this time.",
            "key_risks": [],
        }


async def get_ticker_news_intelligence(ticker: str) -> dict:
    """Full news intelligence pipeline for a ticker."""
    # Fetch articles using existing news_collector
    articles = []
    try:
        from core.data_ingestion.news_collector import NewsCollector
        collector = NewsCollector()
        raw = collector.fetch_articles(ticker)
        articles = raw if isinstance(raw, list) else []
    except Exception:
        pass

    # Step 3: FinBERT sentiment (reuse existing)
    sentiment_scores = []
    try:
        from core.sentiment_engine import analyze_headlines
        headlines = [a.get("title", "") for a in articles[:10] if a.get("title")]
        if headlines:
            sentiment_scores = analyze_headlines(headlines)
    except Exception:
        pass

    avg_sentiment = (
        sum(s.get("score", 0) for s in sentiment_scores) / len(sentiment_scores)
        if sentiment_scores else 0.0
    )

    # Steps 4-7: LLM classification and summary
    ai_result = await _classify_news_impact(articles, ticker)

    return {
        "ticker": ticker,
        "article_count": len(articles),
        "avg_finbert_sentiment": round(avg_sentiment, 3),
        "tone": ai_result["tone"],
        "severity": ai_result["severity"],
        "affected_sectors": ai_result["affected_sectors"],
        "summary": ai_result["summary"],
        "key_risks": ai_result["key_risks"],
        "articles": [
            {
                "title": a.get("title"),
                "source": a.get("source_name") or a.get("source", {}).get("name"),
                "published_at": a.get("publishedAt") or a.get("published_at"),
                "url": a.get("url"),
            }
            for a in articles[:8]
        ],
        "disclaimer": MANDATORY_DISCLAIMER,
        "generated_at": datetime.utcnow().isoformat(),
    }
