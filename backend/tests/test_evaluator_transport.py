"""交通规划评分与文字生成测试

重点验证：评分驱动因素（coverage）与生成文字的一致性。
当 coverage=0 时，用户看到的文字必须解释 70 分的原因。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import (
    _compute_transport_metrics,
    _generate_transport_text,
    _generate_transport_tags,
)


# ---------------------------------------------------------------------------
# 辅助构造器
# ---------------------------------------------------------------------------

def _make_legs(cities_days):
    """
    cities_days: [(city, [transport_list_per_day, ...]), ...]
    transport_list_per_day: list[str] or None (None → 无 transport 字段)
    """
    legs = []
    day_num = 1
    for city, transport_days in cities_days:
        days = []
        for t in transport_days:
            d = {"day_number": day_num, "activities": []}
            if t is not None:
                d["transport"] = t
            days.append(d)
            day_num += 1
        legs.append({"city": city, "days": days})
    return legs


# ---------------------------------------------------------------------------
# _compute_transport_metrics
# ---------------------------------------------------------------------------

class TestTransportMetricsScore:

    def test_zero_coverage_gives_baseline_70(self):
        """无 transport 记录时 score=70（底分）"""
        legs = _make_legs([
            ("伦敦", [None, None, None, None]),
            ("爱丁堡", [None, None, None, None, None]),
        ])
        m = _compute_transport_metrics(legs)
        assert m["score"] == 70
        assert m["coverage"] == 0

    def test_full_coverage_gives_95(self):
        """全部天数都有 transport 记录 → score=95"""
        transport = [["高铁 G1234"], ["打车"], ["地铁"]]
        legs = _make_legs([("东京", [["航班 NH102"], ["打车"], ["地铁"]])])
        m = _compute_transport_metrics(legs)
        assert m["score"] == 95
        assert m["coverage"] == 100

    def test_partial_coverage_score(self):
        """跨城日部分有 transport 记录时部分覆盖：

        3 城（北京→上海→广州，2 次跨城）但只有第一次跨城填了大交通，
        另一次跨城用户用了城内交通词忘记填大交通 → 50% 覆盖。
        城内日的打车 / 地铁不计入分母，避免要求每天都填 transport。
        """
        legs = _make_legs([
            ("北京", [["航班"]]),    # day1 跨城日，记录 ✓
            ("上海", [["打车"]]),     # day2 城内日（仅打车）
            ("广州", [["地铁"]]),     # day3 城内日（仅地铁）— 实际是从上海跨到广州但用户没填
        ])
        m = _compute_transport_metrics(legs)
        # 实际识别 transit_day = 1; inferred = 3-1 = 2; max → 2
        # has_transport_transit = 1
        assert m["coverage"] == 50, m
        # base = 70 + 0.5*25 = 82.5; 无 backtrack
        assert m["score"] == 82, m

    def test_backtrack_deducts_15(self):
        """回头路 -15 分"""
        legs = _make_legs([
            ("北京", [["航班"], ["打车"]]),
            ("上海", [["高铁"]]),
            ("北京", [["打车"]]),  # 回头路
        ])
        m = _compute_transport_metrics(legs)
        assert m["has_backtrack"] is True
        assert m["score"] == _compute_transport_metrics(
            _make_legs([("北京", [["航班"], ["打车"]]), ("上海", [["高铁"], ["打车"]])])
        )["score"] - 15

    def test_two_cities_no_backtrack(self):
        """只有两个城市不触发回头路检测（需要 >=3 城才能有回头路）"""
        legs = _make_legs([
            ("伦敦", [None, None]),
            ("爱丁堡", [None]),
        ])
        m = _compute_transport_metrics(legs)
        assert m["has_backtrack"] is False
        assert m["city_route"] == "伦敦 → 爱丁堡"

    def test_multi_day_stays_only_transit_days_have_transport(self):
        """回归 trip 9: 多日停留的城市，城内日不填 transport，
        所有跨城日都用航班/航班码记录 → 必须 100% 覆盖、95 分。

        曾经的 bug: 旧逻辑用 total_days 作分母，把"城内日没填 transport"
        也算成覆盖率欠缺，结果 8 天 / 3 跨城日 → 38% / 79 分,
        与"路线合理无回头路"的正面评价自相矛盾。
        """
        legs = [
            {"city": "曼谷", "days": [
                {"day_number": 1, "transport": ["HU429:北京→曼谷"], "activities": ["大皇宫"]},
                {"day_number": 2, "transport": [],                  "activities": ["卧佛寺"]},
                {"day_number": 3, "transport": [],                  "activities": ["郑王庙"]},
            ]},
            {"city": "清迈", "days": [
                {"day_number": 4, "transport": ["FD3447:曼谷→清迈"], "activities": ["古城"]},
                {"day_number": 5, "transport": [],                   "activities": ["素贴山"]},
                {"day_number": 6, "transport": [],                   "activities": ["夜市"]},
                {"day_number": 7, "transport": ["SL509:清迈→曼谷",
                                                "FD600:曼谷→北京"], "activities": []},
            ]},
            {"city": "清莱", "days": [
                {"day_number": 8, "transport": [], "activities": ["白庙"]},
            ]},
        ]
        m = _compute_transport_metrics(legs)
        assert m["coverage"] == 100, m
        assert m["score"] == 95, m
        assert m["has_backtrack"] is False, m
        assert m["transit_total"] == 3, m

    def test_pure_arrow_intercity_transport_recognized_as_transit(self):
        """回归 trip 3 (2019 日本): 跨城 transport 仅含纯箭头格式"城A→城B"，
        不含航班码也不含"航班"等关键词，但仍必须被识别为 transit_day。

        线性 4 城 (东京→京都→奈良→大阪)，5 个跨城日全部用纯箭头记录，
        中间穿插 3 个城内日 transport 为空 → 正确分母仅含 5 跨城日，
        coverage=100%, score=95。

        曾经的 bug: 旧逻辑分母 = 全部 8 天，5/8=62% → 86 分，
        让"路线规划合理"被"记录习惯"误判扣分。
        """
        legs = [
            {"city": "东京", "days": [
                {"day_number": 1, "transport": ["UO622:香港→东京"], "activities": ["新宿"]},
                {"day_number": 2, "transport": [],                  "activities": ["浅草寺"]},
                {"day_number": 3, "transport": [],                  "activities": ["迪士尼"]},
            ]},
            {"city": "京都", "days": [
                {"day_number": 4, "transport": ["东京→京都"],       "activities": ["清水寺"]},
            ]},
            {"city": "奈良", "days": [
                {"day_number": 5, "transport": ["京都→奈良"],       "activities": ["奈良公园"]},
            ]},
            {"city": "大阪", "days": [
                {"day_number": 6, "transport": ["奈良→大阪"],       "activities": ["心斋桥"]},
                {"day_number": 7, "transport": [],                  "activities": ["大阪城"]},
                {"day_number": 8, "transport": ["大阪→香港"],       "activities": []},
            ]},
        ]
        m = _compute_transport_metrics(legs)
        assert m["transit_total"] == 5, m
        assert m["coverage"] == 100, m
        assert m["score"] == 95, m
        assert m["has_backtrack"] is False, m
        assert m["city_route"] == "东京 → 京都 → 奈良 → 大阪", m


# ---------------------------------------------------------------------------
# _generate_transport_text — 文字必须解释评分驱动因素
# ---------------------------------------------------------------------------

class TestTransportText:

    def test_zero_coverage_text_mentions_no_records(self):
        """
        coverage=0 → 文字必须提及"无交通记录"或"暂无记录"，
        而不是只说"路线合理"。用户需要知道 70 分是因为数据缺失，不是路线差。
        """
        m = {
            "city_route": "伦敦 → 爱丁堡",
            "has_backtrack": False,
            "coverage": 0,
            "score": 70,
        }
        text = _generate_transport_text(m)
        keywords = ["无记录", "暂无", "未记录", "缺少", "补充"]
        assert any(kw in text for kw in keywords), (
            f"coverage=0 时文字应提示缺少交通记录，实际文字: {text!r}"
        )

    def test_zero_coverage_text_still_mentions_route(self):
        """coverage=0 时路线路径依然要出现在文字中"""
        m = {
            "city_route": "伦敦 → 爱丁堡",
            "has_backtrack": False,
            "coverage": 0,
            "score": 70,
        }
        text = _generate_transport_text(m)
        assert "伦敦" in text and "爱丁堡" in text, (
            f"文字应包含路线信息，实际: {text!r}"
        )

    def test_good_coverage_text_no_warning(self):
        """coverage>=80 → 不应出现"无记录"提示"""
        m = {
            "city_route": "东京 → 大阪",
            "has_backtrack": False,
            "coverage": 100,
            "score": 95,
        }
        text = _generate_transport_text(m)
        for kw in ["无记录", "暂无", "未记录", "缺少"]:
            assert kw not in text, f"高覆盖率不应出现 {kw!r}，实际: {text!r}"

    def test_partial_coverage_text_mentions_ratio(self):
        """coverage<50 → 文字应提示覆盖不完整"""
        m = {
            "city_route": "北京 → 上海",
            "has_backtrack": False,
            "coverage": 30,
            "score": 77,
        }
        text = _generate_transport_text(m)
        hint_keywords = ["无记录", "暂无", "未记录", "缺少", "补充", "部分", "%", "30"]
        assert any(kw in text for kw in hint_keywords), (
            f"低覆盖率文字应给出提示，实际: {text!r}"
        )

    def test_backtrack_text_is_negative(self):
        """存在回头路 → 文字应包含警告"""
        m = {
            "city_route": "北京 → 上海 → 北京",
            "has_backtrack": True,
            "coverage": 100,
            "score": 80,
        }
        text = _generate_transport_text(m)
        assert "回头路" in text


# ---------------------------------------------------------------------------
# _generate_transport_tags — 标签必须反映 coverage 状态
# ---------------------------------------------------------------------------

class TestTransportTags:

    def test_zero_coverage_has_warning_or_info_tag(self):
        """
        coverage=0 → 必须有一个 info/warning 标签提示数据缺失，
        不能只有"路线合理"正面标签。
        """
        m = {
            "city_route": "伦敦 → 爱丁堡",
            "has_backtrack": False,
            "coverage": 0,
            "score": 70,
        }
        tags = _generate_transport_tags(m)
        non_positive_tags = [t for t in tags if t.get("type") != "positive"]
        assert non_positive_tags, (
            f"coverage=0 时至少应有一个 info/warning 标签说明缺少数据，"
            f"实际标签: {tags}"
        )

    def test_good_route_no_backtrack_positive_tag(self):
        """无回头路 → 应有"路线合理"正面标签"""
        m = {
            "city_route": "伦敦 → 爱丁堡",
            "has_backtrack": False,
            "coverage": 80,
            "score": 90,
        }
        tags = _generate_transport_tags(m)
        positive_texts = [t["text"] for t in tags if t.get("type") == "positive"]
        assert any("路线" in t or "合理" in t for t in positive_texts), tags

    def test_backtrack_warning_tag(self):
        """存在回头路 → 标签中应有 warning"""
        m = {
            "city_route": "A → B → A",
            "has_backtrack": True,
            "coverage": 50,
            "score": 67,
        }
        tags = _generate_transport_tags(m)
        warning_tags = [t for t in tags if t.get("type") == "warning"]
        assert warning_tags, "存在回头路时应有 warning 标签"
