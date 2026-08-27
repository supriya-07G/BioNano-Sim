import type { WheelEvent } from 'react'

/**
 * Stop a mouse wheel from changing a focused `<input type="number">`,
 * `<input type="range">` or `<select>`.
 *
 * Browsers treat wheel-over-a-focused-control as increment/decrement. In a tall
 * scrolling configuration panel that is a genuine hazard: scrolling past the
 * dose field silently changes the dose, and the user has no idea the value they
 * submitted is not the value they set. Blurring on wheel makes the gesture do
 * what the user meant — scroll the panel — and leaves the value alone.
 */
export function blurOnWheel(event: WheelEvent<HTMLElement>): void {
  const element = event.currentTarget
  if (document.activeElement === element) {
    element.blur()
  }
}
