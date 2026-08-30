import { useState, type ReactNode } from 'react'
import { AlertTriangle, ChevronDown, FlaskConical, Info, ShieldAlert } from 'lucide-react'

import { cn } from '@/components/ui/cn'

type Variant = 'info' | 'caution' | 'warning' | 'scientific'

const VARIANTS: Record<
  Variant,
  { wrap: string; icon: typeof Info; iconClass: string }
> = {
  info: {
    wrap: 'border-accent/25 bg-accent/[0.06]',
    icon: Info,
    iconClass: 'text-accent',
  },
  scientific: {
    wrap: 'border-violet/25 bg-violet/[0.06]',
    icon: FlaskConical,
    iconClass: 'text-violet',
  },
  caution: {
    wrap: 'border-warn/25 bg-warn/[0.06]',
    icon: AlertTriangle,
    iconClass: 'text-warn',
  },
  warning: {
    wrap: 'border-danger/25 bg-danger/[0.06]',
    icon: ShieldAlert,
    iconClass: 'text-danger',
  },
}

interface ScientificNoticeProps {
  title: string
  children?: ReactNode
  variant?: Variant
  items?: string[]
  className?: string
  /** Render collapsed, with a toggle. Useful for long warning lists. */
  collapsible?: boolean
  defaultOpen?: boolean
  compact?: boolean
}

/**
 * The standard container for a scientific caveat.
 *
 * Every limitation the backend reports is surfaced through this component so
 * caveats look consistent and cannot be mistaken for decoration.
 */
export function ScientificNotice({
  title,
  children,
  variant = 'info',
  items,
  className,
  collapsible = false,
  defaultOpen = true,
  compact = false,
}: ScientificNoticeProps) {
  const [open, setOpen] = useState(defaultOpen)
  const { wrap, icon: Icon, iconClass } = VARIANTS[variant]
  const showBody = !collapsible || open
  const count = items?.length ?? 0

  return (
    <section
      className={cn('rounded-lg border', wrap, compact ? 'p-3' : 'p-4', className)}
      aria-label={title}
    >
      <div className="flex items-start gap-2.5">
        <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', iconClass)} aria-hidden />
        <div className="min-w-0 flex-1">
          {collapsible ? (
            <button
              type="button"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
              className="flex w-full items-center justify-between gap-2 text-left"
            >
              <span className="text-xs font-semibold text-ink">
                {title}
                {count > 0 && (
                  <span className="ml-1.5 font-normal text-ink-faint">({count})</span>
                )}
              </span>
              <ChevronDown
                className={cn(
                  'h-4 w-4 shrink-0 text-ink-faint transition-transform duration-200',
                  open && 'rotate-180',
                )}
                aria-hidden
              />
            </button>
          ) : (
            <h3 className="text-xs font-semibold text-ink">{title}</h3>
          )}

          {showBody && (
            <div
              className={cn(
                'text-xs leading-relaxed text-ink-muted',
                (children || count > 0) && 'mt-1.5',
              )}
            >
              {children}
              {count > 0 && (
                <ul className="space-y-1.5">
                  {items!.map((item, index) => (
                    <li key={index} className="flex gap-2">
                      <span
                        className={cn('mt-[0.4rem] h-1 w-1 shrink-0 rounded-full', iconClass, 'bg-current')}
                        aria-hidden
                      />
                      <span className="min-w-0">{item}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

/** The project-wide scope statement, used on the landing and methodology pages. */
export function ScopeNotice({ className }: { className?: string }) {
  return (
    <ScientificNotice title="Scientific scope" variant="scientific" className={className}>
      <p className="mb-2">
        BioNano-Sim does not claim that proteins replace silicon electronics.
        Proteins and silicon are separate technologies. This platform investigates
        whether selected proteins could act as nanoscale <em>mechanical</em>{' '}
        components — molecular springs, switches, sensors or structural elements —
        by measuring how their stiffness changes when residues lose side chains.
      </p>
      <p className="mb-2">
        <strong>Radiation is not simulated.</strong> No dose, particle track or
        energy deposition enters the model. Which residues are damaged is chosen
        using literature radiosensitivity; the damage itself is applied as a
        structural lesion and the mechanical consequence is measured.
      </p>
      <p>
        The ML degradation estimate comes from an MVP bootstrap model trained on a
        synthetic public-data proxy, not experimental measurements. Molecular
        dynamics runs are real but very short. Neither has been validated against
        experiment.
      </p>
    </ScientificNotice>
  )
}
