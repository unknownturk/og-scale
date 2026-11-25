"""OG Scale — Backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import demo, jobs, llm, settings
from .api import content as content_api
from .api.routes import router
from .media import get_provider
from .store import get_store


@asynccontextmanager
async def lifespan(app):
    jobs.init()
    jobs.recover()
    if settings.DEMO_SEED:
        demo.seed(get_store())
    yield


app = FastAPI(title="OG Scale", lifespan=lifespan)
if settings.CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.include_router(content_api.router)
app.include_router(content_api.public)


@app.get("/health")
def health():
    return {"ok": True, "store": get_store().kind, "ai": llm.configured(), "media": get_provider().name if get_provider().configured() else None}
