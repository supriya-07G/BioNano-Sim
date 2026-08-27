import { RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/components/ui/cn'
import { describeError } from '@/utils/errors'

interface ErrorStateProps {
  error: unknown
  onRetry?: () => void
  className?: string
  title?: string
  compact?: boolean
  children?: ReactNode
}

export function ErrorState({
  error,
  onRetry,
  className,
  title,
  compact = false,
  children,
}: ErrorStateProps) {
  const described = describeError(error, title)
  const Icon = described.icon

  return (
    <div
      className={cn(
        'rounded-lg border border-danger/30 bg-danger/[0.06]',
        compact ? 'p-3' : 'p-5',
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-ink">{described.title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-ink-muted">
            {described.message}
          </p>

          {described.details.length > 0 && (
            <ul className="mt-2 space-y-1">
              {described.details.map((detail, index) => (
                <li key={index} className="font-mono text-2xs text-ink-faint">
                  • {detail}
                </li>
              ))}
            </ul>
          )}

          {described.hint && (
            <p className="mt-2 rounded border border-hairline bg-void/60 p-2 font-mono text-2xs leading-relaxed text-ink-muted">
              {described.hint}
            </p>
          )}

          {children && <div className="mt-3">{children}</div>}

          <div className="mt-3 flex flex-wrap items-center gap-3">
            {onRetry && (
              <button type="button" onClick={onRetry} className="btn-secondary !py-1.5 !text-xs">
                <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                Retry
              </button>
            )}
            {described.requestId && (
              <span className="font-mono text-2xs text-ink-faint">
                request {described.requestId.slice(0, 8)}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
