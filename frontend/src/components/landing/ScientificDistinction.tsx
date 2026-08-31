import { Activity, Radiation, Scissors, ShieldAlert } from 'lucide-react'

export function ScientificDistinction() {
  return (
    <section className="rounded-2xl border border-hairline bg-elevated/60 p-6 backdrop-blur space-y-4">
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-5 w-5 text-accent" />
        <h2 className="text-sm font-bold uppercase tracking-wider text-ink">
          Core Scientific Distinction: Environment vs Damage vs Testing
        </h2>
      </div>

      <div className="grid gap-4 sm:grid-cols-3 text-xs">
        {/* Card 1: Radiation Environment */}
        <div className="rounded-xl border border-hairline/80 bg-surface/80 p-4 space-y-2">
          <div className="flex items-center gap-2 text-ink font-semibold">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-warn/15 text-warn">
              <Radiation className="h-4 w-4" />
            </span>
            <span>1. Radiation Environment</span>
          </div>
          <p className="text-2xs leading-relaxed text-ink-muted">
            Solar particle events (SPE) & galactic cosmic rays (GCR). Serves as mission provenance and category risk classification — numeric dose does not enter the physics integrator.
          </p>
        </div>

        {/* Card 2: Controlled Damage Proxy */}
        <div className="rounded-xl border border-hairline/80 bg-surface/80 p-4 space-y-2">
          <div className="flex items-center gap-2 text-ink font-semibold">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet/15 text-violet">
              <Scissors className="h-4 w-4" />
            </span>
            <span>2. Controlled Damage Proxy</span>
          </div>
          <p className="text-2xs leading-relaxed text-ink-muted">
            Specific side-chain truncation / lesion applied at candidate residue positions (e.g. Lysine, Cysteine, Tyrosine) based on known radiosensitivity literature.
          </p>
        </div>

        {/* Card 3: Mechanical Testing */}
        <div className="rounded-xl border border-hairline/80 bg-surface/80 p-4 space-y-2">
          <div className="flex items-center gap-2 text-ink font-semibold">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/15 text-accent">
              <Activity className="h-4 w-4" />
            </span>
            <span>3. Steered MD Mechanical Test</span>
          </div>
          <p className="text-2xs leading-relaxed text-ink-muted">
            Physical OpenMM steered molecular dynamics. Domain is pulled along terminal vector; slope of force-extension curve yields exact apparent stiffness ($k$ in pN/nm).
          </p>
        </div>
      </div>
    </section>
  )
}
