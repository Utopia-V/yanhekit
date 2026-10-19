"""Timed transcripts: 字幕.txt, query, batch fixes and embedding."""

import math
import os
from bisect import bisect_right

from workspace import clock, ffmpeg, read_slides, read_tsv, replacing, timeline, write_tsv


def write_text(lecture):
  """Write 字幕.txt from the transcript, a `[00:02:30] text` line per segment."""
  rows = read_tsv(timeline(lecture, 'transcript'))
  (lecture / '字幕.txt').write_text(''.join(f'[{clock(start)}] {text}\n' for start, _, text in rows), encoding='utf-8')


def srt(lecture):
  """The transcript as the text of an .srt file."""
  rows = read_tsv(timeline(lecture, 'transcript'))
  return ''.join(
    f'{number}\n{clock(start, ",")} --> {clock(end, ",")}\n{text}\n\n'
    for number, (start, end, text) in enumerate(rows, 1)
  )


def replace(lecture, pairs):
  """Apply (wrong, right) pairs in turn to the transcript and return each one's hits; rewrite 字幕.txt after any."""
  rows, hits = read_tsv(timeline(lecture, 'transcript')), []
  for wrong, right in pairs:
    hits.append(sum(text.count(wrong) for _, _, text in rows))
    rows = [(start, end, text.replace(wrong, right)) for start, end, text in rows]
  if any(hits):
    write_tsv(timeline(lecture, 'transcript'), rows)
    write_text(lecture)
  return hits


def query(lecture, source='transcript', pattern=None, start=0, end=math.inf):
  """Segments matching the compiled `pattern` as `[00:02:30] text` lines, after a `slides/008.jpg` line whenever
  another slide is on screen."""
  slides = read_slides(lecture)
  times = [slide['time_s'] for slide in slides]
  shown = -1
  for begin, finish, text in read_tsv(timeline(lecture, source)):
    if finish >= start and begin <= end and (not pattern or pattern.search(text)):
      current = bisect_right(times, begin) - 1
      if current > shown:
        shown = current
        yield f'slides/{slides[current]["file"]}'
      yield f'[{clock(begin)}] {text}'


def embedded(video, lecture):
  """Whether the recording carries the current transcript, which `embed` marks with the transcript's modification time."""
  return video.stat().st_mtime_ns == timeline(lecture, 'transcript').stat().st_mtime_ns


def embed(video, subtitles, source=None):
  """Replace `video` with a copy whose only subtitle track is `subtitles`, the text of an .srt or .vtt file, without
  re-encoding; the copy takes the modification time of the `source` file the subtitles come from."""
  with replacing(video) as output:
    ffmpeg('-i', video, '-i', 'pipe:', '-map', '0:v', '-map', '0:a?', '-map', '1:0', '-c', 'copy', '-c:s', 'mov_text',
           '-metadata:s:s:0', 'language=zho', '-movflags', '+faststart', output, input=subtitles.encode())  # fmt: skip
  if source:
    os.utime(video, ns=(video.stat().st_atime_ns, source.stat().st_mtime_ns))
