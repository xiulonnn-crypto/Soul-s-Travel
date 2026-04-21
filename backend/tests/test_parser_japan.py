"""Tests for ai_parser with Japan 2019 PDF text structure.

The PDF has 8 days spanning April 27 → May 4, crossing a month boundary.
Day markers use day-of-month numbers (27, 28, ..., 01, 02, ..., 04).
Expense table has repeated hotel names across different days.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.ai_parser import parse_text, _normalize, _split_by_day, _parse_expenses
from services.nlu.classifier import classify
from services.nlu.extractors import extract_change_category, extract_add_expense, extract_set_accommodation

# Minimal reproduction of the Japan PDF overview + expense structure
JAPAN_PDF_TEXT = """SexySouL的日本行程
2019年4月27日出发 | 共8天,1个国家,4个城市
作者:SexySouL
香港 18:05 - 23:25 1. 新宿三丁目歌舞伎町 , Kabukichō 酒店 Villa Fontaine 东京田
27
星期六 Hong Kong 香港 → 东京 町,Hotel Villa Fontaine
2019年4月 东京 Grand Tokyo-Tamachi,东京
Tokyo 地址:Mita First Building
东京 1. 秋叶原 , Akihabara 酒店 Villa Fontaine 东京田
28
星期天 Tokyo 2. 浅草寺 , Sensōji 町,Hotel Villa Fontaine
2019年4月 3. 银座 , Ginza
4. 东京塔 , Tokyo Tower
5. 一兰拉面(涩谷店) , Yichiran ramen
东京 1. 东京迪士尼度假区 , Tokyo Disney Resort 酒店 Villa Fontaine 东京田
29
星期一 Tokyo 町,Hotel Villa Fontaine
2019年4月
东京 --:-- - --:-- 1. 浅草寺 , Sensōji 月沈原
30
星期二 Tokyo 东京 → 京都 2. 原宿竹下通 , TakeshitaDōri
2019年4月 京都 3. 明治神宫,Meiji Jingu
Kyoto 4. 花见小路 , Hanamikoji Dori
京都 --:-- - --:-- 1. 奈良公园 , Nara Park 樱花酒店,HOTEL Mai
01
星期三 Kyoto 京都 → 奈良 Sakura,奈良
2019年5月 奈良 地址:三条本町 7-7
Nara
奈良 --:-- - --:-- 1. Hep Five摩天轮 , Hep Five Ferris Wheel 大阪圆顶球场无限酒店
02
星期四 Nara 奈良 → 大阪 2. 大丸(梅田店) , Daimaru Umeda
2019年5月 大阪 3. 松阪牛焼肉 M 法善寺横丁店
Osaka
大阪 1. 黑门市场 , Kuromon Ichiba Market 大阪圆顶球场无限酒店
03
星期五 Osaka 2. 心斋桥 , Shinsaibashi
2019年5月 3. 道顿堀 , Dōtonbori
4. 大阪城公园 , Osaka Castle Park
大阪 --:-- - --:--
04
星期六 Osaka 大阪 → 香港
2019年5月 香港
Hong Kong
日期 城市 交通 景点 住宿
| P1
全部费用
CNY 11768
第1天(总价:¥3638) 单价 数量 总价
香港到东京的交通预算 CNY 1294.00 2 CNY 2588
东京田町芬迪别墅大酒店 CNY 1050.00 1 CNY 1050
第2天(总价:¥1050) 单价 数量 总价
东京田町芬迪别墅大酒店 CNY 1050.00 1 CNY 1050
第3天(总价:¥1050) 单价 数量 总价
东京田町芬迪别墅大酒店 CNY 1050.00 1 CNY 1050
第4天(总价:¥800) 单价 数量 总价
月沈原 CNY 800.00 1 CNY 800
第5天(总价:¥539) 单价 数量 总价
樱花酒店 CNY 539.00 1 CNY 539
第6天(总价:¥705.5) 单价 数量 总价
大阪圆顶球场无限酒店 CNY 705.50 1 CNY 705.5
第7天(总价:¥705.5) 单价 数量 总价
大阪圆顶球场无限酒店 CNY 705.50 1 CNY 705.5
第8天(总价:¥3280) 单价 数量 总价
大阪到香港的交通预算 CNY 1640.00 2 CNY 3280
"""


class TestJapanPDFDates:
    """Day dates should be sequential from start_date, not derived from day-of-month."""

    def test_start_and_end_date(self):
        result = parse_text(JAPAN_PDF_TEXT)
        assert result['trip']['start_date'] == '2019-04-27'
        assert result['trip']['end_date'] == '2019-05-04'

    def test_day_dates_sequential(self):
        result = parse_text(JAPAN_PDF_TEXT)
        legs = result['legs']
        all_days = [d for leg in legs for d in leg['days']]
        dates = sorted(d['date'] for d in all_days if d['date'])
        expected = [
            '2019-04-27', '2019-04-28', '2019-04-29', '2019-04-30',
            '2019-05-01', '2019-05-02', '2019-05-03', '2019-05-04',
        ]
        assert dates == expected

    def test_day_numbers_sequential(self):
        result = parse_text(JAPAN_PDF_TEXT)
        legs = result['legs']
        all_days = [d for leg in legs for d in leg['days']]
        day_numbers = [d['day_number'] for d in all_days]
        assert sorted(day_numbers) == list(range(1, 9))

    def test_tokyo_leg_dates(self):
        result = parse_text(JAPAN_PDF_TEXT)
        tokyo_leg = next(l for l in result['legs'] if l['city'] == '东京')
        assert tokyo_leg['start_date'] == '2019-04-27'
        assert tokyo_leg['end_date'] == '2019-04-29'


class TestJapanPDFExpenses:
    """Repeated hotel entries across days should NOT be deduplicated."""

    def test_expense_count(self):
        result = parse_text(JAPAN_PDF_TEXT)
        assert len(result['expenses']) == 9

    def test_expense_total(self):
        result = parse_text(JAPAN_PDF_TEXT)
        total = sum(e['amount'] for e in result['expenses'])
        assert total == pytest.approx(11768.0)

    def test_repeated_hotel_not_deduped(self):
        result = parse_text(JAPAN_PDF_TEXT)
        hotel_expenses = [e for e in result['expenses'] if '芬迪' in e['description'] or '田町' in e['description']]
        assert len(hotel_expenses) == 3

    def test_expense_dates_from_day_headers(self):
        result = parse_text(JAPAN_PDF_TEXT)
        expenses = result['expenses']
        day1_expenses = [e for e in expenses if e['date'] == '2019-04-27']
        assert len(day1_expenses) == 2


class TestJapanPDFDaySplit:
    """Last day chunk should not absorb detail page content."""

    def test_day_count(self):
        result = parse_text(JAPAN_PDF_TEXT)
        all_days = [d for leg in result['legs'] for d in leg['days']]
        assert len(all_days) == 8

    def test_last_day_no_junk_activities(self):
        result = parse_text(JAPAN_PDF_TEXT)
        all_days = [d for leg in result['legs'] for d in leg['days']]
        last_day = max(all_days, key=lambda d: d['day_number'])
        for act in last_day['activities']:
            assert '不要' not in act
            assert '玩扭蛋' not in act


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


class TestJapanPDFCities:
    """PDF declares 4 cities: 东京, 京都, 奈良, 大阪. All must appear as legs."""

    def test_four_city_legs(self):
        result = parse_text(JAPAN_PDF_TEXT)
        cities = [leg['city'] for leg in result['legs']]
        assert '东京' in cities
        assert '京都' in cities
        assert '奈良' in cities
        assert '大阪' in cities

    def test_nara_leg_exists(self):
        result = parse_text(JAPAN_PDF_TEXT)
        nara = _find_leg(result, '奈良')
        assert nara is not None
        assert nara['start_date'] == '2019-05-01'

    def test_travel_day_uses_destination(self):
        """Day 4 (Tokyo→Kyoto) should be classified as Kyoto, Day 5 (Kyoto→Nara) as Nara."""
        result = parse_text(JAPAN_PDF_TEXT)
        kyoto = _find_leg(result, '京都')
        assert kyoto is not None
        assert any(d['day_number'] == 4 for d in kyoto['days'])
        nara = _find_leg(result, '奈良')
        assert any(d['day_number'] == 5 for d in nara['days'])

    def test_return_day_stays_in_departure_city(self):
        """Day 8 (Osaka→HK) should stay classified as Osaka, not Hong Kong."""
        result = parse_text(JAPAN_PDF_TEXT)
        osaka = _find_leg(result, '大阪')
        assert any(d['day_number'] == 8 for d in osaka['days'])


class TestJapanPDFActivities:
    """Activity extraction: no cross-day leakage, English-starting names supported."""

    def test_day3_no_leaked_asakusa(self):
        """Day 3 has only Disney; '浅草寺' is Day 4's first activity, must not leak."""
        result = parse_text(JAPAN_PDF_TEXT)
        day3 = _find_day(result, 3)
        assert '浅草寺' not in day3['activities']
        assert '东京迪士尼度假区' in day3['activities']

    def test_day4_no_leaked_nara(self):
        """Day 4 must not contain '奈良公园' (that belongs to Day 5)."""
        result = parse_text(JAPAN_PDF_TEXT)
        day4 = _find_day(result, 4)
        assert '奈良公园' not in day4['activities']
        assert '浅草寺' in day4['activities']

    def test_day6_has_hep_five(self):
        """Day 6 must include 'Hep Five摩天轮' despite English-starting name."""
        result = parse_text(JAPAN_PDF_TEXT)
        day6 = _find_day(result, 6)
        assert any('Hep' in a or '摩天轮' in a for a in day6['activities'])

    def test_day8_no_leaked_activities(self):
        """Day 8 is departure day — should have no activities."""
        result = parse_text(JAPAN_PDF_TEXT)
        day8 = _find_day(result, 8)
        assert len(day8['activities']) == 0


