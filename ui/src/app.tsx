import { useEffect, useState } from 'react'
import { domAnimation, LazyMotion } from 'motion/react'

import { post, subscribe, type State } from '@/api'
import { Login } from '@/login'

/** What the app hands the sign-in card. */
export interface ViewProps {
  state: State
  /** The action being posted, if any. */
  busy: string | null
  /** Post an action and resolve to its error message, or '' on success. */
  run: (action: string, body?: object) => Promise<string>
  notify: (text: string) => void
}

export function App() {
  const [state, setState] = useState<State | null>(null)
  const [closed, setClosed] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState('')

  useEffect(() => subscribe(setState, () => setClosed(true)), [])
  useEffect(() => setNotice(''), [state?.stage])
  useEffect(() => {
    if (state?.message) setNotice(state.message)
  }, [state?.message])

  async function run(action: string, body?: object) {
    setBusy(action)
    setNotice('')
    try {
      await post(action, body)
      return ''
    } catch (error) {
      return (error as Error).message
    } finally {
      setBusy(null)
    }
  }

  // The server stops on its own once signed in.
  const stopped = closed && state?.stage !== 'done'
  const props = state && { state, busy, run, notify: setNotice }
  return (
    <LazyMotion features={domAnimation} strict>
      <main className="flex min-h-svh flex-col items-center justify-center gap-4 px-4 py-10 sm:px-8">
        {props && <Login {...props} />}
        <p role="status" className="min-h-10 max-w-[560px] text-center text-sm text-balance text-muted-foreground">
          {stopped ? '本地服务已停止，请重新运行命令' : notice}
        </p>
      </main>
    </LazyMotion>
  )
}
