"""PiTravel-style planner parser tests.

Inputs are literal multi-line strings that mirror the real rapidocr output
observed on /Users/soul/Downloads/IMG_4800.JPG. The extractor outputs one
visual row per line and rapidocr emits day headers in SIX observed variants
from this single document (due to font/weakness), so every variant must stay
green; regressing any one silently drops a day from the split.

Observed header variants in the sample (all from one extractor, one doc):
  '09.29/周日', '09.30/周-', '10.01/周二', '10.04/月五', '10.07/-', and
  canonical '10.05/周六'. The parser must NOT require a valid weekday char.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime

import pytest

from services.planner_parser import parse_planner_text


# ---------------------------------------------------------------------------
# Fixture: literal OCR output from the real IMG_4800.JPG (verbatim)
# ---------------------------------------------------------------------------

UK_9DAY_OCR = """PI TFAVEL  ITINERARY
英国9日游
SouL的09.29至10.079天8晚行程单
09.29/周日
四号航站楼
伦敦帕丁顿车站
伦敦摄政公园万豪酒店
大英博物馆
OPSO
摄政公园
伦敦摄政公园万豪酒店
09.30/周-
伦敦摄政公园万豪酒店
Madame Tussauds London
Baker Street
Victoriaand Albert Museum
自然史博物馆
科学博物馆
伦敦摄政公园万豪酒店
10.01/周二
伦敦摄政公园万豪酒店
圣保罗座堂
伦敦大火纪念碑
伦敦塔桥
伦敦塔
Westminster Abbey
珠宝塔
大本钟
伦敦眼
伦敦摄政公园万豪酒店
10.02/周三
伦敦摄政公园万豪酒店
海德公园
白金汉宫
Westminster Pier
Greenwich Pier
格林威治天文台
Golden Chippy
卡蒂萨克号
旧皇家海军学院
Putney Pier
London Bridge City Pier
碎片大厦
伦敦摄政公园万豪酒店
10.03/周四
伦敦摄政公园万豪酒店
National express stop, Liverpool street
斯坦斯特德机场  11:30
爱丁堡机场  12:50
爱丁堡城堡
Makars Mash Bar
万豪爱丁堡官邸酒店
10.04/月五
万豪爱丁堡官邸酒店
The Balmoral
Luss View Point
洛蒙德湖
格伦科
三姐妹山停车场
威廉堡
格伦芬南
10.05/周六
波特里
Old Man of Storr
Kilt Rock & Mealt Falls Viewpoint
Public Parking
内斯湖
10.06/周日
苏格兰高地
皮特洛赫里
圣安德鲁斯
福斯桥
Moxy Edinburgh Airport
10.07/-
爱丁堡机场  06:00
卢顿机场  07:20
Heathrow Airport  14:05
北京大兴国际机场  08:35
"""


# ---------------------------------------------------------------------------
# End-to-end shape + leaf-value assertions
# ---------------------------------------------------------------------------


def test_parses_uk_9day_full_shape():
    """Full end-to-end: title, date range, legs, accommodation, 9 days total."""
    result = parse_planner_text(UK_9DAY_OCR)

    assert result['type'] == 'trip'
    assert result['expenses'] == []

    trip = result['trip']
    assert trip['title'] == '英国9日游'
    assert trip['status'] == 'completed'
    assert trip['traveler_count'] == 1

    cur_year = datetime.now().year
    assert trip['start_date'] == f'{cur_year}-09-29'
    assert trip['end_date'] == f'{cur_year}-10-07'

    legs = result['legs']
    # Day 9 (10.07) OCR 含"北京大兴国际机场"，按机场→城市映射归属"北京 leg"
    # （回程落地）；与 Kenya Day 11 同语义。原测试假设 2 legs（回程并入爱丁堡）
    # 已经废弃，新行为下回程落地国/城市单成 leg 更精确反映用户行程。
    assert len(legs) == 3, f'expected 3 legs (伦敦 → 爱丁堡 → 北京), got {len(legs)}'
    london, edinburgh, beijing = legs

    assert london['city'] == '伦敦'
    assert london['country'] == '英国'
    assert london['start_date'] == f'{cur_year}-09-29'
    assert london['end_date'] == f'{cur_year}-10-02'
    assert len(london['days']) == 4

    assert edinburgh['city'] == '爱丁堡'
    assert edinburgh['country'] == '英国'
    assert edinburgh['start_date'] == f'{cur_year}-10-03'
    assert edinburgh['end_date'] == f'{cur_year}-10-06'
    assert len(edinburgh['days']) == 4

    assert beijing['city'] == '北京'
    assert beijing['country'] == '中国'
    assert beijing['start_date'] == f'{cur_year}-10-07'
    assert beijing['end_date'] == f'{cur_year}-10-07'
    assert len(beijing['days']) == 1

    # 完整性审计：所有日子加起来应等于 9 天，覆盖 09.29 到 10.07
    total_days = sum(len(leg['days']) for leg in legs)
    assert total_days == 9, f'expected 9 days total, got {total_days}'


def test_day1_activities_and_accommodation_leaf_values():
    """Leaf-level assertions on day 1's content (assert to the leaf, not just shape)."""
    result = parse_planner_text(UK_9DAY_OCR)
    day1 = result['legs'][0]['days'][0]

    assert day1['day_number'] == 1
    assert day1['date'] == f'{datetime.now().year}-09-29'
    assert day1['accommodation'] == '伦敦摄政公园万豪酒店'
    # 关键景点必须出现在 activities 中（无论顺序）
    assert '大英博物馆' in day1['activities']
    assert '伦敦帕丁顿车站' in day1['activities']
    assert '摄政公园' in day1['activities']
    # 酒店行不得出现在 activities 中
    assert not any('酒店' in a for a in day1['activities']), (
        f"酒店行不应在 activities 中，实际 activities={day1['activities']}"
    )
    assert day1['transport'] == []