class TestJapanPDFAccommodation:
    """Accommodation should match PDF data for every day."""

    def test_day1_villa_fontaine(self):
        result = parse_text(JAPAN_PDF_TEXT)
        accom = _find_day(result, 1)['accommodation'] or ''
        assert '田町' in accom or 'Fontaine' in accom or '芬迪' in accom

    def test_day2_villa_fontaine(self):
        result = parse_text(JAPAN_PDF_TEXT)
        accom = _find_day(result, 2)['accommodation'] or ''
        assert '田町' in accom or 'Fontaine' in accom or '芬迪' in accom

    def test_day3_villa_fontaine_not_disney(self):
        result = parse_text(JAPAN_PDF_TEXT)
        accom = _find_day(result, 3)['accommodation'] or ''
        assert 'Disney' not in accom
        assert '田町' in accom or 'Fontaine' in accom or '芬迪' in accom

    def test_day4_getsuchinbaru(self):
        result = parse_text(JAPAN_PDF_TEXT)
        accom = _find_day(result, 4)['accommodation'] or ''
        assert '月沈原' in accom

    def test_day5_sakura(self):
        result = parse_text(JAPAN_PDF_TEXT)
        accom = _find_day(result, 5)['accommodation'] or ''
        assert '樱花' in accom

    def test_day6_osaka_dome(self):
        result = parse_text(JAPAN_PDF_TEXT)
        accom = _find_day(result, 6)['accommodation'] or ''
        assert '大阪' in accom or '无限' in accom

    def test_day7_osaka_dome(self):
        result = parse_text(JAPAN_PDF_TEXT)
        accom = _find_day(result, 7)['accommodation'] or ''
        assert '大阪' in accom or '无限' in accom

    def test_day8_no_accommodation(self):
        result = parse_text(JAPAN_PDF_TEXT)
        accom = _find_day(result, 8)['accommodation']
        assert accom is None


