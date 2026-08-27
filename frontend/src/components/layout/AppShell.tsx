import { Outlet } from 'react-router-dom'

import { Sidebar } from './Sidebar'
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
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-void">
      {/* Fixed decorative ground; all content sits above it. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 bg-grid-fine opacity-50"
      />
      <div aria-hidden className="pointer-events-none fixed inset-0 bg-orbit-glow" />

      <div className="relative z-10 flex h-full flex-col">
        <Topbar />
        <div className="flex min-h-0 flex-1">
          <Sidebar className="w-48 lg:w-56" />
          <main className="min-w-0 flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
