"""Aggregate router for API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import health, predictions, proteins, reports, simulations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(proteins.router)
api_router.include_router(predictions.router)
api_router.include_router(simulations.router)
api_router.include_router(reports.router)
