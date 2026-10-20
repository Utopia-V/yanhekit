"""Bounded, resumable local transcription; model runtimes live in local_asr.py."""

import math
import subprocess
import time
from functools import partial

import numpy as np

from transcript import write_text
from workspace import Ticker, count, ffmpeg, log, read_json, recordings, stamp, timeline, write_json, write_tsv

SAMPLE_RATE = 16000
CHUNK_SECONDS = 300


def read_hotwords(path):
  """One phrase per UTF-8 line; preserve spaces within phrases and remove duplicates."""
  return list(dict.fromkeys(line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()))


def decode(video, offset):
  """Decode at most five minutes into RAM, leaving the recording and workspace untouched."""
  result = ffmpeg(
    '-ss', f'{offset:.6f}', '-i', video, '-t', str(CHUNK_SECONDS), '-vn', '-ac', '1', '-ar', str(SAMPLE_RATE),
    '-f', 'f32le', 'pipe:1', stdout=subprocess.PIPE,
  )  # fmt: skip
  return np.frombuffer(result.stdout, dtype='<f4').copy()


def quiet_cut(audio):
  """End a full chunk at the quietest 200 ms in its last five seconds; keep every sample on resume."""
  if len(audio) < CHUNK_SECONDS * SAMPLE_RATE:
    return audio
  window = SAMPLE_RATE // 5
  tail_start = len(audio) - 5 * SAMPLE_RATE
  tail = audio[tail_start:].reshape(-1, window)
  energy = np.mean(tail**2, axis=1)
  cut = tail_start + int(np.argmin(energy)) * window + window // 2
  return audio[:cut]


def checked_rows(rows, offset, duration):
  """Validate model-relative seconds before committing them to the timeline."""
  checked = []
  previous = 0
  for start, end, text in rows:
    text = ' '.join(text.split())
    if not text:
      continue
    if not (
      math.isfinite(start)
      and math.isfinite(end)
      and 0 <= start < min(end, duration)
      and end <= duration + 0.1
      and start >= previous
    ):
      raise ValueError(f'Invalid local ASR timestamp: {start}, {end} (chunk length {duration:.3f}s)')
    checked.append((offset + start, offset + min(end, duration), text))
    previous = start
  return checked


def transcribe_lecture(lecture, recognize, config, overwrite=False):
  """Checkpoint each chunk's rows, then publish the shared TSV and text only after EOF."""
  say = partial(log, lecture)
  output = timeline(lecture, 'transcript')
  if output.exists() and not overwrite:
    if not (lecture / '字幕.txt').exists():
      write_text(lecture)
    say('kept existing transcript')
    return
  if (lecture / '字幕.txt').exists() and not output.exists() and not overwrite:
    raise ValueError(f'{lecture}: 字幕.txt exists without transcript.tsv; use --overwrite to replace it')
  video = next(iter(recordings(lecture).values()), None)
  if video is None:
    raise ValueError(f'{lecture}: no recording; run `download --classroom` first')
  if list(lecture.glob('*.part.mp4')) or list((lecture / '.cache').glob('*.parts')):
    raise ValueError(f'{lecture}: recording download is unfinished; wait for `download` to complete')
  stat = video.stat()
  signature = {
    'format': 1,
    'recording': video.name,
    'size': stat.st_size,
    'mtime_ns': stat.st_mtime_ns,
    'sample_rate': SAMPLE_RATE,
    'chunk_seconds': CHUNK_SECONDS,
    **config,
  }
  checkpoint = lecture / '.cache' / 'local-asr.json'
  state = read_json(checkpoint, None) if not overwrite else None
  if state and state['signature'] != signature:
    raise ValueError(f'{lecture}: local ASR checkpoint differs from the recording/options; use --overwrite to restart')
  state = state or {'signature': signature, 'samples': 0, 'rows': [], 'elapsed_s': 0, 'complete': False}
  started = time.monotonic()
  with Ticker(say) as ticker:
    while not state['complete']:
      offset = state['samples'] / SAMPLE_RATE
      ticker.set(f'local ASR from {stamp(offset)}')
      tick = time.monotonic()
      audio = decode(video, offset)
      if not len(audio):
        state['complete'] = True
      else:
        final = len(audio) < CHUNK_SECONDS * SAMPLE_RATE
        if not final:
          audio = quiet_cut(audio)
        rows = checked_rows(recognize(audio), offset, len(audio) / SAMPLE_RATE)
        state['rows'].extend(rows)
        state['samples'] += len(audio)
        state['complete'] = final
      current = video.stat()
      if (current.st_size, current.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
        raise ValueError(f'{lecture}: recording changed during local transcription')
      state['elapsed_s'] += time.monotonic() - tick
      write_json(checkpoint, state)
  if not state['rows']:
    raise ValueError(f'{lecture}: local ASR found no speech; checkpoint kept for inspection')
  segments = write_tsv(output, state['rows'])
  write_text(lecture)
  say(
    f'{count(segments, "segment")} in 字幕.txt; local ASR covered {stamp(state["samples"] / SAMPLE_RATE)} '
    f'in {stamp(time.monotonic() - started)} (active total {stamp(state["elapsed_s"])})'
  )
