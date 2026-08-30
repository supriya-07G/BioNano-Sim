import { useId, useMemo } from 'react'
import type { ReactNode } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { EmptyState } from '@/components/common/EmptyState'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import type { SeriesPoint } from '@/types/simulation'

/** Shared axis/grid styling so every chart in the app reads as one system. */
export const CHART_COLOURS = {
  primary: 'rgb(var(--color-accent))',
  secondary: 'rgb(var(--color-violet))',
  tertiary: 'rgb(var(--color-ok))',
  warn: 'rgb(var(--color-warn))',
  danger: 'rgb(var(--color-danger))',
  grid: 'rgb(var(--color-hairline))',
  axis: 'rgb(var(--color-ink-faint))',
} as const

const AXIS_PROPS = {
  stroke: CHART_COLOURS.axis,
  tick: { fill: CHART_COLOURS.axis, fontSize: 10 },
  tickLine: false,
} as const

/**
 * Injected by ResponsiveContainer, which clones its direct child and passes
 * measured pixel dimensions. A custom wrapper component must forward them to
 * the actual recharts chart, otherwise the chart renders at zero size and
 * produces an empty SVG.
 */
interface InjectedSize {
  width?: number
  height?: number
}

interface ChartShellProps {
  title: string
  help: string
  unit?: string
  children: ReactNode
  actions?: ReactNode
  isEmpty?: boolean
  emptyMessage?: string
  className?: string
  height?: number
  /**
   * What the chart shows, for a screen reader. A recharts SVG exposes no
   * accessible content at all, so without this the chart is silent and the
   * reader learns only that a region exists. State the trend and the range
   * rather than repeating the title.
   */
  summary?: string
}

let chartSequence = 0
const nextChartId = () => `chart-${(chartSequence += 1)}`

