import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import {
  Atom,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  FlaskConical,
  GitCompare,
  History,
  Info,
  LayoutDashboard,
  Radiation,
} from 'lucide-react'

import { cn } from '@/components/ui/cn'

const STORAGE_KEY = 'cosmora-sidebar-collapsed'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/experiment', label: 'Experiment', icon: FlaskConical },
  { to: '/simulation', label: 'Simulation', icon: Radiation },
  { to: '/results', label: 'Results', icon: Atom },
  { to: '/compare', label: 'Compare', icon: GitCompare },
  { to: '/history', label: 'History', icon: History },
  { to: '/methodology', label: 'Methodology', icon: BookOpen },
] as const

interface SidebarProps {
  className?: string
}

export function Sidebar({ className }: SidebarProps) {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(collapsed))
    } catch {
      // Ignore storage write failures (e.g. private browsing mode)
    }
  }, [collapsed])

  const toggleCollapsed = () => setCollapsed((prev) => !prev)

  return (
    <aside
      aria-label="Primary Navigation"
      className={cn(
        'relative flex shrink-0 flex-col border-r border-hairline bg-surface/80 shadow-[inset_-1px_0_0_rgba(255,255,255,0.02)] backdrop-blur-md transition-[width] duration-300 ease-crisp',
        collapsed ? 'w-16' : 'w-48 lg:w-56',
        className,
      )}
    >
      {/* Collapse / Expand Toggle Button Header */}
      <div
        className={cn(
          'flex items-center border-b border-hairline/60 p-2',
          collapsed ? 'justify-center' : 'justify-end',
        )}
      >
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="group relative flex h-8 w-8 items-center justify-center rounded-lg border border-hairline/60 bg-elevated/60 text-ink-muted transition-all duration-200 ease-crisp hover:border-accent/40 hover:bg-raised hover:text-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          {collapsed ? (
            <ChevronRight
              className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
              aria-hidden
            />
          ) : (
            <ChevronLeft
              className="h-4 w-4 transition-transform duration-200 group-hover:-translate-x-0.5"
              aria-hidden
            />
          )}
          {collapsed && (
            <span className="pointer-events-none absolute left-full ml-3 z-50 hidden rounded-md border border-hairline bg-elevated px-2 py-1 text-xs font-medium text-ink shadow-panel group-hover:block group-focus-visible:block whitespace-nowrap">
              Expand sidebar
            </span>
          )}
        </button>
      </div>

      <nav className="flex flex-1 flex-col justify-between overflow-y-auto overflow-x-hidden p-2">
        <ul className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <li key={to} className="relative">
              <NavLink
                to={to}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  cn(
                    'group relative flex items-center rounded-lg text-sm transition-all duration-200 ease-crisp',
                    collapsed ? 'h-10 w-full justify-center px-0' : 'gap-3 px-3 py-2',
                    isActive
                      ? 'bg-accent/[0.10] text-accent shadow-[inset_0_0_0_1px_rgba(204,194,255,0.18)]'
                      : 'text-ink-muted hover:bg-raised hover:text-ink',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn(
                        'h-4 w-4 shrink-0 transition-colors duration-200',
                        isActive
                          ? 'text-accent'
                          : 'text-ink-faint group-hover:text-ink-muted',
                      )}
                      aria-hidden
                    />
                    {!collapsed && <span className="truncate">{label}</span>}
                    {collapsed && (
                      <span className="pointer-events-none absolute left-full ml-3 z-50 hidden rounded-md border border-hairline bg-elevated px-2.5 py-1 text-xs font-medium text-ink shadow-panel group-hover:block group-focus-visible:block whitespace-nowrap">
                        {label}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer disclaimer */}
      <div className="border-t border-hairline bg-void/40 p-3">
        {collapsed ? (
          <div className="group relative flex justify-center">
            <span
              tabIndex={0}
              role="note"
              aria-label="MVP build disclaimer"
              className="flex h-6 w-6 cursor-help items-center justify-center rounded-full text-ink-faint transition-colors hover:text-accent focus-visible:text-accent focus-visible:outline-none"
            >
              <Info className="h-3.5 w-3.5" aria-hidden />
            </span>
            <span className="pointer-events-none absolute bottom-0 left-full ml-3 z-50 hidden w-60 rounded-md border border-hairline bg-elevated p-2.5 text-2xs leading-relaxed text-ink-muted shadow-panel group-hover:block group-focus-visible:block">
              MVP build. ML estimates are not experimentally validated; simulations are picosecond-scale.
            </span>
          </div>
        ) : (
          <p className="text-2xs leading-relaxed text-ink-faint">
            MVP build. ML estimates are not experimentally validated; simulations are
            picosecond-scale.
          </p>
        )}
      </div>
    </aside>
  )
}
