"""Loads the ML bundle exactly once, at startup, and self-verifies it.

Design points that matter:

* **Load-once.** ``get_model()`` returns a process-wide singleton; unpickling an
  XGBoost booster per request would dominate latency.
* **Never fatal.** A missing or corrupt bundle degrades the service to
  "predictions unavailable" and is reported through ``/system/readiness``. The
  protein registry, simulation engine and viewer keep working (spec 10).
* **Self-verifying.** We confirm the pickle's SHA-256 against
  ``release_manifest.json`` and confirm that the generated feature schema still
  matches the live pipeline's own columns and encoder vocabularies. A silent
  drift between the two would let the API validate against the wrong contract.
"""

from __future__ import annotations

import hashlib
import json
import threading
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.logging import get_logger
from app.ml.feature_schema import FeatureSchema, load_feature_schema

logger = get_logger("COSMORA.ml.loader")

_lock = threading.Lock()
_state: ModelState | None = None


@dataclass
class ModelState:
    """Outcome of the single load attempt."""

    available: bool
    pipeline: Any | None = None
    schema: FeatureSchema | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    model_version: str = "unknown"
    scientific_status: str = "UNKNOWN"
    bundle_sha256: str | None = None
    sha256_verified: bool = False
    schema_verified: bool = False
    load_error: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.available:
            return "unavailable"
        if self.warnings:
            return "degraded"
        return "ready"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_schema_against_pipeline(
    pipeline: Any, schema: FeatureSchema, notes: list[str]
) -> bool:
    """Confirm the generated JSON still describes this exact pipeline."""
    try:
        pre = pipeline.named_steps["preprocessor"]
        num_cols = list(pre.transformers_[0][2])
        cat_cols = list(pre.transformers_[1][2])
        encoder = pre.transformers_[1][1].named_steps["encoder"]
        live_vocab = {
            col: [str(v) for v in cats]
            for col, cats in zip(cat_cols, encoder.categories_, strict=True)
        }
    except (AttributeError, KeyError, IndexError) as exc:
        notes.append(
            f"Could not introspect the pipeline to verify the feature schema ({exc}). "
            "Input validation is running against the generated schema unverified."
        )
        return False

    ok = True
    if num_cols != schema.numeric_features:
        notes.append(
            "Schema drift: numeric feature list differs from the pipeline's own "
            f"columns (schema={schema.numeric_features}, pipeline={num_cols})."
        )
        ok = False
    if cat_cols != schema.categorical_features:
        notes.append(
            "Schema drift: categorical feature list differs from the pipeline's "
            f"own columns (schema={schema.categorical_features}, pipeline={cat_cols})."
        )
        ok = False
    if live_vocab != schema.vocabulary:
        notes.append(
            "Schema drift: encoder vocabulary differs from the generated schema. "
            "Regenerate with scripts/generate_feature_schema.py."
        )
        ok = False
    return ok


