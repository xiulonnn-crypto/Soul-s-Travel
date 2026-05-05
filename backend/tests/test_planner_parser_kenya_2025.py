"""PiTravel-poster (PNG) parser tests for the 2025-05 Kenya itinerary.

These tests cover days where the OCR rows ONLY contain airport / hotel names
WITHOUT any standalone city literal. _infer_city used to fall back to
'[待确认]' for these days; now an airport→city table provides the mapping.

OCR fixtures below are LITERAL strings as produced by image_extractor on
/Users/soul/Downloads/202505肯尼亚.pdf cover poster (PNG variant).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.planner_parser import parse_planner_text


# ---------------------------------------------------------------------------
# Fixture: literal OCR output for the Kenya PNG (verbatim, captured 2026-05)
# ---------------------------------------------------------------------------

KENYA_11DAY_OCR = """PITRAVEL  ITINERUFOY
肯尼亚10日游
SouL的05.01至05.1111天10晚行程单
05.01/四
哈马德国际机场  北京大兴国际机场  06:55  01:45
哈马德国际机场  乔莫·肯雅塔国际机场  23:50  18:30
SwissLenana MountHotel
05.02/五
Swiss Lenana Mount Hotel
Keekorok  威尔逊机场  08-60
10:15
JW Marriott Masai Mara Lodge
05.03/六
JW Marriott Masai Mara Lodge
马赛马拉
05.04/周日
JWMarriott Masai MaraLodge
05.05/-
JW Marriott Masai Mara Lodge
05.06/二
JW Marriott Masai Mara Lodge
05.07/三
JW Marriott Masai Mara Lodge
Keekorok  威尔逊机场  16:45  16:00
Swiss Lenana MountHotel
05.08/四
BurahaZenonl Hotel & Resort
05.09/周五
Swiss Lenana Mount Hotel
05.10/周六
哈马德国际机场  乔莫·肯雅塔国际机场  23:25  18:10
05.11/日
哈马德国际机场  北京大兴国际机场  01:45  14:40
"""

DAY1_ONLY_OCR = """肯尼亚10日游
SouL的05.01至05.0111天10晚行程单
05.01/四
哈马德国际机场  北京大兴国际机场  06:55  01:45
哈马德国际机场  乔莫·肯雅塔国际机场  23:50  18:30
SwissLenana MountHotel
"""

DAY11_ONLY_OCR = """肯尼亚10日游
SouL的05.11至05.1111天10晚行程单
05.11/日
哈马德国际机场  北京大兴国际机场  01:45  14:40
"""


def _all_days(result):
    return [d for leg in result.get('legs', []) for d in leg['days']]


def _city_of_day(result, target_date):
    for leg in result.get('legs', []):
        for d in leg['days']:
            if d.get('date') == target_date:
                return leg.get('city')
    return None


# ---------------------------------------------------------------------------
# RED tests: today these all fail with city='[待确认]' or wrong-leg assignment
# ---------------------------------------------------------------------------


def test_day1_arrival_city_is_nairobi():
    """Day 1 PNG only has 北京/哈马德/乔莫·肯雅塔 airport names + Swiss
    Lenana hotel. The arrival airport is 乔莫·肯雅塔 (内罗毕). City must
    resolve to '内罗毕', NOT '[待确认]'."""
    result = parse_planner_text(DAY1_ONLY_OCR)
    city = _city_of_day(result, '2025-05-01') or _city_of_day(result, '2026-05-01')
    assert city == '内罗毕', f"Day 1 city 期望 '内罗毕'，实际 {city!r}"


def test_day11_arrival_city_is_beijing():
    """Day 11 PNG only has 哈马德 + 北京大兴 airports. Arrival = 北京. City
    must resolve to '北京', NOT carry over the previous leg's city."""
    result = parse_planner_text(DAY11_ONLY_OCR)
    all_days = _all_days(result)
    assert all_days, "Day 11 OCR must produce at least one day"
    last = all_days[-1]
    city = None
    for leg in result['legs']:
        if last in leg['days']:
            city = leg['city']
            break
    assert city == '北京', f"Day 11 city 期望 '北京'，实际 {city!r}"


def test_beijing_country_is_china():
    """When 北京 is the resolved city, country lookup must return '中国'
    rather than the '[待确认]' fallback. Country mapping completeness."""
    result = parse_planner_text(DAY11_ONLY_OCR)
    last_leg = result['legs'][-1]
    if last_leg['city'] == '北京':
        assert last_leg['country'] == '中国', (
            f"北京 country 期望 '中国'，实际 {last_leg['country']!r}"
        )


def test_kenya_full_ocr_no_pending_leg():
    """Full 11-day Kenya OCR must produce zero leg with city='[待确认]'.
    Every day's OCR rows contain at least an airport name; the airport→city
    map must cover every airport present in real Kenya/PRC PNG itineraries."""
    result = parse_planner_text(KENYA_11DAY_OCR)
    pending_legs = [L for L in result['legs'] if L['city'] == '[待确认]']
    assert not pending_legs, (
        f"完整肯尼亚 PNG 不应有 [待确认] leg，实际命中 {len(pending_legs)} 条："
        f"{[(L['city'], [d['date'] for d in L['days']]) for L in pending_legs]}"
    )


def test_kenya_day1_lands_in_nairobi_not_pending():
    """End-to-end: in the FULL OCR, Day 1 must end up in a leg whose city
    equals '内罗毕' — not '[待确认]', not '马赛马拉国家保护区'."""
    result = parse_planner_text(KENYA_11DAY_OCR)
    city = _city_of_day(result, '2025-05-01') or _city_of_day(result, '2026-05-01')
    assert city == '内罗毕', f"Day 1 leg city 期望 '内罗毕'，实际 {city!r}"


def test_kenya_day11_lands_in_beijing_not_carryover():
    """End-to-end: Day 11's leg city must be '北京' (arrival airport),
    not carried over from Day 10's leg."""
    result = parse_planner_text(KENYA_11DAY_OCR)
    city = _city_of_day(result, '2025-05-11') or _city_of_day(result, '2026-05-11')
    assert city == '北京', f"Day 11 leg city 期望 '北京'，实际 {city!r}"


def test_kenya_day10_no_longer_carries_over_mara():
    """Day 10 OCR row "哈马德国际机场  乔莫·肯雅塔国际机场  23:25  18:10" 来自
    PNG 排版被 OCR 重排后的两机场拼接（PiTravel 海报每段单机场+时间，OCR 把
    相邻段合并），列序倒错使最后位置的机场是出发地"乔莫·肯雅塔"而非落地"哈马德"。
    本测试只断言不再 carry-over 到马赛马拉/[待确认]，接受 city='内罗毕'（出发地）
    或 '多哈'（落地）任一；OCR 列序校正属于独立的下游修复方向。"""
    result = parse_planner_text(KENYA_11DAY_OCR)
    city = _city_of_day(result, '2025-05-10') or _city_of_day(result, '2026-05-10')
    assert city in ('多哈', '内罗毕'), (
        f"Day 10 city 期望 '多哈' 或 '内罗毕'，实际 {city!r} "
        "（不应仍是马赛马拉国家保护区或 [待确认]）"
    )
