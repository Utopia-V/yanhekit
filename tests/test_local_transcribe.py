"""Local ASR's storage and resume contract, without model downloads or a GPU."""

import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'yanhekit' / 'scripts'))

import numpy as np

import local_transcribe as local
import transcript
from workspace import read_json, read_tsv, timeline


class LocalTranscribeTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.lecture = Path(self.temp.name) / '课程' / '课次'
    self.lecture.mkdir(parents=True)
    self.video = self.lecture / '录播-教室.mp4'
    self.video.write_bytes(b'recording')
    self.config = {'engine': 'test', 'hotwords': ['Q 学习']}

  def run_lecture(self, recognize, audio, **kwargs):
    with patch.object(local, 'decode', side_effect=audio), patch.object(local, 'log'):
      local.transcribe_lecture(self.lecture, recognize, self.config, **kwargs)

  def test_hotwords(self):
    path = Path(self.temp.name) / 'terms.txt'
    path.write_text(' 强化学习 \nQ 学习\n\n强化学习\n', encoding='utf-8')
    self.assertEqual(local.read_hotwords(path), ['强化学习', 'Q 学习'])

  def test_timestamp_validation(self):
    self.assertEqual(local.checked_rows([(0, 1, 'a\tb\n')], 10, 1), [(10, 11, 'a b')])
    for rows in [
      [(-1, 1, 'x')],
      [(0, 0, 'x')],
      [(0, 2, 'x')],
      [(1.02, 1.03, 'x')],
      [(float('nan'), 1, 'x')],
      [(0.5, 1, 'x'), (0.1, 1, 'y')],
    ]:
      with self.subTest(rows=rows), self.assertRaises(ValueError):
        local.checked_rows(rows, 0, 1)

  def test_quiet_boundary(self):
    audio = np.ones(local.CHUNK_SECONDS * local.SAMPLE_RATE, dtype=np.float32)
    silent = 297 * local.SAMPLE_RATE
    audio[silent : silent + local.SAMPLE_RATE // 5] = 0
    cut = local.quiet_cut(audio)
    self.assertEqual(len(cut), silent + local.SAMPLE_RATE // 10)
    short = audio[:100]
    self.assertIs(local.quiet_cut(short), short)

  def test_outputs_work_with_query_replace_and_srt(self):
    before = self.video.stat()
    self.run_lecture(lambda _: [(0.1, 0.8, '强化学习\nUCB')], [np.zeros(local.SAMPLE_RATE)])
    self.assertEqual(read_tsv(timeline(self.lecture, 'transcript')), [(0.1, 0.8, '强化学习 UCB')])
    self.assertEqual(list(transcript.query(self.lecture, pattern=re.compile('UCB'))), ['[00:00:00] 强化学习 UCB'])
    self.assertIn('00:00:00,100 --> 00:00:00,800', transcript.srt(self.lecture))
    self.assertEqual(transcript.replace(self.lecture, [('UCB', '置信上界')]), [1])
    self.assertEqual((self.lecture / '字幕.txt').read_text(encoding='utf-8'), '[00:00:00] 强化学习 置信上界\n')
    self.assertEqual(self.video.stat().st_mtime_ns, before.st_mtime_ns)
    self.assertEqual(self.video.read_bytes(), b'recording')

  def test_resume_after_interruption(self):
    with patch.object(local, 'CHUNK_SECONDS', 1), patch.object(local, 'quiet_cut', side_effect=lambda x: x):
      with self.assertRaises(RuntimeError):
        self.run_lecture(lambda _: [(0, 0.5, 'first')], [np.zeros(local.SAMPLE_RATE), RuntimeError('interrupted')])
      self.assertFalse(timeline(self.lecture, 'transcript').exists())
      with (
        patch.object(local, 'decode', return_value=np.zeros(local.SAMPLE_RATE // 2)) as decode,
        patch.object(local, 'log'),
      ):
        local.transcribe_lecture(self.lecture, lambda _: [(0, 0.4, 'second')], self.config)
      self.assertEqual(decode.call_args.args[1], 1)
    self.assertEqual(read_tsv(timeline(self.lecture, 'transcript')), [(0, 0.5, 'first'), (1, 1.4, 'second')])
    state = read_json(self.lecture / '.cache' / 'local-asr.json', None)
    self.assertTrue(state['complete'])
    self.assertEqual(state['samples'], local.SAMPLE_RATE * 1.5)

  def test_existing_transcript_skips_model_and_repairs_text(self):
    self.run_lecture(lambda _: [(0, 0.5, 'kept')], [np.zeros(local.SAMPLE_RATE)])
    (self.lecture / '字幕.txt').unlink()
    self.run_lecture(lambda _: self.fail('model called for finished lecture'), [])
    self.assertEqual((self.lecture / '字幕.txt').read_text(encoding='utf-8'), '[00:00:00] kept\n')

  def test_changed_hotwords_refuse_stale_checkpoint(self):
    with self.assertRaises(RuntimeError):
      self.run_lecture(lambda _: (_ for _ in ()).throw(RuntimeError('interrupted')), [np.zeros(local.SAMPLE_RATE)])
    # Make a resumable checkpoint before changing its signature.
    with patch.object(local, 'CHUNK_SECONDS', 1), patch.object(local, 'quiet_cut', side_effect=lambda x: x):
      with self.assertRaises(RuntimeError):
        self.run_lecture(lambda _: [(0, 0.5, 'first')], [np.zeros(local.SAMPLE_RATE), RuntimeError('interrupted')])
      self.config['hotwords'] = ['different']
      with self.assertRaisesRegex(ValueError, 'checkpoint differs'):
        self.run_lecture(lambda _: self.fail('stale model called'), [])

  def test_invalid_results_never_publish(self):
    with self.assertRaises(ValueError):
      self.run_lecture(lambda _: [(0, 100, 'invalid')], [np.zeros(local.SAMPLE_RATE)])
    self.assertFalse(timeline(self.lecture, 'transcript').exists())
    self.assertFalse((self.lecture / '字幕.txt').exists())

  def test_unfinished_download_refused(self):
    (self.lecture / '录播-教室.part.mp4').write_bytes(b'unfinished')
    with self.assertRaisesRegex(ValueError, 'unfinished'):
      self.run_lecture(lambda _: self.fail('model called'), [])

  def test_orphan_text_is_preserved(self):
    (self.lecture / '字幕.txt').write_text('keep', encoding='utf-8')
    with self.assertRaisesRegex(ValueError, 'exists without'):
      self.run_lecture(lambda _: self.fail('model called'), [])
    self.assertEqual((self.lecture / '字幕.txt').read_text(encoding='utf-8'), 'keep')

  def test_empty_result_not_published(self):
    with self.assertRaisesRegex(ValueError, 'no speech'):
      self.run_lecture(lambda _: [], [np.zeros(local.SAMPLE_RATE)])
    self.assertFalse(timeline(self.lecture, 'transcript').exists())


if __name__ == '__main__':
  unittest.main()
