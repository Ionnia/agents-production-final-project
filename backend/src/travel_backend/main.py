import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, chat, groups, internal, plans, sessions
from .config import get_settings
from .database import SessionFactory
from .errors import install_error_handlers
from .logging import configure_logging
from .seed import seed_data

configure_logging()
logger = logging.getLogger("travel_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with SessionFactory() as db:
        await seed_data(db)
    yield


app = FastAPI(
    title="Travel-Planning Backend",
    version="0.1.0",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Accept-Language", "X-Correlation-ID"],
)
install_error_handlers(app)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    logger.info(
        "request method=%s path=%s status=%s correlation_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        correlation_id,
    )
    return response


app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(groups.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(internal.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
