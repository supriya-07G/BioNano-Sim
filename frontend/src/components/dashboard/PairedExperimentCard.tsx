import { useMemo } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  FileCode,
  FileSpreadsheet,
  FlaskConical,
  ShieldCheck,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import {
  CartesianGrid,
  Legend,
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { experimentKeys, getForceExtension, listExperiments } from '@/services/experiments'
import type { ExperimentSummary, PairedForceExtension } from '@/types/experiment'

/**
 * One real paired run: pristine against damaged, on the same axes.
 *
 * The curve and every number below are fetched from the API, which reads them
 * off the run's own artifacts. This card previously carried an eleven-point
 * array written by hand -- its first five points exactly collinear, its
 * stiffness a quarter of the measured value -- and offered it for download as
 * JSON and CSV. Anyone who plotted the export got a straight line where the
 * real trajectory is thermal noise around a slope.
 *
 * Real steered-MD force is noisy: individual points scatter tens of pN either
 * side of the trend, and some are negative. That is what the measurement looks
 * like, and showing it is the point.
 */

/** Bin width along the extension axis for the displayed trace. */
const BIN_NM = 0.05

interface Binned {
  extension_nm: number
  pristine_force_pn: number | null
  damaged_force_pn: number | null
}

/**
 * Average force into fixed extension bins.
 *
 * The raw series is thousands of timesteps sampled at uneven extensions, which
 * renders as a solid block of ink. Binning keeps the real scatter visible as
 * bin-to-bin variation instead of smoothing it into a fabricated-looking line.
 */
function binByExtension(curve: PairedForceExtension | undefined): Binned[] {
  if (!curve) return []

  const bins = new Map<number, { p: number[]; d: number[] }>()
  const put = (extension: number, force: number, key: 'p' | 'd') => {
    if (!Number.isFinite(extension) || !Number.isFinite(force)) return
    const bin = Math.round(extension / BIN_NM) * BIN_NM
    const entry = bins.get(bin) ?? { p: [], d: [] }
    entry[key].push(force)
    bins.set(bin, entry)
  }

  curve.baseline.forEach((point) => put(point.extension_nm, point.force_pn, 'p'))
  curve.damaged.forEach((point) => put(point.extension_nm, point.force_pn, 'd'))

  const mean = (xs: number[]) =>
    xs.length ? xs.reduce((total, x) => total + x, 0) / xs.length : null

  return [...bins.entries()]
    .sort(([a], [b]) => a - b)
    .map(([extension, entry]) => ({
      extension_nm: Number(extension.toFixed(3)),
      pristine_force_pn: mean(entry.p),
      damaged_force_pn: mean(entry.d),
    }))
}

function download(name: string, body: string, type: string) {
  const url = URL.createObjectURL(new Blob([body], { type }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  URL.revokeObjectURL(url)
}

export function PairedExperimentCard() {
  const experiments = useQuery({
    queryKey: experimentKeys.list(100),
    queryFn: ({ signal }) => listExperiments(100, signal),
  })

  // Prefer a run that passed QC: the card is a worked example, and an example
  // built on a rejected run would misrepresent the dataset.
  const featured: ExperimentSummary | undefined = useMemo(() => {
    const all = experiments.data ?? []
    return all.find((e) => e.status === 'COMPLETED') ?? all[0]
  }, [experiments.data])

  const curve = useQuery({
    queryKey: experimentKeys.forceExtension(featured?.experiment_id ?? ''),
    queryFn: ({ signal }) => getForceExtension(featured!.experiment_id, signal),
    enabled: Boolean(featured?.experiment_id),
  })

  const series = useMemo(() => binByExtension(curve.data), [curve.data])

  if (experiments.isLoading) {
    return (
      <section className="rounded-2xl border border-hairline bg-surface p-5">
        <p className="text-xs text-ink-muted">Loading paired experiment…</p>
      </section>
    )
  }

  if (!featured) {
    return (
      <section className="rounded-2xl border border-hairline bg-surface p-5">
        <h2 className="text-sm font-bold text-ink">Paired mechanical experiment</h2>
        <p className="mt-2 text-xs text-ink-muted">
          No experiments are present in this checkout. Run one from the Simulation Lab, or
          import a completed run, and the paired comparison will appear here.
        </p>
      </section>
    )
  }

  const passed = featured.status === 'COMPLETED'
  const kPristine = featured.baseline_stiffness
  const kDamaged = featured.damaged_stiffness
  const hasStiffness = kPristine !== null && kDamaged !== null
  const absLoss = hasStiffness ? kDamaged! - kPristine! : null
  const pctChange = hasStiffness && kPristine! !== 0 ? (absLoss! / kPristine!) * 100 : null
  // Damage does not reliably reduce stiffness in this dataset; several domains
  // come back marginally stiffer. The sign is read from the data rather than
  // assumed, so the card cannot claim a loss that did not occur.
  const isLoss = absLoss !== null && absLoss < 0

  const handleJson = () => {
    download(
      `${featured.experiment_id}_paired.json`,
      JSON.stringify({ experiment: featured, force_extension: curve.data ?? null }, null, 2),
      'application/json;charset=utf-8;',
    )
  }

  const handleCsv = () => {
    const header = 'extension_nm,pristine_force_pn,damaged_force_pn'
    const rows = series.map(
      (row) =>
        `${row.extension_nm},${row.pristine_force_pn ?? ''},${row.damaged_force_pn ?? ''}`,
    )
    download(
      `${featured.experiment_id}_force_extension.csv`,
      [header, ...rows].join('\n'),
      'text/csv;charset=utf-8;',
    )
  }

  return (
    <section className="space-y-5 rounded-2xl border border-accent/30 bg-surface p-5 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/15 text-accent">
            <FlaskConical className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-bold text-ink">
                Paired mechanical experiment: {featured.pdb_id}
              </h2>
              <span
                className={
                  passed
                    ? 'flex items-center gap-1 rounded-full border border-ok/30 bg-ok/10 px-2.5 py-0.5 text-2xs font-extrabold text-ok'
                    : 'flex items-center gap-1 rounded-full border border-warn/30 bg-warn/10 px-2.5 py-0.5 text-2xs font-extrabold text-warn'
                }
              >
                {passed ? (
                  <CheckCircle2 className="h-3 w-3" aria-hidden />
                ) : (
                  <AlertTriangle className="h-3 w-3" aria-hidden />
                )}
                {featured.status}
              </span>
            </div>
            <p className="tabular font-mono text-2xs text-ink-muted">
              {featured.experiment_id} · seed {featured.random_seed} · damage at{' '}
              {featured.damage_residue_id} ({featured.residue_type})
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleJson}
            disabled={curve.isLoading}
            className="flex items-center gap-1.5 rounded-lg border border-hairline bg-elevated px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-raised disabled:opacity-50"
          >
            <FileCode className="h-3.5 w-3.5 text-accent" aria-hidden />
            <span>JSON</span>
          </button>
          <button
            type="button"
            onClick={handleCsv}
            disabled={curve.isLoading || series.length === 0}
            className="flex items-center gap-1.5 rounded-lg border border-hairline bg-elevated px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:bg-raised disabled:opacity-50"
          >
            <FileSpreadsheet className="h-3.5 w-3.5 text-ok" aria-hidden />
            <span>CSV</span>
          </button>
        </div>
      </div>

      {!passed && featured.qc_failures.length > 0 && (
        <p className="rounded-xl border border-warn/30 bg-warn/5 p-3 text-2xs leading-relaxed text-ink-muted">
          <span className="font-bold text-ink">This run did not pass QC.</span>{' '}
          {featured.qc_failures.join('; ')}. Its stiffness is reported for transparency and
          should not be read as a measurement.
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric
          label="Baseline stiffness (k)"
          value={kPristine}
          unit={featured.stiffness_unit}
          tone="text-accent"
          note="Pristine structure"
        />
        <Metric
          label="Damaged stiffness (k')"
          value={kDamaged}
          unit={featured.stiffness_unit}
          tone="text-warn"
          note="After side-chain removal"
        />
        <div className="space-y-1 rounded-xl border border-hairline/60 bg-elevated/40 p-3.5">
          <div className="text-2xs font-semibold uppercase tracking-wider text-ink-faint">
            Change (Δk)
          </div>
          {absLoss === null ? (
            <div className="text-sm font-bold text-ink-faint">not resolved</div>
          ) : (
            <>
              <div
                className={`flex items-center gap-1 text-lg font-extrabold ${
                  isLoss ? 'text-danger' : 'text-ok'
                }`}
              >
                {isLoss ? (
                  <ArrowDownRight className="h-4 w-4" aria-hidden />
                ) : (
                  <ArrowUpRight className="h-4 w-4" aria-hidden />
                )}
                <span className="tabular">
                  {absLoss.toFixed(1)}{' '}
                  <span className="text-xs font-normal">{featured.stiffness_unit}</span>
                </span>
              </div>
              <div
                className={`tabular text-2xs font-bold ${isLoss ? 'text-danger' : 'text-ok'}`}
              >
                {pctChange !== null ? `${pctChange.toFixed(1)}%` : '—'}{' '}
                {isLoss ? 'stiffness loss' : 'no loss measured'}
              </div>
            </>
          )}
        </div>
        <div className="space-y-1 rounded-xl border border-hairline/60 bg-elevated/40 p-3.5">
          <div className="text-2xs font-semibold uppercase tracking-wider text-ink-faint">
            Damage site
          </div>
          <div className="text-sm font-extrabold text-ink">
            {featured.damage_residue_id} {featured.residue_type}
          </div>
          <div className="text-2xs text-ink-muted">{featured.severity_label} severity</div>
        </div>
      </div>

      <div className="space-y-3 rounded-xl border border-hairline/60 bg-elevated/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-accent" aria-hidden />
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-ink">
              Force-extension, pristine against damaged
            </h3>
          </div>
          <span className="text-2xs text-ink-faint">
            mean force in {BIN_NM} nm bins
          </span>
        </div>

        <div className="h-[14rem] w-full">
          {curve.isLoading ? (
            <p className="text-2xs text-ink-muted">Loading trajectory…</p>
          ) : series.length === 0 ? (
            <p className="text-2xs text-ink-muted">
              No force-extension series is stored for this run.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.15)" />
                <XAxis
                  dataKey="extension_nm"
                  unit=" nm"
                  stroke="#64748b"
                  tick={{ fontSize: 10 }}
                  label={{
                    value: 'Extension (nm)',
                    position: 'insideBottom',
                    offset: -4,
                    fontSize: 10,
                    fill: '#64748b',
                  }}
                />
                <YAxis
                  unit=" pN"
                  stroke="#64748b"
                  tick={{ fontSize: 10 }}
                  label={{
                    value: 'Force (pN)',
                    angle: -90,
                    position: 'insideLeft',
                    fontSize: 10,
                    fill: '#64748b',
                  }}
                />
                <RechartsTooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Legend wrapperStyle={{ fontSize: '10px' }} />
                <Line
                  type="monotone"
                  dataKey="pristine_force_pn"
                  name="Pristine"
                  stroke="#38BDF8"
                  strokeWidth={1.75}
                  dot={false}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="damaged_force_pn"
                  name="Damaged"
                  stroke="#F59E0B"
                  strokeWidth={1.75}
                  strokeDasharray="4 4"
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="grid gap-3 text-xs sm:grid-cols-2">
        <div className="space-y-1 rounded-xl border border-hairline/60 bg-elevated/30 p-3">
          <div className="text-2xs font-bold uppercase tracking-wider text-ink-faint">
            Run provenance
          </div>
          <dl className="space-y-1 text-2xs text-ink-muted">
            <Row label="Scenario" value={featured.scenario_id} />
            <Row label="Random seed" value={String(featured.random_seed)} />
            <Row label="Damage proxy" value={featured.residue_type} />
            <Row label="Synthetic" value={featured.is_synthetic ? 'yes' : 'no'} />
          </dl>
        </div>

        <div className="flex items-start gap-2 rounded-xl border border-accent/20 bg-accent/5 p-3 text-2xs leading-relaxed text-ink-muted">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden />
          <div>
            <span className="font-bold text-ink">These are OpenMM trajectories.</span> The
            curves are steered-MD output for this one run and one seed. Seed-to-seed spread
            in this dataset is wide, so a single pair is an illustration of the protocol, not
            an estimate of the effect. The ML prediction is a separate artefact and is not
            derived from these curves.
          </div>
        </div>
      </div>
    </section>
  )
}

function Metric({
  label,
  value,
  unit,
  tone,
  note,
}: {
  label: string
  value: number | null
  unit: string
  tone: string
  note: string
}) {
  return (
    <div className="space-y-1 rounded-xl border border-hairline/60 bg-elevated/40 p-3.5">
      <div className="text-2xs font-semibold uppercase tracking-wider text-ink-faint">
        {label}
      </div>
      <div className={`tabular text-lg font-extrabold ${tone}`}>
        {value === null ? (
          <span className="text-sm text-ink-faint">not resolved</span>
        ) : (
          <>
            {value.toFixed(1)} <span className="text-xs font-normal text-ink-muted">{unit}</span>
          </>
        )}
      </div>
      <div className="text-2xs text-ink-muted">{note}</div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt>{label}</dt>
      <dd className="truncate font-semibold text-ink">{value}</dd>
    </div>
  )
}
