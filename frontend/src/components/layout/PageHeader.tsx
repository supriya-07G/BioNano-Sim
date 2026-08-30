import type { ReactNode } from 'react'

import { cn } from '@/components/ui/cn'

export function PageHeader({
  title,
  description,
  actions,
  badges,
  className,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
  badges?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('mb-5 flex flex-wrap items-start justify-between gap-4', className)}>
      <div className="page-header-shell min-w-0">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="page-header-title text-lg font-semibold tracking-tight text-ink">
            {title}
          </h1>
          {badges}
        </div>
        {description && (
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-ink-muted">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      )}
    </div>
  )
}
