# Workspace Files

Formats of the files in the workspace layout shown in SKILL.md.

## course.json

```json
{
  "course_id": "10001",
  "title": "示例课程",
  "teacher": "王老师",
  "term": "2026-2027-1",
  "lectures": [
    {"id": "09月23日第3-5节", "sub_id": "200001", "duration_s": 8100.0, "subtitles": 1800, "slides": 40, "videos": ["teacher"]},
    {"id": "09月30日第3-5节", "sub_id": "200002"}
  ]
}
```

`lectures` lists every replay in class order. `id` is the lecture ID and folder name, built from the platform title (`2026-9-23第3-5节`), and `sub_id` is the platform's replay ID. The other fields appear once that resource is downloaded: `duration_s`, `subtitles` (segment count), `slides` (capture count) and `videos` (saved views, `teacher`, `screen` or both). A count of 0 means the resource was fetched and is empty. `"dropped": true` marks an empty lecture whose folder `drop` deleted.

## Timelines

`.cache/subtitles.tsv` holds the platform subtitles and `.cache/transcript.tsv` the BCut transcript. Both are tab-separated with a `start_s`, `end_s`, `text` header, times in seconds and rows ordered by start. Corrections go into `transcript.tsv`, and the readable files are exported from it: `文字稿.txt` as paragraphs stamped `[02:30]` or `[01:02:30]`, `字幕.srt` and `字幕.vtt` with one cue per segment. `.cache/audio.mp3` is the audio BCut transcribed.

## Slides

`slides/index.json` lists the captures in time order:

```json
[{"file": "001.jpg", "time_s": 0.0}, {"file": "002.jpg", "time_s": 96.0}]
```

A capture stays on screen until the next capture's time. `.cache/sheet-001-016.jpg` and the following sheets hold 16 labelled thumbnails each. `课件.pdf` holds one capture per page.

## Unfinished downloads

A name with `.part` before its suffix is a file still being written. `slides/` without `index.json` is fetched again in full. `.cache/录播（教室）.parts/` and `.cache/录播（屏幕）.parts/` hold the finished parts of an interrupted recording; the next `download` fetches only the missing ones and removes the folder after joining them.
