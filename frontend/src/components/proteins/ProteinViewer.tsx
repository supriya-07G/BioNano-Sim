import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Camera,
  Maximize2,
  Minimize2,
  Palette,
  RotateCw,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { cn } from '@/components/ui/cn'
import { useTheme } from '@/hooks/useTheme'
import { load3Dmol, type Mol3DAtom, type Mol3DViewer } from './viewerLoader'

export type RenderMode = 'cartoon' | 'surface' | 'stick' | 'sphere'
export type ColourMode = 'chain' | 'spectrum' | 'element' | 'susceptibility'

export interface HighlightResidue {
  chainId: string
  seqNum: number
  /** Higher means more emphasis; drives colour intensity. */
  weight?: number
  label?: string
}

interface ProteinViewerProps {
  /** Raw PDB text. */
  data: string | null | undefined
  isLoading?: boolean
  error?: unknown
  /** Second structure, drawn translucent for overlay comparison. */
  overlayData?: string | null
  overlayLabel?: string
  mode?: RenderMode
  colourMode?: ColourMode
  highlights?: HighlightResidue[]
  onResidueClick?: (residue: { chainId: string; seqNum: number; resName: string }) => void
  className?: string
  /** Filename stem for the screenshot download. */
  screenshotName?: string
  showControls?: boolean
  /** Slow autorotation, off by default so the structure stays readable. */
  autoSpin?: boolean
  onRetry?: () => void
}

const CHAIN_COLOURS = [
  '#38BDF8', '#8B5CF6', '#22C55E', '#F59E0B',
  '#EF4444', '#7DD3FC', '#A78BFA', '#4ADE80',
]

/**
 * Molecular viewport.
 *
 * The protein is the visual focus of the application, so the surrounding chrome
 * stays minimal and every control is a real operation on the loaded structure.
 * The viewer instance is created once and reused: re-creating it on every style
 * change would flash and lose the camera.
 */
