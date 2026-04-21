"""Tests for Malaysia PDF parsing bugs.

Covers 7 root causes found in 202402 Malaysia trip PDF:
1. "打车" classified as "其他" instead of "交通"
2. "一日游" classified as "其他" instead of "门票"
3. Backfill wrongly promotes activity expense ("一日游") to "住宿"
4. Accommodation backfill includes "(MYR xxx)" price suffix
5. Cross-line activity match: "8.\\n吉隆坡" → "吉隆坡" as activity
6. Hotel names appear in activities list
7. Fake transport "兰卡威→Langkawi" from \\x00 cell separator
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.ai_parser import (
    parse_text, _normalize, _parse_expenses,
    _extract_activities, _extract_transport, _extract_accommodation,
)


MALAYSIA_PDF_TEXT = """SexySouL的马来西亚行程
2024年2月12日出发 | 共7天,2个国家,3个城市
作者:SexySouL
日期 城市 交通 景点 住宿
23:55 - 04:10 +1
12
星期一 北京 → 吉隆坡
2024年2月
1. 2. 旧国家皇宫 , Istana Negara 吉隆坡w酒店
13
星期二 3. 吉隆坡国际机场 , Kuala Lumpur
2024年2月 International Airport
4. 5. 6. 7. 8.
吉隆坡 12:05 - 13:10 1. 2. 3. 兰卡威雅乐轩酒店,Aloft
14
星期三 Kuala Lumpur 兰卡威 → Langkawi Pantai Tengah,
2024年2月 地址:Lot PT 701 Jalan
1. 兰卡威雅乐轩酒店,Aloft
15
星期四 Langkawi Pantai Tengah,
2024年2月
兰卡威 21:10 - 21:50 1. 槟城万怡酒店
16
星期五 Pulau →
2024年2月 Langkawi
1. 2. 3. 依恩奥酒店,Eastern &
17
星期六 Oriental Hotel,槟城
2024年2月 地址:10 Lebuh Farquhar
13:30 - 14:35 1.
18
星期天 →
2024年2月
18:50 - 23:15
→
| P1
→→
吉隆坡//兰卡威
时间 班次 出发 到达 到达时间
1122::0055 AAKK66330044 1133::1100
→→
兰卡威//槟城
时间 班次 出发 到达 到达时间
2211::1100 AAKK66224433 2211::5500
→→
槟城//吉隆坡
时间 班次 出发 到达 到达时间
1133::3300 AAKK66112255 ((PPEENN)) 1144::3355
→→
吉隆坡//北京
时间 班次 出发 到达 到达时间
1188::5500 DD77334422 槟城国际机场 2233::1155
第1天（总价：¥11866.43） 单价 数量 总价
北京到吉隆坡的交通预算 CNY 3551.00 2 CNY 7102
暂无标题 MYR 1050.00 1 MYR 1050
打车 CNY 1758.00 1 CNY 1758
暂无标题 CNY 979.00 1 CNY 979
暂无标题 CNY 397.00 1 CNY 397
第2天（总价：¥1838.51） 单价 数量 总价
吉隆坡w酒店 MYR 1184.00 1 MYR 1184
第3天（总价：¥4111.33） 单价 数量 总价
吉隆坡到兰卡威的交通预算 CNY 1228.80 2 CNY 2457.6
兰卡威雅乐轩酒店 MYR 1065.00 1 MYR 1065
第4天（总价：¥2216） 单价 数量 总价
兰卡威红树林一日游 CNY 2216.00 1 CNY 2216
第5天（总价：¥834.22） 单价 数量 总价
槟城万怡酒店 MYR 537.24 1 MYR 537.24
第6天（总价：¥1182.73） 单价 数量 总价
槟城东方大酒店 MYR 761.68 1 MYR 761.68
"""


def _find_day(result, day_number):
    for leg in result['legs']:
        for d in leg['days']:
            if d['day_number'] == day_number:
                return d
    raise ValueError(f'Day {day_number} not found')


def _find_expense(result, keyword):
    for exp in result['expenses']:
        if keyword in exp['description']:
            return exp
    raise ValueError(f'Expense containing "{keyword}" not found')


class TestExpenseCategory:
    """Bug 1 & 2: CATEGORY_RULES missing keywords."""

    def test_dache_is_transport(self):
        """打车 should be 交通, not 其他."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        exp = _find_expense(result, '打车')
        assert exp['category'] == '交通'

    def test_day_tour_is_ticket(self):
        """一日游 should be 门票, not 其他 or 住宿."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        exp = _find_expense(result, '红树林一日游')
        assert exp['category'] == '门票'


class TestAccommodationBackfill:
    """Bug 3 & 4: Accommodation backfill issues."""

    def test_day_tour_not_promoted_to_accommodation(self):
        """一日游 expense should NOT be promoted to 住宿 category."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        exp = _find_expense(result, '红树林一日游')
        assert exp['category'] != '住宿'

    def test_day4_accommodation_not_day_tour(self):
        """Day 4 accommodation should NOT be 兰卡威红树林一日游."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        day4 = _find_day(result, 4)
        accom = day4.get('accommodation') or ''
        assert '一日游' not in accom

    def test_accommodation_no_price_suffix(self):
        """Accommodation name should not contain (MYR xxx) price info."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        day2 = _find_day(result, 2)
        accom = day2.get('accommodation') or ''
        assert 'MYR' not in accom
        assert accom != ''


