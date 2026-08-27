import { CHART_COLOURS, ChartShell, TimeSeriesChart } from './ChartShell'
import type { SeriesPoint } from '@/types/simulation'

export function EnergyChart({
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
      title="Potential energy"
      unit="kJ/mol"
      className={className}
      height={height}
      isEmpty={!data || data.length === 0}
      emptyMessage="No dynamics were run, so no energy series was recorded."
      help={
        'Potential energy of the whole system, sampled by the OpenMM reporter. It ' +
        'drops steeply during minimisation, then rises as velocities are assigned ' +
        'and settles into a fluctuating plateau once the thermostat takes hold. A ' +
        'flat, noisy plateau is the sign of a stable run. A steady downward or upward ' +
        'drift during production means the system has not equilibrated - expected ' +
        'here, since the trajectory is only picoseconds long. Absolute values are ' +
        'not comparable between proteins of different size.'
      }
    >
      <TimeSeriesChart data={data ?? []} colour={CHART_COLOURS.warn} unit="kJ/mol" />
    </ChartShell>
  )
}

export function TemperatureChart({
  data,
  setpoint,
  className,
  height,
}: {
  data: SeriesPoint[] | undefined
  setpoint?: number | null
  className?: string
  height?: number
}) {
  return (
    <ChartShell
      title="Temperature"
      unit="K"
      className={className}
      height={height}
      isEmpty={!data || data.length === 0}
      emptyMessage="No dynamics were run, so no temperature series was recorded."
      help={
        'Instantaneous temperature derived from the system kinetic energy. It climbs ' +
        'from near zero as velocities are assigned, then fluctuates around the ' +
        'thermostat setpoint (dashed line). Wide swings are normal for a small ' +
        'system: with only a few thousand degrees of freedom, statistical ' +
        'fluctuations of tens of kelvin are expected and are not an error. A ' +
        'systematic offset from the setpoint would be.'
      }
    >
      <TimeSeriesChart
        data={data ?? []}
        colour={CHART_COLOURS.danger}
        unit="K"
        referenceY={setpoint ?? null}
        referenceLabel="setpoint"
      />
    </ChartShell>
  )
}