def _load() -> ModelState:
    notes: list[str] = []
    bundle_path = settings.model_bundle_path

    if not bundle_path.exists():
        msg = f"Model bundle not found at {bundle_path}."
        logger.error(msg)
        return ModelState(available=False, load_error=msg)

    # --- integrity ------------------------------------------------------
    digest = _sha256(bundle_path)
    sha_ok = False
    manifest_path = settings.models_dir / "release_manifest.json"
    if manifest_path.exists():
        try:
            expected = json.loads(manifest_path.read_text(encoding="utf-8")).get(
                "model_sha256"
            )
            sha_ok = expected == digest
            if not sha_ok:
                notes.append(
                    "Model bundle SHA-256 does not match release_manifest.json "
                    f"(expected {expected}, got {digest}). The file may have been "
                    "modified or replaced."
                )
        except (json.JSONDecodeError, OSError) as exc:
            notes.append(f"Could not read release_manifest.json ({exc}).")
    else:
        notes.append("release_manifest.json is missing; bundle integrity unverified.")

    # --- unpickle -------------------------------------------------------
    try:
        import joblib  # imported lazily so a broken install is a soft failure

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            bundle = joblib.load(bundle_path)
        for w in caught:
            text = str(w.message)
            # XGBoost warns on any cross-version pickle. We verify numerical
            # fidelity separately (scripts/validate_model.py reproduces the
            # shipped prediction reports), so this is informational.
            if "InconsistentVersionWarning" in w.category.__name__:
                notes.append(
                    "scikit-learn version mismatch while unpickling: "
                    f"{text}. Pin scikit-learn==1.7.1 (see backend/requirements.txt)."
                )
            elif "xgboost" in text.lower() or "serialized model" in text.lower():
                logger.info("XGBoost pickle notice (expected, benign): %s", text)
    except Exception as exc:  # noqa: BLE001 - any failure must stay non-fatal
        msg = f"Failed to load the model bundle: {type(exc).__name__}: {exc}"
        logger.exception(msg)
        return ModelState(
            available=False, load_error=msg, bundle_sha256=digest, warnings=notes
        )

    if not isinstance(bundle, dict) or "pipeline" not in bundle:
        msg = (
            "Model bundle has an unexpected layout: expected a dict containing a "
            f"'pipeline' key, got {type(bundle).__name__}."
        )
        logger.error(msg)
        return ModelState(
            available=False, load_error=msg, bundle_sha256=digest, warnings=notes
        )

    pipeline = bundle["pipeline"]
    if not hasattr(pipeline, "predict"):
        msg = "Bundle 'pipeline' has no .predict(); refusing to serve predictions."
        logger.error(msg)
        return ModelState(
            available=False, load_error=msg, bundle_sha256=digest, warnings=notes
        )

    # Patch SimpleImputer compatibility across scikit-learn version differences
    def _patch_imputers(obj: Any) -> None:
        if hasattr(obj, "_fit_dtype") and not hasattr(obj, "_fill_dtype"):
            setattr(obj, "_fill_dtype", getattr(obj, "_fit_dtype", None))
        if hasattr(obj, "transformers_"):
            for _, trans, _ in getattr(obj, "transformers_", []):
                _patch_imputers(trans)
        if hasattr(obj, "steps"):
            for _, step in getattr(obj, "steps", []):
                _patch_imputers(step)
        if hasattr(obj, "named_steps"):
            for _, step in getattr(obj, "named_steps", {}).items():
                _patch_imputers(step)

    _patch_imputers(pipeline)

    # --- schema ---------------------------------------------------------
    try:
        schema = load_feature_schema()
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
        msg = f"Feature schema unusable: {exc}"
        logger.error(msg)
        return ModelState(
            available=False, load_error=msg, bundle_sha256=digest, warnings=notes
        )

    schema_ok = _verify_schema_against_pipeline(pipeline, schema, notes)

    bundle_feature_order = list(bundle.get("feature_columns") or [])
    if bundle_feature_order and bundle_feature_order != schema.feature_order:
        notes.append(
            "Schema drift: feature order differs between the bundle and the "
            "generated schema. Regenerate scripts/generate_feature_schema.py."
        )
        schema_ok = False

    metadata: dict[str, Any] = dict(bundle.get("metadata") or {})
    if settings.model_metadata_path.exists():
        try:
            metadata = {
                **json.loads(settings.model_metadata_path.read_text(encoding="utf-8")),
                **metadata,
            }
        except (json.JSONDecodeError, OSError) as exc:
            notes.append(f"Could not read model_metadata.json ({exc}).")

    state = ModelState(
        available=True,
        pipeline=pipeline,
        schema=schema,
        metadata=metadata,
        model_version=str(bundle.get("model_version") or schema.model_version),
        scientific_status=str(
            bundle.get("scientific_status") or schema.scientific_status
        ),
        bundle_sha256=digest,
        sha256_verified=sha_ok,
        schema_verified=schema_ok,
        warnings=notes,
    )
    logger.info(
        "Model loaded: version=%s status=%s sha256_verified=%s schema_verified=%s",
        state.model_version,
        state.scientific_status,
        sha_ok,
        schema_ok,
    )
    for note in notes:
        logger.warning("Model load note: %s", note)
    return state


def get_model() -> ModelState:
    """Process-wide singleton; loads on first call."""
    global _state
    if _state is None:
        with _lock:
            if _state is None:
                _state = _load()
    return _state


def reset_model_cache() -> None:
    """Test hook: forget the loaded model so the next call re-reads from disk."""
    global _state
    with _lock:
        _state = None
    load_feature_schema.cache_clear()