class TestNLUIntentClassification:
    """NLU 分类器应正确识别短句命令的意图。"""

    def test_expense_intent(self):
        assert classify('新增花费：交通100元') == 'add_expense'

    def test_expense_intent_buluq(self):
        assert classify('补录住宿费800块') == 'add_expense'

    def test_change_category_jiang(self):
        assert classify('将月沈原改为住宿') == 'change_category'

    def test_change_category_ba(self):
        assert classify('把月沈原的类别改为住宿') == 'change_category'

    def test_change_category_shi(self):
        assert classify('月沈原是酒店') == 'change_category'

    def test_change_category_shuyv(self):
        assert classify('月沈原属于住宿') == 'change_category'

    def test_set_accommodation_zhuzai(self):
        assert classify('住在樱花酒店') == 'set_accommodation'

    def test_set_accommodation_jiao(self):
        assert classify('酒店叫月沈原') == 'set_accommodation'

    def test_expense_not_accommodation(self):
        assert classify('新增花费：交通100元') != 'change_category'


class TestNLUExpenseExtraction:
    """NLU 费用命令解析。"""

    def test_xinzeng_expense_returns_expense_type(self):
        result = parse_text('新增花费：东京京都新干线+京都奈良大阪JR交通共985*2=1970RMB')
        assert result['type'] == 'expense'

    def test_xinzeng_expense_amount(self):
        result = parse_text('新增花费：东京京都新干线+京都奈良大阪JR交通共985*2=1970RMB')
        assert len(result['expenses']) == 1
        assert result['expenses'][0]['amount'] == 1970.0

    def test_xinzeng_expense_category(self):
        result = parse_text('新增花费：东京京都新干线+京都奈良大阪JR交通共985*2=1970RMB')
        assert result['expenses'][0]['category'] == '交通'

    def test_xinzeng_expense_description_not_command(self):
        result = parse_text('新增花费：东京京都新干线+京都奈良大阪JR交通共985*2=1970RMB')
        desc = result['expenses'][0]['description']
        assert '交通' in desc or '新干线' in desc or 'JR' in desc


