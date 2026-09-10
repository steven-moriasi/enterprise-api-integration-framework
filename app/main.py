from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


app = FastAPI(
    title="Enterprise API Integration Framework",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["operations"])
async def health() -> dict[str, str]:
    return {"service": get_settings().service_name, "status": "healthy"}


@app.get("/ready", tags=["operations"])
async def ready() -> dict[str, str]:
    return {"status": "ready"}
