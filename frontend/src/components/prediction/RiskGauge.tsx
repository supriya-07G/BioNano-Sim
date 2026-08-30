import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import type { RiskLevel } from '@/types/prediction'
import { fmtPercent } from '@/utils/formatters'

/**
 * Quartile boundaries of the mock model's own training target distribution
 * (n = 450: Q1 46.23 %, median 52.34 %, Q3 58.91 %). Using the model's own
 * distribution rather than invented thresholds means "high" genuinely says
 * "in the worst quartile of what this model produces".
 */
const BANDS: { max: number; level: RiskLevel; colour: string }[] = [
  { max: 46.23, level: 'low', colour: 'rgb(var(--color-ok))' },
  { max: 52.34, level: 'moderate', colour: 'rgb(var(--color-accent))' },
  { max: 58.91, level: 'elevated', colour: 'rgb(var(--color-warn))' },
  { max: 100, level: 'high', colour: 'rgb(var(--color-danger))' },
]

/** Observed range of the model's target across the full mock dataset. */
const OBSERVED_MIN = 34.13
const OBSERVED_MAX = 78.29

interface RiskGaugeProps {
  percent: number
  level: RiskLevel
  className?: string
  /** Second value drawn as a marker, e.g. the simulation drift proxy. */
  comparisonPercent?: number | null
  comparisonLabel?: string
}

export function RiskGauge({
  percent,
  level,
  className,
  comparisonPercent,
  comparisonLabel,
}: RiskGaugeProps) {
  const clamped = Math.max(0, Math.min(100, percent))
  const colour = BANDS.find((band) => band.level === level)?.colour ?? 'rgb(var(--color-accent))'

  // Semicircular arc: 180 degrees mapped over 0..100 %.
  const radius = 68
  const cx = 84
  const cy = 84
  const angle = Math.PI * (1 - clamped / 100)
  const needleX = cx + radius * Math.cos(angle)
  const needleY = cy - radius * Math.sin(angle)

  const arcPath = (from: number, to: number) => {
    const a0 = Math.PI * (1 - from / 100)
    const a1 = Math.PI * (1 - to / 100)
    const x0 = cx + radius * Math.cos(a0)
    const y0 = cy - radius * Math.sin(a0)
    const x1 = cx + radius * Math.cos(a1)
    const y1 = cy - radius * Math.sin(a1)
    return `M ${x0} ${y0} A ${radius} ${radius} 0 0 1 ${x1} ${y1}`
  }

  let previous = 0
  const segments = BANDS.map((band) => {
    const segment = { from: previous, to: band.max, colour: band.colour }
    previous = band.max
    return segment
  })

  const comparisonAngle =
    comparisonPercent !== null && comparisonPercent !== undefined
      ? Math.PI * (1 - Math.max(0, Math.min(100, comparisonPercent)) / 100)
      : null

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <svg viewBox="0 0 168 104" className="w-full max-w-[220px]" role="img"
        aria-label={`Predicted degradation ${clamped.toFixed(1)} percent, risk ${level}`}>
        {/* Band arcs */}
        {segments.map((segment) => (
          <path
            key={segment.from}
            d={arcPath(segment.from, segment.to)}
            stroke={segment.colour}
            strokeOpacity={0.24}
            strokeWidth={11}
            strokeLinecap="butt"
            fill="none"
          />
        ))}

        {/* Active arc up to the value */}
        <path
          d={arcPath(0, clamped)}
          stroke={colour}
          strokeWidth={11}
          strokeLinecap="round"
          fill="none"
        />

        {/* Observed-range markers: outside these the model has never produced a value. */}
        {[OBSERVED_MIN, OBSERVED_MAX].map((mark) => {
          const a = Math.PI * (1 - mark / 100)
          return (
            <line
              key={mark}
              x1={cx + (radius - 9) * Math.cos(a)}
              y1={cy - (radius - 9) * Math.sin(a)}
              x2={cx + (radius + 9) * Math.cos(a)}
              y2={cy - (radius + 9) * Math.sin(a)}
              stroke="rgb(var(--color-ink-faint))"
              strokeWidth={1}
              strokeDasharray="2 2"
            />
          )
        })}

        {/* Comparison marker */}
        {comparisonAngle !== null && (
          <g>
            <line
              x1={cx + (radius - 14) * Math.cos(comparisonAngle)}
              y1={cy - (radius - 14) * Math.sin(comparisonAngle)}
              x2={cx + (radius + 6) * Math.cos(comparisonAngle)}
              y2={cy - (radius + 6) * Math.sin(comparisonAngle)}
              stroke="rgb(var(--color-violet))"
              strokeWidth={2.5}
              strokeLinecap="round"
            />
          </g>
        )}

        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needleX}
          y2={needleY}
          stroke={colour}
          strokeWidth={2.5}
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r={4} fill={colour} />

        <text
          x={cx}
          y={cy - 22}
          textAnchor="middle"
          className="fill-ink font-mono"
          style={{ fontSize: 22, fontVariantNumeric: 'tabular-nums' }}
        >
          {clamped.toFixed(1)}%
        </text>
      </svg>

      <div className="mt-1 flex items-center gap-1.5">
        <span
          className="badge capitalize"
          style={{
            borderColor: `${colour}66`,
            backgroundColor: `${colour}1A`,
            color: colour,
          }}
        >
          {level}
        </span>
        <Tooltip
          width="lg"
          content={
            <span>
              Bands are the quartiles of this model&rsquo;s own training target
              distribution (Q1 {BANDS[0].max}%, median {BANDS[1].max}%, Q3{' '}
              {BANDS[2].max}%). A &ldquo;high&rdquo; reading means the estimate sits in
              the top quartile of values this model produces &mdash; it is{' '}
              <strong>not</strong> an experimental damage criterion. Dashed ticks mark
              the observed output range ({OBSERVED_MIN}&ndash;{OBSERVED_MAX}%); the
              model has never produced a value outside them.
            </span>
          }
        />
      </div>

      {comparisonPercent !== null && comparisonPercent !== undefined && (
        <p className="mt-1.5 flex items-center gap-1.5 text-2xs text-ink-faint">
          <span className="h-2 w-0.5 rounded bg-violet" aria-hidden />
          {comparisonLabel ?? 'Simulation proxy'}: {fmtPercent(comparisonPercent, 1)}
        </p>
      )}
    </div>
  )
}
