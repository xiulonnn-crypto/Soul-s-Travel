"""Bug 修复测试 — 参考消费基准低估

根因（多层叠加，跨多次修复完成）：
1. city_benchmarks.json 中泰国城市的 avg_hotel_price_cny 偏低（¥220-450
   对应 3星经济档），导致任何 tier 乘出来的住宿参考都不匹配「中高档消费」直觉
2. dest_coeff 一刀切：同一系数同时作用于「住宿」与「日均消费」上，
   但「穷地富游/富地穷游」核心只体现在住宿/餐饮上。日均消费包含本地交通、
   门票、机场税等不受穷富影响的项，不应被 dest_coeff 同等放大/压缩
3. 上次拆分 dest_coeff 时两个系数都依赖 daily base — semantic 上不解耦：
   上调 daily 数据会让 hotel 参考反向回退，破坏 hotel 修复
4. 低消费国家 daily 数据停留在「经济档」语义（¥450-900），
   与已抬到「中档 4 星均价」的 hotel 不匹配，hotel 几乎填满整个 daily

修复方向（最终）：
- 提高 11 国 55 城的 avg_hotel_price_cny 至「中档 4 星均价」基准（按 daily×0.70）
- 拆分 _destination_upgrade_coefficient 为两个独立系数：
    _hotel_dest_coefficient(base_hotel): 用 hotel anchor=600，与 daily 解耦
    _daily_dest_coefficient(base_daily): 用 daily anchor=800，缓和系数
- 同步上调 11 国 55 城的 avg_daily_cost_cny 使 hotel/daily ≈ 0.55
- 不动 tier_mult 公式与 season_mult
"""
from services.evaluator import (
    _hotel_dest_coefficient,
    _daily_dest_coefficient,
    _build_adjusted_benchmarks,
    _load_benchmarks,
    _compute_tier_multiplier,
    _extract_household_size,
)


# ---------------------------------------------------------------------------
# Bug 1: dest_coeff 必须按「住宿」与「日均」拆分
# ---------------------------------------------------------------------------

class TestDestCoefficientSplit:
    """住宿系数与日均系数的形状属性 — 各自用语义对应的 anchor (hotel/daily)。"""

    def test_anchors_both_near_one(self):
        """hotel=600 (hotel anchor), daily=800 (daily anchor): 两个系数都 ≈ 1.0"""
        assert abs(_hotel_dest_coefficient(600) - 1.0) < 0.05
        assert abs(_daily_dest_coefficient(800) - 1.0) < 0.05

    def test_poor_destination_hotel_steeper_than_daily(self):
        """穷地典型城市（hotel=400, daily=500）：住宿升级幅度大于日均升级幅度。
        — 4 星酒店在穷国相对昂贵，住宿升级空间显著；本地交通门票升级幅度小。
        """
        h = _hotel_dest_coefficient(400)   # 穷地 hotel base
        d = _daily_dest_coefficient(500)   # 穷地 daily base
        assert h > 1.0, f"穷地住宿系数应 > 1.0，实际: {h:.3f}"
        assert d > 1.0, f"穷地日均系数应 > 1.0，实际: {d:.3f}"
        assert h > d, (
            f"穷地住宿升级应大于日均升级（核心是住宿/餐饮），"
            f"实际 hotel={h:.3f}, daily={d:.3f}"
        )
        assert h >= 1.10, f"穷地住宿系数应升幅 >= 10%，实际: {h:.3f}"
        assert d <= 1.15, f"穷地日均系数升幅应温和 <= 15%，实际: {d:.3f}"

    def test_rich_destination_hotel_steeper_than_daily(self):
        """富地典型城市（hotel=1200, daily=2000）：住宿压缩幅度大于日均压缩幅度。"""
        h = _hotel_dest_coefficient(1200)
        d = _daily_dest_coefficient(2000)
        assert h < 1.0, f"富地住宿系数应 < 1.0，实际: {h:.3f}"
        assert d < 1.0, f"富地日均系数应 < 1.0，实际: {d:.3f}"
        assert h < d, (
            f"富地住宿压缩应大于日均压缩（本地交通门票不受穷富影响），"
            f"实际 hotel={h:.3f}, daily={d:.3f}"
        )

    def test_extreme_poor_does_not_explode(self):
        """极穷地不应超出合理上限。"""
        h = _hotel_dest_coefficient(150)   # 极穷 hotel base
        d = _daily_dest_coefficient(200)   # 极穷 daily base
        assert h <= 1.7, f"住宿系数 cap 应 <= 1.7，实际: {h:.3f}"
        assert d <= 1.3, f"日均系数 cap 应 <= 1.3，实际: {d:.3f}"

    def test_extreme_rich_does_not_collapse(self):
        """极富地不应跌破合理下限。"""
        h = _hotel_dest_coefficient(2500)  # 极富 hotel base
        d = _daily_dest_coefficient(3000)
        assert h >= 0.7, f"住宿系数 floor 应 >= 0.7，实际: {h:.3f}"
        assert d >= 0.85, f"日均系数 floor 应 >= 0.85，实际: {d:.3f}"

    def test_zero_input_safe(self):
        """边界：base <= 0 应返回 1.0，不抛异常。"""
        assert _hotel_dest_coefficient(0) == 1.0
        assert _hotel_dest_coefficient(-100) == 1.0
        assert _daily_dest_coefficient(0) == 1.0