class TestActivityExtraction:
    """Bug 5 & 6: Activity extraction issues."""

    def test_city_name_not_activity(self):
        """City name '吉隆坡' from cross-line '8.\\n吉隆坡' should not be an activity."""
        chunk = "4. 5. 6. 7. 8.\n吉隆坡 12:05 - 13:10"
        activities = _extract_activities(chunk)
        assert '吉隆坡' not in activities

    def test_hotel_not_activity(self):
        """Hotel names like '兰卡威雅乐轩酒店' should be filtered from activities."""
        chunk = "1. 2. 3. 兰卡威雅乐轩酒店,Aloft"
        activities = _extract_activities(chunk)
        hotel_activities = [a for a in activities if '酒店' in a]
        assert hotel_activities == []


class TestTransportExtraction:
    """Bug 7: Fake transport from cell separator."""

    def test_no_fake_langkawi_route(self):
        """兰卡威→Langkawi is a fake route from PDF table separator, not real transport."""
        chunk = "Kuala Lumpur 兰卡威 → Langkawi Pantai Tengah,"
        routes = _extract_transport(chunk)
        assert '兰卡威→Langkawi' not in routes

    def test_real_route_preserved(self):
        """Real CJK→CJK routes like 北京→吉隆坡 should still work."""
        chunk = "星期一 北京 → 吉隆坡\n2024年2月"
        routes = _extract_transport(chunk)
        assert '北京→吉隆坡' in routes


class TestFlightExtraction:
    """Flights from detail pages should be injected into day transports."""

    def test_day3_has_kl_langkawi_flight(self):
        """Day 3 should have 吉隆坡→兰卡威 flight AK6304."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        day3 = _find_day(result, 3)
        transport_str = ' '.join(day3.get('transport', []))
        assert '吉隆坡' in transport_str and '兰卡威' in transport_str
        assert 'AK6304' in transport_str

    def test_day5_has_langkawi_penang_flight(self):
        """Day 5 should have 兰卡威→槟城 flight AK6243."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        day5 = _find_day(result, 5)
        transport_str = ' '.join(day5.get('transport', []))
        assert '兰卡威' in transport_str and '槟城' in transport_str
        assert 'AK6243' in transport_str

    def test_day7_has_two_flights(self):
        """Day 7 should have both 槟城→吉隆坡 (AK6125) and 吉隆坡→北京 (D7342)."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        day7 = _find_day(result, 7)
        transport_str = ' '.join(day7.get('transport', []))
        assert 'AK6125' in transport_str
        assert 'D7342' in transport_str

    def test_day1_still_has_route(self):
        """Day 1 should still have 北京→吉隆坡 from overview."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        day1 = _find_day(result, 1)
        transport_str = ' '.join(day1.get('transport', []))
        assert '北京' in transport_str and '吉隆坡' in transport_str


class TestCityFromTransport:
    """City assignment should use transport route info."""

    def test_day3_city_is_langkawi(self):
        """Day 3 has flight 吉隆坡→兰卡威 → city should be 兰卡威 (arrival)."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        day3 = _find_day(result, 3)
        leg = next(l for l in result['legs'] if any(d['day_number'] == 3 for d in l['days']))
        assert leg['city'] == '兰卡威'

    def test_day5_city_is_penang(self):
        """Day 5 has flight 兰卡威→槟城 → city should be 槟城 (arrival)."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        leg = next(l for l in result['legs'] if any(d['day_number'] == 5 for d in l['days']))
        assert leg['city'] == '槟城'

    def test_day7_city_is_penang(self):
        """Day 7 is return day (槟城→吉隆坡→北京) → city should be 槟城 (first departure)."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        leg = next(l for l in result['legs'] if any(d['day_number'] == 7 for d in l['days']))
        assert leg['city'] == '槟城'

    def test_no_pending_city(self):
        """All legs should have confirmed cities (no [待确认])."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        cities = [l['city'] for l in result['legs']]
        assert '[待确认]' not in cities

    def test_three_city_legs(self):
        """Malaysia trip should have exactly 3 city legs: 吉隆坡, 兰卡威, 槟城."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        cities = [l['city'] for l in result['legs']]
        assert cities == ['吉隆坡', '兰卡威', '槟城']


class TestFullParseMalaysia:
    """Integration: full parse of Malaysia PDF text."""

    def test_expense_count(self):
        result = parse_text(MALAYSIA_PDF_TEXT)
        assert len(result['expenses']) == 11

    def test_day_count(self):
        result = parse_text(MALAYSIA_PDF_TEXT)
        total_days = sum(len(leg['days']) for leg in result['legs'])
        assert total_days == 7

    def test_day1_no_attraction(self):
        """Day 1 is an overnight departure — should have no attractions like 旧国家皇宫."""
        result = parse_text(MALAYSIA_PDF_TEXT)
        day1 = _find_day(result, 1)
        assert '旧国家皇宫' not in day1.get('activities', [])
