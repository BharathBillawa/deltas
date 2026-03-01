"""
FastAPI application entry point.

REST API for damage claims automation system.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import claims, queue, analytics, events, ui
from src.persistence.database import init_db


# Initialize database on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    init_db()
    yield
    # Shutdown (if needed)


# Create FastAPI app
app = FastAPI(
    title="Deltas API",
    description="AI-powered damage claims automation system",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ui.router, prefix="/ui", tags=["Web UI"])
app.include_router(claims.router, prefix="/claims", tags=["Claims"])
app.include_router(queue.router, prefix="/queue", tags=["Approval Queue"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(events.router, prefix="/events", tags=["Events"])


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "name": "Deltas API",
        "version": "0.1.0",
        "description": "AI-powered damage claims automation system",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
