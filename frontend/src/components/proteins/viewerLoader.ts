/**
 * Load the vendored 3Dmol.js UMD bundle on demand.
 *
 * 3Dmol is ~540 KB and only the viewer needs it, so it is injected as a script
 * tag the first time a viewer mounts rather than bundled into the main chunk.
 * The bundle is vendored under `public/vendor/` so the app works with no
 * network access.
 */

export interface Mol3DViewer {
  addModel: (data: string, format: string) => unknown
  setStyle: (selection: object, style: object) => void
  addStyle: (selection: object, style: object) => void
  addSurface: (type: unknown, style: object, selection?: object) => void
  removeAllSurfaces: () => void
  removeAllModels: () => void
  removeAllLabels: () => void
  addLabel: (text: string, options: object) => unknown
  setBackgroundColor: (color: number | string, alpha?: number) => void
  zoomTo: (selection?: object) => void
  zoom: (factor: number, duration?: number) => void
  center: (selection?: object) => void
  render: () => void
  resize: () => void
  clear: () => void
  spin: (axis: string | boolean) => void
  pngURI: () => string
  setClickable: (selection: object, clickable: boolean, callback: (atom: Mol3DAtom) => void) => void
  setHoverable: (
    selection: object,
    hoverable: boolean,
    onHover: (atom: Mol3DAtom) => void,
    onUnhover: (atom: Mol3DAtom) => void,
  ) => void
  getModel: (index?: number) => { selectedAtoms: (selection: object) => Mol3DAtom[] } | undefined
}

export interface Mol3DAtom {
  resi: number
  resn: string
  chain: string
  atom: string
  elem: string
  x: number
  y: number
  z: number
  serial: number
}

interface Mol3DGlobal {
  createViewer: (
    element: HTMLElement,
    config?: Record<string, unknown>,
  ) => Mol3DViewer
  SurfaceType: { VDW: unknown; SAS: unknown; MS: unknown; SES: unknown }
  elementColors: Record<string, unknown>
}

declare global {
  interface Window {
    $3Dmol?: Mol3DGlobal
  }
}

const SCRIPT_ID = 'bionano-3dmol'
const SCRIPT_SRC = '/vendor/3Dmol-min.js'
const FALLBACK_SCRIPT_SRC = 'https://3dmol.org/build/3Dmol-min.js'

let loadPromise: Promise<Mol3DGlobal> | null = null

export function load3Dmol(): Promise<Mol3DGlobal> {
  if (window.$3Dmol) return Promise.resolve(window.$3Dmol)
  if (loadPromise) return loadPromise

  loadPromise = new Promise<Mol3DGlobal>((resolve, reject) => {
    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null

    const settle = () => {
      if (window.$3Dmol) resolve(window.$3Dmol)
      else
        reject(
          new Error(
            'The 3Dmol viewer script loaded but did not register. Re-fetch it with: ' +
              'python scripts/setup_local.py',
          ),
        )
    }

    const tryScript = (src: string, fallbackSrc?: string) => {
      const script = document.createElement('script')
      script.id = SCRIPT_ID
      script.src = src
      script.async = true
      script.crossOrigin = 'anonymous'
      script.addEventListener('load', settle, { once: true })
      script.addEventListener(
        'error',
        () => {
          if (fallbackSrc) {
            const next = document.createElement('script')
            next.id = SCRIPT_ID
            next.src = fallbackSrc
            next.async = true
            next.crossOrigin = 'anonymous'
            next.addEventListener('load', settle, { once: true })
            next.addEventListener(
              'error',
              () => {
                loadPromise = null
                reject(
                  new Error(
                    'Could not load the molecular viewer from the local vendor bundle or the CDN. ' +
                      'The rest of the application still works.',
                  ),
                )
              },
              { once: true },
            )
            document.head.appendChild(next)
            return
          }

          loadPromise = null
          reject(
            new Error(
              'Could not load the molecular viewer (public/vendor/3Dmol-min.js is ' +
                'missing). The rest of the application still works.',
            ),
          )
        },
        { once: true },
      )
      document.head.appendChild(script)
    }

    if (existing) {
      existing.addEventListener('load', settle, { once: true })
      existing.addEventListener(
        'error',
        () => {
          existing.remove()
          tryScript(FALLBACK_SCRIPT_SRC)
        },
        { once: true },
      )
      return
    }

    tryScript(SCRIPT_SRC, FALLBACK_SCRIPT_SRC)
  })

  return loadPromise
}
