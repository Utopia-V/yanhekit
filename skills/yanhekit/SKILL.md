---
name: yanhekit
description: Download Yanhekt (延河课堂, aita.yanhekt.cn) lecture recordings, platform subtitles and PPT captures, build slide PDFs, transcribe with BCut, embed subtitles, and maintain course notes or answer questions from the material. Use for Yanhekt course links, BIT lecture replays, local lecture recordings, and requests for lecture transcripts, study notes, review outlines or course questions.
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/yanhekit.py *)
---

# Yanhekit

`<yanhekit>` in the commands below is the absolute path of `scripts/yanhekit.py` beside this `SKILL.md`; write it out in each command and run from the user's workspace so course material stays there. Ordinary Python 3.11+ can replace `uv run` once the script's declared dependencies are installed in a virtual environment. Video and audio processing need `ffmpeg` on PATH.

Pick the workflow below that fits the request and follow its steps in order; the command reference after them gives the details. Notes are the product: transcripts and subtitles only need to be readable enough to work from, so never rewrite them line by line.

## Workspace

```text
<course title>/
  course.json          course and lecture index
  课程总结.md           course notes
  复习提纲.md           review outline, when asked for
  10月08日第6-7节/      one folder per lecture, named by its lecture ID
    笔记.md            lecture notes
    录播-教室.mp4       classroom view (optional)
    录播-屏幕.mp4       screen view (optional)
    文字稿.txt          readable transcript
    字幕.srt            subtitles, also 字幕.vtt
    课件.pdf            slides
    slides/            index.json and numbered captures: 001.jpg, 002.jpg, …
    .cache/            subtitles.tsv, transcript.tsv, audio.mp3, sheet-001-016.jpg
```

`<lecture>` below is a lecture folder, such as `示例课程/10月08日第6-7节`, and `<course folder>` the folder holding `course.json`; commands on a lecture print paths relative to it. [references/files.md](references/files.md) gives the file formats and [references/notes.md](references/notes.md) the note templates.

## Workflows

### Start

1. Run `login` in the background. It returns at once while the saved session is valid; otherwise it prints the URL of a local sign-in page, so give the user that URL if no browser window appears. The user completes the password, captcha and SMS steps there. Never ask for or handle the password yourself.
2. Find the course with `courses`, which lists the user's enrolled courses with the latest term first, or with `search` for public electives and past courses. Ask only when the request matches several courses.
3. When the workspace already has the course folder, read its `课程总结.md` and run `lectures <course>`, which shows what each lecture has saved and which are dropped, and continue from there.

### Process a course

The default for a course, a set of lectures, or "整理/复习这门课". Running it again later picks up new lectures and skips finished work.

1. Survey: `download <course> --all --subtitles --slides` takes seconds and prints each lecture's duration, subtitle segments and captures.
2. Drop empty lectures. Holidays, cancelled classes and empty-room recordings show few subtitle segments and few or no captures. Skim the doubtful ones with `query <lecture> --source subtitles`, which is rough but shows whether a class took place, then `drop` the empty ones and list each in `课程总结.md` with its reason. `--all` passes over dropped lectures from then on.
3. Recordings: `download <course> --all --video` in the background.
4. Transcribe: `transcribe <course folder>` in the background once the recordings are saved. It writes `文字稿.txt` and `字幕.srt` for each lecture.
5. Fix recurring errors: BCut turns course terms into homophones, such as 赌马 for 补码 or 阿斯玛 for ASCII, and garbles campus names: `乐学` is the learning platform and `i北理` the campus app built on 钉钉. Collect the course's terms from slide sheets, grep the transcripts for their misheard forms, and fix them for the whole course with one `replace <course folder> -r <wrong> <right>...`. Leave one-off errors alone.
6. Embed `字幕.srt` into each saved recording with `embed`.
7. Slides and lecture notes: delegate per the brief below, about three lectures to a subagent. Without subagents, do the same yourself one lecture at a time.
8. Course notes: integrate the subagents' reports into `课程总结.md`, then tell the user what was processed, what was dropped, and the assignments, attendance checks and exam hints found.

### Check recent lectures

For quick questions such as "上节课点名了吗" or "最近留了什么作业". Read `笔记.md` first when the lecture is processed. Otherwise fetch the latest lectures with `download <course> -l <lecture ID>... --subtitles --slides` and read the platform subtitles with `query <lecture> --source subtitles`, which prints every segment without `--keyword`. Answer with timestamps and slide images, and offer to process the course when the platform text is too garbled to be sure.

### Slide deck