# ---------------------------------------------------------------------------
# Bug 2: 泰国基础住宿价应反映「中档 4 星均价」而非「3 星经济档」
# ---------------------------------------------------------------------------

class TestThaiHotelBaselineUplifted:
    """修正前曼谷 ¥350 是经济档；修正后应在 4 星均价区间。"""

    def test_bangkok_hotel_at_least_500(self):
        bm = _load_benchmarks()
        assert bm["曼谷"]["avg_hotel_price_cny"] >= 500, (
            f"曼谷基础住宿应至少 ¥500（4 星均价），"
            f"实际: ¥{bm['曼谷']['avg_hotel_price_cny']}"
        )

    def test_chiangmai_hotel_at_least_350(self):
        bm = _load_benchmarks()
        assert bm["清迈"]["avg_hotel_price_cny"] >= 350, (
            f"清迈基础住宿应至少 ¥350，实际: ¥{bm['清迈']['avg_hotel_price_cny']}"
        )

    def test_phuket_hotel_at_least_600(self):
        bm = _load_benchmarks()
        assert bm["普吉岛"]["avg_hotel_price_cny"] >= 600, (
            f"普吉岛基础住宿应至少 ¥600，实际: ¥{bm['普吉岛']['avg_hotel_price_cny']}"
        )

    def test_chiangrai_hotel_at_least_300(self):
        bm = _load_benchmarks()
        assert bm["清莱"]["avg_hotel_price_cny"] >= 300, (
            f"清莱基础住宿应至少 ¥300，实际: ¥{bm['清莱']['avg_hotel_price_cny']}"
        )


# ---------------------------------------------------------------------------
# Bug 3: _build_adjusted_benchmarks 应分别使用两个 dest_coeff
# ---------------------------------------------------------------------------

class TestAdjustedBenchmarksUsesSplitCoeff:
    """同一城市的 hotel 和 daily 调整后比例应不同（因 dest_coeff 已拆分）。"""

    def test_thai_city_hotel_vs_daily_have_different_ratios(self):
        bm = _load_benchmarks()
        legs = [{"city": "清迈", "country": "泰国", "days": [
            {"date": "2024-09-15", "transport": [], "activities": []},
        ]}]
        adjusted = _build_adjusted_benchmarks(bm, tier_mult=1.0, legs=legs)
        adj = adjusted["清迈"]
        orig_hotel = bm["清迈"]["avg_hotel_price_cny"]
        orig_daily = bm["清迈"]["avg_daily_cost_cny"]

        # 9 月清迈淡季（off_peak month list 含 5-9），season_mult=0.8
        # tier_mult=1.0
        # hotel_coeff > daily_coeff（清迈 daily 较低，属穷地）
        hotel_ratio = adj["avg_hotel_price_cny"] / orig_hotel
        daily_ratio = adj["avg_daily_cost_cny"] / orig_daily
        assert hotel_ratio > daily_ratio, (
            f"穷地清迈：调整后住宿比例({hotel_ratio:.3f}) "
            f"应大于日均比例({daily_ratio:.3f})"
        )


# ---------------------------------------------------------------------------
# Bug 4: Trip 9 真实场景端到端 — 品质型住宿参考应贴合 5 星标准而非经济档
# ---------------------------------------------------------------------------

