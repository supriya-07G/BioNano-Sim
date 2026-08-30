/** Types mirroring the /simulations, /reports and /system endpoints. */

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export type JobStage =
  | 'input_validation'
  | 'protein_preparation'
  | 'system_construction'
  | 'energy_minimization'
  | 'equilibration'
  | 'production'
  | 'trajectory_analysis'
  | 'report_generation'

export type StageState = 'pending' | 'active' | 'done' | 'failed' | 'skipped'

export const TERMINAL_STATUSES: readonly JobStatus[] = [
  'completed',
  'failed',
  'cancelled',
]

export function isTerminal(status: JobStatus | undefined): boolean {
  return status !== undefined && TERMINAL_STATUSES.includes(status)
}

export interface SimulationPreset {
  preset_id: string
  label: string
  summary: string
  platform: string
  solvent: string
  forcefield: string[]
  constraints: string | null
  nonbonded_cutoff_nm: number
  production_steps: number
  equilibration_steps: number
  minimisation_steps: number
  timestep_fs: number
  report_interval: number
  friction_per_ps: number
  simulated_time_ps: number
  estimated_runtime_note: string
  is_default: boolean
  /** The exact label results from this preset must carry in the UI. */
  scientific_label: string
  limitations: string[]
  /**
   * Present only on presets that actually pull. The load comes from these
   * values, never from the mechanical_force_pn request field.
   */
  pulling?: {
    spring_constant_kj_mol_nm2: number
    pull_velocity_nm_per_ps: number
  } | null
}

export interface SimulationRequest {
  pdb_id?: string
  upload_id?: string
  chain_id: string
  scenario_id: string
  preset_id: string
  temperature_kelvin: number
  dose: number
  dose_unit: string
  exposure_duration_days: number
  mechanical_force_pn: number
  random_seed: number
  prediction_id?: string | null
  ml_degradation_percent?: number | null
}

export interface StageProgress {
  stage: JobStage
  label: string
  state: StageState
  started_at: string | null
  finished_at: string | null
  detail: string | null
}

export interface SimulationJobSummary {
  job_id: string
  status: JobStatus
  pdb_id: string | null
  upload_id: string | null
  chain_id: string
  scenario_id: string
  preset_id: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  progress: number
  current_stage: JobStage | null
  ml_degradation_percent: number | null
  simulation_degradation_proxy_percent: number | null
  engine: string
  error_code: string | null
  error_message: string | null
}

export interface RetryHint {
  preset_id: string
  label: string
  reason: string
}

export interface SimulationJobDetail extends SimulationJobSummary {
  request: Record<string, unknown>
  stages: StageProgress[]
  steps_completed: number
  steps_total: number
  elapsed_seconds: number
  temperature_kelvin: number | null
  potential_energy_kj_mol: number | null
  log_tail: string[]
  reproducibility: Record<string, unknown>
  warnings: string[]
  retry_hint: RetryHint | null
  artifacts: Record<string, boolean>
}

export interface SeriesPoint {
  x: number
  /** Null marks a gap: non-finite values are nulled rather than dropped. */
  y: number | null
}

export interface RmsfRow {
  residue_index: number
  residue_id: string
  residue_type: string
  rmsf_nm: number
}

export interface MobileResidue {
  rank: number
  residue_id: string
  residue_type: string
  rmsf_nm: number
}

export interface DegradationProxyComponent {
  weight: number
  normalised: number
  contribution_percent: number
  [key: string]: number
}

export interface DegradationProxy {
  percent: number
  label: string
  formula: string
  components: Record<string, DegradationProxyComponent>
  reference_scales: Record<string, unknown>
  caveats: string[]
}

export interface StatSummary {
  min: number | null
  max: number | null
  mean: number | null
  final: number | null
  std: number | null
}

export interface SimulationMetrics {
  preset_id: string
  engine: string
  result_label: string
  dynamics_run: boolean
  n_frames: number
  n_atoms?: number
  n_ca_atoms?: number
  trajectory_reader?: string
  steps_total?: number
  timestep_fs?: number
  report_interval?: number
  simulated_time_ps: number
  requested_temperature_kelvin?: number
  minimisation: {
    potential_energy_before_kj_mol: number
    potential_energy_after_kj_mol: number
    delta_kj_mol: number
    max_iterations: number
  }
  rmsd_nm?: { final: number | null; max: number | null; mean: number | null }
  radius_of_gyration_nm?: {
    initial: number | null
    final: number | null
    relative_change: number | null
  }
  rmsf_nm?: { mean: number | null; max: number | null }
  potential_energy_kj_mol?: {
    initial: number | null
    final: number | null
    mean: number | null
  }
  temperature_kelvin?: { mean: number | null; std: number | null }
  degradation_proxy?: DegradationProxy
}

