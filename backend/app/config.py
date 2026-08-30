"""Application configuration.

Every path is derived from the repository root so the backend runs identically
whether it is started from ``backend/`` or from the repo root, on Windows or
POSIX. Nothing here reads a database; the MVP persists job state on disk.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/app/config.py -> backend/app -> backend -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings, overridable via environment or ``backend/.env``."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / "backend" / ".env"),
        env_prefix="COSMORA_",
        extra="ignore",
        # `model_` is a Pydantic-reserved prefix; we use model_* field names
        # deliberately (they describe the ML model, not the pydantic model).
        protected_namespaces=(),
    )

    # --- Identity -----------------------------------------------------------
    app_name: str = "COSMORA"
    api_prefix: str = "/api/v1"
    version: str = "0.1.0"

    # --- Paths --------------------------------------------------------------
    repo_root: Path = REPO_ROOT
    data_dir: Path = REPO_ROOT / "data"
    models_dir: Path = REPO_ROOT / "models"
    runtime_dir: Path = REPO_ROOT / "runtime"

    # --- CORS ---------------------------------------------------------------
    # Local frontend dev origins only. Deliberately not "*": the API serves
    # file downloads and accepts uploads.
    # NoDecode is required, not cosmetic. pydantic-settings JSON-decodes any
    # complex-typed field from the environment *before* validators run, so
    # COSMORA_CORS_ORIGINS="https://a.com,https://b.com" raised SettingsError
    # and the app failed to boot -- the _split_origins validator below never
    # got the chance to run. This matters for any deployment that serves the
    # frontend from a different origin than the API.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",  # vite preview
            "http://127.0.0.1:4173",
        ]
    )

    # --- Upload limits ------------------------------------------------------
    max_upload_bytes: int = 8 * 1024 * 1024  # 8 MiB
    max_upload_atoms: int = 100_000
    max_upload_residues: int = 2_000

    # --- Storage quotas and retention (issues #23, #26) ---------------------
    # A single paired experiment writes hundreds of MB of trajectory, so
    # repeated team use fills a disk quietly. These are checked before a job
    # starts: a rejected submission is an error message, a job that dies at
    # step 18,000 because the disk filled is lost work.
    runtime_quota_bytes: int = 8 * 1024**3        # 8 GiB under runtime/
    min_free_disk_bytes: int = 2 * 1024**3        # refuse to start below 2 GiB

    # Days to keep a finished job before it becomes a cleanup candidate.
    # Failed and cancelled jobs go sooner: their artifacts are rarely wanted
    # once the failure has been read, and they are the bulk of the churn.
    retention_days_completed: int = 30
    retention_days_failed: int = 7
    retention_days_cancelled: int = 3

    # --- Simulation safety limits ------------------------------------------
    # One job at a time for the MVP (spec 8). Raising this needs a real queue.
    max_concurrent_jobs: int = 1
    max_production_steps: int = 50_000
    max_minimisation_steps: int = 5_000
    job_wall_clock_limit_s: int = 900

    # --- Logging ------------------------------------------------------------
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        """Allow a comma-separated string from the environment."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    # --- Derived paths ------------------------------------------------------
    @property
    def pdb_dir(self) -> Path:
        return self.data_dir / "proteins" / "pdb"

    @property
    def protein_metadata_dir(self) -> Path:
        return self.data_dir / "proteins" / "metadata"

    @property
    def scenarios_file(self) -> Path:
        return self.data_dir / "scenarios" / "radiation_scenarios.json"

    @property
    def precomputed_dir(self) -> Path:
        return self.data_dir / "precomputed"

    @property
    def ml_data_dir(self) -> Path:
        return self.data_dir / "ml" / "data"

    @property
    def residue_features_csv(self) -> Path:
        return self.ml_data_dir / "public_residue_features.csv"

    @property
    def ranked_candidates_csv(self) -> Path:
        return self.ml_data_dir / "ranked_candidate_residues.csv"

    @property
    def model_bundle_path(self) -> Path:
        return self.models_dir / "COSMORA_mock_model_bundle.pkl"

    @property
    def model_metadata_path(self) -> Path:
        return self.models_dir / "model_metadata.json"

    @property
    def feature_schema_path(self) -> Path:
        return self.models_dir / "feature_schema.json"

    @property
    def jobs_dir(self) -> Path:
        return self.runtime_dir / "jobs"

    @property
    def uploads_dir(self) -> Path:
        return self.runtime_dir / "uploads"

    @property
    def reports_dir(self) -> Path:
        return self.runtime_dir / "reports"

    @property
    def logs_dir(self) -> Path:
        return self.runtime_dir / "logs"

    def ensure_runtime_dirs(self) -> None:
        for path in (self.jobs_dir, self.uploads_dir, self.reports_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