When the user asks for slides: `download <course> -l <lecture ID>... --slides`, then build a reviewed `课件.pdf` per lecture as described under [Slides](#slides), through a subagent per few lectures when available.

### Questions and review

Answer from the notes first, then `query` the transcripts and open the slides they point to; cite timestamps and slide images. For a review outline or self-test, process the lectures without notes first, then write `复习提纲.md` from `课程总结.md` and the lecture notes, opening transcripts and slides for the details.

## Subagent brief

Use the cheapest vision-capable subagent with write access. Give it the absolute `<yanhekit>` path, its lecture folders, the path of `references/notes.md`, and these tasks:

1. Slides: run `sheet` and `similar`, keep the clearest, most complete capture of each slide in lecture order, and write `课件.pdf` with `pdf`.
2. Notes: read `文字稿.txt`, open the slides it refers to, and write `笔记.md` with the lecture template. Prioritize attendance, assignments and deadlines, exam hints, teacher warnings and platform notices. Mark doubtful passages `需确认`. Do not edit the transcripts or subtitles.
3. Report per lecture: page count, one-line overview, and the attendance, assignment and exam items with timestamps, for the course summary.

## Commands

### Download

```sh
uv run <yanhekit> login
uv run <yanhekit> courses [--term 2026-2027-1]
uv run <yanhekit> search [<keyword>] [--term 2024-2025-2] [--college 计算机学院] [--sort newest|oldest|popular] [--page 1] [--limit 50]
uv run <yanhekit> lectures <course> [-o <workspace>]
uv run <yanhekit> download <course> (-l <lecture ID>... | --all) [--subtitles] [--slides] [--video [teacher] [screen]] [--pdf] [-o <workspace>]
uv run <yanhekit> drop <lecture>...
```

`search` covers every course on the platform; the keyword matches titles and teacher names. Each call fetches one page, so narrow the keyword, term or college rather than paging through everything. `<course>` is a course ID from `courses` or `search`, or a coursedetail URL. `lectures` prints each replay's lecture ID, `sub_id` and what the workspace holds for it.

`-l` takes a lecture ID or `sub_id` and can repeat; `--all` selects every replay except dropped ones. `download` fetches only what you name:

- `--subtitles` saves the platform subtitles as `.cache/subtitles.tsv`.
- `--slides` saves the timed PPT captures into `slides/`.
- `--video` gets the teacher view; `--video screen` or `--video teacher screen` chooses the views, each saved as its own recording.
- `--pdf` combines every saved capture into `课件.pdf`.

Each lecture's last line gives what it holds. A recording is 1–2 GB and can outlast a command timeout, so run video downloads in the background. Progress goes to stdout and retries to stderr, and an interrupted recording resumes from its finished parts. Existing files are kept unless you pass `--overwrite`. `--connections` (default 16) sets parallel requests.

`drop` deletes a lecture folder and marks the lecture `dropped` in `course.json`. Naming a dropped lecture with `-l` fetches it again.

`ui [<course>] [-o <workspace>]` opens a local page where the user picks lectures and follows the download queue. Offer it only when the user would rather click than say what to fetch; it runs until stopped.

### Transcribe and fix

```sh
uv run <yanhekit> transcribe <lecture | course folder | recording>... [--overwrite]
uv run <yanhekit> replace <lecture | course folder>... -r <wrong> <right> [-r <wrong> <right>]...
```

`transcribe` uploads extracted audio to Bilibili’s BCut service, from the teacher view when both are saved, and writes `.cache/audio.mp3`, `.cache/transcript.tsv`, `文字稿.txt` and `字幕.srt`. Lectures with a transcript are skipped, and a course folder covers every downloaded lecture. A recording from elsewhere works from a folder of its own, passed as its `.mp4` path or saved as `录播（教室）.mp4`.

`replace` applies each pair in order to every transcript text, prints the hits per lecture, and exports `文字稿.txt` and `字幕.srt` again where anything changed. Check a wrong form that is also a real word with `query --keyword` first.

### Query, export and embed

```sh
uv run <yanhekit> query <lecture> [--source transcript|subtitles] [--keyword 流水线] [--start 2:30] [--end 5:00]
uv run <yanhekit> export <lecture> [--source transcript|subtitles] [--format txt|srt|vtt]...
uv run <yanhekit> embed <recording> <subtitles>
```

The source is the BCut transcript unless you pass `--source subtitles`. `query` prints matching segments as `[02:30] text` lines, each run after the capture then on screen, such as `slides/008.jpg`; open the slide images for formulas, diagrams and uncertain terms. `export` writes `文字稿.txt` by default, or `字幕.srt` and `字幕.vtt`. `embed` replaces `<recording>`, such as `<lecture>/录播（教室）.mp4`, with a copy carrying the `.srt` or `.vtt` file as its only subtitle track, without re-encoding.

### Slides

```sh
uv run <yanhekit> sheet <lecture> [<capture>...] [--columns 4] [--rows 4]
uv run <yanhekit> similar <lecture> [--distance 12]
uv run <yanhekit> pdf <lecture> [<capture>...]
```

A capture is its number, such as `44`; `044.jpg` and `slides/044.jpg` work too. `sheet` and `pdf` take every capture when none are given.

`sheet` writes contact sheets of 16 thumbnails labelled with number and time, as `.cache/sheet-001-016.jpg` and so on. Use them to survey a lecture, find the slide a passage refers to, or collect terms for transcript fixes. Fewer columns give larger thumbnails; open the original capture for small text and formulas.

`similar` prints groups of near-identical captures with their times, one group per line, such as `005@02:10  044@41:20  054@55:05`. It is a rough first filter; confirm every choice in the images. Neighbours in a group are usually one slide shown longer or built up step by step, and the last is usually the most complete; distant ones are repeat visits. Small changes, such as another contents item highlighted or one added line, can share a group.

`pdf` writes `课件.pdf` with one capture per page in the given order. For a reviewed deck, go through the sheets and the similar groups, keep the clearest, most complete capture of each slide in lecture order, and drop desktops, transitions, video playback and repeat visits. Check the page count and a few pages before delivering.

## Notes

Maintain `笔记.md`, `课程总结.md` and `复习提纲.md` with the templates in [references/notes.md](references/notes.md).

A class spans two or three 45-minute periods with 5-minute breaks. The recording starts on time and may run past the end, so expect stray talk or silence around each break and at the end.

Prioritize what is easy to miss: attendance, assignments and deadlines, exam hints, teacher warnings, platform notices and procedural details. By default, map the content with timestamps rather than retelling it. Go deeper when asked: concept notes, formulas and worked examples, a review outline, cross-lecture answers or self-test questions. Write only what the transcript, slides or audio support, and cite timestamps and slide images.