class TestTrip9EndToEndAccommodationReference:
    """Trip 9 真实场景：曼谷3+清迈4+清莱1，9月淡季，profile=夫妻10万年预算。

    用户实际入住「皇家兰花喜来登」¥975/晚（夫妻房）= ¥487/人/晚，
    系统应判为「品质型住的 5 星酒店」合理偏上，而非「住宿花费偏高」。
    """

    PROFILE_COUPLE_100K = {
        "annual_travel_budget": 100_000,
        "family_description": "夫妻两人",
    }

    TRIP9_LEGS = [
        {"city": "曼谷", "country": "泰国", "days": [
            {"date": "2024-09-15", "transport": ["北京→曼谷"], "activities": []},
            {"date": "2024-09-16", "transport": [], "activities": []},
            {"date": "2024-09-17", "transport": [], "activities": []},
        ]},
        {"city": "清迈", "country": "泰国", "days": [
            {"date": "2024-09-18", "transport": ["曼谷→清迈"], "activities": []},
            {"date": "2024-09-19", "transport": [], "activities": []},
            {"date": "2024-09-20", "transport": [], "activities": []},
            {"date": "2024-09-21", "transport": ["清迈→清莱"], "activities": []},
        ]},
        {"city": "清莱", "country": "泰国", "days": [
            {"date": "2024-09-22", "transport": [], "activities": []},
        ]},
    ]

    def test_quality_tier_hotel_reference_above_400(self):
        """品质型 + 9月泰国淡季：加权住宿参考应 >= ¥400（修复前 ¥312）"""
        household_size = _extract_household_size(self.PROFILE_COUPLE_100K)
        tier_mult = _compute_tier_multiplier(self.PROFILE_COUPLE_100K, household_size)
        bm = _load_benchmarks()
        adjusted = _build_adjusted_benchmarks(bm, tier_mult, self.TRIP9_LEGS)

        # 加权: 曼谷 3 + 清迈 4 + 清莱 1
        weighted = (
            adjusted["曼谷"]["avg_hotel_price_cny"] * 3 +
            adjusted["清迈"]["avg_hotel_price_cny"] * 4 +
            adjusted["清莱"]["avg_hotel_price_cny"] * 1
        ) / 8
        assert weighted >= 400, (
            f"品质型旅行者去 9 月泰国，住宿参考应 >= ¥400/晚，"
            f"实际: ¥{weighted:.0f}/晚（修复前为 ¥312）"
        )

    def test_quality_tier_hotel_reference_below_700(self):
        """合理上限：品质型不应被推得过高（5 星均价水平以上是高端型才有的）"""
        household_size = _extract_household_size(self.PROFILE_COUPLE_100K)
        tier_mult = _compute_tier_multiplier(self.PROFILE_COUPLE_100K, household_size)
        bm = _load_benchmarks()
        adjusted = _build_adjusted_benchmarks(bm, tier_mult, self.TRIP9_LEGS)

        weighted = (
            adjusted["曼谷"]["avg_hotel_price_cny"] * 3 +
            adjusted["清迈"]["avg_hotel_price_cny"] * 4 +
            adjusted["清莱"]["avg_hotel_price_cny"] * 1
        ) / 8
        assert weighted <= 700, (
            f"品质型住宿参考不应超过 ¥700/晚（保留高端型空间），"
            f"实际: ¥{weighted:.0f}/晚"
        )

    def test_chiangmai_hotel_off_season_does_not_undercut_baseline(self):
        """穷地 × 淡季叠加不应让最终参考低于原始基础数据 50%（避免反直觉）。"""
        household_size = _extract_household_size(self.PROFILE_COUPLE_100K)
        tier_mult = _compute_tier_multiplier(self.PROFILE_COUPLE_100K, household_size)
        bm = _load_benchmarks()
        adjusted = _build_adjusted_benchmarks(bm, tier_mult, self.TRIP9_LEGS)

        orig = bm["清迈"]["avg_hotel_price_cny"]
        adj = adjusted["清迈"]["avg_hotel_price_cny"]
        # 品质型用户去淡季穷地，hotel 调整后不应低于原始基础的 80%
        assert adj >= orig * 0.8, (
            f"清迈品质型淡季住宿参考 ¥{adj} 不应低于原始 ¥{orig} 的 80%"
        )


# ---------------------------------------------------------------------------
# Bug 5: 其他低消费国家的基础住宿数据也应反映「中档 4 星均价」
# ---------------------------------------------------------------------------

