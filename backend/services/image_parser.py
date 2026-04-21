"""Parse trip itinerary from uploaded images using OpenAI Vision API."""
import os
import re
import json
import base64
from datetime import datetime

_API_KEY = None
_MODEL = None
_BASE_URL = None


def _get_config():
    global _API_KEY, _MODEL, _BASE_URL
    if _API_KEY is None:
        _API_KEY = os.environ.get('AI_API_KEY', '')
        _MODEL = os.environ.get('AI_MODEL', 'gpt-4o')
        _BASE_URL = os.environ.get('AI_BASE_URL', 'https://api.openai.com/v1')
    return _API_KEY, _MODEL, _BASE_URL


def _call_vision(image_bytes: bytes, mime_type: str = 'image/jpeg') -> str:
    """Send image to OpenAI-compatible vision endpoint and return text response."""
    import urllib.request

    api_key, model, base_url = _get_config()
    if not api_key:
        raise RuntimeError('未配置 AI_API_KEY，无法使用图片识别功能。请在 backend/.env 中设置。')

    b64 = base64.b64encode(image_bytes).decode()
    data_uri = f'data:{mime_type};base64,{b64}'

    payload = {
        'model': model,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': (
                    '你是旅行行程解析助手。请仔细阅读这张行程表图片，提取所有信息，返回严格JSON格式：\n'
                    '{\n'
                    '  "title": "行程标题",\n'
                    '  "start_date": "YYYY-MM-DD",\n'
                    '  "traveler_count": 数字,\n'
                    '  "days": [\n'
                    '    {\n'
                    '      "date": "YYYY-MM-DD",\n'
                    '      "city": "中文城市名",\n'
                    '      "activities": ["活动1", "活动2"],\n'
                    '      "accommodation": "酒店名或null",\n'
                    '      "transport": ["交通信息"] 或 []\n'
                    '    }\n'
                    '  ]\n'
                    '}\n'
                    '要求：\n'
                    '- 城市名用中文\n'
                    '- 日期格式 YYYY-MM-DD\n'
                    '- 如果图片中没有年份，请根据上下文推断\n'
                    '- activities 包含所有景点和活动\n'
                    '- transport 包含航班号、火车等交通信息\n'
                    '- 只返回JSON，不要其他文字'
                )},
                {'type': 'image_url', 'image_url': {'url': data_uri}},
            ]
        }],
        'max_tokens': 2000,
    }

    url = f'{base_url.rstrip("/")}/chat/completions'
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read())

    return body['choices'][0]['message']['content']


def _infer_year(days_data):
    """If dates lack year, infer from current context."""
    current_year = datetime.now().year
    for d in days_data:
        date_str = d.get('date', '')
        if date_str and not date_str.startswith('20'):
            d['date'] = f'{current_year}-{date_str}'
    return days_data


def _build_trip_result(parsed: dict) -> dict:
    """Convert vision API JSON into parse_text-compatible result format."""
    from services.ai_parser import COUNTRY_MAP, DEST_CITIES

    days_data = parsed.get('days', [])
    _infer_year(days_data)

    title = parsed.get('title', '行程')
    traveler_count = parsed.get('traveler_count', 1)

    start_date = parsed.get('start_date')
    if not start_date and days_data:
        start_date = days_data[0].get('date')

    end_date = None
    if days_data:
        end_date = days_data[-1].get('date')

    from collections import OrderedDict
    city_legs = OrderedDict()

    for i, day in enumerate(days_data):
        city = day.get('city', '未知')
        if city not in city_legs:
            city_legs[city] = {'days': [], 'start': None, 'end': None}

        day_date = day.get('date')
        activities = day.get('activities', [])
        transport = day.get('transport', [])
        accommodation = day.get('accommodation')

        day_entry = {
            'day_number': i + 1,
            'date': day_date,
            'description': ', '.join(activities[:4]) if activities else f'Day {i+1}',
            'highlights': None,
            'activities': activities,
            'transport': transport,
            'accommodation': accommodation,
        }

        city_legs[city]['days'].append(day_entry)
        if day_date:
            try:
                dt = datetime.strptime(day_date, '%Y-%m-%d')
                if not city_legs[city]['start'] or dt < city_legs[city]['start']:
                    city_legs[city]['start'] = dt
                if not city_legs[city]['end'] or dt > city_legs[city]['end']:
                    city_legs[city]['end'] = dt
            except ValueError:
                pass

    legs = []
    for idx, (city, info) in enumerate(city_legs.items()):
        if not info['days']:
            continue
        legs.append({
            'order_index': idx,
            'city': city,
            'country': COUNTRY_MAP.get(city, '[待确认]'),
            'start_date': info['start'].strftime('%Y-%m-%d') if info['start'] else None,
            'end_date': info['end'].strftime('%Y-%m-%d') if info['end'] else None,
            'days': info['days'],
        })

    return {
        'trip': {
            'title': title,
            'start_date': start_date,
            'end_date': end_date,
            'duration': len(days_data),
            'traveler_count': traveler_count,
            'status': 'draft',
        },
        'legs': legs,
        'expenses': [],
    }


def parse_image(image_bytes: bytes, mime_type: str = 'image/jpeg') -> dict:
    """Main entry: image bytes → trip structure dict."""
    raw = _call_vision(image_bytes, mime_type)

    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        raise ValueError('AI 未返回有效JSON，请重试')

    parsed = json.loads(json_match.group())
    return _build_trip_result(parsed)
