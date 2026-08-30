export interface ForceExtensionPoint {
  time_ps: number
  restraint_center_nm: number
  end_to_end_nm: number
  extension_nm: number
  force_pn: number
  work_kj_mol: number
  potential_energy_kj_mol: number
}

export interface PairedForceExtension {
  experiment_id: string
  stiffness_unit: string
  baseline: ForceExtensionPoint[]
  damaged: ForceExtensionPoint[]
}

export interface StiffnessFit {
  slope_pn_per_nm: number
  intercept_pn: number
  r_squared: number
  n_points: number
  fit_start_nm: number
  fit_end_nm: number
  reliable: boolean
  unreliable_reasons: string[]
}

export interface ExperimentSummary {
  experiment_id: string
  protein_id: string
  pdb_id: string
  chain_id: string
  scenario_id: string
  status: 'COMPLETED' | 'QC_FAILED'
  severity_label: 'MILD' | 'MODERATE' | 'SEVERE' | 'EXTREME'
  damage_residue_id: string
  residue_type: string
  baseline_stiffness: number | null
  damaged_stiffness: number | null
  stiffness_unit: string
  mechanical_degradation_pct: number | null
  random_seed: number
  is_synthetic: boolean
  qc_failures: string[]
}

export interface ExperimentDetail extends ExperimentSummary {
  schema_version: string
  uniprot_id?: string
  scenario_version?: string
  residue_index_norm?: number
  proxy_type: string
  proxy_rank?: number
  n_residues_damaged: number
  damage_residue_ids: string[]
  n_side_chain_atoms_removed?: number
  severity_is_a_dose: false
  severity_note?: string
  ineligible_candidates: Record<string, unknown>[]
  sim_config_hash: string
  git_commit?: string
  structure_sha256?: string
  damaged_structure_sha256?: string
  fit_quality?: number
  baseline_fit?: StiffnessFit
  damaged_fit?: StiffnessFit
  degradation_definition?: string
  baseline_rmsd_mean?: number
  baseline_rmsd_std?: number
  baseline_rg_mean?: number
  baseline_rg_std?: number
  baseline_contact_mean?: number
  baseline_hbond_mean?: number
  damaged_rmsd_mean?: number
  quality_status: string
  artifacts: Record<string, boolean>
}

export interface ExperimentImportRequest {
  source_path: string
  experiment_id?: string
}

export interface ExperimentImportResponse {
  experiment_id: string
  status: string
  message: string
  detail: ExperimentDetail
}
