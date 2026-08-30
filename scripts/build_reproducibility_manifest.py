#!/usr/bin/env python
"""Assemble the reproducibility manifest for a release (issue #25).

Provenance already exists, but scattered: the git SHA is in one artifact, the
protocol in another, library versions nowhere durable. Given a report, nobody
could answer "which exact code, structures, model and settings produced this
number?" without reading four files and guessing at the fifth.

This collects all of it into one machine-readable document and, crucially,
**refuses to write a release manifest with holes**. A manifest that silently
omits the model hash is worse than none: it looks like provenance.

Usage:
    python scripts/build_reproducibility_manifest.py
    python scripts/build_reproducibility_manifest.py --release --tag v0.2.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

DEFAULT_OUT = REPO / "models" / "reproducibility_manifest.json"


def show(path: Path) -> str:
    """Repo-relative when possible; absolute otherwise. Never raises."""
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)

#: Every one of these must be present and non-null before a release manifest is
#: written. The list is the answer to "what would I need to reproduce this?"
REQUIRED_FOR_RELEASE = (
    "git.commit",
    "code.contract_version",
    "code.damage_proxy_type",
    "code.damage_proxy_version",
    "environment.python",
    "environment.openmm",
    "environment.forcefield",
    "models.real_bundle_sha256",
    "dataset.manifest_sha256",
    "dataset.rows_accepted",
    "protocol.production_steps",
    "protocol.spring_constant_kj_mol_nm2",
    "protocol.pull_velocity_nm_per_ps",
    "protocol.seeds",
    "structures",
)


def run_git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                             text=True, check=True)
        return out.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def library_versions() -> dict[str, Any]:
    versions: dict[str, Any] = {
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()} {platform.machine()}",
    }
    for name, module in (("openmm", "openmm"), ("mdtraj", "mdtraj"),
                         ("scikit_learn", "sklearn"), ("xgboost", "xgboost"),
                         ("numpy", "numpy"), ("pandas", "pandas")):
        try:
            versions[name] = __import__(module).__version__
        except Exception:  # noqa: BLE001 - a missing library is data, not a crash
            versions[name] = None

    try:
        from openmm import Platform  # noqa: PLC0415

        versions["openmm_platforms"] = [
            Platform.getPlatform(i).getName()
            for i in range(Platform.getNumPlatforms())
        ]
    except Exception:  # noqa: BLE001
        versions["openmm_platforms"] = None
    return versions


def protocol_block() -> dict[str, Any]:
    """The frozen protocol, read from the producer rather than restated here."""
    try:
        from scripts.run_paired_experiment import (  # noqa: PLC0415
            protocol_config, sim_config_hash,
        )

        config = protocol_config()
        config["sim_config_hash"] = sim_config_hash()
        return config
    except Exception as exc:  # noqa: BLE001
        return {"error": f"could not import the protocol: {type(exc).__name__}: {exc}"}


def structure_hashes() -> dict[str, str]:
    pdb_dir = REPO / "data" / "proteins" / "pdb"
    if not pdb_dir.is_dir():
        return {}
    return {p.name: sha256_file(p) or "" for p in sorted(pdb_dir.glob("*.pdb"))}


def dig(payload: dict[str, Any], dotted: str) -> Any:
    node: Any = payload
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def build() -> dict[str, Any]:
    sys.path.insert(0, str(REPO))
    from app.contracts.paired_experiment import CONTRACT_VERSION  # noqa: PLC0415
    from app.simulation.damage import PROXY_TYPE, PROXY_VERSION  # noqa: PLC0415

    dataset_manifest_path = (
        REPO / "data" / "ml" / "stiffness_results_REAL_v1.manifest.json"
    )
    dataset_manifest = (
        json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
        if dataset_manifest_path.is_file() else {}
    )
    protocol = protocol_block()

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": run_git("rev-parse", "HEAD"),
            "branch": run_git("rev-parse", "--abbrev-ref", "HEAD"),
            "describe": run_git("describe", "--tags", "--always"),
            "dirty": bool(run_git("status", "--porcelain")),
        },
        "code": {
            "contract_version": CONTRACT_VERSION,
            "damage_proxy_type": PROXY_TYPE,
            "damage_proxy_version": PROXY_VERSION,
        },
        "environment": library_versions() | {
            "forcefield": protocol.get("forcefield"),
            "solvent_model": protocol.get("solvent_model"),
        },
        "models": {
            "mock_bundle_sha256": sha256_file(
                REPO / "models" / "bionano_mock_model_bundle.pkl"),
            "real_bundle_sha256": sha256_file(
                REPO / "models" / "bionano_real_model_bundle.pkl"),
            "feature_schema_sha256": sha256_file(
                REPO / "models" / "feature_schema.json"),
        },
        "dataset": {
            "file": dataset_manifest.get("dataset_file"),
            "dataset_sha256": dataset_manifest.get("dataset_sha256"),
            "manifest_sha256": sha256_file(dataset_manifest_path),
            "rows_total": dataset_manifest.get("rows_total"),
            "rows_accepted": dataset_manifest.get("rows_accepted"),
            "proteins": dataset_manifest.get("proteins"),
            "sim_config_hashes": dataset_manifest.get("sim_config_hashes"),
        },
        "protocol": protocol | {"seeds": dataset_manifest.get("seeds")},
        "structures": structure_hashes(),
        "protocol_matches_dataset": protocol_match(protocol, dataset_manifest),
    }


def protocol_match(
    protocol: dict[str, Any], dataset_manifest: dict[str, Any]
) -> dict[str, Any]:
    """Does the protocol in this checkout match the one that made the dataset?

    Reported rather than asserted. The committed dataset was produced by the
    Kaggle notebook, which hashes its own protocol dict, so the two hashes are
    not expected to agree today. Recording the mismatch is the honest thing: a
    reader can then see that the local protocol is *not* proof of how those
    rows were made, instead of assuming it is.
    """
    local = protocol.get("sim_config_hash")
    dataset_hashes = dataset_manifest.get("sim_config_hashes") or []
    matches = bool(local) and local in dataset_hashes
    return {
        "matches": matches,
        "local_sim_config_hash": local,
        "dataset_sim_config_hashes": dataset_hashes,
        "note": (
            "Matches: the protocol in this checkout is the one that produced "
            "the dataset." if matches else
            "Does not match. The committed dataset was produced by the Kaggle "
            "notebook, which hashes its own protocol dict, so this checkout's "
            "sim_config_hash is not evidence of how those rows were generated. "
            "Reproduce them from the dataset's own hash, not this one."
        ),
    }


def missing_fields(manifest: dict[str, Any]) -> list[str]:
    absent = []
    for field in REQUIRED_FOR_RELEASE:
        value = dig(manifest, field)
        if value is None or value == [] or value == {}:
            absent.append(field)
    return absent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--release", action="store_true",
                    help="fail if any required provenance is missing")
    ap.add_argument("--tag", default=None, help="release tag to record")
    args = ap.parse_args()

    manifest = build()
    if args.tag:
        manifest["release_tag"] = args.tag

    absent = missing_fields(manifest)
    manifest["provenance_complete"] = not absent
    manifest["provenance_missing"] = absent

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, default=str) + "\n",
                        encoding="utf-8")

    git = manifest["git"]
    print(f"commit       {git['commit']}"
          f"{'  (working tree dirty)' if git['dirty'] else ''}")
    print(f"contract     v{manifest['code']['contract_version']}")
    print(f"damage proxy {manifest['code']['damage_proxy_type']} "
          f"v{manifest['code']['damage_proxy_version']}")
    print(f"openmm       {manifest['environment']['openmm']}")
    print(f"dataset      {manifest['dataset']['rows_accepted']} accepted rows")
    print(f"structures   {len(manifest['structures'])} hashed")
    print(f"manifest     {show(args.out)}")

    if absent:
        print(f"\n{len(absent)} required field(s) missing:")
        for field in absent:
            print(f"  [missing] {field}")
        if args.release:
            print("\nFAIL  refusing to publish a release manifest with holes. "
                  "A manifest that omits provenance is worse than none: it "
                  "looks like provenance.", file=sys.stderr)
            return 1
        print("\nWARN  incomplete; re-run with --release to make this fatal")
        return 0

    if args.release and git["dirty"]:
        print("\nFAIL  the working tree is dirty; a release manifest must "
              "describe committed code", file=sys.stderr)
        return 1

    print("\nOK    provenance complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
