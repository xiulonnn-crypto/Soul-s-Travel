"""测试城市评价景点标签的死区 bug（spot_pct 在 50-79 时不应无标签）"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import _evaluate_city


def _make_leg(city, activities_per_day):
    return {
        "id": 1,
        "city": city,
        "country": "斯里兰卡",
        "days": [{"activities": activities_per_day, "transport": []}],
    }


def _make_leg_days(city, activities_by_day):
    """多天行程，用于在停留天数已足时仍保持较低原始覆盖率（调整后期望仍低）。"""
    return {
        "id": 1,
        "city": city,
        "country": "斯里兰卡",
        "days": [{"activities": acts, "transport": []} for acts in activities_by_day],
    }


BENCHMARKS = {
    "尼甘布": {
        "must_see": ["荷兰运河", "圣玛丽教堂", "荷兰堡垒遗址", "尼甘布鱼市", "尼甘布泻湖", "尼甘布海滩"],
        "typical_stay_days": 2,
        "avg_daily_cost_cny": 440,
        "country": "斯里兰卡",
    }
}


def test_spot_pct_50_has_warning_tag():
    """在停留天数已覆盖典型停留时，原始覆盖率 50% → 调整后期望仍为 50%，应警告。"""
    # 4 天 × 有效天 = 4，typical_stay=2 → stay_ratio=1；覆盖 3/6 = 50%
    leg = _make_leg_days(
        "尼甘布",
        [["尼甘布鱼市"], ["尼甘布泻湖"], ["尼甘布海滩"], []],
    )
    result = _evaluate_city(leg, [], BENCHMARKS)

    assert result["metrics"]["spot_coverage_raw"] == 50
    assert result["metrics"]["spot_coverage"] == 50

    tag_texts = [t["text"] for t in result["tags"]]
    assert "景点覆盖不足" in tag_texts, (
        f"spot_pct=50 应触发'景点覆盖不足'标签，实际 tags={result['tags']}"
    )
    assert "景点全面" not in tag_texts


def test_spot_pct_79_has_warning_tag():
    """调整后期望覆盖率 <80% 时应显示景点覆盖不足"""
    benchmarks = {
        "测试城市": {
            "must_see": ["A", "B", "C", "D", "E"],
            "typical_stay_days": 2,
            "avg_daily_cost_cny": 500,
            "country": "测试国",
        }
    }
    # 4 天、stay_ratio=1，覆盖 3/5 = 60%
    leg = _make_leg_days("测试城市", [["A"], ["B"], ["C"], []])
    result = _evaluate_city(leg, [], benchmarks)

    tag_texts = [t["text"] for t in result["tags"]]
    assert "景点覆盖不足" in tag_texts, (
        f"spot_pct=60 应触发'景点覆盖不足'，实际 tags={result['tags']}"
    )


def test_spot_pct_100_has_positive_tag():
    """spot_pct=100 应显示"景点全面"正面标签"""
    all_spots = ["荷兰运河", "圣玛丽教堂", "荷兰堡垒遗址", "尼甘布鱼市", "尼甘布泻湖", "尼甘布海滩"]
    leg = _make_leg("尼甘布", all_spots)
    result = _evaluate_city(leg, [], BENCHMARKS)

    tag_texts = [t["text"] for t in result["tags"]]
    assert "景点全面" in tag_texts
    assert "景点覆盖不足" not in tag_texts


def test_spot_pct_80_has_positive_tag():
    """spot_pct=80（边界值）应显示景点全面标签"""
    benchmarks = {
        "测试城市": {
            "must_see": ["A", "B", "C", "D", "E"],
            "typical_stay_days": 2,
            "avg_daily_cost_cny": 500,
            "country": "测试国",
        }
    }
    # 覆盖 4/5 = 80%
    leg = _make_leg("测试城市", ["A", "B", "C", "D"])
    result = _evaluate_city(leg, [], benchmarks)

    tag_texts = [t["text"] for t in result["tags"]]
    assert "景点全面" in tag_texts, (
        f"spot_pct=80 应触发'景点全面'，实际 tags={result['tags']}"
    )
    assert "景点覆盖不足" not in tag_texts
