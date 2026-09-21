import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

type Theme = 'dark' | 'light'
type Motion = 'on' | 'off'

interface UiPrefs {
  theme: Theme
  toggleTheme: () => void
  motion: Motion
  toggleMotion: () => void
}

const Ctx = createContext<UiPrefs>({
  theme: 'dark', toggleTheme: () => {}, motion: 'on', toggleMotion: () => {},
})

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('cdk16-theme')
    return saved === 'light' || saved === 'dark' ? saved : 'dark'
  })
  // Animations are ON by default; users (or embedded browsers that misreport
  // reduced-motion) can switch them off — stored under cdk16-motion.
  // 'auto' would defer to prefers-reduced-motion, but several embedded webviews
  // report reduce incorrectly, so the default is explicit 'on'.
  const [motion, setMotion] = useState<Motion>(() =>
    localStorage.getItem('cdk16-motion') === 'off' ? 'off' : 'on')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('cdk16-theme', theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.setAttribute('data-motion', motion)
    localStorage.setItem('cdk16-motion', motion)
  }, [motion])

  return (
    <Ctx.Provider value={{
      theme,
      toggleTheme: () => setTheme(t => (t === 'dark' ? 'light' : 'dark')),
      motion,
      toggleMotion: () => setMotion(m => (m === 'on' ? 'off' : 'on')),
    }}>
      {children}
    </Ctx.Provider>
  )
}

export const useTheme = () => useContext(Ctx)
