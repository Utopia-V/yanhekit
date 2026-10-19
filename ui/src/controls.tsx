import { useEffect, useId, useLayoutEffect, useReducer, useState, type ReactNode } from 'react'
import { cn } from 'cn'
import { MoonIcon, SunIcon } from 'lucide-react'
import { AnimatePresence, m } from 'motion/react'

import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

export function Card({ title, className, children }: { title: string; className?: string; children: ReactNode }) {
  return (
    <section className={cn('w-full overflow-clip rounded-xl border bg-card p-6 shadow-xs max-sm:p-5', className)}>
      <header className="relative mb-6 flex items-center justify-center">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <ThemeToggle />
      </header>
      {children}
    </section>
  )
}

const dark = matchMedia('(prefers-color-scheme: dark)')

export function applyTheme() {
  const theme = localStorage.getItem('theme') ?? (dark.matches ? 'dark' : 'light')
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

dark.addEventListener('change', applyTheme)

function ThemeToggle() {
  function toggle() {
    localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'light' : 'dark')
    applyTheme()
  }
  return (
    <Button variant="ghost" size="icon" className="absolute right-0" aria-label="切换深浅色" onClick={toggle}>
      <SunIcon className="size-4 transition-transform duration-300 dark:scale-0 dark:-rotate-90" strokeWidth={1.5} />
      <MoonIcon
        className="absolute size-4 scale-0 rotate-90 transition-transform duration-300 dark:scale-100 dark:rotate-0"
        strokeWidth={1.5}
      />
    </Button>
  )
}

/** Button content whose spinner slides in from the left while the label stays centered. */
export function Pending({ active, children }: { active: boolean; children: ReactNode }) {
  return (
    <span className="inline-flex items-center">
      <AnimatePresence initial={false}>
        {active && (
          <m.span
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 'auto', opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="inline-flex overflow-hidden"
          >
            <Spinner className="mr-1 size-[1em]" />
          </m.span>
        )}
      </AnimatePresence>
      {children}
    </span>
  )
}

/** Lucide's eye, crossed out by a slash drawn from the top left. */
export function EyeIcon({ crossed }: { crossed: boolean }) {
  const mask = useId()
  const slash = { pathLength: crossed ? 1 : 0, opacity: crossed ? 1 : 0 }
  const transition = { duration: 0.28, ease: 'easeOut' } as const
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
      <mask id={mask}>
        <rect width="24" height="24" fill="white" stroke="none" />
        <m.path
          d="m2 2 20 20"
          stroke="black"
          strokeWidth={4.5}
          initial={false}
          animate={slash}
          transition={transition}
        />
      </mask>
      <g mask={`url(#${mask})`}>
        <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" />
        <circle cx="12" cy="12" r="3" />
      </g>
      <m.path d="m2 2 20 20" initial={false} animate={slash} transition={transition} />
    </svg>
  )
}

/** Measure an element's height; pass the returned callback as its ref. */
export function useHeight() {
  const [element, setElement] = useState<HTMLElement | null>(null)
  const [height, setHeight] = useState(0)
  useLayoutEffect(() => {
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setHeight(entry.borderBoxSize[0].blockSize))
    observer.observe(element)
    return () => observer.disconnect()
  }, [element])
  return [setElement, height] as const
}

/** Whole seconds left until a Unix time, refreshed every second. */
export function useCountdown(until: number) {
  const [, tick] = useReducer((count: number) => count + 1, 0)
  const left = Math.max(0, Math.ceil(until - Date.now() / 1000))
  useEffect(() => {
    if (!left) return
    const timer = setTimeout(tick, 1000)
    return () => clearTimeout(timer)
  }, [left])
  return left
}
