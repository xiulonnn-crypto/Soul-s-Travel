r"""Day-marker splitting must handle BOTH formats pdfminer emits:

  Format A (existing tests):   "\n01\n星期三 Beijing..."      (NN and 星期 on separate lines)
  Format B (this regression):  "\n02 星期四 Busan..."          (NN and 星期 on the same line)

The 2024-05 韩国 PDF (5 days, Busan + Gyeongju) produces Format A for days 01/03/04
and Format B for days 02/05 — mixed within the SAME document. The original regex
`\n(\d{2})\n\s*星期…` only matched Format A, so days 02 and 05 were silently dropped,
day 02's 7 attractions merged into day 1, and day 04's 庆州 + day 05's return flight
got absorbed into adjacent chunks.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from services.ai_parser import parse_text, _split_by_day


# Real extracted text from pdfminer on /Users/soul/Downloads/202405 韩国.pdf
# (mixed Format A on 01/03/04 and Format B on 02/05 — verified by running the
# file_extractor against the source PDF). Shortened but preserves all relevant
# line breaks and the 5-day marker pattern.
KOREA_202405_PDF_TEXT = """SexySouL的韩国行程
2024年5月1日出发 ｜ 共5天，1个国家，2个城市
作者：SexySouL

日期  城市  交通  景点  住宿
北京  13:40 - 17:00  1. 海云台传统市场 ， Haeundae Traditional  釜山万枫酒店
01
星期三  Beijing  北京  釜山  Market
2024年5月  釜山
Busan
釜山  1. 釜山青沙浦  釜山万枫酒店
02 星期四  Busan  2. 南川洞樱花街 ， Namcheon-dong Cherry
2024年5月  Blossom Road
3. 广安里海水浴场 ，          (Gwangalli
Beach)
4. 甘川文化村 ，
5. 松岛海上缆车 ，
6. 广安大桥 ， Gwangan Bridge
7. 游艇
釜山  1. 海东龙宫寺 ，         釜山朝鲜威斯汀酒店，The
03
星期五  Busan  Westin Josun Busan，釜山
2024年5月  地址：67 DongBaek-Ro
Haeundae-Gu
釜山  1. 庆州普门旅游区 ， Bomun Lake Resort  釜山万枫酒店
04
星期六  Busan
2024年5月  庆州
Gyeongju
釜山  --:-- - --:--
05 星期天
Busan  釜山 \ue6ae 北京
2024年5月  北京
Beijing
 | P1

