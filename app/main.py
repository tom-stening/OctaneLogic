"""OctaneLogic – FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import efficiency, trips, vehicles

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Local-first energy efficiency engine for ICE, Hybrid, and EV drivetrains. "
        "Minimises $/km by integrating real-time fuel/grid pricing with a "
        "terrain-aware physics model."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vehicles.router)
app.include_router(trips.router)
app.include_router(efficiency.router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
