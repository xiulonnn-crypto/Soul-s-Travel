"""Print the overview section (above `| P1`) of each historical PDF for
ground-truth fixture construction."""
import sys, os, glob, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from services.file_extractor import extract_text_from_pdf
from services.ai_parser import _normalize

PDFS = sorted(glob.glob(os.path.expanduser('~/Downloads/*.pdf')))
PDFS = [p for p in PDFS if any(k in os.path.basename(p) for k in (
    '缅甸', '斯里兰卡', '马来西亚', '新加坡', '马尔代夫'
))]

for pdf in PDFS:
    with open(pdf, 'rb') as f:
        text = _normalize(extract_text_from_pdf(f.read()))
    print('=' * 70)
    print('PDF:', os.path.basename(pdf))
    print('=' * 70)
    m = re.search(r'\|\s*P1\b', text)
    end = m.start() if m else 2500
    print(text[:end])
    print()
