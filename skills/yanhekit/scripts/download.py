"""Download lecture resources into the course workspace."""

import json
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import m3u8
import requests
from requests.adapters import HTTPAdapter
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from client import ORIGIN, USER_AGENT
from slides import write_pdf
from transcript import clock, ffmpeg, read_captures, read_tsv, recording, recordings, replacing, stamp, write_tsv

BLOCK = 8 << 20
CONNECTIONS = 16


def file_name(text):
  return re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', text).strip(' .')


def lecture_id(title):
  """2026-10-8第6-7节 -> 10月08日第6-7节; another title is kept as a file name."""
  match = re.fullmatch(r'\d{4}-(\d+)-(\d+)(第.+节)', title)
  return f'{int(match[1]):02}月{int(match[2]):02}日{match[3]}' if match else file_name(title)


def course_folder(workspace, course):
  return workspace / file_name(course['title'])


def read_index(folder):
  path = folder / 'course.json'
  return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def write_json(path, value):
  path.parent.mkdir(parents=True, exist_ok=True)
  with replacing(path) as part:
    part.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def lectures(course, index):
  """The current replay list as course.json lectures, keeping what earlier downloads recorded."""
  known = {lecture['sub_id']: lecture for lecture in index.get('lectures', [])}
  return [
    known.get(row['sub_id'], {'id': lecture_id(row['title']), 'sub_id': row['sub_id']}) for row in course['replays']
  ]


def sync_index(course, folder):
  index = read_index(folder)
  if index.get('course_id', course['id']) != course['id']:
    raise ValueError(f'{folder} belongs to course {index["course_id"]}')
  index = {
    'course_id': course['id'],
    'title': course['title'],
    'teacher': course['teacher'],
    'term': course['term'],
    'lectures': lectures(course, index),
  }
  write_json(folder / 'course.json', index)
  return index


def holdings(lecture, folder):
  """What a lecture has: course.json's records of its downloads, then its transcript and notes."""
  if lecture.get('dropped'):
    return 'dropped'
  held = [clock(lecture['duration_s'])] if 'duration_s' in lecture else []
  held += [f'{lecture[name]} {name}' for name in ('subtitles', 'slides') if name in lecture]
  held += [f'{view} video' for view in lecture.get('videos', [])]
  held += [
    name for name, path in (('transcript', '.cache/transcript.tsv'), ('notes', '笔记.md')) if (folder / path).exists()
  ]
  return '  '.join(held)


def drop(lecture):
  """Delete an empty lecture's folder and mark it in course.json, so that `--all` passes over it."""
  index = read_index(lecture.parent)
  entry = next((entry for entry in index.get('lectures', []) if entry['id'] == lecture.name), None)
  if entry is None:
    raise ValueError(f'{lecture.name} is not a lecture in {lecture.parent.name}/course.json')
  shutil.rmtree(lecture, ignore_errors=True)
  entry['dropped'] = True
  write_json(lecture.parent / 'course.json', index)


def transient(error):
  if isinstance(error, requests.HTTPError):
    return error.response.status_code in (403, 408, 429, 500, 502, 503, 504)  # 403: an expired signature
  return isinstance(error, (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError))


def log_retry(state):
  error = state.outcome.exception()
  reason = f'HTTP {error.response.status_code}' if isinstance(error, requests.HTTPError) else type(error).__name__
  print(
    f'{state.fn.__name__}: {reason}, retry {state.attempt_number}/3 in {state.upcoming_sleep:.0f}s', file=sys.stderr
  )


# Each attempt re-sends the request, so /play/ URLs get a fresh signature.
persistent = retry(
  retry=retry_if_exception(transient),
  stop=stop_after_attempt(4),
  wait=wait_exponential(2, max=30),
  before_sleep=log_retry,
  reraise=True,
)


class MediaSession(requests.Session):
  """Signs /play/ requests."""

  def __init__(self, client):
    super().__init__()
    self.client = client
    self.cookies = client.session.cookies
    self.headers.update({'User-Agent': USER_AGENT, 'Referer': ORIGIN + '/', 'Accept-Encoding': 'identity'})
    self.mount('https://', HTTPAdapter(pool_maxsize=CONNECTIONS))

  def request(self, method, url, *args, **kwargs):
    if urlsplit(url).path.startswith('/play/'):
      url = self.client.sign(url)
    return super().request(method, url, *args, **kwargs)


class Meter:
  """Thread-safe progress over `total` parts; with a label, it prints each quarter with the speed and time left."""

  def __init__(self, total, done, label=None):
    self.total, self.done, self.label = total, done, label
    self.fetched = self.size = 0
    self.quarter = done * 4 // total
    self.start = time.monotonic()
    self.lock = threading.Lock()

  def add(self, size, parts=0):
    with self.lock:
      self.size += size
      self.done += parts
      self.fetched += parts
      if self.label and self.quarter < self.done * 4 // self.total < 4:
        self.quarter = self.done * 4 // self.total
        elapsed = time.monotonic() - self.start
        left = (self.total - self.done) * elapsed / self.fetched
        speed = self.size / elapsed / 1e6
        print(f'  {self.label} {self.done / self.total:.0%}  {speed:.0f} MB/s  {stamp(left)} left', flush=True)


def parts(path):
  """Where a recording's finished parts wait, so that a stopped download resumes."""
  return path.parent / '.cache' / f'{path.stem}.parts'