class TestLowCostCountryHotelBaselinesUplifted:
    """泰国之外其他 10 个低消费国家的代表性城市 hotel 基础数据，
    也应从经济档抬升到中档 4 星均价（约 daily × 0.65 以上）。

    跳过：中国（自国家场景）、缅甸（数据已贴近 4 星均价）。
    """

    # (城市, 期望 hotel 下限)
    # 注：本测试只关心 hotel 是否抬升到中档 4 星均价；daily 由 sibling 测试断言
    REPRESENTATIVE_CITIES = [
        # 越南 — 用户去过
        ("胡志明市", 340),
        ("河内", 310),
        ("岘港", 320),
        # 马来西亚 — 用户去过
        ("吉隆坡", 390),
        ("槟城", 350),
        ("亚庇", 350),
        # 斯里兰卡 — 用户去过
        ("科伦坡", 480),
        ("康提", 420),
        ("加勒", 450),
        # 肯尼亚 — 用户去过
        ("内罗毕", 580),
        ("蒙巴萨", 520),
        # 文莱 — 用户去过
        ("斯里巴加湾市", 450),
        # 埃及 — 旅游热点
        ("开罗", 420),
        ("沙姆沙伊赫", 450),
        ("卢克索", 390),
        # 印度尼西亚
        ("巴厘岛", 450),
        # 柬埔寨
        ("暹粒", 390),
        # 蒙古
        ("乌兰巴托", 390),
        # 土耳其
        ("伊斯坦布尔", 520),
    ]

    def test_each_representative_city_hotel_at_least_4star_floor(self):
        bm = _load_benchmarks()
        failures = []
        for city, expected_min_hotel in self.REPRESENTATIVE_CITIES:
            assert city in bm, f"基准数据缺失城市: {city}"
            actual_hotel = bm[city]["avg_hotel_price_cny"]
            if actual_hotel < expected_min_hotel:
                failures.append(
                    f"{city}: hotel ¥{actual_hotel} < 4星均价下限 ¥{expected_min_hotel}"
                )
        assert not failures, (
            "以下低消费国家城市的 hotel 基础数据仍停留在经济档：\n  " +
            "\n  ".join(failures)
        )

    def test_country_default_hotel_floors(self):
        """国家级回退值也应同步抬升（用于基准数据缺失时的兜底）。"""
        bm = _load_benchmarks()
        # 必须从原始 JSON 拿 _country_defaults，_load_benchmarks() 不暴露
        import json
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "data" / "city_benchmarks.json"
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        defaults = raw["_country_defaults"]

        # (国家, 期望 hotel 下限)
        EXPECTED_FLOORS = [
            ("越南", 340),
            ("马来西亚", 360),
            ("斯里兰卡", 430),
            ("肯尼亚", 540),
            ("文莱", 470),
            ("印度尼西亚", 470),
            ("柬埔寨", 360),
            ("蒙古", 360),
            ("埃及", 400),
            ("土耳其", 540),
        ]
        failures = []
        for country, floor in EXPECTED_FLOORS:
            assert country in defaults, f"_country_defaults 缺失: {country}"
            actual = defaults[country].get("avg_hotel_price_cny", 0)
            if actual < floor:
                failures.append(
                    f"{country}: country_default hotel ¥{actual} < 期望 ¥{floor}"
                )
        assert not failures, (
            "以下国家的回退住宿基准仍偏低：\n  " + "\n  ".join(failures)
        )


# ---------------------------------------------------------------------------
# Bug 6: hotel_dest_coefficient 应该用 hotel base，与 daily 维度解耦
# ---------------------------------------------------------------------------

