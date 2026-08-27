"""Report/export schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExperimentReport(BaseModel):
    """The JSON export for one completed experiment."""

    model_config = ConfigDict(protected_namespaces=())

    report_version: str = "1.0"
    generated_at_utc: str
    job_id: str
    scientific_notice: dict[str, Any] = Field(default_factory=dict)
    experiment: dict[str, Any] = Field(default_factory=dict)
    protein: dict[str, Any] = Field(default_factory=dict)
    scenario: dict[str, Any] = Field(default_factory=dict)
    ml_prediction: dict[str, Any] | None = None
    simulation: dict[str, Any] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    reproducibility: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    time_utc: str


class ComponentReadiness(BaseModel):
    name: str
    ready: bool
    status: str = Field(description="ready | degraded | unavailable")
    detail: str
    version: str | None = None
    remediation: str | None = None


class ReadinessResponse(BaseModel):
    ready: bool
    status: str
    time_utc: str
    components: list[ComponentReadiness]
    counts: dict[str, int] = Field(default_factory=dict)
