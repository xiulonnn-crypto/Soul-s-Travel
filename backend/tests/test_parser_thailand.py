"""Tests for Thailand PDF bilingual attraction-name classification.

穷游 PDF Thailand template puts bilingual attraction names on a single detail-page line:
    曼谷国家博物馆,,BBaannggkkookk NNaattiioonnaall MMuusseeuumm   ← len=53 after dedup
    博物馆                                                      ← type label
    地址 ...

English letters remain doubled after `_normalize` (CJK-only dedup), so the name
line exceeds the 20-char upper bound that the older `_build_activity_category_map`
used for name-line candidates. The activity→category map comes back empty and
every景点 ends up as `其他`.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.ai_parser import _build_activity_category_map, _normalize, parse_text


# ── direct unit coverage for _build_activity_category_map ─────────────────────

class TestActivityCategoryMapBilingualNames:
    """穷游 PDF 中「中文+双写英文」名称行应被识别并映射到类型标签。"""

    def test_cjk_plus_doubled_english_name_line(self):
        """CJK 前缀+双写英文后缀的名称行应抽出 CJK 部分作为键。"""
        text = _normalize(
            "曼谷国家博物馆,,BBaannggkkookk NNaattiioonnaall MMuusseeuumm\n"
            "博物馆\n"
            "地址 xxx\n"
        )
        result = _build_activity_category_map(text)
        assert result.get('曼谷国家博物馆') == '门票', (
            f"bilingual 名称行被过滤，activity_cat={result!r}"
        )

    def test_zoo_type_label_mapped_to_ticket(self):
        """类型标签「动物园」应归为门票。"""
        text = _normalize(
            "清迈夜间动物园,,CChhiiaanngg MMaaii NNiigghhtt SSaaffaarrii\n"
            "动物园\n"
            "地址 xxx\n"
        )
        result = _build_activity_category_map(text)
        assert result.get('清迈夜间动物园') == '门票'

    def test_national_park_type_label_mapped_to_ticket(self):
        """类型标签「国家公园」应归为门票；名称为 英文前缀+CJK 后缀 也需识别。"""
        text = _normalize(
            "KKeerr--CChhoorr大象生态公园\n"
            "国家公园\n"
            "地址 xxx\n"
        )
        result = _build_activity_category_map(text)
        assert result.get('大象生态公园') == '门票'

    def test_district_type_label_mapped_to_ticket(self):
        """类型标签「街区」应归为门票。"""
        text = _normalize(
            "美功铁道集市,,MMaaeekklloonngg MMaarrkkeett\n"
            "街区\n"
            "地址 xxx\n"
        )
        result = _build_activity_category_map(text)
        assert result.get('美功铁道集市') == '门票'

    def test_multiline_name_with_english_continuation(self):
        """长双语名跨两行时，类型标签的反向扫描应跳过纯英文续行找到 CJK 名称行。"""
        text = _normalize(
            "夜游湄南河游轮,,CChhaaoo PPhhrraayyaa PPrriinncceessss DDiinnnneerr\n"
            "CCrruuiissee TThhaaiillaanndd\n"
            "其它活动\n"
            "地址 xxx\n"
        )
        result = _build_activity_category_map(text)
        assert result.get('夜游湄南河游轮') == '门票'


# ── integration: parse_text + expense classification ─────────────────────────

THAILAND_ATTRACTION_TEXT = """SexySouL的泰国行程
2024 年9月15日出发 ｜ 共2天，1个国家，1个城市
作者：SexySouL
曼谷 1. 曼谷国家博物馆
15
星期天 Bangkok 2. 美功铁道集市
2024 年9月 曼谷
Bangkok
曼谷 1. Ker-Chor大象生态公园
16
星期一 Bangkok 2. 夜游湄南河游轮
2024 年9月 曼谷
Bangkok
| P1

曼谷国家博物馆,,BBaannggkkookk NNaattiioonnaall MMuusseeuumm
博物馆
地址 曼谷市区

美功铁道集市,,MMaaeekklloonngg MMaarrkkeett
街区
地址 夜功府

KKeerr--CChhoorr大象生态公园
国家公园
地址 清迈府

夜游湄南河游轮,,CChhaaoo PPhhrraayyaa PPrriinncceessss DDiinnnneerr
CCrruuiissee TThhaaiillaanndd
其它活动
地址 湄南河

第1天（总价：¥1329） 单价 数量 总价
曼谷国家博物馆,Bangkok National Museum CNY 100.00 2 CNY 200
美功铁道集市 CNY 154.00 1 CNY 154
皇家兰花喜来登大酒店 CNY 975.00 1 CNY 975
第2天（总价：¥1657） 单价 数量 总价
Ker-Chor大象生态公园 CNY 210.00 2 CNY 420
夜游湄南河游轮,Chao Phraya Princess Din CNY 262.00 1 CNY 262
皇家兰花喜来登大酒店 CNY 975.00 1 CNY 975
"""


class TestThailandExpenseCategorization:
    """中文+双写英文名称行的景点/活动不应被错放「其他」。"""

    def test_museum_classified_as_ticket(self):
        result = parse_text(THAILAND_ATTRACTION_TEXT)
        museum = next(
            (e for e in result['expenses'] if '博物馆' in e['description']), None
        )
        assert museum is not None, '曼谷国家博物馆未被解析'
        assert museum['category'] == '门票', (
            f"博物馆应为门票，实际={museum['category']} desc={museum['description']!r}"
        )

    def test_market_classified_as_ticket(self):
        result = parse_text(THAILAND_ATTRACTION_TEXT)
        market = next(
            (e for e in result['expenses'] if '美功铁道集市' in e['description']), None
        )
        assert market is not None, '美功铁道集市未被解析'
        assert market['category'] == '门票', (
            f"集市应为门票，实际={market['category']}"
        )

    def test_elephant_park_classified_as_ticket(self):
        result = parse_text(THAILAND_ATTRACTION_TEXT)
        park = next(
            (e for e in result['expenses'] if '大象生态公园' in e['description']), None
        )
        assert park is not None, 'Ker-Chor大象生态公园未被解析'
        assert park['category'] == '门票', (
            f"国家公园应为门票，实际={park['category']}"
        )

    def test_river_cruise_classified_as_ticket(self):
        result = parse_text(THAILAND_ATTRACTION_TEXT)
        cruise = next(
            (e for e in result['expenses'] if '游轮' in e['description']), None
        )
        assert cruise is not None, '夜游湄南河游轮未被解析'
        assert cruise['category'] == '门票', (
            f"游轮(其它活动)应为门票，实际={cruise['category']}"
        )

    def test_forbidden_other_for_known_attractions(self):
        """禁止输出：以上 4 条景点/活动费用中，任何一条被分到「其他」即失败。"""
        result = parse_text(THAILAND_ATTRACTION_TEXT)
        attractions = [
            e for e in result['expenses']
            if any(k in e['description'] for k in
                   ['博物馆', '集市', '大象生态公园', '游轮'])
        ]
        assert len(attractions) == 4, (
            f"景点/活动计数 mismatch: {[(e['description'], e['category']) for e in result['expenses']]}"
        )
        misclassified = [e for e in attractions if e['category'] == '其他']
        assert not misclassified, (
            f"仍有景点被错放其他: {[(e['description'], e['category']) for e in misclassified]}"
        )
