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
        """4/7 days with transport: coverage≈57% → 70 + 4/7*25 ≈ 84"""
        transport_days = [["高铁"], None, ["打车"], ["地铁"], None, ["出租车"], None]
        legs = _make_legs([("伦敦", transport_days)])
        m = _compute_transport_metrics(legs)
        assert m["score"] == 84  # 70 + 4/7*25 = 84.28 → 84
        assert m["coverage"] == 57  # round(4/7*100) = 57

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
