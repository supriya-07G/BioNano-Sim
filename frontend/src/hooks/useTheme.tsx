/* eslint-disable react-refresh/only-export-components */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'bionano-theme'

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  return mode === 'system' ? getSystemTheme() : mode
}

function applyTheme(theme: ResolvedTheme) {
  const root = document.documentElement
  root.dataset.theme = theme
  root.style.colorScheme = theme
  root.classList.toggle('dark', theme === 'dark')

  const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
  if (meta) meta.content = theme === 'dark' ? '#050816' : '#F4F7FB'
}

interface ThemeContextValue {
  mode: ThemeMode
  resolvedTheme: ResolvedTheme
  setMode: (mode: ThemeMode) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'system'
  })

  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => resolveTheme(mode))

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, mode)

    const update = () => {
      const next = resolveTheme(mode)
      setResolvedTheme(next)
      applyTheme(next)
    }

    update()

    if (mode !== 'system') return

    const media = window.matchMedia('(prefers-color-scheme: dark)')
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [mode])

  const value = useMemo(
    () => ({ mode, resolvedTheme, setMode }),
    [mode, resolvedTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used inside ThemeProvider')
  return context
}