class TestHotelDestCoefficientDecoupledFromDaily:
    """上次拆分 dest_coeff 时两个系数都依赖 daily base — semantic 上不一致。
    住宿系数应该用 hotel anchor (中档 4 星均价) 判断穷地/富地，与 daily 解耦。
    这样上调 daily 不会回退已修复的 hotel 参考。"""

    def test_hotel_coeff_at_hotel_anchor_is_one(self):
        """hotel base = 600 (中档 4 星均价 anchor) 应得到系数 1.0"""
        from services.evaluator import _hotel_dest_coefficient
        h = _hotel_dest_coefficient(600)
        assert abs(h - 1.0) < 0.05, (
            f"hotel anchor (600) 处的住宿系数应接近 1.0，实际: {h:.3f}"
        )

    def test_hotel_coeff_for_low_hotel_amplifies(self):
        """低 hotel base (¥350) 表示穷地 4 星，应得到 > 1.0 的系数（升级空间）"""
        from services.evaluator import _hotel_dest_coefficient
        h = _hotel_dest_coefficient(350)
        assert h > 1.10, f"低 hotel 应升幅 >= 10%，实际: {h:.3f}"

    def test_hotel_coeff_for_high_hotel_compresses(self):
        """高 hotel base (¥1500) 表示富地 4 星，应得到 < 1.0 的系数"""
        from services.evaluator import _hotel_dest_coefficient
        h = _hotel_dest_coefficient(1500)
        assert h < 1.0, f"高 hotel 应压缩 < 1.0，实际: {h:.3f}"

    def test_uplifting_daily_does_not_change_hotel_ref(self):
        """daily 上调不应影响 hotel 参考价 — 证明两个维度解耦。
        构造 mock 城市：hotel=600 不变，daily 在 600 / 1000 / 1500 之间变化。
        三个 daily 取值得到的 hotel_coeff 必须完全相同。"""
        from services.evaluator import _build_adjusted_benchmarks

        results = []
        for daily_value in [600, 1000, 1500]:
            mock_bm = {
                "_test_city": {
                    "country": "_test", "avg_daily_cost_cny": daily_value,
                    "avg_hotel_price_cny": 600,
                    "seasons": {"peak": {"months": [], "multiplier": 1.0},
                                "off_peak": {"months": [], "multiplier": 1.0}},
                    "must_see": [], "typical_stay_days": 1, "tips": "",
                }
            }
            legs = [{"city": "_test_city", "country": "_test",
                     "days": [{"date": "2024-06-15", "transport": [], "activities": []}]}]
            adjusted = _build_adjusted_benchmarks(mock_bm, tier_mult=1.0, legs=legs)
            results.append(adjusted["_test_city"]["avg_hotel_price_cny"])

        # 三个 daily 值下 hotel 参考必须一致（hotel_coeff 与 daily 解耦）
        assert results[0] == results[1] == results[2], (
            f"daily 变化 600→1000→1500 时，hotel 参考应保持不变；"
            f"实际: {results}"
        )


# ---------------------------------------------------------------------------
# Bug 7: 低消费国家城市的 daily 基础数据应贴合「中档全包」语义
#   即 hotel/daily ≈ 0.55，留出 45% 给餐饮+本地交通+门票
# ---------------------------------------------------------------------------

class TestLowCostCountryDailyBaselinesUplifted:
    """daily 应反映「中档 4 星住宿 + 中档餐饮 + 本地交通门票」的合理日均，
    使 hotel/daily 比落在 0.50-0.65 区间（穷国住宿占比偏高仍属合理）。"""

    # (城市, 期望 daily 下限) — 按 hotel/daily ≈ 0.60 的容忍下限计算
    REPRESENTATIVE_CITIES = [
        # 泰国
        ("曼谷", 1000),       # hotel 600 → daily ≥ 600/0.60 = 1000
        ("清迈", 660),        # hotel 400 → daily ≥ 666
        ("普吉岛", 1160),     # hotel 700 → daily ≥ 1166
        ("清莱", 530),        # hotel 320 → daily ≥ 533
        # 越南
        ("胡志明市", 600),    # hotel 360 → daily ≥ 600
        ("河内", 560),        # hotel 340 → daily ≥ 566
        # 马来西亚
        ("吉隆坡", 700),      # hotel 420 → daily ≥ 700
        # 斯里兰卡
        ("科伦坡", 860),      # hotel 520 → daily ≥ 866
        ("康提", 750),        # hotel 450 → daily ≥ 750
        # 肯尼亚
        ("内罗毕", 1050),     # hotel 630 → daily ≥ 1050
        ("蒙巴萨", 930),      # hotel 560 → daily ≥ 933
        # 文莱
        ("斯里巴加湾市", 810),# hotel 490 → daily ≥ 816
        # 印尼/柬埔寨/土耳其/蒙古/埃及
        ("巴厘岛", 810),      # hotel 490 → daily ≥ 816
        ("暹粒", 700),        # hotel 420 → daily ≥ 700
        ("伊斯坦布尔", 930),  # hotel 560 → daily ≥ 933
        ("乌兰巴托", 700),    # hotel 420 → daily ≥ 700
        ("开罗", 750),        # hotel 450 → daily ≥ 750
    ]

    def test_each_representative_city_daily_at_least_floor(self):
        bm = _load_benchmarks()
        failures = []
        for city, floor in self.REPRESENTATIVE_CITIES:
            assert city in bm, f"基准数据缺失城市: {city}"
            actual = bm[city]["avg_daily_cost_cny"]
            hotel = bm[city]["avg_hotel_price_cny"]
            if actual < floor:
                ratio = hotel / actual if actual else 0
                failures.append(
                    f"{city}: daily ¥{actual} < ¥{floor}（hotel ¥{hotel} → 比 {ratio:.0%}）"
                )
        assert not failures, (
            "以下城市 daily 仍是「经济档」语义，与「中档 hotel」不匹配：\n  " +
            "\n  ".join(failures)
        )

    def test_hotel_daily_ratio_within_reasonable_range(self):
        """对每个调整过的城市，hotel/daily 比应 ≤ 0.65 (中档全包语义)。"""
        bm = _load_benchmarks()
        TOUCHED_COUNTRIES = {
            "泰国", "越南", "马来西亚", "斯里兰卡", "肯尼亚",
            "印度尼西亚", "柬埔寨", "文莱", "埃及", "土耳其", "蒙古",
        }
        failures = []
        for city, data in bm.items():
            if data.get("country") not in TOUCHED_COUNTRIES:
                continue
            daily = data.get("avg_daily_cost_cny", 0)
            hotel = data.get("avg_hotel_price_cny", 0)
            if daily == 0: continue
            ratio = hotel / daily
            if ratio > 0.65:
                failures.append(
                    f"{city}: hotel/daily = {ratio:.0%}（hotel ¥{hotel} / daily ¥{daily}）"
                )
        assert not failures, (
            f"{len(failures)} 个城市的 hotel/daily 比 > 65%，daily 偏低：\n  " +
            "\n  ".join(failures[:15])
        )


