"""Bug 修复测试 — 花费性价比 score 与文案叙事不一致

根因：
- 文案档位 (line 1064-1073): savings_pct ∈ [-10, 10] → "基本持平、花费合理"
- 分数公式 (line 477-484): ratio = 1.0 → 80, ratio = 1.10 → 74
- 用户在「合理」区间内体验到分数从 87 滑到 74，文案"持平"+ 78 分语义不一致

修复方向（方案 A — plateau）：
- ratio ≤ 0.7 → 100（节省 30%+）
- 0.7 < ratio < 0.9 → 100→90 渐降
- 0.9 ≤ ratio ≤ 1.1 → 90 持平 plateau（与文案"基本持平"区间精确对齐）
- 1.1 < ratio ≤ 1.5 → 90→60
- 1.5 < ratio → 60→低
"""
from services.evaluator import _compute_cost_metrics


def _run(per_person_per_day, market_avg):
    """构造一个最小 trip + legs + expenses，返回 cost score。

    leg 有 activity 防止被 _is_non_sightseeing_leg 排除；
    一天单人，ground_expense / 1 / 1 = per_person_per_day。
    """
    trip = {"traveler_count": 1}
    legs = [{
        "city": "_test_city", "country": "_test",
        "days": [{
            "date": "2024-09-15", "transport": [],
            "activities": ["游览"],  # avoid non-sightseeing exclusion
        }],
    }]
    benchmarks = {
        "_test_city": {
            "country": "_test",
            "avg_daily_cost_cny": market_avg,
            "avg_hotel_price_cny": int(market_avg * 0.55),
            "must_see": [],
        }
    }
    expenses = [{"date": "2024-09-15", "amount": per_person_per_day, "category": "餐饮"}]
    return _compute_cost_metrics(trip, legs, expenses, benchmarks)


# ---------------------------------------------------------------------------
# Bug: 文案"基本持平"区间内分数应该 ≥ 88
# ---------------------------------------------------------------------------

class TestCostScorePlateauAlignsWithNarrative:
    """文案档位 (line 1064-1073):
    - savings_pct >  10  → "花费控制出色"
    - savings_pct ∈ [-10, 10] → "基本持平、花费合理"
    - savings_pct < -10  → "高于参考 X%"
    """

    def test_ratio_103_basic_persistent_score_at_least_88(self):
        """Trip 9 真实场景: ratio = 1.030（high 3%），文案"基本持平"，分数 78 → 应 ≥ 88"""
        m = _run(per_person_per_day=856, market_avg=831)
        assert m["savings_pct"] in range(-10, 11), (
            f"sav% should be 'basic persistent', got {m['savings_pct']}"
        )
        assert m["score"] >= 88, (
            f"文案'基本持平、花费合理'但分数={m['score']} < 88"
        )

    def test_ratio_one_should_be_90(self):
        """ratio = 1.0 (持平正中) 应该是 plateau 的中心，至少 88"""
        m = _run(per_person_per_day=1000, market_avg=1000)
        assert m["score"] >= 88, f"完全持平 score={m['score']}"

    def test_ratio_110_top_of_plateau_still_at_least_88(self):
        """ratio = 1.10 (sav% = -10) 文案仍说"基本持平"，分数应 ≥ 88"""
        m = _run(per_person_per_day=1100, market_avg=1000)
        assert m["savings_pct"] == -10
        assert m["score"] >= 88, (
            f"sav%=-10 仍属'持平'区间，分数={m['score']} 不应低于 88"
        )

    def test_ratio_090_bottom_of_plateau_still_at_least_88(self):
        """ratio = 0.90 (sav% = 10) 文案"持平"边界，分数应 ≥ 88"""
        m = _run(per_person_per_day=900, market_avg=1000)
        assert m["savings_pct"] == 10
        assert m["score"] >= 88

    def test_ratio_in_persistent_range_no_below_88(self):
        """整个"持平"区间 (sav% in [-10, 10]) 分数都应 ≥ 88"""
        for sav_target_pct in [-10, -5, -3, 0, 5, 10]:
            ratio = 1 - sav_target_pct / 100
            ppd = round(1000 * ratio)
            m = _run(per_person_per_day=ppd, market_avg=1000)
            assert m["score"] >= 88, (
                f"sav%={m['savings_pct']} ratio={ratio:.3f} score={m['score']}"
            )

    # --- 边界 / 单调性 ---

    def test_extreme_saving_still_100(self):
        """超大节省 ratio ≤ 0.7 仍然 100 分"""
        m = _run(per_person_per_day=500, market_avg=1000)
        assert m["score"] == 100

    def test_above_plateau_score_decreasing(self):
        """超出 plateau 后分数随 ratio 单调递减"""
        scores = []
        for ppd in [1100, 1200, 1300, 1500, 1800]:
            scores.append(_run(per_person_per_day=ppd, market_avg=1000)["score"])
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"分数应单调递减 ratio↑ → score↓，实际: {scores}"
            )

    def test_severe_overspend_under_60(self):
        """严重超支 (ratio > 1.5) 分数应 < 65"""
        m = _run(per_person_per_day=1700, market_avg=1000)
        assert m["score"] < 65, f"sav%={m['savings_pct']} score={m['score']}"

    def test_extreme_overspend_floor_30(self):
        """极端超支不跌破 30"""
        m = _run(per_person_per_day=5000, market_avg=1000)
        assert m["score"] >= 30
