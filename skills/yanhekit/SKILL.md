---
name: yanhekit
description: Download Yanhekt (延河课堂, aita.yanhekt.cn) lecture recordings, platform subtitles and PPT captures, build slide PDFs, transcribe with BCut, embed subtitles, and maintain course notes or answer questions from the material. Use for Yanhekt course links, BIT lecture replays, local lecture recordings, and requests for lecture transcripts, study notes, review outlines or course questions.
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/yanhekit.py *)
---

# Yanhekit

`<yanhekit>` below is the absolute path of `scripts/yanhekit.py` beside this `SKILL.md`; write it out in each command and run from the user's workspace. Python 3.11+ with the script's declared dependencies can replace `uv run`. Video and audio processing need `ffmpeg` on PATH.

Pick the workflow that fits the request and follow its steps in order. Notes are the product: transcripts and subtitles only need to be readable enough to work from, so never rewrite them line by line.

This toolkit changes quickly, so a workspace from an earlier version may differ from these instructions, such as in file names or `course.json` fields. Adapt to what you find.

## Workspace

```text
<course title>/
  course.json          course and lecture index
  课程总结.md           course notes
  复习提纲.md           review outline, when asked for
  10月08日第6-7节/      one folder per lecture, named by its lecture ID
    笔记.md            lecture notes
    录播-教室.mp4       classroom view
    录播-屏幕.mp4       screen view
    文字稿.txt          readable transcript
    字幕.srt            subtitles
    课件.pdf            slides
    slides/            index.json and numbered captures: 001.jpg, 002.jpg, …
    .cache/            subtitles.tsv, transcript.tsv, audio.mp3, sheet-001-016.jpg
```

`<lecture>` is a lecture folder and `<course folder>` the folder holding `course.json`. [references/files.md](references/files.md) gives the file formats and [references/notes.md](references/notes.md) the note templates.

## Workflows

### Start

1. Run `login` in the background. It signs in silently with the saved session, the remembered SSO session or the saved password; only when all fail does it open a local sign-in page and print its URL, which you pass on to the user. Never ask for or handle the password yourself.
2. Find the course with `courses` (enrolled courses, latest term first) or `search` (every course on the platform). Ask only when the request matches several courses.
3. When the course folder exists, read its `课程总结.md` and run `lectures <course>` to continue from what is saved.

### Process a course

The default for a course or a set of lectures. Running it again picks up new lectures and skips finished work.

1. Survey: `download <course> --all --subtitles --slides`, which takes seconds.
2. Drop empty lectures. Holidays, cancelled classes and empty-room recordings show few subtitle segments and few or no captures. Skim the doubtful ones with `query <lecture> --source subtitles`, `drop` the empty ones and list each in `课程总结.md` with its reason.
3. Recordings: `download <course> --all --video` in the background.
4. Transcribe: `transcribe <course folder>` in the background once the recordings are saved.
5. Fix recurring errors: BCut turns course terms into homophones, such as 赌马 for 补码 or 阿斯玛 for ASCII, and garbles campus names: `乐学` is the learning platform and `i北理` the campus app built on 钉钉. Collect the course's terms from slide sheets, grep the transcripts for their misheard forms, and fix them with one `replace <course folder> -r <wrong> <right>...`. Leave one-off errors alone.
6. `embed` `字幕.srt` into each saved recording.
7. Slides and lecture notes: delegate per the brief below, about three lectures to a subagent, or do the same yourself one lecture at a time.
8. Integrate the reports into `课程总结.md`, then tell the user what was processed, what was dropped, and the assignments, attendance checks and exam hints found.

### Check recent lectures

For questions such as "上节课点名了吗" or "最近留了什么作业". Read `笔记.md` when the lecture is processed. Otherwise run `download <course> -l <lecture>... --subtitles --slides` and read the platform subtitles with `query <lecture> --source subtitles`. Answer with timestamps and slide images, and offer to process the course when the platform text is too garbled to be sure.

### Slide deck

