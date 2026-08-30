#!/usr/bin/env python
"""Check that this machine can run COSMORA, and say precisely what is missing.

    python scripts/validate_environment.py
"""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

# scripts/ is not a package, so the shared console helper is imported by
# path. init_console() must run before any output is written.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import init_console  # noqa: E402

init_console()

REPO = Path(__file__).resolve().parents[1]

REQUIRED = [
    ("fastapi", "web framework"),
    ("uvicorn", "ASGI server"),
    ("pydantic", "validation"),
    ("numpy", "numerics"),
    ("pandas", "dataframes"),
    ("sklearn", "ML pipeline (must be 1.7.1)"),
    ("xgboost", "model estimator"),
    ("joblib", "bundle deserialisation"),
    ("Bio", "BioPython, PDB parsing"),
    ("openmm", "molecular dynamics"),
]
OPTIONAL = [("mdtraj", "trajectory analysis (a built-in reader is used if absent)")]

DATA_FILES = [
    "models/COSMORA_mock_model_bundle.pkl",
    "models/model_metadata.json",
    "models/feature_schema.json",
    "models/release_manifest.json",
    "data/scenarios/radiation_scenarios.json",
    "data/proteins/metadata/proteins.json",
    "data/ml/data/public_residue_features.csv",
    "data/ml/data/ranked_candidate_residues.csv",
]
PDB_IDS = ["1TIT", "1TEN", "2SPC", "1UBQ", "1PGA"]

problems: list[str] = []
notes: list[str] = []


def main() -> int:
    print("COSMORA environment check")
    print("=" * 70)

    print(f"\nPython {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info[:2] != (3, 11):
        problems.append(
            f"Python 3.11 is required (found {sys.version_info.major}."
            f"{sys.version_info.minor}). The pinned dependency set does not resolve "
            "on 3.12+; create the venv with: uv venv backend/.venv --python 3.11"
        )

    print("\nRequired packages:")
    for module, purpose in REQUIRED:
        try:
            mod = importlib.import_module(module)
            version = str(getattr(mod, "__version__", "?"))
            print(f"  [ok]      {module:12} {version:20} {purpose}")
            if module == "sklearn" and version != "1.7.1":
                problems.append(
                    f"scikit-learn {version} is installed but the bundle was fitted "
                    "with 1.7.1. Unpickling across minor versions is not guaranteed "
                    "to reproduce the training transforms."
                )
            if module == "numpy" and int(version.split(".")[0]) < 2:
                problems.append(
                    f"NumPy {version} cannot open the bundle, which references "
                    "numpy._core (NumPy 2+ only)."
                )
        except Exception as exc:  # noqa: BLE001
            print(f"  [MISSING] {module:12} {'':20} {purpose}")
            problems.append(f"{module} is not importable ({type(exc).__name__}): {exc}")

    print("\nOptional packages:")
    for module, purpose in OPTIONAL:
        try:
            mod = importlib.import_module(module)
            version = str(getattr(mod, "__version__", "?"))
            print(f"  [ok]      {module:12} {version:20} {purpose}")
        except Exception:  # noqa: BLE001
            print(f"  [absent]  {module:12} {'':20} {purpose}")
            notes.append(f"{module} is absent; a documented fallback is used.")

    print("\nOpenMM platforms:")
    try:
        from openmm import Platform

        names = [
            Platform.getPlatform(i).getName() for i in range(Platform.getNumPlatforms())
        ]
        print(f"  {', '.join(names)}")
        if not ({"CUDA", "OpenCL", "HIP"} & set(names)):
            notes.append(
                "No GPU platform found. Runs will use the CPU platform: the Rapid "
                "Demo takes roughly 80-120 s instead of 15-25 s."
            )
    except Exception as exc:  # noqa: BLE001
        problems.append(f"OpenMM platforms could not be listed: {exc}")

    print("\nData files:")
    for rel in DATA_FILES:
        path = REPO / rel
        if path.exists():
            print(f"  [ok]      {rel} ({path.stat().st_size:,} bytes)")
        else:
            print(f"  [MISSING] {rel}")
            problems.append(f"{rel} is missing. Run: python scripts/setup_local.py")

    print("\nProtein structures:")
    for pdb_id in PDB_IDS:
        path = REPO / "data" / "proteins" / "pdb" / f"{pdb_id}.pdb"
        if path.exists():
            print(f"  [ok]      {pdb_id}.pdb ({path.stat().st_size:,} bytes)")
        else:
            print(f"  [MISSING] {pdb_id}.pdb")
            problems.append(
                f"{pdb_id}.pdb is missing. Run: python scripts/setup_local.py"
            )

    print("\nRuntime directories:")
    for rel in ("runtime/jobs", "runtime/uploads", "runtime/reports", "runtime/logs"):
        path = REPO / rel
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write-probe"
            probe.touch()
            probe.unlink()
            print(f"  [ok]      {rel}")
        except OSError as exc:
            print(f"  [FAIL]    {rel} - {exc}")
            problems.append(f"{rel} is not writable: {exc}")

    print("\nFrontend toolchain:")
    node = shutil.which("node")
    npm = shutil.which("npm")
    print(f"  node: {node or 'NOT FOUND'}")
    print(f"  npm : {npm or 'NOT FOUND'}")
    if not node:
        notes.append("node is not on PATH; the frontend cannot be built or served.")

    print("\n" + "=" * 70)
    if problems:
        print(f"{len(problems)} problem(s) must be fixed:\n")
        for item in problems:
            print(f"  - {item}")
    else:
        print("No blocking problems found.")
    if notes:
        print(f"\n{len(notes)} note(s):\n")
        for item in notes:
            print(f"  - {item}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
