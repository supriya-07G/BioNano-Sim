/** Types mirroring the /proteins endpoints. */

export type MlDatasetSplit = 'train' | 'validation' | 'test'

export interface ChainSummary {
  chain_id: string
  n_residues: number
  n_atoms: number
  first_residue: number | null
  last_residue: number | null
  is_default: boolean
}

export interface ProteinSummary {
  pdb_id: string
  name: string
  uniprot: string | null
  proposed_role: string
  chain_id: string
  protein_length: number
  molecular_weight: number
  experiment_method: string | null
  resolution_angstrom: number | null
  /**
   * Which split of the mock model's data this protein was in. A protein in
   * 'train' will look optimistically accurate; 1UBQ (validation) and 1TEN
   * (test) are the honest held-out cases.
   */
  ml_dataset_split: MlDatasetSplit
  is_rapid_demo_default: boolean
}

export interface CandidateResidue {
  residue_id: string
  chain_id: string
  seq_num: number
  residue_type: string
  residue_index_norm: number
  residue_sasa_norm: number
  residue_contact_count: number
  qualitative_susceptibility: 'high' | 'medium' | 'low'
  inverse_packing: number
  susceptibility_score: number
  candidate_score: number
  proxy_rank: number
  ranking_source: 'reference_table' | 'recomputed'
}

export interface ProteinDetail extends ProteinSummary {
  why_selected: string
  hydrophobic_fraction: number
  charged_fraction: number
  n_reference_residues: number
  deposited: string | null
  pdb_title: string | null
  n_models_in_file: number
  source: string
  license_note: string
  chains: ChainSummary[]
  /** 'reference_table' is exact; 'recomputed' is approximate. */
  feature_source: 'reference_table' | 'recomputed'
  candidate_residues: CandidateResidue[]
}

export interface UploadedProtein {
  upload_id: string
  filename: string
  size_bytes: number
  n_models: number
  chains: ChainSummary[]
  default_chain: string
  n_atoms: number
  n_residues: number
  warnings: string[]
  feature_source: 'recomputed'
  expires_note: string
}

/** Either an approved protein or an uploaded one. */
export type StructureRef =
  | { kind: 'approved'; pdbId: string; chainId: string }
  | { kind: 'upload'; uploadId: string; chainId: string; filename: string }
