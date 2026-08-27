import { ExternalLink } from 'lucide-react'

import { Tooltip } from '@/components/ui/Tooltip'
import type { ProteinDetail } from '@/types/protein'
import { fmtMolecularWeight, fmtNumber, fmtPercent } from '@/utils/formatters'

export function ProteinSummary({ protein }: { protein: ProteinDetail }) {
  const rows: { label: string; value: string; help?: string }[] = [
    { label: 'Chain', value: protein.chain_id },
    {
      label: 'Residues',
      value: `${protein.protein_length}`,
      help:
        'Standard amino acids carrying a Cα atom. Residues with an incomplete ' +
        'backbone are excluded, matching the table the ML model was trained on.',
    },
    { label: 'Molecular weight', value: fmtMolecularWeight(protein.molecular_weight) },
    {
      label: 'Hydrophobic fraction',
      value: fmtPercent(protein.hydrophobic_fraction * 100, 1),
      help:
        'Fraction of residues in {A, F, I, L, M, V, W, Y}. This exact set was ' +
        'recovered from the training data, and is an ML model input.',
    },
    {
      label: 'Charged fraction',
      value: fmtPercent(protein.charged_fraction * 100, 1),
      help:
        'Fraction of residues in {D, E, K, R}. Histidine is deliberately excluded, ' +
        'matching the training data. This is an ML model input.',
    },
    {
      label: 'Method',
      value: protein.experiment_method ?? '—',
      help: 'Experimental method used to determine the deposited structure.',
    },
    {
      label: 'Resolution',
      value: protein.resolution_angstrom
        ? `${fmtNumber(protein.resolution_angstrom, 2)} Å`
        : 'n/a (NMR)',
    },
  ]

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-baseline gap-2">
          <h3 className="font-mono text-sm font-semibold text-ink">{protein.pdb_id}</h3>
          <span className="text-xs text-ink-muted">{protein.name}</span>
        </div>
        <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">
          {protein.why_selected}
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
        {rows.map((row) => (
          <div key={row.label} className="min-w-0">
            <dt className="flex items-center gap-1 text-2xs text-ink-faint">
              {row.label}
              {row.help && <Tooltip width="md" content={row.help} />}
            </dt>
            <dd className="tabular mt-0.5 truncate font-mono text-xs text-ink">
              {row.value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="hairline-divider" />

      <div className="space-y-1.5">
        <p className="text-2xs leading-relaxed text-ink-faint">
          <span className="text-ink-muted">Proposed mechanical role:</span>{' '}
          {protein.proposed_role}
        </p>
        <p className="text-2xs leading-relaxed text-ink-faint">
          <span className="text-ink-muted">Provenance:</span> {protein.source}.{' '}
          {protein.license_note}
        </p>
        {protein.uniprot && (
          <a
            href={`https://www.uniprot.org/uniprotkb/${protein.uniprot}`}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 text-2xs text-accent hover:underline"
          >
            UniProt {protein.uniprot}
            <ExternalLink className="h-2.5 w-2.5" aria-hidden />
          </a>
        )}
      </div>
    </div>
  )
}
