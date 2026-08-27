/** Display formatting. Every function tolerates null/undefined/NaN. */

const EM_DASH = '—'

export function fmtNumber(
  value: number | null | undefined,
  digits = 2,
  fallback = EM_DASH,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return fallback
  return value.toFixed(digits)
}

export function fmtPercent(
  value: number | null | undefined,
  digits = 1,
  fallback = EM_DASH,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return fallback
  return `${value.toFixed(digits)}%`
}

/** Signed percentage-point difference, e.g. "+12.3 pp". */
export function fmtDelta(
  value: number | null | undefined,
  digits = 1,
  unit = 'pp',
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return EM_DASH
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(digits)} ${unit}`
}

export function fmtNm(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return EM_DASH
  return `${value.toFixed(digits)} nm`
}

export function fmtEnergy(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return EM_DASH
  return `${value.toLocaleString(undefined, {
    maximumFractionDigits: 0,
  })} kJ/mol`
}

export function fmtKelvin(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return EM_DASH
  return `${value.toFixed(digits)} K`
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) {
    return EM_DASH
  }
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`
  if (seconds < 60) return `${seconds.toFixed(1)} s`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  if (minutes < 60) return `${minutes}m ${rest}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

export function fmtBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return EM_DASH
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

/** Local date-time, or an em dash. */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return EM_DASH
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return EM_DASH
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function fmtRelativeTime(iso: string | null | undefined): string {
  if (!iso) return EM_DASH
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return EM_DASH
  const seconds = (Date.now() - date.getTime()) / 1000
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`
  return `${Math.floor(seconds / 86400)} d ago`
}

/** Short job id for display; the full id stays in tooltips and exports. */
export function shortId(id: string | null | undefined, length = 8): string {
  if (!id) return EM_DASH
  return id.slice(0, length)
}

/** 'energy_minimization' -> 'Energy minimization'. */
export function humanise(value: string | null | undefined): string {
  if (!value) return EM_DASH
  const spaced = value.replace(/[_-]+/g, ' ').trim()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

export function fmtMolecularWeight(daltons: number | null | undefined): string {
  if (daltons === null || daltons === undefined || !Number.isFinite(daltons)) {
    return EM_DASH
  }
  return `${(daltons / 1000).toFixed(2)} kDa`
}
