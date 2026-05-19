from pydantic import BaseModel, Field

MANDATORY_DISCLAIMER = (
    "This analysis is AI-generated for educational and informational purposes only. "
    "It does not constitute financial advice, investment recommendations, or solicitation "
    "to buy or sell any security. Past performance is not indicative of future results. "
    "All trading involves significant risk of loss. Consult a registered financial advisor "
    "before making investment decisions."
)


class BaseIntelligenceOutput(BaseModel):
    disclaimer: str = Field(default=MANDATORY_DISCLAIMER)
