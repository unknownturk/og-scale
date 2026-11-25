"""Aufträge: eine Laufzeit, ein Speicherort.

Aufträge liegen in der SQL-Datenbank und laufen in einem Thread-Pool im
API-Prozess. Nach einem Neustart bleibt nichts auf „läuft" hängen: jeder
unterbrochene Auftrag wird entweder von seinem Handler wieder aufgenommen
(`resume=True`) oder klar als fehlgeschlagen markiert.
"""

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, create_engine, select
from sqlalchemy.orm import declarative_base, sessionmaker

from . import settings

Base = declarative_base()

QUEUED, RUNNING, SUCCEEDED, FAILED = "queued", "running", "succeeded", "failed"
INTERRUPTED = "Durch einen Neustart unterbrochen. Bitte noch einmal starten."


def _now():
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(String(40), primary_key=True)
    kind = Column(String(60), nullable=False)
    status = Column(String(20), nullable=False, default=QUEUED)
    subject = Column(String(80), default="")  # worauf sich der Auftrag bezieht
    payload = Column(Text, default="{}")
    result = Column(Text, default="null")
    error = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


_engine = None
_Session = None
_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="job")
_handlers = {}
_lock = threading.Lock()


def init(url=None):
    global _engine, _Session
    url = url or settings.DATABASE_URL
    if url.startswith("sqlite:///") and ":memory:" not in url:
        from pathlib import Path

        Path(url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    kwargs = {}
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    _engine = create_engine(url, **kwargs)
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(_engine, expire_on_commit=False)


def session():
    """Eine Datenbank-Sitzung (auch für den AliRemote-Plan)."""
    return _Session()


def handler(kind, resume=False):
    """Registriert die Funktion, die einen Auftragstyp ausführt."""

    def wrap(fn):
        _handlers[kind] = (fn, resume)
        return fn

    return wrap


def _view(job):
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "subject": job.subject,
        "result": json.loads(job.result or "null"),
        "error": job.error or "",
        "createdAt": job.created_at.isoformat() if job.created_at else None,
    }


def _set(job_id, **changes):
    with _Session() as s:
        job = s.get(Job, job_id)
        for key, value in changes.items():
            setattr(job, key, value)
        s.commit()


def _run(job_id):
    with _Session() as s:
        job = s.get(Job, job_id)
        kind, payload = job.kind, json.loads(job.payload or "{}")
    _set(job_id, status=RUNNING)
    try:
        result = _handlers[kind][0](payload)
    except Exception as exc:  # jede Ursache landet lesbar beim Nutzer
        _set(job_id, status=FAILED, error=str(exc) or exc.__class__.__name__)
    else:
        _set(job_id, status=SUCCEEDED, result=json.dumps(result, ensure_ascii=False))


def start(kind, payload, subject="", run_inline=False):
    if kind not in _handlers:
        raise ValueError(f"Unbekannter Auftragstyp: {kind}")
    job = Job(
        id="job_" + uuid.uuid4().hex[:16],
        kind=kind,
        subject=subject,
        payload=json.dumps(payload),
    )
    with _Session() as s:
        s.add(job)
        s.commit()
    if run_inline:
        _run(job.id)
    else:
        _pool.submit(_run, job.id)
    return get(job.id)


def get(job_id):
    with _Session() as s:
        job = s.get(Job, job_id)
        return _view(job) if job else None


def active(subject=None):
    with _Session() as s:
        query = select(Job).where(Job.status.in_((QUEUED, RUNNING)))
        if subject:
            query = query.where(Job.subject == subject)
        return [_view(j) for j in s.scalars(query.order_by(Job.created_at))]


def recover():
    """Beim Start aufrufen: nichts bleibt für immer auf „läuft"."""
    with _lock, _Session() as s:
        stuck = list(s.scalars(select(Job).where(Job.status.in_((QUEUED, RUNNING)))))
        resumed = []
        for job in stuck:
            fn_resume = _handlers.get(job.kind, (None, False))[1]
            if fn_resume:
                job.status = QUEUED
                resumed.append(job.id)
            else:
                job.status, job.error = FAILED, INTERRUPTED
        s.commit()
    for job_id in resumed:
        _pool.submit(_run, job_id)
    return {"resumed": len(resumed), "failed": len(stuck) - len(resumed)}
