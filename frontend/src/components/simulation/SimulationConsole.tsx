import { useEffect, useRef, useState } from 'react'
import { ArrowDownToLine, Download, Terminal } from 'lucide-react'

import { cn } from '@/components/ui/cn'
import { downloadUrl } from '@/services/api'

/**
 * The simulation log.
 *
 * Autoscroll sticks to the bottom while the user is already there, and releases
 * as soon as they scroll up to read something — the usual behaviour for a live
 * log, and the reason a "jump to latest" control exists.
 */
export function SimulationConsole({
  lines,
  jobId,
  className,
  maxHeight = '15rem',
}: {
  lines: string[]
  jobId: string
  className?: string
  maxHeight?: string
}) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [pinned, setPinned] = useState(true)

  useEffect(() => {
    const element = scrollRef.current
    if (!element || !pinned) return
    element.scrollTop = element.scrollHeight
  }, [lines, pinned])

  const onScroll = () => {
    const element = scrollRef.current
    if (!element) return
    const atBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight < 24
    setPinned(atBottom)
  }

  return (
    <div className={cn('flex min-h-0 flex-col', className)}>
      <div className="mb-2 flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <Terminal className="h-3 w-3" aria-hidden />
          Simulation log
          <span className="font-normal normal-case tracking-normal text-ink-faint">
            ({lines.length} lines)
          </span>
        </span>
        <div className="flex items-center gap-1">
          {!pinned && (
            <button
              type="button"
              className="btn-ghost !px-2 !py-1 !text-2xs"
              onClick={() => {
                setPinned(true)
                const element = scrollRef.current
                if (element) element.scrollTop = element.scrollHeight
              }}
            >
              <ArrowDownToLine className="h-3 w-3" aria-hidden />
              Latest
            </button>
          )}
          <a
            href={downloadUrl(`/simulations/${jobId}/log`)}
            download={`COSMORA-${jobId.slice(0, 8)}.log`}
            className="btn-ghost !px-2 !py-1 !text-2xs"
          >
            <Download className="h-3 w-3" aria-hidden />
            Full log
          </a>
        </div>
      </div>

      <div
        ref={scrollRef}
        onScroll={onScroll}
        style={{ maxHeight }}
        className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-hairline bg-void p-2.5"
        role="log"
        aria-live="polite"
        aria-atomic="false"
      >
        {lines.length === 0 ? (
          <p className="font-mono text-2xs text-ink-faint">
            Waiting for the worker to start writing&hellip;
          </p>
        ) : (
          <pre className="whitespace-pre-wrap break-words font-mono text-2xs leading-relaxed text-ink-muted">
            {lines.map((line, index) => (
              <span key={index} className={cn('block', lineTone(line))}>
                {line}
              </span>
            ))}
          </pre>
        )}
      </div>
    </div>
  )
}

function lineTone(line: string): string {
  if (line.includes('ERROR') || line.includes('Traceback')) return 'text-danger'
  if (line.includes('stage ->')) return 'text-accent'
  if (line.includes('WARNING') || line.includes('Dropped')) return 'text-warn'
  return ''
}
