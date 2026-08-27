import type { LucideIcon } from 'lucide-react'
import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/components/ui/cn'

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  className,
  compact = false,
}: {
  title: string
  description?: string
  icon?: LucideIcon
  action?: ReactNode
  className?: string
  compact?: boolean
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-hairline text-center',
        compact ? 'gap-2 p-5' : 'gap-3 p-10',
        className,
      )}
    >
      <div className="rounded-lg border border-hairline bg-elevated p-2.5">
        <Icon className="h-5 w-5 text-ink-faint" aria-hidden />
      </div>
      <h3 className="text-sm font-medium text-ink">{title}</h3>
      {description && (
        <p className="max-w-md text-xs leading-relaxed text-ink-muted">{description}</p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}
