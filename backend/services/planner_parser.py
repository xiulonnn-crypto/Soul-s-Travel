r"""PiTravel / 圆周旅迹 风格行程海报解析器。

输入：OCR 后的多行纯文本（来自 image_extractor.extract_text_from_image）。
输出：与 ai_parser.parse_text() 完全相同 shape 的 dict，即
    {type:'trip', trip, legs, expenses}，可直接被 routes/parse.py 返回、
    被前端 TripEditor.applyAction 原样消费。

PiTravel 海报的结构锚点（来自 IMG_4800.JPG 的实测 OCR 输出）：

    英国9日游                      ← 标题行，含 "N日游" / "N天行程"
    SouL的09.29至10.079天8晚行程单   ← caption，含起止 MM.DD（年份缺失）

    09.29/周日                    ← day header：MM.DD/[周]X 或 MM.DD/-
    四号航站楼                    ← day content：景点 / 酒店 / 地点
    伦敦帕丁顿车站
    ...

    09.30/周-                     ← OCR 常把弱字识为乱码，header 的弱字段要宽容
    ...

    10.07/-                       ← OCR 完全丢失 weekday 也要接受

变体覆盖：同一张图里出现 `/周日` / `/周-` / `/周二` / `/月五` / `/-` 五种尾缀。
day-header 正则用 `^MM.DD(?:\s*/.{0,6})?$` 兼容所有实际观测，不依赖 weekday。
"""
from __future__ import annotations

import re
from collections import OrderedDict
from datetime import date, datetime, timedelta
from typing import List, Optional

from services.ai_parser import COUNTRY_MAP, DEST_CITIES, _EN_TO_ZH_CITY


_DAY_HEADER_RE = re.compile(
    r'^(?P<mm>\d{1,2})\.(?P<dd>\d{1,2})(?:\s*[/／]\s*.{0,6})?\s*$'
)

# "N日游" / "N天游" / "N日行程" / "N天行程"
_TITLE_DURATION_RE = re.compile(
    r'(?P<region>[^\s\d]{1,12})?\s*(?P<n>\d{1,3})\s*[天日]\s*(?:游|行程)'
)

# caption "XX的MM.DD至MM.DD" / "MM.DD-MM.DD" / "MM.DD~MM.DD"；OCR 可能把 "10.07" 和
# 紧跟的 "9天8晚" 合并为 "10.079天8晚"，所以 end 捕获后用最后 4 位数字重建 MM.DD。
_CAPTION_RANGE_RE = re.compile(
    r'(\d{1,2})\.(\d{1,2})\s*(?:至|到|—|-|~|–)\s*(\d{1,2})\.(\d{1,2})'
)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def parse_planner_text(ocr_text: str, context_year: Optional[int] = None) -> dict:
    """Parse OCR'd PiTravel-style itinerary into the trip/legs/expenses dict.

    Returns the same shape as `services.ai_parser.parse_text()`. Raises
    ValueError with a user-facing message when the text does not contain any
    recognizable day-header — the upstream route turns that into a 400.

    ``context_year`` (optional): 若图片不含年份（PiTravel 海报 caption 常见情况），
    使用调用方传入的年份——典型来源是"同一页已经存在一份 PDF 解析结果"的年份。
    未传时回落到 ``datetime.now().year``。
    """
    lines = [ln.strip() for ln in (ocr_text or '').splitlines() if ln.strip()]
    if not lines:
        raise ValueError('图片未识别出文本，请确认图片清晰度或上传 PiTravel/圆周旅迹 风格的行程海报。')

    day_blocks = _split_by_day(lines)
    if not day_blocks:
        raise ValueError('未识别到任何日期行（如 09.29/周日），请确认上传的是 PiTravel/圆周旅迹 风格的行程海报。')

    title = _extract_title(lines, day_blocks[0][3])
    start_date, end_date = _extract_dates(lines, day_blocks, context_year=context_year)
    legs = _build_legs(day_blocks, start_date)

    return {
        'type': 'trip',
        'trip': {
            'title': title,
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else None,
            'traveler_count': 1,
            'description': title,
            'status': 'completed',
        },
        'legs': legs,
        'expenses': [],
    }


# ---------------------------------------------------------------------------
# 1. 切天（按 MM.DD[/ 弱尾缀]）
# ---------------------------------------------------------------------------


