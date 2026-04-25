"""直接验证 `_parse_expenses` 的 CATEGORY_RULES 覆盖度。

穷游 PDF 费用表的 description 栏可能是「纯类型裸标签」（如 `美食`、`活动`、
`GOCITY`）或「中文景点名」（如 `爱丁堡城堡`、`大英博物馆`、`游艇`）。当
CATEGORY_RULES 仅覆盖少量窄关键字（餐饮只认 `午餐|晚餐|早餐|餐饮|餐厅|饭`、
门票只认 `门票|景点|入场|一日游|半日游|游览`）时，大量常见条目会被兜底到
`其他`。本文件锁住以下分类（实测来自 5 份真实 PDF）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from services.ai_parser import _parse_expenses


def _make(rows: list[str]) -> str:
    """Wrap expense rows under a day-total header so _parse_expenses picks them up."""
    header = "第1天(总价:¥10000) 单价 数量 总价\n"
    return header + "\n".join(rows) + "\n"


def _find(expenses, keyword):
    for e in expenses:
        if keyword in e["description"]:
            return e
    raise AssertionError(
        f"description 中含 {keyword!r} 的条目未解析出；实际={[e['description'] for e in expenses]}"
    )


class TestDiningKeywords:
    """餐饮类应覆盖穷游 PDF 常见的「美食 / 小吃 / 料理」裸标签。"""

    def test_meishi_is_dining(self):
        exp = _parse_expenses(_make(["美食 CNY 2893.15 1 CNY 2893.15"]))
        assert _find(exp, "美食")["category"] == "餐饮"

    def test_xiaochi_is_dining(self):
        exp = _parse_expenses(_make(["小吃 CNY 120 1 CNY 120"]))
        assert _find(exp, "小吃")["category"] == "餐饮"

    def test_liaoli_is_dining(self):
        exp = _parse_expenses(_make(["日式料理 CNY 400 1 CNY 400"]))
        assert _find(exp, "料理")["category"] == "餐饮"


class TestTicketKeywords:
    """门票类应覆盖穷游 PDF 常见的「活动 / 城堡 / 宫殿 / 博物馆 / 动物园 /
    主题乐园 / 游艇 / GoCity 票券」。"""

    def test_huodong_bare_label_is_ticket(self):
        """`活动` 裸标签（UK PDF 共 3 行）应为门票，而非其他。"""
        exp = _parse_expenses(_make(["活动 CNY 4.69 1 CNY 4.69"]))
        assert _find(exp, "活动")["category"] == "门票"

    def test_huodong_with_suffix_is_ticket(self):
        """`活动-加时费` 之类描述应为门票。"""
        exp = _parse_expenses(_make(["活动-加时费 CNY 352.5 1 CNY 352.5"]))
        assert _find(exp, "活动")["category"] == "门票"

    def test_chengbao_is_ticket(self):
        """`爱丁堡城堡`（UK PDF 真实条目）应为门票。"""
        exp = _parse_expenses(_make(["爱丁堡城堡 CNY 359.00 2 CNY 718"]))
        assert _find(exp, "城堡")["category"] == "门票"

    def test_gugong_is_ticket(self):
        """`白金汉宫` 之类「宫」景点应为门票。"""
        exp = _parse_expenses(_make(["白金汉宫 CNY 280 1 CNY 280"]))
        assert _find(exp, "白金汉宫")["category"] == "门票"

    def test_bowuguan_is_ticket(self):
        """`博物馆` 字面匹配（不依赖详情页 activity_cat）应为门票。"""
        exp = _parse_expenses(_make(["大英博物馆 CNY 198.00 2 CNY 396"]))
        assert _find(exp, "博物馆")["category"] == "门票"

    def test_dongwuyuan_is_ticket(self):
        exp = _parse_expenses(_make(["上野动物园 CNY 50 1 CNY 50"]))
        assert _find(exp, "动物园")["category"] == "门票"

    def test_theme_park_is_ticket(self):
        exp = _parse_expenses(_make(["迪士尼主题乐园 CNY 699 1 CNY 699"]))
        assert _find(exp, "主题乐园")["category"] == "门票"

    def test_yacht_is_ticket(self):
        """`游艇`（韩国 PDF 真实条目）应为门票。"""
        exp = _parse_expenses(_make(["游艇 CNY 158 2 CNY 316"]))
        assert _find(exp, "游艇")["category"] == "门票"

    def test_gocity_is_ticket(self):
        """`GOCITY` 通票（UK PDF 真实条目）应为门票。"""
        exp = _parse_expenses(_make(["GOCITY CNY 2001.00 1 CNY 2001"]))
        assert _find(exp, "GOCITY")["category"] == "门票"

    def test_go_city_spaced_is_ticket(self):
        """`GO CITY`（新加坡 PDF 真实条目，带空格）应为门票。"""
        exp = _parse_expenses(_make(["GO CITY CNY 1745 2 CNY 3490"]))
        assert _find(exp, "GO CITY")["category"] == "门票"

    def test_luge_is_ticket(self):
        """`圣淘沙天际线斜坡滑车,Skyline Sentosa Luge`（新加坡 PDF 真实条目）
        应为门票（匹配 `滑车` / `Luge` / `Skyline` 任一关键字）。"""
        exp = _parse_expenses(_make([
            "圣淘沙天际线斜坡滑车,Skyline Sentosa Luge CNY 189 2 CNY 378"
        ]))
        assert _find(exp, "滑车")["category"] == "门票"


class TestNoRegression:
    """既有关键字仍需命中原类别。"""

    def test_wucan_still_dining(self):
        exp = _parse_expenses(_make(["午餐 CNY 80 1 CNY 80"]))
        assert _find(exp, "午餐")["category"] == "餐饮"

    def test_jiudian_still_accommodation(self):
        exp = _parse_expenses(_make(["槟城东方大酒店 CNY 800 1 CNY 800"]))
        assert _find(exp, "酒店")["category"] == "住宿"

    def test_dache_still_transport(self):
        exp = _parse_expenses(_make(["打车 CNY 35 1 CNY 35"]))
        assert _find(exp, "打车")["category"] == "交通"

    def test_jichang_daijie_still_transport(self):
        exp = _parse_expenses(_make(["机票 CNY 3000 1 CNY 3000"]))
        assert _find(exp, "机票")["category"] == "交通"

    def test_menpiao_still_ticket(self):
        exp = _parse_expenses(_make(["景点门票 CNY 50 1 CNY 50"]))
        assert _find(exp, "门票")["category"] == "门票"

    def test_gouwu_still_shopping(self):
        exp = _parse_expenses(_make(["购物纪念品 CNY 200 1 CNY 200"]))
        assert _find(exp, "购物")["category"] == "购物"


class TestStillOtherWhenUnknown:
    """真正无法判定的条目仍保持「其他」。"""

    def test_baoxian_stays_other(self):
        """`保险` 不在任何业务类别（交通/住宿/餐饮/门票/购物），保持其他。"""
        exp = _parse_expenses(_make(["保险 CNY 524 1 CNY 524"]))
        assert _find(exp, "保险")["category"] == "其他"

    def test_qianzheng_stays_other(self):
        exp = _parse_expenses(_make(["签证 CNY 2178 1 CNY 2178"]))
        assert _find(exp, "签证")["category"] == "其他"

    def test_cash_opaque_stays_other(self):
        """`现金开销 / 信用卡开销`（泰国 PDF 真实条目）无具体分类信息，保持其他。"""
        exp = _parse_expenses(_make(["现金开销 CNY 2870 1 CNY 2870"]))
        assert _find(exp, "现金")["category"] == "其他"


class TestSightseeingBoatKeywords:
    """游船/游轮 是观光消费，不是运输，应归入门票。
    普通渡船/乘船 仍归交通。"""

    def test_youchuan_is_ticket(self):
        """「游船」（越南湄公河游船体验）应为门票，而非交通。"""
        exp = _parse_expenses(_make(["游船 CNY 150 1 CNY 150"]))
        assert _find(exp, "游船")["category"] == "门票"

    def test_youhulun_is_ticket(self):
        """「游轮」（邮轮观光体验）应为门票。"""
        exp = _parse_expenses(_make(["游轮 CNY 2000 1 CNY 2000"]))
        assert _find(exp, "游轮")["category"] == "门票"

    def test_halongbay_youchuan_is_ticket(self):
        """「下龙湾游船」（真实行程描述）应为门票。"""
        exp = _parse_expenses(_make(["下龙湾游船 CNY 680 1 CNY 680"]))
        assert _find(exp, "游船")["category"] == "门票"

    def test_duchuan_still_transport(self):
        """「渡船」仍应为交通（轮渡通勤，非观光）。"""
        exp = _parse_expenses(_make(["渡船 CNY 30 1 CNY 30"]))
        assert _find(exp, "渡船")["category"] == "交通"

    def test_chengchuan_still_transport(self):
        """「乘船前往」仍应为交通。"""
        exp = _parse_expenses(_make(["乘船前往富国岛 CNY 80 1 CNY 80"]))
        assert _find(exp, "乘船")["category"] == "交通"


class TestPerformanceKeywords:
    """表演/展览 是付费文化体验，应归门票。"""

    def test_biaoyan_is_ticket(self):
        """「水上木偶表演」（越南 PDF 真实条目）应为门票。"""
        exp = _parse_expenses(_make(["水上木偶表演 CNY 100 1 CNY 100"]))
        assert _find(exp, "表演")["category"] == "门票"

    def test_zaji_is_ticket(self):
        """「杂技表演」应为门票。"""
        exp = _parse_expenses(_make(["杂技表演 CNY 180 1 CNY 180"]))
        assert _find(exp, "表演")["category"] == "门票"

    def test_zhanlan_is_ticket(self):
        """「展览」（博物馆临时展、美术展）应为门票。"""
        exp = _parse_expenses(_make(["美术展览 CNY 80 1 CNY 80"]))
        assert _find(exp, "展览")["category"] == "门票"

    def test_tiyan_is_ticket(self):
        """「茶道体验」（日本 PDF 常见条目）应为门票（付费活动体验）。"""
        exp = _parse_expenses(_make(["茶道体验 CNY 200 1 CNY 200"]))
        assert _find(exp, "体验")["category"] == "门票"


class TestTeaDiningKeywords:
    """下午茶 / 早茶 / 奶茶 是餐饮消费，应归餐饮。"""

    def test_xiawucha_is_dining(self):
        """「下午茶」应为餐饮。"""
        exp = _parse_expenses(_make(["下午茶套餐 CNY 200 1 CNY 200"]))
        assert _find(exp, "下午茶")["category"] == "餐饮"

    def test_zaocha_is_dining(self):
        """「早茶」（港式早茶）应为餐饮。"""
        exp = _parse_expenses(_make(["早茶 CNY 120 1 CNY 120"]))
        assert _find(exp, "早茶")["category"] == "餐饮"

    def test_naicha_is_dining(self):
        """「奶茶」应为餐饮。"""
        exp = _parse_expenses(_make(["奶茶 CNY 25 1 CNY 25"]))
        assert _find(exp, "奶茶")["category"] == "餐饮"


class TestTransportPickupKeywords:
    """接机/送机 是常见地接交通，应归交通。"""

    def test_jieji_hcmc_is_transport(self):
        """「胡志明接机」（越南 PDF 真实条目）应为交通。"""
        exp = _parse_expenses(_make(["胡志明接机 CNY 306 1 CNY 306"]))
        assert _find(exp, "接机")["category"] == "交通"

    def test_songji_is_transport(self):
        """「送机服务」应为交通。"""
        exp = _parse_expenses(_make(["送机服务 CNY 200 1 CNY 200"]))
        assert _find(exp, "送机")["category"] == "交通"


class TestCuisineDiningKeywords:
    """菜系名称（法餐/西餐/中餐等）是餐饮消费，应归餐饮。"""

    def test_facai_is_dining(self):
        """「法餐」（越南 PDF 真实条目）应为餐饮。"""
        exp = _parse_expenses(_make(["法餐 CNY 3253 1 CNY 3253"]))
        assert _find(exp, "法餐")["category"] == "餐饮"

    def test_xican_is_dining(self):
        """「西餐」应为餐饮。"""
        exp = _parse_expenses(_make(["西餐 CNY 500 1 CNY 500"]))
        assert _find(exp, "西餐")["category"] == "餐饮"

    def test_rican_is_dining(self):
        """「日餐」应为餐饮。"""
        exp = _parse_expenses(_make(["日餐 CNY 300 1 CNY 300"]))
        assert _find(exp, "日餐")["category"] == "餐饮"
