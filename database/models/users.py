import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Numeric, Integer, Text, ForeignKey, DateTime, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from apps.api.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    watchlists: Mapped[list["Watchlist"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    positions: Mapped[list["PortfolioPosition"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    journal_entries: Mapped[list["TradeJournal"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    strategies: Mapped[list["UserStrategy"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    learning_profile: Mapped["UserLearningProfile | None"] = relationship(back_populates="user", uselist=False)
    conversations: Mapped[list["AgentConversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Watchlist(Base):
    __tablename__ = "watchlists"

    watchlist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    tickers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    alerts_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="watchlists")


class UserStrategy(Base):
    __tablename__ = "user_strategies"

    user_strategy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    strategy_name: Mapped[str] = mapped_column(String(255))
    based_on_template: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entry_conditions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    exit_conditions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    risk_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    asset_scope: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="strategies")


class TradeJournal(Base):
    __tablename__ = "trade_journal"

    journal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    position_size: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    entry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    target: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    actual_pnl: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    pnl_percent: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    emotion_entry: Mapped[str | None] = mapped_column(String(50), nullable=True)
    emotion_exit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rule_followed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_review: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    behavioral_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="journal_entries")


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    position_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    ticker: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    avg_cost: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    current_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="positions")


class BehavioralScore(Base):
    __tablename__ = "behavioral_scores"

    score_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    period_start: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    discipline_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    stop_adherence_rate: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    target_achievement_rate: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    overtrading_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    revenge_trading_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    early_exit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserLearningProfile(Base):
    __tablename__ = "user_learning_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[str] = mapped_column(String(20), default="beginner")
    concepts_mastered: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    learning_history: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    adaptive_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="learning_profile")


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    messages: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    context_used: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="conversations")


class AINarrative(Base):
    __tablename__ = "ai_narratives"

    narrative_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    narrative_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


class AlertLog(Base):
    __tablename__ = "alert_log"

    alert_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    alert_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    trigger_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    ai_narration: Mapped[str | None] = mapped_column(Text, nullable=True)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
