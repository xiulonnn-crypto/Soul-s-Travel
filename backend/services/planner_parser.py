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

    # OCR 质量检查：若大比例文字是拉丁乱码（非中文/数字/斜杠）则拒绝解析，
    # 避免手机 App 截图被当作海报处理后产生垃圾数据。
    # 策略：统计所有行中 CJK 字符比例，低于阈值说明 OCR 无法有效识别此图。
    _all_chars = ''.join(lines)
    if len(_all_chars) >= 20:
        _cjk_count = sum(1 for c in _all_chars if '\u4e00' <= c <= '\u9fff')
        _cjk_ratio = _cjk_count / len(_all_chars)
        # PiTravel 海报以中文为主，合理比例 ≥ 30%；截图乱码通常 < 10%
        if _cjk_ratio < 0.10:
            raise ValueError(
                '图片内容无法识别（识别到的中文字符过少），请上传清晰的 PiTravel/圆周旅迹 行程海报图片。'
            )

    day_blocks = _split_by_day(lines)
    if not day_blocks:
        raise ValueError('未识别到任何日期行（如 09.29/周日），请确认上传的是 PiTravel/圆周旅迹 风格的行程海报。')

    title = _extract_title(lines, day_blocks[0][3])
    start_date, end_date = _extract_dates(lines, day_blocks, context_year=context_year)
    legs = _build_legs(day_blocks, start_date)

    # 活动乱码过滤：OCR 质量差时（非中文截图、低分辨率）会产生大量拉丁乱码，
    # 将中文比例低于 30% 且长度超过 4 字符的活动视为乱码删除，防止污染行程数据。
    # 保留：纯中文活动（CJK 比例高），以及短词（≤4字符，可能是合法缩写）。
    def _is_garbled_activity(name: str) -> bool:
        if len(name) <= 4:
            return False  # 短词不判断（可能是合法缩写）
        cjk = sum(1 for c in name if '\u4e00' <= c <= '\u9fff')
        return cjk / len(name) < 0.30

    for leg in legs:
        for day in leg.get('days', []):
            raw = day.get('activities', [])
            day['activities'] = [a for a in raw if not _is_garbled_activity(a)]

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


# 机场名 → 城市映射。OCR 出来的 PiTravel 行程图上，常见 day 内只列机场+酒店，
# 没有独立城市字面量（如 5/01 = 北京大兴+哈马德+乔莫·肯雅塔+酒店）。这张表把
# "<城市><限定词>国际机场" 归到对应城市，使 _infer_city 在没有 DEST_CITY /
# 英文地名命中时仍能给出正确 city。机场名故意写得宽（含"国际机场"全字 +
# 简写），让 substring 命中尽量稳定。新增机场只需追加这张表。
_AIRPORT_TO_CITY: dict = {
    # 中国
    '北京大兴国际机场': '北京', '大兴国际机场': '北京', '大兴机场': '北京',
    '北京首都国际机场': '北京', '首都国际机场': '北京',
    '上海浦东国际机场': '上海', '浦东国际机场': '上海',
    '上海虹桥国际机场': '上海', '虹桥国际机场': '上海',
    '广州白云国际机场': '广州', '白云国际机场': '广州',
    '深圳宝安国际机场': '深圳', '宝安国际机场': '深圳',
    '成都天府国际机场': '成都', '成都天府机场': '成都', '天府国际机场': '成都',
    '成都双流国际机场': '成都', '双流国际机场': '成都',
    '香港国际机场': '香港',
    # 卡塔尔
    '哈马德国际机场': '多哈',
    # 肯尼亚
    '乔莫·肯雅塔国际机场': '内罗毕', '乔莫肯雅塔国际机场': '内罗毕',
    '威尔逊机场': '内罗毕',
    # 马来西亚
    '吉隆坡国际机场': '吉隆坡',
    # 越南
    '西贡新山一国际机场': '胡志明市', '新山一国际机场': '胡志明市',
    # 日本
    '成田国际机场': '东京', '羽田国际机场': '东京', '羽田机场': '东京',
    '关西国际机场': '大阪',
    # 韩国
    '仁川国际机场': '首尔', '金浦国际机场': '首尔',
    # 泰国
    '素万那普国际机场': '曼谷', '廊曼国际机场': '曼谷',
    # 新加坡
    '樟宜国际机场': '新加坡', '樟宜机场': '新加坡',
    # 英国
    '希思罗国际机场': '伦敦', '希思罗机场': '伦敦', '盖特威克机场': '伦敦',
    '爱丁堡机场': '爱丁堡',
}


# 所有能识别的"可读出的城市字面量"。既覆盖中文 DEST_CITIES，也覆盖英文地名（OCR
# 常见 Edinburgh / London / Beijing），翻译成中文后用同一套 COUNTRY_MAP。
# 用 "（中文 key, 判定 substring 列表）" 让同一城市的多种写法命中。
def _infer_city(day_lines: List[str], prev_city: Optional[str]) -> str:
    """取 day 内最后一个出现位置的 city（destination > origin 启发式）。

    优先级（同 line 内取 char 位置最靠后的命中）：
    - 中文 DEST_CITIES 直接 substring
    - _EN_TO_ZH_CITY 的英文地名（要求独立词，避免 'London Bridge'）
    - _AIRPORT_TO_CITY 机场名（PiTravel 海报常见每天只列机场+酒店，没有独立
      城市字面量；机场命中作为兜底）

    "char 位置最靠后" 是关键：OCR 行内 "哈马德国际机场 北京大兴国际机场" 这种
    "中转地 落地地" 排版下，落地地在右侧、char 位置更靠后 → last_hit = 落地。
    若按 dict 遍历顺序取，会被 dict 字面量的定义顺序污染。
    """
    last_hit = None
    for line in day_lines:
        line_hits = []  # (char_pos, city_zh)
        for city in DEST_CITIES:
            pos = line.rfind(city)
            if pos >= 0:
                line_hits.append((pos, city))
        for en, zh in _EN_TO_ZH_CITY.items():
            for m in re.finditer(r'\b' + re.escape(en) + r'\b', line):
                line_hits.append((m.start(), zh))
        for airport, city in _AIRPORT_TO_CITY.items():
            pos = line.rfind(airport)
            if pos >= 0:
                line_hits.append((pos, city))
        if line_hits:
            line_hits.sort(key=lambda x: x[0])
            last_hit = line_hits[-1][1]
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

        # Activities: exclude airports, hotels, and PiTravel branding watermarks.
        # Exception: a non-last hotel-like line that carries a parenthetical
        # secondary name — e.g. "蓝天酒店（蓝天塔）" — signals a visited landmark
        # that happens to share its name with a hotel.  Pure hotel names without
        # a parenthetical remain excluded from activities.
        activities = [
            ln for ln in raw_lines
            if not _AIRPORT_RE.search(ln)
            and not _PITRAVEL_NOISE_RE.search(ln)
            and (
                not _ACCOM_HINT_RE.search(ln)
                or (ln != accommodation and _LANDMARK_PAREN_RE.search(ln))
            )
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

# 括号副名：形如「蓝天酒店（蓝天塔）」表示地标性兼用场所，应保留为 activity
_LANDMARK_PAREN_RE = re.compile(r'[（(].{1,20}[）)]')


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
