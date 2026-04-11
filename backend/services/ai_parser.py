import re
import unicodedata
from datetime import datetime, timedelta
from collections import OrderedDict


# ── Kangxi Radical → Standard CJK ────────────────────────────────────────────
_RADICAL_MAP = {
    '\u2F00':'\u4E00','\u2F01':'\u4E28','\u2F02':'\u4E36','\u2F03':'\u4E3F',
    '\u2F04':'\u4E59','\u2F05':'\u4E85','\u2F06':'\u4E8C','\u2F07':'\u4EA0',
    '\u2F08':'\u4EBA','\u2F09':'\u513F','\u2F0A':'\u5165','\u2F0B':'\u516B',
    '\u2F0C':'\u5182','\u2F0D':'\u5196','\u2F0E':'\u51AB','\u2F0F':'\u51E0',
    '\u2F10':'\u51F5','\u2F11':'\u5200','\u2F12':'\u529B','\u2F13':'\u52F9',
    '\u2F14':'\u5315','\u2F15':'\u531A','\u2F16':'\u5338','\u2F17':'\u5341',
    '\u2F18':'\u535C','\u2F19':'\u5369','\u2F1A':'\u5382','\u2F1B':'\u53B6',
    '\u2F1C':'\u53C8','\u2F1D':'\u53E3','\u2F1E':'\u56D7','\u2F1F':'\u571F',
    '\u2F20':'\u58EB','\u2F21':'\u5902','\u2F22':'\u590A','\u2F23':'\u5915',
    '\u2F24':'\u5927','\u2F25':'\u5973','\u2F26':'\u5B50','\u2F27':'\u5B80',
    '\u2F28':'\u5BF8','\u2F29':'\u5C0F','\u2F2A':'\u5C22','\u2F2B':'\u5C38',
    '\u2F2C':'\u5C6E','\u2F2D':'\u5C71','\u2F2E':'\u5DDB','\u2F2F':'\u5DE5',
    '\u2F30':'\u5DF1','\u2F31':'\u5DFE','\u2F32':'\u5E72','\u2F33':'\u5E7A',
    '\u2F34':'\u5E7F','\u2F35':'\u5EF4','\u2F36':'\u5EFE','\u2F37':'\u5F0B',
    '\u2F38':'\u5F13','\u2F39':'\u5F50','\u2F3A':'\u5F61','\u2F3B':'\u5F73',
    '\u2F3C':'\u5FC3','\u2F3D':'\u6208','\u2F3E':'\u6236','\u2F3F':'\u624B',
    '\u2F40':'\u652F','\u2F41':'\u6534','\u2F42':'\u6587','\u2F43':'\u6597',
    '\u2F44':'\u65A4','\u2F45':'\u65B9','\u2F46':'\u65E0','\u2F47':'\u65E5',
    '\u2F48':'\u66F0','\u2F49':'\u6708','\u2F4A':'\u6728','\u2F4B':'\u6B20',
    '\u2F4C':'\u6B62','\u2F4D':'\u6B79','\u2F4E':'\u6BB3','\u2F4F':'\u6BCB',
    '\u2F50':'\u6BD4','\u2F51':'\u6BDB','\u2F52':'\u6C0F','\u2F53':'\u6C14',
    '\u2F54':'\u6C34','\u2F55':'\u706B','\u2F56':'\u722A','\u2F57':'\u7236',
    '\u2F58':'\u723B','\u2F59':'\u723F','\u2F5A':'\u7247','\u2F5B':'\u7259',
    '\u2F5C':'\u725B','\u2F5D':'\u72AC','\u2F5E':'\u7384','\u2F5F':'\u7389',
    '\u2F60':'\u74DC','\u2F61':'\u74E6','\u2F62':'\u7518','\u2F63':'\u751F',
    '\u2F64':'\u7528','\u2F65':'\u7530','\u2F66':'\u758B','\u2F67':'\u7592',
    '\u2F68':'\u7676','\u2F69':'\u767D','\u2F6A':'\u76AE','\u2F6B':'\u76BF',
    '\u2F6C':'\u76EE','\u2F6D':'\u77DB','\u2F6E':'\u77E2','\u2F6F':'\u77F3',
    '\u2F70':'\u793A','\u2F71':'\u79B8','\u2F72':'\u79BE','\u2F73':'\u7A74',
    '\u2F74':'\u7ACB','\u2F75':'\u7AF9','\u2F76':'\u7C73','\u2F77':'\u7CF8',
    '\u2F78':'\u7F36','\u2F79':'\u7F51','\u2F7A':'\u7F8A','\u2F7B':'\u7FBD',
    '\u2F7C':'\u8001','\u2F7D':'\u800C','\u2F7E':'\u8012','\u2F7F':'\u8033',
    '\u2F80':'\u807F','\u2F81':'\u8089','\u2F82':'\u81E3','\u2F83':'\u81EA',
    '\u2F84':'\u81F3','\u2F85':'\u81FC','\u2F86':'\u820C','\u2F87':'\u821B',
    '\u2F88':'\u821F','\u2F89':'\u826E','\u2F8A':'\u8272','\u2F8B':'\u8278',
    '\u2F8C':'\u864D','\u2F8D':'\u866B','\u2F8E':'\u8840','\u2F8F':'\u884C',
    '\u2F90':'\u8863','\u2F91':'\u897E','\u2F92':'\u898B','\u2F93':'\u89D2',
    '\u2F94':'\u8A00','\u2F95':'\u8C37','\u2F96':'\u8C46','\u2F97':'\u8C55',
    '\u2F98':'\u8C78','\u2F99':'\u8C9D','\u2F9A':'\u8D64','\u2F9B':'\u8D70',
    '\u2F9C':'\u8DB3','\u2F9D':'\u8EAB','\u2F9E':'\u8ECA','\u2F9F':'\u8F9B',
    '\u2FA0':'\u8FB0','\u2FA1':'\u8FB5','\u2FA2':'\u9091','\u2FA3':'\u9149',
    '\u2FA4':'\u91C6','\u2FA5':'\u91CC','\u2FA6':'\u91D1','\u2FA7':'\u9577',
    '\u2FA8':'\u9580','\u2FA9':'\u961C','\u2FAA':'\u96B6','\u2FAB':'\u96B9',
    '\u2FAC':'\u96E8','\u2FAD':'\u9751','\u2FAE':'\u975E','\u2FAF':'\u9762',
    '\u2FB0':'\u9769','\u2FB1':'\u97CB','\u2FB2':'\u97ED','\u2FB3':'\u97F3',
    '\u2FB4':'\u9801','\u2FB5':'\u98A8','\u2FB6':'\u98DB','\u2FB7':'\u98DF',
    '\u2FB8':'\u9996','\u2FB9':'\u9999','\u2FBA':'\u99AC','\u2FBB':'\u9AA8',
    '\u2FBC':'\u9AD8','\u2FBD':'\u9ADF','\u2FBE':'\u9B25','\u2FBF':'\u9B2F',
    '\u2FC0':'\u9B32','\u2FC1':'\u9B3C','\u2FC2':'\u9B5A','\u2FC3':'\u9CE5',
    '\u2FC4':'\u9E75','\u2FC5':'\u9E7F','\u2FC6':'\u9EA5','\u2FC7':'\u9EBB',
    '\u2FC8':'\u9EC3','\u2FC9':'\u9ECD','\u2FCA':'\u9ED1','\u2FCB':'\u9EF9',
    '\u2FCC':'\u9EFD','\u2FCD':'\u9F0E','\u2FCE':'\u9F13','\u2FCF':'\u9F20',
    '\u2FD0':'\u9F3B','\u2FD1':'\u9F4A','\u2FD2':'\u9F52','\u2FD3':'\u9F8D',
    '\u2FD4':'\u9F9C','\u2FD5':'\u9FA0',
}