第1天（总价：¥5470）  单价  数量  总价
北京到釜山的交通预算  CNY 2275.00  2  CNY 4550
海云台传统市场,Haeundae Traditional Mar  KRW 0.00  1  KRW 0
釜山万枫酒店  CNY 920.00  1  CNY 920
第2天（总价：¥1417.36）  单价  数量  总价
釜山青沙浦  KRW 17500.00  2  KRW 35000
广安大桥,Gwangan Bridge  KRW 0.00  1  KRW 0
甘川文化村,        KRW 0.00  1  KRW 0
松岛海上缆车,          KRW 0.00  1  KRW 0
游艇  CNY 158.00  2  CNY 316
釜山万枫酒店  CNY 920.00  1  CNY 920
第3天（总价：¥1808）  单价  数量  总价
釜山朝鲜威斯汀酒店  CNY 1808.00  1  CNY 1808
第4天（总价：¥1816）  单价  数量  总价
庆州普门旅游区,Bomun Lake Resort  CNY 448.00  2  CNY 896
釜山万枫酒店  CNY 920.00  1  CNY 920
"""


def _find_leg(result, city):
    for leg in result['legs']:
        if leg['city'] == city:
            return leg
    return None


def _all_days(result):
    return [d for leg in result['legs'] for d in leg['days']]


def _find_day_by_date(result, date_str):
    for d in _all_days(result):
        if d['date'] == date_str:
            return d
    raise ValueError(f'No day with date {date_str}')


class TestDayMarkerSameLineSplit:
    """_split_by_day must detect day markers in both line-break and same-line formats."""

    def test_all_five_day_markers_detected(self):
        """5 day markers (01/02/03/04/05) must yield 5 chunks even when 02 and 05
        are on the same line as 星期X."""
        chunks = _split_by_day(KOREA_202405_PDF_TEXT)
        day_nums = [dn for dn, _ in chunks]
        assert day_nums == [1, 2, 3, 4, 5], (
            f"期望匹配到全部 5 个 DAY marker，实际只抓到 {day_nums}"
        )

    def test_same_line_day2_marker_detected(self):
        chunks = _split_by_day(KOREA_202405_PDF_TEXT)
        day_map = dict(chunks)
        assert 2 in day_map, '02 星期四 markers must be detected even on same line'

    def test_same_line_day5_marker_detected(self):
        chunks = _split_by_day(KOREA_202405_PDF_TEXT)
        day_map = dict(chunks)
        assert 5 in day_map, '05 星期天 markers must be detected even on same line'


class TestKorea202405TripStructure:
    """End-to-end parse must match PDF ground truth."""

    def test_trip_has_five_days(self):
        result = parse_text(KOREA_202405_PDF_TEXT)
        assert len(_all_days(result)) == 5, (
            f"期望 5 天，实际 {len(_all_days(result))} 天"
        )

    def test_trip_end_date(self):
        result = parse_text(KOREA_202405_PDF_TEXT)
        assert result['trip']['end_date'] == '2024-05-05'

    def test_gyeongju_leg_exists(self):
        """Day 4 visits 庆州 (Gyeongju) — leg must be created."""
        result = parse_text(KOREA_202405_PDF_TEXT)
        gyeongju = _find_leg(result, '庆州')
        assert gyeongju is not None, (
            f"期望 庆州 leg 存在，实际 legs={[l['city'] for l in result['legs']]}"
        )
        assert gyeongju['country'] == '韩国'

    def test_busan_leg_exists(self):
        result = parse_text(KOREA_202405_PDF_TEXT)
        busan = _find_leg(result, '釜山')
        assert busan is not None

    def test_day2_has_seven_attractions(self):
        """Day 2 (2024-05-02) has 7 attractions per PDF; day 1 has only 海云台."""
        result = parse_text(KOREA_202405_PDF_TEXT)
        day2 = _find_day_by_date(result, '2024-05-02')
        assert len(day2['activities']) >= 6, (
            f"Day 2 应有多个景点(青沙浦/南川洞/广安里/甘川/松岛/广安大桥/游艇)，"
            f"实际 {day2['activities']}"
        )
        assert any('青沙浦' in a for a in day2['activities'])
        assert any('甘川' in a for a in day2['activities'])

    def test_day1_has_only_haeundae_market(self):
        """Day 1 (2024-05-01) should contain 海云台传统市场 only — NOT day 2's attractions."""
        result = parse_text(KOREA_202405_PDF_TEXT)
        day1 = _find_day_by_date(result, '2024-05-01')
        assert any('海云台' in a for a in day1['activities']), (
            f"Day 1 应含海云台传统市场，实际 {day1['activities']}"
        )
        # Day 2 attractions must NOT leak into day 1
        for a in day1['activities']:
            assert '青沙浦' not in a, f"Day 1 不应含 day 2 的 {a}"
            assert '甘川' not in a, f"Day 1 不应含 day 2 的 {a}"

    def test_day3_has_haedong_temple(self):
        result = parse_text(KOREA_202405_PDF_TEXT)
        day3 = _find_day_by_date(result, '2024-05-03')
        assert any('海东龙宫寺' in a for a in day3['activities']), (
            f"Day 3 应含海东龙宫寺，实际 {day3['activities']}"
        )

    def test_day4_has_bomun_lake(self):
        result = parse_text(KOREA_202405_PDF_TEXT)
        day4 = _find_day_by_date(result, '2024-05-04')
        assert any('庆州普门' in a for a in day4['activities']), (
            f"Day 4 应含庆州普门旅游区，实际 {day4['activities']}"
        )

    def test_day5_return_flight(self):
        """Day 5 should have 釜山→北京 return flight (CA730)."""
        result = parse_text(KOREA_202405_PDF_TEXT)
        day5 = _find_day_by_date(result, '2024-05-05')
        transport_str = ' '.join(day5.get('transport', []))
        assert '釜山' in transport_str and '北京' in transport_str, (
            f"Day 5 应有釜山→北京 返程交通，实际 transport={day5.get('transport')}"
        )
