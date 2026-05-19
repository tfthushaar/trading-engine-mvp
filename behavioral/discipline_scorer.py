"""
Discipline Scorer — computes monthly discipline score (0–100)
and generates AI behavioral report.
"""
from datetime import datetime, timezone, timedelta
import anthropic

from apps.api.config import get_settings
from intelligence.base import MANDATORY_DISCLAIMER

settings = get_settings()


async def compute_discipline_score(user_id: str, days: int = 30) -> dict:
    from behavioral.pattern_detector import detect_patterns, _fetch_recent_trades

    trades = await _fetch_recent_trades(user_id, days)
    patterns = await detect_patterns(user_id, days)

    if not trades:
        return {
            "score": None,
            "message": "No trade data found for the period.",
            "disclaimer": MANDATORY_DISCLAIMER,
        }

    total = len(trades)
    closed = [t for t in trades if t.get("exit_price")]
    n_closed = len(closed)

    # Score components (out of 100)
    score = 70.0  # base

    # Stop loss adherence
    rules_followed = sum(1 for t in trades if t.get("rule_followed") is True)
    rules_total = sum(1 for t in trades if t.get("rule_followed") is not None)
    stop_rate = rules_followed / rules_total if rules_total > 0 else 0.5
    score += (stop_rate - 0.5) * 20  # +10 if 100%, -10 if 0%

    # Journal completion
    journal_rate = n_closed / total if total > 0 else 0
    score += journal_rate * 5

    # Pattern penalties
    high_severity = sum(1 for p in patterns if p.severity == "high")
    score -= high_severity * 8
    medium_severity = sum(1 for p in patterns if p.severity == "medium")
    score -= medium_severity * 4

    # Win rate (reward profitable discipline)
    winners = sum(1 for t in closed if (t.get("pnl_percent") or 0) > 0)
    win_rate = winners / n_closed if n_closed > 0 else 0.5
    if win_rate > 0.55:
        score += 5

    final_score = round(max(0, min(100, score)), 1)

    return {
        "score": final_score,
        "grade": "A" if final_score >= 85 else "B" if final_score >= 70 else "C" if final_score >= 55 else "D",
        "total_trades": total,
        "closed_trades": n_closed,
        "stop_adherence_rate": round(stop_rate, 3),
        "win_rate": round(win_rate, 3),
        "behavioral_patterns": [
            {"pattern": p.pattern, "severity": p.severity, "description": p.description, "count": p.occurrence_count}
            for p in patterns
        ],
        "disclaimer": MANDATORY_DISCLAIMER,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


async def generate_monthly_report(user_id: str) -> dict:
    """Full AI monthly behavioral report."""
    score_data = await compute_discipline_score(user_id, days=30)
    if not score_data.get("score"):
        return score_data

    patterns_text = "\n".join(
        f"- {p['pattern']}: {p['description']}"
        for p in score_data.get("behavioral_patterns", [])
    )

    prompt = f"""You are a trading performance coach writing a monthly behavioral review.

Statistics:
- Discipline Score: {score_data['score']}/100 (Grade: {score_data['grade']})
- Total Trades: {score_data['total_trades']}
- Win Rate: {score_data['win_rate']:.1%}
- Stop Adherence: {score_data['stop_adherence_rate']:.1%}

Behavioral Patterns Detected:
{patterns_text or 'No significant patterns detected.'}

Write a 4-5 sentence coaching report that:
1. Acknowledges what the trader did well
2. Identifies the most important behavioral issue to fix
3. Gives ONE specific, actionable habit to build this month
Be direct, honest, and encouraging — like a good coach, not a cheerleader."""

    narrative = ""
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        narrative = response.content[0].text.strip()
    except Exception:
        narrative = f"Your discipline score this month is {score_data['score']}/100. Focus on following your trading rules consistently."

    return {
        **score_data,
        "ai_report": narrative,
        "period": "last_30_days",
    }
