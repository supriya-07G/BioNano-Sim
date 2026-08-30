"""Feature assembly for the ML pipeline.

Two distinct paths, and the difference is scientifically important:

**Approved proteins** are featurised from ``data/ml/data/public_residue_features.csv``
and ``ranked_candidate_residues.csv`` — the exact tables the bundle was trained
on. Fidelity is perfect by construction.

**Uploaded proteins** have no such table, so their features are recomputed here
from the structure. Everything reproduces the reference tables exactly
(``residue_contact_count`` at 8.0 Å Cα, the composition fractions, the candidate
score) *except* ``residue_sasa_norm``, where BioPython's Shrake-Rupley
correlates r = 0.93–0.99 with the reference but is not bit-identical. Upload
predictions therefore carry an explicit approximation warning.

The reverse-engineered formulas live in ``models/feature_schema.json`` under
``derived_feature_formulas`` and are documented in ``docs/model-card.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.core.exceptions import InvalidProteinError
from app.core.logging import get_logger
from app.ml.feature_schema import FeatureSchema

logger = get_logger("COSMORA.ml.preprocessing")

CA_CONTACT_CUTOFF_ANGSTROM = 8.0
SASA_PROBE_RADIUS = 1.40
SASA_N_POINTS = 100
CANDIDATE_TOP_N = 10

# Candidate-score weights, solved exactly from ranked_candidate_residues.csv
# (max |diff| 1.1e-16 across all 50 rows).
W_SASA, W_PACKING, W_SUSCEPTIBILITY = 0.45, 0.30, 0.25

_THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}

# Average residue masses (Da) minus one water, plus a single water for the chain.
# Matches Bio.SeqUtils ProtParam.molecular_weight(), verified to 1e-4 Da against
# the reference table for 1PGA / 1UBQ / 2SPC / 1TIT.
_RESIDUE_MASS = {
    "A": 71.0788, "R": 156.1875, "N": 114.1038, "D": 115.0886, "C": 103.1388,
    "Q": 128.1307, "E": 129.1155, "G": 57.0519, "H": 137.1411, "I": 113.1594,
    "L": 113.1594, "K": 128.1741, "M": 131.1926, "F": 147.1766, "P": 97.1167,
    "S": 87.0782, "T": 101.1051, "W": 186.2132, "Y": 163.1760, "V": 99.1326,
}
_WATER_MASS = 18.0153


@dataclass
class ResidueRecord:
    """One residue's static features."""

    residue_id: str  # "A:42"
    chain_id: str
    seq_num: int
    residue_type: str  # three-letter, e.g. "LYS"
    residue_index_norm: float
    residue_sasa_norm: float
    residue_contact_count: float
    qualitative_susceptibility: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "residue_id": self.residue_id,
            "chain_id": self.chain_id,
            "seq_num": self.seq_num,
            "residue_type": self.residue_type,
            "residue_index_norm": self.residue_index_norm,
            "residue_sasa_norm": self.residue_sasa_norm,
            "residue_contact_count": self.residue_contact_count,
            "qualitative_susceptibility": self.qualitative_susceptibility,
        }


@dataclass
class ChainFeatures:
    """Whole-chain features plus every residue record."""

    pdb_id: str
    chain_id: str
    protein_length: int
    molecular_weight: float
    hydrophobic_fraction: float
    charged_fraction: float
    residues: list[ResidueRecord]
    source: str  # "reference_table" | "recomputed"
    warnings: list[str] = field(default_factory=list)

    def chain_level(self) -> dict[str, float]:
        return {
            "protein_length": float(self.protein_length),
            "molecular_weight": float(self.molecular_weight),
            "hydrophobic_fraction": float(self.hydrophobic_fraction),
            "charged_fraction": float(self.charged_fraction),
        }


# --------------------------------------------------------------------------- #
# Structure-derived featurisation (upload path)
# --------------------------------------------------------------------------- #
def _kept_residues(chain: Any) -> list[Any]:
    """Residues the reference pipeline kept: standard AA, hetflag ' ', has CA.

    The CA requirement is what excludes 1TEN ``A:802`` (an ARG carrying only C
    and O), reconciling a naive 90-residue parse with the reference table's 89.
    """
    kept = []
    for res in chain:
        if res.id[0] != " ":
            continue
        if res.get_resname().upper() not in _THREE_TO_ONE:
            continue
        if not res.has_id("CA"):
            continue
        kept.append(res)
    return kept


def compute_contact_counts(ca_coords: np.ndarray, cutoff: float = CA_CONTACT_CUTOFF_ANGSTROM) -> np.ndarray:
    """Cα–Cα neighbour counts within ``cutoff`` Å, self excluded.

    Vectorised equivalent of the O(N²) loop in ``legacy/build_contact_graph.py``;
    reproduces ``residue_contact_count`` in the reference table exactly (56/56
    for 1PGA, 76/76 for 1UBQ).
    """
    if len(ca_coords) == 0:
        return np.zeros(0, dtype=float)
    d = np.linalg.norm(ca_coords[:, None, :] - ca_coords[None, :, :], axis=-1)
    return ((d <= cutoff).sum(axis=1) - 1).astype(float)


