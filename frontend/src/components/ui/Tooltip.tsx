import { useId, useState, type KeyboardEvent, type ReactNode } from 'react'
import { HelpCircle } from 'lucide-react'

import { cn } from './cn'

interface TooltipProps {
  content: ReactNode
  children?: ReactNode
  className?: string
  side?: 'top' | 'bottom'
  width?: 'sm' | 'md' | 'lg'
}

const WIDTHS = { sm: 'w-52', md: 'w-72', lg: 'w-96' } as const

/**
 * Plain-language explainer attached to a metric.
 *
 * Opens on hover *and* on focus, and is reachable by keyboard, so the
 * explanation is never mouse-only.
 *
 * The trigger is a `span` with button semantics rather than a real `<button>`:
 * tooltips appear inside clickable rows and table cells, and a nested `<button>`
 * is invalid HTML (React flags it, and browsers recover unpredictably). The ARIA
 * role plus an explicit keydown handler keeps it fully operable.
 */
export function Tooltip({
  content,
  children,
  className,
  side = 'top',
  width = 'md',
}: TooltipProps) {
  const [open, setOpen] = useState(false)
  const id = useId()

  const toggle = () => setOpen((value) => !value)

  const onKeyDown = (event: KeyboardEvent<HTMLSpanElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      event.stopPropagation()
      toggle()
    } else if (event.key === 'Escape' && open) {
      setOpen(false)
    }
  }

  return (
    <span className={cn('relative inline-flex items-center', className)}>
      <span
        role="button"
        tabIndex={0}
        aria-label="Explain this metric"
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        className="inline-flex cursor-help items-center rounded text-ink-faint transition-colors hover:text-accent focus-visible:text-accent"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
        onClick={(event) => {
          // Stop the click reaching an enclosing row/card button.
          event.preventDefault()
          event.stopPropagation()
          toggle()
        }}
      >
        {children ?? <HelpCircle className="h-3.5 w-3.5" aria-hidden />}
      </span>

      {open && (
        <span
          id={id}
          role="tooltip"
          className={cn(
            'absolute left-1/2 z-50 -translate-x-1/2 rounded-lg border border-hairline',
            'bg-elevated p-3 text-xs font-normal leading-relaxed text-ink-muted shadow-panel',
            'pointer-events-none normal-case tracking-normal',
            WIDTHS[width],
            side === 'top' ? 'bottom-full mb-2' : 'top-full mt-2',
          )}
        >
          {content}
        </span>
      )}
    </span>
  )
}