class TestNLUChangeCategoryExtraction:
    """NLU change_category 命令的 slot 提取。"""

    def test_x_shi_jiudian_extracts_name(self):
        r = extract_change_category('月沉原是酒店')
        assert r['item_name'] == '月沉原'

    def test_jiang_extracts_name(self):
        r = extract_change_category('将月沈原的类别改为住宿')
        assert r['item_name'] == '月沈原'

    def test_ba_extracts_name(self):
        r = extract_change_category('把月沈原的类别改为住宿')
        assert r['item_name'] == '月沈原'

    def test_parse_text_returns_category_related_type(self):
        result = parse_text('月沉原是酒店')
        assert result['type'] in ('change_category', 'accommodation')

    def test_parse_text_no_wrong_title(self):
        result = parse_text('月沉原是酒店')
        assert result['trip'] is None

    def test_parse_text_empty_legs(self):
        result = parse_text('月沉原是酒店')
        assert result['legs'] == []

    def test_jiang_returns_change_category_type(self):
        result = parse_text('将月沈原的类别改为住宿')
        assert result['type'] == 'change_category'

    def test_jiang_target_category(self):
        result = parse_text('将月沈原的类别改为住宿')
        assert result['target_category'] == '住宿'

    def test_jiang_no_wrong_title(self):
        result = parse_text('将月沈原的类别改为住宿')
        assert result['trip'] is None

    def test_change_to_transport(self):
        result = parse_text('把地接司导的类别改为交通')
        assert result['type'] == 'change_category'
        assert result['item_name'] == '地接司导'
        assert result['target_category'] == '交通'


class TestNLUSetAccommodationExtraction:
    """NLU set_accommodation 命令的 slot 提取。"""

    def test_zhuzai_extracts_name(self):
        r = extract_set_accommodation('住在樱花酒店')
        assert r['accommodation'] == '樱花酒店'

    def test_jiao_extracts_name(self):
        r = extract_set_accommodation('酒店叫月沈原')
        assert '月沈原' in r['accommodation']

    def test_parse_text_type(self):
        result = parse_text('住在樱花酒店')
        assert result['type'] == 'accommodation'


class TestAccommodationBackfillCategory:
    """当"其他"类费用被用于住宿反填时，其 category 应升级为"住宿"。"""

    def test_getsu_expense_category_is_zhushu(self):
        result = parse_text(JAPAN_PDF_TEXT)
        getsu = [e for e in result['expenses'] if '月沈原' in (e.get('description') or '')]
        assert len(getsu) >= 1, '未找到月沈原费用条目'
        for e in getsu:
            assert e['category'] == '住宿', f'月沈原 category 应为住宿，实际为 {e["category"]}'

    def test_getsu_day4_accommodation_still_set(self):
        """升级 category 后 Day 4 的住宿字段不受影响。"""
        result = parse_text(JAPAN_PDF_TEXT)
        day4 = next((d for leg in result['legs'] for d in leg['days'] if d['day_number'] == 4), None)
        assert day4 is not None
        assert '月沈原' in (day4['accommodation'] or '')
