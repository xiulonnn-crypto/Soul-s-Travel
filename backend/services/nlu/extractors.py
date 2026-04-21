"""Per-intent slot extractors.

Each function receives the normalized user text and returns a structured dict
ready for the frontend. Intent classification is already done — these only
need to pull out the relevant entities.
"""
import re
from datetime import date as _date


# ── Shared constants ─────────────────────────────────────────────────────────

_ACCOM_TYPES = r'酒店|宾馆|民宿|客栈|旅馆|度假村'
_ACCOM_CATEGORY = r'住宿|' + _ACCOM_TYPES

_CATEGORY_KEYWORDS = [
    (r'交通|机票|航班|火车|高铁|大巴|船|包车|飞机|出租|新干线', '交通'),
    (r'酒店|宾馆|民宿|住宿|客栈|旅馆|度假村', '住宿'),
    (r'午餐|晚餐|早餐|餐饮|餐厅|饭', '餐饮'),
    (r'门票|景点|入场', '门票'),
    (r'购物|纪念品', '购物'),
]

_CURRENCY_CODE = {
    '缅甸币': 'MMK', '缅币': 'MMK', 'MMK': 'MMK',
    '泰铢': 'THB', '泰币': 'THB', 'THB': 'THB',
    '日元': 'JPY', 'JPY': 'JPY',
    '美元': 'USD', 'USD': 'USD',
    '港元': 'HKD', '港币': 'HKD', 'HKD': 'HKD',
    '欧元': 'EUR', 'EUR': 'EUR',
    '韩元': 'KRW', 'KRW': 'KRW',
    '人民币': 'CNY', 'CNY': 'CNY', 'RMB': 'CNY',
    '块': 'CNY', '元': 'CNY',
}

_CNY_PER_UNIT = {
    'MMK': 1 / 365, 'THB': 0.20, 'JPY': 0.050, 'USD': 7.30,
    'HKD': 0.93, 'EUR': 7.70, 'KRW': 0.0053, 'CNY': 1.0,
}


# ── change_category ──────────────────────────────────────────────────────────

def extract_change_category(text: str) -> dict:
    """Extract item_name and target category from text."""
    name = None

    # "将/把 X (的类别) 改为/设为/变为 Y"
    m = re.search(
        r'(?:将|把)([^\s的]{2,8})(?:的\S+?)?(?:改为|设为|变为|归[到类])',
        text,
    )
    if m:
        name = m.group(1)

    # "X 是/属于/应该是 酒店/住宿/宾馆..."
    if not name:
        m = re.search(
            r'([\u4e00-\u9fff]{2,10}?)(?:应该(?:是|归[到类])|是|属于)\s*(?:' + _ACCOM_CATEGORY + r'|交通|餐饮|门票|购物)',
            text,
        )
        if m:
            name = m.group(1)

    target = '住宿'
    for pat, cat in _CATEGORY_KEYWORDS:
        if re.search(pat, text):
            target = cat
            break

    return {
        'type': 'change_category',
        'item_name': name,
        'target_category': target,
        'trip': None,
        'legs': [],
        'expenses': [],
    }


# ── add_expense ──────────────────────────────────────────────────────────────

_BATCH_CAT_RE = re.compile(
    r'(酒店|宾馆|住宿|餐饮|午餐|晚餐|早餐|餐厅|景点|门票|交通|机票|购物|签证|保险|其他)\s*(\d+(?:\.\d+)?)'
)

_BATCH_CAT_MAP = {
    '酒店': '住宿', '宾馆': '住宿', '住宿': '住宿',
    '餐饮': '餐饮', '午餐': '餐饮', '晚餐': '餐饮', '早餐': '餐饮', '餐厅': '餐饮',
    '景点': '门票', '门票': '门票',
    '交通': '交通', '机票': '交通',
    '购物': '购物', '签证': '其他', '保险': '其他', '其他': '其他',
}


