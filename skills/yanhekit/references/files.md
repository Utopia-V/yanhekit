# Workspace Files

## course.json

```json
{
  "course_id": "10001",
  "title": "示例课程",
  "teacher": "王老师",
  "term": "2026-2027-1",
  "lectures": [
    {"id": "09月23日第3-5节", "sub_id": "200001", "duration_s": 8100.0, "subtitles": 1800, "slides": 40, "videos": ["classroom"]},
    {"id": "09月30日第3-5节", "sub_id": "200002", "dropped": true}
  ]
}
```

`lectures` lists every replay in class order. `id` is the folder name, built from the platform title (`2026-9-23第3-5节`), and `sub_id` the platform's replay ID. Download fields appear once fetched: `subtitles` and `slides` count segments and captures, and `videos` lists the saved views. `dropped` marks an empty lecture whose folder `drop` deleted.

## Timelines

`.cache/subtitles.tsv` holds the platform subtitles and `.cache/transcript.tsv` the BCut transcript, tab-separated with a `start_s`, `end_s`, `text` header and rows ordered by start. `文字稿.txt` and `字幕.srt` are exported from `transcript.tsv`: paragraphs stamped `[02:30]`, and one cue per segment.

## Slides

`slides/index.json` lists the captures in time order; each stays on screen until the next one's time:

```json
[{"file": "001.jpg", "time_s": 0.0}, {"file": "002.jpg", "time_s": 96.0}]
```

## Unfinished downloads

A name with `.part` before its suffix is still being written, and `slides/` without `index.json` is fetched again. `.cache/录播-教室.parts/` holds the finished parts of an interrupted recording until the next `download` completes it.
