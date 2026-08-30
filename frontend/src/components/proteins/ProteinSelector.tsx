import { useRef, useState } from 'react'
import { Check, FileUp, Loader2, Sparkles, Upload, X } from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { SkeletonRows } from '@/components/common/LoadingState'
import { Tooltip } from '@/components/ui/Tooltip'
import { cn } from '@/components/ui/cn'
import { uploadProtein } from '@/services/proteins'
import type { ProteinSummary, UploadedProtein } from '@/types/protein'
import { fmtMolecularWeight } from '@/utils/formatters'
import { validatePdbFile } from '@/utils/validators'

interface ProteinSelectorProps {
  proteins: ProteinSummary[] | undefined
  isLoading: boolean
  error: unknown
  selectedPdbId: string | null
  selectedUploadId: string | null
  uploadFilename: string | null
  onSelectApproved: (pdbId: string, chainId: string) => void
  onSelectUpload: (upload: UploadedProtein) => void
  onClearUpload: () => void
  onRetry?: () => void
  disabled?: boolean
}

const SPLIT_LABELS: Record<string, { label: string; tone: string; help: string }> = {
  train: {
    label: 'train',
    tone: 'border-warn/40 bg-warn/10 text-warn',
    help:
      'This protein was in the model training set, so its ML estimate will look ' +
      'more accurate than it would on unseen data. Not a held-out result.',
  },
  validation: {
    label: 'held-out',
    tone: 'border-ok/40 bg-ok/10 text-ok',
    help:
      'Held out from training and used for validation (MAE 4.11 percentage ' +
      'points). This is an honest generalisation estimate.',
  },
  test: {
    label: 'held-out',
    tone: 'border-ok/40 bg-ok/10 text-ok',
    help:
      'Held out from training and used as the test protein (MAE 2.26 percentage ' +
      'points). This is an honest generalisation estimate.',
  },
}

export function ProteinSelector({
  proteins,
  isLoading,
  error,
  selectedPdbId,
  selectedUploadId,
  uploadFilename,
  onSelectApproved,
  onSelectUpload,
  onClearUpload,
  onRetry,
  disabled = false,
}: ProteinSelectorProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<unknown>(null)
  const [uploadWarnings, setUploadWarnings] = useState<string[]>([])

  const handleFile = async (file: File | undefined) => {
    if (!file) return
    setUploadError(null)
    setUploadWarnings([])

    const localProblem = validatePdbFile(file)
    if (localProblem) {
      setUploadError(new Error(localProblem))
      return
    }

    setUploading(true)
    try {
      const uploaded = await uploadProtein(file)
      setUploadWarnings(uploaded.warnings)
      onSelectUpload(uploaded)
    } catch (cause) {
      setUploadError(cause)
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  if (error) {
    return <ErrorState error={error} title="Could not load the protein registry" onRetry={onRetry} />
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="label">Approved proteins</span>
        <Tooltip
          content={
            <span>
              Five proteins are approved for this MVP. The badge shows whether the
              protein was in the mock model&rsquo;s training data: a{' '}
              <em>held-out</em> protein gives a more honest picture of how the model
              generalises.
            </span>
          }
        />
      </div>

      {isLoading && <SkeletonRows rows={5} />}

      {proteins && (
        <ul className="space-y-1.5">
          {proteins.map((protein) => {
            const active = !selectedUploadId && selectedPdbId === protein.pdb_id
            const split = SPLIT_LABELS[protein.ml_dataset_split]
            return (
              <li key={protein.pdb_id}>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => onSelectApproved(protein.pdb_id, protein.chain_id)}
                  className={cn(
                    'w-full rounded-lg border p-2.5 text-left transition-colors duration-150',
                    active
                      ? 'border-accent/50 bg-accent/[0.08]'
                      : 'border-hairline bg-elevated hover:border-accent/35 hover:bg-raised',
                    disabled && 'cursor-not-allowed opacity-50',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-xs font-semibold text-ink">
                          {protein.pdb_id}
                        </span>
                        {protein.is_rapid_demo_default && (
                          <span
                            title="Recommended for the Rapid Demo: smallest fast-folding option with a held-out ML result."
                            aria-label="Recommended for the Rapid Demo"
                          >
                            <Sparkles className="h-3 w-3 text-accent" aria-hidden />
                          </span>
                        )}
                        {active && <Check className="h-3 w-3 text-accent" aria-hidden />}
                      </div>
                      <p className="mt-0.5 truncate text-xs text-ink">{protein.name}</p>
                      <p className="mt-0.5 truncate text-2xs text-ink-faint">
                        {protein.proposed_role}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      {split && (
                        // A plain title rather than a Tooltip: this sits inside
                        // the row's own button, and nesting interactive elements
                        // is invalid HTML.
                        <span className={cn('badge', split.tone)} title={split.help}>
                          {split.label}
                        </span>
                      )}
                      <span className="tabular font-mono text-2xs text-ink-faint">
                        {protein.protein_length} aa
                      </span>
                      <span className="tabular font-mono text-2xs text-ink-faint">
                        {fmtMolecularWeight(protein.molecular_weight)}
                      </span>
                    </div>
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {/* --- Upload ------------------------------------------------------ */}
      <div className="hairline-divider" />

      <div className="flex items-center justify-between">
        <span className="label">Custom structure</span>
        <Tooltip
          content={
            <span>
              Uploaded structures are validated then featurised by COSMORA&rsquo;s
              own extractor. One feature (<code>residue_sasa_norm</code>) correlates
              r&nbsp;=&nbsp;0.93&ndash;0.99 with the table the model was trained on but
              is not identical, so upload estimates are less faithful than those for
              the five approved proteins.
            </span>
          }
        />
      </div>

      {selectedUploadId ? (
        <div className="rounded-lg border border-violet/40 bg-violet/[0.07] p-2.5">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <FileUp className="h-3.5 w-3.5 shrink-0 text-violet" aria-hidden />
                <span className="truncate font-mono text-xs text-ink">
                  {uploadFilename}
                </span>
              </div>
              <p className="mt-1 text-2xs text-ink-muted">
                Features recomputed &mdash; approximate relative to the approved set.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setUploadWarnings([])
                onClearUpload()
              }}
              className="btn-ghost !p-1"
              aria-label="Remove uploaded structure"
              disabled={disabled}
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        </div>
      ) : (
        <>
          <input
            ref={inputRef}
            type="file"
            accept=".pdb,.ent"
            className="hidden"
            onChange={(event) => void handleFile(event.target.files?.[0])}
          />
          <button
            type="button"
            disabled={disabled || uploading}
            onClick={() => inputRef.current?.click()}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-hairline bg-elevated/50 px-3 py-3 text-xs text-ink-muted transition-colors hover:border-accent/40 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploading ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                Validating&hellip;
              </>
            ) : (
              <>
                <Upload className="h-3.5 w-3.5" aria-hidden />
                Upload a .pdb file (max 8 MB)
              </>
            )}
          </button>
        </>
      )}

      {Boolean(uploadError) && (
        <ErrorState
          error={uploadError}
          compact
          title="Upload rejected"
          onRetry={() => setUploadError(null)}
        />
      )}

      {uploadWarnings.length > 0 && (
        <ul className="space-y-1 rounded-lg border border-warn/25 bg-warn/[0.06] p-2.5">
          {uploadWarnings.map((warning, index) => (
            <li key={index} className="text-2xs leading-relaxed text-ink-muted">
              &bull; {warning}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
