"""越南 8 日 PDF 解析回归测试。

BUG 1: 穷游 PDF 概览表中，Day 6 (02.04) 的「浮潜垂钓一日游」单元格跨行合并，
pdfminer 将该行内容在 Day 7 (02.05) 的标记前重复抽取一次。
导致：
  - Day 7 activities 错误含有「浮潜垂钓一日游」（应为 []）
  - Day 7 accommodation 错误为「新世界富国度假村」（应为「西贡洲际酒店」）

BUG 2: 「西贡新山一国际机场」中的「新山」被误识别为马来西亚城市「新山」（Johor Bahru）。
「新山一」是胡志明市 Tân Sơn Nhất 机场的专有名，不是目的地城市。

使用从真实 PDF 提取的最小化 fixture 文本复现 bug，并验证修复。
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.ai_parser import parse_text, _extract_city_from_chunk

# Minimal fixture extracted from 202502 越南.pdf overview section.
# The key structure that triggers the bug:
#   - "1. 浮潜垂钓一日游" line appears BEFORE both "04 星期二" and "05 星期三"
#     because the PDF table cell is a merged row spanning Day 6 and Day 7.
VIETNAM_OVERVIEW_TEXT = """SexySouL的越南行程
2025年1月30日出发 ｜ 共8天，1个国家，2个城市
作者：SexySouL

成都 20:30 - 23:15  西贡洲际酒店
30
星期四 Chengdu 成都 → 胡志明市  - IHG 旗下饭店，JW Marriott
2025年1月 胡志明市 Ho Chi Minh City Hotel and Suites Saigon

胡志明市 1. 古芝地道 ， Cu Chi Tunnels  西贡洲际酒店

31
星期五 Ho Chi Minh 2. 湄公河三角洲 ， Mekong Delta  - IHG 旗下饭店，JW Marriott
2025年1月 City 3. 胡志明双层巴士   Hotel and Suites Saigon

胡志明市  西贡洲际酒店

01
星期六 Ho Chi Minh  - IHG 旗下饭店，JW Marriott
2025年2月 City   Hotel and Suites Saigon

胡志明市 11:20 - 12:30  富国岛威尼斯酒店
02
星期天 Ho Chi Minh 胡志明市 → 富国岛
2025年2月 City 富国岛 Dao Phu Quoc

富国岛  新世界富国度假村

03
星期一 Dao Phu
2025年2月 Quoc

富国岛  1. 浮潜垂钓一日游 ， One Day Snorkeling &  新世界富国度假村

04 星期二  Dao Phu  Fishing Tour
2025年2月  Quoc

富国岛  1. 浮潜垂钓一日游 ， One Day Snorkeling &  新世界富国度假村

05
星期三 Dao Phu 富国岛 → 胡志明市 西贡洲际酒店 - IHG 旗下饭
2025年2月 Quoc 15:45 - 16:50 店，JW Marriott Hotel and
胡志明市 Ho Chi Minh City Suites Saigon，胡志明市

胡志明市  胡志明市 → 成都  西贡洲际酒店

06
星期四 Ho Chi Minh 08:40 - 13:20 - IHG 旗下饭店，JW Marriott
2025年2月 City Hotel and Suites Saigon

第1天 （总价：¥29427） 单价 数量 总价
成都到胡志明市的交通预算  CNY 3246.00 7 CNY 22722
西贡洲际酒店 - IHG 旗下饭店  CNY 3599.00 1 CNY 3599

第2天 （总价：¥8792） 单价 数量 总价
古芝地道,Cu Chi Tunnels  CNY 3742.00 1 CNY 3742
胡志明双层巴士  CNY 266.00 1 CNY 266
西贡洲际酒店 - IHG 旗下饭店  CNY 3599.00 1 CNY 3599

第3天 （总价：¥8056） 单价 数量 总价
西贡洲际酒店 - IHG 旗下饭店  CNY 3599.00 1 CNY 3599

第4天 （总价：¥9125） 单价 数量 总价
胡志明市到富国岛的交通预算  CNY 907.00 7 CNY 6349
富国岛威尼斯酒店  CNY 2776.00 1 CNY 2776

第5天 （总价：¥4690） 单价 数量 总价
新世界富国度假村  CNY 4690.00 1 CNY 4690

第6天 （总价：¥9094） 单价 数量 总价
浮潜垂钓一日游  CNY 2333.00 1 CNY 2333
新世界富国度假村  CNY 4690.00 1 CNY 4690

