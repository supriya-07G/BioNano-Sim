"""Pydantic contract for the paired pristine-vs-damaged mechanical experiment.

This is the integration boundary between the simulation, ML, backend and
dashboard sides (issue #2). Anything a producer writes and a consumer reads is
declared here once, with its units, so neither side has to re-derive the shape
from the other's source.

Two rules shaped these models:

* **Units are part of the type, not a comment.** ``stiffness_unit`` is a literal
  that can only be ``pN/nm``; a producer emitting kJ/mol/nm² fails validation
  rather than silently poisoning a training set by a factor of 1660.
* **A rejected run must say why.** ``status='QC_FAILED'`` with an empty
  ``qc_failures`` is refused. Silent rejection is how unexplained holes appear
  in a dataset weeks later.

Sign convention on degradation is deliberate and is enforced, not assumed:
``(baseline - damaged) / baseline * 100``. A *negative* value means the damaged
construct measured stiffer than the pristine one. That happens, it is physically
real at short pull times, and it must be reported as measured rather than
clamped to zero.

Contract version 1.0 -- matches ``SCHEMA_VERSION`` in
``scripts/run_paired_experiment.py``.
"""

from __future__ import annotations

import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "1.0"

#: Tolerance when re-deriving degradation from the two stiffnesses. Producers
#: round for readability, so an exact comparison would reject valid rows.
DEGRADATION_TOLERANCE_PP = 0.05

StiffnessUnit = Literal["pN/nm"]
ExperimentStatus = Literal["COMPLETED", "QC_FAILED"]
SeverityLabel = Literal["MILD", "MODERATE", "SEVERE", "EXTREME"]
ProxyType = Literal["SIDE_CHAIN_LOSS"]

#: Column order of force_extension.csv, mirroring pulling.CSV_HEADER. Units are
#: fixed by the name: picoseconds, nanometres, piconewtons, kJ/mol.
FORCE_EXTENSION_COLUMNS: tuple[str, ...] = (
    "time_ps",
    "restraint_center_nm",
    "end_to_end_nm",
    "extension_nm",
    "force_pn",
    "work_kj_mol",
    "potential_energy_kj_mol",
)

#: Column order of one stiffness_results_REAL_v1.csv row: the block the ML spec
#: fixed, then the severity block appended after it.
STIFFNESS_CSV_COLUMNS: tuple[str, ...] = (
    "experiment_id", "job_id", "protein_id", "pdb_id", "chain_id", "scenario_id",
    "damage_residue_id", "residue_type", "proxy_type", "proxy_rank", "random_seed",
    "baseline_stiffness", "damaged_stiffness", "stiffness_unit", "fit_quality",
    "sim_config_hash", "git_commit", "status", "is_synthetic",
    "severity_label", "n_residues_damaged", "damage_residue_ids",
    "mechanical_degradation_pct",
)

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ResidueId = Annotated[str, Field(pattern=r"^[A-Za-z0-9]:-?\d+$")]


def check_degradation_arithmetic(
    baseline: float | None, damaged: float | None, stated: float | None
) -> None:
    """Re-derive degradation and refuse a value whose arithmetic disagrees.

    A mismatch means the producer changed the definition, mixed units, or wrote
    the two stiffnesses from different runs. All three silently corrupt a
    training set, so the contract recomputes rather than trusts.

    Shared by the result model and the CSV row: the CSV is what actually feeds
    training, so it must not be the weaker check of the two.
    """
    if stated is None or baseline is None or damaged is None:
        return
    if not all(math.isfinite(v) for v in (baseline, damaged, stated)):
        return
    if baseline == 0:
        return
    expected = (baseline - damaged) / baseline * 100.0
    if abs(expected - stated) > DEGRADATION_TOLERANCE_PP:
        raise ValueError(
            f"mechanical_degradation_pct is {stated:.4f} but "
            f"(baseline - damaged) / baseline * 100 is {expected:.4f} "
            f"(baseline={baseline}, damaged={damaged}); the contract defines "
            "degradation by that formula"
        )


class StiffnessFit(BaseModel):
    """Diagnostics for one linear fit of force against extension.

    Kept separate from the stiffness value so a consumer can judge whether a
    number is worth using without re-reading the curve.
    """

    model_config = ConfigDict(extra="forbid")

    slope_pn_per_nm: float
    intercept_pn: float
    r_squared: Annotated[float, Field(ge=0.0, le=1.0)]
    n_points: Annotated[int, Field(ge=2)]
    fit_start_nm: float
    fit_end_nm: float
    reliable: bool
    unreliable_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> StiffnessFit:
        if self.fit_end_nm <= self.fit_start_nm:
            raise ValueError(
                f"fit interval must be increasing, got "
                f"[{self.fit_start_nm}, {self.fit_end_nm}]"
            )
        # Same rule as the QC status below: an unreliable fit has to say why.
        if not self.reliable and not self.unreliable_reasons:
            raise ValueError(
                "an unreliable fit must list at least one reason in "
                "unreliable_reasons"
            )
        return self


