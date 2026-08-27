/**
 * Experiment draft state.
 *
 * Only the *draft configuration* and the last job id are persisted. Uploaded
 * coordinates are never written to localStorage — they can be megabytes, they
 * are the user's data, and the backend already holds them under an id.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import type { DoseUnit } from '@/types/prediction'
import type { StructureRef } from '@/types/protein'

const STORAGE_KEY = 'bionano-sim.experiment-draft.v1'

export interface ExperimentDraft {
  pdbId: string | null
  uploadId: string | null
  uploadFilename: string | null
  chainId: string
  scenarioId: string
  presetId: string
  dose: number
  doseUnit: DoseUnit
  exposureDurationDays: number
  temperatureKelvin: number
  mechanicalForcePn: number
  randomSeed: number
  topNResidues: number
}

export const DEFAULT_DRAFT: ExperimentDraft = {
  pdbId: '1UBQ',
  uploadId: null,
  uploadFilename: null,
  chainId: 'A',
  scenarioId: 'GCR_DEEP_SPACE_REFERENCE',
  presetId: 'rapid_demo',
  dose: 0.5,
  doseUnit: 'Gy',
  exposureDurationDays: 180,
  temperatureKelvin: 300,
  mechanicalForcePn: 0,
  randomSeed: 42,
  topNResidues: 10,
}

interface ExperimentState {
  draft: ExperimentDraft
  lastJobId: string | null
  /** Job ids selected on the Compare page. Not persisted. */
  compareSelection: string[]

  setDraft: (patch: Partial<ExperimentDraft>) => void
  selectApprovedProtein: (pdbId: string, chainId?: string) => void
  selectUpload: (uploadId: string, filename: string, chainId: string) => void
  applyScenarioDefaults: (
    scenarioId: string,
    defaults: Partial<ExperimentDraft>,
  ) => void
  resetDraft: () => void
  setLastJobId: (jobId: string | null) => void
  toggleCompare: (jobId: string) => void
  clearCompare: () => void
}

export const useExperimentStore = create<ExperimentState>()(
  persist(
    (set) => ({
      draft: DEFAULT_DRAFT,
      lastJobId: null,
      compareSelection: [],

      setDraft: (patch) => set((state) => ({ draft: { ...state.draft, ...patch } })),

      selectApprovedProtein: (pdbId, chainId = 'A') =>
        set((state) => ({
          draft: {
            ...state.draft,
            pdbId,
            chainId,
            // Selecting an approved protein clears any upload: the request
            // schema accepts exactly one of the two.
            uploadId: null,
            uploadFilename: null,
          },
        })),

      selectUpload: (uploadId, filename, chainId) =>
        set((state) => ({
          draft: {
            ...state.draft,
            uploadId,
            uploadFilename: filename,
            chainId,
            pdbId: null,
          },
        })),

      applyScenarioDefaults: (scenarioId, defaults) =>
        set((state) => ({
          draft: { ...state.draft, ...defaults, scenarioId },
        })),

      resetDraft: () => set({ draft: DEFAULT_DRAFT }),

      setLastJobId: (jobId) => set({ lastJobId: jobId }),

      toggleCompare: (jobId) =>
        set((state) => {
          const selected = state.compareSelection.includes(jobId)
          if (selected) {
            return { compareSelection: state.compareSelection.filter((id) => id !== jobId) }
          }
          // Keep at most two; the newest replaces the oldest.
          const next = [...state.compareSelection, jobId]
          return { compareSelection: next.slice(-2) }
        }),

      clearCompare: () => set({ compareSelection: [] }),
    }),
    {
      name: STORAGE_KEY,
      version: 1,
      // Deliberately excludes compareSelection and any structure content.
      partialize: (state) => ({ draft: state.draft, lastJobId: state.lastJobId }),
      merge: (persisted, current) => {
        // Tolerate a partial or stale persisted draft without throwing.
        const saved = persisted as Partial<ExperimentState> | undefined
        return {
          ...current,
          ...saved,
          draft: { ...DEFAULT_DRAFT, ...(saved?.draft ?? {}) },
          compareSelection: [],
        }
      },
    },
  ),
)

/** Derive the API-shaped structure reference from the draft. */
export function structureRefFromDraft(draft: ExperimentDraft): StructureRef | null {
  if (draft.uploadId) {
    return {
      kind: 'upload',
      uploadId: draft.uploadId,
      chainId: draft.chainId,
      filename: draft.uploadFilename ?? 'uploaded.pdb',
    }
  }
  if (draft.pdbId) {
    return { kind: 'approved', pdbId: draft.pdbId, chainId: draft.chainId }
  }
  return null
}
