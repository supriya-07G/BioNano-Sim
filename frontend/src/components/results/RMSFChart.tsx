import { CHART_COLOURS, ChartShell, ResidueBarChart } from './ChartShell'
import type { RmsfRow } from '@/types/simulation'

export function RMSFChart({
  rows,
  meanValue,
  className,
  height,
}: {
  rows: RmsfRow[] | undefined
  meanValue?: number | null
  className?: string
  height?: number
}) {
  const data = (rows ?? []).map((row) => ({
    label: String(row.residue_index),
    value: row.rmsf_nm,
  }))

  return (
    <ChartShell
      title="Per-residue RMSF"
      unit="nm"
      className={className}
      height={height}
      isEmpty={data.length === 0}
      emptyMessage="No trajectory was produced, so per-residue fluctuations are unavailable."
      help={
        'Root-mean-square fluctuation: how much each residue moves about its own ' +
        'average position, after the frames are superposed on the mean structure. ' +
        'This isolates internal flexibility from whole-molecule tumbling. Peaks are ' +
        'normally loops and chain termini - for ubiquitin the C-terminal tail ' +
        '(residues 72-76) dominates, which is exactly what the experimental ' +
        'literature reports. A peak in the middle of a secondary-structure element ' +
        'is more interesting than one at an end.'
      }
    >
      <ResidueBarChart
        data={data}
        colour={CHART_COLOURS.secondary}
        unit="nm"
        meanValue={meanValue}
      />
    </ChartShell>
  )
}
