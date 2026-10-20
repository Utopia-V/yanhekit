"""BCut remains the default; only explicit local requests launch the optional runtime."""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'yanhekit' / 'scripts'))

import yanhekit


class LocalCliTests(unittest.TestCase):
  def args(self, *options):
    with patch.object(sys, 'argv', ['yanhekit.py', 'transcribe', '课程', *options]):
      return yanhekit.parse()

  def test_bcut_is_default(self):
    self.assertEqual(self.args().engine, 'bcut')
    with (
      patch.object(yanhekit, 'parse', return_value=self.args()),
      patch.object(yanhekit, 'having', return_value=[]),
      patch.object(yanhekit.transcribe, 'transcribe', return_value=0) as bcut,
      patch.object(yanhekit.subprocess, 'run') as child,
    ):
      yanhekit.main()
    bcut.assert_called_once_with([], False)
    child.assert_not_called()

  def test_local_forwarding_and_failure(self):
    args = self.args('--engine', 'local', '--hotwords', '术语.txt', '--device', 'cpu', '--batch-seconds', '30')
    lecture = Path('/tmp/课程/课次')
    with (
      patch.object(yanhekit, 'parse', return_value=args),
      patch.object(yanhekit, 'having', return_value=[lecture]),
      patch.object(yanhekit.transcribe, 'transcribe') as bcut,
      patch.object(yanhekit.subprocess, 'run', return_value=SimpleNamespace(returncode=7)) as child,
      self.assertRaises(SystemExit) as error,
    ):
      yanhekit.main()
    self.assertEqual(error.exception.code, 7)
    command = child.call_args.args[0]
    self.assertEqual(command[:2], ['uv', 'run'])
    self.assertEqual(Path(command[2]).name, 'local_asr.py')
    self.assertIn(str(lecture), command)
    self.assertEqual(command[-2:], ['--hotwords', str(Path('术语.txt').resolve())])
    self.assertEqual(child.call_args.kwargs['env'], {**os.environ, 'PYTHONUTF8': '1'})
    bcut.assert_not_called()

  def test_bcut_does_not_ignore_local_options(self):
    args = self.args('--hotwords', '术语.txt')
    with (
      patch.object(yanhekit, 'parse', return_value=args),
      patch.object(yanhekit, 'having', return_value=[]),
      self.assertRaisesRegex(ValueError, 'require --engine local'),
    ):
      yanhekit.main()

  def test_batch_size_must_be_positive(self):
    with self.assertRaises(SystemExit), patch.object(sys, 'stderr'):
      self.args('--batch-seconds', '0')


if __name__ == '__main__':
  unittest.main()
