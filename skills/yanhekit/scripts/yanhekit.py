# /// script
# requires-python = '>=3.11'
# dependencies = [
#   'beautifulsoup4>=4.12',
#   'flask>=3.1',
#   'img2pdf>=0.6',
#   'keyring>=25',
#   'm3u8>=6',
#   'pillow>=11',
#   'pycryptodome>=3.23',
#   'requests>=2.32',
#   'tenacity>=9',
# ]
# ///
"""Yanhekt lecture material: download, transcribe, query and review slides."""

import argparse
import math
import re
import subprocess
import sys
from itertools import groupby
from pathlib import Path

import requests

import download
import slides
import transcribe
import transcript
from client import SORTS, STREAMS, APIError, Yanhekt, describe, upgrade_to_campus


def signed_in():
  upgrade_to_campus()
  client = Yanhekt()
  if not client.authenticate():
    import server  # Flask and the sign-in stack load only when the page is needed

    server.serve(client)
  return client


def select(course, lectures):
  """Map lecture IDs or sub_ids to sub_ids."""
  known = {download.lecture_id(row['title']): row['sub_id'] for row in course['replays']}
  unknown = [name for name in lectures if name not in known and name not in known.values()]
  if unknown:
    raise ValueError(f'Unknown lecture {", ".join(unknown)}; run `lectures` for the list')
  return [known.get(name, name) for name in lectures]


def holdings(lecture, folder):
  """What a lecture has: course.json's records of its downloads, then its transcript and notes."""
  if lecture.get('dropped'):
    return 'dropped'
  held = [transcript.clock(lecture['duration_s'])] if 'duration_s' in lecture else []
  held += [f'{lecture[name]} {name}' for name in ('subtitles', 'slides') if name in lecture]
  held += [f'{view} video' for view in lecture.get('videos', [])]
  held += [
    name for name, path in (('transcript', '.cache/transcript.tsv'), ('notes', '笔记.md')) if (folder / path).exists()
  ]
  return '  '.join(held)


class Printer:
  """Download progress for a log: each lecture's ID, each video at every quarter, then what the lecture holds."""

  def __init__(self, folder):
    self.folder = folder
    self.lecture, self.task, self.quarter = None, None, 0

  def __call__(self, lecture, task, fraction=0, speed=None, remaining=None):
    if lecture['id'] != self.lecture:
      self.lecture = lecture['id']
      print(lecture['id'], flush=True)
    if task != self.task:
      self.task, self.quarter = task, 0
    if task in STREAMS and self.quarter < int(fraction * 4) < 4:
      self.quarter = int(fraction * 4)
      left = f'  {transcript.stamp(remaining)} left' if remaining else ''
      print(f'  {task} video {fraction:.0%}  {speed / 1e6:.0f} MB/s{left}', flush=True)
    elif task == 'done':
      print('  ' + holdings(lecture, self.folder / lecture['id']), flush=True)


def course_id(value):
  """Accept a numeric course ID or a coursedetail URL."""
  if value.isdigit():
    return value
  match = re.search(r'[?&]course_id=(\d+)', value)
  if not match:
    raise argparse.ArgumentTypeError(f'{value!r} is not a course ID or coursedetail URL; `courses` lists the IDs')
  return match[1]


def capture(value):
  return int(Path(value).stem)  # 44, 044.jpg or slides/044.jpg


def absolute(value):
  return Path(value).resolve()  # so that `.` too has the lecture ID as its name