def _min_max(values: np.ndarray) -> np.ndarray:
    """Min-max to [0, 1]; a constant vector maps to all zeros."""
    lo, hi = float(values.min()), float(values.max())
    if hi - lo <= 0.0:
        return np.zeros_like(values, dtype=float)
    return (values - lo) / (hi - lo)


def _featurise_structure_pure_python(
    pdb_path: Path,
    chain_id: str,
    schema: FeatureSchema,
    *,
    pdb_id: str = "UPLOAD",
) -> ChainFeatures:
    from app.analysis.structural_damage import parse_pdb_atoms, compute_sasa

    atoms = parse_pdb_atoms(pdb_path)
    chain_atoms = [a for a in atoms if a.chain_id == chain_id and a.res_name in _THREE_TO_ONE]

    if not chain_atoms:
        raise InvalidProteinError(f"Chain '{chain_id}' not found or contains no standard protein residues.")

    res_ca: dict[int, np.ndarray] = {}
    res_type: dict[int, str] = {}
    for a in chain_atoms:
        if a.name == "CA":
            res_ca[a.res_seq] = a.coord
            res_type[a.res_seq] = a.res_name

    valid_seqs = sorted(res_ca.keys())
    if not valid_seqs:
        raise InvalidProteinError(f"Chain '{chain_id}' contains no standard amino-acid residues with a Cα atom.")

    n = len(valid_seqs)
    seq = "".join(_THREE_TO_ONE[res_type[s]] for s in valid_seqs)

    sasa_res = compute_sasa(chain_atoms, damage_res_seqs=valid_seqs)["per_residue_sasa"]
    raw_sasa = np.array([sasa_res.get(f"{chain_id}:{s}", 0.0) for s in valid_seqs], dtype=float)
    sasa_norm = _min_max(raw_sasa)

    ca_coords = np.array([res_ca[s] * 10.0 for s in valid_seqs], dtype=float)
    contacts = compute_contact_counts(ca_coords)
    susceptibility = schema.susceptibility_by_residue

    records = [
        ResidueRecord(
            residue_id=f"{chain_id}:{seq_num}",
            chain_id=chain_id,
            seq_num=seq_num,
            residue_type=res_type[seq_num],
            residue_index_norm=(i / (n - 1)) if n > 1 else 0.0,
            residue_sasa_norm=float(sasa_norm[i]),
            residue_contact_count=float(contacts[i]),
            qualitative_susceptibility=susceptibility.get(
                res_type[seq_num], "medium"
            ),
        )
        for i, seq_num in enumerate(valid_seqs)
    ]

    mw = sum(_RESIDUE_MASS[c] for c in seq) + _WATER_MASS
    hydro = schema.hydrophobic_set
    charged = schema.charged_set

    return ChainFeatures(
        pdb_id=pdb_id,
        chain_id=chain_id,
        protein_length=n,
        molecular_weight=round(mw, 4),
        hydrophobic_fraction=sum(c in hydro for c in seq) / n,
        charged_fraction=sum(c in charged for c in seq) / n,
        residues=records,
        source="recomputed",
        warnings=[
            "Features were recomputed from the uploaded structure. "
            "'residue_sasa_norm' uses pure Python Shrake-Rupley which correlates "
            "with the reference table the model was trained on but is not identical, "
            "so this estimate is less faithful than one for an approved protein."
        ],
    )