class PairedExperimentResult(BaseModel):
    """One ``result.json``: the paired pristine and damaged run, plus provenance.

    ``extra='allow'`` on purpose. A producer may add fields as the science
    develops, and rejecting a richer file would force lockstep releases across
    four teams. Everything declared here is still required and still checked.
    """

    model_config = ConfigDict(extra="allow")

    # --- Identity -----------------------------------------------------------
    experiment_id: Annotated[str, Field(min_length=1)]
    schema_version: str
    status: ExperimentStatus

    # --- Subject ------------------------------------------------------------
    protein_id: Annotated[str, Field(min_length=1)]
    pdb_id: Annotated[str, Field(min_length=1)]
    chain_id: Annotated[str, Field(min_length=1, max_length=4)]

    # --- Damage -------------------------------------------------------------
    damage_residue_id: ResidueId
    residue_type: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    proxy_type: ProxyType
    severity_label: SeverityLabel
    n_residues_damaged: Annotated[int, Field(ge=1)]
    damage_residue_ids: list[ResidueId]
    severity_is_a_dose: Literal[False]

    # --- Protocol provenance ------------------------------------------------
    random_seed: int
    sim_config_hash: Sha256
    is_synthetic: bool

    # --- Measurement --------------------------------------------------------
    baseline_stiffness: float | None
    damaged_stiffness: float | None
    stiffness_unit: StiffnessUnit
    mechanical_degradation_pct: float | None
    baseline_fit: StiffnessFit | None = None
    damaged_fit: StiffnessFit | None = None

    # --- Quality ------------------------------------------------------------
    qc_failures: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> PairedExperimentResult:
        if self.status == "QC_FAILED" and not self.qc_failures:
            raise ValueError(
                "status is QC_FAILED but qc_failures is empty: a rejected "
                "experiment must record why it was rejected"
            )
        if self.status == "COMPLETED" and self.qc_failures:
            raise ValueError(
                f"status is COMPLETED but {len(self.qc_failures)} qc_failures "
                "were recorded; a run cannot both pass and fail"
            )

        if self.n_residues_damaged != len(self.damage_residue_ids):
            raise ValueError(
                f"n_residues_damaged is {self.n_residues_damaged} but "
                f"damage_residue_ids has {len(self.damage_residue_ids)} entries"
            )
        if self.damage_residue_id not in self.damage_residue_ids:
            raise ValueError(
                f"damage_residue_id {self.damage_residue_id!r} is not present in "
                "damage_residue_ids"
            )

        # A completed run must carry the numbers it exists to produce.
        if self.status == "COMPLETED":
            for name in ("baseline_stiffness", "damaged_stiffness",
                         "mechanical_degradation_pct"):
                value = getattr(self, name)
                if value is None or not math.isfinite(value):
                    raise ValueError(
                        f"status is COMPLETED but {name} is {value!r}; a passing "
                        "experiment must report a finite measurement"
                    )

        self._check_degradation()
        return self

    def _check_degradation(self) -> None:
        check_degradation_arithmetic(
            self.baseline_stiffness, self.damaged_stiffness,
            self.mechanical_degradation_pct,
        )


class StiffnessResultRow(BaseModel):
    """One row of ``stiffness_results_REAL_v1.csv``.

    A flat projection of the result above, which is what the ML side consumes.
    Validating the row separately catches a broken CSV writer even when the
    result.json it came from was fine.
    """

    model_config = ConfigDict(extra="forbid")

    experiment_id: Annotated[str, Field(min_length=1)]
    job_id: str
    protein_id: Annotated[str, Field(min_length=1)]
    pdb_id: str
    chain_id: str
    scenario_id: str
    damage_residue_id: ResidueId
    residue_type: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    proxy_type: ProxyType
    proxy_rank: Annotated[int, Field(ge=1)]
    random_seed: int
    baseline_stiffness: float | None
    damaged_stiffness: float | None
    stiffness_unit: StiffnessUnit
    fit_quality: Annotated[float, Field(ge=0.0, le=1.0)] | None
    sim_config_hash: Sha256
    git_commit: str
    status: ExperimentStatus
    is_synthetic: bool
    severity_label: SeverityLabel
    n_residues_damaged: Annotated[int, Field(ge=1)]
    damage_residue_ids: str
    mechanical_degradation_pct: float | None

    @model_validator(mode="after")
    def _check(self) -> StiffnessResultRow:
        if self.is_synthetic:
            # The whole point of this file is that it is not the mock dataset.
            raise ValueError(
                "is_synthetic must be false in stiffness_results_REAL_v1.csv; "
                "synthetic rows belong in a separate file"
            )
        check_degradation_arithmetic(
            self.baseline_stiffness, self.damaged_stiffness,
            self.mechanical_degradation_pct,
        )
        return self


def validate_result_payload(payload: dict[str, Any]) -> PairedExperimentResult:
    """Validate one ``result.json``. Raises ``pydantic.ValidationError``."""
    return PairedExperimentResult.model_validate(payload)


def validate_stiffness_row(row: dict[str, Any]) -> StiffnessResultRow:
    """Validate one stiffness CSV row. Raises ``pydantic.ValidationError``."""
    return StiffnessResultRow.model_validate(row)
