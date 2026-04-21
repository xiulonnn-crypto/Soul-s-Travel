"""Tests for ai_parser with Sri Lanka and Korea PDF text structures.

Sri Lanka PDF: 8 days, 7 cities, no activities, no routes (arrows).
Korea PDF: 8 days, uses PUA arrow char \ue6ae instead of →.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.ai_parser import parse_text, _normalize

# ── Sri Lanka PDF (minimal reproduction of overview + expense) ──────────────
SRILANKA_PDF_TEXT = """SexySouL的斯里兰卡行
程
2023年5月8日出发 | 共8天,1个国家,7个城市
作者:SexySouL
日期 城市 交通 景点 住宿
成都
08
星期一 Chengdu
2023年5月 尼甘布
Negombo
尼甘布
09
星期二 Negombo
2023年5月 丹布勒
Dambulla
丹布勒
10
星期三 Dambulla
2023年5月 斯里兰卡康堤
Kandy
斯里兰卡康堤
11
星期四 Kandy
2023年5月 努瓦勒埃利耶
Nuwara eliya
努瓦勒埃利耶
12
星期五 Nuwara eliya
2023年5月 埃勒
Ella
埃勒
13
星期六 Ella
2023年5月 加勒
Galle
加勒
14
星期天 Galle
2023年5月
加勒
15
星期一 Galle
2023年5月 科伦坡
Colombo
北京
Beijing
| P1
全部费用
CNY 20280
第1天(总价:¥16457) 单价 数量 总价
地接司导 CNY 3500.00 1 CNY 3500
机票 CNY 12957.00 1 CNY 12957
第8天(总价:¥3823) 单价 数量 总价
现金 CNY 3823.00 1 CNY 3823
"""

# ── Korea PDF (minimal reproduction — uses \ue6ae as arrow) ─────────────────
KOREA_PDF_TEXT = (
    "SexySouL的韩国行程\n"
    "2023年9月29日出发 | 共8天,2个国家,5个城市\n"
    "作者:SexySouL\n"
    "日期 城市 交通 景点 住宿\n"
    "北京 10:40 - 13:50 1. 首尔广场 , Seoul Plaza 首尔广场傲途格精选酒\n"
    "29\n"
    "星期五 Beijing 北京 \ue6ae 首尔 2. 明洞天主教堂 , Myeong-Dong Catholic 店,The Plaza Seoul,\n"
    "2023年9月 首尔 Cathedral Autograph Collection,首\n"
    "Seoul 3. 明洞 , Myeong-dong 尔\n"
    "首尔 1. 北村韩屋村 , Bukchon Hanok Village 首尔广场傲途格精选酒\n"
    "30\n"
    "星期六 Seoul 2. 弘大 店,The Plaza Seoul,\n"
    "2023年9月 3. N首尔塔 , N Seoul Tower Autograph Collection,首\n"
    "尔\n"
    "首尔 1. 光化门广场 , Gwanghwamun 首尔广场傲途格精选酒\n"
    "01\n"
    "星期天 Seoul 2. 景福宫 , Gyeongbok Gung 店,The Plaza Seoul,\n"
    "2023年10月 3. 国立古宫博物馆 Autograph Collection,首\n"
    "尔\n"
    "首尔 1. 清潭洞 , Cheongdam Dong 首尔广场傲途格精选酒\n"
    "02\n"
    "星期一 Seoul 2. 牛家 店,The Plaza Seoul,\n"
    "2023年10月 3. 国立中央博物馆儿童馆 Autograph Collection,首\n"
    "尔\n"
    "首尔 19:20 - 20:30 1. 大瓦房酱油蟹 万豪济州神话世界酒\n"
    "03\n"
    "星期二 Seoul 首尔 \ue6ae 济州岛 2. Dombe豚 店,Marriott Jeju Shinhwa\n"
    "2023年10月 济州岛 World Hotel,西归浦\n"
    "Jejudo\n"
    "济州岛 万豪济州神话世界酒\n"
    "04\n"
    "星期三 Jejudo 店,Marriott Jeju Shinhwa\n"
    "2023年10月 济州市 World Hotel,西归浦\n"
    "Jeju\n"
    "济州岛 1. Hello Kitty主题公园 , Hello Kitty Island 万豪济州神话世界酒\n"
    "05\n"
    "星期四 Jejudo 2. 山茶花之丘 , camellia hill 店,Marriott Jeju Shinhwa\n"
    "2023年10月 济州市 3. 泰迪熊博物馆 World Hotel,西归浦\n"
    "Jeju\n"
    "济州岛 22:40 - 01:10 1. 正房瀑布 , Jeongbang Falls\n"
    "06\n"
    "星期五 Jejudo 济州岛 \ue6ae 北京 2. 柱状节理\n"
    "2023年10月 北京 3. 济州岛泰迪熊博物馆\n"
    "Beijing\n"
    "| P1\n"
    "全部费用\n"
    "CNY 50000\n"
    "第1天(总价:¥6000) 单价 数量 总价\n"
    "机票 CNY 3000.00 2 CNY 6000\n"
    "第8天(总价:¥6000) 单价 数量 总价\n"
    "机票 CNY 3000.00 2 CNY 6000\n"
)


def _find_day(result, day_number):
    for leg in result['legs']:
        for d in leg['days']:
            if d['day_number'] == day_number:
                return d
    raise ValueError(f'Day {day_number} not found')


def _find_leg(result, city):
    for leg in result['legs']:
        if leg['city'] == city:
            return leg
    return None


# ── Sri Lanka Tests ─────────────────────────────────────────────────────────

class TestSriLankaCities:
    """All 7 destination cities must be recognized with correct countries."""

    def test_leg_count(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        assert len(result['legs']) >= 7

    def test_negombo(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        leg = _find_leg(result, '尼甘布')
        assert leg is not None
        assert leg['country'] == '斯里兰卡'

    def test_dambulla(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        leg = _find_leg(result, '丹布勒')
        assert leg is not None
        assert leg['country'] == '斯里兰卡'

    def test_kandy(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        leg = _find_leg(result, '康堤')
        assert leg is not None
        assert leg['country'] == '斯里兰卡'

    def test_nuwara_eliya(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        leg = _find_leg(result, '努瓦勒埃利耶')
        assert leg is not None
        assert leg['country'] == '斯里兰卡'

    def test_ella(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        leg = _find_leg(result, '埃勒')
        assert leg is not None
        assert leg['country'] == '斯里兰卡'

    def test_galle(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        leg = _find_leg(result, '加勒')
        assert leg is not None
        assert leg['country'] == '斯里兰卡'

    def test_colombo(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        leg = _find_leg(result, '科伦坡')
        assert leg is not None
        assert leg['country'] == '斯里兰卡'

    def test_no_pending_country(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        for leg in result['legs']:
            assert leg['country'] != '[待确认]', f'{leg["city"]} country is [待确认]'


class TestSriLankaDates:

    def test_start_date(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        assert result['trip']['start_date'] == '2023-05-08'

    def test_end_date(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        assert result['trip']['end_date'] == '2023-05-15'

    def test_day_count(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        all_days = [d for leg in result['legs'] for d in leg['days']]
        assert len(all_days) == 8


class TestSriLankaTitle:

    def test_title_contains_srilanka(self):
        result = parse_text(SRILANKA_PDF_TEXT)
        title = result['trip']['title']
        assert '斯里兰卡' in title

    def test_title_joined(self):
        """Title split across lines (行\\n程) should be joined."""
        result = parse_text(SRILANKA_PDF_TEXT)
        title = result['trip']['title']
        assert '行程' in title


# ── Korea Tests ─────────────────────────────────────────────────────────────

class TestKoreaArrowNormalization:
    """PUA arrow \\ue6ae must be normalized to → for route detection."""

    def test_normalize_pua_arrow(self):
        text = '北京 \ue6ae 首尔'
        assert '→' in _normalize(text)

    def test_day1_is_seoul_not_beijing(self):
        result = parse_text(KOREA_PDF_TEXT)
        day1 = _find_day(result, 1)
        seoul_leg = _find_leg(result, '首尔')
        assert seoul_leg is not None
        assert any(d['day_number'] == 1 for d in seoul_leg['days'])

    def test_no_beijing_leg(self):
        result = parse_text(KOREA_PDF_TEXT)
        beijing = _find_leg(result, '北京')
        assert beijing is None, 'Beijing should not be a destination leg'


class TestKoreaCities:

    def test_seoul_leg(self):
        result = parse_text(KOREA_PDF_TEXT)
        seoul = _find_leg(result, '首尔')
        assert seoul is not None
        assert seoul['country'] == '韩国'

    def test_jeju_leg(self):
        result = parse_text(KOREA_PDF_TEXT)
        jeju = _find_leg(result, '济州岛')
        assert jeju is not None
        assert jeju['country'] == '韩国'

    def test_day5_is_jeju(self):
        """Day 5 has route 首尔→济州岛, should be in Jeju leg."""
        result = parse_text(KOREA_PDF_TEXT)
        jeju = _find_leg(result, '济州岛')
        assert jeju is not None
        assert any(d['day_number'] == 5 for d in jeju['days'])

    def test_day8_return_stays_in_jeju(self):
        """Day 8 (Jeju→Beijing) should stay in Jeju, not become Beijing."""
        result = parse_text(KOREA_PDF_TEXT)
        jeju = _find_leg(result, '济州岛')
        assert jeju is not None
        assert any(d['day_number'] == 8 for d in jeju['days'])


class TestKoreaDates:

    def test_start_date(self):
        result = parse_text(KOREA_PDF_TEXT)
        assert result['trip']['start_date'] == '2023-09-29'

    def test_end_date(self):
        result = parse_text(KOREA_PDF_TEXT)
        assert result['trip']['end_date'] == '2023-10-06'


# ── Japan country fix ───────────────────────────────────────────────────────

class TestNaraCountry:
    """奈良 must map to 日本 in COUNTRY_MAP."""

    def test_nara_country_is_japan(self):
        from services.ai_parser import COUNTRY_MAP
        assert COUNTRY_MAP.get('奈良') == '日本'


# ── Missing Sri Lanka cities ──────────────────────────────────────────────

class TestNewSriLankaCities:
    """蒂瑟 and 美瑞莎 must be recognized as Sri Lanka destinations."""

    def test_tissa_in_dest(self):
        from services.ai_parser import DEST_CITIES
        assert '蒂瑟' in DEST_CITIES

    def test_mirissa_in_dest(self):
        from services.ai_parser import DEST_CITIES
        assert '美瑞莎' in DEST_CITIES

    def test_tissa_country(self):
        from services.ai_parser import COUNTRY_MAP
        assert COUNTRY_MAP.get('蒂瑟') == '斯里兰卡'

    def test_mirissa_country(self):
        from services.ai_parser import COUNTRY_MAP
        assert COUNTRY_MAP.get('美瑞莎') == '斯里兰卡'

    def test_en_negombo(self):
        from services.ai_parser import _EN_TO_ZH_CITY
        assert _EN_TO_ZH_CITY.get('Negombo') == '尼甘布'

    def test_en_dambulla(self):
        from services.ai_parser import _EN_TO_ZH_CITY
        assert _EN_TO_ZH_CITY.get('Dambulla') == '丹布勒'

    def test_en_ella(self):
        from services.ai_parser import _EN_TO_ZH_CITY
        assert _EN_TO_ZH_CITY.get('Ella') == '埃勒'

    def test_en_tissa(self):
        from services.ai_parser import _EN_TO_ZH_CITY
        assert _EN_TO_ZH_CITY.get('Tissa') == '蒂瑟'

    def test_en_mirissa(self):
        from services.ai_parser import _EN_TO_ZH_CITY
        assert _EN_TO_ZH_CITY.get('Mirissa') == '美瑞莎'

    def test_en_weligama(self):
        from services.ai_parser import _EN_TO_ZH_CITY
        assert _EN_TO_ZH_CITY.get('Weligama') == '美瑞莎'


# ── NLU compound command ──────────────────────────────────────────────────

class TestNLUCompoundCommand:
    """Compound commands separated by ；should produce multiple results."""

    def test_multi_expense_semicolon(self):
        text = '新增花费：交通100元；补录住宿费800块'
        result = parse_text(text)
        assert result['type'] == 'compound'
        assert len(result['actions']) >= 2

    def test_category_change_in_compound(self):
        text = '新增花费：交通100元；把地接司导的类别改为交通'
        result = parse_text(text)
        assert result['type'] == 'compound'
        types = [a.get('type') for a in result['actions']]
        assert 'expense' in types

    def test_single_command_not_compound(self):
        text = '新增花费：交通100元'
        result = parse_text(text)
        assert result['type'] != 'compound'