export interface StabilitySummary {
  verdict: 'stable' | 'mildly_perturbed' | 'perturbed' | 'strongly_perturbed' | 'unknown'
  explanation: string
  threshold_note: string
  rmsd_nm: StatSummary
  radius_of_gyration_nm: StatSummary
  rmsf_nm: StatSummary
  temperature_kelvin: { mean: number | null; std: number | null; n_samples: number }
}

export interface ComparisonBlock {
  ml_degradation_percent: number | null
  ml_label: string
  simulation_degradation_proxy_percent: number | null
  simulation_label: string
  difference_percentage_points: number | null
  agreement: 'close' | 'moderate' | 'divergent' | 'unavailable'
  agreement_note?: string
  interpretation: string
  caveats: string[]
}

export type SeriesKey =
  | 'rmsd'
  | 'radius_of_gyration'
  | 'potential_energy'
  | 'kinetic_energy'
  | 'total_energy'
  | 'temperature'

export interface SimulationResults {
  job_id: string
  status: JobStatus
  engine: string
  /** e.g. 'Rapid OpenMM Simulation' or 'Precomputed OpenMM Result'. */
  result_label: string
  metrics: SimulationMetrics
  series: Partial<Record<SeriesKey, SeriesPoint[]>>
  rmsf: RmsfRow[]
  highest_mobility_residues: MobileResidue[]
  stability_summary: StabilitySummary
  comparison: ComparisonBlock
  metadata: {
    pdb_id: string | null
    upload_id: string | null
    chain_id: string | null
    scenario: Record<string, unknown>
    preset: Partial<SimulationPreset>
    created_at: string | null
    started_at: string | null
    finished_at: string | null
    duration_seconds: number | null
    prediction_id: string | null
    topology: Record<string, unknown>
    engine_notes: string[]
  }
  reproducibility: Record<string, unknown>
  warnings: string[]
  limitations: string[]
}

/** Comparison of two completed jobs. */
export interface CompareMetricRow {
  metric: string
  label: string
  unit: string
  a: number | null
  b: number | null
  delta_b_minus_a: number | null
  more_stable_job_id: string | null
}

export interface CompareBrief {
  job_id: string
  result_label: string
  engine: string
  pdb_id: string | null
  upload_id: string | null
  chain_id: string | null
  scenario_id: string | null
  scenario_label: string | null
  preset_id: string | null
  preset_label: string | null
  simulated_time_ps: number | null
  n_frames: number | null
  duration_seconds: number | null
  finished_at: string | null
  ml_degradation_percent: number | null
  simulation_degradation_proxy_percent: number | null
  final_rmsd_nm: number | null
  max_rmsd_nm: number | null
  mean_rmsf_nm: number | null
  rg_relative_change: number | null
  stability_verdict: string | null
  series: Partial<Record<SeriesKey, SeriesPoint[]>>
  rmsf: RmsfRow[]
}

export interface CompareResponse {
  a: CompareBrief
  b: CompareBrief
  /** False when the two runs used different presets: not a like-for-like ranking. */
  comparable: boolean
  differences: CompareMetricRow[]
  stability_ranking: { rank: number; job_id: string; final_rmsd_nm: number; label: string }[]
  notes: string[]
  interpretation_limits: string[]
}

/** System readiness. */
export interface ComponentReadiness {
  name: string
  ready: boolean
  status: 'ready' | 'degraded' | 'unavailable'
  detail: string
  version: string | null
  remediation: string | null
}

export interface ReadinessResponse {
  ready: boolean
  status: 'ready' | 'degraded' | 'not_ready'
  time_utc: string
  components: ComponentReadiness[]
  counts: Record<string, number>
}

export interface EngineHealth {
  openmm: {
    available: boolean
    version: string | null
    platforms: string[]
    detail: string
    remediation?: string
  }
  mdtraj: { available: boolean; version: string | null; detail: string }
  max_concurrent_jobs: number
  active_jobs: string[]
  trajectory_analysis: string
}