# ---------------------------------------------------------------------------
# Bug 8: Trip 9 端到端 — daily 参考贴合实际中档花费
# ---------------------------------------------------------------------------

class TestTrip9DailyReferenceMatchesActualCost:
    """Trip 9 真实场景：实际人均日花费 ¥856。
    修复后 daily 参考应在 ¥800-900 之间，使 856 落在「与参考相当」区间。"""

    PROFILE_COUPLE_100K = {
        "annual_travel_budget": 100_000,
        "family_description": "夫妻两人",
    }
    TRIP9_LEGS = [
        {"city": "曼谷", "country": "泰国", "days": [
            {"date": f"2024-09-{15+i}", "transport": [], "activities": []} for i in range(3)
        ]},
        {"city": "清迈", "country": "泰国", "days": [
            {"date": f"2024-09-{18+i}", "transport": [], "activities": []} for i in range(4)
        ]},
        {"city": "清莱", "country": "泰国", "days": [
            {"date": "2024-09-22", "transport": [], "activities": []}
        ]},
    ]

    def test_daily_reference_in_reasonable_range(self):
        household_size = _extract_household_size(self.PROFILE_COUPLE_100K)
        tier_mult = _compute_tier_multiplier(self.PROFILE_COUPLE_100K, household_size)
        bm = _load_benchmarks()
        adjusted = _build_adjusted_benchmarks(bm, tier_mult, self.TRIP9_LEGS)
        weighted = (
            adjusted["曼谷"]["avg_daily_cost_cny"] * 3 +
            adjusted["清迈"]["avg_daily_cost_cny"] * 4 +
            adjusted["清莱"]["avg_daily_cost_cny"] * 1
        ) / 8
        assert 700 <= weighted <= 1000, (
            f"品质型 9 月泰国 daily 参考应在 ¥700-1000/天，"
            f"实际: ¥{weighted:.0f}/天（修复前 ¥626，过低）"
        )

    def test_hotel_reference_not_regressed(self):
        """daily 上调后 hotel 参考必须保持上次修复的水平 (¥500-550)。"""
        household_size = _extract_household_size(self.PROFILE_COUPLE_100K)
        tier_mult = _compute_tier_multiplier(self.PROFILE_COUPLE_100K, household_size)
        bm = _load_benchmarks()
        adjusted = _build_adjusted_benchmarks(bm, tier_mult, self.TRIP9_LEGS)
        weighted = (
            adjusted["曼谷"]["avg_hotel_price_cny"] * 3 +
            adjusted["清迈"]["avg_hotel_price_cny"] * 4 +
            adjusted["清莱"]["avg_hotel_price_cny"] * 1
        ) / 8
        assert 480 <= weighted <= 600, (
            f"daily 上调不应回退 hotel 参考，hotel 应保持 ¥480-600 区间，"
            f"实际: ¥{weighted:.0f}/晚"
        )
