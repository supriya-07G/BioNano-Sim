import { Link } from 'react-router-dom'
import { Activity, BookOpen, Boxes, Cpu, ExternalLink } from 'lucide-react'

import { ReadinessBadge } from '@/components/common/StatusBadge'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import { useReadiness } from '@/hooks/useSimulation'
import { API_BASE } from '@/services/api'

export function Topbar({ className }: { className?: string }) {
  // Poll readiness slowly: enough to notice a backend restart, not enough to
  // add noise while a simulation is running.
  const { data, isLoading, isError } = useReadiness({ refetchInterval: 20_000 })

  const model = data?.components.find((c) => c.name === 'ml_model')
  const engine = data?.components.find((c) => c.name === 'simulation_engine')

  return (
    <header
      className={cn(
        'flex h-14 shrink-0 items-center gap-4 border-b border-hairline bg-surface/80 px-4 backdrop-blur',
        className,
      )}
    >
      <Link to="/" className="flex items-center gap-2.5">
        <span className="relative grid h-8 w-8 place-items-center rounded-lg border border-accent/30 bg-accent/10">
          <Boxes className="h-4 w-4 text-accent" aria-hidden />
        </span>
        <span className="leading-tight">
          <span className="block text-sm font-semibold tracking-tight text-ink">
            BioNano-Sim
          </span>
          <span className="block text-2xs text-ink-faint">
            Protein nanomachine stress testing
          </span>
        </span>
      </Link>

      <div className="ml-auto flex items-center gap-2">
        {isLoading && <span className="skeleton h-6 w-40" />}

        {isError && (
          <span className="badge border-danger/40 bg-danger/10 text-danger">
            Backend unreachable
          </span>
        )}

        {data && (
          <>
            <Tooltip
              side="bottom"
              content={
                <span>
                  <strong className="text-ink">ML model</strong> &mdash; {model?.detail}
                  {model?.version && (
                    <span className="mt-1 block font-mono text-2xs">
                      version {model.version}
                    </span>
                  )}
                </span>
              }
            >
              <span
                className={cn(
                  'badge cursor-help',
                  model?.ready
                    ? 'border-ok/40 bg-ok/10 text-ok'
                    : 'border-danger/40 bg-danger/10 text-danger',
                )}
              >
                <Activity className="h-3 w-3" aria-hidden />
                Model
              </span>
            </Tooltip>

            <Tooltip
              side="bottom"
              content={
                <span>
                  <strong className="text-ink">Simulation engine</strong> &mdash;{' '}
                  {engine?.detail}
                </span>
              }
            >
              <span
                className={cn(
                  'badge cursor-help',
                  engine?.ready
                    ? 'border-ok/40 bg-ok/10 text-ok'
                    : 'border-danger/40 bg-danger/10 text-danger',
                )}
              >
                <Cpu className="h-3 w-3" aria-hidden />
                OpenMM
              </span>
            </Tooltip>

            <ReadinessBadge status={data.status} />
          </>
        )}

        <Link to="/methodology" className="btn-ghost !px-2.5 !py-1.5 !text-xs">
          <BookOpen className="h-3.5 w-3.5" aria-hidden />
          Methodology
        </Link>

        <a
          href={API_BASE + '/docs'}
          target="_blank"
          rel="noreferrer noopener"
          className="btn-ghost !px-2.5 !py-1.5 !text-xs"
        >
          API
          <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      </div>
    </header>
  )
}
