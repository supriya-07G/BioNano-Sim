/** Fetch raw PDB coordinates for the viewer. */

import { useQuery } from '@tanstack/react-query'

import { getStructure, getUploadedStructure, proteinKeys } from '@/services/proteins'
import { getJobStructure, getPrecomputedStructure } from '@/services/simulations'

export type StructureSource =
  | { kind: 'approved'; pdbId: string }
  | { kind: 'upload'; uploadId: string }
  | { kind: 'job'; jobId: string; which?: 'final' | 'prepared' | 'topology' | 'input' }
  | { kind: 'precomputed'; pdbId: string; which?: 'final' | 'input' }
  | null

function keyFor(source: StructureSource): readonly unknown[] {
  if (!source) return ['structure', 'none']
  switch (source.kind) {
    case 'approved':
      return proteinKeys.structure(source.pdbId)
    case 'upload':
      return proteinKeys.uploadStructure(source.uploadId)
    case 'job':
      return ['structure', 'job', source.jobId, source.which ?? 'final']
    case 'precomputed':
      return ['structure', 'precomputed', source.pdbId, source.which ?? 'final']
  }
}

function fetcher(source: StructureSource, signal: AbortSignal): Promise<string> {
  if (!source) return Promise.reject(new Error('No structure selected'))
  switch (source.kind) {
    case 'approved':
      return getStructure(source.pdbId, signal)
    case 'upload':
      return getUploadedStructure(source.uploadId, signal)
    case 'job':
      return getJobStructure(source.jobId, source.which ?? 'final', signal)
    case 'precomputed':
      return getPrecomputedStructure(source.pdbId, source.which ?? 'final', signal)
  }
}

export function useStructure(source: StructureSource) {
  return useQuery({
    queryKey: keyFor(source),
    queryFn: ({ signal }) => fetcher(source, signal),
    enabled: source !== null,
    // Coordinates are immutable for a given id.
    staleTime: Infinity,
    gcTime: 10 * 60_000,
    retry: 1,
  })
}