def parse():
  parser = argparse.ArgumentParser(description=__doc__)
  commands = parser.add_subparsers(dest='command', required=True)
  commands.add_parser('login', help='Sign in through the local page unless the saved session is still valid')
  listing = commands.add_parser('courses', help='List enrolled courses by term: id, title, teacher')
  listing.add_argument('--term', help='Only this term, such as 2026-2027-1')
  lookup = commands.add_parser('search', help='Search every course on the platform, one page per call')
  lookup.add_argument('keyword', nargs='?', default='', help='Words in the course title or teacher name')
  lookup.add_argument('--term', help='Such as 2024-2025-2')
  lookup.add_argument('--college', help='Offering college, such as 计算机学院')
  lookup.add_argument('--sort', choices=SORTS, help='Default: platform order')
  lookup.add_argument('--page', type=int, default=1)
  lookup.add_argument('--limit', type=int, default=50, choices=range(1, 101), metavar='1-100')
  replays = commands.add_parser('lectures', help='List a course’s replays: lecture ID, sub_id and what is saved')
  replays.add_argument('course', type=course_id, help='Course ID or coursedetail URL')
  replays.add_argument('-o', '--output', type=Path, default=Path('.'), help='Workspace (default: current folder)')
  fetch = commands.add_parser('download', help='Download lecture resources and update course.json')
  fetch.add_argument('course', type=course_id, help='Course ID or coursedetail URL')
  chosen = fetch.add_mutually_exclusive_group(required=True)
  chosen.add_argument('-l', '--lecture', action='append', help='Lecture ID or sub_id; repeat it for several')
  chosen.add_argument('--all', action='store_true', help='Every replay of the course except dropped ones')
  fetch.add_argument(
    '--video', nargs='*', choices=STREAMS, help='Recording views, teacher and screen (default: teacher)'
  )
  fetch.add_argument('--subtitles', action='store_true', help='Platform subtitles as .cache/subtitles.tsv')
  fetch.add_argument('--slides', action='store_true', help='Timed PPT captures in slides/')
  fetch.add_argument('--pdf', action='store_true', help='Combine every capture into 课件.pdf')
  fetch.add_argument('--connections', type=int, default=16)
  fetch.add_argument('--overwrite', action='store_true', help='Fetch selected resources again')
  fetch.add_argument('-o', '--output', type=Path, default=Path('.'), help='Workspace (default: current folder)')
  empty = commands.add_parser('drop', help='Delete empty lectures and mark them dropped in course.json')
  empty.add_argument('lectures', nargs='+', type=absolute, help='Lecture folders')
  page = commands.add_parser('ui', help='Open the download page and keep it running')
  page.add_argument('course', nargs='?', type=course_id, help='Course to open first')
  page.add_argument('-o', '--output', type=Path, default=Path('.'), help='Workspace (default: current folder)')

  asr = commands.add_parser('transcribe', help='Transcribe recordings with BCut into .cache/transcript.tsv')
  asr.add_argument('paths', nargs='+', type=absolute, help='Lecture folders, course folders or .mp4 recordings')
  asr.add_argument('--overwrite', action='store_true', help='Extract and transcribe again')
  fix = commands.add_parser('replace', help='Fix recurring transcript errors, then export 文字稿.txt and 字幕.srt')
  fix.add_argument('paths', nargs='+', type=absolute, help='Lecture or course folders')
  fix.add_argument(
    '-r', dest='pairs', nargs=2, action='append', required=True, metavar=('WRONG', 'RIGHT'), help='Repeat for several'
  )
  text = argparse.ArgumentParser(add_help=False)
  text.add_argument('lecture', type=absolute)
  text.add_argument('--source', choices=['transcript', 'subtitles'], default='transcript')
  find = commands.add_parser('query', parents=[text], help='Print matching segments, each after the capture on screen')
  find.add_argument('--keyword')
  find.add_argument('--start', type=transcript.seconds, default=0, help='Seconds or [h:]mm:ss')
  find.add_argument('--end', type=transcript.seconds, default=math.inf, help='Seconds or [h:]mm:ss')
  render = commands.add_parser('export', parents=[text], help='Write 文字稿.txt, 字幕.srt or 字幕.vtt')
  render.add_argument('--format', choices=['txt', 'srt', 'vtt'], action='append')
  attach = commands.add_parser(
    'embed', help='Add a subtitle file to a recording as a soft track, replacing earlier ones'
  )
  attach.add_argument('video', type=absolute, help='Recording to replace, such as 录播（教室）.mp4')
  attach.add_argument('subtitles', type=absolute, help='.srt or .vtt file')

  grid = commands.add_parser('sheet', help='Write contact sheets of numbered, timed thumbnails to .cache/')
  grid.add_argument('lecture', type=absolute)
  grid.add_argument('captures', nargs='*', type=capture, help='Capture numbers; default: every capture')
  grid.add_argument('--columns', type=int, default=4, help='Fewer columns give larger thumbnails')
  grid.add_argument('--rows', type=int, default=4)
  alike = commands.add_parser(
    'similar', help='Print groups of near-identical captures with their times, one group a line'
  )
  alike.add_argument('lecture', type=absolute)
  alike.add_argument('--distance', type=int, default=12, help='Most differing bits of 256 (default: 12)')
  combine = commands.add_parser('pdf', help='Write 课件.pdf, one capture per page')
  combine.add_argument('lecture', type=absolute)
  combine.add_argument('captures', nargs='*', type=capture, help='Capture numbers in page order; default: all')
  return parser.parse_args()


