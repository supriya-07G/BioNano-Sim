import { cn } from '@/components/ui/cn'

/**
 * System architecture, drawn as inline SVG.
 *
 * Inline rather than an image so it inherits the palette, scales cleanly and
 * stays readable at 1366x768. The point of the diagram is the *separation* of
 * the two result paths — ML inference and physics — which is why they are drawn
 * as distinct lanes that only meet at the comparison step.
 */
export function ArchitectureDiagram({ className }: { className?: string }) {
  return (
    <div className={cn('scroll-x rounded-lg border border-hairline bg-void p-3', className)}>
      <svg
        viewBox="0 0 880 380"
        className="h-auto w-full min-w-[680px]"
        role="img"
        aria-label="COSMORA architecture: React frontend calls a FastAPI backend, which splits into an ML inference path and an OpenMM simulation path that meet at the comparison and report step."
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgb(var(--color-ink-faint))" />
          </marker>
          <linearGradient id="ml-lane" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgb(var(--color-accent))" stopOpacity="0.10" />
            <stop offset="100%" stopColor="rgb(var(--color-accent))" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="sim-lane" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgb(var(--color-ok))" stopOpacity="0.10" />
            <stop offset="100%" stopColor="rgb(var(--color-ok))" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Lane backgrounds */}
        <rect x="232" y="66" width="440" height="94" rx="10" fill="url(#ml-lane)" />
        <rect x="232" y="186" width="440" height="94" rx="10" fill="url(#sim-lane)" />

        <text x="240" y="60" fill="rgb(var(--color-accent))" fontSize="10" fontWeight="600">
          ML INFERENCE PATH
        </text>
        <text x="240" y="180" fill="rgb(var(--color-ok))" fontSize="10" fontWeight="600">
          PHYSICS PATH
        </text>

        {/* Frontend */}
        <Box x={20} y={140} w={150} h={82} title="React frontend" accent="rgb(var(--color-violet))"
          lines={['TypeScript · Vite', 'TanStack Query', '3Dmol.js viewer']} />

        {/* API */}
        <Box x={196} y={140} w={0} h={0} title="" accent="#000" lines={[]} />
        <rect x="186" y="150" width="34" height="62" rx="6" fill="rgb(var(--color-elevated))" stroke="rgb(var(--color-hairline))" />
        <text x="203" y="176" fill="rgb(var(--color-ink-muted))" fontSize="9" textAnchor="middle">API</text>
        <text x="203" y="188" fill="rgb(var(--color-ink-faint))" fontSize="8" textAnchor="middle">v1</text>

        {/* ML lane */}
        <Box x={244} y={78} w={128} h={70} title="Model loader" accent="rgb(var(--color-accent))"
          lines={['load once', 'SHA-256 verify', 'schema verify']} />
        <Box x={392} y={78} w={128} h={70} title="Featurisation" accent="rgb(var(--color-accent))"
          lines={['reference table', 'or recomputed', 'candidate ranking']} />
        <Box x={540} y={78} w={124} h={70} title="Inference" accent="rgb(var(--color-accent))"
          lines={['unknown-cat guard', 'envelope check', 'aggregate + warn']} />

        {/* Physics lane */}
        <Box x={244} y={198} w={128} h={70} title="Job manager" accent="rgb(var(--color-ok))"
          lines={['worker thread', 'atomic status.json', 'one job at a time']} />
        <Box x={392} y={198} w={128} h={70} title="OpenMM engine" accent="rgb(var(--color-ok))"
          lines={['amber14 + GBn2', 'Langevin, fixed seed', 'step-driven progress']} />
        <Box x={540} y={198} w={124} h={70} title="Analysis" accent="rgb(var(--color-ok))"
          lines={['RMSD · RMSF · Rg', 'energy · temperature', 'drift proxy']} />

        {/* Convergence */}
        <Box x={694} y={140} w={162} h={82} title="Compare + report" accent="rgb(var(--color-warn))"
          lines={['ML vs proxy', 'labelled separately', 'JSON + CSV export']} />

        {/* Storage */}
        <rect x="244" y="304" width="420" height="52" rx="8" fill="rgb(var(--color-surface))" stroke="rgb(var(--color-hairline))" strokeDasharray="4 3" />
        <text x="454" y="324" fill="rgb(var(--color-ink-muted))" fontSize="10" textAnchor="middle" fontWeight="600">
          Local filesystem — no database
        </text>
        <text x="454" y="340" fill="rgb(var(--color-ink-faint))" fontSize="8.5" textAnchor="middle" fontFamily="monospace">
          models/ · data/proteins/ · data/ml/ · runtime/jobs/&lt;job_id&gt;/ · runtime/uploads/
        </text>

        {/* Arrows */}
        <Arrow d="M 170 181 L 184 181" />
        <Arrow d="M 220 170 L 232 128 L 244 113" />
        <Arrow d="M 220 192 L 232 234 L 244 233" />
        <Arrow d="M 372 113 L 392 113" />
        <Arrow d="M 520 113 L 540 113" />
        <Arrow d="M 372 233 L 392 233" />
        <Arrow d="M 520 233 L 540 233" />
        <Arrow d="M 664 113 L 680 113 L 680 165 L 694 165" />
        <Arrow d="M 664 233 L 680 233 L 680 198 L 694 198" />
        {/* Report back to the frontend */}
        <Arrow d="M 775 222 L 775 262 L 95 262 L 95 222" dashed />
        <text x="435" y="256" fill="rgb(var(--color-ink-faint))" fontSize="8.5" textAnchor="middle">
          results · progress · exports
        </text>

        {/* Storage links */}
        <Arrow d="M 308 268 L 308 304" dashed />
        <Arrow d="M 602 268 L 602 304" dashed />
      </svg>

      <p className="mt-2 text-2xs leading-relaxed text-ink-faint">
        The two result paths stay separate all the way to the comparison step, and each
        keeps its own provenance label. Nothing in the physics path can be relabelled as
        a prediction, and nothing in the ML path can be presented as a trajectory.
      </p>
    </div>
  )
}

function Box({
  x,
  y,
  w,
  h,
  title,
  lines,
  accent,
}: {
  x: number
  y: number
  w: number
  h: number
  title: string
  lines: string[]
  accent: string
}) {
  if (w === 0) return null
  return (
    <g>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={8}
        fill="rgb(var(--color-elevated))"
        stroke={accent}
        strokeOpacity={0.4}
      />
      <rect x={x} y={y} width={3} height={h} rx={1.5} fill={accent} fillOpacity={0.7} />
      <text x={x + 12} y={y + 20} fill="rgb(var(--color-ink))" fontSize="11" fontWeight="600">
        {title}
      </text>
      {lines.map((line, index) => (
        <text
          key={line}
          x={x + 12}
          y={y + 36 + index * 12}
          fill="rgb(var(--color-ink-muted))"
          fontSize="8.5"
          fontFamily="monospace"
        >
          {line}
        </text>
      ))}
    </g>
  )
}

function Arrow({ d, dashed = false }: { d: string; dashed?: boolean }) {
  return (
    <path
      d={d}
      fill="none"
      stroke="rgb(var(--color-ink-faint))"
      strokeWidth={1.2}
      strokeDasharray={dashed ? '4 3' : undefined}
      markerEnd="url(#arrow)"
    />
  )
}
