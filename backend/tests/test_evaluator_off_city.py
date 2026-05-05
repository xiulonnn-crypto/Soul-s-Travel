"""基地式多日游识别（off-city day）：以 X 为基地玩 Y/Z 时降低 X leg 的覆盖率分母。

真实场景（trip 10 爱丁堡）：
  - Day6: 爱丁堡城堡（市内日）
  - Day7: 苏格兰高地团 — 罗蒙湖、格伦科、威廉堡（不在爱丁堡市内）
  - Day8: 天空岛 — 波特里、裙岩悬崖、尼斯湖（不在爱丁堡市内）
  - Day9: 皮特洛赫里、福斯桥、圣安德鲁斯（不在爱丁堡市内）

当前算法把这 4 天都算成爱丁堡的 effective_days，分母 4 天但分子只有
"爱丁堡城堡" 1 个 → 覆盖率 14%，把整体加权拉到 54%。

修复后：识别 Day7/8/9 是 off-city day（活动不匹配爱丁堡必去清单也不含
"爱丁堡"），从 effective_days 中折减 0.7/天，反映用户实际只在爱丁堡市内
消耗了少数日子。

设计原则：
  - off-city day = 非交通日 + 非空 activities + 所有 activities 都不匹配
    leg 城市必去清单（含 OCR 容错）也不含 leg 城市名
  - 每个 off-city day 从 effective_days 扣减 0.7（保留 0.3 反映用户至少
    在该城落地睡过）
  - 与 transit_day 互斥（transit_day 已有 0.5 折减）
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import _compute_attractions_metrics


BENCHMARKS_EDINBURGH = {
    "爱丁堡": {
        "country": "英国",
        "avg_daily_cost_cny": 1750,
        "must_see": [
            "爱丁堡城堡", "皇家英里", "亚瑟王座",
            "荷里路德宫", "卡尔顿山", "苏格兰国家博物馆", "王子街花园",
        ],
        "typical_stay_days": 3,
    }
}


def _edinburgh_basecamp_leg():
    """复现 trip 10 爱丁堡 leg：以爱丁堡为基地的苏格兰高地多城游。"""
    return {
        "city": "爱丁堡",
        "country": "英国",
        "days": [
            {
                "day_number": 6,
                "activities": ["爱丁堡城堡"],
                "accommodation": "爱丁堡官邸万豪居家酒店",
                "transport": ["U2308:伦敦→爱丁堡"],
            },
            {
                "day_number": 7,
                "activities": ["苏格兰三日游", "罗蒙湖猛禽中心", "格伦科峡谷", "威廉堡火车站"],
                "accommodation": "苏格兰三日游",
                "transport": [],
            },
            {
                "day_number": 8,
                "activities": ["波特里湾", "苏格兰裙岩悬崖", "米尔特湖", "尼斯湖"],
                "accommodation": None,
                "transport": [],
            },
            {
                "day_number": 9,
                "activities": ["皮特洛赫里大坝和鲑鱼台阶", "福斯桥", "圣安德鲁斯大教堂"],
                "accommodation": "爱丁堡机场moxy酒店",
                "transport": [],
            },
        ],
    }


class TestOffCityDayDetection:
    """识别 off-city day 并从 effective_days 折减。"""

    def test_edinburgh_basecamp_effective_days_reduced(self):
        """爱丁堡 leg：1 transit + 3 off-city → effective_days 应明显小于 3.5（旧值）。

        旧值：4 - 1×0.5 - 0×0.7 = 3.5
        新值：4 - 1×0.5 - 3×0.7 = 1.4
        """
        m = _compute_attractions_metrics([_edinburgh_basecamp_leg()], BENCHMARKS_EDINBURGH)
        city = m["cities"][0]
        assert city["effective_days"] <= 2.0, (
            f"基地式 leg 应折减大量 effective_days，预期 <= 2.0，实际 {city['effective_days']}"
        )
        assert city["effective_days"] >= 0.5, (
            f"effective_days 不应被折减到完全无效，实际 {city['effective_days']}"
        )

    def test_edinburgh_basecamp_adjusted_coverage_higher_than_raw(self):
        """基地式 leg：调整后覆盖率应明显高于原始 14%（短停留期望降低）。

        旧值：14% / (3.5/3 cap 1.0) = 14%
        新值：14% / (1.4/3 ≈ 0.467) ≈ 30%
        """
        m = _compute_attractions_metrics([_edinburgh_basecamp_leg()], BENCHMARKS_EDINBURGH)
        city = m["cities"][0]
        assert city["raw_coverage_pct"] == 14, (
            f"原始覆盖率应不变 = 1/7 = 14%，实际 {city['raw_coverage_pct']}"
        )
        assert city["coverage_pct"] >= 25, (
            f"基地式 leg 调整后覆盖率应明显高于原始 14%，预期 >= 25%，"
            f"实际 {city['coverage_pct']}"
        )

    def test_pure_intracity_leg_unaffected(self):
        """纯市内游 leg（每天都有匹配必去清单的活动）不应被识别为 off-city。"""
        leg = {
            "city": "爱丁堡",
            "days": [
                {"activities": ["爱丁堡城堡"], "transport": [], "accommodation": "酒店A"},
                {"activities": ["皇家英里", "亚瑟王座"], "transport": [], "accommodation": "酒店A"},
                {"activities": ["荷里路德宫"], "transport": [], "accommodation": "酒店A"},
            ],
        }
        m = _compute_attractions_metrics([leg], BENCHMARKS_EDINBURGH)
        city = m["cities"][0]
        # 3 天全市内日 → effective_days = 3
        assert city["effective_days"] == 3.0, (
            f"纯市内 leg 不应被折减，预期 3.0，实际 {city['effective_days']}"
        )

    def test_activities_with_city_name_not_off_city(self):
        """活动名包含 leg 城市名（如"爱丁堡王子街"）不应被判 off-city。"""
        leg = {
            "city": "爱丁堡",
            "days": [
                {"activities": ["爱丁堡王子街购物", "爱丁堡老城散步"],
                 "transport": [], "accommodation": "酒店A"},
            ],
        }
        m = _compute_attractions_metrics([leg], BENCHMARKS_EDINBURGH)
        city = m["cities"][0]
        # 1 天市内日（虽然不在 must_see 但活动含城市名） → effective_days = 1
        assert city["effective_days"] == 1.0, (
            f"活动名含 leg 城市的 day 不应被判 off-city，实际 {city['effective_days']}"
        )

    def test_empty_activities_day_not_off_city(self):
        """空 activities 的 day（休息日）不应被判 off-city，避免误判。"""
        leg = {
            "city": "爱丁堡",
            "days": [
                {"activities": ["爱丁堡城堡"], "transport": [], "accommodation": "酒店A"},
                {"activities": [], "transport": [], "accommodation": "酒店A"},
                {"activities": ["皇家英里"], "transport": [], "accommodation": "酒店A"},
            ],
        }
        m = _compute_attractions_metrics([leg], BENCHMARKS_EDINBURGH)
        city = m["cities"][0]
        assert city["effective_days"] == 3.0, (
            f"空 activities 不应被判 off-city，预期 3.0，实际 {city['effective_days']}"
        )

    def test_transit_day_takes_precedence_over_off_city(self):
        """transit_day 优先于 off_city：跨城日按 0.5 折减，不再额外按 off-city 折减。"""
        leg = {
            "city": "爱丁堡",
            "days": [
                # 跨城日（含 transport），活动是外地景点（按 off_city 规则也算）
                # 但 transit_day 优先 → 仅 0.5 折减
                {"activities": ["威廉堡火车站"], "transport": ["U2308:伦敦→爱丁堡"],
                 "accommodation": None},
            ],
        }
        m = _compute_attractions_metrics([leg], BENCHMARKS_EDINBURGH)
        city = m["cities"][0]
        # 1 day - 0.5 transit = 0.5（不被再扣 0.7）
        assert city["effective_days"] == 0.5, (
            f"transit_day 优先，仅按 0.5 折减，实际 {city['effective_days']}"
        )


class TestOffCityIntegrationOverallCoverage:
    """整合 trip 10 真实场景：爱丁堡基地式 + 伦敦正常游 → 整体覆盖率提升。"""

    def _trip10_legs(self):
        """复现 trip 10 完整 legs（含 OCR 错字"白金汉官"和"伦教塔桥"）。"""
        return [
            {
                "city": "斯里巴加湾市",
                "country": "文莱",
                "days": [
                    {"activities": [], "accommodation": "伦敦摄政公园万豪酒店",
                     "transport": ["BI624:北京→斯里巴加湾市", "斯里巴加湾市→伦敦"]},
                ],
            },
            {
                "city": "伦敦",
                "country": "英国",
                "days": [
                    {"activities": ["大英博物馆"], "accommodation": "伦敦摄政公园万豪酒店",
                     "transport": []},
                    {"activities": ["杜莎夫人蜡像馆", "贝克街", "西敏寺"],
                     "accommodation": "伦敦摄政公园万豪酒店", "transport": []},
                    {"activities": [
                        "圣保罗座堂", "伦敦大火纪念碑", "伦教塔桥",
                        "伦敦塔", "Westminster Abbey", "大本钟", "伦敦眼",
                     ], "accommodation": "伦敦摄政公园万豪酒店", "transport": []},
                    # OCR 错字"白金汉官"
                    {"activities": ["海德公园", "白金汉官", "格林威治天文台"],
                     "accommodation": "伦敦摄政公园万豪酒店", "transport": []},
                    {"activities": ["希思罗机场"], "accommodation": None,
                     "transport": ["U2301:爱丁堡→伦敦", "伦敦→北京"]},
                ],
            },
            _edinburgh_basecamp_leg(),
            {
                "city": "北京",
                "country": "中国",
                "days": [
                    {"activities": [], "accommodation": None, "transport": []},
                ],
            },
        ]

    def _trip10_benchmarks(self):
        return {
            "斯里巴加湾市": {"country": "文莱", "must_see": ["水上村落"], "typical_stay_days": 2,
                       "avg_daily_cost_cny": 826},
            "伦敦": {
                "country": "英国",
                "avg_daily_cost_cny": 2200,
                "must_see": ["大本钟", "伦敦塔桥", "白金汉宫", "大英博物馆",
                             "伦敦眼", "海德公园", "西敏寺"],
                "typical_stay_days": 4,
            },
            "爱丁堡": BENCHMARKS_EDINBURGH["爱丁堡"],
            "北京": {"country": "中国", "must_see": ["故宫"], "typical_stay_days": 4,
                  "avg_daily_cost_cny": 1220},
        }

    def test_overall_coverage_improves_after_off_city_and_typo_fix(self):
        """整体覆盖率应从旧的 54% 升至明显更高的水平。

        预期值（仅作下界）：
          - 伦敦（白金汉官+伦教塔桥都被 OCR 容错匹配）→ 7/7 = 100%，权重 4.5
          - 爱丁堡（off-city 折减后）→ 30%，权重 1.4
          - 整体 = (100×4.5 + 30×1.4) / 5.9 ≈ 83.6%
        """
        m = _compute_attractions_metrics(self._trip10_legs(), self._trip10_benchmarks())
        assert m["overall_coverage"] >= 75, (
            f"修复后整体景点覆盖率应 >= 75%，实际 {m['overall_coverage']}%"
        )

    def test_london_full_covered_after_typo_fix(self):
        """伦敦：白金汉官 + 伦教塔桥 都被 OCR 容错匹配 → 7/7 全覆盖。"""
        m = _compute_attractions_metrics(self._trip10_legs(), self._trip10_benchmarks())
        london = next(c for c in m["cities"] if c["city"] == "伦敦")
        assert london["raw_coverage_pct"] == 100, (
            f"伦敦 OCR 容错后应 7/7 全覆盖，实际 {london['raw_coverage_pct']}%；"
            f"covered={london['covered']}, missed={london['missed']}"
        )

    def test_attractions_score_significantly_higher(self):
        """景点维度评分应明显高于旧的 59 分。"""
        m = _compute_attractions_metrics(self._trip10_legs(), self._trip10_benchmarks())
        assert m["score"] >= 75, (
            f"修复后景点评分应 >= 75，实际 {m['score']}"
        )
