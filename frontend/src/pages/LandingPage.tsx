import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity,
  ArrowRight,
  Atom,
  BookOpen,
  Boxes,
  CheckCircle2,
  Cpu,
  Microscope,
  Radiation,
  Settings2,
  Sparkles,
} from 'lucide-react'

import { ScopeNotice } from '@/components/common/ScientificNotice'
import { OrbitLines, Starfield } from '@/components/layout/Starfield'
import { cn } from '@/components/ui/cn'
import { useReadiness } from '@/hooks/useSimulation'

const CHIPS = [
  { icon: Boxes, label: '5 approved proteins' },
  { icon: Activity, label: 'ML degradation estimation' },
  { icon: Cpu, label: 'OpenMM rapid simulation' },
  { icon: Atom, label: 'Interactive molecular analysis' },
] as const

const WORKFLOW = [
  {
    icon: Boxes,
    title: 'Select protein',
    body: 'Choose one of five approved domains, or upload your own validated PDB.',
  },
  {
    icon: Settings2,
    title: 'Configure environment',
    body: 'Pick a demonstration radiation scenario and set temperature and exposure.',
  },
  {
    icon: Sparkles,
    title: 'Predict degradation',
    body: 'Get a per-residue ML estimate from the MVP bootstrap model.',
  },
  {
    icon: Radiation,
    title: 'Run rapid simulation',
    body: 'Execute a real, short OpenMM molecular-dynamics run and watch it progress.',
  },
  {
    icon: Microscope,
    title: 'Analyse stability',
    body: 'Compare RMSD, RMSF and radius of gyration, then export the full record.',
  },
] as const

