"""Tests for Korea PDF with doubled-character expense table headers.

The Korea PDF uses doubled characters for all chars on certain rows:
  第第11天天 → after CJK dedup → 第11天 (bug: treated as day 11 not day 1)
This causes wrong expense dates and missing accommodation backfill.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.ai_parser import parse_text, _normalize

# Minimal reproduction: overview table + doubled-digit expense table
KOREA_PDF_TEXT = """SexySouL的韩国行程
2023年9月29日出发 ｜ 共8天，2个国家，5个城市
作者：SexySouL
北京 10:40 - 13:50 1. 首尔广场 ， Seoul Plaza 首尔广场傲途格精选酒
29
星期五 Beijing 北京  首尔 2. 明洞天主教堂 ， Myeong-Dong Catholic 店，The Plaza Seoul,
2023年9月 首尔 Cathedral Autograph Collection，首
Seoul 3. 明洞 ， Myeong-dong 尔
首尔 1. 北村韩屋村 ， Bukchon Hanok Village 首尔广场傲途格精选酒
30
星期六 Seoul 2. 弘大 店，The Plaza Seoul,
2023年9月 3. N首尔塔 ， N Seoul Tower Autograph Collection，首
尔
首尔 19:20 - 20:30 1. 大瓦房酱油蟹 万豪济州神话世界酒
03
星期二 Seoul 首尔  济州岛 2. Dombe豚(黑猪肉街店) 店，Marriott Jeju Shinhwa
2023年10月 济州岛 World Hotel，西归浦
Jejudo
济州岛 22:40 - 01:10 1. 正房瀑布 ， Jeongbang Falls
06
星期五 Jejudo 济州岛  北京 2. 柱状节理
2023年10月 北京
Beijing
| P1
花花费费 全部费用
CCNNYY 2200330022..7799
第第11天天（总价：¥8676） 单价 数量 总价
首尔广场傲途格精选酒店,The Plaza Seoul,
CNY 1666.00 1 CNY 1666
机票 CNY 3505.00 2 CNY 7010
第第22天天（总价：¥1666） 单价 数量 总价
首尔广场傲途格精选酒店 CNY 1666.00 1 CNY 1666
第第33天天（总价：¥1666） 单价 数量 总价
首尔广场傲途格精选酒店,The Plaza Seoul,
CNY 1666.00 1 CNY 1666
第第55天天（总价：¥1190） 单价 数量 总价
万豪济州神话世界酒店,Marriott Jeju Shinhwa CNY 1190.00 1 CNY 1190
第第66天天（总价：¥1190） 单价 数量 总价
万豪济州神话世界酒店,Marriott Jeju Shinhwa CNY 1190.00 1 CNY 1190
"""


def _find_day(result, day_number):
    for leg in result['legs']:
        for d in leg['days']:
            if d['day_number'] == day_number:
                return d
    raise ValueError(f'Day {day_number} not found')


class TestNormalizeDoubledDigits:
    """_normalize should collapse PDF-doubled digit sequences in day-header context."""

    def test_doubled_day1(self):
        assert '第11天' not in _normalize('第第11天天')
        assert '第1天' in _normalize('第第11天天')

    def test_doubled_day2(self):
        assert '第2天' in _normalize('第第22天天')

    def test_doubled_day10(self):
        """Two-digit day like 10 → 第第1100天天 → 第10天."""
        assert '第10天' in _normalize('第第1100天天')

    def test_normal_day1_unchanged(self):
        assert '第1天' in _normalize('第1天')

    def test_normal_day10_unchanged(self):
        assert '第10天' in _normalize('第10天')

    def test_amount_unchanged(self):
        """CNY amounts like 1666 must NOT be affected."""
        result = _normalize('CNY 1666.00 1 CNY 1666')
        assert '1666' in result

    def test_amount_1190_unchanged(self):
        result = _normalize('CNY 1190.00 1 CNY 1190')
        assert '1190' in result


class TestKoreaExpenseDates:
    """Expense dates must map to actual trip dates, not 10+ days later."""

    def test_day1_expense_date(self):
        result = parse_text(KOREA_PDF_TEXT)
        hotel_d1 = [e for e in result['expenses']
                    if '首尔广场傲途格精选酒店' in e['description'] and e['date'] == '2023-09-29']
        assert len(hotel_d1) >= 1, (
            f"期望第1天费用日期=2023-09-29，实际费用={result['expenses']}"
        )

    def test_day2_expense_date(self):
        result = parse_text(KOREA_PDF_TEXT)
        hotel_d2 = [e for e in result['expenses']
                    if '首尔广场傲途格精选酒店' in e['description'] and e['date'] == '2023-09-30']
        assert len(hotel_d2) >= 1

    def test_no_wrong_dates(self):
        """No expense should have dates beyond 2023-10-06 (trip end)."""
        result = parse_text(KOREA_PDF_TEXT)
        for exp in result['expenses']:
            assert exp['date'] <= '2023-10-06', (
                f"费用日期 {exp['date']} 超出行程范围: {exp['description']}"
            )

    def test_flight_expense_date(self):
        result = parse_text(KOREA_PDF_TEXT)
        flight = [e for e in result['expenses'] if '机票' in e['description']]
        assert len(flight) >= 1
        assert flight[0]['date'] == '2023-09-29'


class TestKoreaAccommodationBackfill:
    """Accommodation names should be backfilled from expense table."""

    def test_day1_seoul_hotel(self):
        result = parse_text(KOREA_PDF_TEXT)
        day1 = _find_day(result, 1)
        accom = day1['accommodation'] or ''
        assert '首尔广场傲途格精选酒店' in accom or 'Plaza' in accom, (
            f"Day 1 accommodation should contain hotel name, got: {accom!r}"
        )

    def test_day2_seoul_hotel(self):
        result = parse_text(KOREA_PDF_TEXT)
        day2 = _find_day(result, 2)
        accom = day2['accommodation'] or ''
        assert '首尔广场傲途格精选酒店' in accom or 'Plaza' in accom


# ── 用真实 PDF 结构补充的 USD 费用测试 ─────────────────────────────────────────
KOREA_DAY4_USD_TEXT = """SexySouL的韩国行程
2023年9月29日出发 ｜ 共5天，1个国家，1个城市
作者：SexySouL
北京 10:40 - 13:50 1. 首尔广场
29
星期五 Beijing 北京  首尔 2. 明洞
2023年9月 首尔
Seoul
首尔 1. 清潭洞
02
星期一 Seoul 2. 牛家
2023年10月 首尔
Seoul
| P1
第第11天天（总价：¥8676） 单价 数量 总价
机票 CNY 3505.00 2 CNY 7010
第第44天天（总价：¥5179.79） 单价 数量 总价
牛家 USD 197.12 1 USD 197.12
清潭洞,Cheongdam Dong USD 312.38 1 USD 312.38
首尔广场傲途格精选酒店,The Plaza Seoul,
CNY 1666.00 1 CNY 1666
"""


class TestKoreaUSDExpenses:
    """USD expenses must be converted to CNY using the day total back-calculation.

    Day 4 breakdown:
      day_total = 5179.79 CNY
      hotel     = 1666.00 CNY
      remaining = 3513.79 CNY (= USD 197.12 + USD 312.38 at implicit rate)
      rate      = 3513.79 / 509.50 ≈ 6.896 CNY/USD
    """
    # Implicit rate for day 4: (5179.79 - 1666.00) / (197.12 + 312.38)
    _rate = (5179.79 - 1666.00) / (197.12 + 312.38)

    def test_usd_converted_to_cny(self):
        result = parse_text(KOREA_DAY4_USD_TEXT)
        niujia = [e for e in result['expenses'] if '牛家' in e['description']]
        assert len(niujia) == 1
        assert niujia[0]['currency'] == 'CNY', (
            f"USD 费用应折算为 CNY，实际 currency={niujia[0]['currency']}"
        )

    def test_niujia_converted_amount(self):
        result = parse_text(KOREA_DAY4_USD_TEXT)
        niujia = next(e for e in result['expenses'] if '牛家' in e['description'])
        expected = round(197.12 * self._rate, 2)
        assert niujia['amount'] == pytest.approx(expected, rel=1e-4)

    def test_qingtan_converted_amount(self):
        result = parse_text(KOREA_DAY4_USD_TEXT)
        qingtan = next(e for e in result['expenses'] if '清潭洞' in e['description'])
        expected = round(312.38 * self._rate, 2)
        assert qingtan['amount'] == pytest.approx(expected, rel=1e-4)

    def test_converted_sum_equals_remaining_cny(self):
        """两条USD费用折算后加总，应精确等于（第4天总价 - CNY酒店）。"""
        result = parse_text(KOREA_DAY4_USD_TEXT)
        converted = [e for e in result['expenses']
                     if '牛家' in e['description'] or '清潭洞' in e['description']]
        assert len(converted) == 2
        assert sum(e['amount'] for e in converted) == pytest.approx(3513.79, rel=1e-4)

    def test_original_currency_in_description(self):
        """描述中应保留原始外币金额，方便用户核对。"""
        result = parse_text(KOREA_DAY4_USD_TEXT)
        niujia = next(e for e in result['expenses'] if '牛家' in e['description'])
        assert 'USD' in niujia['description'] and '197.12' in niujia['description'], (
            f"描述应含原始外币，实际: {niujia['description']!r}"
        )

    def test_usd_expense_has_date(self):
        result = parse_text(KOREA_DAY4_USD_TEXT)
        niujia = next(e for e in result['expenses'] if '牛家' in e['description'])
        assert niujia['date'] == '2023-10-02'

    def test_total_expense_count(self):
        """全部 4 条费用都被解析出来。"""
        result = parse_text(KOREA_DAY4_USD_TEXT)
        assert len(result['expenses']) == 4

    def test_cny_items_unchanged(self):
        """CNY 原始费用金额不受折算影响。"""
        result = parse_text(KOREA_DAY4_USD_TEXT)
        hotel = [e for e in result['expenses'] if '首尔广场傲途格精选酒店' in e['description']]
        assert len(hotel) == 1
        assert hotel[0]['amount'] == pytest.approx(1666.0)
        assert hotel[0]['currency'] == 'CNY'


# ── 景点类型标签驱动的费用分类测试 ────────────────────────────────────────────
# PDF 第13页: 牛家 → "其他美食" 类型标签 → 应归类为餐饮
KOREA_ACTIVITY_TYPE_TEXT = """SexySouL的韩国行程
2023年9月29日出发 ｜ 共4天，1个国家，1个城市
作者：SexySouL
首尔 1. 牛家
02
星期一 Seoul 2. 清潭洞
2023年10月 首尔
Seoul
| P1
 1.2公里


牛牛家家
其他美食
地地址址 首尔特别市江南区新沙洞653-20
时时间间 12:00-22:00

 4.84公里


清清潭潭洞洞，，Cheongdam Dong
其他景点
地地址址 首尔特别市江南区清潭洞
时时间间 全天开放
| P2
第第22天天（总价：¥1888） 单价 数量 总价
牛家 CNY 300.00 1 CNY 300
清潭洞 CNY 500.00 1 CNY 500
"""


class TestActivityTypeCategoryMapping:
    """从 PDF 景点类型标签推导费用分类。"""

    def test_niujia_classified_as_dining(self):
        """牛家在 PDF 中标注为"其他美食"，费用应归类为餐饮。"""
        result = parse_text(KOREA_ACTIVITY_TYPE_TEXT)
        niujia = next(e for e in result['expenses'] if '牛家' in e['description'])
        assert niujia['category'] == '餐饮', (
            f"牛家应为餐饮，实际={niujia['category']}"
        )
