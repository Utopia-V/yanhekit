"""Model result adapters and checkpoint fingerprints need no inference runtime."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills' / 'yanhekit' / 'scripts'))

from local_asr import model_hashes, sentence_rows


class LocalAsrTests(unittest.TestCase):
  def test_millisecond_conversion(self):
    self.assertEqual(
      sentence_rows([{'text': '你好。', 'sentence_info': [{'start': 100, 'end': 900, 'text': '你好。'}]}]),
      [(0.1, 0.9, '你好。')],
    )
    self.assertEqual(sentence_rows([{'text': ''}]), [])

  def test_text_without_timing_is_an_error(self):
    with self.assertRaisesRegex(ValueError, 'without sentence timestamps'):
      sentence_rows([{'text': 'unindexed speech'}])

  def test_content_fingerprint(self):
    with tempfile.TemporaryDirectory() as temporary:
      root = Path(temporary)
      weights = root / 'model.pt'
      weights.write_bytes(b'first revision')
      before = model_hashes({'model': root})
      (root / 'README.md').write_text('irrelevant', encoding='utf-8')
      self.assertEqual(before, model_hashes({'model': root}))
      weights.write_bytes(b'newer revision')
      self.assertNotEqual(before, model_hashes({'model': root}))


if __name__ == '__main__':
  unittest.main()
