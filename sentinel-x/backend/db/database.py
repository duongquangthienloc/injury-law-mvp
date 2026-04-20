from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, select, text,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from ..config import settings


engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SignalRow(Base):
    __tablename__ = "signals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, nullable=False, index=True)
    source = Column(String(200), nullable=False)
    headline = Column(Text, nullable=False)
    content_summary = Column(Text, default="")
    actor = Column(String(200), default="")
    actor_bloc = Column(String(20), default="OTHER")
    severity = Column(Integer, default=1)
    action_keywords = Column(Text, default="")  # JSON-encoded list
    url = Column(Text, default="")
    is_realtime = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EscalationRow(Base):
    __tablename__ = "escalation_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, nullable=False, index=True)
    burden_of_restraint = Column(Float, default=0.0)
    probability_of_harm = Column(Float, default=0.0)
    loss_magnitude = Column(Float, default=0.0)
    expected_loss = Column(Float, default=0.0)
    threshold_breached = Column(Boolean, default=False)
    escalation_index = Column(Float, default=0.0)
    risk_tier = Column(String(20), default="STABLE")
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def save_signal(session: AsyncSession, signal_data: dict) -> None:
    row = SignalRow(**signal_data)
    session.add(row)
    await session.commit()


async def save_escalation(session: AsyncSession, record: dict) -> None:
    row = EscalationRow(**record)
    session.add(row)
    await session.commit()


async def fetch_signals_in_window(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    is_realtime: Optional[bool] = None,
) -> List[SignalRow]:
    stmt = select(SignalRow).where(
        SignalRow.timestamp >= start,
        SignalRow.timestamp <= end,
    ).order_by(SignalRow.timestamp.desc())

    if is_realtime is not None:
        stmt = stmt.where(SignalRow.is_realtime == is_realtime)

    result = await session.execute(stmt)
    return result.scalars().all()


async def fetch_escalation_history(
    session: AsyncSession,
    limit: int = 180,
) -> List[EscalationRow]:
    stmt = (
        select(EscalationRow)
        .order_by(EscalationRow.timestamp.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()
