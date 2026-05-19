"""
Behavioral pattern detection from trade journal entries.

Detects: revenge_trading, emotional_exit, overtrading,
         stop_loss_moving, fomo_entry, winner_cutting.
"""
from datetime import datetime, timedelta, timezone
from typing import NamedTuple
import pandas as pd


class BehavioralFlag(NamedTuple):
    pattern: str
    severity: str       # low | medium | high
    description: str
    occurrence_count: int


async def detect_patterns(user_id: str, days: int = 30) -> list[BehavioralFlag]:
    """Analyze trade journal for behavioral patterns over the last N days."""
    trades = await _fetch_recent_trades(user_id, days)
    if not trades:
        return []

    flags: list[BehavioralFlag] = []
    df = pd.DataFrame(trades)

    # ── 1. Revenge trading ────────────────────────────────────────────────────
    # 3+ trades within 2h after a losing trade > 1.5% loss
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df = df.sort_values("entry_date")

    losing_trades = df[df["pnl_percent"].fillna(0) < -1.5]
    revenge_count = 0
    for _, loss_row in losing_trades.iterrows():
        loss_time = loss_row["entry_date"]
        window_end = loss_time + timedelta(hours=2)
        subsequent = df[(df["entry_date"] > loss_time) & (df["entry_date"] <= window_end)]
        if len(subsequent) >= 2:
            revenge_count += 1

    if revenge_count > 0:
        flags.append(BehavioralFlag(
            pattern="revenge_trading",
            severity="high" if revenge_count >= 3 else "medium",
            description=f"Detected {revenge_count} instances of taking multiple trades within 2 hours after a loss > 1.5%.",
            occurrence_count=revenge_count,
        ))

    # ── 2. Overtrading ────────────────────────────────────────────────────────
    daily_counts = df.groupby(df["entry_date"].dt.date).size()
    avg_daily = daily_counts.mean()
    std_daily = daily_counts.std()
    overtrade_days = (daily_counts > avg_daily + 2 * std_daily).sum() if std_daily > 0 else 0
    if overtrade_days > 0:
        flags.append(BehavioralFlag(
            pattern="overtrading",
            severity="medium",
            description=f"Traded significantly above your average on {overtrade_days} days (>2σ above your daily mean).",
            occurrence_count=int(overtrade_days),
        ))

    # ── 3. Winner cutting — exits before 50% of target ────────────────────────
    winning_closed = df[
        (df["pnl_percent"].fillna(0) > 0) &
        (df["target"].notna()) &
        (df["exit_price"].notna()) &
        (df["entry_price"].notna())
    ].copy()

    if not winning_closed.empty:
        winning_closed["target_achievement"] = (
            (winning_closed["exit_price"] - winning_closed["entry_price"]).abs() /
            (winning_closed["target"] - winning_closed["entry_price"]).abs().clip(lower=0.01)
        )
        early_exits = (winning_closed["target_achievement"] < 0.5).sum()
        if early_exits > 0:
            flags.append(BehavioralFlag(
                pattern="winner_cutting",
                severity="medium" if early_exits > 2 else "low",
                description=f"Exited {early_exits} winning trade(s) before reaching 50% of your target.",
                occurrence_count=int(early_exits),
            ))

    # ── 4. Stop loss not honored ──────────────────────────────────────────────
    rule_breaks = df[df["rule_followed"] == False].shape[0]
    if rule_breaks > 0:
        flags.append(BehavioralFlag(
            pattern="rule_violation",
            severity="high" if rule_breaks >= 3 else "medium",
            description=f"You marked {rule_breaks} trade(s) as 'rules not followed'.",
            occurrence_count=rule_breaks,
        ))

    # ── 5. Emotional entry patterns ───────────────────────────────────────────
    fomo_count = df[df["emotion_entry"].isin(["fomo", "anxiety"])].shape[0]
    if fomo_count > 2:
        flags.append(BehavioralFlag(
            pattern="emotional_entry",
            severity="medium",
            description=f"{fomo_count} trades entered with FOMO or anxiety — these emotions correlate with poor trade selection.",
            occurrence_count=fomo_count,
        ))

    return flags


async def _fetch_recent_trades(user_id: str, days: int) -> list[dict]:
    try:
        from apps.api.database import AsyncSessionLocal
        from database.models.users import TradeJournal
        from sqlalchemy import select
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TradeJournal)
                .where(
                    TradeJournal.user_id == user_id,
                    TradeJournal.entry_date >= cutoff,
                )
                .order_by(TradeJournal.entry_date)
            )
            entries = result.scalars().all()
        return [
            {
                "ticker": e.ticker,
                "pnl_percent": float(e.pnl_percent) if e.pnl_percent else None,
                "entry_date": e.entry_date,
                "exit_date": e.exit_date,
                "entry_price": float(e.entry_price) if e.entry_price else None,
                "exit_price": float(e.exit_price) if e.exit_price else None,
                "target": float(e.target) if e.target else None,
                "stop_loss": float(e.stop_loss) if e.stop_loss else None,
                "rule_followed": e.rule_followed,
                "emotion_entry": e.emotion_entry,
            }
            for e in entries
        ]
    except Exception:
        return []
