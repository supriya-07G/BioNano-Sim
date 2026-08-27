"""Pre-flight validation for a simulation request.

Everything that can be checked cheaply is checked before a job directory is
created, so an invalid request fails fast with an actionable message rather than
dying inside a worker thread three stages later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.exceptions import InvalidSimulationInputError
from app.core.logging import get_logger

logger = get_logger("bionano.simulation.validators")

MIN_RESIDUES = 4
MAX_RESIDUES_RAPID = 400


def openmm_availability() -> dict[str, Any]:
    """Probe OpenMM without letting an import error escape."""
    try:
        import openmm
        from openmm import Platform

        platforms = [
            Platform.getPlatform(i).getName() for i in range(Platform.getNumPlatforms())
        ]
        return {
            "available": True,
            "version": openmm.__version__,
            "platforms": platforms,
            "detail": f"OpenMM {openmm.__version__} with platforms: {', '.join(platforms)}.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "version": None,
            "platforms": [],
            "detail": f"OpenMM is not usable: {type(exc).__name__}: {exc}",
            "remediation": (
                "Install it into the backend virtual environment with "
                "`pip install openmm==8.6.0` (PyPI ships cp311 wheels for Windows, "
                "Linux and macOS)."
            ),
        }


def mdtraj_availability() -> dict[str, Any]:
    try:
        import mdtraj

        return {
            "available": True,
            "version": mdtraj.__version__,
            "detail": f"MDTraj {mdtraj.__version__} available for trajectory analysis.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "version": None,
            "detail": f"MDTraj unavailable ({type(exc).__name__}). "
            "BioNano-Sim falls back to its own NumPy DCD reader, which supplies "
            "every metric the dashboard shows.",
        }


def require_openmm() -> None:
    info = openmm_availability()
    if not info["available"]:
        raise InvalidSimulationInputError(
            info["detail"],
            code="SIMULATION_ENGINE_UNAVAILABLE",
            http_status=503,
            details=[info.get("remediation", "")],
        )


def validate_structure_for_simulation(
    pdb_path: Path, chain_id: str, preset_id: str
) -> dict[str, Any]:
    """Confirm the chain is something the engine can actually build a system from."""
    from app.services.protein_service import describe_chains

    if not pdb_path.exists():
        raise InvalidSimulationInputError(
            f"Structure file not found: {pdb_path.name}", code="STRUCTURE_MISSING"
        )

    try:
        chains, n_models = describe_chains(pdb_path)
    except Exception as exc:  # noqa: BLE001
        raise InvalidSimulationInputError(
            f"The structure could not be parsed: {type(exc).__name__}: {exc}",
            code="STRUCTURE_UNPARSEABLE",
        ) from exc

    available = {c.chain_id: c for c in chains}
    if chain_id not in available:
        raise InvalidSimulationInputError(
            f"Chain '{chain_id}' is not present. Available chains: "
            f"{', '.join(sorted(available)) or 'none'}.",
            code="CHAIN_NOT_FOUND",
        )

    chain = available[chain_id]
    if chain.n_residues < MIN_RESIDUES:
        raise InvalidSimulationInputError(
            f"Chain '{chain_id}' has only {chain.n_residues} residues; at least "
            f"{MIN_RESIDUES} are needed to build a meaningful system.",
            code="CHAIN_TOO_SHORT",
        )
    if chain.n_residues > MAX_RESIDUES_RAPID:
        raise InvalidSimulationInputError(
            f"Chain '{chain_id}' has {chain.n_residues} residues, above the "
            f"{MAX_RESIDUES_RAPID}-residue limit for local rapid presets. This cap "
            "keeps a demo run inside a few minutes on a laptop CPU.",
            code="CHAIN_TOO_LARGE",
        )

    return {
        "chain_id": chain_id,
        "n_residues": chain.n_residues,
        "n_atoms": chain.n_atoms,
        "n_models": n_models,
        "first_residue": chain.first_residue,
        "last_residue": chain.last_residue,
    }


def validate_simulation_request(
    request: Any, pdb_path: Path
) -> tuple[dict[str, Any], list[str]]:
    """Full validation. Returns (structure_info, warnings)."""
    from app.services.prediction_service import get_scenario
    from app.simulation.presets import get_preset

    warnings: list[str] = []
    preset = get_preset(request.preset_id)
    scenario = get_scenario(request.scenario_id)

    if not 100.0 <= request.temperature_kelvin <= 500.0:
        raise InvalidSimulationInputError(
            f"Temperature {request.temperature_kelvin} K is outside the supported "
            "100-500 K range for this MVP. Below ~100 K the implicit-solvent model "
            "and HBonds constraints are not meaningful; above ~500 K the integrator "
            "becomes unstable at a 2 fs timestep.",
            code="TEMPERATURE_OUT_OF_RANGE",
        )
    if request.temperature_kelvin > 400.0:
        warnings.append(
            f"{request.temperature_kelvin} K is far above physiological. Expect large "
            "thermal drift that is not radiation damage."
        )

    structure_info = validate_structure_for_simulation(
        pdb_path, request.chain_id, request.preset_id
    )

    if structure_info["n_models"] > 1:
        warnings.append(
            f"Structure contains {structure_info['n_models']} models; model 1 is used."
        )

    if not scenario.get("ml_supported", False):
        warnings.append(
            f"Scenario '{scenario['scenario_id']}' has no ML degradation estimate "
            "(outside the model's trained vocabulary), so this run has nothing to "
            "compare against. The simulation itself is unaffected."
        )

    if request.mechanical_force_pn > 0:
        warnings.append(
            f"A mechanical force of {request.mechanical_force_pn} pN was recorded for "
            "provenance, but the Rapid Demo engine applies no external pulling force. "
            "Steered MD is future scope."
        )

    if request.dose > 0:
        warnings.append(
            f"A dose of {request.dose} {request.dose_unit} was recorded for provenance. "
            "Standard OpenMM does not model ionising radiation: no particle track, "
            "energy deposition or bond scission is simulated. The trajectory reflects "
            "thermal dynamics at the requested temperature only."
        )

    est_atoms = structure_info["n_atoms"]
    if preset.production_steps > 0 and est_atoms > 1800:
        warnings.append(
            f"{est_atoms} heavy atoms with {preset.production_steps} production steps "
            "may take several minutes on a CPU. Consider the Minimisation-only preset "
            "for a fast check."
        )

    return structure_info, warnings
