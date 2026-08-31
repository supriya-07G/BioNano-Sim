import { Link as RouterLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Activity,
  ArrowRight,
  BookOpen,
  Boxes,
  Cpu,
  Database,
  FlaskConical,
  Microscope,
  Radiation,
  Scissors,
  Settings2,
  Sparkles,
} from 'lucide-react'

import { ScopeNotice } from '@/components/common/ScientificNotice'
import { HeroStructure } from '@/components/landing/HeroStructure'
import { ScientificDistinction } from '@/components/landing/ScientificDistinction'
import { OrbitLines, Starfield } from '@/components/layout/Starfield'
import { cn } from '@/components/ui/cn'

const CHIPS = [
  { icon: Boxes, label: '13 domains screened, 4 resolved' },
  { icon: Activity, label: '520 paired steered MD experiments' },
  { icon: Cpu, label: 'OpenMM force-extension engine' },
  { icon: Database, label: 'Empirical physics dataset' },
] as const

const COUNTERS = [
  { value: '520', label: 'Paired MD Experiments', sub: 'Pristine vs Damaged steered pulling runs' },
  { value: '13', label: 'Validated Domains', sub: 'Including titin I27 benchmark & 2F4K' },
  { value: '520', label: 'Damage Configurations', sub: 'Targeted side-chain lesion positions' },
  { value: '100%', label: 'Empirical Physics', sub: 'Measured in piconewtons per nanometre' },
] as const

const PAIRED_WORKFLOW = [
  {
    icon: Boxes,
    title: '1. Protein Selection',
    body: 'Select an approved domain (e.g. 1UBQ, titin I27) or onboard a custom candidate PDB structure.',
  },
  {
    icon: Activity,
    title: '2. Pristine Baseline Test',
    body: 'Execute OpenMM steered MD pulling along terminal vector to measure pristine stiffness (k_pristine).',
  },
  {
    icon: Scissors,
    title: '3. Controlled Damage Proxy',
    body: 'Apply targeted side-chain truncation / lesion at radiosensitive residue candidate sites.',
  },
  {
    icon: Radiation,
    title: '4. Damaged Mechanical Test',
    body: 'Re-pull damaged structure under identical steered MD parameters to measure post-lesion stiffness (k_damaged).',
  },
  {
    icon: Settings2,
    title: '5. Stiffness Loss Comparison',
    body: 'Calculate absolute Δk and percentage stiffness degradation from overlaid force-extension curves.',
  },
  {
    icon: Database,
    title: '6. ML Dataset & Triage',
    body: 'Feed measured physics into the COSMORA dataset to train millisecond per-residue ML triage models.',
  },
] as const

