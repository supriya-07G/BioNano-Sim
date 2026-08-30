import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme, type ThemeMode } from '@/hooks/useTheme'

const OPTIONS: { value: ThemeMode; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

export function ThemeSwitcher() {
  const { mode, setMode } = useTheme()
  const active = OPTIONS.find((option) => option.value === mode) ?? OPTIONS[2]
  const Icon = active.icon

  return (
    <label className="inline-flex items-center gap-1.5 rounded-lg border border-hairline bg-elevated px-2 py-1.5 text-xs text-ink-muted">
      <Icon className="h-3.5 w-3.5 text-accent" aria-hidden />
      <span className="sr-only">Theme</span>

      <select
        aria-label="Theme"
        value={mode}
        onChange={(event) => {
          const next = event.target.value
          if (next === 'light' || next === 'dark' || next === 'system') {
            setMode(next)
          }
        }}
        className="theme-select cursor-pointer appearance-none bg-transparent pr-0 text-xs font-medium text-ink outline-none"
      >
        {OPTIONS.map(({ value, label }) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
    </label>
  )
}