"""景点名匹配的 OCR/错字宽容（中文等长一字之差）。

真实场景（trip 10）：
  - PDF 解析后 Day5 出现 "白金汉官"（"官" vs "宫" OCR 错字）
  - 此前匹配逻辑 `spot in activity or activity in spot` 双向都不成立
  - 必去景点 "白金汉宫" 被错算为未去 → 伦敦覆盖率从 7/7=100% 降为 6/7=86%

设计原则：
  1. 中文景点名长度 >= 3 才启用（避免 "古城"/"新城" 短词误匹配）
  2. 仅在等长情况下允许 1 字差（避免"伦敦塔" vs "伦敦塔桥" 长度不等被判匹配）
  3. 不影响原有双向子串匹配（"伦敦塔" 子串于 "伦敦塔桥" 仍命中）
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import _compute_attractions_metrics


BENCHMARKS_LONDON = {
    "伦敦": {
        "country": "英国",
        "avg_daily_cost_cny": 2200,
        "must_see": [
            "大本钟", "伦敦塔桥", "白金汉宫",
            "大英博物馆", "伦敦眼", "海德公园", "西敏寺",
        ],
        "typical_stay_days": 4,
    }
}


class TestOcrTypoTolerance:
    """中文景点名一字之差应视为同一景点（处理 PDF/OCR 错字）。"""

    def test_baijinhanguan_matches_baijinhangong(self):
        """白金汉官 (OCR 错字) 应匹配 白金汉宫。"""
        legs = [
            {
                "city": "伦敦",
                "days": [
                    {"activities": ["白金汉官"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, BENCHMARKS_LONDON)
        city = m["cities"][0]
        assert "白金汉宫" in city["covered"], (
            f"白金汉官（OCR 错字）应匹配白金汉宫，实际 covered={city['covered']}"
        )
        assert "白金汉宫" not in city["missed"], (
            f"白金汉官（OCR 错字）匹配后白金汉宫不应出现在 missed，实际 missed={city['missed']}"
        )

    def test_lunjiaotaqiao_matches_lundunatqiao(self):
        """伦教塔桥 (OCR 错字 教/敦) 应匹配 伦敦塔桥。"""
        legs = [
            {
                "city": "伦敦",
                "days": [
                    {"activities": ["伦教塔桥"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, BENCHMARKS_LONDON)
        city = m["cities"][0]
        assert "伦敦塔桥" in city["covered"], (
            f"伦教塔桥（OCR 错字）应匹配伦敦塔桥，实际 covered={city['covered']}"
        )

    def test_short_2char_names_not_typo_matched(self):
        """长度小于 3 的中文名不启用一字差容错（避免"古城"/"新城"误匹配）。"""
        benchmarks = {
            "测试城": {
                "must_see": ["古城"],
                "typical_stay_days": 2,
            }
        }
        legs = [
            {
                "city": "测试城",
                "days": [
                    {"activities": ["新城"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, benchmarks)
        city = m["cities"][0]
        assert "古城" not in city["covered"], (
            f"长度 < 3 的短名不应一字差匹配，covered={city['covered']}"
        )

    def test_two_char_diff_not_matched(self):
        """两字之差仍不匹配（避免过度宽容）。"""
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
                    {"activities": ["白银汉殿"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, benchmarks)
        city = m["cities"][0]
        assert "白金汉宫" not in city["covered"], (
            f"两字之差不应匹配，covered={city['covered']}"
        )

    def test_substring_match_still_works(self):
        """原有双向子串匹配不受影响：'伦敦塔' 子串于 '伦敦塔桥' 仍匹配。"""
        legs = [
            {
                "city": "伦敦",
                "days": [
                    {"activities": ["伦敦塔"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, BENCHMARKS_LONDON)
        city = m["cities"][0]
        assert "伦敦塔桥" in city["covered"], (
            f"伦敦塔 应子串匹配 伦敦塔桥（向下兼容），covered={city['covered']}"
        )

    def test_different_length_one_diff_not_typo_matched(self):
        """长度不等的字符串即使有共同字也不算一字差（已由子串匹配兜底）。"""
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
                    # 长度 5 vs 4，且不互为子串
                    {"activities": ["白金汉皇宫"], "transport": []},
                ],
            }
        ]
        m = _compute_attractions_metrics(legs, benchmarks)
        city = m["cities"][0]
        # 子串包含规则下："白金汉宫" 不在 "白金汉皇宫" 内（"金汉宫" vs "金汉皇"）；反之 "白金汉皇宫" 也不在 "白金汉宫" 内
        # → OCR 容错也不应启用（长度不等）
        assert "白金汉宫" not in city["covered"], (
            f"长度不等不启用一字差，covered={city['covered']}"
        )
