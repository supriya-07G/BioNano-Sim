/** Types mirroring /model, /scenarios and /predictions. */

export type RiskLevel = 'low' | 'moderate' | 'elevated' | 'high'
export type DoseUnit = 'Gy' | 'mGy' | 'kGy' | 'rad'

export interface DoseUnitOption {
  unit: DoseUnit
  label: string
  to_gray: number
}

export interface ScenarioDefaults {
  dose: number
  dose_unit: DoseUnit
  exposure_duration_days: number
  temperature_kelvin: number
  mechanical_force_pn: number
}

export interface Scenario {
  scenario_id: string
  label: string
  summary: string
  radiation_class: string | null
  environment: string
  particle_group: string | null
  /**
   * False when the scenario is outside the model's trained vocabulary. Those
   * scenarios still simulate, but produce no ML estimate.
   */
  ml_supported: boolean
  ml_unsupported_reason?: string
  defaults: ScenarioDefaults
  notes: string
}

export interface ScenarioProvenance {
  status: string
  statement: string
  ml_coupling: string
  trained_scenarios: string[]
}

export interface ScenariosResponse {
  scenarios: Scenario[]
  dose_units: DoseUnitOption[]
  provenance: ScenarioProvenance
}

export interface HeldOutMetrics {
  split: string
  rows: number
  proteins: string[]
  mae: number
  rmse: number
  r2: number
}

export interface FeatureImportance {
  feature: string
  group: 'numeric' | 'categorical'
  importance: number
}

export interface ModelInfo {
  available: boolean
  status: 'ready' | 'degraded' | 'unavailable'
  model_name: string | null
  model_version: string
  scientific_status: string
  label_source: string | null
  scientifically_validated: boolean
  approved_use: string | null
  created_at_utc: string | null
  bundle_sha256: string | null
  sha256_verified: boolean
  schema_verified: boolean
  load_error: string | null
  warnings: string[]
  target_column: string | null
  feature_order: string[]
  numeric_features: string[]
  categorical_features: string[]
  categorical_vocabulary: Record<string, string[]>
  n_transformed_features: number | null
  supports_uncertainty: boolean
  uncertainty_note: string | null
  validation_metrics: HeldOutMetrics | null
  test_metrics: HeldOutMetrics | null
  train_proteins: string[]
  validation_proteins: string[]
  test_proteins: string[]
  replacement_requirement: string | null
  limitations: string[]
  top_feature_importances: FeatureImportance[]
}

export interface PredictionRequest {
  pdb_id?: string
  upload_id?: string
  chain_id: string
  scenario_id: string
  dose: number
  dose_unit: DoseUnit
  exposure_duration_days: number
  temperature_kelvin: number
  mechanical_force_pn: number
  random_seed: number
  top_n_residues: number
}

export interface ResiduePrediction {
  residue_id: string
  residue_type: string
  proxy_rank: number
  degradation_percent: number
  residue_sasa_norm: number
  residue_contact_count: number
  qualitative_susceptibility: string
  /** False means the one-hot block was all zeros: the estimate is unreliable. */
  residue_type_in_model_vocabulary: boolean
}

export interface PredictionAggregation {
  method: string
  risk_band_basis: string
  explanation: string
  n_residues_predicted: number
  n_residues_used_in_mean: number
  n_residues_excluded_unknown_type: number
  per_residue_min: number
  per_residue_max: number
  per_residue_std: number
  whole_chain_mean_note: string
  exclusion_note?: string
}

export interface PredictionResponse {
  prediction_id: string
  model_version: string
  model_status: string
  degradation_percent: number
  risk_level: RiskLevel
  /** Always null: the bundle exposes no calibrated uncertainty. */
  confidence: number | null
  warnings: string[]
  input_summary: {
    structure: Record<string, unknown>
    scenario: Record<string, unknown>
    used_by_model: Record<string, unknown>
    not_used_by_model: Record<string, unknown>
  }
  residue_predictions: ResiduePrediction[]
  aggregation: PredictionAggregation
  held_out_error: {
    supported: boolean
    note: string
    validation: HeldOutMetrics | null
    test: HeldOutMetrics | null
  }
  /**
   * Spread of the per-residue predictions behind the protein-level figure.
   * Not a confidence interval -- the bundle exposes no calibrated uncertainty,
   * so there is no coverage probability to report and no `confidence_level`.
   */
  prediction_dispersion?: {
    available: boolean
    note: string
    basis?: string
    sd?: number
    min_pct?: number
    max_pct?: number
    mean_pct?: number
    n_residues?: number
  }
  applicability_domain?: {
    classification: 'IN_VOCABULARY' | 'CAUTION' | 'OUT_OF_DOMAIN' | string
    basis: string
    reasons: string[]
    note: string
  }
  /**
   * Closest proteins in the measured dataset by scaled sequence-descriptor
   * distance. No similarity percentage: the distance has no principled mapping
   * onto one. Empty when the queried protein is not itself measured.
   */
  nearest_neighbors?: Array<{
    pdb_id: string
    distance: number
    baseline_stiffness_pnnm: number
    resolved: boolean
  }>
  /** Exact tree SHAP contributions for the top-ranked candidate residue. */
  local_feature_attributions?: Array<{
    feature: string
    value: string | number | null
    contribution: number
    direction: 'increase' | 'decrease'
  }>
  global_feature_importance?: Record<string, number>
  attribution_disclaimer?: string
}
