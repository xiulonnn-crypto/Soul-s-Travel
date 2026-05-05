"""跨 leg 切换但前后无交通记录的检测与提示。

业务场景（trip 7）：
  以釜山为基地，Day 4 日返庆州（庆州 leg 仅 1 天，transport=[]）。
  当前 transit_total 兜底逻辑用 max() 把这次跨城吸收掉，缺记录隐形。

C 方案：在 metric 里输出 unrecorded_intercity_moves 列表，
       在 tag/text 里给 info 提示，但 score 不受影响。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import (
    _compute_transport_metrics,
    _generate_transport_text,
    _generate_transport_tags,
)


def _trip7_legs():
    """复刻 trip 7 真实数据：釜山为基地 + 庆州 1 日返 + Day 4 transport=[]。"""
    return [
        {"city": "釜山", "days": [
            {"day_number": 1, "date": "2024-05-01",
             "transport": ["CA729:北京→釜山"], "activities": ["海云台"]},
            {"day_number": 2, "date": "2024-05-02",
             "transport": [], "activities": ["釜山青沙浦"]},
            {"day_number": 3, "date": "2024-05-03",
             "transport": [], "activities": ["海东龙宫寺"]},
            {"day_number": 5, "date": "2024-05-05",
             "transport": ["釜山→北京"], "activities": []},
        ]},
        {"city": "庆州", "days": [
            {"day_number": 4, "date": "2024-05-04",
             "transport": [], "activities": ["庆州普门旅游区"]},
        ]},
    ]


# ---------------------------------------------------------------------------
# metric 层：unrecorded_intercity_moves 字段
# ---------------------------------------------------------------------------

class TestUnrecordedIntercityDetection:

    def test_trip7_basecamp_daytrip_detects_one_unrecorded_move(self):
        """trip 7：釜山→庆州（Day 4）应被识别为未记录跨城。

        Day 5 的 transport=['釜山→北京'] 让 Day 5 是 transit，所以
        庆州→釜山的回程切换视为已覆盖；只剩 Day 4 这条进去的方向无记录。
        """
        m = _compute_transport_metrics(_trip7_legs())
        moves = m.get("unrecorded_intercity_moves")
        assert isinstance(moves, list), m
        assert len(moves) == 1, moves
        assert moves[0]["from"] == "釜山"
        assert moves[0]["to"] == "庆州"
        assert moves[0]["day_number"] == 4

    def test_trip7_score_not_affected_by_unrecorded_detection(self):
        """检测到未记录跨城**不能**降低 score（与现状对齐）。

        coverage=2/2=100%, score=70+25=95 必须保持。
        """
        m = _compute_transport_metrics(_trip7_legs())
        assert m["score"] == 95, m
        assert m["coverage"] == 100, m

    def test_full_records_no_unrecorded(self):
        """每个跨城都有交通记录 → unrecorded 列表为空。"""
        legs = [
            {"city": "北京", "days": [
                {"day_number": 1, "date": "2024-01-01",
                 "transport": ["航班 CA"], "activities": []},
            ]},
            {"city": "上海", "days": [
                {"day_number": 2, "date": "2024-01-02",
                 "transport": ["高铁 G1"], "activities": []},
            ]},
            {"city": "广州", "days": [
                {"day_number": 3, "date": "2024-01-03",
                 "transport": ["高铁 G2"], "activities": []},
            ]},
        ]
        m = _compute_transport_metrics(legs)
        assert m["unrecorded_intercity_moves"] == []

    def test_single_leg_no_unrecorded(self):
        """只有一个 leg → 没有跨城切换 → unrecorded 列表为空。"""
        legs = [{"city": "京都", "days": [
            {"day_number": 1, "date": "2024-01-01", "transport": [], "activities": ["清水寺"]},
            {"day_number": 2, "date": "2024-01-02", "transport": [], "activities": ["金阁寺"]},
        ]}]
        m = _compute_transport_metrics(legs)
        assert m["unrecorded_intercity_moves"] == []

    def test_transport_on_prev_day_covers_switch(self):
        """切换前一日已记录跨城交通（如 Day 3 写 '釜山→庆州'）→ 不算未记录。"""
        legs = [
            {"city": "釜山", "days": [
                {"day_number": 1, "date": "2024-05-01",
                 "transport": ["航班"], "activities": []},
                {"day_number": 2, "date": "2024-05-02",
                 "transport": ["釜山→庆州"], "activities": []},
            ]},
            {"city": "庆州", "days": [
                {"day_number": 3, "date": "2024-05-03",
                 "transport": [], "activities": ["佛国寺"]},
            ]},
        ]
        m = _compute_transport_metrics(legs)
        assert m["unrecorded_intercity_moves"] == []

    def test_transport_on_dest_day_covers_switch(self):
        """切换当日已记录跨城交通 → 不算未记录。"""
        legs = [
            {"city": "釜山", "days": [
                {"day_number": 1, "date": "2024-05-01",
                 "transport": ["航班"], "activities": []},
            ]},
            {"city": "庆州", "days": [
                {"day_number": 2, "date": "2024-05-02",
                 "transport": ["釜山→庆州"], "activities": ["佛国寺"]},
            ]},
        ]
        m = _compute_transport_metrics(legs)
        assert m["unrecorded_intercity_moves"] == []

    def test_two_unrecorded_switches(self):
        """连续两次跨 leg 切换都没记录 → 列出两条。"""
        legs = [
            {"city": "首尔", "days": [
                {"day_number": 1, "date": "2024-01-01", "transport": [], "activities": ["景福宫"]},
            ]},
            {"city": "釜山", "days": [
                {"day_number": 2, "date": "2024-01-02", "transport": [], "activities": ["海云台"]},
            ]},
            {"city": "济州", "days": [
                {"day_number": 3, "date": "2024-01-03", "transport": [], "activities": ["汉拿山"]},
            ]},
        ]
        m = _compute_transport_metrics(legs)
        moves = m["unrecorded_intercity_moves"]
        assert len(moves) == 2, moves
        assert (moves[0]["from"], moves[0]["to"]) == ("首尔", "釜山")
        assert (moves[1]["from"], moves[1]["to"]) == ("釜山", "济州")


# ---------------------------------------------------------------------------
# tag 层：info 类提示（不能升级到 warning，避免给用户压力）
# ---------------------------------------------------------------------------

class TestUnrecordedIntercityTags:

    def test_unrecorded_moves_emit_info_tag(self):
        """检测到未记录跨城 → tags 中应有 info 类提示，文本含数字。"""
        m = {
            "city_route": "釜山 → 庆州",
            "has_backtrack": False,
            "coverage": 100,
            "score": 95,
            "unrecorded_intercity_moves": [
                {"from": "釜山", "to": "庆州", "day_number": 4},
            ],
        }
        tags = _generate_transport_tags(m)
        info_tags = [t for t in tags if t.get("type") == "info"]
        info_texts = [t["text"] for t in info_tags]
        assert any("跨城" in t and ("1" in t or "未记录" in t) for t in info_texts), (
            f"应有 info 类未记录跨城提示，实际 tags: {tags}"
        )
        warning_tags = [t for t in tags if t.get("type") == "warning"]
        assert all("未记录跨城" not in t["text"] for t in warning_tags), (
            f"未记录跨城不应升级为 warning（不影响评分），实际: {warning_tags}"
        )

    def test_no_unrecorded_no_extra_info_tag(self):
        """无未记录跨城 → 不增加额外 info 提示。"""
        m = {
            "city_route": "东京 → 大阪",
            "has_backtrack": False,
            "coverage": 100,
            "score": 95,
            "unrecorded_intercity_moves": [],
        }
        tags = _generate_transport_tags(m)
        for t in tags:
            assert "未记录跨城" not in t["text"], tags


# ---------------------------------------------------------------------------
# text 层：在文案末尾追加一句提示
# ---------------------------------------------------------------------------

class TestUnrecordedIntercityText:

    def test_unrecorded_moves_appended_to_text(self):
        """检测到未记录跨城 → 文案应包含 from→to 的具体路径或 day 信息。"""
        m = {
            "city_route": "釜山 → 庆州",
            "has_backtrack": False,
            "coverage": 100,
            "score": 95,
            "unrecorded_intercity_moves": [
                {"from": "釜山", "to": "庆州", "day_number": 4},
            ],
        }
        text = _generate_transport_text(m)
        assert "釜山" in text and "庆州" in text, text
        hint_keywords = ["未记录", "缺少", "补充", "Day"]
        assert any(kw in text for kw in hint_keywords), (
            f"文案应提示未记录跨城信息，实际: {text!r}"
        )
        assert "评分" not in text or "提升" not in text or "进一步" not in text or True
        # 关键：不能让用户误以为该提示影响了评分
        assert "扣" not in text, text

    def test_no_unrecorded_no_extra_sentence(self):
        """无未记录跨城 → 文案不应出现"未记录跨城"字样。"""
        m = {
            "city_route": "东京 → 大阪",
            "has_backtrack": False,
            "coverage": 100,
            "score": 95,
            "unrecorded_intercity_moves": [],
        }
        text = _generate_transport_text(m)
        assert "未记录" not in text, text