export function ProteinViewer({
  data,
  isLoading = false,
  error,
  overlayData,
  overlayLabel,
  mode = 'cartoon',
  colourMode = 'chain',
  highlights = [],
  onResidueClick,
  className,
  screenshotName = 'bionano-structure',
  showControls = true,
  autoSpin = false,
  onRetry,
}: ProteinViewerProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const { resolvedTheme } = useTheme()

  const viewerBackground = () =>
    getComputedStyle(document.documentElement).getPropertyValue('--theme-viewer-bg').trim() || '#050816'
  const viewerRef = useRef<Mol3DViewer | null>(null)
  const [engineError, setEngineError] = useState<Error | null>(null)
  const [engineReady, setEngineReady] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [hovered, setHovered] = useState<string | null>(null)

  // --- create the viewer once ------------------------------------------
  useEffect(() => {
    let cancelled = false
    load3Dmol()
      .then((mol) => {
        if (cancelled || !hostRef.current) return
        viewerRef.current = mol.createViewer(hostRef.current, {
          backgroundColor: viewerBackground(),
          antialias: true,
brightness: 0.9,
        })
        setEngineReady(true)
      })
      .catch((cause: Error) => {
        if (!cancelled) setEngineError(cause)
      })

    return () => {
      cancelled = true
      try {
        viewerRef.current?.clear()
      } catch {
        // The WebGL context may already be gone on unmount; nothing to do.
      }
      viewerRef.current = null
    }
  }, [])

  // Keep the WebGL viewport background in sync with the semantic theme.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!engineReady || !viewer) return
    viewer.setBackgroundColor(viewerBackground())
    viewer.render()
  }, [engineReady, resolvedTheme])

  // --- apply styles -----------------------------------------------------
  const applyStyles = useCallback(
    (viewer: Mol3DViewer) => {
      const mol = window.$3Dmol
      if (!mol) return

      const base: Record<string, unknown> = {}
      if (colourMode === 'spectrum') base.color = 'spectrum'
      else if (colourMode === 'element') base.colorscheme = 'default'
      else base.colorfunc = undefined

      const chainColour = (atom: Mol3DAtom) => {
        const index = atom.chain ? atom.chain.charCodeAt(0) % CHAIN_COLOURS.length : 0
        return CHAIN_COLOURS[index]
      }

      const styleFor = (): Record<string, unknown> => {
        const colour =
          colourMode === 'spectrum'
            ? { color: 'spectrum' }
            : colourMode === 'element'
              ? { colorscheme: 'Jmol' }
              : { colorfunc: chainColour }

        switch (mode) {
          case 'stick':
            return { stick: { radius: 0.14, ...colour } }
          case 'sphere':
            return { sphere: { scale: 0.28, ...colour } }
          case 'surface':
            // A cartoon underneath keeps the fold legible through the surface.
            return { cartoon: { thickness: 0.32, arrows: true, ...colour } }
          case 'cartoon':
          default:
            return { cartoon: { thickness: 0.45, arrows: true, tubes: false, ...colour } }
        }
      }

      viewer.setStyle({}, styleFor())
      viewer.removeAllSurfaces()

      if (mode === 'surface') {
        viewer.addSurface(mol.SurfaceType.VDW, {
          opacity: 0.62,
          color: '#38BDF8',
        })
      }

      // Overlay: the second structure in a distinct violet, translucent, so
      // both folds remain visible where they diverge.
      if (overlayData) {
        viewer.setStyle(
          { model: 1 },
          { cartoon: { color: '#8B5CF6', thickness: 0.34, opacity: 0.55 } },
        )
      }

      // Highlights sit on top as coloured sticks plus a sphere, so a selected
      // residue is visible even inside a cartoon or surface.
      for (const highlight of highlights) {
        const weight = highlight.weight ?? 1
        const colour =
          weight > 0.66 ? '#EF4444' : weight > 0.33 ? '#F59E0B' : '#38BDF8'
        const selection = {
          chain: highlight.chainId,
          resi: highlight.seqNum,
          model: 0,
        }
        viewer.addStyle(selection, {
          stick: { radius: 0.3, color: colour },
          sphere: { scale: 0.34, color: colour },
        })
      }

      viewer.render()
    },
    [colourMode, highlights, mode, overlayData],
  )

  // --- load models ------------------------------------------------------
  useEffect(() => {
    const viewer = viewerRef.current
    if (!engineReady || !viewer || !data) return

    try {
      viewer.removeAllModels()
      viewer.removeAllLabels()
      viewer.addModel(data, 'pdb')
      if (overlayData) viewer.addModel(overlayData, 'pdb')

      if (onResidueClick) {
        viewer.setClickable({}, true, (atom) => {
          onResidueClick({
            chainId: atom.chain,
            seqNum: atom.resi,
            resName: atom.resn,
          })
        })
      }
      viewer.setHoverable(
        {},
        true,
        (atom) => setHovered(`${atom.chain}:${atom.resi} ${atom.resn}`),
        () => setHovered(null),
      )

      applyStyles(viewer)
      viewer.zoomTo()
      viewer.render()
    } catch (cause) {
      setEngineError(
        cause instanceof Error ? cause : new Error('Failed to render the structure.'),
      )
    }
  }, [applyStyles, data, engineReady, onResidueClick, overlayData])

  // Restyle without reloading when only presentation changes.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!engineReady || !viewer || !data) return
    applyStyles(viewer)
  }, [applyStyles, data, engineReady])

  useEffect(() => {
    const viewer = viewerRef.current
    if (!engineReady || !viewer) return
    viewer.spin(autoSpin ? 'y' : false)
  }, [autoSpin, engineReady])

  // Keep the canvas sized to its container (panel resize, fullscreen toggle).
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const observer = new ResizeObserver(() => {
      try {
        viewerRef.current?.resize()
        viewerRef.current?.render()
      } catch {
        // Resizing a disposed viewer is harmless.
      }
    })
    observer.observe(host)
    return () => observer.disconnect()
  }, [])

  // Escape leaves fullscreen.
  useEffect(() => {
    if (!fullscreen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setFullscreen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [fullscreen])

  const screenshot = () => {
    const viewer = viewerRef.current
    if (!viewer) return
    try {
      const uri = viewer.pngURI()
      const anchor = document.createElement('a')
      anchor.href = uri
      anchor.download = `${screenshotName}.png`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
    } catch {
      setEngineError(new Error('Could not capture a screenshot of the viewport.'))
    }
  }

  const wrapper = cn(
    'relative overflow-hidden rounded-xl border border-hairline bg-void',
    fullscreen ? 'fixed inset-3 z-50 shadow-2xl' : 'h-full w-full',
    className,
  )

  if (engineError) {
    return (
      <div className={wrapper}>
        <ErrorState
          error={engineError}
          title="Molecular viewer unavailable"
          className="m-4"
          onRetry={onRetry}
        />
      </div>
    )
  }

  return (
    <div className={wrapper}>
      <div ref={hostRef} className="absolute inset-0" />

      {(isLoading || (!engineReady && !error)) && (
        <div className="absolute inset-0 grid place-items-center bg-void/85">
          <LoadingState label={engineReady ? 'Loading structure…' : 'Starting viewer…'} />
        </div>
      )}

      {Boolean(error) && !isLoading && (
        <div className="absolute inset-0 grid place-items-center bg-void/90 p-4">
          <ErrorState error={error} title="Could not load structure" onRetry={onRetry} />
        </div>
      )}

      {!data && !isLoading && !error && engineReady && (
        <div className="absolute inset-0 grid place-items-center">
          <p className="text-xs text-ink-faint">No structure selected.</p>
        </div>
      )}

      {/* Controls */}
      {showControls && data && (
        <div className="absolute right-2 top-2 flex flex-col gap-1">
          <ViewerButton onClick={() => viewerRef.current?.zoom(1.2, 260)} title="Zoom in">
            <ZoomIn className="h-3.5 w-3.5" aria-hidden />
          </ViewerButton>
          <ViewerButton onClick={() => viewerRef.current?.zoom(0.8, 260)} title="Zoom out">
            <ZoomOut className="h-3.5 w-3.5" aria-hidden />
          </ViewerButton>
          <ViewerButton
            onClick={() => {
              viewerRef.current?.zoomTo()
              viewerRef.current?.render()
            }}
            title="Reset view"
          >
            <RotateCw className="h-3.5 w-3.5" aria-hidden />
          </ViewerButton>
          <ViewerButton onClick={screenshot} title="Download screenshot (PNG)">
            <Camera className="h-3.5 w-3.5" aria-hidden />
          </ViewerButton>
          <ViewerButton
            onClick={() => setFullscreen((value) => !value)}
            title={fullscreen ? 'Exit full screen (Esc)' : 'Full screen'}
          >
            {fullscreen ? (
              <Minimize2 className="h-3.5 w-3.5" aria-hidden />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" aria-hidden />
            )}
          </ViewerButton>
        </div>
      )}

      {/* Legend */}
      {data && (
        <div className="pointer-events-none absolute bottom-2 left-2 flex flex-col gap-1.5">
          <div className="pointer-events-auto flex items-center gap-2 rounded-md border border-hairline bg-surface/90 px-2 py-1 backdrop-blur">
            <Palette className="h-3 w-3 text-ink-faint" aria-hidden />
            <span className="text-2xs capitalize text-ink-muted">
              {mode} · {colourMode}
            </span>
          </div>

          {overlayData && (
            <div className="pointer-events-auto flex flex-col gap-1 rounded-md border border-hairline bg-surface/90 px-2 py-1.5 backdrop-blur">
              <LegendRow colour="#38BDF8" label="Original structure" />
              <LegendRow colour="#8B5CF6" label={overlayLabel ?? 'Final structure'} />
            </div>
          )}

          {highlights.length > 0 && (
            <div className="pointer-events-auto flex flex-col gap-1 rounded-md border border-hairline bg-surface/90 px-2 py-1.5 backdrop-blur">
              <span className="text-2xs font-medium text-ink">
                Candidate residues ({highlights.length})
              </span>
              <LegendRow colour="#EF4444" label="Higher predicted degradation" />
              <LegendRow colour="#38BDF8" label="Lower predicted degradation" />
            </div>
          )}
        </div>
      )}

      {hovered && (
        <div className="pointer-events-none absolute bottom-2 right-2 rounded-md border border-accent/30 bg-surface/95 px-2 py-1 font-mono text-2xs text-accent backdrop-blur">
          {hovered}
        </div>
      )}
    </div>
  )
}

function ViewerButton({
  onClick,
  title,
  children,
}: {
  onClick: () => void
  title: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className="rounded-md border border-hairline bg-surface/90 p-1.5 text-ink-muted backdrop-blur transition-colors hover:border-accent/45 hover:text-accent"
    >
      {children}
    </button>
  )
}

function LegendRow({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-2xs text-ink-muted">
      <span
        className="h-2 w-2 shrink-0 rounded-sm"
        style={{ backgroundColor: colour }}
        aria-hidden
      />
      {label}
    </span>
  )
}
