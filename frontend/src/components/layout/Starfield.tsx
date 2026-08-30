import { useEffect, useRef } from 'react'
import { useTheme } from '@/hooks/useTheme'

import { cn } from '@/components/ui/cn'

interface StarfieldProps {
  className?: string
  density?: number
  /** Slow drift. Disabled automatically under prefers-reduced-motion. */
  animated?: boolean
}

interface Star {
  x: number
  y: number
  r: number
  alpha: number
  twinkle: number
  drift: number
}

/**
 * Canvas starfield.
 *
 * Deliberately restrained: small, dim, slow. It sits behind content at low
 * opacity and pauses entirely when the tab is hidden or the user has asked for
 * reduced motion, so it never competes with the protein structure for
 * attention or burns CPU while a simulation is running.
 */
export function Starfield({ className, density = 0.00013, animated = true }: StarfieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { resolvedTheme } = useTheme()

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const context = canvas.getContext('2d')
    if (!context) return

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const shouldAnimate = animated && !reduceMotion

    let stars: Star[] = []
    let frame = 0
    let raf = 0
    let width = 0
    let height = 0

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const rect = canvas.getBoundingClientRect()
      width = rect.width
      height = rect.height
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      context.setTransform(dpr, 0, 0, dpr, 0, 0)

      const count = Math.min(420, Math.max(60, Math.floor(width * height * density)))
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * 1.05 + 0.25,
        alpha: Math.random() * 0.5 + 0.16,
        twinkle: Math.random() * 0.014 + 0.003,
        drift: Math.random() * 0.014 + 0.003,
      }))
    }

    const draw = () => {
      context.clearRect(0, 0, width, height)
      for (const star of stars) {
        // A slow sine keeps the field alive without visible flicker.
        const pulse = shouldAnimate
          ? star.alpha + Math.sin(frame * star.twinkle) * 0.12
          : star.alpha
        context.globalAlpha = Math.max(0.05, Math.min(0.78, pulse))
        context.fillStyle = resolvedTheme === 'dark' ? '#CBE9FF' : '#0E7490'
        context.beginPath()
        context.arc(star.x, star.y, star.r, 0, Math.PI * 2)
        context.fill()

        if (shouldAnimate) {
          star.y += star.drift
          if (star.y > height + 2) {
            star.y = -2
            star.x = Math.random() * width
          }
        }
      }
      context.globalAlpha = 1
    }

    const loop = () => {
      frame += 1
      draw()
      raf = window.requestAnimationFrame(loop)
    }

    const stop = () => {
      if (raf) window.cancelAnimationFrame(raf)
      raf = 0
    }

    const start = () => {
      if (!raf && shouldAnimate) raf = window.requestAnimationFrame(loop)
    }

    // Pause when hidden: no reason to animate a background nobody can see.
    const onVisibility = () => (document.hidden ? stop() : start())

    resize()
    draw()
    start()

    const observer = new ResizeObserver(() => {
      resize()
      draw()
    })
    observer.observe(canvas)
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      stop()
      observer.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [animated, density, resolvedTheme])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={cn('pointer-events-none absolute inset-0 h-full w-full', className)}
    />
  )
}

/** Orbital arcs: a static, very low-contrast motif for hero areas. */
export function OrbitLines({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={cn('pointer-events-none absolute inset-0 h-full w-full', className)}
      viewBox="0 0 1200 600"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
    >
      <defs>
        <linearGradient id="orbit-stroke" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="rgb(var(--color-accent))" stopOpacity="0.24" />
          <stop offset="55%" stopColor="rgb(var(--color-violet))" stopOpacity="0.12" />
          <stop offset="100%" stopColor="rgb(var(--color-accent))" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g stroke="url(#orbit-stroke)" strokeWidth="1">
        <ellipse cx="600" cy="300" rx="520" ry="180" />
        <ellipse cx="600" cy="300" rx="380" ry="290" />
        <ellipse
          cx="600"
          cy="300"
          rx="470"
          ry="240"
          transform="rotate(-18 600 300)"
        />
      </g>
      <circle cx="1080" cy="238" r="2.5" fill="rgb(var(--color-accent))" opacity="0.5" />
      <circle cx="238" cy="392" r="2" fill="rgb(var(--color-violet))" opacity="0.42" />
    </svg>
  )
}
