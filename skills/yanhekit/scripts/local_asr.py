# /// script
# requires-python = '>=3.11,<3.13'
# dependencies = [
#   'funasr==1.4.16',
#   'imageio-ffmpeg>=0.6',
#   'modelscope==1.40.2',
#   'torch==2.7.0',
#   'torchaudio==2.7.0',
#   'transformers<5',
# ]
# [tool.uv.sources]
# torch = [{ index = 'pytorch', marker = "sys_platform != 'darwin'" }]
# torchaudio = [{ index = 'pytorch', marker = "sys_platform != 'darwin'" }]
# [[tool.uv.index]]
# name = 'pytorch'
# url = 'https://download.pytorch.org/whl/cu128'
# explicit = true
# ///
"""Optional local ASR worker, launched by `yanhekit.py transcribe --engine local`."""

import argparse
import hashlib
import logging
import os
import subprocess
import sys
import tempfile
from functools import partial
from importlib.metadata import version
from pathlib import Path

from local_transcribe import read_hotwords, transcribe_lecture
from transcript import write_text
from workspace import Ticker, log, timeline

MODELS = {
  'model': 'iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch',
  'vad_model': 'iic/speech_fsmn_vad_zh-cn-16k-common-pytorch',
  'punc_model': 'iic/punc_ct-transformer_cn-en-common-vocab471067-large',
}


def sentence_rows(results):
  """FunASR's sentence milliseconds as the shared (seconds, seconds, text) rows."""
  rows = []
  for item in results:
    sentences = item.get('sentence_info', [])
    if item.get('text', '').strip() and not sentences:
      raise ValueError('Local ASR returned text without sentence timestamps')
    rows.extend((s['start'] / 1000, s['end'] / 1000, s['text']) for s in sentences)
  return rows


class Recognizer:
  """Load one Paraformer/VAD/punctuation pipeline and share it across lectures."""

  def __init__(self, paths, hotword_file, device, batch_seconds):
    self.paths, self.hotword_file = paths, hotword_file
    self.device, self.batch_seconds = device, batch_seconds
    self.model = None

  def __call__(self, audio):
    import torch
    from funasr import AutoModel

    logging.getLogger().setLevel(logging.ERROR)
    logging.getLogger('jieba').setLevel(logging.ERROR)

    if self.model is None:
      if self.device == 'cuda':
        if not torch.cuda.is_available():
          raise RuntimeError('CUDA is unavailable; install a compatible NVIDIA driver or use --device cpu')
        # Limit the allocator to 18 GiB, leaving room for the display and non-PyTorch CUDA allocations.
        total = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(min(0.8, 18 * 1024**3 / total))
      self.model = AutoModel(
        **self.paths,
        device='cuda:0' if self.device == 'cuda' else 'cpu',
        vad_kwargs={'max_single_segment_time': 30000},
        disable_update=True,
        disable_pbar=True,
        trust_remote_code=False,
        ncpu=4,
        log_level='ERROR',
      )
    results = self.model.generate(
      input=audio,
      batch_size_s=self.batch_seconds,
      sentence_timestamp=True,
      hotword=str(self.hotword_file),
      disable_pbar=True,
      disable_log=True,
    )
    return sentence_rows(results)


def model_paths():
  """Fetch model artifacts only; AutoModel receives local directories and never a remote input."""
  from modelscope import snapshot_download

  logging.getLogger('modelscope_hub').setLevel(logging.ERROR)

  return {
    key: snapshot_download(
      repo, local_files_only=os.environ.get('MODELSCOPE_OFFLINE') == '1',
      allow_patterns=['*.pt', '*.yaml', '*.json', 'am.mvn', 'seg_dict'],
    )
    for key, repo in MODELS.items()
  }  # fmt: skip


def model_hashes(paths):
  """Bind resume checkpoints to the actual weights and decoding assets, including cached model revisions."""
  hashes = {}
  for name, directory in paths.items():
    digest = hashlib.sha256()
    for path in sorted(Path(directory).iterdir()):
      if path.suffix in ('.pt', '.yaml', '.json') or path.name in ('am.mvn', 'seg_dict'):
        digest.update(path.name.encode('utf-8'))
        with path.open('rb') as file:
          digest.update(hashlib.file_digest(file, 'sha256').digest())
    hashes[name] = digest.hexdigest()
  return hashes


def main():
  for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding='utf-8')
  # Model downloads are the only network operation; suppress optional library telemetry.
  os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
  os.environ['DO_NOT_TRACK'] = '1'
  os.environ['TQDM_DISABLE'] = '1'
  os.environ['MODELSCOPE_LOG_LEVEL'] = '40'
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('lectures', nargs='+', type=Path)
  parser.add_argument('--hotwords', type=Path)
  parser.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
  parser.add_argument('--batch-seconds', type=int, default=60)
  parser.add_argument('--overwrite', action='store_true')
  args = parser.parse_args()
  if args.batch_seconds < 1:
    parser.error('--batch-seconds must be positive')
  hotwords = read_hotwords(args.hotwords) if args.hotwords else []
  pending = []
  for lecture in args.lectures:
    if timeline(lecture, 'transcript').exists() and not args.overwrite:
      if not (lecture / '字幕.txt').exists():
        write_text(lecture)
      log(lecture, 'kept existing transcript')
    else:
      pending.append(lecture)
  if not pending:
    return
  with Ticker(partial(log, pending[0]), 'preparing local ASR models'):
    paths = model_paths()
    config = {
      'engine': 'paraformer',
      'models': model_hashes(paths),
      'funasr': version('funasr'),
      'torch': version('torch'),
      'hotwords': hotwords,
      'device': args.device,
      'batch_seconds': args.batch_seconds,
    }
  failed = 0
  with tempfile.TemporaryDirectory(prefix='yanhekit-asr-') as temporary:
    hotword_file = Path(temporary) / 'hotwords.txt'
    hotword_file.write_text('\n'.join(hotwords) + '\n' if hotwords else '', encoding='utf-8')
    recognize = Recognizer(paths, hotword_file, args.device, args.batch_seconds)
    for lecture in pending:
      try:
        transcribe_lecture(lecture, recognize, config, args.overwrite)
      except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        log(lecture, f'local transcription failed: {error}')
        failed += 1
  if failed:
    raise SystemExit(f'{failed} local transcription(s) failed')


if __name__ == '__main__':
  try:
    main()
  except KeyboardInterrupt:
    raise SystemExit(130) from None