def extract_add_expense(text: str) -> dict:
    """Extract amount, currency, category, description, date from text.
    Supports batch format like '酒店6206餐饮6637景点2823'.
    """
    batch = _BATCH_CAT_RE.findall(text)
    if len(batch) >= 2:
        expenses = []
        for cat_word, amt_str in batch:
            expenses.append({
                'date': None,
                'category': _BATCH_CAT_MAP.get(cat_word, '其他'),
                'amount': float(amt_str),
                'currency': 'CNY',
                'description': cat_word,
            })
        return {'type': 'expense', 'trip': None, 'legs': [], 'expenses': expenses}

    original_amount = None
    currency_name = None

    wan_matches = list(re.finditer(r'(\d+(?:\.\d+)?)\s*万\s*([^\s，。,（(]{1,5})', text))
    plain_matches = list(re.finditer(r'(\d+(?:\.\d+)?)\s*([^\s，。,（(0-9]{1,5})', text))
    if wan_matches:
        m = wan_matches[-1]
        original_amount = float(m.group(1)) * 10000
        currency_name = m.group(2)
    elif plain_matches:
        m = plain_matches[-1]
        original_amount = float(m.group(1))
        currency_name = m.group(2)

    if original_amount is None:
        return {'type': 'expense', 'trip': None, 'legs': [], 'expenses': []}

    currency_code = 'CNY'
    for key, code in _CURRENCY_CODE.items():
        if currency_name and key in currency_name:
            currency_code = code
            break

    rate = _CNY_PER_UNIT.get(currency_code, 1.0)
    amount_cny = round(original_amount * rate, 2)

    date_str = None
    m_date = re.search(r'(\d{1,2})[./](\d{1,2})', text)
    if m_date:
        month, day = int(m_date.group(1)), int(m_date.group(2))
        today = _date.today()
        year = today.year
        if month > today.month + 1:
            year -= 1
        try:
            date_str = f'{year}-{month:02d}-{day:02d}'
        except ValueError:
            pass

    desc = None
    m_desc = re.search(r'(?:花费|费用|消费|支出)[：:]\s*(.+?)(?:共|合计)\s*\d', text)
    if m_desc:
        desc = m_desc.group(1).strip()
    if not desc or len(desc) < 2:
        desc_m = re.search(r'[\u4e00-\u9fff]{2,8}(?:花费|费用|消费|支出)', text)
        if desc_m:
            desc = desc_m.group(0)
        else:
            desc_m = re.search(r'(新增|增加|添加|补录)\S*?\s*([\u4e00-\u9fff]{2,10})', text)
            desc = desc_m.group(2) if desc_m else '花费'

    if currency_code != 'CNY' and currency_name:
        orig_str = f'{int(original_amount // 10000)}万' if original_amount >= 10000 else str(int(original_amount))
        desc = f'{desc} ({orig_str}{currency_name})'

    category = '其他'
    for pat, cat in _CATEGORY_KEYWORDS:
        if re.search(pat, text):
            category = cat
            break

    expense = {
        'date': date_str,
        'category': category,
        'amount': amount_cny,
        'currency': 'CNY',
        'description': desc,
    }
    return {'type': 'expense', 'trip': None, 'legs': [], 'expenses': [expense]}


# ── set_accommodation ────────────────────────────────────────────────────────

def extract_set_accommodation(text: str) -> dict:
    """Extract hotel name from text."""
    name = None

    # "住在/住的 X酒店"
    m = re.search(r'住[的在了]\s*([\u4e00-\u9fffA-Za-z ]{2,20}(?:' + _ACCOM_TYPES + r')?)', text)
    if m:
        name = m.group(1).strip()

    # "酒店叫/是 X"
    if not name:
        m = re.search(r'(?:酒店|宾馆|民宿|客栈|旅馆|住宿)\s*(?:叫|是|名字叫)\s*([\u4e00-\u9fffA-Za-z ]{2,20})', text)
        if m:
            name = m.group(1).strip()

    # "入住了 X酒店"
    if not name:
        m = re.search(r'入住了?\s*([\u4e00-\u9fffA-Za-z ]{2,20}(?:' + _ACCOM_TYPES + r')?)', text)
        if m:
            name = m.group(1).strip()

    return {
        'type': 'accommodation',
        'accommodation': name,
        'trip': None,
        'legs': [],
        'expenses': [],
    }


# ── rename_activity ──────────────────────────────────────────────────────────

def extract_rename_activity(text: str) -> dict:
    """Extract old_name and new_name from rename commands.

    Supports patterns like:
      [旧名]改名为[新名]
      把旧名改名为新名
      将旧名重命名为新名
    """
    old_name = None
    new_name = None

    # "[旧名]改名为[新名]" or "[旧名]重命名为[新名]"（支持 [ 和 【 两种括号）
    m = re.search(r'[\[【](.+?)[\]】]\s*(?:改名为|重命名为|改为|更名为)\s*[\[【](.+?)[\]】]', text)
    if m:
        old_name, new_name = m.group(1).strip(), m.group(2).strip()

    # "把/将 旧名 改名为/重命名为 新名"
    if not old_name:
        m = re.search(
            r'(?:把|将)?\s*([\u4e00-\u9fffA-Za-z0-9·\-]{2,20}?)\s*(?:改名为|重命名为|更名为)\s*([\u4e00-\u9fffA-Za-z0-9·\-]{2,20})',
            text,
        )
        if m:
            old_name, new_name = m.group(1).strip(), m.group(2).strip()

    return {
        'type': 'rename',
        'old_name': old_name,
        'new_name': new_name,
        'trip': None,
        'legs': [],
        'expenses': [],
    }


# ── Dispatcher ───────────────────────────────────────────────────────────────

_EXTRACTORS = {
    'change_category': extract_change_category,
    'add_expense': extract_add_expense,
    'set_accommodation': extract_set_accommodation,
    'rename_activity': extract_rename_activity,
}


def extract(intent: str, text: str) -> dict:
    extractor = _EXTRACTORS.get(intent)
    if extractor:
        return extractor(text)
    return {'type': 'trip', 'trip': None, 'legs': [], 'expenses': []}
