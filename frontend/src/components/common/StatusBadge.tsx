import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
} from 'lucide-react'

import { cn } from '@/components/ui/cn'
import type { JobStatus } from '@/types/simulation'
import { RESULT_LABELS, type ResultKind } from '@/utils/resultLabels'

type Tone = 'ok' | 'warn' | 'danger' | 'accent' | 'neutral'

const TONE_CLASSES: Record<Tone, string> = {
  ok: 'border-ok/40 bg-ok/10 text-ok',
  warn: 'border-warn/40 bg-warn/10 text-warn',
  danger: 'border-danger/40 bg-danger/10 text-danger',
  accent: 'border-accent/40 bg-accent/10 text-accent',
  neutral: 'border-hairline bg-elevated text-ink-muted',
}

const JOB_STATUS: Record<JobStatus, { tone: Tone; label: string }> = {
  queued: { tone: 'neutral', label: 'Queued' },
  running: { tone: 'accent', label: 'Running' },
  completed: { tone: 'ok', label: 'Completed' },
  failed: { tone: 'danger', label: 'Failed' },
  cancelled: { tone: 'warn', label: 'Cancelled' },
}

export function StatusBadge({
  status,
  className,
}: {
  status: JobStatus
  className?: string
}) {
  const { tone, label } = JOB_STATUS[status] ?? JOB_STATUS.queued
  const Icon =
    status === 'running'
      ? Loader2
      : status === 'completed'
        ? CheckCircle2
        : status === 'failed'
          ? XCircle
          : status === 'cancelled'
            ? Ban
            : Circle

  return (
    <span className={cn('badge', TONE_CLASSES[tone], className)}>
      <Icon
        className={cn('h-3 w-3', status === 'running' && 'animate-spin')}
        aria-hidden
      />
      {label}
    </span>
  )
}

/** Readiness badge for a subsystem. */
export function ReadinessBadge({
  status,
  className,
}: {
  status: 'ready' | 'degraded' | 'unavailable' | 'not_ready'
  className?: string
}) {
  const map = {
    ready: { tone: 'ok' as Tone, label: 'Ready', Icon: CheckCircle2 },
    degraded: { tone: 'warn' as Tone, label: 'Degraded', Icon: AlertTriangle },
    unavailable: { tone: 'danger' as Tone, label: 'Unavailable', Icon: XCircle },
    not_ready: { tone: 'danger' as Tone, label: 'Not ready', Icon: XCircle },
  }
  const { tone, label, Icon } = map[status] ?? map.unavailable
  return (
    <span className={cn('badge', TONE_CLASSES[tone], className)}>
      <Icon className="h-3 w-3" aria-hidden />
      {label}
    </span>
  )
}

/**
 * The provenance label for a result. The label strings themselves live in
 * utils/resultLabels.ts so they can be reused without breaking Fast Refresh.
 */
const RESULT_TONES: Record<ResultKind, Tone> = {
  ml_prediction: 'accent',
  rapid_openmm: 'ok',
  precomputed: 'warn',
  minimisation_only: 'neutral',
  visualization: 'warn',
  production_future: 'neutral',
  proxy: 'accent',
}

export function ResultLabel({
  kind,
  className,
  override,
}: {
  kind: ResultKind
  className?: string
  /** Use the backend's exact label string when it supplies one. */
  override?: string | null
}) {
  return (
    <span className={cn('badge', TONE_CLASSES[RESULT_TONES[kind]], className)}>
      {override || RESULT_LABELS[kind]}
    </span>
  )
}

/** Risk level badge for an ML degradation estimate. */
export function RiskBadge({
  level,
  className,
}: {
  level: 'low' | 'moderate' | 'elevated' | 'high'
  className?: string
}) {
  const tone: Record<string, Tone> = {
    low: 'ok',
    moderate: 'accent',
    elevated: 'warn',
    high: 'danger',
  }
  return (
    <span className={cn('badge capitalize', TONE_CLASSES[tone[level]], className)}>
      {level}
    </span>
  )
}
