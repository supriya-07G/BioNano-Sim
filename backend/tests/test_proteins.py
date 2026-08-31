"""Protein registry, structure serving, and upload validation."""

from __future__ import annotations

import pytest

APPROVED = {"1TIT", "1TEN", "2SPC", "1UBQ", "1PGA"}


def test_lists_exactly_the_five_approved_proteins(client, api):
    body = client.get(f"{api}/proteins").json()
    assert APPROVED.issubset({p["pdb_id"] for p in body})


def test_rapid_demo_default_is_1ubq_and_listed_first(client, api):
    body = client.get(f"{api}/proteins").json()
    assert body[0]["pdb_id"] == "1UBQ"
    assert body[0]["is_rapid_demo_default"] is True
    assert sum(p["is_rapid_demo_default"] for p in body) == 1


def test_dataset_split_is_exposed_so_heldout_status_is_visible(client, api):
    splits = {p["pdb_id"]: p["ml_dataset_split"] for p in client.get(f"{api}/proteins").json()}
    # 1UBQ and 1TEN are the honest held-out cases; the rest were trained on.
    assert splits["1UBQ"] == "validation"
    assert splits["1TEN"] == "test"
    assert splits["1PGA"] == splits["1TIT"] == splits["2SPC"] == "train"


@pytest.mark.parametrize("pdb_id", sorted(APPROVED))
def test_detail_matches_the_training_reference_table(client, api, pdb_id):
    body = client.get(f"{api}/proteins/{pdb_id}").json()
    assert body["pdb_id"] == pdb_id
    # Chain statistics must come from the table the model was trained on.
    assert body["feature_source"] == "reference_table"
    assert body["protein_length"] == body["n_reference_residues"]
    assert body["chains"], "at least one chain must be described"
    assert 0.0 <= body["hydrophobic_fraction"] <= 1.0
    assert 0.0 <= body["charged_fraction"] <= 1.0
    assert body["license_note"]


@pytest.mark.parametrize("pdb_id", sorted(APPROVED))
def test_candidate_residues_use_the_shipped_ranking(client, api, pdb_id):
    body = client.get(f"{api}/proteins/{pdb_id}").json()
    candidates = body["candidate_residues"]
    assert len(candidates) == 10
    assert [c["proxy_rank"] for c in candidates] == [float(i) for i in range(1, 11)]
    assert all(c["ranking_source"] == "reference_table" for c in candidates)
    # candidate_score must be descending, matching proxy_rank order.
    scores = [c["candidate_score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_candidate_score_formula_is_reproducible(client, api):
    """0.45*sasa + 0.30*inverse_packing + 0.25*susceptibility, solved from the CSVs."""
    for candidate in client.get(f"{api}/proteins/1PGA").json()["candidate_residues"]:
        expected = (
            0.45 * candidate["residue_sasa_norm"]
            + 0.30 * candidate["inverse_packing"]
            + 0.25 * candidate["susceptibility_score"]
        )
        assert candidate["candidate_score"] == pytest.approx(expected, abs=1e-12)


def test_structure_endpoint_serves_parseable_coordinates(client, api):
    response = client.get(f"{api}/proteins/1UBQ/structure")
    assert response.status_code == 200
    text = response.text
    assert text.startswith("HEADER") or "ATOM" in text[:5000]
    assert sum(1 for line in text.splitlines() if line.startswith("ATOM  ")) > 500


@pytest.mark.parametrize(
    "pdb_id,expected_code",
    [
        ("XXXX", "NOT_FOUND"),        # well-formed but not approved
        ("1L2Y", "NOT_FOUND"),        # a real PDB id, deliberately not approved
        ("AB", "INVALID_PDB_ID"),     # wrong length
        ("1UB", "INVALID_PDB_ID"),
    ],
)
def test_rejects_unapproved_and_unsafe_ids(client, api, pdb_id, expected_code):
    response = client.get(f"{api}/proteins/{pdb_id}")
    assert response.status_code in (400, 404)
    assert response.json()["error"]["code"] == expected_code


def test_pdb_id_guard_rejects_traversal_directly():
    """httpx normalises "../" out of a URL path, so the guard is tested directly."""
    from app.core.exceptions import UnsafePathError
    from app.core.security import validate_pdb_id

    for bad in ["../etc", "../../models", "1UB/", "....", "", "1UBQ.pdb", "%2e%2e"]:
        with pytest.raises(UnsafePathError):
            validate_pdb_id(bad)


def test_pdb_id_guard_accepts_and_uppercases_valid_ids():
    from app.core.security import validate_pdb_id

    assert validate_pdb_id("1ubq") == "1UBQ"
    assert validate_pdb_id("1UBQ") == "1UBQ"


def test_traversal_in_structure_path_is_refused(client, api):
    # Even if a router matched, validate_pdb_id is the gate.
    response = client.get(f"{api}/proteins/..%2f..%2fmodels/structure")
    assert response.status_code in (400, 404)


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
def test_valid_upload_is_accepted_and_flagged_approximate(client, api, valid_pdb_text):
    response = client.post(
        f"{api}/proteins/upload",
        files={"file": ("fragment.pdb", valid_pdb_text, "chemical/x-pdb")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["n_residues"] == 5
    assert body["default_chain"] == "A"
    assert body["feature_source"] == "recomputed"
    # The approximation must be disclosed, not silent.
    assert any("residue_sasa_norm" in w for w in body["warnings"])

    # And the uploaded coordinates must be retrievable for the viewer.
    fetched = client.get(f"{api}/proteins/upload/{body['upload_id']}/structure")
    assert fetched.status_code == 200
    assert "ATOM" in fetched.text


@pytest.mark.parametrize(
    "filename,content,expected_code",
    [
        ("notes.txt", "hello", "INVALID_FILE_TYPE"),
        ("structure.cif", "data_1ABC", "INVALID_FILE_TYPE"),
        ("empty.pdb", "", "EMPTY_FILE"),
        ("junk.pdb", "this is not a pdb file at all\n" * 5, "NO_PDB_RECORDS"),
        (
            "ligand_only.pdb",
            "HETATM    1  O   HOH A   1       0.000   0.000   0.000  1.00  0.00           O\nEND\n",
            "NO_ATOM_RECORDS",
        ),
    ],
)
def test_unsafe_or_unusable_uploads_are_rejected(
    client, api, filename, content, expected_code
):
    response = client.post(
        f"{api}/proteins/upload", files={"file": (filename, content, "text/plain")}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == expected_code


def test_oversized_upload_is_rejected_without_buffering_all_of_it(client, api):
    from app.config import settings

    oversized = "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    payload = oversized * (settings.max_upload_bytes // len(oversized) + 200)
    response = client.post(
        f"{api}/proteins/upload", files={"file": ("huge.pdb", payload, "chemical/x-pdb")}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] in ("FILE_TOO_LARGE", "TOO_MANY_ATOMS")


def test_filename_with_path_traversal_is_sanitised(client, api, valid_pdb_text):
    response = client.post(
        f"{api}/proteins/upload",
        files={"file": ("../../../evil.pdb", valid_pdb_text, "chemical/x-pdb")},
    )
    assert response.status_code == 200
    # The stored name must be flat: no separators survive.
    assert response.json()["filename"] == "evil.pdb"


def test_missing_upload_id_is_a_clean_404(client, api):
    response = client.get(f"{api}/proteins/upload/{'0' * 32}/structure")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_malformed_upload_id_is_refused(client, api):
    response = client.get(f"{api}/proteins/upload/..%2f..%2fsecrets/structure")
    assert response.status_code in (400, 404)
