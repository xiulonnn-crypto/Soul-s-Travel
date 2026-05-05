"""景点名别名（must_see 同一景点的多个常见译名）。

真实场景（trip 7 釜山）：
  - must_see "广安里大桥"（韩文 광안대교 = Gwangan Bridge，跨越釜山广安里海湾）
  - 用户 Day 2 activities 实际写 "广安大桥"（同一座桥的常见简称）
  - 长度差 1（5 vs 4）+ 互不为子串 → `_spot_match` 漏匹配
  - 釜山覆盖率从应有 4/7=57% 误降至 3/7=43%，整体景点覆盖维度评分 55→45

设计原则：
  1. 别名以 `|` 分隔写在 must_see 字符串内，第一个为规范展示名
  2. 任一别名 `_spot_match` 命中即视为该景点已覆盖
  3. 不影响 `白金汉宫` vs `白金汉皇宫` 等长度差 1 的字符串容错决策
     （字符串相似度无法区分两者；语义等价性必须由数据显式声明）
  4. `_is_off_city_day` 也按别名集判断，避免别名命中但 off-city 误判
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import _compute_attractions_metrics, _is_off_city_day


BENCHMARKS_BUSAN_WITH_ALIAS = {
    "釜山": {
        "country": "韩国",
        "avg_daily_cost_cny": 850,
        "must_see": [
            "海云台海滩",
            "甘川文化村",
            "海东龙宫寺",
            "广安里大桥|广安大桥",
            "札嘎其鱼市场",
            "太宗台",
            "影岛大桥",
        ],
        "typical_stay_days": 3,
    }
}


class TestSpotAlias:
    """must_see 字段的 `|` 分隔别名应被识别为同一景点。"""

    def test_alias_short_form_matches(self):
        """用户写「广安大桥」应命中 must_see「广安里大桥|广安大桥」。"""
        legs = [
            {
                "city": "釜山",
                "days": [
                    {"activities": ["广安大桥"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, BENCHMARKS_BUSAN_WITH_ALIAS)
        city = m["cities"][0]
        assert "广安里大桥" in city["covered"], (
            f"广安大桥 应通过别名匹配规范名 广安里大桥；"
            f"实际 covered={city['covered']}, missed={city['missed']}"
        )
        assert "广安里大桥" not in city["missed"], (
            f"匹配后规范名不应同时在 missed 中；missed={city['missed']}"
        )

    def test_alias_canonical_form_still_matches(self):
        """直接写规范名「广安里大桥」也应命中。"""
        legs = [
            {
                "city": "釜山",
                "days": [
                    {"activities": ["广安里大桥"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, BENCHMARKS_BUSAN_WITH_ALIAS)
        city = m["cities"][0]
        assert "广安里大桥" in city["covered"]

    def test_busan_trip7_full_scenario(self):
        """复现 trip 7 釜山 leg 完整场景：4 天 10 个活动，应命中 4/7。"""
        legs = [
            {
                "city": "釜山",
                "days": [
                    {
                        "activities": ["海云台传统市场"],
                        "transport": ["CA729:北京→釜山"],
                        "accommodation": "釜山万枫酒店",
                    },
                    {
                        "activities": [
                            "釜山青沙浦",
                            "南川洞樱花街",
                            "广安里海水浴场",
                            "甘川文化村",
                            "松岛海上缆车",
                            "广安大桥",
                            "游艇",
                            "海云台海滩",
                        ],
                        "transport": [],
                        "accommodation": "釜山万枫酒店",
                    },
                    {
                        "activities": ["海东龙宫寺"],
                        "transport": [],
                        "accommodation": "釜山朝鲜威斯汀酒店",
                    },
                    {
                        "activities": [],
                        "transport": ["釜山→北京"],
                        "accommodation": None,
                    },
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, BENCHMARKS_BUSAN_WITH_ALIAS)
        city = m["cities"][0]
        assert set(city["covered"]) == {
            "海云台海滩",
            "甘川文化村",
            "海东龙宫寺",
            "广安里大桥",
        }, f"实际 covered={city['covered']}"
        assert set(city["missed"]) == {
            "札嘎其鱼市场",
            "太宗台",
            "影岛大桥",
        }, f"实际 missed={city['missed']}"
        assert city["raw_coverage_pct"] == 57, (
            f"raw_coverage_pct 应为 4/7=57%，实际 {city['raw_coverage_pct']}"
        )

    def test_baijinhanguan_皇宫_still_not_matched(self):
        """守护既有决策：长度差 1 的字符串相似度仍不应单凭算法匹配。

        `白金汉宫` vs `白金汉皇宫` 字符串上与 `广安大桥` vs `广安里大桥`
        完全等价（Levenshtein=1 单字插入），但语义上不同。
        别名机制不应被用作"放宽全局字符串容错"的借口。
        """
        benchmarks = {
            "测试城": {
                "must_see": ["白金汉宫"],
                "typical_stay_days": 2,
            }
        }
        legs = [
            {
                "city": "测试城",
                "days": [
                    {"activities": ["白金汉皇宫"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, benchmarks)
        city = m["cities"][0]
        assert "白金汉宫" not in city["covered"], (
            f"未声明别名时长度差 1 不应匹配，covered={city['covered']}"
        )

    def test_alias_used_in_off_city_day_check(self):
        """`_is_off_city_day` 必须用别名集合判断，否则别名活动会被误判为出城日。

        Day 2 用户只在釜山广安大桥附近游玩，活动名都不含"釜山"二字，
        若 _is_off_city_day 不识别别名，会把 Day 2 标为 off-city，
        effective_days 被多扣 0.7，分母再次被错误压缩。
        """
        day = {
            "activities": ["广安大桥"],
            "transport": [],
        }
        must_see = ["广安里大桥|广安大桥"]
        assert _is_off_city_day(day, "釜山", must_see) is False, (
            "Day 2 含 must_see 别名 '广安大桥'，不应被判为出城日"
        )

    def test_no_alias_pipe_behaves_as_before(self):
        """不含 `|` 的 must_see 项行为完全与之前一致。"""
        benchmarks = {
            "测试城": {
                "must_see": ["大本钟", "伦敦塔桥"],
                "typical_stay_days": 2,
            }
        }
        legs = [
            {
                "city": "测试城",
                "days": [
                    {"activities": ["伦敦塔"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, benchmarks)
        city = m["cities"][0]
        assert "伦敦塔桥" in city["covered"], (
            f"子串包含规则应仍生效；covered={city['covered']}"
        )
