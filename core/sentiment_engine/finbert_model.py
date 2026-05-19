"""
FinBERT model wrapper for financial sentiment analysis.

Provides a singleton-style lazy-loaded analyser that handles:
- Tokenisation and inference via the ``ProsusAI/finbert`` model
- Batched prediction for throughput
- Regex-based ticker extraction against a known-ticker list
- Keyword-based entity / company extraction from text
"""

from __future__ import annotations

import re


import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from utils.config import FINBERT_MODEL_NAME, SENTIMENT_BATCH_SIZE, KNOWN_TICKERS
from utils.logger import get_logger

logger = get_logger(__name__)

# Label mapping for ProsusAI/finbert output indices
_LABELS = ["positive", "negative", "neutral"]


class FinBERTAnalyzer:
    """Lazy-loaded FinBERT analyser for financial text sentiment."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or FINBERT_MODEL_NAME
        self._tokenizer = None
        self._model = None

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------
    def _load_model(self) -> None:
        """Download / load the FinBERT model and tokenizer on first use."""
        if self._model is not None:
            return
        logger.info("Loading FinBERT model '%s' …", self.model_name)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name
        )
        self._model.eval()
        logger.info("FinBERT model loaded successfully.")

    @property
    def tokenizer(self):
        self._load_model()
        return self._tokenizer

    @property
    def model(self):
        self._load_model()
        return self._model

    # ------------------------------------------------------------------
    # Sentiment prediction
    # ------------------------------------------------------------------
    def predict(self, text: str) -> tuple[str, float]:
        """Classify a single piece of text.

        Returns
        -------
        (label, score)
            ``label`` is one of ``positive``, ``neutral``, ``negative``.
            ``score`` is a float in [-1, 1] where positive → +1 and
            negative → -1.
        """
        results = self.predict_batch([text])
        return results[0]

    def predict_batch(
        self, texts: list[str], batch_size: int | None = None
    ) -> list[tuple[str, float]]:
        """Classify a list of texts in batches.

        Returns a list of ``(label, score)`` tuples, one per input text.
        """
        if not texts:
            return []

        batch_size = batch_size or SENTIMENT_BATCH_SIZE
        self._load_model()

        all_results: list[tuple[str, float]] = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            # Truncate to model max length, pad for uniform tensors
            inputs = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )

            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

            for j in range(len(batch_texts)):
                prob_values = probs[j].tolist()
                pred_idx = int(torch.argmax(probs[j]).item())
                label = _LABELS[pred_idx]

                # Convert to a single score in [-1, 1]:
                #   score = P(positive) - P(negative)
                score = round(prob_values[0] - prob_values[1], 4)
                all_results.append((label, score))

        return all_results

    # ------------------------------------------------------------------
    # Ticker extraction
    # ------------------------------------------------------------------
    @staticmethod
    def extract_tickers(text: str) -> list[str]:
        """Extract stock tickers mentioned in *text*.

        Detects both ``$AAPL`` cash-tag notation and bare uppercase words
        (1–5 chars) that match ``KNOWN_TICKERS``.
        """
        if not text:
            return []

        found: set[str] = set()

        # 1. Cash-tag pattern: $AAPL
        for match in re.finditer(r"\$([A-Z]{1,5})\b", text.upper()):
            symbol = match.group(1)
            if symbol in KNOWN_TICKERS:
                found.add(symbol)

        # 2. Bare uppercase words that are in known tickers
        for word in re.findall(r"\b[A-Z]{1,5}\b", text):
            if word in KNOWN_TICKERS:
                found.add(word)

        return sorted(found)

    # ------------------------------------------------------------------
    # Entity extraction (keyword-based)
    # ------------------------------------------------------------------
    @staticmethod
    def extract_entities(text: str) -> list[str]:
        """Extract financial entities (companies, sectors, orgs) from text.

        Uses a curated keyword list for fast, deterministic matching.
        """
        if not text:
            return []

        text_lower = text.lower()
        entities: set[str] = set()

        # Company names → entity
        _COMPANY_NAMES = {
            "apple": "Apple Inc.",
            "microsoft": "Microsoft Corp.",
            "google": "Alphabet Inc.",
            "alphabet": "Alphabet Inc.",
            "amazon": "Amazon.com Inc.",
            "meta": "Meta Platforms Inc.",
            "facebook": "Meta Platforms Inc.",
            "tesla": "Tesla Inc.",
            "nvidia": "NVIDIA Corp.",
            "netflix": "Netflix Inc.",
            "jpmorgan": "JPMorgan Chase",
            "jp morgan": "JPMorgan Chase",
            "goldman sachs": "Goldman Sachs",
            "morgan stanley": "Morgan Stanley",
            "bank of america": "Bank of America",
            "wells fargo": "Wells Fargo",
            "berkshire": "Berkshire Hathaway",
            "exxon": "Exxon Mobil",
            "chevron": "Chevron Corp.",
            "pfizer": "Pfizer Inc.",
            "johnson & johnson": "Johnson & Johnson",
            "walmart": "Walmart Inc.",
            "disney": "Walt Disney Co.",
            "boeing": "Boeing Co.",
            "intel": "Intel Corp.",
            "amd": "Advanced Micro Devices",
            "salesforce": "Salesforce Inc.",
            "oracle": "Oracle Corp.",
            "paypal": "PayPal Holdings",
            "coinbase": "Coinbase Global",
        }

        for keyword, entity_name in _COMPANY_NAMES.items():
            if keyword in text_lower:
                entities.add(entity_name)

        # Sector / organisation keywords
        _SECTOR_KEYWORDS = {
            "federal reserve": "Federal Reserve",
            "the fed": "Federal Reserve",
            "sec ": "SEC",
            "securities and exchange": "SEC",
            "wall street": "Wall Street",
            "nasdaq": "NASDAQ",
            "s&p 500": "S&P 500",
            "dow jones": "Dow Jones",
            "nyse": "NYSE",
            "treasury": "U.S. Treasury",
            "imf": "IMF",
            "world bank": "World Bank",
            "opec": "OPEC",
        }

        for keyword, entity_name in _SECTOR_KEYWORDS.items():
            if keyword in text_lower:
                entities.add(entity_name)

        return sorted(entities)
