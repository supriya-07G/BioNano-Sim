"""Unit tests for evidence bundle generator (#21)."""

import json
import zipfile
import pytest

from app.core.exceptions import NotFoundError
from app.services import bundle_service


def test_generate_precomputed_bundle_1ubq():
    zip_path = bundle_service.generate_precomputed_bundle("1UBQ")
    assert zip_path.exists()
    assert zip_path.name.endswith(".zip")

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "experiment.json" in namelist
        assert "final.pdb" in namelist
        assert "input.pdb" in namelist

        # Validate manifest.json
        manifest_bytes = zf.read("manifest.json")
        manifest_doc = json.loads(manifest_bytes.decode("utf-8"))
        assert manifest_doc["manifest_version"] == "1.0"
        assert manifest_doc["pdb_id"] == "1UBQ"
        assert len(manifest_doc["files"]) >= 3

        # Verify SHA-256 hash match for experiment.json
        exp_bytes = zf.read("experiment.json")
        matching = [f for f in manifest_doc["files"] if f["filename"] == "experiment.json"]
        assert len(matching) == 1
        assert matching[0]["sha256"] == bundle_service._compute_sha256(exp_bytes)


def test_generate_bundle_1pga_fallback():
    zip_path = bundle_service.generate_precomputed_bundle("1PGA")
    assert zip_path.exists()
    assert zip_path.name == "1PGA_evidence_bundle.zip"

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "input.pdb" in namelist
        assert "final.pdb" in namelist
        assert "experiment.json" in namelist


def test_generate_precomputed_bundle_nonexistent():
    with pytest.raises(NotFoundError):
        bundle_service.generate_precomputed_bundle("NONEXISTENT999")
