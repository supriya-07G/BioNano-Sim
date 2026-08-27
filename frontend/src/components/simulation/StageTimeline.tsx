import { Check, Circle, Loader2, Minus, X } from 'lucide-react'

import { cn } from '@/components/ui/cn'
import type { StageProgress } from '@/types/simulation'

const STATE_STYLE = {
  done: { icon: Check, ring: 'border-ok/50 bg-ok/15 text-ok', text: 'text-ink-muted' },
  active: {
    icon: Loader2,
    ring: 'border-accent/60 bg-accent/15 text-accent',
    text: 'text-ink',
  },
  failed: {
    icon: X,
    ring: 'border-danger/60 bg-danger/15 text-danger',
    text: 'text-danger',
  },
  skipped: {
    icon: Minus,
    ring: 'border-hairline bg-elevated text-ink-faint',
    text: 'text-ink-faint',
  },
  pending: {
    icon: Circle,
    ring: 'border-hairline bg-elevated text-ink-faint',
    text: 'text-ink-faint',
  },
} as const

/**
 * The eight reported stages, driven entirely by backend job state.
 *
 * Nothing here advances on a timer: a stage becomes active only when the worker
 * publishes it. If a run stalls, the timeline stalls with it, which is the
 * behaviour that makes it trustworthy.
 */
export function StageTimeline({
  stages,
  className,
}: {
  stages: StageProgress[]
  className?: string
}) {
  return (
    <ol className={cn('space-y-0', className)}>
      {stages.map((stage, index) => {
        const style = STATE_STYLE[stage.state] ?? STATE_STYLE.pending
        const Icon = style.icon
        const isLast = index === stages.length - 1

        return (
          <li key={stage.stage} className="relative flex gap-3 pb-3 last:pb-0">
            {/* Connector */}
            {!isLast && (
              <span
                aria-hidden
                className={cn(
                  'absolute left-[0.6875rem] top-6 h-[calc(100%-1rem)] w-px',
                  stage.state === 'done' ? 'bg-ok/35' : 'bg-hairline',
                )}
              />
            )}

            <span
              className={cn(
                'relative z-10 grid h-[1.375rem] w-[1.375rem] shrink-0 place-items-center rounded-full border',
                style.ring,
              )}
            >
              <Icon
                className={cn('h-3 w-3', stage.state === 'active' && 'animate-spin')}
                aria-hidden
              />
            </span>

            <div className="min-w-0 flex-1 pt-0.5">
              <p className={cn('text-xs font-medium', style.text)}>{stage.label}</p>
              {stage.detail && (
                <p className="mt-0.5 truncate font-mono text-2xs text-ink-faint">
                  {stage.detail}
                </p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
