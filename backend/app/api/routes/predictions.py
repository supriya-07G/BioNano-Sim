"""Model info and prediction endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.schemas.prediction import (
    ModelInfoResponse,
    PredictionRequest,
    PredictionResponse,
)
from app.services import prediction_service

router = APIRouter(tags=["predictions"])


@router.get("/model", response_model=ModelInfoResponse, summary="ML model status")
def model_info() -> dict[str, Any]:
    return prediction_service.model_info()


@router.get("/scenarios", summary="Radiation scenario presets")
def scenarios() -> dict[str, Any]:
    return {
        "scenarios": prediction_service.list_scenarios(),
        "dose_units": prediction_service.dose_units(),
        "provenance": prediction_service.scenario_provenance(),
    }


@router.post(
    "/predictions",
    response_model=PredictionResponse,
    summary="ML degradation estimate (MVP model)",
)
def create_prediction(request: PredictionRequest) -> dict[str, Any]:
    """Produce a degradation estimate for one protein/scenario pair.

    Returns 503 when the bundle is unavailable and 400 when the requested
    scenario is outside the model's trained vocabulary — in both cases the
    simulation path remains usable.
    """
    return prediction_service.run_prediction(request).as_dict()
