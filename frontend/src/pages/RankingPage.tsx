import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Sliders, Sparkles, ShieldCheck, FileSpreadsheet, Braces } from 'lucide-react'

import { PageHeader } from '@/components/layout/PageHeader'
import { CandidateRankingCard } from '@/components/ranking/CandidateRankingCard'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { fetchRankings, RankingWeights } from '@/services/ranking'

export function RankingPage() {
  const [weights, setWeights] = useState<RankingWeights>({
    stiffness_retention: 0.4,
    baseline_strength: 0.3,
    measurement_confidence: 0.3,
    uncertainty_penalty: 0.15,
  })

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['candidates-ranking', weights],
    queryFn: ({ signal }) => fetchRankings(weights, signal),
    staleTime: 5000,
  })

  const handleSliderChange = (key: keyof RankingWeights, value: number) => {
    setWeights((prev) => ({
      ...prev,
      [key]: value,
    }))
  }

  const handleExportJson = () => {
    if (!data) return
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `COSMORA-Ranked-Shortlist-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const handleExportCsv = () => {
    if (!data) return
    const headers = [
      'Rank',
      'PDB_ID',
      'Name',
      'Resolved',
      'Composite_Score',
      'Pareto_Optimal',
      'Baseline_Stiffness_pNnm',
      'Baseline_SD_pNnm',
      'Stiffness_Retained_Pct',
      'Mean_Fit_R2',
      'Runs_Passing_QC',
      'Runs_Screened',
    ]
    const rows = data.candidates.map((c) => [
      c.rank ?? '',
      c.pdb_id,
      `"${c.name}"`,
      c.resolved ? 'YES' : 'NO',
      c.composite_score ?? '',
      c.is_pareto_optimal ? 'YES' : 'NO',
      c.baseline_stiffness_pnnm ?? '',
      c.baseline_stiffness_sd ?? '',
      c.stiffness_retained_pct ?? '',
      c.mean_fit_quality ?? '',
      c.runs_passing_qc,
      c.runs_screened,
    ])
    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `COSMORA-Ranked-Shortlist-${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-8 p-4 sm:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-hairline pb-4">
        <div>
          <PageHeader
            title="Multi-objective candidate ranking"
            description="Rank protein mechanical components on measured steered-MD results: stiffness retention, pristine strength, fit quality and seed spread."
          />
        </div>

        {/* Export & Mode Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleExportJson}
            disabled={!data}
            className="flex items-center gap-1.5 rounded-lg border border-hairline bg-elevated px-3 py-1.5 text-xs font-semibold text-ink hover:bg-raised transition-colors disabled:opacity-50"
          >
            <Braces className="h-4 w-4 text-accent" />
            <span>Export Shortlist (JSON)</span>
          </button>
          <button
            onClick={handleExportCsv}
            disabled={!data}
            className="flex items-center gap-1.5 rounded-lg border border-hairline bg-elevated px-3 py-1.5 text-xs font-semibold text-ink hover:bg-raised transition-colors disabled:opacity-50"
          >
            <FileSpreadsheet className="h-4 w-4 text-accent" />
            <span>Export Shortlist (CSV)</span>
          </button>
        </div>
      </div>

      {/* Scientific Mode Banner */}
      {data && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-hairline/80 bg-surface px-4 py-3 shadow-xs">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="h-5 w-5 shrink-0 text-emerald-500" aria-hidden />
            <div>
              <p className="text-xs font-bold text-ink">
                {data.ranked_candidates} of {data.total_candidates} candidates have a usable
                measurement
              </p>
              <p className="text-2xs text-ink-muted">
                {data.dataset.runs_passing_qc} of {data.dataset.runs_screened} runs across{' '}
                {data.dataset.proteins_screened} domains passed the dataset quality gate.
                Source: <span className="font-mono">{data.dataset.source_file}</span>
              </p>
            </div>
          </div>
          {data.pareto_frontier_ids.length > 0 && (
            <div className="flex items-center gap-2 text-2xs text-ink-muted">
              <Sparkles className="h-3.5 w-3.5 text-amber-500" aria-hidden />
              <span>Pareto frontier: </span>
              <span className="font-mono font-bold text-amber-500">
                {data.pareto_frontier_ids.join(', ')}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Main Grid: Controls Left, Candidate Cards Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Interactive Weights Panel */}
        <div className="lg:col-span-4 space-y-4">
          <div className="rounded-2xl border border-hairline bg-surface p-5 shadow-xs sticky top-20">
            <div className="flex items-center gap-2 border-b border-hairline pb-3 mb-4">
              <Sliders className="h-4 w-4 text-accent" />
              <h2 className="text-sm font-bold text-ink">Objective Weight Controls</h2>
            </div>

            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs font-semibold text-ink mb-1">
                  <span>Stiffness Retention (Δk)</span>
                  <span className="font-mono text-accent">{(weights.stiffness_retention * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={weights.stiffness_retention}
                  onChange={(e) => handleSliderChange('stiffness_retention', parseFloat(e.target.value))}
                  className="w-full accent-accent cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold text-ink mb-1">
                  <span>Baseline Strength (pN/nm)</span>
                  <span className="font-mono text-accent">{(weights.baseline_strength * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={weights.baseline_strength}
                  onChange={(e) => handleSliderChange('baseline_strength', parseFloat(e.target.value))}
                  className="w-full accent-accent cursor-pointer"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold text-ink mb-1">
                  <span>Measurement confidence (R²)</span>
                  <span className="font-mono text-accent">{(weights.measurement_confidence * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={weights.measurement_confidence}
                  onChange={(e) => handleSliderChange('measurement_confidence', parseFloat(e.target.value))}
                  className="w-full accent-accent cursor-pointer"
                />
              </div>

              <div className="hairline-divider my-2" />

              <div>
                <div className="flex justify-between text-xs font-semibold text-ink mb-1">
                  <span>Uncertainty Penalty (σ)</span>
                  <span className="font-mono text-amber-500">{(weights.uncertainty_penalty * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={weights.uncertainty_penalty}
                  onChange={(e) => handleSliderChange('uncertainty_penalty', parseFloat(e.target.value))}
                  className="w-full accent-amber-500 cursor-pointer"
                />
              </div>

            </div>

            {/*
              Two sliders used to sit here -- SASA preservation and an
              out-of-domain distance -- alongside a "mock demo mode" checkbox.
              None of the three changed a number: the values behind them were
              constants, and the checkbox only swapped a banner label. A control
              that does nothing is worse than a missing one.
            */}
            <p className="mt-5 border-t border-hairline/60 pt-3 text-2xs leading-relaxed text-ink-faint">
              Weights are renormalised over the three positive objectives, so moving one
              changes the balance rather than the total.
            </p>
          </div>
        </div>

        {/* Right Column: Ranked Candidate List */}
        <div className="lg:col-span-8 space-y-4">
          {isLoading && <LoadingState label="Calculating Multi-Objective Candidate Scores…" />}

          {isError && (
            <ErrorState
              error={error}
              title="Failed to calculate rankings"
              onRetry={() => refetch()}
            />
          )}

          {data && (
            <div className="space-y-4">
              {data.candidates.map((candidate) => (
                <CandidateRankingCard key={candidate.pdb_id} candidate={candidate} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
