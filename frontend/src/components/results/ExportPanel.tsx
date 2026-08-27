import { Braces, Download, FileSpreadsheet, FileText, Orbit } from 'lucide-react'

import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import { downloadUrl } from '@/services/api'

interface ExportPanelProps {
  jobId: string
  artifacts?: Record<string, boolean>
  className?: string
  /** Precomputed results have no downloadable job artifacts. */
  isPrecomputed?: boolean
}

export function ExportPanel({
  jobId,
  artifacts,
  className,
  isPrecomputed = false,
}: ExportPanelProps) {
  const short = jobId.slice(0, 8)

  const reports = [
    {
      icon: Braces,
      label: 'Experiment report (JSON)',
      href: `/reports/${jobId}.json`,
      filename: `bionano-sim-${short}.json`,
      help:
        'The complete record: scientific notice, protein and scenario provenance, ' +
        'ML prediction with its caveats, every simulation metric, all time series, ' +
        'per-residue RMSF, the comparison block, and full reproducibility metadata.',
    },
    {
      icon: FileSpreadsheet,
      label: 'Experiment report (CSV)',
      href: `/reports/${jobId}.csv`,
      filename: `bionano-sim-${short}.csv`,
      help:
        'The same content flattened to section/key/value rows, so it opens cleanly ' +
        'in a spreadsheet. A UTF-8 byte-order mark is included so Excel on Windows ' +
        'renders the units and symbols correctly.',
    },
  ]

  const files = [
    {
      icon: Orbit,
      label: 'Final structure (PDB)',
      href: `/simulations/${jobId}/structure?which=final`,
      filename: `${short}-final.pdb`,
      available: artifacts?.final_pdb !== false,
      help: 'Coordinates at the end of the run.',
    },
    {
      icon: Orbit,
      label: 'Simulated topology (PDB)',
      href: `/simulations/${jobId}/structure?which=topology`,
      filename: `${short}-topology.pdb`,
      available: artifacts?.topology_pdb === true,
      help:
        'The exact system that was simulated, including the hydrogens OpenMM added. ' +
        'This is the correct topology to pair with the trajectory file.',
    },
    {
      icon: Download,
      label: 'Trajectory (DCD)',
      href: `/simulations/${jobId}/trajectory`,
      filename: `${short}-trajectory.dcd`,
      available: artifacts?.trajectory_dcd === true,
      help:
        'Binary trajectory. Open it with the topology PDB above in VMD, PyMOL or ' +
        'MDTraj for your own analysis.',
    },
    {
      icon: FileText,
      label: 'Simulation log',
      href: `/simulations/${jobId}/log`,
      filename: `${short}.log`,
      available: artifacts?.simulation_log !== false,
      help: 'Full worker log, including every stage transition and any exception.',
    },
  ]

  return (
    <section className={cn('card p-4', className)}>
      <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-ink">
        <Download className="h-4 w-4 text-accent" aria-hidden />
        Exports
      </h2>

      <div className="space-y-1.5">
        {reports.map((report) => (
          <ExportRow key={report.href} {...report} available />
        ))}
      </div>

      {!isPrecomputed && (
        <>
          <div className="hairline-divider my-3" />
          <p className="label mb-2">Raw artifacts</p>
          <div className="space-y-1.5">
            {files.map((file) => (
              <ExportRow key={file.href} {...file} />
            ))}
          </div>
        </>
      )}

      {isPrecomputed && (
        <p className="mt-3 text-2xs leading-relaxed text-ink-faint">
          This is a precomputed result, so live job artifacts are not available. Run a
          simulation to produce a trajectory you can download.
        </p>
      )}
    </section>
  )
}

function ExportRow({
  icon: Icon,
  label,
  href,
  filename,
  help,
  available,
}: {
  icon: typeof Download
  label: string
  href: string
  filename: string
  help: string
  available: boolean
}) {
  if (!available) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-hairline bg-void/30 px-2.5 py-2 opacity-50">
        <Icon className="h-3.5 w-3.5 shrink-0 text-ink-faint" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-xs text-ink-faint">{label}</span>
        <span className="shrink-0 text-2xs text-ink-faint">not produced</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <a
        href={downloadUrl(href)}
        download={filename}
        className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-hairline bg-elevated px-2.5 py-2 transition-colors hover:border-accent/40 hover:bg-raised"
      >
        <Icon className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden />
        <span className="min-w-0 flex-1 truncate text-xs text-ink">{label}</span>
        <Download className="h-3 w-3 shrink-0 text-ink-faint" aria-hidden />
      </a>
      <Tooltip width="md" content={help} />
    </div>
  )
}
