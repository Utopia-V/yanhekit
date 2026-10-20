# Workspace Files

## course.json

```json
{
  "course_id": "10001",
  "title": "示例课程",
  "teacher": "王老师",
  "term": "2026-2027-1",
  "lectures": [
    {"id": "09月23日第3-5节", "sub_id": "200001", "duration_s": 8100.0},
    {"id": "10月01日第3-5节", "sub_id": "200002", "dropped": true}
  ]
}
```

`lectures` lists every replay in class order. `id` is the folder name, built from the platform title (`2026-9-23第3-5节`), and `sub_id` the platform's replay ID. `duration_s` appears once the lecture is downloaded, and `dropped` marks an empty lecture whose folder `drop` deleted.

## Timelines

`.cache/fast-transcript.tsv` holds the platform's fast transcript and `.cache/transcript.tsv` the completed transcript from BCut or the local engine, tab-separated with a `start_s`, `end_s`, `text` header and rows ordered by start. `字幕.txt` is written from `transcript.tsv`, one `[00:02:30] text` line per segment.

`.cache/local-asr.json` holds resumable local ASR rows, the decoded sample offset, completion state, active runtime and a signature of the recording, model contents, hotwords and runtime options. It is published atomically after each chunk; the final `transcript.tsv` and `字幕.txt` appear after all audio is processed. Audio is decoded in RAM.

## Slides

`slides/` holds the slides extracted from the screen recording, and `slides/index.json` lists them in time order; each stays on screen until the next one's time:

```json
[{"file": "001.jpg", "time_s": 0.0}, {"file": "002.jpg", "time_s": 96.0}]
```

## Unfinished downloads

A name with `.part` before its suffix is still being written, and `slides/` without `index.json` is extracted again. `.cache/录播-教室.parts/` holds the finished parts of an interrupted recording until the next `download` completes it.
