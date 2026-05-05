"""肯尼亚 safari/lake 城市基准缺失 — RED tests.

根因:
  city_benchmarks.json 仅包含肯尼亚的城市/海滨条目（内罗毕/蒙巴萨/马林迪），
  缺失 野生动物保护区 / 湖区 类城市（马赛马拉国家保护区 / 纳库鲁 / 奈瓦沙）。
  评价器对这三类城市回退到 _country_defaults["肯尼亚"] 的 ¥560 hotel /
  ¥1020 daily — 该默认值是按城市/海滨平均建立，与 safari 营地实际
  ¥2200-5000/晚的价位相差 3-9 倍。

  典型症状（trip 13 = 11 天 5 城肯尼亚 safari 行程）:
    - 实际平均住宿 ¥1963/晚（含 5 晚 ¥3220 JW 万豪 Mara）
    - 评价显示参考 ¥685/晚 → "高于参考价" 错误扣分
    - 实际人均日花费 ¥3088
    - 评价显示参考 ¥1158/天 → "高于参考 167%" 严重错判

修复:
  在 city_benchmarks.json 内为这三个城市添加 safari/lake 档位的基准
  （hotel/daily ≈ 0.55-0.60，对齐项目 "中档全包" 语义）。
  必须不动 _country_defaults["肯尼亚"]、不动现有的 内罗毕/蒙巴萨/马林迪 ——
  surgical 原则：本次只补缺失档位，不调既有档位。
"""
import json
from pathlib import Path

from services.evaluator import (
    _build_adjusted_benchmarks,
    _compute_accommodation_metrics,
    _compute_cost_metrics,
    _compute_tier_multiplier,
    _extract_household_size,
    _load_benchmarks,
)


_DATA = Path(__file__).resolve().parents[1] / "data" / "city_benchmarks.json"


