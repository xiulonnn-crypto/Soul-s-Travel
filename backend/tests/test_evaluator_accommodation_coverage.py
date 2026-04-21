"""住宿覆盖率：返程日 / 过夜航班日不应计入分母。

用户反馈：Trip 7（5 天韩国行）Day 5 是返程日（transport=['釜山→北京']，无住宿），
被当成「缺失住宿」而拉低分数。两类情形其实无需住宿记录：
  1. 行程最后一天含跨城大交通（返程日）
  2. 任一日含跨城大交通且无住宿（过夜/通宵航班）
判定标准：交通日 + 无住宿 → 视为在途过夜，不纳入覆盖率分母。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import (
    _compute_accommodation_metrics,
    _generate_accommodation_text,
)


def test_return_flight_last_day_excluded_from_denominator():
    """Trip 7 真实场景复现：最后一天 transport=['釜山→北京'] + accommodation=None。"""
    legs = [
        {
            "city": "釜山",
            "country": "韩国",
            "days": [
                {"accommodation": "釜山万枫酒店", "transport": ["CA729:北京→釜山"], "activities": []},
                {"accommodation": "釜山万枫酒店", "transport": [], "activities": []},
                {"accommodation": "釜山朝鲜威斯汀酒店", "transport": [], "activities": []},
                {"accommodation": "釜山万枫酒店", "transport": [], "activities": []},
                {"accommodation": None, "transport": ["釜山→北京"], "activities": []},
            ],
        }
    ]
    m = _compute_accommodation_metrics(legs, [], {})
    assert m["coverage"] == 100, (
        f"返程日（最后一天 + 跨城交通 + 无住宿）应排除分母，预期 100%，实际 {m['coverage']}%"
    )


def test_overnight_midnight_flight_day_excluded():
    """真实数据里存在的凌晨航班格式：'广州→曼谷 FD531 00:10'，当晚在飞机上过夜。"""
    legs = [
        {
            "city": "广州",
            "country": "中国",
            "days": [
                {"accommodation": "广州酒店", "transport": [], "activities": ["沙面"]},
                {"accommodation": None, "transport": ["广州→曼谷 FD531 00:10"], "activities": []},
            ],
        },
        {
            "city": "曼谷",
            "country": "泰国",
            "days": [
                {"accommodation": "曼谷酒店", "transport": [], "activities": ["大皇宫"]},
            ],
        },
    ]
    m = _compute_accommodation_metrics(legs, [], {})
    assert m["coverage"] == 100, (
        f"过夜航班日（跨城 + 无住宿）应排除分母，预期 100%，实际 {m['coverage']}%"
    )


def test_non_transit_day_missing_accommodation_still_penalized():
    """非交通日忘填住宿是真正的数据缺失，应继续计入分母。"""
    legs = [
        {
            "city": "成都",
            "country": "中国",
            "days": [
                {"accommodation": "成都酒店", "transport": [], "activities": ["宽窄巷子"]},
                {"accommodation": None, "transport": [], "activities": ["锦里"]},
            ],
        }
    ]
    m = _compute_accommodation_metrics(legs, [], {})
    assert m["coverage"] == 50, (
        f"非交通日无住宿 = 真数据缺失，应保留惩罚，预期 50%，实际 {m['coverage']}%"
    )


def test_transit_day_with_accommodation_still_counted():
    """含大交通但同时记录了住宿（例如中午到达入住酒店），应正常计数。"""
    legs = [
        {
            "city": "东京",
            "country": "日本",
            "days": [
                {"accommodation": "东京酒店", "transport": ["NH955:北京→东京"], "activities": ["浅草寺"]},
                {"accommodation": "东京酒店", "transport": [], "activities": ["银座"]},
            ],
        }
    ]
    m = _compute_accommodation_metrics(legs, [], {})
    assert m["coverage"] == 100


def test_last_day_with_hotel_still_counted():
    """最后一天虽有返程大交通，但记录了住宿（白天飞行前入住）→ 正常计数。"""
    legs = [
        {
            "city": "东京",
            "country": "日本",
            "days": [
                {"accommodation": "东京酒店", "transport": [], "activities": ["浅草寺"]},
                {"accommodation": "机场快捷酒店", "transport": ["东京→北京 MU231 19:00"], "activities": []},
            ],
        }
    ]
    m = _compute_accommodation_metrics(legs, [], {})
    assert m["coverage"] == 100


def test_all_days_transit_no_accommodation_does_not_divide_by_zero():
    """纯过境行程（全部是交通日且无住宿）不应因除零崩溃，视为 100% 覆盖。"""
    legs = [
        {
            "city": "中转",
            "country": "",
            "days": [
                {"accommodation": None, "transport": ["北京→东京"], "activities": []},
                {"accommodation": None, "transport": ["东京→首尔"], "activities": []},
            ],
        }
    ]
    m = _compute_accommodation_metrics(legs, [], {})
    assert m["coverage"] == 100
    assert m["score"] >= 0  # 不崩溃


def test_trip7_accommodation_text_is_complete_after_fix():
    """Trip 7 修复后：coverage=100 应触发'住宿记录完整'文案，不再是'大部分天数有住宿记录'。"""
    legs = [
        {
            "city": "釜山",
            "country": "韩国",
            "days": [
                {"accommodation": "A酒店", "transport": ["CA729:北京→釜山"], "activities": []},
                {"accommodation": "A酒店", "transport": [], "activities": []},
                {"accommodation": "B酒店", "transport": [], "activities": []},
                {"accommodation": "A酒店", "transport": [], "activities": []},
                {"accommodation": None, "transport": ["釜山→北京"], "activities": []},
            ],
        }
    ]
    m = _compute_accommodation_metrics(legs, [], {})
    text = _generate_accommodation_text(m)
    assert "住宿记录完整" in text, f"预期文案包含'住宿记录完整'，实际：{text}"
    assert "大部分天数" not in text