def _split_by_day(lines: List[str]):
    """返回 [(mm, dd, content_lines, header_line_index), ...]，保持原始顺序。

    content_lines 是 header 到下一 header 之间的原始行（不含 header 本身）。
    """
    headers = []
    for i, line in enumerate(lines):
        m = _DAY_HEADER_RE.match(line)
        if not m:
            continue
        mm, dd = int(m.group('mm')), int(m.group('dd'))
        if 1 <= mm <= 12 and 1 <= dd <= 31:
            headers.append((i, mm, dd))

    blocks = []
    for idx, (line_idx, mm, dd) in enumerate(headers):
        next_idx = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        content = lines[line_idx + 1:next_idx]
        blocks.append((mm, dd, content, line_idx))
    return blocks


# ---------------------------------------------------------------------------
# 2. 标题
# ---------------------------------------------------------------------------


def _extract_title(lines: List[str], first_header_idx: int) -> str:
    """优先从首个 day header 之前的行里找含 'N日游' / 'N天游' / 'N日行程' 的行。
    兜底：取 header 前最长的非空行；再兜底：'行程单'。
    """
    candidates = lines[:first_header_idx]
    for ln in candidates:
        if _TITLE_DURATION_RE.search(ln) and len(ln) <= 40:
            return ln
    # 最长且不像元信息的行（过滤 "PI TRAVEL" / "ITINERARY" / 短码）
    meaningful = [
        ln for ln in candidates
        if len(ln) >= 3 and not re.match(r'^[A-Za-z\s]+$', ln)
    ]
    if meaningful:
        return max(meaningful, key=len)
    return '行程单'


# ---------------------------------------------------------------------------
# 3. 日期
# ---------------------------------------------------------------------------


def _extract_dates(lines: List[str], day_blocks, context_year: Optional[int] = None):
    """返回 (start_date, end_date) 两个 date 对象，或 (None, None)。

    策略：
      a) caption 里抓到 "MM.DD 至 MM.DD" → 用这对
      b) 否则用首/末 day header 的 MM.DD
      c) 年份优先使用 caller 提供的 ``context_year``（典型来自同一编辑页已有
         PDF 解析结果的年份），缺省才回落到 ``datetime.now().year``
      d) 若 end_month < start_month 则 end 年份 +1（跨年）
    """
    full_text = '\n'.join(lines)
    caption_match = _CAPTION_RANGE_RE.search(full_text)
    if caption_match:
        sm, sd, em, ed = (int(x) for x in caption_match.groups())
    else:
        sm, sd = day_blocks[0][0], day_blocks[0][1]
        em, ed = day_blocks[-1][0], day_blocks[-1][1]

    year = context_year if context_year else datetime.now().year
    try:
        start = date(year, sm, sd)
    except ValueError:
        return None, None
    try:
        end_year = year + 1 if em < sm else year
        end = date(end_year, em, ed)
    except ValueError:
        end = None
    return start, end


# ---------------------------------------------------------------------------
# 4. 城市推断 + 组装 legs
# ---------------------------------------------------------------------------


# 所有能识别的"可读出的城市字面量"。既覆盖中文 DEST_CITIES，也覆盖英文地名（OCR
# 常见 Edinburgh / London / Beijing），翻译成中文后用同一套 COUNTRY_MAP。
# 用 "（中文 key, 判定 substring 列表）" 让同一城市的多种写法命中。
def _infer_city(day_lines: List[str], prev_city: Optional[str]) -> str:
    """取最后一个出现的 DEST_CITY（destination > origin 启发式）。

    - 直接扫中文 DEST_CITIES
    - 同时扫 _EN_TO_ZH_CITY 的英文 key，命中则返回对应中文
    """
    last_hit = None
    for line in day_lines:
        for city in DEST_CITIES:
            if city in line:
                last_hit = city
        for en, zh in _EN_TO_ZH_CITY.items():
            # 英文地名要求是独立词，避免 'London Bridge' 误中时顺便也是 London
            if re.search(r'\b' + re.escape(en) + r'\b', line):
                last_hit = zh
    if last_hit:
        return last_hit
    return prev_city or '[待确认]'


