#!/usr/bin/env python
"""Fetch missing approved structures and regenerate derived data files.

Safe to re-run: existing files are left alone unless ``--force`` is given.

    python scripts/setup_local.py
    python scripts/setup_local.py --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path
import sys

# scripts/ is not a package, so the shared console helper is imported by
# path. init_console() must run before any output is written.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import init_console  # noqa: E402

init_console()

REPO = Path(__file__).resolve().parents[1]
RCSB = "https://files.rcsb.org/download/{pdb_id}.pdb"

APPROVED = {
    "1TIT": {
        "name": "Titin I27 domain",
        "uniprot": "Q8WZ42",
        "proposed_role": "Molecular spring / force-bearing element",
        "why_selected": (
            "The I27 immunoglobulin domain is the canonical single-molecule "
            "force-spectroscopy model. Its mechanical unfolding is characterised, "
            "which makes it the natural reference for a protein acting as a "
            "nanoscale spring."
        ),
        "split": "train",
    },
    "1TEN": {
        "name": "Fibronectin type III domain (tenascin)",
        "uniprot": "P24821",
        "proposed_role": "Structural / load-transmitting element",
        "why_selected": (
            "A beta-sandwich FnIII domain widely used as a mechanically stable "
            "scaffold; a candidate structural member in a nanomachine frame."
        ),
        "split": "test",
    },
    "2SPC": {
        "name": "Spectrin repeat",
        "uniprot": "P13395",
        "proposed_role": "Elastic linker",
        "why_selected": (
            "Spectrin's triple-helical coiled-coil repeat is the archetypal "
            "compliant, extensible linker, giving a contrasting mechanical class to "
            "the beta-rich domains."
        ),
        "split": "train",
    },
    "1UBQ": {
        "name": "Ubiquitin",
        "uniprot": "P0CG48",
        "proposed_role": "Compact switch / sensor body",
        "why_selected": (
            "Small, extremely well characterised and fast to simulate, which is why "
            "it is the Rapid Demo default and the held-out validation protein for "
            "the mock model."
        ),
        "split": "validation",
    },
    "1PGA": {
        "name": "Protein G B1 domain",
        "uniprot": "P06654",
        "proposed_role": "Minimal stable module",
        "why_selected": (
            "At 56 residues it is one of the smallest autonomously folding domains, "
            "useful as a minimal structural unit and the fastest to prepare."
        ),
        "split": "train",
    },
}


def fetch_structures(force: bool) -> list[str]:
    out_dir = REPO / "data" / "proteins" / "pdb"
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched = []
    for pdb_id in APPROVED:
        dest = out_dir / f"{pdb_id}.pdb"
        if dest.exists() and not force:
            print(f"  {pdb_id}: present ({dest.stat().st_size:,} bytes), skipped")
            continue
        url = RCSB.format(pdb_id=pdb_id)
        try:
            body = urllib.request.urlopen(url, timeout=60).read()
        except Exception as exc:  # noqa: BLE001
            print(f"  {pdb_id}: FAILED to download from {url} - {exc}", file=sys.stderr)
            continue
        dest.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()[:16]
        print(f"  {pdb_id}: downloaded {len(body):,} bytes (sha256 {digest}...)")
        fetched.append(pdb_id)
    return fetched


def parse_header(path: Path) -> dict[str, object]:
    text = path.read_text(errors="ignore")
    out: dict[str, object] = {
        "title": None,
        "resolution": None,
        "experiment": None,
        "deposited": None,
        "n_models": 0,
    }
    for line in text.splitlines():
        if line.startswith("TITLE") and out["title"] is None:
            out["title"] = line[10:].strip().title()
        elif line.startswith("EXPDTA") and out["experiment"] is None:
            out["experiment"] = line[10:].strip().title()
        elif "RESOLUTION." in line and out["resolution"] is None:
            match = re.search(r"RESOLUTION\.\s*([\d.]+)", line)
            if match:
                out["resolution"] = float(match.group(1))
        elif line.startswith("HEADER") and out["deposited"] is None:
            match = re.search(r"(\d{2}-[A-Z]{3}-\d{2})", line)
            if match:
                out["deposited"] = match.group(1)
        elif line.startswith("MODEL "):
            out["n_models"] = int(out["n_models"]) + 1
    out["n_models"] = max(int(out["n_models"]), 1)
    return out


def regenerate_metadata() -> None:
    import pandas as pd

    features_csv = REPO / "data" / "ml" / "data" / "public_residue_features.csv"
    if not features_csv.exists():
        print(
            f"  SKIPPED: {features_csv.relative_to(REPO)} is missing, so chain "
            "statistics cannot be taken from the training reference table.",
            file=sys.stderr,
        )
        return
    reference = pd.read_csv(features_csv)

    records = []
    for pdb_id, info in APPROVED.items():
        path = REPO / "data" / "proteins" / "pdb" / f"{pdb_id}.pdb"
        if not path.exists():
            print(f"  {pdb_id}: structure missing, omitted from registry")
            continue
        rows = reference[reference["protein_id"] == pdb_id]
        if rows.empty:
            print(f"  {pdb_id}: no reference features, omitted from registry")
            continue
        header = parse_header(path)
        first = rows.iloc[0]
        records.append(
            {
                "pdb_id": pdb_id,
                "name": info["name"],
                "uniprot": info["uniprot"],
                "proposed_role": info["proposed_role"],
                "why_selected": info["why_selected"],
                "experiment_method": header["experiment"],
                "resolution_angstrom": header["resolution"],
                "deposited": header["deposited"],
                "n_models_in_file": header["n_models"],
                "pdb_title": header["title"],
                "chain_id": str(first["chain_id"]),
                "protein_length": int(first["protein_length"]),
                "molecular_weight": float(first["molecular_weight"]),
                "hydrophobic_fraction": float(first["hydrophobic_fraction"]),
                "charged_fraction": float(first["charged_fraction"]),
                "n_reference_residues": int(len(rows)),
                "ml_dataset_split": info["split"],
                "structure_file": f"{pdb_id}.pdb",
                "source": "RCSB PDB (files.rcsb.org)",
                "license_note": (
                    "PDB coordinate data is distributed by RCSB PDB under CC0 1.0 "
                    "Universal."
                ),
            }
        )

    dest = REPO / "data" / "proteins" / "metadata" / "proteins.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {
                "_comment": (
                    "Generated by scripts/setup_local.py from the PDB headers and "
                    "data/ml/data/public_residue_features.csv. Chain, length and "
                    "composition figures come from the reference feature table the ML "
                    "bundle was trained on, so they match the model exactly."
                ),
                "approved_proteins": records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"  wrote {dest.relative_to(REPO)} ({len(records)} proteins)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="re-download structures that already exist"
    )
    args = parser.parse_args()

    print("BioNano-Sim local setup")
    print("=" * 70)

    print("\n[1] Runtime directories")
    for rel in ("runtime/jobs", "runtime/uploads", "runtime/reports", "runtime/logs"):
        path = REPO / rel
        path.mkdir(parents=True, exist_ok=True)
        (path / ".gitkeep").touch()
        print(f"  {rel}")

    print("\n[2] Approved protein structures (from RCSB PDB)")
    fetch_structures(args.force)

    print("\n[3] Protein registry metadata")
    regenerate_metadata()

    print("\n[4] Feature schema")
    schema_path = REPO / "models" / "feature_schema.json"
    if schema_path.exists() and not args.force:
        print(f"  {schema_path.relative_to(REPO)} present, skipped (use --force)")
    else:
        import subprocess

        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "generate_feature_schema.py")],
            check=False,
        )

    print("\n[5] Molecular viewer bundle")
    viewer = REPO / "frontend" / "public" / "vendor" / "3Dmol-min.js"
    if viewer.exists() and not args.force:
        print(f"  {viewer.relative_to(REPO)} present, skipped (use --force)")
    else:
        import subprocess

        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "fetch_viewer.py")]
            + (["--force"] if args.force else []),
            check=False,
        )

    print("\n" + "=" * 70)
    print("Setup complete. Next: python scripts/validate_environment.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
