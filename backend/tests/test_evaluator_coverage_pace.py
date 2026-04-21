"""景点覆盖与行程节奏评分（停留天数、交通日、城市密度）"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import (
    _compute_attractions_metrics,
    _compute_pace_metrics,
    _is_transit_day,
)


def test_is_transit_day_detects_arrow_route():
    """→ 箭头格式是实际数据的主要格式（之前漏判的真实 bug）。"""
    for transport_str in ["东京→京都", "广州→曼谷 FD531 00:10", "AK6304:吉隆坡→兰卡威"]:
        day = {"transport": [transport_str], "activities": []}
        assert _is_transit_day(day) is True, f"应识别为交通日: {transport_str!r}"


def test_is_transit_day_detects_keyword_route():
    """含关键词（航班/高铁）的条目即使无箭头也应识别。"""
    day = {"transport": ["高铁 G1234", "航班 MU231 19:00"], "activities": []}
    assert _is_transit_day(day) is True


def test_is_transit_day_false_for_empty():
    day = {"transport": [], "activities": ["浅草寺"]}
    assert _is_transit_day(day) is False


def test_attractions_short_stay_boosts_adjusted_coverage():
    """停留短于典型天数时，调整后期望覆盖率应高于原始覆盖率。"""
    benchmarks = {
        "测试城": {
            "must_see": ["A", "B", "C", "D"],
            "typical_stay_days": 4,
        }
    }
    legs = [
        {
            "city": "测试城",
            "days": [
                {"activities": ["A", "B"], "transport": []},
                {"activities": [], "transport": []},
            ],
        }
    ]
    m = _compute_attractions_metrics(legs, benchmarks)
    c = m["cities"][0]
    assert c["raw_coverage_pct"] == 50
    assert c["coverage_pct"] > c["raw_coverage_pct"]
    assert m["overall_coverage"] > m["raw_overall_coverage"]


def test_attractions_transit_reduces_effective_days():
    benchmarks = {
        "测试城": {
            "must_see": ["A", "B", "C", "D"],
            "typical_stay_days": 2,
        }
    }
    legs = [
        {
            "city": "测试城",
            "days": [
                {"activities": ["A"], "transport": ["高铁 测试城到乙城"]},
                {"activities": ["B", "C"], "transport": []},
            ],
        }
    ]
    m = _compute_attractions_metrics(legs, benchmarks)
    c = m["cities"][0]
    assert c["transit_days"] == 1
    assert c["effective_days"] == 1.5


def test_pace_transit_days_do_not_inflate_variance_penalty():
    """含交通日时：游览日节奏稳定应得较高分（不因交通日活动少而重罚方差）。"""
    benchmarks = {
        "甲": {"must_see": ["X"], "typical_stay_days": 3},
    }
    legs = [
        {
            "city": "甲",
            "days": [
                {"activities": [], "transport": ["甲到乙 高铁"]},
                {"activities": ["a", "b"], "transport": []},
                {"activities": ["c", "d"], "transport": []},
            ],
        }
    ]
    m = _compute_pace_metrics(legs, benchmarks)
    assert m["transit_day_count"] == 1
    assert m["score"] >= 75


def test_pace_city_density_raises_ideal_range():
    """景点密度高的城市允许非交通日更多活动而不大幅扣分。"""
    benchmarks = {
        "奈良式": {
            "must_see": ["a", "b", "c", "d", "e", "f"],
            "typical_stay_days": 1,
        },
    }
    legs = [
        {
            "city": "奈良式",
            "days": [{"activities": [str(i) for i in range(6)], "transport": []}],
        }
    ]
    m = _compute_pace_metrics(legs, benchmarks)
    assert m["score"] >= 80


def test_attractions_empty_must_see_full_score():
    legs = [{"city": "无清单城", "days": [{"activities": ["闲逛"], "transport": []}]}]
    m = _compute_attractions_metrics(legs, {"无清单城": {"typical_stay_days": 2}})
    assert m["cities"][0]["coverage_pct"] == 100
    assert m["score"] >= 90