def test_transition_day_picks_destination_city():
    """Day 10.03 crosses 伦敦 → 爱丁堡. City must resolve to 爱丁堡 (destination),
    not 伦敦 (origin). This is the discriminating case for the "last-mentioned
    DEST_CITY wins" heuristic."""
    result = parse_planner_text(UK_9DAY_OCR)
    edinburgh_days = result['legs'][1]['days']
    transition = edinburgh_days[0]
    assert transition['date'] == f'{datetime.now().year}-10-03'
    assert transition['accommodation'] == '万豪爱丁堡官邸酒店'
    assert '爱丁堡城堡' in transition['activities']
    # 机场行必须进 transport，不得进 activities
    assert any('斯坦斯特德机场' in t for t in transition['transport']), (
        f"斯坦斯特德机场 应在 transport 中，实际 transport={transition['transport']}"
    )
    assert not any('斯坦斯特德机场' in a for a in transition['activities']), (
        f"斯坦斯特德机场 不应在 activities 中，实际 activities={transition['activities']}"
    )
    # 酒店行不得进 activities
    assert not any('酒店' in a for a in transition['activities']), (
        f"酒店行不应在 activities 中，实际 activities={transition['activities']}"
    )


def test_day_with_no_dest_city_inherits_previous():
    """Day 10.05 contains 波特里 / 内斯湖 / Old Man of Storr — none are in
    DEST_CITIES. The day must inherit 爱丁堡 from the previous day, not fall
    back to '[待确认]'. (Tiered-fallback rule: every tier must return a valid leg.)"""
    result = parse_planner_text(UK_9DAY_OCR)
    # Day 10.05 is day_number 7 in the 爱丁堡 leg (index 2)
    day_oct5 = [d for leg in result['legs'] for d in leg['days'] if d['date'].endswith('-10-05')][0]
    # 它应该被归到爱丁堡 leg 里
    edinburgh = [leg for leg in result['legs'] if leg['city'] == '爱丁堡'][0]
    assert day_oct5 in edinburgh['days']


# ---------------------------------------------------------------------------
# Day-header variant coverage (extractor emits multiple forms per document)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('header', [
    '09.29/周日',   # canonical full weekday
    '09.30/周-',    # OCR weakness: 一 misread as '-'
    '10.01/周二',   # canonical
    '10.04/月五',   # OCR weakness: 周 misread as 月
    '10.07/-',      # OCR dropped '周' and weekday entirely
    '09.29/日',     # short form (single-char weekday)
    '09.29',        # weekday omitted completely
])
def test_day_header_variants_all_parse(header):
    """All six observed + one minimal header variant must split to a day."""
    text = f"""测试9日游
{header}
某景点
10.10/周三
下一天景点
"""
    result = parse_planner_text(text)
    assert len(result['legs']) >= 1
    total_days = sum(len(leg['days']) for leg in result['legs'])
    assert total_days == 2, f'header {header!r} must produce exactly 2 days, got {total_days}'


# ---------------------------------------------------------------------------
# Year-boundary edge case
# ---------------------------------------------------------------------------


def test_year_rollover_when_end_month_less_than_start_month():
    """12.28 -> 01.03 should span the new year; end_date year must be start+1."""
    text = """跨年3日游
By me, from 12.28 至 01.03
12.28/周六
跨年夜景点
12.31/周二
元旦景点
01.03/周五
回家
"""
    result = parse_planner_text(text)
    cur = datetime.now().year
    assert result['trip']['start_date'] == f'{cur}-12-28'
    assert result['trip']['end_date'] == f'{cur + 1}-01-03'


