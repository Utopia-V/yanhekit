---
name: yanhekit
description: Download Yanhekt (延河课堂, aita.yanhekt.cn) lecture recordings and transcripts, extract slides from screen recordings, build slide PDFs, transcribe with BCut, embed subtitles, and maintain course notes or answer questions from the material. Use for Yanhekt course links, BIT lecture replays, local lecture recordings, and requests for lecture transcripts, slides, study notes, review outlines or course questions.
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/yanhekit.py *)
---

# Yanhekit

`<yanhekit>` below is the absolute path of `scripts/yanhekit.py` beside this `SKILL.md`; write it out in each command and run from the user's workspace. Python 3.11+ with the script's declared dependencies can replace `uv run`. Video and audio processing need `ffmpeg` on PATH.

Pick the workflow that fits the request and follow its steps in order. Notes are the product: transcripts only need to be readable enough to work from, so never rewrite them line by line.

## Workspace

```text
<course title>/
  course.json          course and lecture index
  课程总结.md           course notes
  复习提纲.md           review outline, when asked for
  10月08日第6-7节/      one folder per lecture, named by its lecture ID
    笔记.md            lecture notes
    录播-教室.mp4       classroom recording
    录播-屏幕.mp4       screen recording, when kept
    字幕.txt            transcript, a [00:02:30] line per segment
    课件.pdf            slides
    slides/            index.json and numbered slides: 001.jpg, 002.jpg, …
    frames/            frames taken at given times: 教室-00-41-20.jpg, …
    .cache/            fast-transcript.tsv, transcript.tsv, audio.m4a, sheet-001-016.jpg
```

Commands take targets: a course folder stands for its lectures not dropped, and `--latest N` narrows it to the last N; a lecture folder stands for itself, and `download` also takes one not yet created, named `<course folder>/<lecture ID>` as `status` lists it. [references/files.md](references/files.md) gives the file formats and [references/notes.md](references/notes.md) the note templates.

Whenever a transcript shows an empty lecture, such as a holiday, a cancelled class or an empty room, `drop` it and list it in `课程总结.md` with its reason.

## Workflows

### Start

1. Run `login` in the background. It signs in silently with the saved session, the remembered SSO session or the saved password; only when all fail does it open a local sign-in page and print its URL, which you pass on to the user. Never ask for or handle the password yourself.
2. Find the course with `courses` (enrolled courses, latest term first) or `search` (every course on the platform). Ask only when the request matches several courses.
3. Run `add <course>` to create the course folder, or read `课程总结.md` and run `status` when it exists, and continue from what is saved.

### Process a course

The default for a course or a set of lectures, with `C` the course folder. Running it again picks up new lectures and skips finished work.

1. Survey: `download C --fast-transcript`, which takes seconds.
2. Drop empty lectures: their fast transcripts have few or no segments, and `query <lecture> --fast-transcript` settles the doubtful ones.
3. Recordings, slides and transcripts: `download C --classroom --slides --transcribe` in the background.
4. Fix recurring errors: BCut turns course terms into homophones and garbles campus names: `延河课堂` is the lecture platform, `乐学` the learning platform and `i北理` the campus app built on 钉钉. Collect the course's terms from the slides, grep the transcripts for their misheard forms, and fix the forms that recur and that the slides or context confirm with one `replace C -r <wrong> <right>...`. Leave one-off errors and unclear phrases as they are.
5. `embed C`.
6. Slides and lecture notes: delegate per the brief below, about three lectures to a subagent, or do the same yourself one lecture at a time.
7. Integrate the reports into `课程总结.md`, then tell the user what was processed, what was dropped, and the assignments, attendance checks and exam hints found.

### Check recent lectures

For questions such as "上节课点名了吗" or "最近留了什么作业", across one or more course folders. Read `笔记.md` when the lecture is processed, or else `字幕.txt` when it is transcribed. Otherwise run `download <course folders> --latest 1 --fast-transcript` and read it with `query <course folders> --latest 1 --fast-transcript`. Answer with timestamps, and offer to process the course when the fast transcript is too garbled to be sure.

### Slide deck

