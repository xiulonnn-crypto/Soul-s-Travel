"""Walk all historical travel PDFs through the current parser and dump a
compact summary of what the parser *currently* believes about each file.

Use this output + direct PDF reading to construct ground-truth fixtures.

Run: python3 backend/scripts/baseline_all_pdfs.py
"""
import sys, os, json, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.file_extractor import extract_text_from_pdf
from services.ai_parser import parse_text

PDFS = sorted(glob.glob(os.path.expanduser('~/Downloads/*.pdf')))
TRIP_PDFS = [p for p in PDFS if any(k in os.path.basename(p) for k in (
    '日本', '缅甸', '斯里兰卡', '韩国', '马来西亚', '新加坡', '马尔代夫'
))]


def summarize(pdf_path):
    with open(pdf_path, 'rb') as f:
        text = extract_text_from_pdf(f.read())
    result = parse_text(text)
    trip = result.get('trip', {})
    legs = result.get('legs', [])
    expenses = result.get('expenses', [])

    per_day_total = {}
    for e in expenses:
        if e.get('currency') != 'CNY':
            continue
        per_day_total.setdefault(e['date'], 0.0)
        per_day_total[e['date']] += e['amount']

    all_days = []
    for leg in legs:
        for d in leg['days']:
            all_days.append({
                'date': d['date'],
                'leg_city': leg['city'],
                'activities': d['activities'],
                'hotel': d.get('accommodation'),
                'transport': d.get('transport', []),
            })

    return {
        'pdf': os.path.basename(pdf_path),
        'trip': {
            'title': trip.get('title'),
            'start_date': trip.get('start_date'),
            'end_date': trip.get('end_date'),
            'traveler_count': trip.get('traveler_count'),
        },
        'legs': [
            {'city': L['city'], 'country': L['country'],
             'start': L['start_date'], 'end': L['end_date'],
             'day_count': len(L['days'])}
            for L in legs
        ],
        'days': all_days,
        'expense_count': len(expenses),
        'expense_cny_total': round(sum(e['amount'] for e in expenses if e['currency'] == 'CNY'), 2),
        'expense_per_day_cny': {k: round(v, 2) for k, v in per_day_total.items()},
    }


def main():
    out = {}
    for pdf in TRIP_PDFS:
        print(f'--- {os.path.basename(pdf)} ---', file=sys.stderr)
        try:
            out[os.path.basename(pdf)] = summarize(pdf)
        except Exception as e:
            out[os.path.basename(pdf)] = {'error': str(e)}
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
