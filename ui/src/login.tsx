import { useEffect, useRef, useState, type FormEvent } from 'react'
import { REGEXP_ONLY_DIGITS } from 'input-otp'
import { CircleCheckIcon, LockIcon, ShieldCheckIcon, UserIcon } from 'lucide-react'
import { cn } from 'cn'

import type { ViewProps } from '@/app'
import { Button } from '@/components/ui/button'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from '@/components/ui/input-group'
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp'
import { Switch } from '@/components/ui/switch'
import { Card, EyeIcon, Pending, useCountdown, useHeight } from '@/controls'

const STEPS = { credentials: 0, verify: 1, done: 2 }

/** One card whose steps slide sideways while its height follows the visible step. */
export function Login(props: ViewProps) {
  const step = STEPS[props.state.stage]
  // The success step is left unmeasured, so it keeps the size of the step before it.
  const [measure, height] = useHeight()
  const steps = [<Credentials {...props} />, <Verification {...props} />, <Success height={height} />]
  return (
    <Card title="统一身份认证" className="max-w-[360px]">
      <div className="transition-[height] duration-200 ease-out" style={{ height: height || undefined }}>
        <div
          className="flex items-start gap-12 transition-transform duration-200 ease-out max-sm:gap-10"
          style={{ transform: `translateX(calc(${-step} * (100% + var(--spacing) * 12)))` }}
        >
          {steps.map((content, index) => (
            <div
              key={index}
              ref={index === step && step < 2 ? measure : undefined}
              inert={index !== step}
              className="w-full shrink-0"
            >
              {content}
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function Credentials({ state, busy, run, notify }: ViewProps) {
  const [username, setUsername] = useState(state.username)
  const [password, setPassword] = useState('')
  const [captcha, setCaptcha] = useState('')
  const [remember, setRemember] = useState(true)
  const [visible, setVisible] = useState(false)
  const locked = busy === 'login'

  function submit(event: FormEvent) {
    event.preventDefault()
    run('login', { username, password, captcha, remember }).then(notify)
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <InputGroup>
        <InputGroupAddon>
          <UserIcon />
        </InputGroupAddon>
        <InputGroupInput
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="请输入学号"
          autoComplete="username"
          aria-label="学号"
          disabled={locked}
        />
      </InputGroup>
      <InputGroup>
        <InputGroupAddon>
          <LockIcon />
        </InputGroupAddon>
        <InputGroupInput
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          type={visible ? 'text' : 'password'}
          placeholder={state.saved && username === state.username ? '使用已保存的密码' : '请输入密码'}
          autoComplete="current-password"
          aria-label="密码"
          disabled={locked}
        />
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            aria-label={visible ? '隐藏密码' : '显示密码'}
            aria-pressed={visible}
            onClick={() => setVisible(!visible)}
          >
            <EyeIcon crossed={!visible} />
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
      {state.captcha && (
        <InputGroup>
          <InputGroupAddon>
            <ShieldCheckIcon />
          </InputGroupAddon>
          <InputGroupInput
            value={captcha}
            onChange={(event) => setCaptcha(event.target.value)}
            placeholder="请输入图中字符"
            autoComplete="off"
            aria-label="图形验证码"
            disabled={locked}
          />
          <img src={state.captcha} alt="图形验证码" className="mr-1.5 h-7 rounded-sm" />
        </InputGroup>
      )}
      <label className="mt-1 flex w-fit items-center gap-2 text-sm text-muted-foreground">
        记住账户
        <Switch checked={remember} onCheckedChange={setRemember} disabled={locked} />
      </label>
      <Button type="submit" className="mt-2" disabled={locked}>
        <Pending active={locked}>登录</Pending>
      </Button>
    </form>
  )
}

function Verification({ state, busy, run }: ViewProps) {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const input = useRef<HTMLInputElement>(null)
  const wait = useCountdown(state.resend_at)
  const sending = state.sending || busy === 'resend'
  const verifying = busy === 'verify'
  const ready = state.stage === 'verify' && !sending && !verifying

  useEffect(() => {
    if (ready) input.current?.focus({ preventScroll: true })
  }, [ready])

  useEffect(() => {
    if (!error) return
    const timer = setTimeout(() => setError(''), 1800)
    return () => clearTimeout(timer)
  }, [error])

  async function verify(value: string) {
    const failure = await run('verify', { code: value })
    if (failure) {
      setCode('')
      setError(failure)
    }
  }

  async function resend() {
    setError(await run('resend'))
  }

  function cancel() {
    setCode('')
    setError('')
    run('cancel')
  }

  const phone = state.phone || '绑定手机'
  const message =
    error ||
    (sending ? `正在发送验证码至 ${phone}` : state.resend_at ? `验证码已发送至 ${phone}` : '验证码未发送，请重新发送')

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3 text-xs whitespace-nowrap">
        <p className={cn('truncate', error && 'text-destructive')}>{message}</p>
        <button
          type="button"
          className="underline underline-offset-4 tabular-nums disabled:text-muted-foreground disabled:no-underline"
          disabled={sending || verifying || wait > 0}
          onClick={resend}
        >
          <Pending active={sending}>{wait ? `${wait} 秒后重新发送` : '重新发送'}</Pending>
        </button>
      </div>
      <InputOTP
        ref={input}
        maxLength={6}
        pattern={REGEXP_ONLY_DIGITS}
        value={code}
        onChange={setCode}
        onComplete={verify}
        disabled={!ready}
        aria-label="短信验证码"
        containerClassName="p-[3px]"
      >
        <InputOTPGroup className="grid w-full grid-cols-6 gap-2">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <InputOTPSlot
              key={index}
              index={index}
              aria-invalid={Boolean(error)}
              className="aspect-square rounded-lg bg-muted/40 text-2xl font-medium tabular-nums shadow-[inset_0_1px_2px_#0000000a,inset_0_-1px_2px_#00000005] data-[filled=true]:border-ring group-has-disabled/otp:bg-muted group-has-disabled/otp:text-muted-foreground"
            />
          ))}
        </InputOTPGroup>
      </InputOTP>
      <Button variant="secondary" disabled={verifying} onClick={cancel}>
        <Pending active={verifying}>{verifying ? '验证中' : '取消'}</Pending>
      </Button>
    </div>
  )
}

function Success({ height }: { height: number }) {
  return (
    <div role="status" className="flex flex-col items-center justify-center gap-2 text-center" style={{ height }}>
      <CircleCheckIcon className="size-10 text-green-600 dark:text-green-500" strokeWidth={1.5} />
      <p className="text-base">登录成功</p>
      <p className="text-xs text-muted-foreground">可以关闭此页面了</p>
    </div>
  )
}