def _raw_data():
    """直接读 JSON 拿 _country_defaults（_load_benchmarks 已 pop 出去了）。"""
    with open(_DATA, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Bug A: 三个 safari/lake 城市基准必须存在
# ---------------------------------------------------------------------------

class TestSafariCitiesBenchmarkExists:
    SAFARI_CITIES = ["马赛马拉国家保护区", "纳库鲁", "奈瓦沙"]

    def test_each_safari_city_in_benchmarks(self):
        bm = _load_benchmarks()
        missing = [c for c in self.SAFARI_CITIES if c not in bm]
        assert not missing, (
            f"city_benchmarks.json 缺失肯尼亚野生动物/湖区城市: {missing}；"
            f"这些城市当前回退到 _country_defaults[肯尼亚]=¥560/¥1020 (城市/海滨档)，"
            f"与 safari 营地实际 ¥2200-5000/晚 严重不符"
        )

    def test_each_safari_city_has_country_kenya(self):
        bm = _load_benchmarks()
        for city in self.SAFARI_CITIES:
            assert city in bm, f"{city} 不在 benchmarks"
            assert bm[city].get("country") == "肯尼亚", (
                f"{city} 应标记国家=肯尼亚，实际: {bm[city].get('country')!r}"
            )


# ---------------------------------------------------------------------------
# Bug B: Mara 等 safari 城市的 hotel/daily 必须达到 safari 档位
# ---------------------------------------------------------------------------

class TestSafariBenchmarkValues:
    """safari 营地（Mara/Nakuru）/ lake lodge（Naivasha）应在 safari 档位，
    不能停在 ¥600 城市档。"""

    def test_mara_hotel_at_safari_lodge_floor(self):
        bm = _load_benchmarks()
        hotel = bm["马赛马拉国家保护区"]["avg_hotel_price_cny"]
        # 马赛马拉营地中档 4 星水平（如 Mara Sopa / Sarova Mara）
        # 实际 ¥1800-2900；JW 万豪等 mid-luxury 在 ¥3000+。基准取中位偏上。
        assert hotel >= 2200, (
            f"马赛马拉国家保护区 hotel 基准应 ≥ ¥2200/晚（safari 营地中档），"
            f"实际: ¥{hotel}"
        )

    def test_mara_daily_includes_park_and_drive(self):
        bm = _load_benchmarks()
        daily = bm["马赛马拉国家保护区"]["avg_daily_cost_cny"]
        # 园区入场费 $100/天 ≈ ¥720 + 游猎车包车摊 + 餐饮 → 中档 4000+
        assert daily >= 3800, (
            f"马赛马拉 daily 应 ≥ ¥3800/天（含园区入场费 + 游猎车 + 全餐），"
            f"实际: ¥{daily}"
        )

    def test_nakuru_hotel_at_lake_lodge_floor(self):
        bm = _load_benchmarks()
        hotel = bm["纳库鲁"]["avg_hotel_price_cny"]
        # Lake Nakuru lodges (Sarova Lion Hill / Lake Nakuru Sopa): ¥1200-2200
        assert hotel >= 1300, (
            f"纳库鲁 hotel 基准应 ≥ ¥1300/晚（湖区 lodge 中档），实际: ¥{hotel}"
        )

    def test_naivasha_hotel_at_lake_lodge_floor(self):
        bm = _load_benchmarks()
        hotel = bm["奈瓦沙"]["avg_hotel_price_cny"]
        # Naivasha lodges (Sopa / Crayfish Camp): ¥800-1500
        assert hotel >= 900, (
            f"奈瓦沙 hotel 基准应 ≥ ¥900/晚（湖区 lodge 中档），实际: ¥{hotel}"
        )

    def test_mara_costs_more_than_nakuru_more_than_naivasha(self):
        """档位排序：Mara (旗舰 safari) > Nakuru (湖区+小园) > Naivasha (近郊湖)。"""
        bm = _load_benchmarks()
        m = bm["马赛马拉国家保护区"]["avg_hotel_price_cny"]
        n = bm["纳库鲁"]["avg_hotel_price_cny"]
        v = bm["奈瓦沙"]["avg_hotel_price_cny"]
        assert m > n > v, (
            f"档位应递减：马赛马拉(¥{m}) > 纳库鲁(¥{n}) > 奈瓦沙(¥{v})"
        )

    def test_mara_costs_more_than_nairobi_city_hotel(self):
        """野奢营地必须显著高于内罗毕城市酒店（否则等于 fallback 失效）。"""
        bm = _load_benchmarks()
        mara = bm["马赛马拉国家保护区"]["avg_hotel_price_cny"]
        nairobi = bm["内罗毕"]["avg_hotel_price_cny"]
        assert mara >= nairobi * 3, (
            f"马赛马拉营地应至少为内罗毕城市酒店的 3 倍；"
            f"Mara ¥{mara} vs 内罗毕 ¥{nairobi}（比 {mara/nairobi:.1f}x）"
        )


# ---------------------------------------------------------------------------
# Bug C: hotel/daily 比落在「中档全包」语义区间
# ---------------------------------------------------------------------------

class TestSafariHotelDailyRatio:
    """与项目 dest_coefficient_split 锁定的 0.50-0.65 区间一致。"""

    SAFARI_CITIES = ["马赛马拉国家保护区", "纳库鲁", "奈瓦沙"]

    def test_each_city_ratio_within_band(self):
        bm = _load_benchmarks()
        failures = []
        for city in self.SAFARI_CITIES:
            hotel = bm[city]["avg_hotel_price_cny"]
            daily = bm[city]["avg_daily_cost_cny"]
            ratio = hotel / daily
            if not (0.50 <= ratio <= 0.65):
                failures.append(
                    f"{city}: hotel/daily = {ratio:.2f} "
                    f"(¥{hotel}/¥{daily})，期望 0.50-0.65"
                )
        assert not failures, "safari 城市 hotel/daily 比超出中档全包带:\n  " + "\n  ".join(failures)


# ---------------------------------------------------------------------------
# Bug D: 不破坏现状（surgical）
# ---------------------------------------------------------------------------

class TestSurgicalScope:
    """本次修复必须不动既有的 _country_defaults['肯尼亚'] 与城市/海滨条目，
    避免误抬其他 Kenya 行程的参考价。"""

    def test_country_default_unchanged(self):
        raw = _raw_data()
        kenya = raw["_country_defaults"]["肯尼亚"]
        assert kenya["avg_hotel_price_cny"] == 560, (
            f"_country_defaults[肯尼亚] hotel 不应改动；实际: ¥{kenya['avg_hotel_price_cny']}"
        )
        assert kenya["avg_daily_cost_cny"] == 1020, (
            f"_country_defaults[肯尼亚] daily 不应改动；实际: ¥{kenya['avg_daily_cost_cny']}"
        )

    def test_existing_kenya_cities_unchanged(self):
        bm = _load_benchmarks()
        # 内罗毕保留城市档位
        assert bm["内罗毕"]["avg_hotel_price_cny"] == 630
        assert bm["内罗毕"]["avg_daily_cost_cny"] == 1150
        # 蒙巴萨/马林迪 海滨档位
        assert bm["蒙巴萨"]["avg_hotel_price_cny"] == 560
        assert bm["蒙巴萨"]["avg_daily_cost_cny"] == 1020
        assert bm["马林迪"]["avg_hotel_price_cny"] == 520
        assert bm["马林迪"]["avg_daily_cost_cny"] == 950

    def test_safari_cities_must_see_optional(self):
        """新增条目 must_see 可为空 — 当前 trip 13 的 safari leg 覆盖率
        来自空 must_see→100% 路径，本次修复不应回归这一行为。"""
        bm = _load_benchmarks()
        for city in ["马赛马拉国家保护区", "纳库鲁", "奈瓦沙"]:
            ms = bm[city].get("must_see", [])
            assert isinstance(ms, list), f"{city}.must_see 必须是 list"


# ---------------------------------------------------------------------------
# Bug E: Trip 13 端到端 — 修复后 评分应大幅好转
# ---------------------------------------------------------------------------

class TestTrip13EndToEnd:
    """合成与 trip 13 同形态的 11 天 / 1 人肯尼亚 safari 行程，
    断言修复后住宿与花费的市场参考贴近真实 safari 档。"""

    PROFILE_QUALITY = {
        "annual_travel_budget": 100_000,
        "family_description": "夫妻两人",
    }

    @staticmethod
    def _build_legs():
        """5 城：内罗毕 3 + 马赛马拉 5 + 纳库鲁 1 + 奈瓦沙 1 + 北京 1（返程）。"""
        return [
            {"id": 1, "city": "内罗毕", "country": "肯尼亚", "days": [
                {"date": "2025-05-01", "day_number": 1, "transport": ["多哈→内罗毕"], "activities": ["多哈国际机场"], "accommodation": "Swiss Lenana"},
                {"date": "2025-05-07", "day_number": 7, "transport": [], "activities": ["JW Marriott Mara"], "accommodation": "Swiss Lenana"},
                {"date": "2025-05-10", "day_number": 10, "transport": [], "activities": ["肯尼亚国家博物馆"], "accommodation": None},
            ]},
            {"id": 2, "city": "马赛马拉国家保护区", "country": "肯尼亚", "days": [
                {"date": f"2025-05-{2+i:02d}", "day_number": 2+i, "transport": [], "activities": ["游猎"], "accommodation": "马赛马拉JW万豪酒店"}
                for i in range(5)
            ]},
            {"id": 3, "city": "纳库鲁", "country": "肯尼亚", "days": [
                {"date": "2025-05-08", "day_number": 8, "transport": [], "activities": ["纳库鲁湖国家公园"], "accommodation": "Buraha Zenoni"},
            ]},
            {"id": 4, "city": "奈瓦沙", "country": "肯尼亚", "days": [
                {"date": "2025-05-09", "day_number": 9, "transport": [], "activities": ["奈瓦沙湖", "新月岛"], "accommodation": "Swiss Lenana"},
            ]},
            {"id": 5, "city": "北京", "country": "中国", "days": [
                {"date": "2025-05-11", "day_number": 11, "transport": [], "activities": [], "accommodation": None},
            ]},
        ]

    @staticmethod
    def _build_expenses():
        """模拟 trip 13 实际支出：5 晚 Mara JW 万豪 ¥3220 + 4 晚 Lenana ¥490-538，
        加上一次大交通 ¥17830，其他餐饮等略。"""
        items = []
        # Mara JW 万豪 5 晚
        for i in range(5):
            items.append({
                "id": 100 + i, "amount": 3220.0, "category": "住宿",
                "description": "马赛马拉JW万豪酒店",
                "date": f"2025-05-{3+i:02d}", "leg_id": None,
            })
        # Lenana 4 晚
        for d in ["2025-05-01", "2025-05-02", "2025-05-07", "2025-05-09"]:
            items.append({
                "id": 200, "amount": 538.34, "category": "住宿",
                "description": "勒纳纳蒙特瑞士酒店", "date": d, "leg_id": None,
            })
        # 大交通
        items.append({
            "id": 300, "amount": 17830.0, "category": "交通",
            "description": "多哈→内罗毕航班", "date": "2025-05-01", "leg_id": None,
        })
        return items

    def _adjusted(self):
        legs = self._build_legs()
        size = _extract_household_size(self.PROFILE_QUALITY)
        tier = _compute_tier_multiplier(self.PROFILE_QUALITY, size)
        bm = _load_benchmarks()
        adjusted = _build_adjusted_benchmarks(bm, tier, legs)
        return adjusted, legs

    def test_mara_resolved_to_safari_benchmark_not_country_default(self):
        """关键回归：马赛马拉 leg 必须解析到城市 safari 基准，
        不应再落到 _country_defaults['肯尼亚'] 的 ¥560 hotel。"""
        adjusted, _ = self._adjusted()
        mara = adjusted["马赛马拉国家保护区"]
        # 修复前: 560 * 1.22 * 1.0 * dest_coeff ≈ 720
        # 修复后: ≥ 2200 * 1.22 * 0.75(off_peak) * dest_coeff_floor 0.75 ≈ 1500+
        assert mara["avg_hotel_price_cny"] >= 1300, (
            f"马赛马拉 adjusted hotel 应 ≥ ¥1300/晚 (落到 safari 档基准)，"
            f"实际 ¥{mara['avg_hotel_price_cny']}/晚"
        )

    def test_accommodation_market_avg_realistic(self):
        """trip 13 形态下，加权 hotel 参考必须显著高于 ¥685（修复前）。"""
        adjusted, legs = self._adjusted()
        expenses = self._build_expenses()
        m = _compute_accommodation_metrics(legs, expenses, adjusted, traveler_count=1)
        # 修复前: ¥685；修复后基于 5 晚 Mara 主导，应 ≥ ¥1100
        assert m["market_avg"] >= 1100, (
            f"住宿加权参考应 ≥ ¥1100/晚 (主导是 5 晚 safari)，"
            f"实际 ¥{m['market_avg']}/晚（修复前 ¥685）"
        )
        # 平均每晚 ¥1963 不应再被判为「严重高于参考」
        ratio = m["avg_nightly"] / m["market_avg"]
        assert ratio < 2.0, (
            f"实际 ¥{m['avg_nightly']}/晚 vs 参考 ¥{m['market_avg']}/晚 "
            f"= {ratio:.2f}x，仍被错判为严重偏高（修复前 2.87x）"
        )

    def test_accommodation_score_no_longer_punished(self):
        """住宿子分应明显回升（修复前 74，目标修复后 ≥ 80）。"""
        adjusted, legs = self._adjusted()
        expenses = self._build_expenses()
        m = _compute_accommodation_metrics(legs, expenses, adjusted, traveler_count=1)
        assert m["score"] >= 80, (
            f"住宿评分应 ≥ 80（修复前 74），实际: {m['score']}"
        )

    def test_cost_market_avg_realistic(self):
        """日均花费的 weighted_market 应反映 safari 高消费，不再 ¥1158。"""
        adjusted, legs = self._adjusted()
        expenses = self._build_expenses()
        trip = {"traveler_count": 1, "expenses": expenses}
        m = _compute_cost_metrics(trip, legs, expenses, adjusted)
        # 修复前: ¥1158；修复后 5 晚 Mara 主导，应 ≥ ¥2000
        assert m["market_avg"] >= 2000, (
            f"日均参考应 ≥ ¥2000/天 (5 晚 safari 加权主导)，"
            f"实际 ¥{m['market_avg']}/天（修复前 ¥1158）"
        )

    def test_cost_score_no_longer_in_red(self):
        """花费评分应明显回升（修复前 32 = 红字告警，目标 ≥ 70）。"""
        adjusted, legs = self._adjusted()
        expenses = self._build_expenses()
        trip = {"traveler_count": 1, "expenses": expenses}
        m = _compute_cost_metrics(trip, legs, expenses, adjusted)
        assert m["score"] >= 70, (
            f"花费评分应 ≥ 70（修复前 32），实际: {m['score']}；"
            f"savings_pct={m['savings_pct']}, ratio={m['per_person_per_day']/m['market_avg']:.2f}"
        )