# English city name → Chinese
_EN_TO_ZH_CITY = {
    'Mandalay': '曼德勒', 'Bagan': '蒲甘', 'Inle': '茵莱湖',
    'Yangon': '仰光', 'Nyaung': '良乌', 'Bangkok': '曼谷',
    'Tokyo': '东京', 'Kyoto': '京都', 'Osaka': '大阪',
    'Seoul': '首尔', 'Hanoi': '河内', 'Singapore': '新加坡',
    'Paris': '巴黎', 'London': '伦敦', 'Sydney': '悉尼',
    'Siem': '暹粒',
}

# Cities that are DESTINATIONS (not departure/transit origins to be filtered)
DEST_CITIES = [
    '曼德勒', '蒲甘', '茵莱湖', '仰光', '良乌', '娘水',
    '曼谷', '清迈', '普吉岛',
    '东京', '京都', '大阪', '奈良',
    '首尔', '釜山', '河内', '暹粒', '新加坡',
    '巴黎', '伦敦', '纽约',
    '香港', '澳门', '台北',
]

COUNTRY_MAP = {
    '曼德勒': '缅甸', '蒲甘': '缅甸', '茵莱湖': '缅甸', '仰光': '缅甸',
    '良乌': '缅甸', '娘水': '缅甸',
    '曼谷': '泰国', '清迈': '泰国',
    '东京': '日本', '京都': '日本', '大阪': '日本',
    '首尔': '韩国', '釜山': '韩国',
    '河内': '越南', '暹粒': '柬埔寨', '新加坡': '新加坡',
    '巴黎': '法国', '伦敦': '英国', '纽约': '美国',
    '香港': '中国', '澳门': '中国', '台北': '中国',
}


