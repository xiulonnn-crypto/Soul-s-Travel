"""行程节奏按活动难度加权评分"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import (
    _activity_load_weight,
    _day_activity_load,
    _compute_pace_metrics,
)


# ---------------------------------------------------------------------------
# 单元：_activity_load_weight 关键词权重
# ---------------------------------------------------------------------------

def test_weight_high_difficulty_museum_and_palace():
    """博物馆、皇宫、古城等耗时体力活动应为高权重。"""
    for name in [
        "曼谷国家博物馆",
        "黑屋博物馆",
        "大皇宫",
        "曼谷大皇宫",
        "清迈古城",
        "大象自然保护区",
        "清迈夜间动物园",
        "富士山",
        "徒步尾濑国立公园",
    ]:
        assert _activity_load_weight(name) == 1.5, f"{name} 应为高权重"


def test_weight_low_difficulty_market_and_square():
    """夜市、广场、餐厅、游轮等轻量活动应为低权重。"""
    for name in [
        "iconsiam夜市",
        "暹罗广场",
        "陈瑞兴餐室",
        "美功铁道集市",
        "丹嫩沙多水上市场",
        "夜游湄南河游轮",
        "曼谷夜市摩天轮",
    ]:
        assert _activity_load_weight(name) == 0.5, f"{name} 应为低权重"


def test_weight_default_standard_activities():
    """普通景点（寺/庙/神祠/门/园）保持 1.0。"""
    for name in ["玉佛寺", "郑王庙", "塔佩门", "清曼寺", "伊拉旺神祠四面佛", "白庙"]:
        assert _activity_load_weight(name) == 1.0, f"{name} 应为标准权重"


def test_weight_mall_not_confused_with_palace():
    """暹罗百丽宫是商场而非皇宫，不应误判为高强度。"""
    assert _activity_load_weight("暹罗百丽宫") == 1.0


def test_day_activity_load_sums_weights():
    """单日活动量 = sum(活动权重)。"""
    day = {"activities": ["大皇宫", "玉佛寺", "iconsiam夜市"]}
    assert _day_activity_load(day) == 1.5 + 1.0 + 0.5


# ---------------------------------------------------------------------------
# 集成：加权后整日评分差异
# ---------------------------------------------------------------------------

def test_pace_light_day_scores_higher_than_heavy_day_same_count():
    """8 个低强度活动应比 8 个高强度活动得分更高（因为后者真的密集）。"""
    benchmarks = {"甲": {"must_see": ["a", "b", "c"], "typical_stay_days": 3}}
    light = [{
        "city": "甲",
        "days": [{
            "day_number": 1,
            "activities": [
                "A餐厅", "B夜市", "C市场", "D广场",
                "E夜市", "F咖啡馆", "G商场", "H游轮",
            ],
            "transport": [],
        }],
    }]
    heavy = [{
        "city": "甲",
        "days": [{
            "day_number": 1,
            "activities": [
                "A博物馆", "B国家公园", "C保护区", "D古城",
                "E皇宫", "F动物园", "G水族馆", "H美术馆",
            ],
            "transport": [],
        }],
    }]
    light_score = _compute_pace_metrics(light, benchmarks)["score"]
    heavy_score = _compute_pace_metrics(heavy, benchmarks)["score"]
    assert light_score > heavy_score, (
        f"轻量日应比重量日得分更高: light={light_score}, heavy={heavy_score}"
    )


def test_pace_busiest_day_chosen_by_weighted_load():
    """busiest_day 应按加权活动量选择，而非纯数量。"""
    benchmarks = {"甲": {"must_see": ["x"], "typical_stay_days": 3}}
    legs = [{
        "city": "甲",
        "days": [
            # Day 1: 3 个重活动，活动量 4.5
            {"day_number": 1, "activities": ["A博物馆", "B山", "C保护区"], "transport": []},
            # Day 2: 5 个轻活动，活动量 2.5
            {"day_number": 2, "activities": ["a夜市", "b广场", "c餐厅", "d咖啡馆", "e商场"], "transport": []},
        ],
    }]
    m = _compute_pace_metrics(legs, benchmarks)
    assert m["busiest_day"] == 1, (
        f"Day1 虽然只有 3 个活动，加权活动量 4.5 高于 Day2 的 2.5，应被选为 busiest_day，"
        f"实际 busiest_day={m['busiest_day']}"
    )


def test_pace_eight_light_activities_not_flagged_as_packed():
    """8 个低强度活动不应被标记为'偏满'（活动量 4.0 低于阈值）。"""
    benchmarks = {"甲": {"must_see": ["a"], "typical_stay_days": 3}}
    legs = [{
        "city": "甲",
        "days": [{
            "day_number": 1,
            "activities": [
                "A餐厅", "B夜市", "C市场", "D广场",
                "E夜市", "F咖啡馆", "G商场", "H游轮",
            ],
            "transport": [],
        }],
    }]
    m = _compute_pace_metrics(legs, benchmarks)
    # 不应出现 "略显密集" 或 "偏满" 文字
    from services.evaluator import _generate_pace_text, _generate_pace_tags
    text = _generate_pace_text(m)
    tags = _generate_pace_tags(m)
    warning_texts = [t["text"] for t in tags if t["type"] == "warning"]
    assert "略显密集" not in text, f"8 个轻活动不应被标为密集: {text!r}"
    assert not any("偏满" in w for w in warning_texts), (
        f"8 个轻活动不应触发 '偏满' 警告: {warning_texts}"
    )


def test_pace_metrics_exposes_avg_load_and_busiest_load():
    """指标应暴露加权后的活动量字段（供前端透明展示）。"""
    benchmarks = {"甲": {"must_see": ["a"], "typical_stay_days": 3}}
    legs = [{
        "city": "甲",
        "days": [{
            "day_number": 1,
            "activities": ["博物馆X", "餐厅Y", "广场Z"],  # load = 1.5 + 0.5 + 0.5 = 2.5
            "transport": [],
        }],
    }]
    m = _compute_pace_metrics(legs, benchmarks)
    assert "avg_load" in m, "pace metrics 应包含 avg_load 字段"
    assert abs(m["avg_load"] - 2.5) < 0.01, f"avg_load 应为 2.5，实际 {m['avg_load']}"
    assert "busiest_load" in m, "pace metrics 应包含 busiest_load 字段"
    assert abs(m["busiest_load"] - 2.5) < 0.01


def test_pace_text_mentions_difficulty_weighting():
    """节奏文案应说明按难度加权。"""
    benchmarks = {"甲": {"must_see": ["a"], "typical_stay_days": 3}}
    legs = [{
        "city": "甲",
        "days": [{
            "day_number": 1,
            "activities": ["A", "B", "C"],
            "transport": [],
        }],
    }]
    from services.evaluator import _compute_pace_metrics, _generate_pace_text
    m = _compute_pace_metrics(legs, benchmarks)
    text = _generate_pace_text(m)
    assert "难度" in text or "加权" in text or "活动量" in text, (
        f"节奏文案应体现难度加权概念: {text!r}"
    )
