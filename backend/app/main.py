import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401
from .collaboration import sio
from .db import Base, engine
from .routes_auth import router as auth_router
from .routes_documents import router as documents_router
from .routes_search import router as search_router

# Ensure DB tables exist when imported in test/dev contexts where startup may not run
Base.metadata.create_all(bind=engine)


def create_app() -> FastAPI:
    app = FastAPI(title="Haqnow Community API", version="0.1.0")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=600,
    )

    # Add simple HEAD handlers for health/root to satisfy scripts that probe via HEAD
    @app.head("/health")
    async def health_head() -> None:
        return None

    @app.head("/")
    async def root_head() -> None:
        return None

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/", tags=["system"])
    async def root() -> dict:
        return {"service": "haqnow-community", "version": "0.1.0"}

    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(search_router)

    # Mount Socket.IO for collaboration while keeping FastAPI instance
    # so lifecycle events and dependency injection continue to work.
    # Mount Socket.IO ASGI app at /socket.io, enable CORS headers for polling
    socketio_app = socketio.ASGIApp(sio, socketio_path="/socket.io")
    app.mount("/socket.io", socketio_app)

    return app


app = create_app()


@app.on_event("startup")
def on_startup_create_tables() -> None:
    # No-op; tables ensured at import-time for tests
    return None
