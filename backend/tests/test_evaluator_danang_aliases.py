"""景点覆盖别名 —— 岘港跨语言匹配（trip 16 真实场景）。

真实场景（trip 16 岘港5日游）：
  - must_see 仅含简体中文名：巴拿山、会安古城、山茶半岛、龙桥
  - 用户 activities 实际写的是：
      Day 1: '會安古鎮'（繁体 + 鎮 ≠ 城，2字差，一字差容错无法命中）
      Day 2: 'Dragon Bridge'（英文，_spot_match 无法跨语言）
      Day 3: 'Ba Na Hills'（英文）
      Day 4: 'Sơn Trà Marina'（越南语）
  - 上述 4 景点被错判为未去，coverage 1/6=17% 而非正确的 5/6=83%

修复方式：在 city_benchmarks.json 岘港条目的 must_see 里加 | 别名声明。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import _compute_attractions_metrics

# 原始数据（未加别名），用于验证 RED 状态
BENCHMARKS_DANANG_NO_ALIAS = {
    "岘港": {
        "country": "越南",
        "avg_daily_cost_cny": 640,
        "avg_hotel_price_cny": 350,
        "must_see": [
            "美溪海滩",
            "巴拿山",
            "会安古城",
            "山茶半岛",
            "龙桥",
            "五行山",
        ],
        "typical_stay_days": 3,
    }
}

# 修复后数据（加别名），用于验证 GREEN 状态
BENCHMARKS_DANANG_WITH_ALIAS = {
    "岘港": {
        "country": "越南",
        "avg_daily_cost_cny": 640,
        "avg_hotel_price_cny": 350,
        "must_see": [
            "美溪海滩",
            "巴拿山|Ba Na Hills",
            "会安古城|会安古镇|會安古鎮|会安",
            "山茶半岛|Sơn Trà|山茶",
            "龙桥|Dragon Bridge",
            "五行山|Marble Mountains",
        ],
        "typical_stay_days": 3,
    }
}

# trip 16 的真实 activities（逐字复制自 DB）
TRIP16_LEGS = [
    {
        "city": "岘港",
        "days": [
            {
                "activities": [
                    "Yaly Couture",
                    "Hanh Coconut",
                    "會安古鎮",
                    "Morning Glory Original",
                    "Mót Hội An - Nước Thảo Mộc Sả Chanh",
                ],
                "transport": ["UO552:香港→岘港"],
            },
            {
                "activities": [
                    "美溪海滩",
                    "Maya Spa & Nail - Massage Da Nang | 다낭 마사지 & 네일 - 다낭 마사지",
                    "Dragon Bridge",
                    "占婆雕刻博物馆",
                    "Da Nang Cathedral",
                    "Ăn Thôi Restaurant",
                    "Quán Bún Bà Diệu",
                ],
                "transport": [],
            },
            {
                "activities": [
                    "Ba Na Hills",
                    "Golden Bridge",
                    "美山圣地世界文化遗产",
                ],
                "transport": [],
            },
            {
                "activities": [
                    "Linh Ứng Pagoda",
                    "Sơn Trà Marina",
                    "Bếp Hên",
                ],
                "transport": [],
            },
        ],
    }
]


class TestDanangAliasRed:
    """验证未加别名时，跨语言景点名确实漏判（RED 状态存档）。"""

    def test_no_alias_misses_ba_na_hills(self):
        """未加别名：'Ba Na Hills' 无法匹配 '巴拿山'。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_NO_ALIAS)
        city = m["cities"][0]
        assert "巴拿山" not in city["covered"], (
            f"未加别名时 Ba Na Hills 不应命中巴拿山；covered={city['covered']}"
        )

    def test_no_alias_misses_huian_traditional(self):
        """未加别名：'會安古鎮'（繁体+鎮）无法匹配 '会安古城'（2字差）。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_NO_ALIAS)
        city = m["cities"][0]
        assert "会安古城" not in city["covered"], (
            f"未加别名时 會安古鎮 不应命中 会安古城；covered={city['covered']}"
        )

    def test_no_alias_misses_dragon_bridge(self):
        """未加别名：'Dragon Bridge' 无法匹配 '龙桥'。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_NO_ALIAS)
        city = m["cities"][0]
        assert "龙桥" not in city["covered"], (
            f"未加别名时 Dragon Bridge 不应命中龙桥；covered={city['covered']}"
        )

    def test_no_alias_misses_son_tra(self):
        """未加别名：'Sơn Trà Marina' 无法匹配 '山茶半岛'。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_NO_ALIAS)
        city = m["cities"][0]
        assert "山茶半岛" not in city["covered"], (
            f"未加别名时 Sơn Trà Marina 不应命中 山茶半岛；covered={city['covered']}"
        )


class TestDanangAliasGreen:
    """加别名后，跨语言景点名应正确覆盖（GREEN 状态目标）。"""

    def test_ba_na_hills_matches_with_alias(self):
        """加别名后：'Ba Na Hills' 应命中 '巴拿山'。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_WITH_ALIAS)
        city = m["cities"][0]
        assert "巴拿山" in city["covered"], (
            f"Ba Na Hills 应通过别名匹配 巴拿山；covered={city['covered']}, missed={city['missed']}"
        )
        assert "巴拿山" not in city["missed"]

    def test_huian_traditional_matches_with_alias(self):
        """加别名后：'會安古鎮' 应命中 '会安古城'（通过 '会安古镇|會安古鎮' 别名）。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_WITH_ALIAS)
        city = m["cities"][0]
        assert "会安古城" in city["covered"], (
            f"會安古鎮 应通过别名匹配 会安古城；covered={city['covered']}, missed={city['missed']}"
        )
        assert "会安古城" not in city["missed"]

    def test_dragon_bridge_matches_with_alias(self):
        """加别名后：'Dragon Bridge' 应命中 '龙桥'。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_WITH_ALIAS)
        city = m["cities"][0]
        assert "龙桥" in city["covered"], (
            f"Dragon Bridge 应通过别名匹配 龙桥；covered={city['covered']}, missed={city['missed']}"
        )
        assert "龙桥" not in city["missed"]

    def test_son_tra_matches_with_alias(self):
        """加别名后：'Sơn Trà Marina' 应命中 '山茶半岛'（通过 Sơn Trà 子串）。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_WITH_ALIAS)
        city = m["cities"][0]
        assert "山茶半岛" in city["covered"], (
            f"Sơn Trà Marina 应通过别名匹配 山茶半岛；covered={city['covered']}, missed={city['missed']}"
        )
        assert "山茶半岛" not in city["missed"]

    def test_wuxing_mountain_still_missed(self):
        """五行山真正未去，加别名后仍在 missed 中。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_WITH_ALIAS)
        city = m["cities"][0]
        assert "五行山" not in city["covered"], (
            f"五行山确实未去，不应出现在 covered；covered={city['covered']}"
        )
        assert "五行山" in city["missed"]

    def test_full_coverage_5_of_6(self):
        """加别名后：覆盖应为 5/6=83%，而非当前错误的 1/6=17%。"""
        m = _compute_attractions_metrics(TRIP16_LEGS, BENCHMARKS_DANANG_WITH_ALIAS)
        city = m["cities"][0]
        assert city["raw_coverage_pct"] == 83, (
            f"应覆盖 5/6=83%，实际 {city['raw_coverage_pct']}%；"
            f"covered={city['covered']}, missed={city['missed']}"
        )
        assert len(city["covered"]) == 5, f"应命中 5 个景点，实际 {len(city['covered'])}"
        assert len(city["missed"]) == 1, f"应漏 1 个景点，实际 {len(city['missed'])}"
