from fastapi import FastAPI
from .routes_auth import router as auth_router
from .routes_documents import router as documents_router
from .db import Base, engine
from . import models  # noqa: F401

# Ensure DB tables exist when imported in test/dev contexts where startup may not run
Base.metadata.create_all(bind=engine)


def create_app() -> FastAPI:
    app = FastAPI(title="Haqnow Community API", version="0.1.0")

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/", tags=["system"])
    async def root() -> dict:
        return {"service": "haqnow-community", "version": "0.1.0"}

    app.include_router(auth_router)
    app.include_router(documents_router)

    return app


app = create_app()


@app.on_event("startup")
def on_startup_create_tables() -> None:
    # No-op; tables ensured at import-time for tests
    return None


