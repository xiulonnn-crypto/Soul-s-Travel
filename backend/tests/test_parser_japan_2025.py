"""针对 2025-01 日本 PDF 的分类准确性回归测试。

该 PDF 暴露 `_parse_expenses` 里两类已知缺口：

1. **CATEGORY_RULES 关键字覆盖不足**：日本常用交通 IC 卡（SUICA/PASMO）、
   JR 线路、电车以及带「旅店」后缀的住宿，因为不在主关键字表里全部退到
   「其他」。
2. **`_build_activity_category_map` 没有「住宿」/「交通」类型标签**：穷游
   PDF 详情页明明给出「住宿」「电车」「其他景点」标签，但映射规则只覆盖
   餐饮/门票/购物，导致命名不含「酒店」二字的酒店（如 Agora Place 东京
   浅草）拿不到 `住宿` 分类，最终落到「其他」。
3. **住宿反填过于激进**：当某日没有原生「住宿」条目时，`_post_assign_
   hotel_from_accommodation` 会把当日第一条「其他」盲目提升为住宿。对
   于回程日（如 Day 5 只有餐厅消费）或一日多条「其他」的日子（如 Day 3
   的鸟贵族 vs 湘南藤泽阿蒙特旅店），会把**餐厅**错误地提升为住宿，还
   会污染 `day.accommodation` 字段。

以上每条 bug 都用真实 PDF 条目锁定，避免今后修复倒退。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.ai_parser import parse_text
from services.file_extractor import extract_text_from_pdf

PDF_PATH = Path(os.path.expanduser("~/Downloads/202501 日本.pdf"))


@pytest.fixture(scope="module")
def parsed():
    if not PDF_PATH.exists():
        pytest.skip(f"PDF 不存在: {PDF_PATH}")
    with open(PDF_PATH, "rb") as f:
        text = extract_text_from_pdf(f.read())
    return parse_text(text)


def _find_expense(parsed, keyword):
    for e in parsed["expenses"]:
        if keyword in (e.get("description") or ""):
            return e
    raise AssertionError(
        f"未找到包含 {keyword!r} 的费用条目；"
        f"实际={[e['description'] for e in parsed['expenses']]}"
    )


class TestTransportKeywords:
    """日本行程里的 IC 卡与 JR 电车消费必须识别为「交通」。"""

    def test_suica_is_transport(self, parsed):
        for e in parsed["expenses"]:
            if "SUICA" in (e.get("description") or ""):
                assert e["category"] == "交通", (
                    f"SUICA 应为交通，实际 {e['category']}；desc={e['description']}"
                )

    def test_jr_line_is_transport(self, parsed):
        e = _find_expense(parsed, "JR")
        assert e["category"] == "交通", (
            f"JR 线路票价应为交通，实际 {e['category']}；desc={e['description']}"
        )


class TestAccommodationKeywords:
    """包含「旅店」后缀或详情页「住宿」类型标签的酒店应归入「住宿」。"""

    def test_lvdian_suffix_is_accommodation(self, parsed):
        e = _find_expense(parsed, "旅店")
        assert e["category"] == "住宿", (
            f"含「旅店」应为住宿，实际 {e['category']}；desc={e['description']}"
        )

    def test_agora_place_is_accommodation(self, parsed):
        """Agora Place 东京浅草（无「酒店」关键字）应通过详情页「住宿」
        类型标签归入住宿。"""
        e = _find_expense(parsed, "Agora Place")
        assert e["category"] == "住宿", (
            f"Agora Place 应为住宿，实际 {e['category']}；desc={e['description']}"
        )


class TestAttractionTypeLabel:
    """详情页「其他景点」类型标签应归入「门票」。"""

    def test_sunshine60_is_ticket(self, parsed):
        e = _find_expense(parsed, "Sunshine60")
        assert e["category"] in ("门票", "其他"), (
            f"Sunshine60 瞭望台的分类不合理：{e['category']}"
        )
        assert e["category"] == "门票", (
            f"Sunshine60 瞭望台应为门票，实际 {e['category']}"
        )


class TestFallbackPromotionSafety:
    """住宿反填不能把餐厅/活动类「其他」条目误升为住宿。"""

    def test_niaoguizu_not_accommodation(self, parsed):
        """鸟贵族是居酒屋连锁，不得被反填逻辑误分成住宿。"""
        e = _find_expense(parsed, "鸟贵族")
        assert e["category"] != "住宿", (
            f"鸟贵族（居酒屋）不该是住宿；desc={e['description']}"
        )

    def test_momoparadise_not_accommodation(self, parsed):
        """MO-MO-PARADISE 是涮锅餐厅，不得被反填逻辑误分成住宿。"""
        e = _find_expense(parsed, "MO-MO-PARADISE")
        assert e["category"] != "住宿", (
            f"MO-MO-PARADISE（涮锅店）不该是住宿；desc={e['description']}"
        )


class TestFallbackBucketShareBound:
    """「其他」桶占比作为白名单完整性的硬上限。真实 PDF 里 21 条里合理的
    「其他」应 ≤ 30%（实践中通常 ≤ 20%）。"""

    def test_other_share_upper_bound(self, parsed):
        total = len(parsed["expenses"])
        other = sum(1 for e in parsed["expenses"] if e["category"] == "其他")
        assert total > 0, "解析的费用为空，无法评估分类质量"
        ratio = other / total
        assert ratio <= 0.30, (
            f"「其他」占比 {other}/{total} = {ratio:.0%} 超过 30% 上限；"
            f"白名单/类型标签规则需要扩充。\n"
            f"其他条目：{[e['description'] for e in parsed['expenses'] if e['category'] == '其他']}"
        )


class TestDay5Content:
    """Day 5 是回程日，PDF 景点列明确写了 `1. MO-MO-PARADISE Kabukicho`，
    且 overview 列出了 3 段转运交通（富士河口湖→大月、大月町→东京、北京→东京）。
    此前由于 (1) 景点正则强制 CJK 起首，(2) overview 用了 PUA 字符 \\ue6af /
    \\ue6ab 作箭头（Day 1 是真 →），(3) 交通正则城市长度上限 4，导致 Day 5
    的 activities/transport/description 全部为空/兜底。
    """

    def _day(self, parsed, day_number):
        for leg in parsed["legs"]:
            for d in leg["days"]:
                if d["day_number"] == day_number:
                    return d
        raise AssertionError(f"day {day_number} not found")

    def test_day5_activity_latin_only(self, parsed):
        d = self._day(parsed, 5)
        assert any("MO-MO-PARADISE" in a for a in d.get("activities") or []), (
            f"Day 5 应包含 MO-MO-PARADISE，实际 activities={d.get('activities')}"
        )

    def test_day5_transport_non_empty(self, parsed):
        d = self._day(parsed, 5)
        t = d.get("transport") or []
        assert len(t) >= 1, f"Day 5 应有至少一段交通，实际={t}"

    def test_day5_transport_has_fujikawaguchiko_or_otsuki(self, parsed):
        """交通至少命中 3 段里的一段：富士河口湖→大月 或 大月町→东京。
        富士河口湖是 5 个 CJK 字符，此前 {1,4} 上限会把它截成「河口湖」。"""
        d = self._day(parsed, 5)
        transports = d.get("transport") or []
        joined = " | ".join(transports)
        assert (
            "富士河口湖" in joined or "大月町" in joined
        ), f"Day 5 交通缺失 富士河口湖→大月 或 大月町→东京，实际={transports}"

    def test_day5_description_not_fallback(self, parsed):
        d = self._day(parsed, 5)
        desc = d.get("description") or ""
        assert desc != f"Day {d['day_number']}", (
            f"Day 5 description 仍是兜底「Day 5」——说明 activities 没抽出；实际={desc!r}"
        )


class TestDayAccommodationFromChunk:
    """修复住宿反填后，day 3 的真实酒店（湘南藤泽阿蒙特）应成为 accommodation，
    而非被鸟贵族污染；day 5 没有住宿就保持为空，不要被 MO-MO-PARADISE 顶上。"""

    def _day(self, parsed, day_number):
        for leg in parsed["legs"]:
            for d in leg["days"]:
                if d["day_number"] == day_number:
                    return d
        raise AssertionError(f"day {day_number} not found")

    def test_day3_accommodation_is_shonan_fujisawa(self, parsed):
        d = self._day(parsed, 3)
        accom = d.get("accommodation") or ""
        assert "阿尔蒙特" in accom or "阿蒙特" in accom or "Almont" in accom, (
            f"Day 3 的住宿应是湘南藤泽阿蒙特/Almont，实际={accom!r}"
        )

    def test_day5_accommodation_not_restaurant(self, parsed):
        """Day 5 是回程日，最多只在新宿吃 MO-MO-PARADISE 做纪念餐；
        它不该被当作当天住宿。"""
        d = self._day(parsed, 5)
        accom = d.get("accommodation") or ""
        assert "MO-MO-PARADISE" not in accom, (
            f"Day 5 住宿不该是 MO-MO-PARADISE 餐厅，实际={accom!r}"
        )
