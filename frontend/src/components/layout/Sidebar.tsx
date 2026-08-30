import { NavLink } from 'react-router-dom'
import {
  Atom,
  BookOpen,
  FlaskConical,
  GitCompare,
  History,
  LayoutDashboard,
  Radiation,
} from 'lucide-react'

import { cn } from '@/components/ui/cn'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/experiment', label: 'Experiment', icon: FlaskConical },
  { to: '/simulation', label: 'Simulation', icon: Radiation },
  { to: '/results', label: 'Results', icon: Atom },
  { to: '/compare', label: 'Compare', icon: GitCompare },
  { to: '/history', label: 'History', icon: History },
  { to: '/methodology', label: 'Methodology', icon: BookOpen },
] as const

export function Sidebar({ className }: { className?: string }) {
  return (
    <nav
      className={cn(
        'flex shrink-0 flex-col border-r border-hairline bg-surface/80 shadow-[inset_-1px_0_0_rgba(255,255,255,0.02)] backdrop-blur-md',
        className,
      )}
      aria-label="Primary"
    >
      <ul className="flex flex-1 flex-col gap-0.5 p-2">
        {NAV.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              className={({ isActive }) =>
                cn(
                  'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-200 ease-crisp',
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
                      'h-4 w-4 shrink-0',
                      isActive
                        ? 'text-accent'
                        : 'text-ink-faint group-hover:text-ink-muted',
                    )}
                    aria-hidden
                  />
                  <span className="truncate">{label}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="border-t border-hairline bg-void/40 p-3">
        <p className="text-2xs leading-relaxed text-ink-faint">
          MVP build. ML estimates are not experimentally validated; simulations are
          picosecond-scale.
        </p>
      </div>
    </nav>
  )
}
