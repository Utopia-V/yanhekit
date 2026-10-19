import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { cn } from 'cn'
import {
  CaptionsIcon,
  ChevronRightIcon,
  FileStackIcon,
  FolderIcon,
  GaugeIcon,
  MonitorIcon,
  PauseIcon,
  PlayIcon,
  PresentationIcon,
  RefreshCwIcon,
  RotateCwIcon,
  VideoIcon,
  XIcon,
  type LucideIcon,
} from 'lucide-react'
import { AnimatePresence, m } from 'motion/react'
import { Collapsible } from 'radix-ui'

import type { Course, Job, Lecture } from '@/api'
import type { ViewProps } from '@/app'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { InputGroup, InputGroupInput } from '@/components/ui/input-group'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Card, Pending } from '@/controls'

type Action = 'pause' | 'resume' | 'cancel'

const defaults = {
  teacher: true,
  screen: false,
  subtitles: true,
  slides: true,
  pdf: false,
  overwrite: false,
  connections: '16',
}

export function Courses({ state, busy, run, notify }: ViewProps) {
  const course = state.course
  const [selected, setSelected] = useState<string[]>([])
  const [options, setOptions] = useState(defaults)
  const { teacher, screen, subtitles, slides } = options
  const content = teacher || screen || subtitles || slides
  const terms = Map.groupBy(state.courses, (course) => course.term)
  const jobs = Object.values(state.jobs)
  const active = jobs.filter((job) => job.status === 'queued' || job.status === 'running').length
  const speed = jobs.find((job) => job.status === 'running')?.speed
  const connectionsId = useId()

  function option<K extends keyof typeof defaults>(key: K) {
    return (value: (typeof defaults)[K]) => setOptions((current) => ({ ...current, [key]: value }))
  }

  function open(id: string) {
    setSelected([])
    run('course', { course_id: id }).then(notify)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const error = await run('download', {
      ...options,
      course_id: course!.id,
      sub_ids: selected,
      videos: [teacher && 'teacher', screen && 'screen'].filter(Boolean),
      connections: Number(options.connections) || 16,
    })
    if (error) notify(error)
    else setSelected([])
  }

  function control(sub_id: string, action: Action) {
    run('job', { sub_id, action }).then(notify)
  }

  return (
    <Card title="课程资料" className="max-w-[600px]">
      <Select value={course?.id ?? ''} onValueChange={open}>
        <SelectTrigger aria-label="课程">
          <SelectValue placeholder="选择课程" />
        </SelectTrigger>
        <SelectContent className="max-h-80">
          {[...terms].map(([term, courses]) => (
            <SelectGroup key={term}>
              <SelectLabel>{term}</SelectLabel>
              {courses.map(({ id, title, teacher }) => (
                <SelectItem key={id} value={id}>
                  {title}
                  <span className="text-muted-foreground">{teacher}</span>
                </SelectItem>
              ))}
            </SelectGroup>
          ))}
        </SelectContent>
      </Select>
      {course && (
        <form onSubmit={submit}>
          <p className="mt-2 flex items-center gap-1.5 px-1 text-xs text-muted-foreground">
            <FolderIcon className="size-3.5 shrink-0" strokeWidth={1.5} />
            <span className="truncate" title={course.folder}>
              {course.folder}
            </span>
          </p>
          <Section title="课次" aside={active ? `${active} 节下载中${speed ? ` · ${rate(speed)}` : ''}` : ''}>
            <Lectures course={course} jobs={state.jobs} selected={selected} select={setSelected} control={control} />
          </Section>
          <Section title="下载内容">
            <Option
              icon={VideoIcon}
              title="教室视频"
              detail="MP4 录像，每节约 1–2 GB"
              checked={teacher}
              onCheckedChange={option('teacher')}
            />
            <Option
              icon={MonitorIcon}
              title="屏幕视频"
              detail="讲台电脑的屏幕画面，体积相近"
              checked={screen}
              onCheckedChange={option('screen')}
            />
            <Option
              icon={CaptionsIcon}
              title="平台字幕"
              detail="平台语音识别的草稿，便于检索"
              checked={subtitles}
              onCheckedChange={option('subtitles')}
            />
            <Option
              icon={PresentationIcon}
              title="PPT 截图"
              detail="课件画面及出现时间"
              checked={slides}
              onCheckedChange={option('slides')}
            />
          </Section>
          <Collapsible.Root>
            <Collapsible.Content className="overflow-hidden data-open:animate-collapsible-down data-closed:animate-collapsible-up">
              <Section>
                <Option
                  icon={FileStackIcon}
                  title="合成 PDF"
                  detail="按时间顺序合并全部 PPT 截图"
                  checked={options.pdf}
                  onCheckedChange={option('pdf')}
                />
                <Option
                  icon={RefreshCwIcon}
                  title="重新下载"
                  detail="覆盖已保存的文件"
                  checked={options.overwrite}
                  onCheckedChange={option('overwrite')}
                />
                <Setting icon={GaugeIcon} title="并发连接" detail="同时下载的连接数" htmlFor={connectionsId}>
                  <InputGroup className="h-7 w-16 pointer-coarse:h-7 pointer-coarse:text-sm">
                    <InputGroupInput
                      id={connectionsId}
                      type="number"
                      min={1}
                      max={64}
                      value={options.connections}
                      onChange={(event) => option('connections')(event.target.value)}
                      className="px-2 text-right tabular-nums"
                    />
                  </InputGroup>
                </Setting>
              </Section>
            </Collapsible.Content>
            <footer className="mt-5 flex items-center justify-between gap-3">
              <Collapsible.Trigger className="group flex items-center gap-1 rounded-sm px-1 text-xs text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50">
                更多选项
                <ChevronRightIcon className="size-3.5 transition-transform group-data-[state=open]:rotate-90" />
              </Collapsible.Trigger>
              <Button type="submit" disabled={!selected.length || !content || busy !== null}>
                <Pending active={busy === 'download'}>
                  {!selected.length ? '选择课次' : content ? `下载 ${selected.length} 节` : '选择内容'}
                </Pending>
              </Button>
            </footer>
          </Collapsible.Root>
        </form>
      )}
    </Card>
  )
}

