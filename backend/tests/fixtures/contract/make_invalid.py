"""Generate the invalid contract fixtures from the single valid one.

Each invalid file differs from valid_minimal.json by exactly one field, so a
test failure points at one rule rather than a soup of them. Regenerate with:

    python backend/tests/fixtures/contract/make_invalid.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VALID = json.loads((HERE / "valid_minimal.json").read_text(encoding="utf-8"))

# filename -> (mutation, the rule it violates)
CASES: dict[str, tuple[dict, str]] = {
    "invalid_wrong_stiffness_unit.json": (
        {"stiffness_unit": "kJ/mol/nm^2"},
        "stiffness_unit must be pN/nm; kJ/mol/nm^2 is out by a factor of ~1660",
    ),
    "invalid_qc_failed_without_reasons.json": (
        {"status": "QC_FAILED", "qc_failures": []},
        "a rejected experiment must record why",
    ),
    "invalid_completed_with_qc_failures.json": (
        {"status": "COMPLETED", "qc_failures": ["baseline fit unreliable"]},
        "a run cannot both pass and fail",
    ),
    "invalid_degradation_arithmetic.json": (
        {"mechanical_degradation_pct": 42.0},
        "stated degradation disagrees with (baseline - damaged) / baseline * 100",
    ),
    "invalid_residue_count_mismatch.json": (
        {"n_residues_damaged": 3},
        "n_residues_damaged disagrees with len(damage_residue_ids)",
    ),
    "invalid_primary_residue_not_in_list.json": (
        {"damage_residue_id": "A:99"},
        "damage_residue_id is not present in damage_residue_ids",
    ),
    "invalid_completed_without_measurement.json": (
        {"baseline_stiffness": None, "mechanical_degradation_pct": None},
        "a passing experiment must report a finite measurement",
    ),
    "invalid_severity_label.json": (
        {"severity_label": "CATASTROPHIC"},
        "severity vocabulary is fixed",
    ),
    "invalid_severity_claimed_as_dose.json": (
        {"severity_is_a_dose": True},
        "severity counts side chains and is never a dose",
    ),
    "invalid_short_config_hash.json": (
        {"sim_config_hash": "abc123"},
        "sim_config_hash must be a full sha256",
    ),
    "invalid_residue_id_format.json": (
        {"damage_residue_id": "74", "damage_residue_ids": ["74"]},
        "residue ids are chain-qualified, e.g. A:74",
    ),
    "invalid_missing_required_field.json": (
        {"__delete__": "proxy_type"},
        "proxy_type is required",
    ),
}


def main() -> None:
    index = {}
    for name, (mutation, why) in CASES.items():
        payload = json.loads(json.dumps(VALID))
        for key, value in mutation.items():
            if key == "__delete__":
                payload.pop(value)
            else:
                payload[key] = value
        (HERE / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        index[name] = why
    (HERE / "invalid_index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(CASES)} invalid fixtures and invalid_index.json")


if __name__ == "__main__":
    main()
