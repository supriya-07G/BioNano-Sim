import { CHART_COLOURS, ChartShell, TimeSeriesChart } from './ChartShell'
import type { SeriesPoint } from '@/types/simulation'

export function RadiusGyrationChart({
  data,
  initialValue,
  className,
  height,
}: {
  data: SeriesPoint[] | undefined
  initialValue?: number | null
  className?: string
  height?: number
}) {
  return (
    <ChartShell
      title="Radius of gyration"
      unit="nm"
      className={className}
      height={height}
      isEmpty={!data || data.length === 0}
      emptyMessage="No trajectory was produced, so radius of gyration is unavailable."
      help={
        'A compactness measure: the root-mean-square distance of the Cα atoms from ' +
        'their centre of mass. A folded domain holds it nearly constant. A sustained ' +
        'rise means the structure is swelling or unfolding; a fall means it is ' +
        'collapsing. The dashed line marks the starting value, so what matters here ' +
        'is the change rather than the absolute number, which scales with chain length.'
      }
    >
      <TimeSeriesChart
        data={data ?? []}
        colour={CHART_COLOURS.tertiary}
        unit="nm"
        referenceY={initialValue ?? null}
        referenceLabel="initial"
      />
    </ChartShell>
  )
}
