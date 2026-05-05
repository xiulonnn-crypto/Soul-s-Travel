"""叶子级 RED tests for 202505 Kenya PDF parsing.

每个测试聚焦一类 bug，断言到具体字段值（assert-to-the-leaf 原则）：

A. _normalize 误折叠合法相邻相同 CJK 字符
B. _extract_accommodation 不支持中英混合酒店名
C. DEST_CITIES + COUNTRY_MAP 缺肯尼亚境内城市
D. _extract_transport 城市名长度上限 + 跨行 CJK 拼接
E. _split_by_day 仅识别"1. 景点行"作为下日 row1，时间段行漏 trim
F. _extract_accommodation 英文 fallback 长度上限 30 + 列合并不切分
G. 概览表无箭头时的 transport 推断（Days 8/9/10 陆路移动）

PDF 不在 ~/Downloads 时跳过（与 test_pdf_fixtures.py 一致）。
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.ai_parser import (
    parse_text,
    _normalize,
    _extract_accommodation,
    _extract_transport,
    _split_by_day,
    DEST_CITIES,
    COUNTRY_MAP,
)
from services.file_extractor import extract_text_from_pdf

PDF_PATH = Path(os.path.expanduser("~/Downloads/202505肯尼亚.pdf"))


@pytest.fixture(scope="module")
def parsed():
    if not PDF_PATH.exists():
        pytest.skip(f"PDF {PDF_PATH} not found")
    with open(PDF_PATH, "rb") as f:
        text = extract_text_from_pdf(f.read())
    return parse_text(text)


def _all_days(result):
    return [d for leg in result["legs"] for d in leg["days"]]


def _day(result, date_str):
    for d in _all_days(result):
        if d["date"] == date_str:
            return d
    raise AssertionError(f"未找到日期 {date_str}；现有 dates: {[d['date'] for d in _all_days(result)]}")


# ── Bug A：_normalize 不应误折叠合法相邻相同字符 ──────────────────────────
class TestNormalizeDoesNotEatLegalRepeats:
    def test_中国国际_kept_intact(self):
        assert _normalize("中国国际大酒店") == "中国国际大酒店"

    def test_勒纳纳_kept_intact(self):
        assert _normalize("勒纳纳蒙特瑞士酒店") == "勒纳纳蒙特瑞士酒店"

    def test_doubled_cjk_block_still_folded(self):
        # 整段 doubled 中文（穷游 detail 页"北北京京 多多哈哈"）应折叠
        out = _normalize("北北京京 多多哈哈")
        assert "北京" in out and "多哈" in out
        assert "北北" not in out and "多多" not in out


# ── Bug B：_extract_accommodation 中英混合 ───────────────────────────────
class TestAccommodationMixedZhEn:
    def test_jw_marriott_zh_name_full(self):
        # 中文+英文+中文+酒店关键字 — 预期保留完整字符串
        chunk = "马赛马拉国家保护区  马赛马拉JW万豪酒店"
        assert _extract_accommodation(chunk) == "马赛马拉JW万豪酒店"

    def test_pure_zh_still_works(self):
        # 不能回归：纯中文酒店名仍然抽取正确
        chunk = "纯中文行程  中国国际大酒店  Swiss"
        assert _extract_accommodation(chunk) == "中国国际大酒店"


# ── Bug C：DEST_CITIES + COUNTRY_MAP 含肯尼亚关键城市 ─────────────────────
class TestKenyaCitiesRegistered:
    def test_masai_mara_in_dest(self):
        assert "马赛马拉国家保护区" in DEST_CITIES

    def test_nakuru_in_dest(self):
        assert "纳库鲁" in DEST_CITIES

    def test_naivasha_in_dest(self):
        assert "奈瓦沙" in DEST_CITIES

    def test_country_mapping_kenya(self):
        assert COUNTRY_MAP.get("马赛马拉国家保护区") == "肯尼亚"
        assert COUNTRY_MAP.get("纳库鲁") == "肯尼亚"
        assert COUNTRY_MAP.get("奈瓦沙") == "肯尼亚"


# ── Bug D：_extract_transport 长城市名 ───────────────────────────────────
class TestTransportLongCityName:
    def test_long_zh_city_not_truncated(self):
        chunk = "马赛马拉国家保护区 → 内罗毕"
        out = _extract_transport(chunk)
        assert out == ["马赛马拉国家保护区→内罗毕"], f"实际: {out!r}"

    def test_short_city_still_works(self):
        chunk = "北京 → 多哈"
        out = _extract_transport(chunk)
        assert out == ["北京→多哈"]


# ── Bug E：_split_by_day 时间段行也算下日 row1 ────────────────────────────
class TestSplitByDayTrimTimeRowAsNextDayMarker:
    def test_day6_chunk_does_not_contain_day7_hotel_line(self):
        # 模拟 Kenya PDF 实际 chunk（去重后）
        text = (
            "\n05 星期一  保护区\n"
            "2025年5月\n"
            "马赛马拉国家  马赛马拉JW万豪酒店\n"
            "\n06 星期二  保护区\n"
            "2025年5月\n"
            "马赛马拉国家  16:00 - 16:45  中国国际大酒店,Swiss\n"
            "\n07 星期三\n"
            "保护区\n"
        )
        chunks = _split_by_day(text)
        d6 = next((c for dom, c in chunks if dom == 6), None)
        assert d6 is not None, f"未抽到 day 6；chunks={chunks}"
        # Day 6 chunk 不应包含 Day 7 row1 的"中国国际大酒店"那行
        assert "中国国际大酒店" not in d6, f"Day 6 chunk 渗漏 Day 7 内容: {d6!r}"


# ── Bug F：_extract_accommodation 英文 fallback 列分割 ────────────────────
class TestEnglishHotelInColumnMergedRow:
    def test_buraha_extracted_from_attraction_merge(self):
        # 实际 PDF chunk：1. 景点  Lake Nakuru  Buraha zezoni hotel
        # — Lake Nakuru 是景点列内容，Buraha zezoni hotel 是住宿列
        chunk = (
            "内罗毕  1. 纳库鲁湖国家公园 , Lake Nakuru  Buraha zezoni hotel\n"
            "08 星期四  Nairobi  National Park\n"
        )
        # 期望抽到 "Buraha zezoni hotel" 而非整段 "Lake Nakuru  Buraha zezoni hotel"
        out = _extract_accommodation(chunk)
        assert out is not None, f"未抽到英文酒店名；chunk={chunk!r}"
        assert "Buraha" in out and "hotel" in out.lower()
        assert "Lake Nakuru" not in out, f"误吞景点列: {out!r}"


# ── Bug G：概览表无箭头 transport（Day 8/9/10 陆路）── 暂不强求，与端到端绑定 ──


# ── 端到端综合：基于 Kenya PDF 跑一遍，对最关键叶子值断言 ─────────────────
class TestKenyaEndToEnd:
    def test_day1_accommodation_full_name(self, parsed):
        d = _day(parsed, "2025-05-01")
        assert d["accommodation"] == "中国国际大酒店", f"got={d['accommodation']!r}"

    def test_day2_accommodation_jw_marriott_full(self, parsed):
        d = _day(parsed, "2025-05-02")
        assert d["accommodation"] == "马赛马拉JW万豪酒店", f"got={d['accommodation']!r}"

    def test_day6_accommodation_jw_marriott_not_swiss(self, parsed):
        # 关键回归点：Day 6 不应是"中国国际大酒店"（那是 Day 7 内容渗漏）
        d = _day(parsed, "2025-05-06")
        assert "JW" in d["accommodation"] or "万豪" in d["accommodation"], (
            f"Day 6 acc 错配: {d['accommodation']!r}"
        )

    def test_day8_accommodation_buraha(self, parsed):
        d = _day(parsed, "2025-05-08")
        assert d["accommodation"] is not None and "Buraha" in d["accommodation"], (
            f"Day 8 缺英文酒店名: {d['accommodation']!r}"
        )

    def test_day2_transport_full_route(self, parsed):
        d = _day(parsed, "2025-05-02")
        assert d["transport"], "Day 2 transport 不应为空"
        # 整段路径不被截断
        joined = " | ".join(d["transport"])
        assert "马赛马拉国家保护区" in joined, f"Day 2 transport 截断: {joined!r}"

    def test_day7_transport_full_route(self, parsed):
        d = _day(parsed, "2025-05-07")
        assert d["transport"], "Day 7 transport 不应为空"
        joined = " | ".join(d["transport"])
        assert "马赛马拉国家保护区" in joined and "内罗毕" in joined, (
            f"Day 7 transport 不完整: {joined!r}"
        )

    def test_no_phantom_leg(self, parsed):
        cities = {leg["city"] for leg in parsed["legs"]}
        assert "[待确认]" not in cities, f"出现 [待确认] 虚假 leg: {cities}"

    def test_masai_mara_leg_recognized(self, parsed):
        cities = {leg["city"] for leg in parsed["legs"]}
        assert "马赛马拉国家保护区" in cities, f"未出现马赛马拉国家保护区 leg: {cities}"
