"""Review a lecture's PPT captures and combine the chosen ones into 课件.pdf."""

import math
from itertools import combinations, pairwise

from PIL import Image, ImageDraw, ImageFont

from transcript import clock, read_captures

SHEET_WIDTH = 1600
LABEL = 30


def captures(lecture, numbers=()):
  """Entries of slides/index.json, or those with the given capture numbers in the given order."""
  entries = read_captures(lecture)
  if not entries:
    raise ValueError(f'{lecture.name} has no captures; `download --slides` saves them')
  missing = [str(n) for n in numbers if not 1 <= n <= len(entries)]
  if missing:
    raise ValueError(f'No capture {", ".join(missing)}; captures run from 1 to {len(entries)}')
  return [entries[n - 1] for n in numbers] or entries


def sheets(lecture, entries, columns=4, rows=4):
  """Write labelled thumbnails, columns x rows to a sheet, as .cache/sheet-<first>-<last>.jpg."""
  width = SHEET_WIDTH // columns
  height = width * 9 // 16
  font = ImageFont.load_default(20)
  paths = []
  (lecture / '.cache').mkdir(exist_ok=True)
  for old in (lecture / '.cache').glob('sheet-*.jpg'):  # sheets of other ranges and layouts
    old.unlink()
  for start in range(0, len(entries), columns * rows):
    group = entries[start : start + columns * rows]
    sheet = Image.new('RGB', (SHEET_WIDTH, math.ceil(len(group) / columns) * (height + LABEL)), 'white')
    draw = ImageDraw.Draw(sheet)
    for n, entry in enumerate(group):
      x, y = n % columns * width, n // columns * (height + LABEL)
      with Image.open(lecture / 'slides' / entry['file']) as image:
        image.thumbnail((width - 8, height))
        sheet.paste(image.convert('RGB'), (x + 4, y + LABEL))
      label = f'{entry["file"].removesuffix(".jpg")}  {clock(entry["time_s"])}'
      draw.text((x + 6, y + 5), label, fill='black', font=font)
    first, last = (entry['file'].removesuffix('.jpg') for entry in (group[0], group[-1]))
    path = lecture / '.cache' / f'sheet-{first}-{last}.jpg'
    sheet.save(path, quality=85)
    paths.append(path)
  return paths


def fingerprint(path, size=16):
  """A 256-bit difference hash: whether each pixel of a small grayscale copy is brighter than its right neighbour."""
  with Image.open(path) as image:
    image.draft('L', (size * 8, size * 8))  # decode a JPEG at reduced scale
    pixels = image.convert('L').resize((size + 1, size)).tobytes()
  rows = (pixels[start : start + size + 1] for start in range(0, len(pixels), size + 1))
  return int(''.join('1' if left > right else '0' for row in rows for left, right in pairwise(row)), 2)


def similar(lecture, entries, distance=12):
  """Groups of captures linked through fingerprints that differ in at most `distance` bits, in capture order."""
  prints = [fingerprint(lecture / 'slides' / entry['file']) for entry in entries]
  parent = list(range(len(entries)))

  def root(i):
    while parent[i] != i:
      parent[i] = parent[parent[i]]
      i = parent[i]
    return i

  for i, j in combinations(range(len(entries)), 2):
    if (prints[i] ^ prints[j]).bit_count() <= distance:
      parent[root(j)] = root(i)
  groups = {}
  for i, entry in enumerate(entries):
    groups.setdefault(root(i), []).append(entry)
  return [group for group in groups.values() if len(group) > 1]


def write_pdf(lecture, entries):
  import img2pdf  # with pikepdf it takes a second to load, so only `pdf` pays for it

  output = lecture / '课件.pdf'
  output.write_bytes(img2pdf.convert([str(lecture / 'slides' / entry['file']) for entry in entries]))
  return output
