import { Outlet } from 'react-router-dom'

import { useTheme } from '@/hooks/useTheme'

import { Sidebar } from './Sidebar'
import { Starfield } from './Starfield'
import { Topbar } from './Topbar'

/**
 * Application chrome.
 *
 * A fixed viewport height with one scrolling main region, so pages that need to
 * fill the screen (the experiment workspace and its 3D viewport) can use
 * h-full without the page itself scrolling. This is what keeps the 1366x768
 * layout free of scrollbars around the viewer.
 */
export function AppShell() {
  const { resolvedTheme } = useTheme()

  return (
    <div
      data-theme={resolvedTheme}
      className="internal-app-theme flex h-screen flex-col overflow-hidden bg-void"
    >
      {/*
        First focusable element on the page, visually hidden until focused.
        Without it a keyboard user tabs through the whole sidebar on every
        navigation before reaching the content.
      */}
      <a
        href="#main-content"
        className="sr-only z-50 focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:rounded-md focus:bg-elevated focus:px-4 focus:py-2 focus:text-sm focus:text-ink focus:ring-2 focus:ring-accent"
      >
        Skip to main content
      </a>

      {/* Fixed decorative ground; all content sits above it. */}
      <div aria-hidden className="pointer-events-none fixed inset-0">
        <div className="absolute inset-0 bg-grid-fine opacity-40" />
        <div className="absolute inset-0 bg-orbit-glow opacity-75" />
        <Starfield density={0.00016} className="opacity-75" />
      </div>

      <div className="relative z-10 flex h-full flex-col">
        <Topbar />
        <div className="flex min-h-0 flex-1">
          <Sidebar className="w-48 lg:w-56" />
          <main
            id="main-content"
            tabIndex={-1}
            aria-label="Main content"
            className="min-w-0 flex-1 overflow-y-auto"
          >
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
