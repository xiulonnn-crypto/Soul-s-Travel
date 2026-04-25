"""历史已去景点应计入当次行程景点覆盖（不再列为 missed）

真实场景：Trip 11（2025 年东京行程）是第二次日本行，Trip 3（2019 年）已去过
东京塔、秋叶原、银座。当前评价不应把这些景点列为"遗漏"。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import _compute_attractions_metrics, _evaluate_city

BENCHMARKS = {
    "东京": {
        "must_see": ["浅草寺", "东京塔", "涩谷十字路口", "明治神宫", "秋叶原"],
        "typical_stay_days": 4,
        "avg_daily_cost_cny": 1200,
        "country": "日本",
    }
}

# ---- _compute_attractions_metrics 测试 ----------------------------------------

def test_past_visited_counts_as_covered_in_attractions_metrics():
    """历史行程去过的景点应算入 covered，不计入 missed。"""
    legs = [
        {
            "city": "东京",
            "days": [
                {"activities": ["浅草寺"], "transport": []},
            ],
        }
    ]
    # 模拟 2019 年已去过东京塔、秋叶原
    past_visited = {"东京": ["东京塔", "秋叶原"]}

    m = _compute_attractions_metrics(legs, BENCHMARKS, past_visited=past_visited)
    city = m["cities"][0]

    assert "东京塔" in city["covered"], "历史景点东京塔应在 covered 中"
    assert "秋叶原" in city["covered"], "历史景点秋叶原应在 covered 中"
    assert "东京塔" not in city["missed"], "东京塔不应出现在 missed 中"
    assert "秋叶原" not in city["missed"], "秋叶原不应出现在 missed 中"


def test_past_visited_improves_coverage_score():
    """历史景点计入后，覆盖率应高于不计历史时的值。"""
    legs = [
        {
            "city": "东京",
            "days": [
                {"activities": ["浅草寺"], "transport": []},
            ],
        }
    ]
    m_without = _compute_attractions_metrics(legs, BENCHMARKS)
    m_with = _compute_attractions_metrics(
        legs, BENCHMARKS, past_visited={"东京": ["东京塔", "秋叶原"]}
    )

    assert m_with["cities"][0]["raw_coverage_pct"] > m_without["cities"][0]["raw_coverage_pct"], (
        "加入历史景点后原始覆盖率应提升"
    )


def test_without_past_visited_keeps_baseline_behavior():
    """不传 past_visited 时行为与原来一致（对比基线，避免引入回归）。"""
    legs = [
        {
            "city": "东京",
            "days": [
                {"activities": ["浅草寺"], "transport": []},
            ],
        }
    ]
    m = _compute_attractions_metrics(legs, BENCHMARKS)
    city = m["cities"][0]

    assert "东京塔" in city["missed"], "不传历史景点时，东京塔应仍在 missed 中"
    assert "秋叶原" in city["missed"], "不传历史景点时，秋叶原应仍在 missed 中"


# ---- _evaluate_city 测试 -------------------------------------------------------

def test_evaluate_city_past_visited_not_in_missed_spots():
    """_evaluate_city 中历史景点应计入 covered，不出现在 missed_spots 中。"""
    leg = {
        "id": 1,
        "city": "东京",
        "country": "日本",
        "days": [
            {"activities": ["浅草寺"], "transport": []},
        ],
    }
    past_visited = {"东京": ["东京塔", "秋叶原"]}

    result = _evaluate_city(leg, [], BENCHMARKS, past_visited=past_visited)

    assert "东京塔" not in result["missed_spots"], (
        f"历史已去的东京塔不应在 missed_spots 中，实际: {result['missed_spots']}"
    )
    assert "秋叶原" not in result["missed_spots"], (
        f"历史已去的秋叶原不应在 missed_spots 中，实际: {result['missed_spots']}"
    )


def test_evaluate_city_score_improves_with_past_visited():
    """历史景点计入后，城市评分（景点子分）应提升。"""
    leg = {
        "id": 1,
        "city": "东京",
        "country": "日本",
        "days": [
            {"activities": ["浅草寺"], "transport": []},
        ],
    }
    score_without = _evaluate_city(leg, [], BENCHMARKS)["score"]
    score_with = _evaluate_city(
        leg, [], BENCHMARKS, past_visited={"东京": ["东京塔", "秋叶原"]}
    )["score"]

    assert score_with >= score_without, (
        f"有历史记录时评分({score_with})应 >= 无历史时({score_without})"
    )


def test_evaluate_city_other_city_past_visited_ignored():
    """其他城市的历史景点不应影响当前城市评价。"""
    leg = {
        "id": 1,
        "city": "东京",
        "country": "日本",
        "days": [
            {"activities": ["浅草寺"], "transport": []},
        ],
    }
    # 传入的是京都的历史景点，东京不应受影响
    past_visited = {"京都": ["金阁寺", "岚山竹林"]}
    result = _evaluate_city(leg, [], BENCHMARKS, past_visited=past_visited)

    assert "东京塔" in result["missed_spots"] or len(result["missed_spots"]) > 0, (
        "其他城市历史景点不应改变东京的 missed_spots"
    )
