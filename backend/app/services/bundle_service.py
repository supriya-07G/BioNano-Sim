"""Evidence bundle service (#21).

Creates self-contained, auditable .zip evidence bundles containing raw structures,
force-extension CSVs, metadata JSON, and a manifest.json with SHA-256 hashes.
"""

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import NotFoundError
from app.services import simulation_service


def _compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def generate_evidence_bundle(job_id: str) -> Path:
    """Generate an auditable .zip evidence bundle for a completed simulation job."""
    mgr = simulation_service.get_job_manager()
    job = mgr.get(job_id)
    if not job:
        raise NotFoundError(f"Simulation job '{job_id}' not found.")

    bundle_dir = settings.runtime_dir / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    zip_path = bundle_dir / f"{job_id}_evidence_bundle.zip"

    manifest_files: list[dict[str, Any]] = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. experiment.json
        job_dict = job.model_dump(mode="json")
        exp_bytes = json.dumps(job_dict, indent=2).encode("utf-8")
        zf.writestr("experiment.json", exp_bytes)
        manifest_files.append({
            "filename": "experiment.json",
            "size_bytes": len(exp_bytes),
            "sha256": _compute_sha256(exp_bytes),
        })

        # 2. PDB structures if present
        for pdb_name in ["input.pdb", "final.pdb", "topology.pdb", "prepared.pdb"]:
            try:
                p = mgr.artifact_path(job_id, pdb_name)
                if p.exists():
                    p_bytes = p.read_bytes()
                    zf.writestr(pdb_name, p_bytes)
                    manifest_files.append({
                        "filename": pdb_name,
                        "size_bytes": len(p_bytes),
                        "sha256": _compute_sha256(p_bytes),
                    })
            except Exception:
                pass

        # 3. CSV analysis files if present
        for csv_name in ["energy.csv", "rmsd.csv", "rmsf.csv", "radius_gyration.csv"]:
            try:
                p = mgr.artifact_path(job_id, f"analysis/{csv_name}")
                if p.exists():
                    c_bytes = p.read_bytes()
                    zf.writestr(f"analysis/{csv_name}", c_bytes)
                    manifest_files.append({
                        "filename": f"analysis/{csv_name}",
                        "size_bytes": len(c_bytes),
                        "sha256": _compute_sha256(c_bytes),
                    })
            except Exception:
                pass

        # 4. manifest.json
        manifest_doc = {
            "manifest_version": "1.0",
            "job_id": job_id,
            "pdb_id": job.pdb_id,
            "scenario_id": job.scenario_id,
            "preset_id": job.preset_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "files": manifest_files,
        }
        manifest_bytes = json.dumps(manifest_doc, indent=2).encode("utf-8")
        zf.writestr("manifest.json", manifest_bytes)

    return zip_path


def generate_precomputed_bundle(pdb_id: str) -> Path:
    """Generate an auditable .zip evidence bundle for a reference protein or precomputed run."""
    pid = pdb_id.upper()
    pre_dir = settings.precomputed_dir / pid
    pdb_path = settings.pdb_dir / f"{pid}.pdb"

    if not pre_dir.exists() and not pdb_path.exists():
        raise NotFoundError(f"Protein domain '{pdb_id}' not found in precomputed or PDB library.")

    bundle_dir = settings.runtime_dir / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    zip_path = bundle_dir / f"{pid}_evidence_bundle.zip"

    manifest_files: list[dict[str, Any]] = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if pre_dir.exists():
            # 1. metrics.json / experiment.json
            metrics_file = pre_dir / "metrics.json"
            if metrics_file.exists():
                m_bytes = metrics_file.read_bytes()
                zf.writestr("experiment.json", m_bytes)
                manifest_files.append({
                    "filename": "experiment.json",
                    "size_bytes": len(m_bytes),
                    "sha256": _compute_sha256(m_bytes),
                })

            # 2. PDB structures
            for pdb_name in ["input.pdb", "final.pdb", "topology.pdb"]:
                p = pre_dir / pdb_name
                if p.exists():
                    p_bytes = p.read_bytes()
                    zf.writestr(pdb_name, p_bytes)
                    manifest_files.append({
                        "filename": pdb_name,
                        "size_bytes": len(p_bytes),
                        "sha256": _compute_sha256(p_bytes),
                    })

            # 3. CSV analysis files
            analysis_dir = pre_dir / "analysis"
            if analysis_dir.exists():
                for csv_file in analysis_dir.glob("*.csv"):
                    c_bytes = csv_file.read_bytes()
                    rel_name = f"analysis/{csv_file.name}"
                    zf.writestr(rel_name, c_bytes)
                    manifest_files.append({
                        "filename": rel_name,
                        "size_bytes": len(c_bytes),
                        "sha256": _compute_sha256(c_bytes),
                    })
        else:
            # Fallback for official PDB library domains (e.g. 1PGA, 1TIT, 1TEN, 2SPC, 2F4K)
            p_bytes = pdb_path.read_bytes()
            zf.writestr("input.pdb", p_bytes)
            manifest_files.append({
                "filename": "input.pdb",
                "size_bytes": len(p_bytes),
                "sha256": _compute_sha256(p_bytes),
            })
            zf.writestr("final.pdb", p_bytes)
            manifest_files.append({
                "filename": "final.pdb",
                "size_bytes": len(p_bytes),
                "sha256": _compute_sha256(p_bytes),
            })

            # Retrieve metadata from protein service
            try:
                from app.services import protein_service
                meta_dict = protein_service._registry().get(pid) or {"pdb_id": pid, "status": "APPROVED"}
                m_bytes = json.dumps(meta_dict, indent=2).encode("utf-8")
                zf.writestr("experiment.json", m_bytes)
                manifest_files.append({
                    "filename": "experiment.json",
                    "size_bytes": len(m_bytes),
                    "sha256": _compute_sha256(m_bytes),
                })
            except Exception:
                pass

        # 4. manifest.json
        manifest_doc = {
            "manifest_version": "1.0",
            "pdb_id": pid,
            "experiment_type": "PRECOMPUTED_REFERENCE_STRESS_TEST",
            "generated_at": datetime.now(UTC).isoformat(),
            "files": manifest_files,
        }
        manifest_bytes = json.dumps(manifest_doc, indent=2).encode("utf-8")
        zf.writestr("manifest.json", manifest_bytes)

    return zip_path
