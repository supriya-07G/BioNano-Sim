import { CHART_COLOURS, ChartShell, TimeSeriesChart } from './ChartShell'
import type { SeriesPoint } from '@/types/simulation'

export function RMSDChart({
  data,
  className,
  height,
}: {
  data: SeriesPoint[] | undefined
  className?: string
  height?: number
}) {
  return (
    <ChartShell
      title="Backbone RMSD over time"
      unit="nm"
      className={className}
      height={height}
      isEmpty={!data || data.length === 0}
      emptyMessage="No trajectory was produced, so RMSD is unavailable. A minimisation-only run has no dynamics."
      help={
        'Root-mean-square deviation of the Cα atoms from the first frame, after ' +
        'optimal rigid-body superposition. It answers "how far has the fold moved ' +
        'from where it started". A small stable domain typically settles below ' +
        '0.15 nm; a curve that keeps climbing suggests real rearrangement rather ' +
        'than thermal jitter. Some drift is always present at 300 K, so compare ' +
        'against the no-radiation baseline preset rather than against zero.'
      }
    >
      <TimeSeriesChart
        data={data ?? []}
        colour={CHART_COLOURS.primary}
        unit="nm"
        area
      />
    </ChartShell>
  )
}