@persistent
def fetch(session, meter, url, path, headers=None):
  with session.get(url, headers=headers, stream=True, timeout=60) as response:
    response.raise_for_status()
    with replacing(path) as part, part.open('wb') as file:
      for chunk in response.iter_content(1 << 18):
        file.write(chunk)
        meter.add(len(chunk))


def fetch_all(session, jobs, label=None):
  """Fetch (url, path, headers) jobs in parallel, skipping paths that already exist."""
  missing = [job for job in jobs if not job[1].exists()]
  if not missing:
    return
  meter = Meter(len(jobs), len(jobs) - len(missing), label)

  def run(job):
    fetch(session, meter, *job)
    meter.add(0, 1)

  pool = ThreadPoolExecutor(CONNECTIONS)
  try:
    list(pool.map(run, missing))
  finally:
    pool.shutdown(cancel_futures=True)  # after a failure or an interrupt, start no further parts


@persistent
def fetch_text(session, url):
  response = session.get(url, timeout=60)
  response.raise_for_status()
  return response.text


@persistent
def content_length(session, url):
  with session.get(url, headers={'Range': 'bytes=0-0'}, stream=True, timeout=60) as response:
    response.raise_for_status()
    return int(response.headers['Content-Range'].rpartition('/')[2])


def download_video(session, url, path, label):
  """Fetch a recording as parts, 8 MiB ranges of an MP4 or the segments of an HLS stream, then join them."""
  folder = parts(path)
  folder.mkdir(parents=True, exist_ok=True)
  with replacing(path) as joined:
    if urlsplit(url).path.endswith('.mp4'):
      size = content_length(session, url)
      spans = [(first, min(first + BLOCK, size) - 1) for first in range(0, size, BLOCK)]
      jobs = [(url, folder / f'{first:012}', {'Range': f'bytes={first}-{last}'}) for first, last in spans]
      fetch_all(session, jobs, label)
      with joined.open('wb') as file:
        for _, piece, _ in jobs:
          file.write(piece.read_bytes())
    else:
      playlist = m3u8.loads(fetch_text(session, url), uri=url)
      jobs = [(segment.absolute_uri, folder / f'{n:05}.ts', None) for n, segment in enumerate(playlist.segments)]
      fetch_all(session, jobs, label)
      for segment, (_, piece, _) in zip(playlist.segments, jobs):
        segment.uri = piece.name
      playlist.dump(folder / 'index.m3u8')
      ffmpeg('-i', folder / 'index.m3u8', '-c', 'copy', joined)
  shutil.rmtree(folder)


def download_slides(session, slides, folder):
  """Replace the captures with 001.jpg, 002.jpg and so on, and their times in index.json."""
  shutil.rmtree(folder, ignore_errors=True)
  folder.mkdir(parents=True)
  entries = [{'file': f'{n:03}.jpg', 'time_s': time_s} for n, (time_s, _) in enumerate(slides, 1)]
  jobs = [(url, folder / entry['file'], None) for entry, (_, url) in zip(entries, slides)]
  fetch_all(session, jobs)
  write_json(folder / 'index.json', entries)


def download(client, course, workspace, names=None, *, videos=(), subtitles=False, slides=False, pdf=False,
             overwrite=False):  # fmt: skip
  """Fetch the selected resources of each lecture, printing its progress and recording it in course.json.

  `names` are lecture IDs or sub_ids, by default every lecture not dropped; a named dropped lecture is unmarked.
  """
  if not (videos or subtitles or slides or pdf):
    raise ValueError('Nothing to download; choose --subtitles, --slides, --video or --pdf')
  folder = course_folder(workspace, course)
  index = sync_index(course, folder)
  if names is None:
    chosen = [lecture for lecture in index['lectures'] if not lecture.get('dropped')]
  else:
    chosen = [lecture for lecture in index['lectures'] if {lecture['id'], lecture['sub_id']} & set(names)]
    unknown = set(names).difference(*({lecture['id'], lecture['sub_id']} for lecture in chosen))
    if unknown:
      raise ValueError(f'Unknown lecture {", ".join(sorted(unknown))}; run `lectures` for the list')
  if not chosen:
    raise ValueError(f'{course["title"]} has no replays to download')
  session = MediaSession(client)
  for lecture in chosen:
    base = folder / lecture['id']
    base.mkdir(parents=True, exist_ok=True)
    lecture.pop('dropped', None)
    print(lecture['id'], flush=True)
    if videos or 'duration_s' not in lecture:
      info = client.lecture(course['id'], lecture['sub_id'])
      lecture['duration_s'] = info['duration_s']
    try:
      if subtitles:
        path = base / '.cache' / 'subtitles.tsv'
        if overwrite or not path.exists():
          write_tsv(path, client.subtitles(lecture['sub_id']))
        lecture['subtitles'] = len(read_tsv(path))
      if slides:
        if overwrite or not (base / 'slides' / 'index.json').exists():
          download_slides(session, client.slides(course['id'], lecture['sub_id']), base / 'slides')
        lecture['slides'] = len(read_captures(base))
      for view in videos:
        path = recording(base, view)
        if overwrite or not path.exists():
          if view not in info['streams']:
            raise ValueError(f'{lecture["id"]}: no {view} recording')
          download_video(session, info['streams'][view], path, f'{view} video')
      if pdf and lecture.get('slides'):
        write_pdf(base, read_captures(base))
    finally:
      if videos:
        lecture['videos'] = list(recordings(base))
      write_json(folder / 'course.json', index)  # what finished before a failure is recorded too
    print('  ' + holdings(lecture, base), flush=True)
  return folder