export function ChartShell({
  title,
  help,
  unit,
  children,
  actions,
  isEmpty = false,
  emptyMessage = 'No data was produced for this metric.',
  className,
  height = 200,
  summary,
}: ChartShellProps) {
  const headingId = useMemo(nextChartId, [])
  const describedBy = `${headingId}-desc`

  return (
    <section className={cn('card p-3', className)} aria-labelledby={headingId}>
      <header className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <h3 id={headingId} className="text-xs font-medium text-ink">
            {title}
          </h3>
          {unit && <span className="font-mono text-2xs text-ink-faint">({unit})</span>}
          <Tooltip width="lg" content={help} />
        </div>
        {actions}
      </header>

      {/*
        The help text explains the metric and is otherwise reachable only by
        hovering the tooltip, which a keyboard or screen-reader user cannot do.
        Exposing it here makes it available to both without duplicating it
        visually.
      */}
      <p id={describedBy} className="sr-only">
        {summary ? `${summary} ` : ''}
        {help}
        {unit ? ` Values are in ${unit}.` : ''}
      </p>

      {isEmpty ? (
        <EmptyState compact title="Not available" description={emptyMessage} />
      ) : (
        <div
          style={{ height }}
          role="img"
          aria-labelledby={headingId}
          aria-describedby={describedBy}
        >
          <ResponsiveContainer width="100%" height="100%">
            {children as React.ReactElement}
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}

/** Recharts tooltip styled to match the surface palette. */
export function ChartTooltip({
  unit,
  xLabel,
}: {
  unit?: string
  xLabel?: string
}) {
  return (
    <RechartsTooltip
      contentStyle={{
        backgroundColor: 'rgb(var(--color-elevated))',
        border: '1px solid rgb(var(--color-hairline))',
        borderRadius: 8,
        fontSize: 11,
        padding: '6px 10px',
      }}
      labelStyle={{ color: 'rgb(var(--color-ink-muted))', fontSize: 10 }}
      itemStyle={{ color: 'rgb(var(--color-ink))' }}
      labelFormatter={(value) =>
        xLabel ? `${xLabel}: ${Number(value).toFixed(2)}` : String(value)
      }
      formatter={(value: unknown) => [
        `${Number(value).toFixed(4)}${unit ? ` ${unit}` : ''}`,
        '',
      ]}
    />
  )
}

/** A single time series line chart. */
export function TimeSeriesChart({
  data,
  colour = CHART_COLOURS.primary,
  unit,
  xLabel = 'Time (ps)',
  referenceY,
  referenceLabel,
  area = false,
  width,
  height,
}: InjectedSize & {
  data: SeriesPoint[]
  colour?: string
  unit?: string
  xLabel?: string
  referenceY?: number | null
  referenceLabel?: string
  area?: boolean
}) {
  const Chart = area ? AreaChart : LineChart
  const chartId = useId()
  const gradientId = `grad-${chartId.replace(/:/g, '')}`

  return (
    <Chart
      data={data}
      width={width}
      height={height}
      margin={{ top: 4, right: 8, bottom: 2, left: -12 }}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={colour} stopOpacity={0.28} />
          <stop offset="100%" stopColor={colour} stopOpacity={0} />
        </linearGradient>
      </defs>
      <CartesianGrid stroke={CHART_COLOURS.grid} strokeDasharray="3 3" vertical={false} />
      <XAxis
        dataKey="x"
        {...AXIS_PROPS}
        tickFormatter={(value: number) => value.toFixed(0)}
      />
      <YAxis {...AXIS_PROPS} width={52} />
      <ChartTooltip unit={unit} xLabel={xLabel} />
      {referenceY !== null && referenceY !== undefined && (
        <ReferenceLine
          y={referenceY}
          stroke={CHART_COLOURS.axis}
          strokeDasharray="4 4"
          label={{
            value: referenceLabel,
            fill: CHART_COLOURS.axis,
            fontSize: 9,
            position: 'insideTopRight',
          }}
        />
      )}
      {area ? (
        <Area
          type="monotone"
          dataKey="y"
          stroke={colour}
          strokeWidth={1.6}
          fill={`url(#${gradientId})`}
          dot={false}
          connectNulls={false}
        />
      ) : (
        <Line
          type="monotone"
          dataKey="y"
          stroke={colour}
          strokeWidth={1.6}
          dot={false}
          connectNulls={false}
        />
      )}
    </Chart>
  )
}

/** Per-residue bar chart, used for RMSF. */
export function ResidueBarChart({
  data,
  colour = CHART_COLOURS.secondary,
  unit,
  meanValue,
  width,
  height,
}: InjectedSize & {
  data: { label: string; value: number; highlight?: boolean }[]
  colour?: string
  unit?: string
  meanValue?: number | null
}) {
  return (
    <BarChart
      data={data}
      width={width}
      height={height}
      margin={{ top: 4, right: 8, bottom: 2, left: -12 }}
      barCategoryGap={0}
    >
      <CartesianGrid stroke={CHART_COLOURS.grid} strokeDasharray="3 3" vertical={false} />
      <XAxis
        dataKey="label"
        {...AXIS_PROPS}
        interval="preserveStartEnd"
        minTickGap={28}
      />
      <YAxis {...AXIS_PROPS} width={52} />
      <RechartsTooltip
        contentStyle={{
          backgroundColor: 'rgb(var(--color-elevated))',
          border: '1px solid rgb(var(--color-hairline))',
          borderRadius: 8,
          fontSize: 11,
          padding: '6px 10px',
        }}
        labelStyle={{ color: 'rgb(var(--color-ink-muted))', fontSize: 10 }}
        itemStyle={{ color: 'rgb(var(--color-ink))' }}
        formatter={(value: unknown) => [
          `${Number(value).toFixed(4)}${unit ? ` ${unit}` : ''}`,
          'RMSF',
        ]}
      />
      {meanValue !== null && meanValue !== undefined && (
        <ReferenceLine
          y={meanValue}
          stroke={CHART_COLOURS.axis}
          strokeDasharray="4 4"
          label={{
            value: 'mean',
            fill: CHART_COLOURS.axis,
            fontSize: 9,
            position: 'insideTopRight',
          }}
        />
      )}
      <Bar dataKey="value" fill={colour} radius={[1, 1, 0, 0]} />
    </BarChart>
  )
}

/** Two series on shared axes, for comparing runs. */
export function DualSeriesChart({
  seriesA,
  seriesB,
  labelA,
  labelB,
  unit,
  xLabel = 'Time (ps)',
  width,
  height,
}: InjectedSize & {
  seriesA: SeriesPoint[]
  seriesB: SeriesPoint[]
  labelA: string
  labelB: string
  unit?: string
  xLabel?: string
}) {
  // Merge on x so a single tooltip shows both runs at the same time point.
  const merged = new Map<number, { x: number; a?: number | null; b?: number | null }>()
  for (const point of seriesA) {
    merged.set(point.x, { x: point.x, a: point.y })
  }
  for (const point of seriesB) {
    const existing = merged.get(point.x)
    if (existing) existing.b = point.y
    else merged.set(point.x, { x: point.x, b: point.y })
  }
  const data = [...merged.values()].sort((left, right) => left.x - right.x)

  return (
    <LineChart
      data={data}
      width={width}
      height={height}
      margin={{ top: 4, right: 8, bottom: 2, left: -12 }}
    >
      <CartesianGrid stroke={CHART_COLOURS.grid} strokeDasharray="3 3" vertical={false} />
      <XAxis
        dataKey="x"
        {...AXIS_PROPS}
        tickFormatter={(value: number) => value.toFixed(0)}
      />
      <YAxis {...AXIS_PROPS} width={52} />
      <RechartsTooltip
        contentStyle={{
          backgroundColor: 'rgb(var(--color-elevated))',
          border: '1px solid rgb(var(--color-hairline))',
          borderRadius: 8,
          fontSize: 11,
          padding: '6px 10px',
        }}
        labelStyle={{ color: 'rgb(var(--color-ink-muted))', fontSize: 10 }}
        labelFormatter={(value) => `${xLabel}: ${Number(value).toFixed(2)}`}
        formatter={(value: unknown, name: unknown) => [
          `${Number(value).toFixed(4)}${unit ? ` ${unit}` : ''}`,
          name === 'a' ? labelA : labelB,
        ]}
      />
      <Line
        type="monotone"
        dataKey="a"
        stroke={CHART_COLOURS.primary}
        strokeWidth={1.6}
        dot={false}
        connectNulls={false}
      />
      <Line
        type="monotone"
        dataKey="b"
        stroke={CHART_COLOURS.secondary}
        strokeWidth={1.6}
        dot={false}
        connectNulls={false}
      />
    </LineChart>
  )
}