Run `download <course> -l <lecture>... --slides`, then build a reviewed `课件.pdf` per lecture as described under [Slides](#slides), through a subagent per few lectures when available.

### Questions and review

Answer from the notes first, then `query` the transcripts and open the slides they point to; cite timestamps and slide images. For a review outline or self-test, process the lectures without notes first, then write `复习提纲.md` from `课程总结.md` and the lecture notes.

## Subagent brief

Use the cheapest vision-capable subagent with write access. Give it the absolute `<yanhekit>` path, its lecture folders, the path of `references/notes.md`, and these tasks:

1. Slides: build a reviewed `课件.pdf` as described under [Slides](#slides).
2. Notes: read `文字稿.txt`, open the slides it refers to, and write `笔记.md` with the lecture template. Do not edit the transcripts or subtitles.
3. Report per lecture: page count, one-line overview, and the attendance, assignment and exam items with timestamps.

## Commands

### Download

```sh
uv run <yanhekit> login
uv run <yanhekit> courses [--term 2026-2027-1]
uv run <yanhekit> search [<keyword>] [--term 2024-2025-2] [--college 计算机学院] [--sort newest|oldest|popular] [--page 1] [--limit 50]
uv run <yanhekit> lectures <course> [-o <workspace>]
uv run <yanhekit> download <course> (-l <lecture>... | --all) [--subtitles] [--slides] [--video [classroom] [screen]] [--pdf] [--overwrite] [-o <workspace>]
uv run <yanhekit> drop <lecture>...
```

`<course>` is a course ID or a coursedetail URL. `search` matches titles and teacher names and fetches one page per call, so narrow the keyword, term or college rather than paging. `lectures` prints each replay's lecture ID, `sub_id` and what the workspace holds for it.

`download -l` takes lecture IDs or `sub_id`s; `--all` takes every replay except dropped ones. `--video` gets the classroom view unless you name the views. `--pdf` combines every saved capture into `课件.pdf`. Existing files are kept unless you pass `--overwrite`, and an interrupted recording resumes. A recording is 1–2 GB, so run video downloads in the background.

`drop` deletes a lecture folder and marks it dropped in `course.json`; naming it with `-l` fetches it again.

### Transcribe and fix

```sh
uv run <yanhekit> transcribe <lecture | course folder | recording>... [--overwrite]
uv run <yanhekit> replace <lecture | course folder>... -r <wrong> <right> [-r <wrong> <right>]...
```

`transcribe` uploads the audio of one recording per lecture, the classroom view first, to Bilibili’s BCut service and writes `文字稿.txt` and `字幕.srt`; lectures with a transcript are skipped. A recording from elsewhere works from a folder of its own.

`replace` applies the pairs in order to every transcript, prints the hits, and exports `文字稿.txt` and `字幕.srt` again. Check a wrong form that is also a real word with `query --keyword` first.

### Query, export and embed

```sh
uv run <yanhekit> query <lecture> [--source transcript|subtitles] [--keyword 流水线] [--start 2:30] [--end 5:00]
uv run <yanhekit> export <lecture> [--source transcript|subtitles] [--format txt|srt|vtt]...
uv run <yanhekit> embed <recording> <subtitles>
```

`--source` defaults to the BCut transcript. `query` prints `[02:30] text` lines, each run after the capture then on screen, such as `slides/008.jpg`, and every segment without `--keyword`. `export` writes `文字稿.txt` by default, or `字幕.srt` and `字幕.vtt`. `embed` replaces the recording with a copy whose only subtitle track is the given `.srt` or `.vtt`, without re-encoding.

### Slides

```sh
uv run <yanhekit> sheet <lecture> [<capture>...] [--columns 4] [--rows 4]
uv run <yanhekit> similar <lecture> [--distance 12]
uv run <yanhekit> pdf <lecture> [<capture>...]
```

A capture is its number, such as `44`; `sheet` and `pdf` take every capture when none are given. `sheet` writes contact sheets of labelled thumbnails to `.cache/`; fewer columns give larger thumbnails, and the original capture shows small text and formulas. `similar` prints groups of near-identical captures as `005@02:10  044@41:20`: neighbours are usually one slide built up step by step, the last being the most complete, and distant ones are repeat visits. It is a rough filter, so confirm choices in the images. `pdf` writes `课件.pdf` from the captures in the given order.

For a reviewed deck, go through the sheets and the similar groups, keep the clearest, most complete capture of each slide in lecture order, and drop desktops, transitions, video playback and repeat visits. Check the page count and a few pages before delivering.

## Notes

A class spans two or three 45-minute periods with 5-minute breaks; expect stray talk or silence around each break and after the end.

Prioritize what is easy to miss: attendance, assignments and deadlines, exam hints, teacher warnings, platform notices and procedural details. By default, map the content with timestamps rather than retelling it, and go deeper when asked. Write only what the transcript, slides or audio support, cite timestamps and slide images, and mark doubtful passages `需确认`.
