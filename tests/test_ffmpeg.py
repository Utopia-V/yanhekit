"""Executable selection and bounded recovery, without processing user recordings."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'yanhekit' / 'scripts'))

import workspace


class FfmpegTests(unittest.TestCase):
  def setUp(self):
    self.bundled = str(Path(workspace.imageio_ffmpeg.__file__).resolve().parent / 'binaries' / 'ffmpeg-test')
    self.selector = patch.object(workspace.imageio_ffmpeg, 'get_ffmpeg_exe', return_value=self.bundled)
    self.selector.start()
    self.addCleanup(self.selector.stop)

  def failure(self, code=-11):
    return subprocess.CalledProcessError(code, [self.bundled], output=b'partial', stderr=b'diagnostic')

  def test_success_keeps_bundled_default(self):
    result = subprocess.CompletedProcess([], 0)
    with (
      patch.object(workspace.subprocess, 'run', return_value=result) as run,
      patch.object(workspace.shutil, 'which') as which,
    ):
      self.assertIs(workspace.ffmpeg('-version'), result)
    run.assert_called_once_with([self.bundled, '-v', 'error', '-y', '-version'], check=True)
    which.assert_not_called()

  def test_environment_override_is_used(self):
    self.selector.stop()
    with (
      patch.dict(os.environ, {'IMAGEIO_FFMPEG_EXE': '/custom/ffmpeg'}),
      patch.object(workspace.subprocess, 'run') as run,
    ):
      workspace.ffmpeg('-version')
    self.assertEqual(run.call_args.args[0][0], '/custom/ffmpeg')

  def test_signal_retries_once_and_preserves_input_and_capture(self):
    result = subprocess.CompletedProcess([], 0, stdout=b'retried')
    with (
      patch.object(workspace.subprocess, 'run', side_effect=[self.failure(), result]) as run,
      patch.object(workspace.shutil, 'which', return_value='/system/ffmpeg'),
      patch.object(workspace, 'log') as log,
    ):
      actual = workspace.ffmpeg('-i', 'pipe:', '-f', 'null', '-', input=b'subtitles', stdout=subprocess.PIPE)
    self.assertIs(actual, result)
    self.assertEqual(run.call_count, 2)
    first, second = run.call_args_list
    self.assertEqual(first.args[0][0], self.bundled)
    self.assertEqual(second.args[0][0], '/system/ffmpeg')
    self.assertEqual(first.args[0][1:], second.args[0][1:])
    self.assertEqual(first.kwargs, {'check': True, 'input': b'subtitles', 'stdout': subprocess.PIPE})
    self.assertEqual(first.kwargs, second.kwargs)
    log.assert_called_once_with(None, 'ffmpeg: bundled binary terminated by signal 11; retrying /system/ffmpeg')

  def test_regular_failure_is_preserved(self):
    error = self.failure(1)
    with (
      patch.object(workspace.subprocess, 'run', side_effect=error) as run,
      patch.object(workspace.shutil, 'which') as which,
      self.assertRaises(subprocess.CalledProcessError) as caught,
    ):
      workspace.ffmpeg('-bad-option')
    self.assertIs(caught.exception, error)
    run.assert_called_once()
    which.assert_not_called()

  def test_custom_binary_crash_is_not_replaced(self):
    with (
      patch.object(workspace.imageio_ffmpeg, 'get_ffmpeg_exe', return_value='/custom/ffmpeg'),
      patch.object(workspace.subprocess, 'run', side_effect=self.failure()) as run,
      patch.object(workspace.shutil, 'which') as which,
      self.assertRaises(subprocess.CalledProcessError),
    ):
      workspace.ffmpeg('-version')
    run.assert_called_once()
    which.assert_not_called()

  def test_no_alternative_preserves_original_failure(self):
    for alternative in [None, self.bundled]:
      error = self.failure()
      with (
        self.subTest(alternative=alternative),
        patch.object(workspace.subprocess, 'run', side_effect=error) as run,
        patch.object(workspace.shutil, 'which', return_value=alternative),
        patch.object(workspace, 'log') as log,
        self.assertRaises(subprocess.CalledProcessError) as caught,
      ):
        workspace.ffmpeg('-version')
      self.assertIs(caught.exception, error)
      run.assert_called_once()
      log.assert_not_called()

  @unittest.skipIf(os.name == 'nt', 'Symlink creation may need privileges on Windows')
  def test_path_symlink_to_bundle_is_not_retried(self):
    with tempfile.TemporaryDirectory() as temporary:
      package = Path(temporary) / 'package'
      binaries = package / 'binaries'
      binaries.mkdir(parents=True)
      exe = binaries / 'ffmpeg-test'
      exe.touch()
      alias = Path(temporary) / 'ffmpeg'
      alias.symlink_to(exe)
      with (
        patch.object(workspace.imageio_ffmpeg, '__file__', str(package / '__init__.py')),
        patch.object(workspace.imageio_ffmpeg, 'get_ffmpeg_exe', return_value=str(exe)),
        patch.object(workspace.subprocess, 'run', side_effect=self.failure()) as run,
        patch.object(workspace.shutil, 'which', return_value=str(alias)),
        self.assertRaises(subprocess.CalledProcessError),
      ):
        workspace.ffmpeg('-version')
      run.assert_called_once()

  def test_second_failure_is_reported_without_another_retry(self):
    second = self.failure(-9)
    with (
      patch.object(workspace.subprocess, 'run', side_effect=[self.failure(), second]) as run,
      patch.object(workspace.shutil, 'which', return_value='/system/ffmpeg'),
      patch.object(workspace, 'log') as log,
      self.assertRaises(subprocess.CalledProcessError) as caught,
    ):
      workspace.ffmpeg('-version')
    self.assertIs(caught.exception, second)
    self.assertEqual(run.call_count, 2)
    log.assert_called_once()

  def test_missing_executable_does_not_trigger_crash_recovery(self):
    with (
      patch.object(workspace.subprocess, 'run', side_effect=FileNotFoundError),
      patch.object(workspace.shutil, 'which') as which,
      self.assertRaises(FileNotFoundError),
    ):
      workspace.ffmpeg('-version')
    which.assert_not_called()


if __name__ == '__main__':
  unittest.main()
