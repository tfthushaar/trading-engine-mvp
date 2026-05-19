"""
Sentiment Engine package.
Exports lightweight wrappers usable without the legacy DuckDB stack.
"""
from __future__ import annotations


def analyze_headlines(headlines: list[str]) -> list[dict]:
    """
    Run FinBERT sentiment on a list of headline strings.
    Returns list of {label, score} dicts.
    Falls back to keyword heuristic if FinBERT is unavailable.
    """
    if not headlines:
        return []
    try:
        from core.sentiment_engine.finbert_model import FinBERTAnalyzer
        analyzer = FinBERTAnalyzer()
        results = analyzer.predict_batch(headlines)
        return [{"label": label, "score": score} for label, score in results]
    except Exception:
        # Lightweight fallback — count bullish/bearish keywords
        bullish = {"up", "rise", "rally", "gain", "beat", "surges", "record", "profit"}
        bearish = {"down", "fall", "loss", "miss", "drop", "crash", "decline", "warn"}
        out = []
        for h in headlines:
            words = set(h.lower().split())
            b = len(words & bullish)
            s = len(words & bearish)
            if b > s:
                out.append({"label": "positive", "score": 0.6})
            elif s > b:
                out.append({"label": "negative", "score": 0.6})
            else:
                out.append({"label": "neutral", "score": 0.5})
        return out


def run_sentiment_pipeline() -> int:
    """
    Run the full news sentiment pipeline using the legacy DuckDB stack.
    Returns number of articles processed.
    """
    try:
        from database.db_manager import DatabaseManager
        from core.sentiment_engine.news_sentiment import NewsSentimentProcessor
        db = DatabaseManager()
        processor = NewsSentimentProcessor(db)
        return processor.process_all()
    except Exception as exc:
        print(f"[SentimentPipeline] Error: {exc}")
        return 0
