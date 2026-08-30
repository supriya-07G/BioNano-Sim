"""Experiment replay and configuration diff (issue #32).

Two questions this answers:

* *"Run that again."* — rebuild a draft request from the stored, immutable
  ``request.json``, so a configuration is reproduced rather than retyped.
* *"Why don't these two results match?"* — a field-by-field diff that says not
  just *what* differs but whether the difference **invalidates the comparison**.

That second distinction is the point of the feature. A different seed and a
different force field are both "a difference", but one is the experiment and
the other means the two numbers should never have been put side by side. A diff
that lists them identically leaves the reader to know which is which, and the
reader usually doesn't.

Replay never touches the source job. It returns a *draft*; starting it is a
separate, explicit act, and the new job records ``replay_of`` so the lineage
survives.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.simulation.presets import get_preset, list_presets
from app.utils.files import read_json

#: Fields a user deliberately varies. A difference here is the experiment.
ISOLATING_FIELDS = (
    "pdb_id", "upload_id", "chain_id", "scenario_id", "random_seed",
    "dose", "dose_unit", "exposure_duration_days", "mechanical_force_pn",
)

#: Fields that change the physics. A difference here means the two results are
#: not measurements of the same thing and must not be ranked against each other.
INVALIDATING_FIELDS = (
    "preset_id", "temperature_kelvin",
)

#: Resolved protocol values inside the stored preset. Same rule as above: if
#: these differ the trajectories are different lengths or different physics.
INVALIDATING_PRESET_FIELDS = (
    "forcefield", "solvent", "nonbonded_cutoff_nm", "timestep_fs",
    "production_steps", "equilibration_steps", "minimisation_steps",
)

#: Provenance-only fields. Recorded, but they do not enter any calculation, so
#: a difference is neither the experiment nor a problem.
PROVENANCE_ONLY_FIELDS = (
    "dose", "dose_unit", "exposure_duration_days", "mechanical_force_pn",
    "scenario_id",
)

_SEVERITY_ORDER = {"identical": 0, "provenance": 1, "isolating": 2,
                   "invalidating": 3}


def _comparable(value: Any) -> Any:
    """Normalise for comparison across the JSON round trip.

    A preset holds ``forcefield`` as a tuple; the same value read back from
    request.json is a list. Comparing them raw reports drift that did not
    happen, and a warning that fires every time is a warning nobody reads.
    """
    if isinstance(value, list | tuple):
        return [_comparable(v) for v in value]
    return value


def _job_dir(job_id: str):
    directory = settings.jobs_dir / job_id
    if not directory.is_dir():
        raise NotFoundError(f"No such experiment: {job_id}", code="JOB_NOT_FOUND")
    return directory


def stored_request(job_id: str) -> dict[str, Any]:
    """The immutable request as submitted. Never rewritten after the job runs."""
    payload = read_json(_job_dir(job_id) / "request.json")
    if not payload:
        raise NotFoundError(
            f"Experiment {job_id} has no stored request, so it cannot be "
            "replayed. Jobs from before request capture are affected.",
            code="NO_STORED_REQUEST",
        )
    return payload


def replay_draft(job_id: str) -> dict[str, Any]:
    """A draft request reproducing an earlier configuration.

    Returns a draft, not a job. Compute is not started here: replaying an
    expensive run must be a deliberate confirmation, not a side effect of
    opening a page.
    """
    original = stored_request(job_id)
    draft = {key: original.get(key) for key in (
        "pdb_id", "upload_id", "chain_id", "scenario_id", "preset_id",
        "temperature_kelvin", "dose", "dose_unit", "exposure_duration_days",
        "mechanical_force_pn", "random_seed",
    )}

    warnings: list[str] = []
    blocking: list[str] = []

    preset_id = draft.get("preset_id")
    # list_presets() returns serialised dicts, not Preset objects.
    available = {p["preset_id"] for p in list_presets()}
    if preset_id not in available:
        blocking.append(
            f"Preset {preset_id!r} no longer exists. It was: "
            f"{(original.get('preset') or {}).get('label', 'unknown')}. "
            "Choose a current preset; the replay will not be an exact "
            "reproduction."
        )
        draft["preset_id"] = None
    else:
        stored_preset = original.get("preset") or {}
        current = get_preset(preset_id)
        drifted = [
            f"{field}: was {stored_preset.get(field)!r}, now "
            f"{getattr(current, field, None)!r}"
            for field in INVALIDATING_PRESET_FIELDS
            if field in stored_preset
            and _comparable(stored_preset.get(field))
            != _comparable(getattr(current, field, None))
        ]
        if drifted:
            warnings.append(
                f"Preset {preset_id!r} has changed since the original run "
                f"({'; '.join(drifted)}). A replay will not reproduce the "
                "original numbers exactly."
            )

    if original.get("upload_id"):
        upload = settings.uploads_dir / str(original["upload_id"])
        if not upload.exists():
            blocking.append(
                f"The uploaded structure {original['upload_id']!r} is no longer "
                "present, so this configuration cannot be replayed. Uploads are "
                "subject to retention; re-upload the structure."
            )

    return {
        "replay_of": job_id,
        "draft": draft,
        "warnings": warnings,
        "blocking": blocking,
        "can_replay": not blocking,
        "requires_confirmation": True,
        "note": (
            "This is a draft. The original experiment is untouched and will "
            "not be overwritten; starting this creates a new job that records "
            "replay_of."
        ),
    }


# --------------------------------------------------------------------------- #
# Configuration diff
# --------------------------------------------------------------------------- #
def _classify(field: str) -> str:
    if field in INVALIDATING_FIELDS or field.startswith("preset."):
        return "invalidating"
    if field in PROVENANCE_ONLY_FIELDS:
        return "provenance"
    return "isolating"


def _explain(field: str, kind: str) -> str:
    if kind == "invalidating":
        return ("This changes the physics or the trajectory length, so the two "
                "results are not measurements of the same thing and must not "
                "be ranked against each other.")
    if kind == "provenance":
        return ("Recorded for provenance only. It does not enter any "
                "calculation, so this difference does not affect the results.")
    return ("A deliberate experimental variable. The difference in results is "
            "what this comparison is measuring.")


def configuration_diff(job_id_a: str, job_id_b: str) -> dict[str, Any]:
    """Every configuration difference between two runs, classified."""
    if job_id_a == job_id_b:
        raise ValidationFailedError(
            "Choose two different experiments to compare.", code="SAME_JOB"
        )

    a, b = stored_request(job_id_a), stored_request(job_id_b)
    preset_a = a.get("preset") or {}
    preset_b = b.get("preset") or {}

    differences: list[dict[str, Any]] = []
    identical: list[str] = []

    for field in (*ISOLATING_FIELDS, *INVALIDATING_FIELDS):
        left, right = a.get(field), b.get(field)
        if left == right:
            identical.append(field)
            continue
        kind = _classify(field)
        differences.append({
            "field": field, "a": left, "b": right,
            "kind": kind, "explanation": _explain(field, kind),
        })

    for field in INVALIDATING_PRESET_FIELDS:
        left, right = preset_a.get(field), preset_b.get(field)
        if left == right:
            identical.append(f"preset.{field}")
            continue
        differences.append({
            "field": f"preset.{field}", "a": left, "b": right,
            "kind": "invalidating",
            "explanation": _explain(f"preset.{field}", "invalidating"),
        })

    invalidating = [d for d in differences if d["kind"] == "invalidating"]
    isolating = [d for d in differences if d["kind"] == "isolating"]
    differences.sort(key=lambda d: -_SEVERITY_ORDER[d["kind"]])

    if invalidating:
        verdict = (
            f"Not directly comparable. {len(invalidating)} setting(s) that "
            f"change the physics differ: "
            f"{', '.join(d['field'] for d in invalidating)}. Re-run both under "
            "one protocol before ranking them."
        )
    elif isolating:
        verdict = (
            "Comparable. The protocol is identical; the runs differ only in "
            f"{', '.join(d['field'] for d in isolating)}, which is the "
            "variable under study."
        )
    else:
        verdict = (
            "Identical configurations. Any difference in results is run-to-run "
            "stochastic variation, not an effect."
        )

    return {
        "job_a": job_id_a,
        "job_b": job_id_b,
        "comparable": not invalidating,
        "verdict": verdict,
        "differences": differences,
        "identical_fields": sorted(identical),
        "counts": {
            "invalidating": len(invalidating),
            "isolating": len(isolating),
            "provenance": sum(1 for d in differences if d["kind"] == "provenance"),
        },
    }