export function LandingPage() {
  const { data: readiness } = useReadiness()

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-void">
      <Starfield className="opacity-70" />
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-orbit-glow" />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-grid-fine opacity-40"
      />

      {/* --- Header ------------------------------------------------------ */}
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg border border-accent/30 bg-accent/10">
            <Boxes className="h-4.5 w-4.5 text-accent" aria-hidden />
          </span>
          <span className="text-sm font-semibold tracking-tight text-ink">
            COSMORA
          </span>
        </div>
        <nav className="flex items-center gap-2">
          <Link to="/methodology" className="btn-ghost !text-xs">
            Methodology
          </Link>
          <Link to="/dashboard" className="btn-secondary !text-xs">
            Open dashboard
          </Link>
        </nav>
      </header>

      {/* --- Hero ------------------------------------------------------- */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 pb-8 pt-6 lg:pt-12">
        <div className="relative">
          <OrbitLines className="opacity-60" />

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.2, 0.8, 0.2, 1] }}
            className="relative max-w-3xl"
          >
            <span className="badge border-accent/35 bg-accent/[0.08] text-accent">
              MVP · scientific integrity first
            </span>

            <h1 className="text-balance mt-4 text-4xl font-semibold leading-[1.1] tracking-tight text-ink lg:text-5xl">
              AI-Assisted Stress Testing for{' '}
              <span className="bg-gradient-to-r from-accent via-accent-soft to-violet bg-clip-text text-transparent">
                Protein Nanomachines
              </span>{' '}
              in Deep Space
            </h1>

            <p className="mt-5 max-w-2xl text-sm leading-relaxed text-ink-muted">
              COSMORA combines three clearly separated capabilities: a{' '}
              <strong className="text-ink">machine-learning degradation estimate</strong>{' '}
              from a mock public-data bootstrap model, a{' '}
              <strong className="text-ink">real but short OpenMM simulation</strong> in
              implicit solvent, and{' '}
              <strong className="text-ink">structural stability analysis</strong>{' '}
              computed from the resulting trajectory. Each result carries its own
              provenance label, so a prediction is never mistaken for physics and
              physics is never mistaken for measurement.
            </p>

            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Link to="/experiment" className="btn-primary">
                Launch Simulation Lab
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
              <Link to="/methodology" className="btn-secondary">
                <BookOpen className="h-4 w-4" aria-hidden />
                Explore Methodology
              </Link>
            </div>

            {/* Status chips */}
            <ul className="mt-7 flex flex-wrap gap-2">
              {CHIPS.map((chip) => (
                <li
                  key={chip.label}
                  className="flex items-center gap-1.5 rounded-lg border border-hairline bg-elevated/70 px-2.5 py-1.5 backdrop-blur"
                >
                  <chip.icon className="h-3 w-3 text-accent" aria-hidden />
                  <span className="text-2xs text-ink-muted">{chip.label}</span>
                </li>
              ))}
              {readiness && (
                <li
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 backdrop-blur',
                    readiness.ready
                      ? 'border-ok/35 bg-ok/[0.08]'
                      : 'border-warn/35 bg-warn/[0.08]',
                  )}
                >
                  <CheckCircle2
                    className={cn(
                      'h-3 w-3',
                      readiness.ready ? 'text-ok' : 'text-warn',
                    )}
                    aria-hidden
                  />
                  <span className="text-2xs text-ink-muted">
                    Backend {readiness.status.replace('_', ' ')}
                  </span>
                </li>
              )}
            </ul>
          </motion.div>
        </div>
      </section>

      {/* --- Workflow --------------------------------------------------- */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 py-10">
        <h2 className="label mb-4">How it works</h2>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {WORKFLOW.map((step, index) => (
            <motion.li
              key={step.title}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.05 * index }}
              className="card card-hover p-3.5"
            >
              <div className="flex items-center gap-2">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md border border-accent/25 bg-accent/10 font-mono text-2xs text-accent">
                  {index + 1}
                </span>
                <step.icon className="h-3.5 w-3.5 text-ink-faint" aria-hidden />
              </div>
              <h3 className="mt-2.5 text-xs font-medium text-ink">{step.title}</h3>
              <p className="mt-1 text-2xs leading-relaxed text-ink-muted">{step.body}</p>
            </motion.li>
          ))}
        </ol>
      </section>

      {/* --- Three capabilities ---------------------------------------- */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 pb-10">
        <div className="grid gap-3 lg:grid-cols-3">
          <Capability
            icon={Sparkles}
            tone="accent"
            label="ML Prediction"
            title="Per-residue degradation estimate"
            body="A gradient-boosted model predicts side-chain-loss degradation for the most susceptible residues under a chosen scenario. Labels are a synthetic public-data proxy, so this is an MVP estimate — not a validated prediction."
            facts={[
              'Held-out MAE 2.26–4.11 percentage points',
              'No calibrated confidence: reported as null',
              'Radiation enters only as a scenario category',
            ]}
          />
          <Capability
            icon={Cpu}
            tone="ok"
            label="Rapid OpenMM Simulation"
            title="Real molecular dynamics, honestly scoped"
            body="Amber14 with GBn2 implicit solvent, a Langevin integrator and a fixed seed. The trajectory, energies and temperatures are genuine OpenMM output — over picoseconds, not the seconds-to-years of real degradation."
            facts={[
              'Progress driven by the integrator step counter',
              'Standard OpenMM models no ionising radiation',
              'One job at a time, with hard safety limits',
            ]}
          />
          <Capability
            icon={Microscope}
            tone="violet"
            label="Structural analysis"
            title="Metrics you can audit"
            body="RMSD, per-residue RMSF, radius of gyration and energies, all computed from the real coordinates. The degradation proxy that puts ML and physics on one axis publishes its own formula and reference scales."
            facts={[
              'Every metric downloadable as JSON and CSV',
              'Trajectory and topology exported for external tools',
              'Full reproducibility metadata per run',
            ]}
          />
        </div>
      </section>

      {/* --- Scope ------------------------------------------------------ */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 pb-16">
        <ScopeNotice />
        <p className="mt-4 text-center text-2xs text-ink-faint">
          COSMORA MVP · ML estimates are not experimentally validated ·{' '}
          <Link to="/methodology" className="text-accent hover:underline">
            read what this MVP does not claim
          </Link>
        </p>
      </section>
    </div>
  )
}

function Capability({
  icon: Icon,
  tone,
  label,
  title,
  body,
  facts,
}: {
  icon: typeof Sparkles
  tone: 'accent' | 'ok' | 'violet'
  label: string
  title: string
  body: string
  facts: string[]
}) {
  const tones = {
    accent: 'border-accent/30 bg-accent/10 text-accent',
    ok: 'border-ok/30 bg-ok/10 text-ok',
    violet: 'border-violet/30 bg-violet/10 text-violet',
  } as const

  return (
    <article className="card p-4">
      <div className="flex items-center gap-2">
        <span className={cn('grid h-7 w-7 place-items-center rounded-md border', tones[tone])}>
          <Icon className="h-3.5 w-3.5" aria-hidden />
        </span>
        <span className={cn('badge', tones[tone])}>{label}</span>
      </div>
      <h3 className="mt-3 text-sm font-medium text-ink">{title}</h3>
      <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">{body}</p>
      <ul className="mt-3 space-y-1.5 border-t border-hairline pt-3">
        {facts.map((fact) => (
          <li key={fact} className="flex gap-2 text-2xs leading-relaxed text-ink-faint">
            <span className="mt-[0.35rem] h-1 w-1 shrink-0 rounded-full bg-ink-faint" aria-hidden />
            {fact}
          </li>
        ))}
      </ul>
    </article>
  )
}