def _normalize(text):
    """Normalize CJK radicals + null-byte arrows + NFKC + de-duplicate adjacent identical CJK chars."""
    # Replace null bytes used as arrow separators in PDF (e.g. 广州\x00曼谷)
    text = text.replace('\x00', '→')
    chars = [_RADICAL_MAP.get(ch, ch) for ch in text]
    text = unicodedata.normalize('NFKC', ''.join(chars))
    # Handle CJK Radical Supplements (U+2E80–U+2EFF) not normalized by NFKC.
    # Mapped from actual codepoints found in this PDF by scanning.
    _RS_MAP = {
        '\u2ea0': '\u6c11',  # ⺠ CIVILIAN → 民
        '\u2ec4': '\u897f',  # ⻄ WEST → 西
        '\u2ec5': '\u89c1',  # ⻅ SEE → 见
        '\u2ecb': '\u8f66',  # ⻋ CART → 车
        '\u2ed3': '\u957f',  # ⻓ LONG → 长
        '\u2ed4': '\u95e8',  # ⻔ GATE → 门
        '\u2edb': '\u98ce',  # ⻛ WIND → 风
        '\u2edc': '\u98de',  # ⻜ FLY → 飞
        '\u2ee2': '\u9a6c',  # ⻢ HORSE → 马  ← key: 马哈根达杨僧院
        '\u2ee5': '\u9c7c',  # ⻥ FISH → 鱼
        '\u2ee9': '\u9ec4',  # ⻩ YELLOW → 黄
    }
    text = ''.join(_RS_MAP.get(ch, ch) for ch in text)
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if '\u4e00' <= ch <= '\u9fff' and i + 1 < len(text) and text[i + 1] == ch:
            result.append(ch)
            i += 2
        else:
            result.append(ch)
            i += 1
    return ''.join(result)


