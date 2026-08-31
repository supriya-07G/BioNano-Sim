"""Multi-objective candidate ranking API route (#30)."""

from typing import Any

from fastapi import APIRouter

from app.schemas.ranking import RankingResponse, RankingWeights
from app.services import ranking_service

router = APIRouter(tags=["candidates"])


@router.get(
    "/candidates/rank",
    response_model=RankingResponse,
    summary="Get multi-objective candidate protein ranking",
)
def get_rankings() -> Any:
    """Return candidates evaluated under default weights."""
    return ranking_service.rank_candidates(weights=RankingWeights())


@router.post(
    "/candidates/rank",
    response_model=RankingResponse,
    summary="Evaluate candidates under custom objective weights",
)
def evaluate_custom_rankings(weights: RankingWeights) -> Any:
    """Return candidates evaluated under custom objective weights."""
    return ranking_service.rank_candidates(weights=weights)