Run `download <lectures> --slides`, then build a reviewed `课件.pdf` per lecture as described under [Slides and frames](#slides-and-frames), through a subagent per few lectures when available. When a lecture has no screen recording, tell the user so.

### Questions and review

Answer from the notes first, then `query` the transcripts and open the slides they point to; cite timestamps and slide images. For a review outline or self-test, process the lectures without notes first, then write `复习提纲.md` from `课程总结.md` and the lecture notes.

## Subagent brief

Use the cheapest vision-capable subagent with write access. Give it the absolute `<yanhekit>` path, its lecture folders, the path of `references/notes.md`, and these tasks:

1. Slides: build a reviewed `课件.pdf` as described under [Slides and frames](#slides-and-frames).
2. Notes: read `字幕.txt` and `query` it to see which slide each passage refers to; take a `frame` of the classroom view where the teacher writes on the board or the transcript is unclear. Write `笔记.md` with the lecture template, and leave `字幕.txt` as it is.
3. Report per lecture: page count, one-line overview, and the attendance, assignment and exam items with timestamps.

## Commands

### Courses and downloads

```sh
uv run <yanhekit> login
uv run <yanhekit> courses [--term 2026-2027-1]
uv run <yanhekit> search [<keyword>] [--term 2024-2025-2] [--college 计算机学院] [--sort newest|oldest|popular] [--page 1] [--limit 50]
uv run <yanhekit> add <course>... [-o <workspace>]
uv run <yanhekit> status [<course folder>...]
uv run <yanhekit> download <target>... [--latest N] [--fast-transcript] [--classroom] [--screen] [--slides] [--transcribe] [--overwrite]
uv run <yanhekit> drop <lecture>...
```

`<course>` is a course ID or a coursedetail URL. `courses` and `search` print a course per line: ID, title, teacher, term and, for `search`, college. `search` matches titles and teacher names and fetches one page of up to `--limit 100` per call, so narrow the keyword, term or college rather than paging. `add` and `status` list each lecture with what its folder holds; `status` stays offline and covers every course folder here by default.

`download` refreshes the lecture list first. `--fast-transcript` fetches the platform's own transcript in seconds; it is rougher than BCut's, so it serves surveys and quick checks only. `--classroom` saves the classroom recording and `--screen` the screen recording. `--slides` extracts the slides from the screen recording, fetching it for the purpose and removing it afterwards unless you also pass `--screen`; at most two such recordings wait on disk, and the downloads pause until extraction catches up. `--transcribe` transcribes each lecture's recording as `transcribe` does, so pair it with `--classroom` when no recording is kept. Slides and transcripts are made in two queues of their own while the next lectures download. Each output line starts with the time and the lecture; a long step such as fetching a recording, extracting slides or waiting for BCut reports its progress at least every 10 seconds, so the last lines show where the run stands, and the run ends with a line per lecture on what it holds. Existing files are kept unless you pass `--overwrite`, and an interrupted recording resumes. A recording is 2–3 GB, so run video and slide downloads in the background.

`drop` deletes a lecture folder and marks it dropped, so its course folder passes over it; naming the lecture folder in `download` fetches it again.

### Transcripts

```sh
uv run <yanhekit> transcribe <target>... [--latest N] [--overwrite]
uv run <yanhekit> replace <target>... -r <wrong> <right> [-r <wrong> <right>]...
uv run <yanhekit> embed <target>... [--file <subtitles>]
uv run <yanhekit> query <target>... [--latest N] [--fast-transcript] [-m 流水线] [--start 2:30] [--end 5:00]
```

`transcribe` uploads the sound track of each lecture's recording to Bilibili’s BCut service, one lecture at a time, and writes `字幕.txt`; lectures with a transcript are skipped. A recording from elsewhere works too, saved as `录播-教室.mp4` in a lecture folder of its own.

`replace` applies the pairs in order to every transcript, prints the hits, and rewrites `字幕.txt`. Check a wrong form that is also a real word with `query -m` first. `embed` replaces each recording with a copy whose only subtitle track is the transcript, or the .srt or .vtt `--file` given, without re-encoding, and skips a recording that already carries the current transcript.

`query` prints the matching segments of the BCut transcript, or of the platform's fast transcript with `--fast-transcript`, as `[00:02:30] text` lines, and every segment without `-m`. `-m`/`--match` is a regular expression matched in any case, so one call covers alternatives such as `点名|签到|考勤`. Each lecture with matches starts with a line naming it, and each run of segments follows the slide then on screen, such as `slides/008.jpg`; with no match, it says how many lectures it searched.

### Slides and frames

```sh
uv run <yanhekit> frame <lecture> <time>... [--view classroom|screen]
uv run <yanhekit> sheet <target>... [--columns 4] [--rows 4]
uv run <yanhekit> similar <target>... [--distance 12]
uv run <yanhekit> pdf <lecture> [<slide>...]
```

`frame` saves the frames of a saved recording at the given times to `frames/`. `sheet` writes contact sheets of numbered, timed slides to `.cache/`; fewer columns give larger thumbnails, and the original slide shows small text and formulas. `similar` prints each group of near-identical slides on a line, such as `005@00:02:10 044@00:41:20`. `pdf` writes `课件.pdf` from the given slide numbers, such as `5` or `005`, in order, or from all of them.

`slides/` holds every screen the recording settled on, cropped to the slide where it can be found. It also holds desktops, editing views, video playback and each step of a slide built up line by line. For a reviewed deck, go through the sheets and the similar groups, keep the clearest, most complete version of each slide in lecture order, usually the last step of a build-up, and pass the kept numbers to `pdf`. Check the page count and a few pages before delivering.

## Notes

A class spans two or three 45-minute periods with 5-minute breaks; expect stray talk or silence around each break and after the end.

Prioritize what is easy to miss: attendance, assignments and deadlines, exam hints, teacher warnings, platform notices and procedural details. By default, map the content with timestamps rather than retelling it, and go deeper when asked. Write only what the transcript, slides, frames or audio support, cite timestamps and images, and mark doubtful passages `需确认`.