def main():
  for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding='utf-8')
  args = parse()
  if args.command == 'ui':  # the page signs in itself
    import server

    upgrade_to_campus()
    server.serve(Yanhekt(), args.output, args.course)
  elif args.command == 'login':
    signed_in()
    print('Signed in.')
  elif args.command == 'courses':
    courses = [course for course in signed_in().courses() if args.term in (None, course['term'])]
    for number, (term, group) in enumerate(groupby(courses, key=lambda course: course['term'])):
      print(term + ('  latest term' if number == 0 and args.term is None else ''))
      for course in group:
        print(f'  {course["id"]}  {course["title"]}  {course["teacher"]}')
  elif args.command == 'search':
    total, courses = signed_in().search(
      args.keyword, term=args.term, college=args.college, sort=args.sort, page=args.page, per_page=args.limit
    )
    print(f'{total} courses, page {args.page} of {math.ceil(total / args.limit)}')
    for course in courses:
      print(f'  {course["id"]}  {course["title"]}  {course["teacher"]}  {course["term"]}  {course["college"]}'.rstrip())
  elif args.command == 'lectures':
    course = signed_in().course(args.course)
    folder = download.course_folder(args.output, course)
    print(f'{course["title"]}  {course["term"]}  {course["teacher"]}')
    for lecture in download.lectures(course, download.read_index(folder)):
      print(f'  {lecture["id"]}  {lecture["sub_id"]}  {holdings(lecture, folder / lecture["id"])}'.rstrip())
  elif args.command == 'download':
    client = signed_in()
    course = client.course(args.course)
    saved = download.download(
      client,
      course,
      args.output,
      select(course, args.lecture) if args.lecture else None,
      videos=() if args.video is None else dict.fromkeys(args.video or ['teacher']),
      subtitles=args.subtitles,
      slides=args.slides,
      pdf=args.pdf,
      connections=args.connections,
      overwrite=args.overwrite,
      report=Printer(download.course_folder(args.output, course)),
    )
    print(f'Saved to {saved}')
  elif args.command == 'drop':
    for lecture in args.lectures:
      download.drop(lecture)
      print(f'Dropped {lecture.name}')

  elif args.command == 'transcribe':
    failed = transcribe.transcribe(args.paths, args.overwrite)
    if failed:
      raise SystemExit(f'{failed} recordings failed')
  elif args.command == 'replace':
    lectures = [lecture for path in args.paths for lecture in transcript.lecture_folders(path)]
    lectures = [lecture for lecture in lectures if (lecture / '.cache' / 'transcript.tsv').exists()]
    if not lectures:
      raise ValueError('No transcripts found; run `transcribe` first')
    for lecture in lectures:
      hits = transcript.replace(lecture, args.pairs)
      print(lecture.name)
      for (wrong, right), count in zip(args.pairs, hits):
        if count:
          print(f'  {wrong} -> {right}  {count}')
  elif args.command == 'query':
    for line in transcript.query(args.lecture, args.source, args.keyword, args.start, args.end):
      print(line)
  elif args.command == 'export':
    for format in args.format or ['txt']:
      print(transcript.export(args.lecture, format, args.source).name)
  elif args.command == 'embed':
    transcript.embed(args.video, args.subtitles)
    print(args.video.name)

  elif args.command == 'sheet':
    for path in slides.sheets(args.lecture, slides.captures(args.lecture, args.captures), args.columns, args.rows):
      print(path.relative_to(args.lecture))
  elif args.command == 'similar':
    for group in slides.similar(args.lecture, slides.captures(args.lecture), args.distance):
      print('  '.join(f'{entry["file"].removesuffix(".jpg")}@{transcript.stamp(entry["time_s"])}' for entry in group))
  elif args.command == 'pdf':
    entries = slides.captures(args.lecture, args.captures)
    print(f'{slides.write_pdf(args.lecture, entries).name}  {len(entries)} pages')


if __name__ == '__main__':
  try:
    main()
  except KeyboardInterrupt:
    raise SystemExit(130) from None
  except (APIError, ValueError, OSError, requests.RequestException, subprocess.CalledProcessError) as error:
    raise SystemExit(describe(error)) from None
