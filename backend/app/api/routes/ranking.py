"""Multi-objective candidate ranking API route (#30)."""

from typing import Any
from fastapi import APIRouter, Query

from app.schemas.ranking import RankingResponse, RankingWeights
from app.services import ranking_service

router = APIRouter(tags=["candidates"])


@router.get(
    "/candidates/rank",
    response_model=RankingResponse,
    summary="Get multi-objective candidate protein ranking",
)
def get_rankings(
    allow_mock: bool = Query(
        default=False, description="Set True to allow mock demo mode outputs"
    )
) -> Any:
    """Return candidates evaluated under default conservative weights."""
    return ranking_service.rank_candidates(weights=RankingWeights(), allow_mock=allow_mock)


@router.post(
    "/candidates/rank",
    response_model=RankingResponse,
    summary="Evaluate candidates under custom objective weights",
)
def evaluate_custom_rankings(
    weights: RankingWeights,
    allow_mock: bool = Query(
        default=False, description="Set True to allow mock demo mode outputs"
    ),
) -> Any:
    """Return candidates evaluated under custom objective weights."""
    return ranking_service.rank_candidates(weights=weights, allow_mock=allow_mock)
