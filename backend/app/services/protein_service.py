"""Protein registry, structure serving, and upload validation.

Approved proteins are featurised from the reference tables the ML bundle was
trained on. Uploads are featurised from the structure itself and flagged as
approximate — see :mod:`app.ml.preprocessing` for why that distinction matters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import InvalidProteinError, NotFoundError
from app.core.logging import get_logger
from app.core.security import resolve_within, sanitise_filename, validate_pdb_id
from app.ml.feature_schema import FeatureSchema, load_feature_schema
from app.ml.preprocessing import (
    ChainFeatures,
    ResidueRecord,
    featurise_structure,
    rank_candidate_residues,
)

logger = get_logger("COSMORA.services.protein")

RAPID_DEMO_DEFAULT = "1UBQ"

# Residues that are water, ions or common crystallisation additives rather than
# part of the macromolecule. Used only to describe an upload, never to modify it.
_COMMON_HETERO = {"HOH", "WAT", "SO4", "PO4", "GOL", "EDO", "NA", "CL", "MG", "CA", "ZN"}


@dataclass(frozen=True)
class ChainInfo:
    chain_id: str
    n_residues: int
    n_atoms: int
    first_residue: int | None
    last_residue: int | None


@lru_cache
def _registry() -> dict[str, dict[str, Any]]:
    path = settings.protein_metadata_dir / "proteins.json"
    if not path.exists():
        logger.error("Protein metadata missing at %s", path)
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {r["pdb_id"]: r for r in doc.get("approved_proteins", [])}


@lru_cache
def _reference_tables() -> tuple[Any, Any]:
    """The two CSVs the ML bundle was trained from."""
    import pandas as pd

    features = (
        pd.read_csv(settings.residue_features_csv)
        if settings.residue_features_csv.exists()
        else pd.DataFrame()
    )
    ranked = (
        pd.read_csv(settings.ranked_candidates_csv)
        if settings.ranked_candidates_csv.exists()
        else pd.DataFrame()
    )
    return features, ranked


def list_proteins() -> list[dict[str, Any]]:
    out = []
    for pdb_id, rec in _registry().items():
        out.append(
            {
                **{
                    k: rec.get(k)
                    for k in (
                        "pdb_id", "name", "uniprot", "proposed_role", "chain_id",
                        "protein_length", "molecular_weight", "experiment_method",
                        "resolution_angstrom", "ml_dataset_split",
                    )
                },
                "is_rapid_demo_default": pdb_id == RAPID_DEMO_DEFAULT,
            }
        )
    # Rapid Demo default first, then shortest (fastest to simulate).
    out.sort(key=lambda r: (not r["is_rapid_demo_default"], r["protein_length"]))
    return out


def structure_path(pdb_id: str) -> Path:
    """Locate an approved structure file, with traversal protection."""
    safe = validate_pdb_id(pdb_id)
    if safe not in _registry():
        raise NotFoundError(
            f"'{safe}' is not an approved protein. Approved: "
            f"{', '.join(sorted(_registry()))}."
        )
    path = resolve_within(settings.pdb_dir, f"{safe}.pdb")
    if not path.exists():
        raise NotFoundError(
            f"Structure file for {safe} is missing from data/proteins/pdb. "
            "Re-fetch it with scripts/setup_local.py."
        )
    return path


_STANDARD_AA_3 = {
    "ALA", "CYS", "ASP", "GLU", "PHE", "GLY", "HIS", "ILE", "LYS", "LEU",
    "MET", "ASN", "PRO", "GLN", "ARG", "SER", "THR", "VAL", "TRP", "TYR",
}


def _describe_chains_pure_python(pdb_path: Path) -> tuple[list[ChainInfo], int]:
    lines = pdb_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    n_models = max(1, sum(1 for line in lines if line.startswith("MODEL")))

    model_lines: list[str] = []
    for line in lines:
        if line.startswith("ENDMDL"):
            break
        model_lines.append(line)

    chain_residues: dict[str, dict[int, int]] = {}
    chain_has_ca: dict[str, set[int]] = {}

    for line in model_lines:
        if not line.startswith("ATOM"):
            continue
        atom_name = line[12:16].strip()
        res_name = line[17:20].strip()
        chain_id = line[21:22].strip() or "A"
        raw_seq = line[22:26].strip()
        if not raw_seq.isdigit():
            continue
        res_seq = int(raw_seq)

        if res_name not in _STANDARD_AA_3:
            continue

        chain_residues.setdefault(chain_id, {}).setdefault(res_seq, 0)
        chain_residues[chain_id][res_seq] += 1

        if atom_name == "CA":
            chain_has_ca.setdefault(chain_id, set()).add(res_seq)

    chains: list[ChainInfo] = []
    for chain_id, res_map in chain_residues.items():
        ca_seqs = [seq for seq in res_map if seq in chain_has_ca.get(chain_id, set())]
        if not ca_seqs:
            continue
        n_res = len(ca_seqs)
        n_atoms = sum(res_map[seq] for seq in ca_seqs)
        chains.append(
            ChainInfo(
                chain_id=chain_id,
                n_residues=n_res,
                n_atoms=n_atoms,
                first_residue=min(ca_seqs),
                last_residue=max(ca_seqs),
            )
        )

    if not chains:
        raise InvalidProteinError("Structure contains no valid protein chain.")

    return chains, n_models


def describe_chains(pdb_path: Path) -> tuple[list[ChainInfo], int]:
    """Per-chain residue/atom counts from the first model. Returns (chains, n_models)."""
    try:
        from Bio.PDB import PDBParser
        from Bio.PDB.Polypeptide import is_aa

        structure = PDBParser(QUIET=True).get_structure("s", str(pdb_path))
        models = list(structure)
        if not models:
            raise InvalidProteinError("Structure contains no models.")

        chains: list[ChainInfo] = []
        for chain in models[0]:
            residues = [
                r for r in chain
                if r.id[0] == " " and is_aa(r, standard=True) and r.has_id("CA")
            ]
            if not residues:
                continue
            nums = [int(r.id[1]) for r in residues]
            chains.append(
                ChainInfo(
                    chain_id=chain.id,
                    n_residues=len(residues),
                    n_atoms=sum(len(list(r)) for r in residues),
                    first_residue=min(nums),
                    last_residue=max(nums),
                )
            )
        return chains, len(models)
    except ImportError:
        return _describe_chains_pure_python(pdb_path)


# --------------------------------------------------------------------------- #
# Featurisation
# --------------------------------------------------------------------------- #
def reference_chain_features(pdb_id: str, schema: FeatureSchema) -> ChainFeatures:
    """Build features for an approved protein from the training reference table.

    This path is exact: the numbers are literally the rows the model was fitted
    on, so no recomputation error is introduced.
    """
    features_df, _ = _reference_tables()
    if features_df.empty:
        raise NotFoundError(
            "Reference residue feature table is missing "
            "(data/ml/data/public_residue_features.csv)."
        )
    rows = features_df[features_df["protein_id"] == pdb_id]
    if rows.empty:
        raise NotFoundError(f"No reference features recorded for '{pdb_id}'.")

    rows = rows.reset_index(drop=True)
    first = rows.iloc[0]
    susceptibility = schema.susceptibility_by_residue

    records = [
        ResidueRecord(
            residue_id=str(r["residue_id"]),
            chain_id=str(r["chain_id"]),
            seq_num=int(str(r["residue_id"]).split(":")[-1]),
            residue_type=str(r["residue_type"]).upper(),
            residue_index_norm=float(r["residue_index_norm"]),
            residue_sasa_norm=float(r["residue_sasa_norm"]),
            residue_contact_count=float(r["residue_contact_count"]),
            qualitative_susceptibility=str(
                r.get("qualitative_susceptibility")
                or susceptibility.get(str(r["residue_type"]).upper(), "medium")
            ),
        )
        for _, r in rows.iterrows()
    ]

    return ChainFeatures(
        pdb_id=pdb_id,
        chain_id=str(first["chain_id"]),
        protein_length=int(first["protein_length"]),
        molecular_weight=float(first["molecular_weight"]),
        hydrophobic_fraction=float(first["hydrophobic_fraction"]),
        charged_fraction=float(first["charged_fraction"]),
        residues=records,
        source="reference_table",
        warnings=[],
    )


def candidate_residues(
    pdb_id: str, chain: ChainFeatures, schema: FeatureSchema, top_n: int = 10
) -> list[dict[str, Any]]:
    """Ranked candidates: the shipped ranking when available, else recomputed.

    Reusing the shipped ranking for approved proteins guarantees the exact
    ``proxy_rank`` values the model was trained against; the recomputed formula
    is verified to reproduce them but is only needed for uploads.
    """
    _, ranked_df = _reference_tables()
    if not ranked_df.empty and pdb_id in set(ranked_df["protein_id"]):
        rows = (
            ranked_df[ranked_df["protein_id"] == pdb_id]
            .sort_values("proxy_rank")
            .head(top_n)
            .reset_index(drop=True)
        )
        return [
            {
                "residue_id": str(r["residue_id"]),
                "chain_id": str(r["chain_id"]),
                "seq_num": int(str(r["residue_id"]).split(":")[-1]),
                "residue_type": str(r["residue_type"]).upper(),
                "residue_index_norm": float(r["residue_index_norm"]),
                "residue_sasa_norm": float(r["residue_sasa_norm"]),
                "residue_contact_count": float(r["residue_contact_count"]),
                "qualitative_susceptibility": str(r["qualitative_susceptibility"]),
                "inverse_packing": float(r["_inverse_packing"]),
                "susceptibility_score": float(r["_susceptibility_score"]),
                "candidate_score": float(r["_candidate_score"]),
                "proxy_rank": float(r["proxy_rank"]),
                "ranking_source": "reference_table",
            }
            for _, r in rows.iterrows()
        ]

    out = rank_candidate_residues(chain, schema, top_n=top_n)
    for row in out:
        row["ranking_source"] = "recomputed"
    return out


def get_protein_detail(pdb_id: str, top_n: int = 10) -> dict[str, Any]:
    safe = validate_pdb_id(pdb_id)
    rec = _registry().get(safe)
    if rec is None:
        raise NotFoundError(
            f"'{safe}' is not an approved protein. Approved: "
            f"{', '.join(sorted(_registry()))}."
        )

    schema = load_feature_schema()
    path = structure_path(safe)
    chains, n_models = describe_chains(path)
    default_chain = rec.get("chain_id", "A")

    detail = {
        **rec,
        "is_rapid_demo_default": safe == RAPID_DEMO_DEFAULT,
        "n_models_in_file": n_models,
        "chains": [
            {
                "chain_id": c.chain_id,
                "n_residues": c.n_residues,
                "n_atoms": c.n_atoms,
                "first_residue": c.first_residue,
                "last_residue": c.last_residue,
                "is_default": c.chain_id == default_chain,
            }
            for c in chains
        ],
    }

    try:
        chain_features = reference_chain_features(safe, schema)
        detail["feature_source"] = "reference_table"
        detail["candidate_residues"] = candidate_residues(
            safe, chain_features, schema, top_n=top_n
        )
    except NotFoundError as exc:
        logger.warning("Falling back to recomputed features for %s: %s", safe, exc)
        chain_features = featurise_structure(path, default_chain, schema, pdb_id=safe)
        detail["feature_source"] = "recomputed"
        detail["candidate_residues"] = candidate_residues(
            safe, chain_features, schema, top_n=top_n
        )
    return detail


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
def validate_and_store_upload(
    raw: bytes, filename: str, upload_id: str
) -> dict[str, Any]:
    """Validate an uploaded PDB, then persist it under ``runtime/uploads``.

    Checks, in order: extension, size, decodability, PDB record presence,
    parseability, atom/residue caps, and at least one chain with Cα atoms.
    Nothing is written to disk until every check passes.
    """
    safe_name = sanitise_filename(filename)
    warnings: list[str] = []

    if not safe_name.lower().endswith((".pdb", ".ent")):
        raise InvalidProteinError(
            "Only .pdb (or .ent) files are accepted. mmCIF upload is not supported "
            "in this MVP.",
            code="INVALID_FILE_TYPE",
        )
    if not raw:
        raise InvalidProteinError("The uploaded file is empty.", code="EMPTY_FILE")
    if len(raw) > settings.max_upload_bytes:
        raise InvalidProteinError(
            f"File is {len(raw) / 1e6:.2f} MB, above the "
            f"{settings.max_upload_bytes / 1e6:.0f} MB limit.",
            code="FILE_TOO_LARGE",
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
            warnings.append("File was not valid UTF-8; decoded as latin-1.")
        except UnicodeDecodeError as exc:
            raise InvalidProteinError(
                "File is not decodable text, so it is not a PDB file.",
                code="NOT_TEXT",
            ) from exc

    if not any(
        line.startswith(("ATOM  ", "HETATM", "MODEL ", "HEADER", "CRYST1"))
        for line in text.splitlines()
    ):
        raise InvalidProteinError(
            "No ATOM, HETATM or MODEL records found; this does not look like a PDB file.",
            code="NO_PDB_RECORDS",
        )

    atom_lines = [ln for ln in text.splitlines() if ln.startswith("ATOM  ")]
    if not atom_lines:
        raise InvalidProteinError(
            "File contains no ATOM records (only HETATM/other). A protein structure "
            "is required.",
            code="NO_ATOM_RECORDS",
        )
    if len(atom_lines) > settings.max_upload_atoms:
        raise InvalidProteinError(
            f"Structure has {len(atom_lines)} atoms, above the "
            f"{settings.max_upload_atoms} limit for this local MVP.",
            code="TOO_MANY_ATOMS",
        )

    # Parse from a temp path so nothing lands in uploads/ unless it is valid.
    settings.ensure_runtime_dirs()
    tmp_path = settings.uploads_dir / f".{upload_id}.staging.pdb"
    tmp_path.write_text(text, encoding="utf-8", newline="\n")
    try:
        chains, n_models = describe_chains(tmp_path)
        if not chains:
            raise InvalidProteinError(
                "No chain with standard amino-acid residues carrying Cα atoms was "
                "found. Nucleic-acid-only or ligand-only files are not supported.",
                code="NO_PROTEIN_CHAIN",
            )
        total_residues = sum(c.n_residues for c in chains)
        if total_residues > settings.max_upload_residues:
            raise InvalidProteinError(
                f"Structure has {total_residues} residues, above the "
                f"{settings.max_upload_residues} limit for this local MVP.",
                code="TOO_MANY_RESIDUES",
            )

        final_path = resolve_within(settings.uploads_dir, f"{upload_id}.pdb")
        tmp_path.replace(final_path)
    except InvalidProteinError:
        tmp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:  # noqa: BLE001
        tmp_path.unlink(missing_ok=True)
        raise InvalidProteinError(
            f"The file could not be parsed as a PDB structure: "
            f"{type(exc).__name__}: {exc}",
            code="UNPARSEABLE",
        ) from exc

    if n_models > 1:
        warnings.append(
            f"File contains {n_models} models (an NMR ensemble). Only model 1 is used."
        )
    hetero = sorted(
        {
            ln[17:20].strip()
            for ln in text.splitlines()
            if ln.startswith("HETATM") and ln[17:20].strip() not in _COMMON_HETERO
        }
    )
    if hetero:
        warnings.append(
            f"Non-standard HETATM groups present and ignored: {', '.join(hetero[:8])}."
        )
    warnings.append(
        "Features for uploaded structures are recomputed by the COSMORA "
        "extractor. 'residue_sasa_norm' correlates r = 0.93-0.99 with the table the "
        "model was trained on but is not identical, so estimates are less faithful "
        "than for the five approved proteins."
    )
    if len(chains) > 1:
        warnings.append(
            f"{len(chains)} protein chains found; chain '{chains[0].chain_id}' is "
            "selected by default. Features are computed on the chosen chain in "
            "isolation."
        )

    return {
        "upload_id": upload_id,
        "filename": safe_name,
        "size_bytes": len(raw),
        "n_models": n_models,
        "n_atoms": sum(c.n_atoms for c in chains),
        "n_residues": sum(c.n_residues for c in chains),
        "default_chain": chains[0].chain_id,
        "chains": [
            {
                "chain_id": c.chain_id,
                "n_residues": c.n_residues,
                "n_atoms": c.n_atoms,
                "first_residue": c.first_residue,
                "last_residue": c.last_residue,
                "is_default": i == 0,
            }
            for i, c in enumerate(chains)
        ],
        "warnings": warnings,
        "feature_source": "recomputed",
    }


def upload_path(upload_id: str) -> Path:
    from app.core.security import validate_job_id

    safe = validate_job_id(upload_id)  # uploads also use uuid4().hex
    path = resolve_within(settings.uploads_dir, f"{safe}.pdb")
    if not path.exists():
        raise NotFoundError(
            f"Uploaded structure '{safe}' not found. Uploads do not survive "
            "`make clean`; please upload the file again."
        )
    return path


def resolve_structure(
    pdb_id: str | None, upload_id: str | None
) -> tuple[Path, str, str]:
    """Return (path, identifier, kind) for either selection route."""
    if pdb_id:
        safe = validate_pdb_id(pdb_id)
        return structure_path(safe), safe, "approved"
    if upload_id:
        return upload_path(upload_id), upload_id, "upload"
    raise InvalidProteinError("Either pdb_id or upload_id must be supplied.")