# ---------------------------------------------------------------------------
# context_year: caller-provided year wins over datetime.now()
# ---------------------------------------------------------------------------


def test_context_year_overrides_current_year():
    """When caller passes context_year (e.g. from an already-parsed PDF on the
    same edit page), planner must use THAT year, not datetime.now().year. This
    is the "PDF 先传、JPG 后覆盖" workflow's natural year-carry."""
    result = parse_planner_text(UK_9DAY_OCR, context_year=2024)
    assert result['trip']['start_date'] == '2024-09-29'
    assert result['trip']['end_date'] == '2024-10-07'
    # Per-leg dates must inherit the same year
    assert result['legs'][0]['start_date'] == '2024-09-29'
    # 末段回程 leg（北京）的 end_date 即整段 end_date
    assert result['legs'][-1]['end_date'] == '2024-10-07'
    # Per-day dates must inherit the same year (assert to leaf)
    all_days = [d for leg in result['legs'] for d in leg['days']]
    for day in all_days:
        assert day['date'].startswith('2024-'), f'day {day["date"]} should be in 2024'


def test_context_year_absent_falls_back_to_current_year():
    """No context_year passed → use datetime.now().year (existing behavior)."""
    result = parse_planner_text(UK_9DAY_OCR)  # no context_year kwarg
    cur = datetime.now().year
    assert result['trip']['start_date'] == f'{cur}-09-29'
    assert result['trip']['end_date'] == f'{cur}-10-07'


def test_context_year_none_falls_back_to_current_year():
    """Explicit context_year=None is treated identically to omitted arg."""
    result = parse_planner_text(UK_9DAY_OCR, context_year=None)
    cur = datetime.now().year
    assert result['trip']['start_date'] == f'{cur}-09-29'


def test_context_year_with_cross_year_rollover():
    """context_year applies to START; end still rolls to start+1 when month decreases."""
    text = """跨年3日游
12.28/周六
跨年夜景点
12.31/周二
元旦景点
01.03/周五
回家
"""
    result = parse_planner_text(text, context_year=2024)
    assert result['trip']['start_date'] == '2024-12-28'
    assert result['trip']['end_date'] == '2025-01-03'


# ---------------------------------------------------------------------------
# Empty / malformed inputs
# ---------------------------------------------------------------------------


def test_empty_text_raises():
    with pytest.raises(ValueError):
        parse_planner_text('')


def test_no_day_headers_raises():
    with pytest.raises(ValueError):
        parse_planner_text('这是一段没有日期头的文字\n仅有几行文本')


# ---------------------------------------------------------------------------
# 机场行 → transport；酒店行 → accommodation only，不进 activities
# ---------------------------------------------------------------------------

VIETNAM_PITRAVEL_OCR = """越南8日游
01.30/周四
成都天府机场T1 20:30
西贡新山一国际机场 23:15
JW Marriott Hotel & Suites Saigon
02.05/周三
New World Phu Quoc Resort
富国国际机场 15:45
西贡新山一国际机场 16:50
JW Marriott Hotel & Suites Saigon
Hotel Tower
02.06/周四
JW Marriott Hotel & Suites Saigon
西贡新山一国际机场 08:40
成都天府机场T1 13:20
"""


def test_airport_lines_go_to_transport_not_activities():
    """机场行（含「机场」）必须进 transport，不得进 activities。"""
    result = parse_planner_text(VIETNAM_PITRAVEL_OCR)
    all_days = [d for leg in result['legs'] for d in leg['days']]
    for day in all_days:
        for act in day['activities']:
            assert '机场' not in act, (
                f"Day {day['day_number']} activities 不应含机场行，实际 activities={day['activities']}"
            )
        # 有机场行的天，transport 不能为空
        date = day.get('date', '')
        if date.endswith('-01-30') or date.endswith('-02-05') or date.endswith('-02-06'):
            assert len(day['transport']) > 0, (
                f"Day {day['day_number']} ({date}) 应含机场行在 transport，实际 transport={day['transport']}"
            )


def test_hotel_lines_not_in_activities():
    """酒店行（含 Hotel/Resort/酒店 等）必须不出现在 activities 中。"""
    result = parse_planner_text(VIETNAM_PITRAVEL_OCR)
    all_days = [d for leg in result['legs'] for d in leg['days']]
    for day in all_days:
        for act in day['activities']:
            assert 'Hotel' not in act and 'Resort' not in act and '酒店' not in act, (
                f"Day {day['day_number']} activities 不应含酒店行，实际 activities={day['activities']}"
            )