def featurise_structure(
    pdb_path: Path,
    chain_id: str,
    schema: FeatureSchema,
    *,
    pdb_id: str = "UPLOAD",
) -> ChainFeatures:
    """Recompute all static features for one chain of a structure file."""
    try:
        from Bio.PDB import PDBParser
        from Bio.PDB.SASA import ShrakeRupley
    except ImportError:
        return _featurise_structure_pure_python(
            pdb_path, chain_id, schema, pdb_id=pdb_id
        )

    structure = PDBParser(QUIET=True).get_structure(pdb_id, str(pdb_path))
    try:
        model = next(iter(structure))  # first model; NMR files carry many
    except StopIteration as exc:
        raise InvalidProteinError("Structure contains no models.") from exc

    if chain_id not in [c.id for c in model]:
        raise InvalidProteinError(
            f"Chain '{chain_id}' not found. Available chains: "
            f"{', '.join(c.id for c in model) or 'none'}."
        )

    # SASA is computed on the isolated chain so the value does not depend on
    # which other chains happen to be in the file (matches the reference table's
    # per-chain framing).
    for ch in list(model):
        if ch.id != chain_id:
            model.detach_child(ch.id)
    chain = model[chain_id]

    kept = _kept_residues(chain)
    if not kept:
        raise InvalidProteinError(
            f"Chain '{chain_id}' contains no standard amino-acid residues with a "
            "Cα atom."
        )
    keep_ids = {r.id for r in kept}
    for res in list(chain):
        if res.id not in keep_ids:
            chain.detach_child(res.id)

    # Hydrogens are stripped so SASA does not depend on whether the file is an
    # X-ray structure (no H) or an NMR model (explicit H).
    for res in chain:
        for atom in [a for a in res if (a.element == "H" or a.get_name().startswith("H"))]:
            res.detach_child(atom.get_id())

    ShrakeRupley(probe_radius=SASA_PROBE_RADIUS, n_points=SASA_N_POINTS).compute(
        model, level="R"
    )

    kept = _kept_residues(chain)
    n = len(kept)
    seq = "".join(_THREE_TO_ONE[r.get_resname().upper()] for r in kept)
    sasa_norm = _min_max(np.array([float(r.sasa) for r in kept]))
    contacts = compute_contact_counts(
        np.array([r["CA"].get_coord() for r in kept], dtype=float)
    )
    susceptibility = schema.susceptibility_by_residue

    records = [
        ResidueRecord(
            residue_id=f"{chain_id}:{res.id[1]}",
            chain_id=chain_id,
            seq_num=int(res.id[1]),
            residue_type=res.get_resname().upper(),
            # i/(n-1); a single-residue chain degenerates to 0.0
            residue_index_norm=(i / (n - 1)) if n > 1 else 0.0,
            residue_sasa_norm=float(sasa_norm[i]),
            residue_contact_count=float(contacts[i]),
            qualitative_susceptibility=susceptibility.get(
                res.get_resname().upper(), "medium"
            ),
        )
        for i, res in enumerate(kept)
    ]

    mw = sum(_RESIDUE_MASS[c] for c in seq) + _WATER_MASS
    hydro = schema.hydrophobic_set
    charged = schema.charged_set

    return ChainFeatures(
        pdb_id=pdb_id,
        chain_id=chain_id,
        protein_length=n,
        molecular_weight=round(mw, 4),
        hydrophobic_fraction=sum(c in hydro for c in seq) / n,
        charged_fraction=sum(c in charged for c in seq) / n,
        residues=records,
        source="recomputed",
        warnings=[
            "Features were recomputed from the uploaded structure. "
            "'residue_sasa_norm' uses BioPython Shrake-Rupley (probe 1.40 Å, 100 "
            "points) which correlates r = 0.93–0.99 with the reference table the "
            "model was trained on but is not identical, so this estimate is less "
            "faithful than one for an approved protein."
        ],
    )


# --------------------------------------------------------------------------- #
# Candidate ranking (shared by both paths)
# --------------------------------------------------------------------------- #
def rank_candidate_residues(
    features: ChainFeatures, schema: FeatureSchema, top_n: int = CANDIDATE_TOP_N
) -> list[dict[str, Any]]:
    """Rank residues by the training-set candidate score.

    ``candidate_score = 0.45·sasa_norm + 0.30·inverse_packing + 0.25·susceptibility``
    where ``inverse_packing = 1 − contacts / max(contacts)``. Verified exact
    against ``ranked_candidate_residues.csv``.
    """
    if not features.residues:
        return []

    contacts = np.array([r.residue_contact_count for r in features.residues])
    max_contacts = float(contacts.max())
    score_map = schema.susceptibility_score_map

    scored = []
    for rec in features.residues:
        inverse_packing = (
            1.0 - (rec.residue_contact_count / max_contacts) if max_contacts > 0 else 1.0
        )
        susceptibility_score = score_map.get(rec.qualitative_susceptibility, 0.6)
        score = (
            W_SASA * rec.residue_sasa_norm
            + W_PACKING * inverse_packing
            + W_SUSCEPTIBILITY * susceptibility_score
        )
        scored.append(
            {
                **rec.as_dict(),
                "inverse_packing": inverse_packing,
                "susceptibility_score": susceptibility_score,
                "candidate_score": score,
            }
        )

    # Ties broken by residue number so the ranking is deterministic.
    scored.sort(key=lambda d: (-d["candidate_score"], d["seq_num"]))
    for rank, row in enumerate(scored[:top_n], start=1):
        row["proxy_rank"] = float(rank)
    return scored[:top_n]


def build_feature_frame(
    chain: ChainFeatures,
    candidates: list[dict[str, Any]],
    *,
    scenario_id: str,
    radiation_class: str,
    environment: str,
    proxy_type: str,
    schema: FeatureSchema,
):
    """Assemble the DataFrame the pipeline consumes: one row per candidate.

    Columns are emitted in ``schema.feature_order`` because the bundled
    ColumnTransformer selects by name but the estimator was fitted on a fixed
    column order.
    """
    import pandas as pd

    chain_level = chain.chain_level()
    rows = [
        {
            **chain_level,
            "residue_index_norm": c["residue_index_norm"],
            "residue_sasa_norm": c["residue_sasa_norm"],
            "residue_contact_count": c["residue_contact_count"],
            "proxy_rank": c["proxy_rank"],
            "residue_type": c["residue_type"],
            "qualitative_susceptibility": c["qualitative_susceptibility"],
            "scenario_id": scenario_id,
            "radiation_class": radiation_class,
            "environment": environment,
            "proxy_type": proxy_type,
        }
        for c in candidates
    ]
    return pd.DataFrame(rows, columns=schema.feature_order)