function Section({ title, aside, children }: { title?: string; aside?: string; children: ReactNode }) {
  return (
    <section className="mt-5">
      {title && (
        <h2 className="mb-2 flex items-baseline justify-between px-1 text-xs font-medium text-muted-foreground">
          {title}
          <span className="font-normal tabular-nums">{aside}</span>
        </h2>
      )}
      <div className="divide-y overflow-hidden rounded-lg border">{children}</div>
    </section>
  )
}

interface SettingProps {
  icon: LucideIcon
  title: string
  detail: string
  htmlFor: string
  active?: boolean
  children: ReactNode
}

/** A settings row: an icon, a title over one line of detail, then its controls. */
function Setting({ icon: Icon, title, detail, htmlFor, active = false, children }: SettingProps) {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5">
      <label htmlFor={htmlFor} className="flex min-w-0 flex-1 items-center gap-3">
        <span
          className={cn(
            'grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground transition-colors',
            active && 'bg-primary/10 text-primary dark:bg-primary/20',
          )}
        >
          <Icon className="size-4" strokeWidth={1.5} />
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-medium">{title}</span>
          <span className="block truncate text-xs text-muted-foreground">{detail}</span>
        </span>
      </label>
      {children}
    </div>
  )
}

type OptionProps = Omit<SettingProps, 'htmlFor' | 'active' | 'children'> & {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  children?: ReactNode
}

/** A setting turned on and off by a switch, after any controls of its own. */
function Option({ checked, onCheckedChange, children, ...setting }: OptionProps) {
  const id = useId()
  return (
    <Setting {...setting} htmlFor={id} active={checked}>
      {children}
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} />
    </Setting>
  )
}

interface LecturesProps {
  course: Course
  jobs: Record<string, Job>
  selected: string[]
  select: (ids: string[]) => void
  control: (sub_id: string, action: Action) => void
}

function Lectures({ course, jobs, selected, select, control }: LecturesProps) {
  const free = course.lectures.filter((lecture) => !jobs[lecture.sub_id]).map((lecture) => lecture.sub_id)
  const all = free.length > 0 && free.every((id) => selected.includes(id))
  if (!course.lectures.length) {
    return <p className="py-8 text-center text-sm text-muted-foreground">暂无回放</p>
  }
  return (
    <>
      <label className="flex h-9 items-center gap-3 bg-muted/50 px-3 text-xs text-muted-foreground">
        <Checkbox
          checked={all || (selected.length > 0 && 'indeterminate')}
          onCheckedChange={() => select(all ? [] : free)}
          disabled={!free.length}
        />
        全部课次
        <span className="ml-auto tabular-nums">共 {course.lectures.length} 节</span>
      </label>
      <ul className="max-h-[min(45svh,22rem)] divide-y overflow-y-auto">
        {course.lectures.map((lecture) => (
          <Row
            key={lecture.sub_id}
            lecture={lecture}
            job={jobs[lecture.sub_id]}
            checked={selected.includes(lecture.sub_id)}
            onCheckedChange={(on) =>
              select(on ? [...selected, lecture.sub_id] : selected.filter((id) => id !== lecture.sub_id))
            }
            control={(action) => control(lecture.sub_id, action)}
          />
        ))}
      </ul>
    </>
  )
}

