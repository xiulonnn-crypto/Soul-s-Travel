"""Local OCR for travel itinerary images.

Uses rapidocr-onnxruntime (pure-Python ONNX, ~80MB bundled models, no network
required at runtime, no GPU). Output is a multi-line plain-text string whose
lines correspond to visual rows in the source image, suitable for the
downstream planner_parser.parse_planner_text().

Why rapidocr over easyocr / tesseract:
  - Pure pip install, no system binary (tesseract) required
  - Onnxruntime backend, much smaller install than easyocr's PyTorch
  - Strong Chinese accuracy out of the box (PP-OCRv4 family under the hood)

Row-clustering strategy (same shape as file_extractor's pdfplumber `_cells`):
  rapidocr returns [(bbox, text, confidence), ...] in roughly top-to-bottom
  order. We group boxes whose y-centers are within `Y_TOLERANCE` pixels into
  one row, sort each row left-to-right by x-center, and join with spaces.
  Rows themselves are emitted top-to-bottom as newline-separated lines.
"""
from __future__ import annotations

import io
from typing import List, Tuple

Y_TOLERANCE = 15
CONF_THRESHOLD = 0.5

_OCR_ENGINE = None


def _get_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as e:
            raise RuntimeError(
                "需要安装 rapidocr-onnxruntime 才能做本地图片识别: "
                "pip3 install rapidocr-onnxruntime"
            ) from e
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def _y_center(box) -> float:
    return (box[0][1] + box[2][1]) / 2.0


def _x_center(box) -> float:
    return (box[0][0] + box[2][0]) / 2.0


def _cluster_rows(items: List[Tuple]) -> List[List[Tuple]]:
    """Group OCR boxes whose y-centers are within Y_TOLERANCE into the same row.

    items: iterable of (box, text, conf), not assumed to be y-sorted.
    Returns a list of rows, each a list of (box, text, conf), left-to-right.
    Rows themselves are ordered top-to-bottom.
    """
    sorted_items = sorted(items, key=lambda r: _y_center(r[0]))
    rows: List[List[Tuple]] = []
    for item in sorted_items:
        y = _y_center(item[0])
        if rows and abs(y - _y_center(rows[-1][0][0])) <= Y_TOLERANCE:
            rows[-1].append(item)
        else:
            rows.append([item])
    for row in rows:
        row.sort(key=lambda r: _x_center(r[0]))
    return rows


def extract_text_from_image(image_bytes: bytes) -> str:
    """Run local OCR on an image and return multi-line plain text.

    Each output line corresponds to one visual row in the source image.
    Low-confidence fragments (< CONF_THRESHOLD) are dropped. Returns '' on
    empty OCR result (unreadable image).
    """
    engine = _get_engine()

    # rapidocr accepts raw bytes or numpy arrays. Use a BytesIO-decoded array
    # via Pillow → numpy so input works for JPG/PNG/WebP uniformly.
    from PIL import Image
    import numpy as np

    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    arr = np.array(img)

    result, _elapsed = engine(arr)
    if not result:
        return ''

    kept = [
        (box, text, conf)
        for box, text, conf in result
        if conf is None or conf >= CONF_THRESHOLD
    ]
    if not kept:
        return ''

    rows = _cluster_rows(kept)
    lines: List[str] = []
    for row in rows:
        texts = [str(text).strip() for _, text, _ in row if str(text).strip()]
        if texts:
            lines.append('  '.join(texts))
    return '\n'.join(lines)
