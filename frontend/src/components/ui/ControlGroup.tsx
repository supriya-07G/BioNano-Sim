import type { LucideIcon } from 'lucide-react'

import { cn } from '@/components/ui/cn'

/**
 * A segmented toggle: one icon, a row of mutually exclusive options.
 *
 * Extracted from the experiment workspace so the full-screen viewer can offer
 * the same render and colour controls. Duplicating the markup instead would
 * mean the two copies of the same control diverging the first time either is
 * restyled.
 */
export function ControlGroup<T extends string>({
  icon: Icon,
  options,
  value,
  onChange,
  className,
  label,
}: {
  icon: LucideIcon
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
  className?: string
  /** Names the group for assistive tech; the icon alone conveys nothing. */
  label?: string
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn(
        'flex items-center gap-1 rounded-lg border border-hairline bg-elevated p-0.5',
        className,
      )}
    >
      <Icon className="ml-1.5 h-3 w-3 shrink-0 text-ink-faint" aria-hidden />
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
          className={cn(
            'rounded-md px-2 py-1 text-2xs transition-colors',
            value === option.value
              ? 'bg-accent/15 text-accent'
              : 'text-ink-muted hover:bg-raised hover:text-ink',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
