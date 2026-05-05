"""非游览 leg（中转 / 起讫点）不应污染各维度的市场参考与覆盖率分母。

真实场景（trip 10：北京→文莱中转→伦敦→爱丁堡→北京返程）：
  - 文莱：5 小时中转，无任何 activity
  - 北京：返程终点站，无 activity / 住宿 / transport

四个维度都受影响：
  1. attractions：把这两个 leg 的 0% 覆盖加权进总分，整体覆盖率被拉低
  2. accommodation：market_avg 把没住宿的城市基准计入平均，参考价偏低
  3. cost：market_avg 把无消费天的城市基准计入平均，使 ratio 失真
  4. transport：coverage 按"全部天数"算，要求每天都有 transport 记录
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import (
    _compute_attractions_metrics,
    _compute_accommodation_metrics,
    _compute_cost_metrics,
    _compute_transport_metrics,
    _evaluate_city,
    _is_non_sightseeing_leg,
    generate_evaluation,
)


# ---------------------------------------------------------------------------
# trip 10 真实数据 fixture
# ---------------------------------------------------------------------------

def _trip10_legs():
    """重现 trip 10 的 leg 结构：文莱中转 + 伦敦+爱丁堡游览 + 北京返程。"""
    return [
        {
            "id": 79,
            "city": "斯里巴加湾市",
            "country": "文莱",
            "days": [
                {
                    "day_number": 1,
                    "date": "2024-09-28",
                    "activities": [],
                    "accommodation": "伦敦摄政公园万豪酒店",
                    "transport": [
                        "BI624:北京→斯里巴加湾市",
                        "斯里巴加湾市→伦敦",
                    ],
                },
            ],
        },
        {
            "id": 80,
            "city": "伦敦",
            "country": "英国",
            "days": [
                {
                    "day_number": 2,
                    "date": "2024-09-29",
                    "activities": ["大英博物馆"],
                    "accommodation": "伦敦摄政公园万豪酒店",
                    "transport": [],
                },
                {
                    "day_number": 3,
                    "date": "2024-09-30",
                    "activities": ["杜莎夫人蜡像馆", "贝克街", "西敏寺"],
                    "accommodation": "伦敦摄政公园万豪酒店",
                    "transport": [],
                },
                {
                    "day_number": 4,
                    "date": "2024-10-01",
                    "activities": [
                        "圣保罗座堂", "伦敦大火纪念碑", "伦敦塔桥",
                        "伦敦塔", "Westminster Abbey", "大本钟", "伦敦眼",
                    ],
                    "accommodation": "伦敦摄政公园万豪酒店",
                    "transport": [],
                },
                {
                    "day_number": 5,
                    "date": "2024-10-02",
                    "activities": ["海德公园", "白金汉宫", "格林威治天文台"],
                    "accommodation": "伦敦摄政公园万豪酒店",
                    "transport": [],
                },
                {
                    "day_number": 10,
                    "date": "2024-10-07",
                    "activities": ["希思罗机场"],
                    "accommodation": None,
                    "transport": [
                        "U2301:爱丁堡→伦敦",
                        "伦敦→北京",
                    ],
                },
            ],
        },
        {
            "id": 81,
            "city": "爱丁堡",
            "country": "英国",
            "days": [
                {
                    "day_number": 6,
                    "date": "2024-10-03",
                    "activities": ["爱丁堡城堡"],
                    "accommodation": "爱丁堡官邸万豪居家酒店",
                    "transport": ["U2308:伦敦→爱丁堡"],
                },
                {
                    "day_number": 7,
                    "date": "2024-10-04",
                    "activities": ["苏格兰三日游", "罗蒙湖猛禽中心"],
                    "accommodation": "苏格兰三日游",
                    "transport": [],
                },
                {
                    "day_number": 8,
                    "date": "2024-10-05",
                    "activities": ["波特里湾", "苏格兰裙岩悬崖", "尼斯湖"],
                    "accommodation": None,
                    "transport": [],
                },
                {
                    "day_number": 9,
                    "date": "2024-10-06",
                    "activities": ["皮特洛赫里大坝", "福斯桥", "圣安德鲁斯大教堂"],
                    "accommodation": "爱丁堡机场moxy酒店",
                    "transport": [],
                },
            ],
        },
        {
            "id": 82,
            "city": "北京",
            "country": "中国",
            "days": [
                {
                    "day_number": 11,
                    "date": "2024-10-08",
                    "activities": [],
                    "accommodation": None,
                    "transport": [],
                },
            ],
        },
    ]


def _trip10_benchmarks():
    """对应基准：使用 city_benchmarks.json 中的真实数据简化版。"""
    return {
        "斯里巴加湾市": {
            "country": "文莱",
            "avg_daily_cost_cny": 826,
            "avg_hotel_price_cny": 413,
            "must_see": [
                "奥马尔·阿里·赛福鼎清真寺",
                "水上村落",
                "杰鲁东公园",
                "苏丹皇宫",
                "皇家典藏馆",
                "淡布隆国家公园",
            ],
            "typical_stay_days": 2,
        },
        "伦敦": {
            "country": "英国",
            "avg_daily_cost_cny": 2554,
            "avg_hotel_price_cny": 1509,
            "must_see": [
                "大本钟", "伦敦塔桥", "白金汉宫",
                "大英博物馆", "伦敦眼", "海德公园", "西敏寺",
            ],
            "typical_stay_days": 4,
        },
        "爱丁堡": {
            "country": "英国",
            "avg_daily_cost_cny": 1881,
            "avg_hotel_price_cny": 1075,
            "must_see": [
                "爱丁堡城堡", "皇家英里", "亚瑟王座",
                "荷里路德宫", "卡尔顿山", "苏格兰国家博物馆", "王子街花园",
            ],
            "typical_stay_days": 3,
        },
        "北京": {
            "country": "中国",
            "avg_daily_cost_cny": 1220,
            "avg_hotel_price_cny": 763,
            "must_see": ["故宫", "天安门广场", "长城", "颐和园", "天坛", "南锣鼓巷", "鸟巢"],
            "typical_stay_days": 4,
        },
    }


def _trip10_expenses():
    """住宿 14427 / 8 晚 / 2 人 → 单晚单人约 902；
    地面消费 26646（用于 cost ratio 验算）。"""
    return [
        {"category": "住宿", "amount": 1489, "date": "2024-09-28"},
        {"category": "住宿", "amount": 1489, "date": "2024-09-29"},
        {"category": "住宿", "amount": 1489, "date": "2024-09-30"},
        {"category": "住宿", "amount": 1489, "date": "2024-10-01"},
        {"category": "住宿", "amount": 1489, "date": "2024-10-02"},
        {"category": "住宿", "amount": 710, "date": "2024-10-03"},
        {"category": "住宿", "amount": 5638, "date": "2024-10-04"},
        {"category": "住宿", "amount": 634, "date": "2024-10-06"},
        {"category": "交通", "amount": 11352, "date": "2024-09-28",
         "description": "北京到斯里巴加湾市的交通预算 x2"},
        {"category": "交通", "amount": 945, "date": "2024-10-03",
         "description": "伦敦到爱丁堡的交通预算"},
        {"category": "交通", "amount": 566, "date": "2024-10-07",
         "description": "爱丁堡到伦敦的交通预算"},
        {"category": "交通", "amount": 2233, "date": "2024-09-28", "description": "交通"},
        {"category": "餐饮", "amount": 2893, "date": "2024-09-28", "description": "美食"},
        {"category": "门票", "amount": 2001, "date": "2024-09-28", "description": "GOCITY"},
        {"category": "门票", "amount": 396, "date": "2024-09-29", "description": "大英博物馆"},
        {"category": "门票", "amount": 718, "date": "2024-10-03", "description": "爱丁堡城堡"},
        {"category": "门票", "amount": 918, "date": "2024-09-28", "description": "活动"},
        {"category": "门票", "amount": 352, "date": "2024-09-28"},
        {"category": "门票", "amount": 4.69, "date": "2024-09-28"},
        {"category": "其他", "amount": 524, "date": "2024-09-28", "description": "保险"},
        {"category": "其他", "amount": 2178, "date": "2024-09-28", "description": "签证"},
    ]


# ---------------------------------------------------------------------------
# Helper: _is_non_sightseeing_leg
# ---------------------------------------------------------------------------

class TestIsNonSightseeingLeg:
    """非游览 leg 判定：所有 days 无 activity → True。"""

    def test_brunei_transit_leg_is_non_sightseeing(self):
        """文莱中转日：transport 是跨城但 activities=[] → 非游览。"""
        leg = _trip10_legs()[0]
        assert _is_non_sightseeing_leg(leg) is True

    def test_beijing_endpoint_leg_is_non_sightseeing(self):
        """北京返程终点：activities=[] / transport=[] / accommodation=None → 非游览。"""
        leg = _trip10_legs()[3]
        assert _is_non_sightseeing_leg(leg) is True

    def test_london_actual_visit_is_sightseeing(self):
        """伦敦：含游览活动 → 必须是游览 leg。"""
        leg = _trip10_legs()[1]
        assert _is_non_sightseeing_leg(leg) is False

    def test_edinburgh_actual_visit_is_sightseeing(self):
        leg = _trip10_legs()[2]
        assert _is_non_sightseeing_leg(leg) is False

    def test_single_activity_makes_leg_sightseeing(self):
        """只要 leg 内任意一天有 activity 就算游览 leg。"""
        leg = {
            "city": "测试城",
            "days": [
                {"activities": [], "transport": ["A→B"], "accommodation": None},
                {"activities": ["景点1"], "transport": [], "accommodation": None},
            ],
        }
        assert _is_non_sightseeing_leg(leg) is False

    def test_empty_days_treated_as_non_sightseeing(self):
        """没有任何 day 的 leg（极端情况）→ 视为非游览。"""
        assert _is_non_sightseeing_leg({"city": "X", "days": []}) is True


# ---------------------------------------------------------------------------
# 维度 1: attractions
# ---------------------------------------------------------------------------

class TestAttractionsExcludesNonSightseeing:

    def test_brunei_and_beijing_excluded_from_overall_coverage(self):
        """trip 10：overall_coverage 应只看伦敦+爱丁堡的加权。

        当前 bug：把文莱(0%)+北京(0%)以 effective_days 加权进分母 → 52%
        修复后：只看伦敦+爱丁堡 → 显著提升至 60% 以上
        """
        m = _compute_attractions_metrics(_trip10_legs(), _trip10_benchmarks())
        assert m["overall_coverage"] >= 60, (
            f"非游览 leg 应排除，预期 >= 60%（仅伦敦+爱丁堡加权），实际 {m['overall_coverage']}%"
        )

    def test_non_sightseeing_cities_marked_in_results(self):
        """城市仍出现在 cities 列表中，但带 non_sightseeing=True 标记。"""
        m = _compute_attractions_metrics(_trip10_legs(), _trip10_benchmarks())
        cities = {c["city"]: c for c in m["cities"]}
        assert cities["斯里巴加湾市"].get("non_sightseeing") is True
        assert cities["北京"].get("non_sightseeing") is True
        assert cities["伦敦"].get("non_sightseeing") in (False, None)

    def test_score_higher_after_excluding_non_sightseeing(self):
        """排除非游览 leg 后景点得分应显著高于 51（旧值）。"""
        m = _compute_attractions_metrics(_trip10_legs(), _trip10_benchmarks())
        assert m["score"] >= 55, f"修复后景点评分应 >= 55，实际 {m['score']}"


# ---------------------------------------------------------------------------
# 维度 2: accommodation
# ---------------------------------------------------------------------------

class TestAccommodationMarketAvgWeightedByNights:

    def test_market_avg_weighted_by_nights_not_simple_leg_average(self):
        """trip 10 真实数据：参考价应按住宿夜数加权。

        当前 bug：按 4 个 leg 平均 → 938（被文莱 413 + 北京 763 拉低）
        修复后：伦敦 5 晚 × 1509 + 爱丁堡 3 晚 × 1075 = 1346
        """
        m = _compute_accommodation_metrics(
            _trip10_legs(), _trip10_expenses(), _trip10_benchmarks(), traveler_count=2
        )
        assert 1200 <= m["market_avg"] <= 1450, (
            f"市场参考价应按住宿夜数加权（仅伦敦+爱丁堡），预期 1200-1450，实际 {m['market_avg']}"
        )

    def test_no_accommodation_legs_dont_appear_in_market_avg(self):
        """文莱 / 北京虽在 legs 列表，但用户实际没在那住宿 → 不参与 market_avg。"""
        legs = [
            {
                "city": "中转城",
                "days": [
                    {"activities": [], "accommodation": None,
                     "transport": ["A→中转城", "中转城→B"]},
                ],
            },
            {
                "city": "游览城",
                "days": [
                    {"activities": ["景点1"], "accommodation": "X酒店", "transport": []},
                    {"activities": ["景点2"], "accommodation": "X酒店", "transport": []},
                ],
            },
        ]
        benchmarks = {
            "中转城": {"avg_hotel_price_cny": 100, "country": ""},
            "游览城": {"avg_hotel_price_cny": 1000, "country": ""},
        }
        expenses = [
            {"category": "住宿", "amount": 800, "date": "2024-01-02"},
            {"category": "住宿", "amount": 800, "date": "2024-01-03"},
        ]
        m = _compute_accommodation_metrics(legs, expenses, benchmarks, traveler_count=1)
        assert m["market_avg"] == 1000, (
            f"无住宿城市不应进 market_avg，预期 1000（仅游览城），实际 {m['market_avg']}"
        )


# ---------------------------------------------------------------------------
# 维度 3: cost
# ---------------------------------------------------------------------------

class TestCostMarketAvgExcludesNonSightseeing:

    def test_cost_market_avg_excludes_brunei_and_beijing(self):
        """trip 10 真实数据：cost market_avg 应排除文莱+北京。

        当前 bug：4 城简单平均 → 1616（被文莱 826+北京 1220 拉低）
        修复后：按 effective_days 加权伦敦+爱丁堡 → ≈2260
        """
        trip = {"traveler_count": 2}
        m = _compute_cost_metrics(
            trip, _trip10_legs(), _trip10_expenses(), _trip10_benchmarks()
        )
        assert 2000 <= m["market_avg"] <= 2400, (
            f"cost market_avg 应排除非游览 leg，预期 2000-2400，实际 {m['market_avg']}"
        )

    def test_cost_score_improves_after_fix(self):
        """trip 10：人均日花费 ≈2400，与品质型伦敦+爱丁堡基准接近持平 → 评分应明显高于旧值 50。"""
        trip = {"traveler_count": 2}
        m = _compute_cost_metrics(
            trip, _trip10_legs(), _trip10_expenses(), _trip10_benchmarks()
        )
        assert m["score"] >= 70, f"修复后 cost 得分应 >= 70，实际 {m['score']}"

    def test_savings_pct_no_longer_minus_50(self):
        """修复后不应再误判为"高于参考 50%"。"""
        trip = {"traveler_count": 2}
        m = _compute_cost_metrics(
            trip, _trip10_legs(), _trip10_expenses(), _trip10_benchmarks()
        )
        assert m["savings_pct"] >= -20, (
            f"修复后 savings_pct 应 >= -20%（基本持平），实际 {m['savings_pct']}%"
        )


# ---------------------------------------------------------------------------
# 维度 4: transport
# ---------------------------------------------------------------------------

class TestTransportCoverageOnlyTransitDays:

    def test_coverage_uses_transit_days_only(self):
        """trip 10：3 个跨城日全部有 transport 记录 → 100%
        当前 bug：分母用全部 11 天 → 27%
        """
        m = _compute_transport_metrics(_trip10_legs())
        assert m["coverage"] == 100, (
            f"跨城日全部有 transport 记录应为 100%，实际 {m['coverage']}%"
        )

    def test_score_full_when_all_transit_days_recorded(self):
        m = _compute_transport_metrics(_trip10_legs())
        assert m["score"] >= 90, f"跨城 transport 完整时 score 应 >= 90，实际 {m['score']}"

    def test_partial_transit_records_partial_coverage(self):
        """3 个 leg 跨城两次，只有一次记录了 transport → 50%。"""
        legs = [
            {
                "city": "北京",
                "days": [
                    {"day_number": 1, "activities": ["天安门"], "accommodation": "酒店",
                     "transport": ["G1:出发地→北京"]},
                ],
            },
            {
                "city": "上海",
                "days": [
                    {"day_number": 2, "activities": ["外滩"], "accommodation": "酒店",
                     "transport": []},
                ],
            },
            {
                "city": "广州",
                "days": [
                    {"day_number": 3, "activities": ["塔"], "accommodation": "酒店",
                     "transport": ["G2:上海→广州"]},
                ],
            },
        ]
        m = _compute_transport_metrics(legs)
        assert m["coverage"] == 100, (
            f"识别到的跨城日全部有记录 → 100%，实际 {m['coverage']}%"
        )

    def test_intra_city_days_no_transport_no_penalty(self):
        """城内日不记 transport（地铁/打车）不应被扣覆盖率。"""
        legs = [
            {
                "city": "巴黎",
                "days": [
                    {"day_number": 1, "activities": ["铁塔"], "accommodation": "酒店",
                     "transport": ["AF888:北京→巴黎"]},
                    {"day_number": 2, "activities": ["卢浮宫"], "accommodation": "酒店",
                     "transport": []},
                    {"day_number": 3, "activities": ["凯旋门"], "accommodation": "酒店",
                     "transport": []},
                ],
            },
        ]
        m = _compute_transport_metrics(legs)
        assert m["coverage"] == 100, f"城内日不该拉低 coverage，实际 {m['coverage']}%"


# ---------------------------------------------------------------------------
# 城市评价：非游览 leg 走简化路径
# ---------------------------------------------------------------------------

class TestEvaluateCityForNonSightseeing:

    def test_brunei_marked_as_transit_in_city_evaluation(self):
        """文莱 leg 进入城市评价时不应打"景点覆盖不足"warning。"""
        leg = _trip10_legs()[0]
        ev = _evaluate_city(leg, [], _trip10_benchmarks())
        warning_texts = [t["text"] for t in ev["tags"] if t["type"] == "warning"]
        assert "景点覆盖不足" not in warning_texts, (
            f"非游览 leg 不应有景点覆盖不足 warning，实际 tags: {ev['tags']}"
        )

    def test_brunei_no_missed_spots_listed(self):
        """文莱不游览 → missed_spots 不展示，避免在 UI 上误导。"""
        leg = _trip10_legs()[0]
        ev = _evaluate_city(leg, [], _trip10_benchmarks())
        assert ev["missed_spots"] == [], (
            f"非游览 leg 不应展示 missed_spots，实际 {ev['missed_spots']}"
        )

    def test_beijing_endpoint_marked_transit(self):
        leg = _trip10_legs()[3]
        ev = _evaluate_city(leg, [], _trip10_benchmarks())
        info_or_positive_tags = [
            t for t in ev["tags"] if t["type"] in ("info", "positive")
        ]
        assert info_or_positive_tags, (
            f"非游览 leg 应有 info/positive 标签标识其性质，实际 tags: {ev['tags']}"
        )


# ---------------------------------------------------------------------------
# 非游览 leg 不应出现在城市评价列表中（用户诉求：纯中转/起讫不该有"评价记录"）
# ---------------------------------------------------------------------------

class TestCitiesListExcludesNonSightseeing:

    def test_brunei_and_beijing_not_in_cities_list(self):
        """trip 10：cities 列表只展示真正游览的伦敦+爱丁堡。"""
        trip_dict = {
            "id": 10,
            "title": "trip10",
            "traveler_count": 2,
            "legs": _trip10_legs(),
            "expenses": _trip10_expenses(),
        }
        result = generate_evaluation(trip_dict, profile=None, past_visited=None)
        city_names = {c["city"] for c in result["evaluation_data"]["cities"]}
        assert "斯里巴加湾市" not in city_names, (
            f"文莱中转不应出现在城市评价列表，实际 cities: {city_names}"
        )
        assert "北京" not in city_names, (
            f"北京终点不应出现在城市评价列表，实际 cities: {city_names}"
        )
        assert city_names == {"伦敦", "爱丁堡"}, (
            f"应只剩游览城市，实际 cities: {city_names}"
        )

    def test_non_sightseeing_still_in_attractions_metrics_for_route_view(self):
        """非游览 leg 仍出现在 attractions metrics 的 cities（让 city_route 完整），
        但不出现在顶层 cities 评价列表。两个列表语义不同：
          - attractions.metrics.cities：路径视图，含全部经过城市
          - evaluation_data.cities：城市评价卡，仅游览城市
        """
        trip_dict = {
            "id": 10,
            "title": "trip10",
            "traveler_count": 2,
            "legs": _trip10_legs(),
            "expenses": _trip10_expenses(),
        }
        result = generate_evaluation(trip_dict, profile=None, past_visited=None)
        attr_cities = {
            c["city"] for c in result["evaluation_data"]["dimensions"]["attractions"]["metrics"]["cities"]
        }
        # 路径视图保留全部 4 城（用于 attractions 的 weight=0 标记展示）
        assert attr_cities == {"斯里巴加湾市", "伦敦", "爱丁堡", "北京"}


# ---------------------------------------------------------------------------
# accommodation coverage 分母也要排除非游览 leg
# ---------------------------------------------------------------------------

class TestAccommodationCoverageExcludesNonSightseeing:

    def test_beijing_endpoint_no_accommodation_does_not_lower_coverage(self):
        """trip 10 真实：北京终点 Day11 无住宿不应被算成「应有住宿但缺失」。

        当前 bug：required_days 把北京 day11 计入 → 8/10 = 80%
        修复后：non_sightseeing leg 整 leg 排除 → 7/8 = 88%（Day8 数据缺失独立问题）
        """
        m = _compute_accommodation_metrics(
            _trip10_legs(), _trip10_expenses(), _trip10_benchmarks(), traveler_count=2
        )
        assert m["coverage"] >= 85, (
            f"非游览 leg 不应拉低住宿覆盖率，预期 >= 85%（排除文莱+北京后），实际 {m['coverage']}%"
        )

    def test_pure_transit_endpoint_does_not_demand_accommodation(self):
        """构造性测试：纯中转/终点 leg 不要求填住宿。"""
        legs = [
            {
                "city": "游览城",
                "days": [
                    {"activities": ["景点1"], "accommodation": "X酒店", "transport": []},
                    {"activities": ["景点2"], "accommodation": "X酒店", "transport": []},
                ],
            },
            {
                "city": "终点城",  # 起讫点：无 activity / 无住宿 / 无 transport
                "days": [
                    {"activities": [], "accommodation": None, "transport": []},
                ],
            },
        ]
        benchmarks = {
            "游览城": {"avg_hotel_price_cny": 1000, "country": ""},
            "终点城": {"avg_hotel_price_cny": 500, "country": ""},
        }
        expenses = [
            {"category": "住宿", "amount": 1000, "date": "2024-01-01"},
            {"category": "住宿", "amount": 1000, "date": "2024-01-02"},
        ]
        m = _compute_accommodation_metrics(legs, expenses, benchmarks, traveler_count=1)
        assert m["coverage"] == 100, (
            f"终点 leg 无住宿不应拉低覆盖率，预期 100%（仅游览城 2/2），实际 {m['coverage']}%"
        )

    def test_brunei_transit_with_accommodation_field_excluded_from_both_sides(self):
        """文莱 leg 虽然 accommodation 字段被填了"伦敦的酒店"（数据录入特殊），
        但 leg 本身是非游览 leg，应整 leg 排除——分子分母同时减 1，
        既不当作"住了"也不当作"应该住"。"""
        # 单独构造：文莱 leg 1 day（with acc, transit）+ 伦敦 leg 2 day（with acc, no transit）
        legs = [
            {
                "city": "斯里巴加湾市",
                "days": [
                    {
                        "activities": [],
                        "accommodation": "伦敦摄政公园万豪酒店",
                        "transport": ["BI624:北京→斯里巴加湾市", "斯里巴加湾市→伦敦"],
                    },
                ],
            },
            {
                "city": "伦敦",
                "days": [
                    {"activities": ["大本钟"], "accommodation": "伦敦酒店", "transport": []},
                    {"activities": ["伦敦塔"], "accommodation": "伦敦酒店", "transport": []},
                ],
            },
        ]
        benchmarks = {
            "斯里巴加湾市": {"avg_hotel_price_cny": 350, "country": "文莱"},
            "伦敦": {"avg_hotel_price_cny": 1300, "country": "英国"},
        }
        expenses = [
            {"category": "住宿", "amount": 1300, "date": "2024-01-01"},
            {"category": "住宿", "amount": 1300, "date": "2024-01-02"},
        ]
        m = _compute_accommodation_metrics(legs, expenses, benchmarks, traveler_count=1)
        # 排除文莱整 leg → required_days = 2，has = 2 → coverage = 100%
        assert m["coverage"] == 100, m
        # market_avg 也只看伦敦 → 1300（不被文莱 350 拉低）
        assert m["market_avg"] == 1300, m
