import { request, requestText } from './api'
import type {
  ProteinDetail,
  ProteinSummary,
  UploadedProtein,
} from '@/types/protein'

export const proteinKeys = {
  all: ['proteins'] as const,
  detail: (pdbId: string, topN = 10) => ['proteins', pdbId, topN] as const,
  structure: (pdbId: string) => ['proteins', pdbId, 'structure'] as const,
  uploadStructure: (uploadId: string) =>
    ['proteins', 'upload', uploadId, 'structure'] as const,
}

export function listProteins(signal?: AbortSignal) {
  return request<ProteinSummary[]>('/proteins', { signal })
}

export function getProtein(pdbId: string, topN = 10, signal?: AbortSignal) {
  return request<ProteinDetail>(`/proteins/${pdbId}?top_n=${topN}`, { signal })
}

/** Raw PDB text for the molecular viewer. */
export function getStructure(pdbId: string, signal?: AbortSignal) {
  return requestText(`/proteins/${pdbId}/structure`, signal)
}

export function getUploadedStructure(uploadId: string, signal?: AbortSignal) {
  return requestText(`/proteins/upload/${uploadId}/structure`, signal)
}

export function uploadProtein(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<UploadedProtein>('/proteins/upload', {
    method: 'POST',
    formData: form,
  })
}
