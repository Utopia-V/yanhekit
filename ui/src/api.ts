/** The server's sign-in state, pushed over /api/events after every change. */
export interface State {
  stage: 'credentials' | 'verify' | 'done'
  username: string
  saved: boolean
  captcha: string | null
  phone: string
  sending: boolean
  resend_at: number
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
