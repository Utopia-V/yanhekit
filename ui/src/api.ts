export type View = 'teacher' | 'screen'

export interface Lecture {
  id: string
  sub_id: string
  duration_s?: number
  subtitles?: number
  slides?: number
  videos?: View[]
  dropped?: boolean
}

export interface CourseSummary {
  id: string
  title: string
  teacher: string
  term: string
}

export interface Course extends CourseSummary {
  folder: string
  lectures: Lecture[]
}

/** A lecture in the download queue; it leaves the queue when finished or cancelled. */
export interface Job {
  status: 'queued' | 'running' | 'paused' | 'failed'
  task?: 'subtitles' | 'slides' | View | 'pdf' | 'done'
  fraction?: number
  speed?: number | null
  remaining?: number | null
  error?: string | null
}

/** The server's shared state, pushed over /api/events after every change. */
export interface State {
  stage: 'checking' | 'credentials' | 'verify' | 'done'
  username: string
  saved: boolean
  captcha: string | null
  phone: string
  sending: boolean
  resend_at: number
  downloads: boolean
  courses: CourseSummary[]
  course: Course | null
  jobs: Record<string, Job>
  message: string
}

const token = location.hash.slice(1)

export async function post(action: string, body: object = {}) {
  let response: Response
  try {
    response = await fetch(`/api/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Token': token },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error('无法连接本地服务')
  }
  if (!response.ok) {
    const { error } = await response.json().catch(() => ({}))
    throw new Error(error ?? `请求失败（HTTP ${response.status}）`)
  }
}

export function subscribe(update: (state: State) => void, close: () => void) {
  const source = new EventSource(`/api/events?token=${token}`)
  source.onmessage = (event) => update(JSON.parse(event.data))
  source.onerror = () => {
    source.close()
    close()
  }
  return () => source.close()
}
