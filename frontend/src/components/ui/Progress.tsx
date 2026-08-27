import { cn } from './cn'

interface ProgressProps {
  /** 0..1 */
  value: number
  className?: string
  tone?: 'accent' | 'ok' | 'warn' | 'danger'
  label?: string
  indeterminate?: boolean
}

const TONES = {
  accent: 'bg-accent',
  ok: 'bg-ok',
  warn: 'bg-warn',
  danger: 'bg-danger',
} as const

export function Progress({
  value,
  className,
  tone = 'accent',
  label,
  indeterminate = false,
}: ProgressProps) {
  const pct = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0)) * 100
  return (
    <div
      className={cn('h-1.5 w-full overflow-hidden rounded-full bg-void', className)}
      role="progressbar"
      aria-valuenow={indeterminate ? undefined : Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? 'Progress'}
    >
      <div
        className={cn(
          'h-full rounded-full transition-[width] duration-500 ease-crisp',
          TONES[tone],
          indeterminate && 'animate-pulse-soft',
        )}
        style={{ width: indeterminate ? '35%' : `${pct}%` }}
      />
    </div>
  )
}
