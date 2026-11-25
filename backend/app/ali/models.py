"""Der AliRemote-Plan liegt in SQL: Sperren und »genau einmal« brauchen Transaktionen."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.types import TypeDecorator

from ..jobs import Base


def now():
    return datetime.now(timezone.utc)


class Moment(TypeDecorator):
    """Zeitpunkt, immer mit Zeitzone. SQLite vergisst die Zone sonst beim Lesen."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Zeitpunkt ohne Zeitzone")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class Account(Base):
    __tablename__ = "ali_accounts"
    id = Column(String(40), primary_key=True)
    username = Column(String(40), nullable=False, unique=True)
    model_id = Column(String(40), nullable=False)
    niche_id = Column(String(40), nullable=False)
    device_id = Column(String(80), nullable=False)
    device_name = Column(String(120), default="")
    native_id = Column(String(80), default="")  # Konto-Kennung bei AliRemote (für native Warm-ups)
    course = Column(String(20), default="")
    created_at = Column(Moment)  # dein Klick »Account erstellt«
    opening_at = Column(Moment)  # ab wann der Kurs wirklich läuft (Automatik eingeschaltet)
    armed = Column(Boolean, default=False)  # Automatik an?
    note = Column(Text, default="")  # warum die Automatik pausiert wurde
    added_at = Column(Moment, default=now)


class Slot(Base):
    __tablename__ = "ali_slots"
    id = Column(String(40), primary_key=True)
    account_id = Column(String(40), nullable=False, index=True)
    device_id = Column(String(80), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    day = Column(Integer, nullable=False)
    ordinal = Column(Integer, default=0)
    due = Column(Moment, nullable=False, index=True)
    window_end = Column(Moment, nullable=False)
    busy_until = Column(Moment, nullable=False)
    minutes = Column(Integer, default=0)
    before = Column(Integer, default=0)
    after = Column(Integer, default=0)
    # planned -> dispatching -> running -> done | posted | failed | uncertain | missed | cancelled
    status = Column(String(20), default="planned", index=True)
    content_id = Column(String(40), default="")
    vault_id = Column(String(80), default="")
    caption = Column(Text, default="")
    dispatch_key = Column(String(80), default="")
    run_id = Column(String(80), default="")
    started_at = Column(Moment)
    finished_at = Column(Moment)
    detail = Column(Text, default="")  # für dich lesbar: warum, was fehlt
    evidence = Column(Text, default="")


class Media(Base):
    """Ein freigegebenes Reel gehört genau einem Account (nie doppelt gepostet)."""

    __tablename__ = "ali_media"
    content_id = Column(String(40), primary_key=True)
    account_id = Column(String(40), nullable=False, index=True)
    vault_id = Column(String(80), default="")
    status = Column(String(20), default="assigned")  # assigned -> delivering -> ready | failed ; used
    delivery_key = Column(String(80), default="")
    detail = Column(Text, default="")


class PhoneLock(Base):
    """Ein Handy macht immer nur eine Sache."""

    __tablename__ = "ali_phone_locks"
    device_id = Column(String(80), primary_key=True)
    slot_id = Column(String(40), nullable=False)
    since = Column(Moment, default=now)


class Flag(Base):
    __tablename__ = "ali_flags"
    key = Column(String(40), primary_key=True)
    value = Column(String(200), default="")