def _extract_trip_header(text):
    """Extract title, start_date, duration, traveler_count."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    title = None
    for ln in lines[:6]:
        if len(ln) > 3 and not re.match(r'^(作者|日期|城市|交通|景点|住宿)', ln):
            title = ln
            break

    start_date = None
    m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]', text)
    if m:
        try:
            start_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    duration = None
    m = re.search(r'共\s*(\d+)\s*天', text)
    if m:
        duration = int(m.group(1))

    traveler_count = 1
    # check expense table qty column (most reliable indicator of party size)
    qtys = re.findall(r'CNY\s*[\d,.]+\s+(\d)\s+CNY', text)
    if qtys:
        common = max(set(qtys), key=qtys.count)
        n = int(common)
        if 1 < n <= 10:
            traveler_count = n
    if traveler_count == 1:
        m = re.search(r'(\d+)\s*个?\s*人', text[:500])
        if m:
            n = int(m.group(1))
            if 1 < n <= 10:
                traveler_count = n

    return title, start_date, duration, traveler_count


def _split_by_day(text):
    """Split text at \nNN\nweekday markers.

    PDF table layout: each day row 1 (attraction #1) appears BEFORE the
    \nNN\n marker; rows 2+ appear after it.
    We grab only the pre-marker row-1 line AND trim the next day's row-1
    line from the end of each body to prevent cross-contamination.
    """
    for pat in [r'\n第1天[天]?[（(]总价', r'\n预\s*算\s*明\s*细', r'\n费\s*用\s*汇\s*总']:
        m = re.search(pat, text)
        if m:
            text = text[:m.start()]
            break

    day_re = re.compile(r'\n(\d{2})\n\s*星期[一二三四五六日天]')
    matches = list(day_re.finditer(text))
    if not matches:
        return []

    # Pre-marker line pattern: CJK_city + numbered attraction
    premarker_re = re.compile(r'[\u4e00-\u9fff\w]+\s+1\.\s+[\u4e00-\u9fff]')

    days = []
    for i, m in enumerate(matches):
        day_num = int(m.group(1))
        marker_start = m.start()
        chunk_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        # Grab only the specific line before this marker that has "N. CJK" (row 1)
        preceding = text[:marker_start]
        pre_lines = [ln for ln in preceding.split('\n') if ln.strip()]
        pre_attraction_line = ''
        for ln in reversed(pre_lines[-4:]):
            if re.search(r'\d+\.\s+[\u4e00-\u9fff]', ln):
                pre_attraction_line = ln
                break

        # Build body and trim its ending "CITY 1. CJK" line (= next day's row 1)
        body = text[marker_start:chunk_end]
        body_lines = body.split('\n')
        trim_idx = None
        for j in range(len(body_lines) - 1, -1, -1):
            if premarker_re.search(body_lines[j].strip()):
                trim_idx = j
                break
        if trim_idx is not None:
            body = '\n'.join(body_lines[:trim_idx])

        chunk = (pre_attraction_line + '\n' + body) if pre_attraction_line else body
        days.append((day_num, chunk))

    return days


def _extract_city_from_chunk(chunk):
    """Determine destination city from a day chunk.

    Priority:
    1. English city name after 星期X  (most reliable in this PDF)
    2. Year-month + CJK city pattern
    3. First known destination city in chunk
    """
    # 1. English city after weekday
    m = re.search(r'星期[一二三四五六日天]\s+([A-Za-z]+)', chunk)
    if m:
        en = m.group(1)
        for key, zh in _EN_TO_ZH_CITY.items():
            if en.lower().startswith(key.lower()):
                return zh

    # 2. year-month + city column pattern: "2019年10月 曼德勒"
    m = re.search(r'20\d{2}年\d{1,2}月\s+([\u4e00-\u9fff]{2,4})', chunk)
    if m:
        city = m.group(1)
        if city in DEST_CITIES:
            return city

    # 3. First known destination city (exclude transit origins)
    for city in DEST_CITIES:
        if city in chunk:
            return city

    return None


def _extract_activities(chunk):
    """Extract numbered Chinese attraction names: N. 景点名，..."""
    activities = []
    # Match: digit dot space CJK-name up to ，or , or end-of-line
    for m in re.finditer(r'\d+\.\s+([\u4e00-\u9fff（）·\-]+(?:\([\u4e00-\u9fff a-zA-Z]+\))?)', chunk):
        name = m.group(1).strip().rstrip('，,、 ')
        if len(name) >= 2 and name not in activities:
            activities.append(name)
    return activities[:12]


def _extract_flight_schedule(text):
    """Extract (code, src_city, dst_city) from the flight schedule section.

    PDF text format: → src//dst\n时间 班次 ...\nHH:MM CODE ...
    """
    results = []
    pattern = re.compile(
        r'→\s*([\u4e00-\u9fff]{2,4})//([\u4e00-\u9fff]{2,4})'  # → src//dst
        r'[\|\n][^\|\n]*班次[^\|\n]*'                            # |时间 班次 出发 到达 到达时间|
        r'[\|\n]\s*\d{1,2}:\d{2}\s+([A-Z]{1,2}\d{3,4})',       # |HH:MM CODE
    )
    for m in pattern.finditer(text):
        results.append({'code': m.group(3), 'src': m.group(1), 'dst': m.group(2)})
    return results


def _extract_transport(chunk):
    """Extract city→city routes from day chunk. Flight codes paired globally."""
    # Cut off page-marker tail (flight schedule / overview pages end up here for the last day)
    page_cut = re.search(r'\|\s*P\d+\s*\|', chunk)
    if page_cut:
        chunk = chunk[:page_cut.start()]

    routes = []
    for m in re.finditer(
        r'([\u4e00-\u9fff]{1,4}|[A-Za-z]{2,10})\s*→\s*([\u4e00-\u9fff]{1,4}|[A-Za-z]{2,10})',
        chunk,
    ):
        src, dst = m.group(1).strip(), m.group(2).strip()
        if re.search(r'\d', src + dst):
            continue
        if re.search(r'酒店|宾馆|度假|旅馆|客栈', src + dst):
            continue
        route = f'{src}→{dst}'
        if route not in routes and len(src) >= 2 and len(dst) >= 2:
            routes.append(route)
    return routes[:8]


def _extract_accommodation(chunk):
    """Extract first clean hotel name from chunk, preferring Chinese names."""
    # Prefer Chinese hotel names
    for m in re.finditer(
        r'([\u4e00-\u9fff]{2,12}(?:酒店|宾馆|度假村|客栈|旅馆|民宿))',
        chunk,
    ):
        name = m.group(1).strip()
        if len(name) <= 20:
            return name
    # Fallback to English hotel names
    for m in re.finditer(
        r'([A-Za-z\s]{4,30}(?:Hotel|Resort|Inn|Hostel|Lodge))',
        chunk, re.IGNORECASE,
    ):
        name = m.group(1).strip()
        if len(name) <= 30:
            return name
    return None


def _parse_expenses(text):
    """Parse expense table rows: 'description CNY unit qty CNY total'."""
    expenses = []
    CATEGORY_RULES = [
        (r'交通|机票|航班|火车|高铁|大巴|船|包车|飞机', '交通'),
        (r'酒店|宾馆|民宿|住宿|Hotel|hostel|客栈|旅馆|度假村', '住宿'),
        (r'午餐|晚餐|早餐|餐饮|餐厅|饭', '餐饮'),
        (r'门票|景点|入场', '门票'),
        (r'购物|纪念品', '购物'),
    ]
    seen = set()
    for m in re.finditer(
        r'(.{2,30}?)\s+CNY\s*([\d,.]+)\s+(\d+)\s+CNY\s*([\d,.]+)',
        text,
    ):
        desc = m.group(1).strip()
        if desc in seen:
            continue
        seen.add(desc)
        try:
            qty = int(m.group(3))
            total = float(m.group(4).replace(',', ''))
        except ValueError:
            continue
        category = '其他'
        for pat, cat in CATEGORY_RULES:
            if re.search(pat, desc, re.IGNORECASE):
                category = cat
                break
        suffix = f' x{qty}' if qty > 1 else ''
        expenses.append({
            'date': None,
            'category': category,
            'amount': total,
            'currency': 'CNY',
            'description': f'{desc}{suffix}',
        })
    return expenses


_CURRENCY_CODE = {
    '缅甸币': 'MMK', '缅币': 'MMK', 'MMK': 'MMK',
    '泰铢': 'THB', '泰币': 'THB', 'THB': 'THB',
    '日元': 'JPY', 'JPY': 'JPY',
    '美元': 'USD', 'USD': 'USD',
    '港元': 'HKD', '港币': 'HKD', 'HKD': 'HKD',
    '欧元': 'EUR', 'EUR': 'EUR',
    '韩元': 'KRW', 'KRW': 'KRW',
    '人民币': 'CNY', 'CNY': 'CNY',
}

# How many CNY per 1 unit of foreign currency (approximate static rates)
_CNY_PER_UNIT = {
    'MMK': 1 / 365,
    'THB': 0.20,
    'JPY': 0.050,
    'USD': 7.30,
    'HKD': 0.93,
    'EUR': 7.70,
    'KRW': 0.0053,
    'CNY': 1.0,
}


def _is_expense_command(text: str) -> bool:
    return bool(re.search(r'(增加|添加|补录).{0,30}(花费|费用|消费|支出)', text))


def _parse_expense_command(text: str):
    # --- amount & currency ---
    original_amount = None
    currency_name = None

    m = re.search(r'(\d+(?:\.\d+)?)\s*万\s*([^\s，。,（(]{2,5})', text)
    if m:
        original_amount = float(m.group(1)) * 10000
        currency_name = m.group(2)
    else:
        m = re.search(r'(\d+(?:\.\d+)?)\s*([^\s，。,（(0-9]{2,5})', text)
        if m:
            original_amount = float(m.group(1))
            currency_name = m.group(2)

    if original_amount is None:
        return None

    currency_code = 'CNY'
    for key, code in _CURRENCY_CODE.items():
        if currency_name and key in currency_name:
            currency_code = code
            break

    rate = _CNY_PER_UNIT.get(currency_code, 1.0)
    amount_cny = round(original_amount * rate, 2)

    # --- date ---
    date_str = None
    m_date = re.search(r'(\d{1,2})[./](\d{1,2})', text)
    if m_date:
        from datetime import date as _date
        month, day = int(m_date.group(1)), int(m_date.group(2))
        today = _date.today()
        year = today.year
        if month > today.month + 1:
            year -= 1
        try:
            date_str = f'{year}-{month:02d}-{day:02d}'
        except ValueError:
            pass

    # --- description ---
    desc_m = re.search(r'[\u4e00-\u9fff]{2,8}花费', text)
    if desc_m:
        desc = desc_m.group(0)
    else:
        desc_m = re.search(r'(增加|添加|补录)\S*?\s*([\u4e00-\u9fff]{2,10})', text)
        desc = desc_m.group(2) if desc_m else '花费'

    if currency_code != 'CNY' and currency_name:
        orig_str = f'{int(original_amount // 10000)}万' if original_amount >= 10000 else str(int(original_amount))
        desc = f'{desc} ({orig_str}{currency_name})'

    # --- category ---
    category = '其他'
    if re.search(r'包车|交通|机票|火车|船|大巴|出租', text):
        category = '交通'
    elif re.search(r'酒店|住宿|宾馆|民宿|客栈', text):
        category = '住宿'
    elif re.search(r'餐|饭|饮食|吃', text):
        category = '餐饮'
    elif re.search(r'门票|景点|入场', text):
        category = '门票'
    elif re.search(r'购物|纪念品', text):
        category = '购物'

    return {'date': date_str, 'category': category, 'amount': amount_cny, 'currency': 'CNY', 'description': desc}


def parse_text(text: str) -> dict:
    text = _normalize(text)

    if _is_expense_command(text):
        expense = _parse_expense_command(text)
        return {
            'type': 'expense',
            'trip': None,
            'legs': [],
            'expenses': [expense] if expense else [],
        }

    title, start_date, duration, traveler_count = _extract_trip_header(text)
    if not title:
        title = '旅行行程'

    end_date = None
    if start_date and duration:
        end_date = start_date + timedelta(days=duration - 1)

    expenses = _parse_expenses(text)
    day_chunks = _split_by_day(text)

    # Extract flight schedule from full text once; build route→code lookup
    flight_schedule = _extract_flight_schedule(text)
    route_to_code = {f'{f["src"]}→{f["dst"]}': f['code'] for f in flight_schedule}

    city_legs: 'OrderedDict[str, dict]' = OrderedDict()

    if day_chunks:
        for day_num, chunk in day_chunks:
            city = _extract_city_from_chunk(chunk)
            if not city:
                city = '[待确认]'

            if city not in city_legs:
                city_legs[city] = {'days': [], 'start': None, 'end': None}

            day_date = (start_date + timedelta(days=day_num - 1)) if start_date else None

            activities = _extract_activities(chunk)
            raw_routes = _extract_transport(chunk)
            # Pair each route with its flight code (if found in schedule)
            transport = []
            for route in raw_routes:
                code = route_to_code.get(route)
                transport.append(f'{code}:{route}' if code else route)
            accommodation = _extract_accommodation(chunk)

            day_entry = {
                'day_number': day_num,
                'date': day_date.strftime('%Y-%m-%d') if day_date else None,
                'description': ', '.join(activities[:4]) if activities else f'Day {day_num}',
                'highlights': None,
                'activities': activities,
                'transport': transport,
                'accommodation': accommodation,
            }

            city_legs[city]['days'].append(day_entry)
            if day_date:
                if not city_legs[city]['start'] or day_date < city_legs[city]['start']:
                    city_legs[city]['start'] = day_date
                if not city_legs[city]['end'] or day_date > city_legs[city]['end']:
                    city_legs[city]['end'] = day_date

    legs = []
    for i, (city, info) in enumerate(city_legs.items()):
        if not info['days']:
            continue
        legs.append({
            'order_index': i,
            'city': city,
            'country': COUNTRY_MAP.get(city, '[待确认]'),
            'start_date': info['start'].strftime('%Y-%m-%d') if info['start'] else None,
            'end_date': info['end'].strftime('%Y-%m-%d') if info['end'] else None,
            'days': info['days'],
        })

    # Assign expense dates by matching to days: hotels → checkin day, transport → matching route day
    all_days = [day for info in city_legs.values() for day in info['days']]
    for exp in expenses:
        if exp['date']:
            continue
        desc = exp['description'] or ''
        matched_date = None
        if exp['category'] == '住宿':
            # Match hotel name against accommodation field of each day
            for day in all_days:
                hotel = day.get('accommodation') or ''
                if hotel and any(tok in desc or tok in hotel for tok in [hotel[:4], desc[:4]] if len(tok) >= 2):
                    matched_date = day['date']
                    break
        elif exp['category'] == '交通':
            # Match route keywords against transport list of each day
            for day in all_days:
                for t in day.get('transport', []):
                    # t looks like "CODE:A→B" or "A→B"; check if city names appear in desc
                    cities = re.findall(r'[\u4e00-\u9fff]{2,4}', t)
                    if cities and any(c in desc for c in cities):
                        matched_date = day['date']
                        break
                if matched_date:
                    break
        if not matched_date and start_date:
            matched_date = start_date.strftime('%Y-%m-%d')
        exp['date'] = matched_date

    return {
        'type': 'trip',
        'trip': {
            'title': title,
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else None,
            'traveler_count': traveler_count,
            'description': title,
            'status': 'completed',
        },
        'legs': legs,
        'expenses': expenses,
    }
