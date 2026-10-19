"""A lecture's files and timed transcripts."""

import csv
import json
import math
import shutil
import subprocess
from bisect import bisect_right
from contextlib import contextmanager


@contextmanager
def replacing(path):
  """Yield a sibling to write instead of `path`, so that `path` appears only once the block completes."""
  part = path.with_suffix('.part' + path.suffix)  # ffmpeg picks the format from the last suffix
  try:
    yield part
    part.replace(path)
  finally:
    part.unlink(missing_ok=True)


def ffmpeg(*args):
  if not shutil.which('ffmpeg'):
    raise ValueError('ffmpeg not found; install it and put it on PATH')
  subprocess.run(['ffmpeg', '-v', 'error', '-y', *args], check=True)


def write_tsv(path, rows):
  """Write (start, end, text) rows by start time, with whitespace collapsed and empty text dropped; return the count."""
  rows = sorted((start, end, ' '.join(text.split())) for start, end, text in rows)
  rows = [row for row in rows if row[2]]
  path.parent.mkdir(parents=True, exist_ok=True)
  with replacing(path) as part, part.open('w', encoding='utf-8', newline='') as file:
    writer = csv.writer(file, delimiter='\t', lineterminator='\n')
    writer.writerow(['start_s', 'end_s', 'text'])
    writer.writerows((f'{start:.3f}', f'{end:.3f}', text) for start, end, text in rows)
  return len(rows)


def read_tsv(path):
  with path.open(encoding='utf-8', newline='') as file:
    return [(float(row['start_s']), float(row['end_s']), row['text']) for row in csv.DictReader(file, delimiter='\t')]


def timeline(lecture, source):
  path = lecture / '.cache' / f'{source}.tsv'
  if not path.exists():
    command = 'transcribe' if source == 'transcript' else 'download --subtitles'
    raise ValueError(f'{lecture.name} has no {source}; run `{command}`')
  return read_tsv(path)


VIEWS = {'classroom': '教室', 'screen': '屏幕'}


def recording(lecture, view):
  return lecture / f'录播-{VIEWS[view]}.mp4'


def recordings(lecture):
  """The saved recordings by view, the classroom view first."""
  return {view: path for view in VIEWS if (path := recording(lecture, view)).exists()}


def lecture_folders(folder):
  """A lecture folder as itself; a course folder, which holds course.json, as its lecture folders."""
  if not (folder / 'course.json').exists():
    return [folder]
  return sorted(path for path in folder.iterdir() if path.is_dir())


def read_captures(lecture):
  """Entries of slides/index.json, or none before the captures are downloaded."""
  index = lecture / 'slides' / 'index.json'
  return json.loads(index.read_text(encoding='utf-8')) if index.exists() else []


def clock(seconds, separator=''):
  """01:02:03, or 01:02:03,456 when given the millisecond separator."""
  hours, rest = divmod(round(seconds * 1000), 3_600_000)
  minutes, rest = divmod(rest, 60_000)
  whole, millis = divmod(rest, 1000)
  text = f'{hours:02}:{minutes:02}:{whole:02}'
  return f'{text}{separator}{millis:03}' if separator else text


def seconds(value):
  """Parse 150, 2:30 or 1:02:30."""
  return sum(float(part) * 60**power for power, part in enumerate(reversed(value.split(':'))))


def stamp(seconds):
  """02:30, or 01:02:30 from the first hour on."""
  return clock(seconds).removeprefix('00:')


def paragraphs(rows, gap=2, size=180, span=60):
  """Join segments separated by short pauses into readable paragraphs."""
  merged = []
  for start, end, text in rows:
    last = merged[-1] if merged else None
    if last and start - last[1] <= gap and len(last[2]) + len(text) <= size and end - last[0] <= span:
      joiner = ' ' if last[2][-1].isascii() and text[0].isascii() else ''
      last[1:] = [end, last[2] + joiner + text]
    else:
      merged.append([start, end, text])
  return merged


def export(lecture, format, source='transcript'):
  """Write 文字稿.txt as stamped paragraphs, or 字幕.srt or 字幕.vtt with a cue per segment."""
  rows = timeline(lecture, source)
  if format == 'txt':
    lines = [f'[{stamp(start)}] {text}' for start, _, text in paragraphs(rows)]
  else:
    separator = ',' if format == 'srt' else '.'
    lines = ['WEBVTT\n'] if format == 'vtt' else []
    for number, (start, end, text) in enumerate(rows, 1):
      lines.append(f'{number}\n{clock(start, separator)} --> {clock(end, separator)}\n{text}\n')
  path = lecture / ('文字稿.txt' if format == 'txt' else f'字幕.{format}')
  path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
  return path


def replace(lecture, pairs):
  """Apply (wrong, right) pairs in turn to the transcript text and return each one's hits; re-export after any."""
  path = lecture / '.cache' / 'transcript.tsv'
  rows, hits = read_tsv(path), []
  for wrong, right in pairs:
    hits.append(sum(text.count(wrong) for _, _, text in rows))
    rows = [(start, end, text.replace(wrong, right)) for start, end, text in rows]
  if any(hits):
    write_tsv(path, rows)
    for format in ('txt', 'srt'):
      export(lecture, format)
  return hits


def query(lecture, source='transcript', keyword=None, start=0, end=math.inf):
  """Matching segments as `[02:30] text` lines, after a `slides/008.jpg` line whenever another capture is on screen."""
  captures = read_captures(lecture)
  times = [capture['time_s'] for capture in captures]
  shown = -1
  for begin, finish, text in timeline(lecture, source):
    if finish >= start and begin <= end and (not keyword or keyword.casefold() in text.casefold()):
      current = bisect_right(times, begin) - 1
      if current > shown:
        shown = current
        yield f'slides/{captures[current]["file"]}'
      yield f'[{stamp(begin)}] {text}'


def embed(video, subtitles):
  """Replace `video` with a copy carrying the .srt or .vtt file as its soft subtitle track, without re-encoding."""
  with replacing(video) as output:
    ffmpeg('-i', video, '-i', subtitles, '-map', '0:v', '-map', '0:a?', '-map', '1:0', '-c', 'copy', '-c:s', 'mov_text',
           '-metadata:s:s:0', 'language=zho', '-movflags', '+faststart', output)  # fmt: skip
