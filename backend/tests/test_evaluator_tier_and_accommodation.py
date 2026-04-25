"""
Bug 修复测试：
1. 消费层级应按家庭人数（profile.family_description）计算，而非行程出行人数
2. 住宿品质均价应按人均每晚计算（÷ traveler_count）

Trip 12 真实场景：
  - profile.annual_travel_budget = 100,000 CNY（夫妻两人）
  - trip.traveler_count = 7（全家出游含亲属）
  - 当前错误：100,000÷7÷35,000=0.408 → 0.61 → 经济型
  - 期望正确：100,000÷2÷35,000=1.43 → ~1.22 → 品质型
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import (
    _compute_tier_multiplier,
    _extract_household_size,
    _tier_label,
    _compute_accommodation_metrics,
)


# ---------------------------------------------------------------------------
# Bug 1: 消费层级应按家庭人数，不受行程人数影响
# ---------------------------------------------------------------------------

class TestExtractHouseholdSize:
    def test_couple_description(self):
        """'夫妻两人' → 2"""
        assert _extract_household_size({"family_description": "夫妻两人"}) == 2

    def test_three_person_description(self):
        """'三口之家' 含'三人' → 3"""
        assert _extract_household_size({"family_description": "三口之家"}) == 3

    def test_solo_description(self):
        """无匹配 → 默认 1"""
        assert _extract_household_size({"family_description": "独行侠"}) == 1

    def test_none_profile(self):
        """profile 为 None → 1"""
        assert _extract_household_size(None) == 1

    def test_empty_family_description(self):
        """family_description 为空 → 1"""
        assert _extract_household_size({"family_description": ""}) == 1

    def test_couple_keyword_without_number(self):
        """'夫妻' 关键词（无人数词） → 2"""
        assert _extract_household_size({"family_description": "夫妻"}) == 2


class TestTierUsesHouseholdSize:
    """消费层级乘数应基于家庭人数，不随行程 traveler_count 变化。"""

    PROFILE_COUPLE = {
        "annual_travel_budget": 100_000,
        "family_description": "夫妻两人",
    }

    def test_trip12_scenario_tier_is_not_economy(self):
        """Trip 12：7人出游，但家庭为2人 → 应为品质型，非经济型。"""
        household_size = _extract_household_size(self.PROFILE_COUPLE)
        mult = _compute_tier_multiplier(self.PROFILE_COUPLE, household_size)
        label = _tier_label(mult)
        # 100000 / 2 / 35000 = 1.4286 → ^0.55 ≈ 1.22 → 品质型
        assert label == "品质型", (
            f"家庭2人+预算10万 → 应为品质型，实际: {label}（乘数={mult:.3f}）"
        )

    def test_household_size_2_gives_consistent_mult(self):
        """与 traveler_count=2 的其他行程结果一致（~1.22）。"""
        mult = _compute_tier_multiplier(self.PROFILE_COUPLE, 2)
        assert 1.15 <= mult < 1.5, f"乘数应在品质型区间 [1.15, 1.5)，实际: {mult:.3f}"

    def test_trip_group_size_7_does_not_lower_tier(self):
        """若误用 traveler_count=7 → 乘数会错误低至 0.61（经济型），本测试确认修复后不再发生。"""
        household_size = _extract_household_size(self.PROFILE_COUPLE)
        mult_correct = _compute_tier_multiplier(self.PROFILE_COUPLE, household_size)
        mult_wrong = _compute_tier_multiplier(self.PROFILE_COUPLE, 7)
        assert mult_correct > mult_wrong, "家庭人数乘数应高于7人组乘数"
        assert mult_correct >= 1.15, "正确乘数应达到品质型下限"


# ---------------------------------------------------------------------------
# Bug 2: 住宿品质均价应按人均每晚（÷ traveler_count）
# ---------------------------------------------------------------------------

class TestAccommodationAvgNightlyPerPerson:
    """Trip 12 真实场景：7人，8晚住宿，住宿总支出 26,530 CNY。"""

    TRIP12_LEGS = [
        {
            "city": "胡志明市",
            "country": "越南",
            "days": [
                {"accommodation": "JW Marriott Saigon", "transport": ["成都→胡志明"], "activities": []},
                {"accommodation": "JW Marriott Saigon", "transport": [], "activities": []},
                {"accommodation": "JW Marriott Saigon", "transport": [], "activities": []},
            ],
        },
        {
            "city": "富国岛",
            "country": "越南",
            "days": [
                {"accommodation": "威尼斯酒店", "transport": ["胡志明→富国"], "activities": []},
                {"accommodation": "新世界富国度假村", "transport": [], "activities": []},
                {"accommodation": "新世界富国度假村", "transport": [], "activities": []},
                {"accommodation": "JW Marriott Saigon", "transport": ["富国→胡志明"], "activities": []},
                {"accommodation": "JW Marriott Saigon", "transport": [], "activities": []},
            ],
        },
    ]

    TRIP12_EXPENSES = [
        {"category": "住宿", "amount": 3599.0},
        {"category": "住宿", "amount": 3599.0},
        {"category": "住宿", "amount": 3599.0},
        {"category": "住宿", "amount": 2776.0},
        {"category": "住宿", "amount": 4690.0},
        {"category": "住宿", "amount": 4690.0},
        {"category": "住宿", "amount": 3577.0},
    ]  # hotel_expense = 26530，nights(has_accommodation) = 8

    def test_avg_nightly_per_person_for_7_travelers(self):
        """7人行程：avg_nightly 应为 26530÷8÷7 ≈ 474，而非 3316（全组合计）。"""
        m = _compute_accommodation_metrics(
            self.TRIP12_LEGS, self.TRIP12_EXPENSES, {}, traveler_count=7
        )
        expected_per_person = round(26530 / 8 / 7)  # ≈ 474
        assert m["avg_nightly"] == expected_per_person, (
            f"avg_nightly 应为人均每晚 {expected_per_person}，实际: {m['avg_nightly']}"
        )

    def test_avg_nightly_unchanged_for_single_traveler(self):
        """单人行程（traveler_count=1）：avg_nightly 不应变化（÷1 = 原值）。"""
        expenses = [{"category": "住宿", "amount": 1000.0}]
        legs = [{"city": "曼谷", "country": "泰国", "days": [
            {"accommodation": "曼谷酒店", "transport": [], "activities": []},
        ]}]
        m_single = _compute_accommodation_metrics(legs, expenses, {}, traveler_count=1)
        m_default = _compute_accommodation_metrics(legs, expenses, {})
        assert m_single["avg_nightly"] == m_default["avg_nightly"], (
            "traveler_count=1 时结果应与默认值相同"
        )

    def test_backward_compat_no_traveler_count_arg(self):
        """不传 traveler_count 时默认为 1，保持与现有测试的兼容性。"""
        m = _compute_accommodation_metrics(self.TRIP12_LEGS, self.TRIP12_EXPENSES, {})
        # 不崩溃，且 avg_nightly 未除以组数
        expected_no_division = round(26530 / 8 / 1)
        assert m["avg_nightly"] == expected_no_division
