"""Print the expense table region from each historical PDF.

Looks for lines matching `第N天.*总价` and dumps ~10 lines each.
"""
import sys, os, glob, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from services.file_extractor import extract_text_from_pdf
from services.ai_parser import _normalize

PDFS = sorted(glob.glob(os.path.expanduser('~/Downloads/*.pdf')))
PDFS = [p for p in PDFS if any(k in os.path.basename(p) for k in (
    '日本', '缅甸', '斯里兰卡', '韩国', '马来西亚', '新加坡', '马尔代夫'
))]

for pdf in PDFS:
    with open(pdf, 'rb') as f:
        text = _normalize(extract_text_from_pdf(f.read()))
    print('=' * 70)
    print('PDF:', os.path.basename(pdf))
    print('=' * 70)
    m = re.search(r'全部费用', text) or re.search(r'花费\s+', text)
    start = m.start() if m else 0
    end_m = re.search(r'出行清单|行前事项', text[start:])
    end = start + (end_m.start() if end_m else 3000)
    print(text[start:end])
    print()