第7天 （总价：¥3577） 单价 数量 总价
西贡洲际酒店  CNY 3577.00 1 CNY 3577
"""


def _find_day(result, date_str):
    """在解析结果中查找指定日期的 day 条目。"""
    for leg in result.get("legs", []):
        for day in leg.get("days", []):
            if day.get("date") == date_str:
                return day
    return None


def test_day6_has_snorkeling_activity():
    """Day 6 (2025-02-04, 富国岛) 应包含浮潜垂钓一日游活动。"""
    result = parse_text(VIETNAM_OVERVIEW_TEXT)
    day6 = _find_day(result, "2025-02-04")
    assert day6 is not None, "未找到 Day 6 (2025-02-04)"
    assert "浮潜垂钓一日游" in day6["activities"], (
        f"Day 6 应含浮潜垂钓一日游，实际 activities={day6['activities']}"
    )


def test_day7_has_no_snorkeling_activity():
    """Day 7 (2025-02-05, 返回胡志明市) 不应包含浮潜垂钓一日游。
    
    这是 PDF 合并单元格 bug：pdfminer 将 Day 6 的活动行在 Day 7 标记前重复一次，
    导致 _split_by_day 将其误设为 Day 7 的 pre_attraction_line。
    """
    result = parse_text(VIETNAM_OVERVIEW_TEXT)
    day7 = _find_day(result, "2025-02-05")
    assert day7 is not None, "未找到 Day 7 (2025-02-05)"
    assert "浮潜垂钓一日游" not in day7["activities"], (
        f"Day 7 不应含浮潜垂钓一日游（属于 Day 6），实际 activities={day7['activities']}"
    )


def test_day7_accommodation_is_jw_marriott():
    """Day 7 (2025-02-05) 住宿应为西贡洲际酒店，而非新世界富国度假村。
    
    PDF 合并单元格 bug 同时错误地将「新世界富国度假村」放入 Day 7 的 chunk，
    导致 _extract_accommodation 提取到错误的住宿。
    """
    result = parse_text(VIETNAM_OVERVIEW_TEXT)
    day7 = _find_day(result, "2025-02-05")
    assert day7 is not None, "未找到 Day 7 (2025-02-05)"
    accom = day7.get("accommodation", "")
    assert accom and "西贡洲际酒店" in accom, (
        f"Day 7 住宿应含「西贡洲际酒店」，实际 accommodation={accom!r}"
    )
    assert "新世界富国度假村" not in (accom or ""), (
        f"Day 7 住宿不应为「新世界富国度假村」，实际 accommodation={accom!r}"
    )


class TestReturnCityMergedIntoOneLeg:
    """Bug 3: 返程回到出发城市时应与首程腿合并，不应产生重复城市腿。

    越南 8 日行程：胡志明市（Day 1-3）→ 富国岛（Day 4-6）→ 胡志明市（Day 7-8 返程）。
    解析结果应只有两个腿：胡志明市（Day 1-3-7-8）和富国岛（Day 4-6），
    而不是三个腿（胡志明市/富国岛/胡志明市）或两个胡志明市腿。
    """

    def test_only_one_hcm_leg(self):
        """解析结果里胡志明市腿数量应为 1，不允许出现两个胡志明市腿。"""
        result = parse_text(VIETNAM_OVERVIEW_TEXT)
        hcm_legs = [leg for leg in result["legs"] if leg["city"] == "胡志明市"]
        assert len(hcm_legs) == 1, (
            f"应只有 1 个胡志明市腿，实际有 {len(hcm_legs)} 个：\n"
            + "\n".join(
                f"  order={l['order_index']} days={[d['day_number'] for d in l['days']]}"
                for l in hcm_legs
            )
        )

    def test_hcm_leg_contains_all_hcm_days(self):
        """胡志明市腿应包含 Day 1-3 和返程 Day 7-8，共 5 天。"""
        result = parse_text(VIETNAM_OVERVIEW_TEXT)
        hcm_legs = [leg for leg in result["legs"] if leg["city"] == "胡志明市"]
        assert len(hcm_legs) == 1
        day_nums = sorted(d["day_number"] for d in hcm_legs[0]["days"])
        assert day_nums == [1, 2, 3, 7, 8], (
            f"胡志明市腿应含 Day 1,2,3,7,8，实际 days={day_nums}"
        )

    def test_total_leg_count_is_two(self):
        """总腿数应为 2（胡志明市 + 富国岛），不多不少。"""
        result = parse_text(VIETNAM_OVERVIEW_TEXT)
        assert len(result["legs"]) == 2, (
            f"总腿数应为 2，实际 {len(result['legs'])}："
            f" {[l['city'] for l in result['legs']]}"
        )

    def test_no_duplicate_city_legs(self):
        """解析结果中不应出现重复城市腿（任意行程中）。"""
        result = parse_text(VIETNAM_OVERVIEW_TEXT)
        cities = [leg["city"] for leg in result["legs"]]
        assert len(cities) == len(set(cities)), (
            f"解析结果含重复城市腿: {cities}"
        )


class TestCityNotFromAirportName:
    """Bug 2: 机场专有名中的子串不应被误识别为目的地城市。

    「西贡新山一国际机场」中的「新山」是 Tân Sơn Nhất 机场名的组成部分，
    而非马来西亚城市新山（Johor Bahru）。机场名后跟「一/二/数字」是识别机场专有名的标志。
    """

    def test_xinshan_not_in_airport_name_chunk(self):
        """含「西贡新山一国际机场」的 chunk 不应识别出城市「新山」。"""
        chunk = "成都天府机场T1  20:30-西贡新山一国际机场  23:15\nJWMarriottHotel&SuitesSaigon"
        city = _extract_city_from_chunk(chunk)
        assert city != "新山", (
            f"chunk 中「新山一」是机场名（Tân Sơn Nhất），不是城市新山（Johor Bahru），"
            f"但 _extract_city_from_chunk 返回了 {city!r}"
        )

    def test_standalone_xinshan_still_matches(self):
        """独立出现的「新山」仍应被正确识别（实际去新山的行程）。"""
        chunk = "2025年1月 新山 入住新山酒店"
        city = _extract_city_from_chunk(chunk)
        assert city == "新山", (
            f"独立的「新山」应被识别为城市，但返回了 {city!r}"
        )