def test_travel_day_accommodation_set_from_last_hotel():
    """含多个酒店行的出行日，accommodation 取最后一个酒店（当晚入住）。"""
    result = parse_planner_text(VIETNAM_PITRAVEL_OCR)
    all_days = [d for leg in result['legs'] for d in leg['days']]
    day7 = next((d for d in all_days if (d.get('date') or '').endswith('-02-05')), None)
    assert day7 is not None, '未找到 02-05 当天'
    assert day7['accommodation'] is not None, '02-05 的 accommodation 不应为空'
    assert 'Hotel' in day7['accommodation'] or '酒店' in day7['accommodation'], (
        f"accommodation 应为酒店，实际 accommodation={day7['accommodation']!r}"
    )


# ---------------------------------------------------------------------------
# PiTravel 品牌水印不应出现在 activities；相邻机场行合并为航班段
# ---------------------------------------------------------------------------

VIETNAM_LAST_DAY_OCR = """越南8日游
01.30/周四
成都天府机场T1 20:30
西贡新山一国际机场 23:15
JW Marriott Hotel & Suites Saigon
02.06/周四
JW Marriott Hotel & Suites Saigon
西贡新山一国际机场 08:40
成都天府机场T1 13:20
园周旅迹
时间、自由和有用的经验
"""

VIETNAM_LAST_DAY_OCR_OCR_VARIANT = """越南8日游
02.06/周四
西贡新山一国际机场 08:40
成都天府机场T1 13:20
JW Marriott Hotel & Suites Saigon
园周旅迹
时问、自由和有用的经验
"""


def test_pitravel_branding_not_in_activities():
    """圆周旅迹 App 水印行（「园周旅迹」「时间/时问、自由和有用的经验」）不应出现在 activities。"""
    for text in [VIETNAM_LAST_DAY_OCR, VIETNAM_LAST_DAY_OCR_OCR_VARIANT]:
        result = parse_planner_text(text)
        all_days = [d for leg in result['legs'] for d in leg['days']]
        for day in all_days:
            for act in day['activities']:
                assert '旅迹' not in act, (
                    f"品牌水印「旅迹」不应在 activities 中，实际 activities={day['activities']}"
                )
                assert '自由和有用的经验' not in act, (
                    f"品牌水印「自由和有用的经验」不应在 activities 中，实际 activities={day['activities']}"
                )


def test_flight_airports_paired_in_transport():
    """相邻机场行应合并为「出发机场 出发时间-到达机场 到达时间」单条航班段。"""
    result = parse_planner_text(VIETNAM_LAST_DAY_OCR)
    all_days = [d for leg in result['legs'] for d in leg['days']]

    # Day 1 (01.30): 成都→胡志明
    day1 = all_days[0]
    assert len(day1['transport']) == 1, (
        f"Day 1 应有 1 条航班段（两机场合并），实际 transport={day1['transport']}"
    )
    assert '成都天府机场T1 20:30' in day1['transport'][0], (
        f"Day 1 transport 应含出发机场，实际={day1['transport']}"
    )
    assert '西贡新山一国际机场 23:15' in day1['transport'][0], (
        f"Day 1 transport 应含到达机场，实际={day1['transport']}"
    )

    # Day 2 (02.06): 胡志明→成都
    day2 = next((d for d in all_days if (d.get('date') or '').endswith('-02-06')), None)
    assert day2 is not None
    assert len(day2['transport']) == 1, (
        f"Day 2 应有 1 条航班段（两机场合并），实际 transport={day2['transport']}"
    )
    assert '西贡新山一国际机场 08:40' in day2['transport'][0]
    assert '成都天府机场T1 13:20' in day2['transport'][0]


# ---------------------------------------------------------------------------
# Shape compliance: every day dict must have every expected key (assert-to-leaf)
# ---------------------------------------------------------------------------


def test_day_dict_shape_matches_parse_text():
    """Every day entry must carry the exact keys parse_text() emits — the
    frontend TripForm / TripEditor.applyAction depend on this shape. A missing
    key silently breaks rendering with no exception."""
    result = parse_planner_text(UK_9DAY_OCR)
    expected_keys = {
        'day_number', 'date', 'description', 'highlights',
        'activities', 'transport', 'accommodation',
    }
    for leg in result['legs']:
        for day in leg['days']:
            assert set(day.keys()) == expected_keys, \
                f'day {day.get("day_number")} keys {set(day.keys())} != {expected_keys}'

    for leg in result['legs']:
        assert set(leg.keys()) >= {
            'order_index', 'city', 'country', 'start_date', 'end_date', 'days',
        }

    assert set(result['trip'].keys()) >= {
        'title', 'start_date', 'end_date', 'traveler_count', 'description', 'status',
    }