def _build_legs(day_blocks, start_date: Optional[date]):
    """把连续同 city 的 day 合并成一条 leg，返回 legs 列表。"""
    if not day_blocks:
        return []

    year = start_date.year if start_date else datetime.now().year
    days_info = []  # [(date, city, activities, transport, accommodation)]
    prev_city: Optional[str] = None
    prev_dt: Optional[date] = None

    for idx, (mm, dd, content, _header_idx) in enumerate(day_blocks):
        # Build raw content (filter pure time lines)
        raw_lines = [ln for ln in content if not re.match(r'^\d{1,2}:\d{2}$', ln)]

        # Transport: lines containing airport keywords but not hotel keywords
        # (hotel names like "Moxy Edinburgh Airport" must not be misclassified)
        transport = _pair_airports([
            ln for ln in raw_lines
            if _AIRPORT_RE.search(ln) and not _ACCOM_HINT_RE.search(ln)
        ])

        # Accommodation: last hotel line from all raw content
        accommodation = _extract_accommodation(raw_lines)

        # Activities: exclude airports, hotels, and PiTravel branding watermarks
        activities = [
            ln for ln in raw_lines
            if not _AIRPORT_RE.search(ln)
            and not _ACCOM_HINT_RE.search(ln)
            and not _PITRAVEL_NOISE_RE.search(ln)
        ]

        city = _infer_city(raw_lines, prev_city)

        # 跨年：如果 month < 上一 day 的 month，视为进入下一年
        try:
            dt = date(year, mm, dd)
        except ValueError:
            dt = None
        if dt and prev_dt and dt < prev_dt:
            try:
                dt = date(year + 1, mm, dd)
                year = year + 1
            except ValueError:
                pass

        days_info.append((dt, city, activities, transport, accommodation))
        prev_city = city
        prev_dt = dt

    # 合并连续同 city
    city_legs: 'OrderedDict[str, dict]' = OrderedDict()
    day_number = 0
    for dt, city, activities, transport, accommodation in days_info:
        day_number += 1
        if city not in city_legs:
            city_legs[city] = {'days': [], 'start': None, 'end': None}
        day_entry = {
            'day_number': day_number,
            'date': dt.strftime('%Y-%m-%d') if dt else None,
            'description': ', '.join(activities[:4]) if activities else f'Day {day_number}',
            'highlights': None,
            'activities': activities,
            'transport': transport,
            'accommodation': accommodation,
        }
        city_legs[city]['days'].append(day_entry)
        if dt:
            bucket = city_legs[city]
            if bucket['start'] is None or dt < bucket['start']:
                bucket['start'] = dt
            if bucket['end'] is None or dt > bucket['end']:
                bucket['end'] = dt

    legs = []
    for order_idx, (city, info) in enumerate(city_legs.items()):
        if not info['days']:
            continue
        legs.append({
            'order_index': order_idx,
            'city': city,
            'country': COUNTRY_MAP.get(city, '[待确认]'),
            'start_date': info['start'].strftime('%Y-%m-%d') if info['start'] else None,
            'end_date': info['end'].strftime('%Y-%m-%d') if info['end'] else None,
            'days': info['days'],
        })
    return legs


# ---------------------------------------------------------------------------
# 5. 附属工具
# ---------------------------------------------------------------------------


_ACCOM_HINT_RE = re.compile(
    r'(?:酒店|宾馆|度假村|客栈|旅馆|民宿|Hotel|Inn|Resort|Airport\s+Hotel|Moxy)',
    re.IGNORECASE,
)

_AIRPORT_RE = re.compile(r'机场|Airport', re.IGNORECASE)

# PiTravel / 圆周旅迹 海报的品牌水印行（OCR 可能把「圆」读作「园」）
_PITRAVEL_NOISE_RE = re.compile(
    r'[圆园]周旅迹|时.{0,3}自由.{0,6}经验',
    re.IGNORECASE,
)


def _pair_airports(airport_lines: List[str]) -> List[str]:
    """将相邻机场行两两合并为「出发机场 出发时间-到达机场 到达时间」航班段。

    PiTravel 海报每个航班段占两行：第一行出发机场+时间，第二行到达机场+时间。
    奇数个机场行时最后一行单独保留。
    """
    paired: List[str] = []
    i = 0
    while i < len(airport_lines):
        if i + 1 < len(airport_lines):
            paired.append(f'{airport_lines[i]}-{airport_lines[i + 1]}')
            i += 2
        else:
            paired.append(airport_lines[i])
            i += 1
    return paired


def _extract_accommodation(activities: List[str]) -> Optional[str]:
    """从 activities 里挑出酒店名（含酒店/宾馆/Hotel 等关键词），取最后一个。

    PiTravel 海报的惯例：一天的最后一行通常是当晚住宿。
    """
    candidates = [ln for ln in activities if _ACCOM_HINT_RE.search(ln)]
    if candidates:
        return candidates[-1]
    return None