interface RowProps {
  lecture: Lecture
  job?: Job
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  control: (action: Action) => void
}

/** A lecture; while queued it shows progress and pause, resume or retry, and cancel, like a browser's downloads. */
function Row({ lecture, job, checked, onCheckedChange, control }: RowProps) {
  const id = useId()
  return (
    <li className="px-3 py-2.5">
      <div className="flex min-h-6 items-center gap-3">
        <Checkbox id={id} checked={checked && !job} onCheckedChange={onCheckedChange} disabled={!!job} />
        <label htmlFor={id} className="flex min-w-0 flex-1 items-baseline gap-3">
          <span className="text-sm whitespace-nowrap tabular-nums">{lecture.id}</span>
          {lecture.duration_s && (
            <span className="text-xs text-muted-foreground tabular-nums max-sm:hidden">
              {clock(lecture.duration_s)}
            </span>
          )}
        </label>
        {job ? <Controls job={job} control={control} /> : <Saved lecture={lecture} />}
      </div>
      <AnimatePresence initial={false}>
        {job && (
          <m.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="overflow-hidden pl-7"
          >
            <Progress
              value={bar(job)}
              className={cn(
                'mt-2.5',
                job.status === 'paused' && '*:bg-muted-foreground/40',
                job.status === 'failed' && '*:bg-destructive',
              )}
            />
            <p
              className={cn(
                'mt-1.5 truncate text-xs text-muted-foreground tabular-nums',
                job.status === 'failed' && 'text-destructive',
              )}
            >
              {status(job)}
            </p>
          </m.div>
        )}
      </AnimatePresence>
    </li>
  )
}

function Controls({ job, control }: { job: Job; control: RowProps['control'] }) {
  const [label, icon, action]: [string, ReactNode, Action] =
    job.status === 'failed'
      ? ['重试', <RotateCwIcon />, 'resume']
      : job.status === 'paused'
        ? ['继续', <PlayIcon fill="currentColor" />, 'resume']
        : ['暂停', <PauseIcon fill="currentColor" />, 'pause']
  return (
    <span className="flex gap-1.5">
      <Button
        type="button"
        variant="muted"
        size="round"
        aria-label={label}
        title={label}
        onClick={() => control(action)}
      >
        {icon}
      </Button>
      <Button
        type="button"
        variant="muted"
        size="round"
        aria-label="取消"
        title="取消"
        onClick={() => control('cancel')}
      >
        <XIcon />
      </Button>
    </span>
  )
}

function Saved({ lecture }: { lecture: Lecture }) {
  const badges = lecture.dropped
    ? ['空课']
    : [
        ...(lecture.videos ?? []).map((view) => `${view === 'screen' ? '屏幕' : '教室'}视频`),
        lecture.subtitles ? '字幕' : '',
        lecture.slides ? 'PPT' : '',
      ].filter(Boolean)
  return (
    <span className="flex gap-1">
      {badges.map((badge) => (
        <Badge key={badge}>{badge}</Badge>
      ))}
    </span>
  )
}

const tasks = {
  subtitles: '获取字幕',
  slides: '下载 PPT 截图',
  teacher: '下载教室视频',
  screen: '下载屏幕视频',
  pdf: '合成 PDF',
}

function measured(job: Job) {
  return job.task === 'teacher' || job.task === 'screen' || job.task === 'slides'
}

/** The bar's percentage, or undefined for a sweeping bar while a step without a measure runs. */
function bar(job: Job) {
  if (measured(job)) return (job.fraction ?? 0) * 100
  return job.status === 'running' ? undefined : 0
}

function status(job: Job) {
  if (job.status === 'queued') return '等待下载'
  if (job.status === 'failed') return job.error
  if (!job.task || job.task === 'done') return job.status === 'paused' ? '已暂停' : '准备中'
  const step = tasks[job.task] + (measured(job) ? ` ${Math.floor((job.fraction ?? 0) * 100)}%` : '')
  if (job.status === 'paused') return `已暂停 · ${step}`
  return [step, job.speed && rate(job.speed), job.remaining && `剩余 ${clock(job.remaining)}`]
    .filter(Boolean)
    .join(' · ')
}

function rate(bytes: number) {
  return `${(bytes / 1e6).toFixed(1)} MB/s`
}

function clock(seconds: number) {
  const whole = Math.round(seconds)
  const pad = (value: number) => String(value).padStart(2, '0')
  const [hours, minutes, rest] = [Math.floor(whole / 3600), Math.floor(whole / 60) % 60, whole % 60]
  return hours ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${minutes}:${pad(rest)}`
}
