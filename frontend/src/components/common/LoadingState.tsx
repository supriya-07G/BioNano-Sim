import { Loader2 } from 'lucide-react'

import { cn } from '@/components/ui/cn'

export function LoadingState({
  label = 'Loading…',
  className,
  compact = false,
}: {
  label?: string
  className?: string
  compact?: boolean
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 text-center',
        compact ? 'py-6' : 'py-14',
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-5 w-5 animate-spin text-accent" aria-hidden />
      <p className="text-sm text-ink-muted">{label}</p>
    </div>
  )
}

/** Skeleton block for a card-shaped placeholder. */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('card p-4', className)} aria-hidden>
      <div className="skeleton h-3 w-24" />
      <div className="skeleton mt-3 h-8 w-32" />
      <div className="skeleton mt-3 h-2.5 w-full" />
      <div className="skeleton mt-2 h-2.5 w-3/4" />
    </div>
  )
}

export function SkeletonRows({
  rows = 5,
  className,
}: {
  rows?: number
  className?: string
}) {
  return (
    <div className={cn('space-y-2', className)} aria-hidden>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton h-11 w-full" />
      ))}
    </div>
  )
}

export function SkeletonChart({ className }: { className?: string }) {
  return (
    <div className={cn('card p-4', className)} aria-hidden>
      <div className="skeleton h-3 w-32" />
      <div className="skeleton mt-4 h-48 w-full" />
    </div>
  )
}