export function LandingPage() {
  return (
    <div data-theme="light" className="relative min-h-screen overflow-x-hidden bg-void">
      <Starfield className="opacity-70" />
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-orbit-glow" />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-grid-fine opacity-40"
      />

      {/* --- Header ------------------------------------------------------ */}
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <img
            src="/logo-mark.png"
            alt=""
            width={36}
            height={36}
            className="h-9 w-9 shrink-0 object-contain"
          />
          <span className="text-sm font-semibold tracking-tight text-ink">
            COSMORA
          </span>
        </div>
        <nav className="flex items-center gap-2">
          <RouterLink to="/methodology" className="btn-ghost !text-xs">
            Methodology
          </RouterLink>
          <RouterLink to="/dashboard" className="btn-secondary !text-xs">
            Open dashboard
          </RouterLink>
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
            className="relative"
          >
            <div className="grid items-center gap-8 lg:grid-cols-[1.15fr_1fr]">
              <div className="max-w-2xl">
                <span className="badge border-accent/35 bg-accent/[0.08] text-accent">
                  COSMORA Paired-Mechanical Platform
                </span>

                <h1 className="text-balance mt-4 text-4xl font-semibold leading-[1.1] tracking-tight text-ink lg:text-5xl">
                  Engineering Proteins That{' '}
                  <span className="bg-gradient-to-r from-accent via-accent-soft to-violet bg-clip-text text-transparent">
                    Survive Deep Space
                  </span>
                </h1>

                <p className="mt-5 max-w-2xl text-sm leading-relaxed text-ink-muted">
                  Proteins are engineered into spaceflight nanomachinery: molecular springs, switches, sensors, and structural members. In deep space, components face unshielded radiation and sustained mechanical load with{' '}
                  <strong className="text-ink">no repair, replacement, or resupply</strong>.
                </p>

                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-muted">
                  COSMORA measures load-bearing capacity directly.{' '}
                  <strong className="text-ink">Which domains carry load once damage occurs?</strong>{' '}
                  A candidate residue is truncated, the domain is pulled via{' '}
                  <strong className="text-ink">steered molecular dynamics</strong>, and the change in stiffness is measured in piconewtons per nanometre (pN/nm). Real physics, on real coordinates.
                </p>

                <div className="mt-7 flex flex-wrap items-center gap-3">
                  <RouterLink to="/dashboard" className="btn-primary shadow-lg">
                    <FlaskConical className="h-4 w-4" aria-hidden />
                    View Validated 1UBQ Experiment
                    <ArrowRight className="h-4 w-4" aria-hidden />
                  </RouterLink>
                  <RouterLink to="/experiment" className="btn-secondary">
                    Launch Simulation Lab
                  </RouterLink>
                  <RouterLink to="/methodology" className="btn-ghost !text-xs">
                    <BookOpen className="h-4 w-4" aria-hidden />
                    Methodology
                  </RouterLink>
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
                </ul>
              </div>

              <HeroStructure />
            </div>
          </motion.div>
        </div>
      </section>

      {/* --- Real-Data Counter Banner ------------------------------------ */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 py-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {COUNTERS.map((counter) => (
            <div key={counter.label} className="rounded-xl border border-hairline bg-elevated/60 p-4 space-y-1 backdrop-blur">
              <div className="text-2xl font-extrabold text-accent">{counter.value}</div>
              <div className="text-xs font-bold text-ink">{counter.label}</div>
              <div className="text-2xs text-ink-faint leading-relaxed">{counter.sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* --- Scientific Distinction Callout ----------------------------- */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 py-6">
        <ScientificDistinction />
      </section>

      {/* --- Real Paired Mechanical Workflow ---------------------------- */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 py-10">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <span className="label">Real Paired-Mechanical Workflow</span>
            <h2 className="mt-1 text-lg font-bold text-ink">From Protein Selection to Empirical ML Dataset</h2>
          </div>
          <span className="badge border-ok/30 bg-ok/10 text-ok font-semibold text-2xs">
            OpenMM Steered MD + ML Triage
          </span>
        </div>

        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PAIRED_WORKFLOW.map((step, index) => (
            <motion.li
              key={step.title}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.05 * index }}
              className="card card-hover p-4 space-y-2"
            >
              <div className="flex items-center gap-2">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md border border-accent/25 bg-accent/10 font-mono text-2xs font-bold text-accent">
                  {index + 1}
                </span>
                <step.icon className="h-4 w-4 text-accent" aria-hidden />
              </div>
              <h3 className="text-xs font-bold text-ink">{step.title}</h3>
              <p className="text-2xs leading-relaxed text-ink-muted">{step.body}</p>
            </motion.li>
          ))}
        </ol>
      </section>

      {/* --- Capabilities ------------------------------------------------ */}
      <section className="relative z-10 mx-auto max-w-7xl px-6 pb-10">
        <div className="grid gap-3 lg:grid-cols-2">
          <Capability
            icon={Activity}
            tone="accent"
            label="Steered MD Force-Extension"
            title="Stiffness, measured in pN/nm"
            body="A moving harmonic restraint pulls the domain apart by its termini and records the force it carries against extension. The slope is an apparent stiffness: the primary physical measurement."
            facts={[
              '520 paired pristine-vs-damaged experiments',
              'Ranked titin I27 first, the experimental AFM benchmark',
              'Fits below noise threshold are rejected, not reported',
            ]}
          />
          <Capability
            icon={Cpu}
            tone="ok"
            label="OpenMM Simulation Engine"
            title="Real molecular dynamics physics"
            body="Amber14 with GBn2 implicit solvent, Langevin integrator and fixed seeds. Output includes genuine OpenMM trajectories, forces, energies, and RMSD metrics."
            facts={[
              'Steered MD pulling with force constant k_pull',
              'Explicit force-extension curve generation',
              'Strict safety & wall-clock execution bounds',
            ]}
          />
          <Capability
            icon={Sparkles}
            tone="violet"
            label="ML Prediction (Demo Mode)"
            title="Fast per-residue triage assistant"
            body="Gradient-boosted model ranking radiosensitive residues in milliseconds before compute-intensive MD simulation runs. Accelerates target residue selection."
            facts={[
              'Trained on 520 paired MD experiments',
              'Fast per-residue susceptibility ranking',
              'Distinctly separated from physical MD measurements',
            ]}
          />
          <Capability
            icon={Microscope}
            tone="violet"
            label="Structural Analysis"
            title="Auditable scientific metrics"
            body="RMSD, per-residue RMSF, radius of gyration, and force curves computed directly from PDB coordinates and OpenMM trajectories."
            facts={[
              'Every metric downloadable as JSON and CSV',
              'PDB structures & force curves exported',
              'Full reproducibility metadata per run',
            ]}
          />
        </div>
      </section>

      {/* --- Scope ------------------------------------------------------ */}
      <section className="relative z-10 mx-auto max-w-4xl px-6 pb-16">
        <ScopeNotice />
        <p className="mt-4 text-center text-2xs text-ink-faint">
          Every number links to the method that produced it ·{' '}
          <RouterLink to="/methodology" className="text-accent hover:underline">
            read the methodology
          </RouterLink>
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
