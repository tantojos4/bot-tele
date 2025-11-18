"""
Database helper module.
Uses SQLAlchemy async ORM when DATABASE_URL is set.
Provides CRUD helpers for subscriber storage used by the bot and api.
"""
from __future__ import annotations

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

SQLALCHEMY_AVAILABLE = True
try:
    # type: ignore[reportMissingImports]
    from sqlalchemy import Column, BigInteger, String, DateTime, select  # type: ignore[reportMissingImports]
    # type: ignore[reportMissingImports]
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker  # type: ignore[reportMissingImports]
    # type: ignore[reportMissingImports]
    from sqlalchemy.orm import declarative_base  # type: ignore[reportMissingImports]
except ImportError:  # pragma: no cover - behaves differently across dev machines
    SQLALCHEMY_AVAILABLE = False
    Column = BigInteger = String = DateTime = select = None  # type: ignore
    create_async_engine = AsyncSession = async_sessionmaker = declarative_base = None  # type: ignore

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
Base = declarative_base() if SQLALCHEMY_AVAILABLE else None

if SQLALCHEMY_AVAILABLE:
    class Subscriber(Base):
        __tablename__ = "subscribers"
        chat_id = Column(BigInteger, primary_key=True, index=True)
        first_name = Column(String, nullable=True)
        last_name = Column(String, nullable=True)
        username = Column(String, nullable=True)
        nip = Column(String(18), nullable=True)
        subscribed_at = Column(DateTime(timezone=True), nullable=True)
        updated_at = Column(DateTime(timezone=True), nullable=True)
        # ensure server-defaults are eagerly available
        __mapper_args__ = {"eager_defaults": True}
else:
    Subscriber = None  # type: ignore


engine = None
AsyncSessionLocal = None
if DATABASE_URL and SQLALCHEMY_AVAILABLE:
    # Tune pool settings for reliability; these are sensible defaults for a dev environment
    engine = create_async_engine(
        DATABASE_URL,
        future=True,
        echo=False,
        pool_pre_ping=True,
    )
    AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

# Helpful warning when DATABASE_URL is present but SQLAlchemy is not installed
if DATABASE_URL and not SQLALCHEMY_AVAILABLE:
    logger.warning("DATABASE_URL is set but SQLAlchemy or async driver is not installed; DB storage disabled. Install SQLAlchemy and asyncpg to enable DB storage.")


def is_db_enabled() -> bool:
    return bool(DATABASE_URL and SQLALCHEMY_AVAILABLE)


async def init_db() -> None:
    """Create tables if DB is configured.

    This is idempotent when called multiple times at startup and safe for tests.
    """
    global engine
    if engine is None:
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Initialized DB tables for subscribers")


def _parse_iso_datetime(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    if isinstance(s, datetime):
        return s
    try:
        # handle trailing Z by replacing with +00:00 for fromisoformat
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except Exception:
        logger.exception("Failed to parse ISO datetime: %s", s)
        return None


async def get_subscribers_map() -> Dict[int, Dict[str, Any]]:
    """Return mapping chat_id -> metadata dict from DB.

    Each metadata dict follows the shape used by the JSON fallback in the project.
    """
    if AsyncSessionLocal is None:
        return {}
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Subscriber))
        subs = {}
        for row in result.scalars().all():
            subs[int(row.chat_id)] = {
                "first_name": row.first_name,
                "last_name": row.last_name,
                "username": row.username,
                "nip": row.nip,
                "subscribed_at": row.subscribed_at.isoformat() if row.subscribed_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        return subs


async def get_subscriber(chat_id: int) -> Optional[Dict[str, Any]]:
    if AsyncSessionLocal is None:
        return None
    async with AsyncSessionLocal() as session:
        obj = await session.get(Subscriber, int(chat_id))
        if obj is None:
            return None
        return {
            "first_name": obj.first_name,
            "last_name": obj.last_name,
            "username": obj.username,
            "nip": obj.nip,
            "subscribed_at": obj.subscribed_at.isoformat() if obj.subscribed_at else None,
            "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
        }


async def upsert_subscriber(chat_id: int, first_name: Optional[str] = None, last_name: Optional[str] = None, username: Optional[str] = None, nip: Optional[str] = None, subscribed_at: Optional[str] = None) -> None:
    if AsyncSessionLocal is None:
        return
    async with AsyncSessionLocal() as session:
        async with session.begin():
            obj = await session.get(Subscriber, int(chat_id))
            now = datetime.now(timezone.utc)
            if obj is None:
                sat = _parse_iso_datetime(subscribed_at) if subscribed_at else now
                obj = Subscriber(
                    chat_id=int(chat_id),
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                    nip=(nip[:18] if nip and len(nip) > 18 else nip),
                    subscribed_at=sat,
                    updated_at=now,
                )
                session.add(obj)
            else:
                updated = False
                if first_name is not None and obj.first_name != first_name:
                    obj.first_name = first_name
                    updated = True
                if last_name is not None and obj.last_name != last_name:
                    obj.last_name = last_name
                    updated = True
                if username is not None and obj.username != username:
                    obj.username = username
                    updated = True
                if nip is not None:
                    # enforce 18 char max length; truncate if necessary
                    if nip and len(nip) > 18:
                        logger.warning("nip provided is longer than 18 characters; truncating for chat_id=%s", chat_id)
                        nip_val = nip[:18]
                    else:
                        nip_val = nip
                    if obj.nip != nip_val:
                        obj.nip = nip_val
                        updated = True
                if updated:
                    obj.updated_at = now
                    session.add(obj)


async def save_subscribers_map(subs_map: Dict[int, Dict[str, Any]]) -> None:
    if AsyncSessionLocal is None:
        return
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for k, meta in (subs_map or {}).items():
                cid = int(k)
                obj = await session.get(Subscriber, cid)
                if obj is None:
                    subscribed_at = _parse_iso_datetime(meta.get("subscribed_at")) if meta else None
                    obj = Subscriber(
                        chat_id=cid,
                        first_name=meta.get("first_name") if meta else None,
                        last_name=meta.get("last_name") if meta else None,
                        username=meta.get("username") if meta else None,
                        nip=(meta.get("nip")[:18] if (meta.get("nip") and len(meta.get("nip")) > 18) else meta.get("nip")) if meta else None,
                        subscribed_at=subscribed_at or datetime.now(timezone.utc),
                        updated_at=_parse_iso_datetime(meta.get("updated_at")) or datetime.now(timezone.utc),
                    )
                    session.add(obj)
                else:
                    obj.first_name = meta.get("first_name") if meta else None
                    obj.last_name = meta.get("last_name") if meta else None
                    obj.username = meta.get("username") if meta else None
                    # enforce 18 char max length for nip
                    nip_val = None
                    if meta and meta.get("nip") is not None:
                        nip_raw = meta.get("nip")
                        nip_val = nip_raw[:18] if (nip_raw and len(nip_raw) > 18) else nip_raw
                    obj.nip = nip_val
                    obj.updated_at = _parse_iso_datetime(meta.get("updated_at")) or datetime.now(timezone.utc)
                    session.add(obj)


async def delete_subscriber(chat_id: int) -> None:
    if AsyncSessionLocal is None:
        return
    async with AsyncSessionLocal() as session:
        async with session.begin():
            obj = await session.get(Subscriber, int(chat_id))
            if obj:
                await session.delete(obj)


async def close_db() -> None:
    if engine is not None:
        await engine.dispose()
