import re
import unicodedata
from datetime import datetime, timedelta
from collections import OrderedDict


# ── Kangxi Radical → Standard CJK ────────────────────────────────────────────
_RADICAL_MAP = {
    '\u2F00':'\u4E00','\u2F01':'\u4E28','\u2F02':'\u4E36','\u2F03':'\u4E3F',
    '\u2F04':'\u4E59','\u2F05':'\u4E85','\u2F06':'\u4E8C','\u2F07':'\u4EA0',
    '\u2F08':'\u4EBA','\u2F09':'\u513F','\u2F0A':'\u5165','\u2F0B':'\u516B',
    '\u2F0C':'\u5182','\u2F0D':'\u5196','\u2F0E':'\u51AB','\u2F0F':'\u51E0',
    '\u2F10':'\u51F5','\u2F11':'\u5200','\u2F12':'\u529B','\u2F13':'\u52F9',
    '\u2F14':'\u5315','\u2F15':'\u531A','\u2F16':'\u5338','\u2F17':'\u5341',
    '\u2F18':'\u535C','\u2F19':'\u5369','\u2F1A':'\u5382','\u2F1B':'\u53B6',
    '\u2F1C':'\u53C8','\u2F1D':'\u53E3','\u2F1E':'\u56D7','\u2F1F':'\u571F',
    '\u2F20':'\u58EB','\u2F21':'\u5902','\u2F22':'\u590A','\u2F23':'\u5915',
    '\u2F24':'\u5927','\u2F25':'\u5973','\u2F26':'\u5B50','\u2F27':'\u5B80',
    '\u2F28':'\u5BF8','\u2F29':'\u5C0F','\u2F2A':'\u5C22','\u2F2B':'\u5C38',
    '\u2F2C':'\u5C6E','\u2F2D':'\u5C71','\u2F2E':'\u5DDB','\u2F2F':'\u5DE5',
    '\u2F30':'\u5DF1','\u2F31':'\u5DFE','\u2F32':'\u5E72','\u2F33':'\u5E7A',
    '\u2F34':'\u5E7F','\u2F35':'\u5EF4','\u2F36':'\u5EFE','\u2F37':'\u5F0B',
    '\u2F38':'\u5F13','\u2F39':'\u5F50','\u2F3A':'\u5F61','\u2F3B':'\u5F73',
    '\u2F3C':'\u5FC3','\u2F3D':'\u6208','\u2F3E':'\u6236','\u2F3F':'\u624B',
    '\u2F40':'\u652F','\u2F41':'\u6534','\u2F42':'\u6587','\u2F43':'\u6597',
    '\u2F44':'\u65A4','\u2F45':'\u65B9','\u2F46':'\u65E0','\u2F47':'\u65E5',
    '\u2F48':'\u66F0','\u2F49':'\u6708','\u2F4A':'\u6728','\u2F4B':'\u6B20',
    '\u2F4C':'\u6B62','\u2F4D':'\u6B79','\u2F4E':'\u6BB3','\u2F4F':'\u6BCB',
    '\u2F50':'\u6BD4','\u2F51':'\u6BDB','\u2F52':'\u6C0F','\u2F53':'\u6C14',
    '\u2F54':'\u6C34','\u2F55':'\u706B','\u2F56':'\u722A','\u2F57':'\u7236',
    '\u2F58':'\u723B','\u2F59':'\u723F','\u2F5A':'\u7247','\u2F5B':'\u7259',
    '\u2F5C':'\u725B','\u2F5D':'\u72AC','\u2F5E':'\u7384','\u2F5F':'\u7389',
    '\u2F60':'\u74DC','\u2F61':'\u74E6','\u2F62':'\u7518','\u2F63':'\u751F',
    '\u2F64':'\u7528','\u2F65':'\u7530','\u2F66':'\u758B','\u2F67':'\u7592',
    '\u2F68':'\u7676','\u2F69':'\u767D','\u2F6A':'\u76AE','\u2F6B':'\u76BF',
    '\u2F6C':'\u76EE','\u2F6D':'\u77DB','\u2F6E':'\u77E2','\u2F6F':'\u77F3',
    '\u2F70':'\u793A','\u2F71':'\u79B8','\u2F72':'\u79BE','\u2F73':'\u7A74',
    '\u2F74':'\u7ACB','\u2F75':'\u7AF9','\u2F76':'\u7C73','\u2F77':'\u7CF8',
    '\u2F78':'\u7F36','\u2F79':'\u7F51','\u2F7A':'\u7F8A','\u2F7B':'\u7FBD',
    '\u2F7C':'\u8001','\u2F7D':'\u800C','\u2F7E':'\u8012','\u2F7F':'\u8033',
    '\u2F80':'\u807F','\u2F81':'\u8089','\u2F82':'\u81E3','\u2F83':'\u81EA',
    '\u2F84':'\u81F3','\u2F85':'\u81FC','\u2F86':'\u820C','\u2F87':'\u821B',
    '\u2F88':'\u821F','\u2F89':'\u826E','\u2F8A':'\u8272','\u2F8B':'\u8278',
    '\u2F8C':'\u864D','\u2F8D':'\u866B','\u2F8E':'\u8840','\u2F8F':'\u884C',
    '\u2F90':'\u8863','\u2F91':'\u897E','\u2F92':'\u898B','\u2F93':'\u89D2',
    '\u2F94':'\u8A00','\u2F95':'\u8C37','\u2F96':'\u8C46','\u2F97':'\u8C55',
    '\u2F98':'\u8C78','\u2F99':'\u8C9D','\u2F9A':'\u8D64','\u2F9B':'\u8D70',
    '\u2F9C':'\u8DB3','\u2F9D':'\u8EAB','\u2F9E':'\u8ECA','\u2F9F':'\u8F9B',
    '\u2FA0':'\u8FB0','\u2FA1':'\u8FB5','\u2FA2':'\u9091','\u2FA3':'\u9149',
    '\u2FA4':'\u91C6','\u2FA5':'\u91CC','\u2FA6':'\u91D1','\u2FA7':'\u9577',
    '\u2FA8':'\u9580','\u2FA9':'\u961C','\u2FAA':'\u96B6','\u2FAB':'\u96B9',
    '\u2FAC':'\u96E8','\u2FAD':'\u9751','\u2FAE':'\u975E','\u2FAF':'\u9762',
    '\u2FB0':'\u9769','\u2FB1':'\u97CB','\u2FB2':'\u97ED','\u2FB3':'\u97F3',
    '\u2FB4':'\u9801','\u2FB5':'\u98A8','\u2FB6':'\u98DB','\u2FB7':'\u98DF',
    '\u2FB8':'\u9996','\u2FB9':'\u9999','\u2FBA':'\u99AC','\u2FBB':'\u9AA8',
    '\u2FBC':'\u9AD8','\u2FBD':'\u9ADF','\u2FBE':'\u9B25','\u2FBF':'\u9B2F',
    '\u2FC0':'\u9B32','\u2FC1':'\u9B3C','\u2FC2':'\u9B5A','\u2FC3':'\u9CE5',
    '\u2FC4':'\u9E75','\u2FC5':'\u9E7F','\u2FC6':'\u9EA5','\u2FC7':'\u9EBB',
    '\u2FC8':'\u9EC3','\u2FC9':'\u9ECD','\u2FCA':'\u9ED1','\u2FCB':'\u9EF9',
    '\u2FCC':'\u9EFD','\u2FCD':'\u9F0E','\u2FCE':'\u9F13','\u2FCF':'\u9F20',
    '\u2FD0':'\u9F3B','\u2FD1':'\u9F4A','\u2FD2':'\u9F52','\u2FD3':'\u9F8D',
    '\u2FD4':'\u9F9C','\u2FD5':'\u9FA0',
}

# English city name → Chinese
_EN_TO_ZH_CITY = {
    # 缅甸
    'Mandalay': '曼德勒', 'Bagan': '蒲甘', 'Inle': '茵莱湖',
    'Yangon': '仰光', 'Nyaung': '良乌',
    # 泰国
    'Bangkok': '曼谷', 'Chiang Mai': '清迈', 'Phuket': '普吉岛',
    'Pattaya': '芭提雅', 'Koh Samui': '苏梅岛', 'Ko Samui': '苏梅岛',
    'Chiang Rai': '清莱', 'Hua Hin': '华欣', 'Krabi': '喀比',
    # 马来西亚
    'Kuala Lumpur': '吉隆坡', 'KL': '吉隆坡', 'Penang': '槟城',
    'George Town': '乔治市', 'Malacca': '马六甲', 'Melaka': '马六甲',
    'Kuching': '古晋', 'Kota Kinabalu': '亚庇', 'Langkawi': '兰卡威',
    'Johor Bahru': '新山',
    # 越南
    'Hanoi': '河内', 'Ho Chi Minh': '胡志明市', 'Saigon': '胡志明市',
    'Da Nang': '岘港', 'Danang': '岘港', 'Hoi An': '会安',
    'Ha Long': '下龙湾', 'Nha Trang': '芽庄', 'Da Lat': '大叻',
    'Hue': '顺化', 'Phu Quoc': '富国岛',
    # 韩国
    'Seoul': '首尔', 'Busan': '釜山', 'Jejudo': '济州岛', 'Jeju': '济州市',
    'Seogwipo': '西归浦', 'Incheon': '仁川', 'Gyeongju': '庆州',
    'Jeonju': '全州', 'Daegu': '大邱', 'Gangneung': '江陵',
    'Chuncheon': '春川', 'Andong': '安东',
    # 日本
    'Tokyo': '东京', 'Kyoto': '京都', 'Osaka': '大阪', 'Nara': '奈良',
    'Hokkaido': '北海道', 'Sapporo': '札幌', 'Okinawa': '冲绳',
    'Naha': '那霸', 'Hiroshima': '广岛', 'Fukuoka': '福冈',
    'Hakone': '箱根', 'Kamakura': '镰仓', 'Kanazawa': '金泽',
    'Sendai': '仙台', 'Nagasaki': '长崎', 'Kobe': '神户',
    'Nagoya': '名古屋',
    # 卡塔尔
    'Doha': '多哈',
    # 马尔代夫
    'Male': '马累', "Malé": '马累',
    'Maldives': '马尔代夫', 'Maafushi': '马富施',
    # 文莱
    'Bandar Seri Begawan': '斯里巴加湾市', 'BSB': '斯里巴加湾市',
    # 斯里兰卡
    'Colombo': '科伦坡', 'Kandy': '康提', 'Nuwara Eliya': '努沃勒埃利耶',
    'Galle': '加勒', 'Sigiriya': '锡吉里耶',
    'Negombo': '尼甘布', 'Dambulla': '丹布勒', 'Ella': '埃勒',
    'Tissa': '蒂瑟', 'Tissamaharama': '蒂瑟',
    'Mirissa': '美瑞莎', 'Weligama': '美瑞莎',
    'Trincomalee': '亭可马里', 'Anuradhapura': '阿努拉德普勒',
    # 蒙古
    'Ulaanbaatar': '乌兰巴托', 'Ulan Bator': '乌兰巴托', 'Karakorum': '哈拉和林',
    # 英国
    'London': '伦敦', 'Edinburgh': '爱丁堡', 'Manchester': '曼彻斯特',
    'Liverpool': '利物浦', 'York': '约克', 'Cambridge': '剑桥',
    'Oxford': '牛津', 'Bath': '巴斯',
    # 奥地利
    'Vienna': '维也纳', 'Salzburg': '萨尔茨堡', 'Innsbruck': '因斯布鲁克',
    'Graz': '格拉茨', 'Hallstatt': '哈尔施塔特',
    # 德国
    'Munich': '慕尼黑', 'Berlin': '柏林', 'Frankfurt': '法兰克福',
    'Hamburg': '汉堡', 'Cologne': '科隆', 'Heidelberg': '海德堡',
    'Nuremberg': '纽伦堡', 'Dresden': '德累斯顿', 'Rothenburg': '罗滕堡',
    # 丹麦
    'Copenhagen': '哥本哈根', 'Aarhus': '奥胡斯', 'Odense': '欧登塞',
    # 瑞典
    'Stockholm': '斯德哥尔摩', 'Gothenburg': '哥德堡', 'Malmo': '马尔默',
    'Kiruna': '基律纳',
    # 芬兰
    'Helsinki': '赫尔辛基', 'Rovaniemi': '罗瓦涅米', 'Tampere': '坦佩雷',
    'Turku': '图尔库',
    # 挪威
    'Oslo': '奥斯陆', 'Bergen': '卑尔根', 'Tromso': '特罗姆瑟',
    'Tromsø': '特罗姆瑟', 'Geiranger': '盖朗厄尔',
    # 肯尼亚
    'Nairobi': '内罗毕', 'Mombasa': '蒙巴萨', 'Malindi': '马林迪',
    # 埃及
    'Cairo': '开罗', 'Luxor': '卢克索', 'Aswan': '阿斯旺',
    'Sharm el-Sheikh': '沙姆沙伊赫', 'Hurghada': '赫尔格达',
    'Alexandria': '亚历山大', 'Abu Simbel': '阿布辛贝',
    # 其他已有
    'Beijing': '北京', 'Singapore': '新加坡',
    'Paris': '巴黎', 'Sydney': '悉尼', 'Siem': '暹粒',
}

# Cities that are DESTINATIONS (not departure/transit origins to be filtered)
DEST_CITIES = [
    # 缅甸
    '曼德勒', '蒲甘', '茵莱湖', '仰光', '良乌', '娘水',
    # 泰国
    '曼谷', '清迈', '普吉岛', '芭提雅', '苏梅岛', '清莱', '华欣', '喀比',
    # 马来西亚
    '吉隆坡', '槟城', '乔治市', '马六甲', '古晋', '亚庇', '兰卡威', '新山',
    # 越南
    '河内', '胡志明市', '岘港', '会安', '下龙湾', '芽庄', '大叻', '顺化', '富国岛',
    # 韩国
    '首尔', '釜山', '济州岛', '济州市', '西归浦', '仁川', '庆州', '全州', '大邱', '江陵', '春川', '安东',
    # 日本
    '东京', '京都', '大阪', '奈良', '北海道', '札幌', '冲绳', '那霸',
    '广岛', '福冈', '箱根', '镰仓', '金泽', '仙台', '长崎', '神户', '名古屋',
    # 卡塔尔
    '多哈',
    # 马尔代夫
    '马累', '马尔代夫', '马富施',
    # 新加坡
    '新加坡',
    # 文莱
    '斯里巴加湾市',
    # 斯里兰卡
    '科伦坡', '康提', '康堤', '努沃勒埃利耶', '努瓦勒埃利耶',
    '加勒', '锡吉里耶', '尼甘布', '丹布勒', '埃勒',
    '蒂瑟', '美瑞莎', '亭可马里', '阿努拉德普勒',
    # 蒙古
    '乌兰巴托', '哈拉和林',
    # 英国
    '伦敦', '爱丁堡', '曼彻斯特', '利物浦', '约克', '剑桥', '牛津', '巴斯',
    # 奥地利
    '维也纳', '萨尔茨堡', '因斯布鲁克', '格拉茨', '哈尔施塔特',
    # 德国
    '慕尼黑', '柏林', '法兰克福', '汉堡', '科隆', '海德堡', '纽伦堡', '德累斯顿', '罗滕堡',
    # 丹麦
    '哥本哈根', '奥胡斯', '欧登塞',
    # 瑞典
    '斯德哥尔摩', '哥德堡', '马尔默', '基律纳',
    # 芬兰
    '赫尔辛基', '罗瓦涅米', '坦佩雷', '图尔库',
    # 挪威
    '奥斯陆', '卑尔根', '特罗姆瑟', '盖朗厄尔',
    # 肯尼亚
    '内罗毕', '蒙巴萨', '马林迪',
    # 埃及
    '开罗', '卢克索', '阿斯旺', '沙姆沙伊赫', '赫尔格达', '亚历山大', '阿布辛贝',
    # 其他已有
    '暹粒', '巴黎', '纽约',
    '香港', '澳门', '台北',
]

COUNTRY_MAP = {
    # 缅甸
    '曼德勒': '缅甸', '蒲甘': '缅甸', '茵莱湖': '缅甸', '仰光': '缅甸',
    '良乌': '缅甸', '娘水': '缅甸',
    # 泰国
    '曼谷': '泰国', '清迈': '泰国', '普吉岛': '泰国', '芭提雅': '泰国',
    '苏梅岛': '泰国', '清莱': '泰国', '华欣': '泰国', '喀比': '泰国',
    # 马来西亚
    '吉隆坡': '马来西亚', '槟城': '马来西亚', '乔治市': '马来西亚',
    '马六甲': '马来西亚', '古晋': '马来西亚', '亚庇': '马来西亚',
    '兰卡威': '马来西亚', '新山': '马来西亚',
    # 越南
    '河内': '越南', '胡志明市': '越南', '岘港': '越南', '会安': '越南',
    '下龙湾': '越南', '芽庄': '越南', '大叻': '越南', '顺化': '越南', '富国岛': '越南',
    # 韩国
    '首尔': '韩国', '釜山': '韩国', '济州岛': '韩国', '济州市': '韩国',
    '西归浦': '韩国', '仁川': '韩国', '庆州': '韩国', '全州': '韩国',
    '大邱': '韩国', '江陵': '韩国', '春川': '韩国', '安东': '韩国',
    # 日本
    '东京': '日本', '京都': '日本', '大阪': '日本', '奈良': '日本',
    '北海道': '日本', '札幌': '日本', '冲绳': '日本', '那霸': '日本',
    '广岛': '日本', '福冈': '日本', '箱根': '日本', '镰仓': '日本',
    '金泽': '日本', '仙台': '日本', '长崎': '日本', '神户': '日本', '名古屋': '日本',
    # 卡塔尔
    '多哈': '卡塔尔',
    # 马尔代夫
    '马累': '马尔代夫', '马尔代夫': '马尔代夫', '马富施': '马尔代夫',
    # 新加坡
    '新加坡': '新加坡',
    # 文莱
    '斯里巴加湾市': '文莱',
    # 斯里兰卡
    '科伦坡': '斯里兰卡', '康提': '斯里兰卡', '康堤': '斯里兰卡',
    '努沃勒埃利耶': '斯里兰卡', '努瓦勒埃利耶': '斯里兰卡',
    '加勒': '斯里兰卡', '锡吉里耶': '斯里兰卡',
    '尼甘布': '斯里兰卡', '丹布勒': '斯里兰卡', '埃勒': '斯里兰卡',
    '蒂瑟': '斯里兰卡', '美瑞莎': '斯里兰卡',
    '亭可马里': '斯里兰卡', '阿努拉德普勒': '斯里兰卡',
    # 蒙古
    '乌兰巴托': '蒙古', '哈拉和林': '蒙古',
    # 英国
    '伦敦': '英国', '爱丁堡': '英国', '曼彻斯特': '英国', '利物浦': '英国',
    '约克': '英国', '剑桥': '英国', '牛津': '英国', '巴斯': '英国',
    # 奥地利
    '维也纳': '奥地利', '萨尔茨堡': '奥地利', '因斯布鲁克': '奥地利',
    '格拉茨': '奥地利', '哈尔施塔特': '奥地利',
    # 德国
    '慕尼黑': '德国', '柏林': '德国', '法兰克福': '德国', '汉堡': '德国',
    '科隆': '德国', '海德堡': '德国', '纽伦堡': '德国', '德累斯顿': '德国', '罗滕堡': '德国',
    # 丹麦
    '哥本哈根': '丹麦', '奥胡斯': '丹麦', '欧登塞': '丹麦',
    # 瑞典
    '斯德哥尔摩': '瑞典', '哥德堡': '瑞典', '马尔默': '瑞典', '基律纳': '瑞典',
    # 芬兰
    '赫尔辛基': '芬兰', '罗瓦涅米': '芬兰', '坦佩雷': '芬兰', '图尔库': '芬兰',
    # 挪威
    '奥斯陆': '挪威', '卑尔根': '挪威', '特罗姆瑟': '挪威', '盖朗厄尔': '挪威',
    # 肯尼亚
    '内罗毕': '肯尼亚', '蒙巴萨': '肯尼亚', '马林迪': '肯尼亚',
    # 埃及
    '开罗': '埃及', '卢克索': '埃及', '阿斯旺': '埃及', '沙姆沙伊赫': '埃及',
    '赫尔格达': '埃及', '亚历山大': '埃及', '阿布辛贝': '埃及',
    # 其他
    '北京': '中国', '暹粒': '柬埔寨',
    '巴黎': '法国', '纽约': '美国',
    '香港': '中国', '澳门': '中国', '台北': '中国',
}


def _normalize(text):
    """Normalize CJK radicals + null-byte arrows + NFKC + de-duplicate adjacent identical CJK chars."""
    # Replace null bytes used as arrow separators in PDF (e.g. 广州\x00曼谷)
    text = text.replace('\x00', '→')
    # PUA arrow chars used by some PDF fonts (穷游 Korea PDF uses \ue6ae)
    text = text.replace('\ue6ae', '→')
    chars = [_RADICAL_MAP.get(ch, ch) for ch in text]
    text = unicodedata.normalize('NFKC', ''.join(chars))
    # Handle CJK Radical Supplements (U+2E80–U+2EFF) not normalized by NFKC.
    # Mapped from actual codepoints found in this PDF by scanning.
    _RS_MAP = {
        '\u2ea0': '\u6c11',  # ⺠ CIVILIAN → 民
        '\u2ec4': '\u897f',  # ⻄ WEST → 西
        '\u2ec5': '\u89c1',  # ⻅ SEE → 见
        '\u2ecb': '\u8f66',  # ⻋ CART → 车
        '\u2ed3': '\u957f',  # ⻓ LONG → 长
        '\u2ed4': '\u95e8',  # ⻔ GATE → 门
        '\u2edb': '\u98ce',  # ⻛ WIND → 风
        '\u2edc': '\u98de',  # ⻜ FLY → 飞
        '\u2ee2': '\u9a6c',  # ⻢ HORSE → 马  ← key: 马哈根达杨僧院
        '\u2ee5': '\u9c7c',  # ⻥ FISH → 鱼
        '\u2ee9': '\u9ec4',  # ⻩ YELLOW → 黄
    }
    text = ''.join(_RS_MAP.get(ch, ch) for ch in text)
    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if '\u4e00' <= ch <= '\u9fff' and i + 1 < len(text) and text[i + 1] == ch:
            result.append(ch)
            i += 2
        else:
            result.append(ch)
            i += 1
    text = ''.join(result)

    # Fix PDF-doubled digit sequences in day-header context without touching
    # amounts elsewhere. Examples: 第第11天天→第1天, 第第1100天天→第10天,
    # 第第1111天天→第11天. The PDF doubles each char: 第10天→第第1100天天.
    # After CJK dedup: 第1100天. Collapse consecutive identical pairs of digits.
    def _dedup_day_num(m):
        s = m.group(1)
        n = len(s)
        if n >= 2 and n % 2 == 0:
            deduped = ''
            for i in range(0, n, 2):
                if s[i] != s[i + 1]:
                    return m.group(0)
                deduped += s[i]
            return f'第{deduped}天'
        return m.group(0)

    text = re.sub(r'第(\d+)天', _dedup_day_num, text)
    return text


def _extract_trip_header(text):
    """Extract title, start_date, duration, traveler_count."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    title = None
    for i, ln in enumerate(lines[:6]):
        if len(ln) > 3 and not re.match(r'^(作者|日期|城市|交通|景点|住宿)', ln):
            # Join short continuation lines (PDF line-break in title)
            if (i + 1 < len(lines) and len(lines[i + 1]) <= 2
                    and re.match(r'^[\u4e00-\u9fff]+$', lines[i + 1])):
                title = ln + lines[i + 1]
            else:
                title = ln
            break

    start_date = None
    m = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]', text)
    if m:
        try:
            start_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    duration = None
    m = re.search(r'共\s*(\d+)\s*天', text)
    if m:
        duration = int(m.group(1))

    traveler_count = 1
    # check expense table qty column (most reliable indicator of party size)
    qtys = re.findall(r'CNY\s*[\d,.]+\s+(\d)\s+CNY', text)
    if qtys:
        common = max(set(qtys), key=qtys.count)
        n = int(common)
        if 1 < n <= 10:
            traveler_count = n
    if traveler_count == 1:
        m = re.search(r'(\d+)\s*个?\s*人', text[:500])
        if m:
            n = int(m.group(1))
            if 1 < n <= 10:
                traveler_count = n

    return title, start_date, duration, traveler_count


def _split_by_day(text):
    """Split text at \nNN\nweekday markers.

    PDF table layout: each day row 1 (attraction #1) appears BEFORE the
    \nNN\n marker; rows 2+ appear after it.
    We grab only the pre-marker row-1 line AND trim the next day's row-1
    line from the end of each body to prevent cross-contamination.
    """
    cut_pos = len(text)
    # 仅在"费用表/预算"出现处截断概览；`| P\d+` 是 PDF 分页符，概览本身可能跨多页，
    # 用它做全局 cut 会把 P1 之后的 day markers 全吞掉（例如 11 天行程概览跨两页）。
    for pat in [r'\n第1天[天]?[（(]总价', r'\n预\s*算\s*明\s*细', r'\n费\s*用\s*汇\s*总']:
        m = re.search(pat, text)
        if m and m.start() < cut_pos:
            cut_pos = m.start()
    text = text[:cut_pos]

    # Day marker can appear as EITHER:
    #   Format A: "\n01\n星期三 ..."  (NN and 星期 on separate lines — Korea 8-day PDF)
    #   Format B: "\n02 星期四 ..."    (NN and 星期 on same line — Korea 202405 PDF)
    # pdfminer emits whichever the PDF's table cell layout produced; both formats
    # can appear in the SAME document. Accept any whitespace (incl. \n) between.
    day_re = re.compile(r'\n(\d{2})\s+星期[一二三四五六日天]')
    matches = list(day_re.finditer(text))
    if not matches:
        return []

    _ACT_START = r'[\u4e00-\u9fff\u3040-\u30ffA-Za-z]'
    premarker_re = re.compile(
        r'(?:[\u4e00-\u9fff]{2,4}\s+.*?1\.\s+|(?:^|\s)1\.\s+(?:\d+\.\s+)*)' + _ACT_START
    )

    days = []
    for i, m in enumerate(matches):
        day_num = int(m.group(1))
        marker_start = m.start()
        chunk_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        preceding = text[:marker_start]
        pre_lines = [ln for ln in preceding.split('\n') if ln.strip()]
        pre_attraction_line = ''
        # 优先找 `1. xxx` 形式的景点列首行；若本日无观光（e.g. 马尔代夫纯度假日），
        # 回退到最近 4 行内含中文酒店名的行（概览表「住宿」列首行），以便本日 chunk
        # 能拿到酒店名（如「马尔代夫 竞技场海滩酒店,Arena」）。
        hotel_line_re = re.compile(r'[\u4e00-\u9fff]{2,12}(?:酒店|宾馆|度假村|客栈|旅馆|民宿)')
        for ln in reversed(pre_lines[-4:]):
            if re.search(r'(?:^|\s)1\.\s+(?:\d+\.\s+)*' + _ACT_START, ln):
                pre_attraction_line = ln
                break
        if not pre_attraction_line:
            for ln in reversed(pre_lines[-4:]):
                if hotel_line_re.search(ln):
                    pre_attraction_line = ln
                    break

        # Build body and trim its ending pre-marker line (= next day's row 1)
        body = text[marker_start:chunk_end]
        # PDF 分页符 `| P\d+`：概览内若跨页（如 11 天行程概览横跨 P1/P2）或最后一天
        # 延伸到详情页，每个 chunk body 内的首个 page marker 就是 overview→overview
        # 或 overview→detail 的分界。在此截断，避免下一页/详情页内容污染本日的
        # activities / accommodation 抽取。
        page_mark_m = re.search(r'\n\s*\|\s*P\d+', body)
        if page_mark_m:
            body = body[:page_mark_m.start()]
        body_lines = body.split('\n')
        trim_idx = None
        for j in range(len(body_lines) - 1, -1, -1):
            if premarker_re.search(body_lines[j].strip()):
                trim_idx = j
                break
        if trim_idx is not None:
            body = '\n'.join(body_lines[:trim_idx])

        chunk = (pre_attraction_line + '\n' + body) if pre_attraction_line else body
        days.append((day_num, chunk))

    return days


def _extract_city_from_chunk(chunk):
    """Determine destination city from a day chunk.

    Priority:
    1. Route destination (A→B → use B) — for travel days, you arrive at B
    2. Year-month + CJK city pattern (destination column in overview table)
    3. English city name after 星期X (often the departure/current city)
    4. First known destination city in chunk
    5-6. Fallbacks without DEST_CITIES requirement
    """
    # 1. Route destination: on travel days the destination is the main city
    route_m = re.search(r'[\u4e00-\u9fff]{2,8}\s*→\s*([\u4e00-\u9fff]{2,8})', chunk)
    if route_m:
        dst = route_m.group(1)
        if dst in DEST_CITIES:
            return dst

    # 2. year-month + city column pattern (shows destination, not departure)
    ym_m = re.search(r'20\d{2}年\d{1,2}月\s+([\u4e00-\u9fff]{2,8})', chunk)
    if ym_m:
        ym_city = ym_m.group(1)
        if ym_city in DEST_CITIES:
            return ym_city
        for city in DEST_CITIES:
            if city in ym_city:
                return city

    # 3. English city after weekday (departure/current city — lower priority than step 2)
    m = re.search(r'星期[一二三四五六日天]\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', chunk)
    if m:
        en = m.group(1)
        for key, zh in _EN_TO_ZH_CITY.items():
            if en.lower().startswith(key.lower()):
                return zh

    # 4. First known destination city (substring match)
    for city in DEST_CITIES:
        if city in chunk:
            return city

    # 5. Year-month city without DEST_CITIES requirement
    if ym_m:
        return ym_m.group(1)

    # 6. Route destination without DEST_CITIES requirement
    if route_m:
        return route_m.group(1)

    return None


def _extract_activities(chunk):
    """Extract numbered attraction names: N. 景点名，...

    Supports CJK, hiragana/katakana, and English-prefixed names (e.g. 'Hep Five摩天轮',
    '圣淘沙4D探险乐园'). 景点名内部允许数字/英文字母，以覆盖「4D」「3.0」这类混合名。
    """
    _CJK_KANA = r'\u4e00-\u9fff\u3040-\u30ff'
    activities = []
    for line in chunk.split('\n'):
        for m in re.finditer(
            r'\d+\.\s+([A-Za-z ]*[' + _CJK_KANA + r'][' + _CJK_KANA + r'·\-A-Za-z0-9]*(?:\([^)]+\))?)',
            line,
        ):
            name = m.group(1).strip().rstrip('，,、 ')
            if len(name) < 2 or name in activities:
                continue
            # 当名字含「酒店/Hotel」且此匹配之前是连续的「N. M. …」空序号序列时，
            # 说明这是穷游概览表里「景点」单元格为空、住宿列文本被串行拼进来的
            # 假景点（如 Malaysia PDF 的「1. 2. 3. 兰卡威雅乐轩酒店」）。过滤掉。
            # 反之，若匹配前缀无连续空序号，视为真实景点（如 Singapore PDF 的
            # 「2. 莱佛士酒店 ， Raffles Hotel」是用户真的去参观的历史建筑）。
            if _HOTEL_RE.search(name):
                pre_text = line[:m.start()]
                if re.search(r'(?:\d+\.\s+)+$', pre_text):
                    continue
            if name in DEST_CITIES:
                continue
            activities.append(name)
    return activities[:15]


def _dedup_pairs(s):
    """Collapse adjacent identical character pairs produced by PDF char doubling."""
    result = []
    i = 0
    while i < len(s):
        result.append(s[i])
        if i + 1 < len(s) and s[i] == s[i + 1]:
            i += 2
        else:
            i += 1
    return ''.join(result)


def _extract_flight_schedule(text):
    """Extract flights from the full text (both normal and doubled-char formats).

    Format 1 (normal): → src//dst ... 班次 ... HH:MM CODE
    Format 2 (doubled): →→ src//dst ... 班次 ... doubled_time doubled_code
    """
    results = []
    seen = set()

    pattern = re.compile(
        r'([\u4e00-\u9fff]{2,6})\s*/+\s*([\u4e00-\u9fff]{2,6})'
        r'\n[^\n]*班次[^\n]*'
        r'\n\s*(\S+)\s+(\S+)',
    )
    for m in pattern.finditer(text):
        src, dst = m.group(1), m.group(2)
        key = (src, dst)
        if key in seen:
            continue
        raw_time = _dedup_pairs(m.group(3).replace(' ', ''))
        raw_code = _dedup_pairs(m.group(4).replace(' ', ''))
        time_m = re.match(r'(\d{1,2}):(\d{2})', raw_time)
        code_m = re.match(r'[A-Z]{1,2}\d{3,5}$', raw_code)
        if time_m and code_m:
            seen.add(key)
            dep_time = f'{int(time_m.group(1)):02d}:{time_m.group(2)}'
            results.append({
                'code': code_m.group(), 'src': src, 'dst': dst,
                '_dep_time': dep_time,
            })
    return results


def _extract_transport(chunk):
    """Extract city→city routes from day chunk. Flight codes paired globally."""
    # Cut off page-marker tail (flight schedule / overview pages end up here for the last day)
    page_cut = re.search(r'\|\s*P\d+\s*\|', chunk)
    if page_cut:
        chunk = chunk[:page_cut.start()]

    _en_city_set = {v.lower() for v in _EN_TO_ZH_CITY.keys()}
    routes = []
    for m in re.finditer(
        r'([\u4e00-\u9fff]{1,4}|[A-Za-z]{2,10})\s*→\s*([\u4e00-\u9fff]{1,4}|[A-Za-z]{2,10})',
        chunk,
    ):
        src, dst = m.group(1).strip(), m.group(2).strip()
        if re.search(r'\d', src + dst):
            continue
        if re.search(r'酒店|宾馆|度假|旅馆|客栈', src + dst):
            continue
        if re.match(r'^[A-Za-z]+$', src) and src.lower() not in _en_city_set:
            continue
        if re.match(r'^[A-Za-z]+$', dst) and dst.lower() not in _en_city_set:
            continue
        src_zh = _EN_TO_ZH_CITY.get(src, src)
        dst_zh = _EN_TO_ZH_CITY.get(dst, dst)
        if src_zh == dst_zh:
            continue
        route = f'{src}→{dst}'
        if route not in routes and len(src) >= 2 and len(dst) >= 2:
            routes.append(route)
    return routes[:8]


def _extract_accommodation(chunk):
    """Extract first clean hotel name from chunk, preferring Chinese names."""
    # Prefer Chinese hotel names
    for m in re.finditer(
        r'([\u4e00-\u9fff]{2,12}(?:酒店|宾馆|度假村|客栈|旅馆|民宿))',
        chunk,
    ):
        name = m.group(1).strip()
        if len(name) <= 20:
            return name
    # Fallback to English hotel names
    for m in re.finditer(
        r'([A-Za-z\s]{4,30}(?:Hotel|Resort|Inn|Hostel|Lodge))',
        chunk, re.IGNORECASE,
    ):
        name = m.group(1).strip()
        if len(name) <= 30:
            return name
    return None


def _build_activity_category_map(text):
    """Extract {activity_name: expense_category} from PDF detail page type labels.

    穷游 PDF detail pages follow this structure after normalize:
        景点名称
        类型标签  (e.g. "其他美食", "博物馆", "韩国料理")
        地址 ...

    We scan line-pairs and map known type keywords to expense categories.
    Only short type-label lines (≤20 chars) are considered to avoid false positives.
    """
    _TYPE_RULES = [
        (r'美食|料理|小吃|餐厅|咖啡|拉面|寿司|烧肉|火锅', '餐饮'),
        (r'博物馆|主题公园|游乐|缆车|观景|遗址|神社|寺庙|城堡|宫殿', '门票'),
        (r'购物|免税|百货|商圈|化妆|时尚', '购物'),
    ]
    _SKIP_PREFIX = re.compile(
        r'^(地址|时间|交通|票价|介绍|提示|Tips|P\d|\d|·| |\|)'
    )
    result = {}
    lines = [ln.strip() for ln in text.split('\n')]
    for i, line in enumerate(lines[:-1]):
        # Candidate name line: 2-20 chars, contains CJK, not a field prefix
        if not (2 <= len(line) <= 20):
            continue
        if not re.search(r'[\u4e00-\u9fff]', line):
            continue
        if _SKIP_PREFIX.match(line):
            continue
        # Find next non-empty line as type candidate
        for j in range(i + 1, min(i + 3, len(lines))):
            nxt = lines[j]
            if not nxt:
                continue
            if len(nxt) > 20 or _SKIP_PREFIX.match(nxt):
                break
            for pat, cat in _TYPE_RULES:
                if re.search(pat, nxt, re.IGNORECASE):
                    name_m = re.match(r'([\u4e00-\u9fff]{2,15})', line)
                    if name_m:
                        result[name_m.group(1)] = cat
            break
    return result


def _parse_expenses(text, start_date=None):
    """Parse expense table rows: 'description CURR unit qty CURR total'.

    Supports CNY and foreign currencies (USD, EUR, JPY, KRW, etc.).
    Foreign currency amounts are converted to CNY using the per-day CNY total
    embedded in the expense table header (e.g. "第4天(总价:¥5179.79)").
    Conversion formula: rate = (day_total_cny - Σ cny_items) / Σ foreign_items
    Original currency and amount are appended to the description for traceability.
    Uses '第N天' headers to assign dates. Does NOT deduplicate.
    """
    CATEGORY_RULES = [
        (r'交通|机票|航班|火车|高铁|大巴|船|包车|飞机|打车|出租车|的士|网约车|Grab', '交通'),
        (r'酒店|宾馆|民宿|住宿|Hotel|hostel|客栈|旅馆|度假村', '住宿'),
        (r'午餐|晚餐|早餐|餐饮|餐厅|饭', '餐饮'),
        (r'门票|景点|入场|一日游|半日游|游览', '门票'),
        (r'购物|纪念品', '购物'),
    ]
    # Build activity-type lookup from PDF detail pages (e.g. 牛家→其他美食→餐饮)
    activity_cat = _build_activity_category_map(text)
    _CURR = r'(?:CNY|USD|EUR|JPY|KRW|HKD|SGD|THB|MYR|TWD)'

    # Step 1: Extract per-day CNY totals from expense table headers.
    # Format after normalize: 第4天(总价:¥5179.79)  [NFKC converts ¥ and brackets]
    day_totals: dict = {}
    for m in re.finditer(r'第(\d+)天[^¥\n]*¥([\d,.]+)', text):
        day_totals[int(m.group(1))] = float(m.group(2).replace(',', ''))

    day_headers = [(dh.start(), int(dh.group(1))) for dh in re.finditer(r'第(\d+)天', text)]

    # Step 2: First pass — parse all raw expense rows, tracking per-day sums.
    # desc 上限放宽到 50 char：PDF 表格里长景点名（含中英双语）如「新加坡夜间野生
    # 动物园,Night Safari of Singa」≈32 字，旧的 30 上限会从头部反复截断直到规则
    # 能对上货币位置，产出「坡夜间野生动物园,Night Safari of Singa」这种开头缺失。
    raw: list = []
    for m in re.finditer(
        r'(.{2,50}?)\s+(' + _CURR + r')\s*([\d,.]+)\s+(\d+)\s+' + _CURR + r'\s*([\d,.]+)',
        text,
    ):
        desc = m.group(1).strip()
        currency = m.group(2)
        try:
            qty = int(m.group(4))
            total = float(m.group(5).replace(',', ''))
        except ValueError:
            continue
        # 过滤总价为 0 的行：0 元条目属于穷游模板里未填价格的占位景点
        # （如「莱佛士酒店 SGD 0.00」作为景点访问但无门票支出），不应出现在花费明细。
        if total == 0:
            continue
        category = '其他'
        for pat, cat in CATEGORY_RULES:
            if re.search(pat, desc, re.IGNORECASE):
                category = cat
                break
        # Fallback: look up category from PDF activity-type labels (e.g. 牛家→餐饮)
        if category == '其他':
            for name, cat in activity_cat.items():
                if name in desc:
                    category = cat
                    break
        suffix = f' x{qty}' if qty > 1 else ''
        day_n = None
        date_str = None
        for pos, dn in reversed(day_headers):
            if pos < m.start():
                day_n = dn
                if start_date:
                    date_str = (start_date + timedelta(days=dn - 1)).strftime('%Y-%m-%d')
                break
        raw.append({
            '_day_n': day_n,
            'date': date_str,
            'category': category,
            'amount': total,
            'currency': currency,
            'description': f'{desc}{suffix}',
        })

    # Step 3: Derive per-day exchange rates for days that have a single foreign
    # currency and a known CNY day total.
    # rate[day_n][currency] = implied CNY/foreign rate
    from collections import defaultdict
    day_cny: dict = defaultdict(float)
    day_foreign: dict = defaultdict(lambda: defaultdict(float))
    for exp in raw:
        dn = exp['_day_n']
        if dn is None:
            continue
        if exp['currency'] == 'CNY':
            day_cny[dn] += exp['amount']
        else:
            day_foreign[dn][exp['currency']] += exp['amount']

    fx_rate: dict = {}  # (day_n, currency) -> CNY rate
    for dn, foreign_by_curr in day_foreign.items():
        day_total = day_totals.get(dn)
        if day_total is None:
            continue
        remaining = day_total - day_cny.get(dn, 0.0)
        if remaining <= 0:
            continue
        # Only derive rate when a single foreign currency exists in this day;
        # mixed foreign currencies (e.g. USD + EUR same day) cannot be separated.
        if len(foreign_by_curr) == 1:
            curr, total_foreign = next(iter(foreign_by_curr.items()))
            if total_foreign > 0:
                fx_rate[(dn, curr)] = remaining / total_foreign

    # Step 4: Build final expenses, converting foreign currencies where rate known.
    expenses = []
    for exp in raw:
        out = {k: v for k, v in exp.items() if k != '_day_n'}
        if out['currency'] != 'CNY':
            rate = fx_rate.get((exp['_day_n'], out['currency']))
            if rate is not None:
                orig_amt = out['amount']
                orig_curr = out['currency']
                out['amount'] = round(orig_amt * rate, 2)
                out['currency'] = 'CNY'
                # Append original for traceability, e.g. "牛家 (USD 197.12)"
                base_desc = re.sub(r'\s+x\d+$', '', out['description'])
                suffix_part = out['description'][len(base_desc):]
                out['description'] = f'{base_desc} ({orig_curr} {orig_amt:.2f}){suffix_part}'
        expenses.append(out)
    return expenses


_HOTEL_RE = re.compile(r'酒店|宾馆|度假村|客栈|旅馆|民宿|Hotel|Resort|Inn|Hostel', re.IGNORECASE)
_NOISE_RE = re.compile(
    r'^(下载APP|线路总览|共有.*穷游|创建了|相关行程|复制行程|创建行程|穷游\s*行程助手'
    r'|点击加载|Day \d|[\d,\s]+个行程|\d{4}年\d{2}月\d{2}日出发)',
)
_DISTANCE_RE = re.compile(r'距离[\d.]+(?:公里|千米|米)')
_ZH_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7,
            '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}


def parse_qyer_web(text: str) -> dict:
    """Parse text scraped from qyer.com mobile trip plan page."""
    lines = text.split('\n')

    # ── header ──
    title = None
    start_date = end_date = None
    for ln in lines[:10]:
        ln = ln.strip()
        if not ln:
            continue
        m = re.match(r'(\d{4})年(\d{2})月(\d{2})日\s*~\s*(\d{4})年(\d{2})月(\d{2})日', ln)
        if m:
            start_date = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            end_date = datetime(int(m.group(4)), int(m.group(5)), int(m.group(6)))
            continue
        if not title and len(ln) > 3 and '行程' in ln and not ln.startswith('下载'):
            title = ln

    duration = (end_date - start_date).days + 1 if start_date and end_date else None

    # ── split by day ──
    day_header_re = re.compile(r'^第([一二三四五六七八九十]+)天\s+(\d{1,2})月(\d{1,2})日\s+星期')
    day_chunks = []
    current_day = None
    current_lines = []
    footer_started = False

    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if _NOISE_RE.match(stripped) or footer_started:
            if re.match(r'^(共有|相关行程|复制行程|穷游)', stripped):
                footer_started = True
            continue
        m = day_header_re.match(stripped)
        if m:
            if current_day is not None:
                day_chunks.append((current_day, current_lines))
            zh_num = m.group(1)
            current_day = _ZH_NUM.get(zh_num, len(day_chunks) + 1)
            current_lines = []
            continue
        if current_day is not None:
            current_lines.append(stripped)

    if current_day is not None:
        day_chunks.append((current_day, current_lines))

    # ── process each day ──
    city_legs: 'OrderedDict[str, dict]' = OrderedDict()

    for seq_idx, (day_num, chunk_lines) in enumerate(day_chunks):
        day_date = (start_date + timedelta(days=seq_idx)) if start_date else None

        # Route line: "北京 > 首尔"
        route_line = None
        cities_in_route = []
        if chunk_lines and re.search(r'>\s*[\u4e00-\u9fff]', chunk_lines[0]):
            route_line = chunk_lines[0]
            cities_in_route = [c.strip() for c in route_line.split('>') if c.strip()]
            chunk_lines = chunk_lines[1:]

        # Determine destination city
        city = None
        dest_candidates = [c for c in cities_in_route if c in DEST_CITIES]
        if dest_candidates:
            city = dest_candidates[-1]
        elif cities_in_route:
            for c in reversed(cities_in_route):
                if c in DEST_CITIES:
                    city = c
                    break
        if not city:
            for c in DEST_CITIES:
                if any(c in ln for ln in chunk_lines[:3]):
                    city = c
                    break
        if not city:
            city = '[待确认]'

        # Extract flights from pattern: "HH:MM / City / Airport / CODE / HH:MM / City / Airport"
        transport = []
        flight_re = re.compile(r'^[A-Z0-9]{1,2}\d{3,5}$')
        time_re = re.compile(r'^\d{1,2}:\d{2}$')
        flight_lines_idx = set()
        flight_codes = set()
        i = 0
        while i < len(chunk_lines):
            if time_re.match(chunk_lines[i]):
                for j in range(i + 1, min(i + 4, len(chunk_lines))):
                    if flight_re.match(chunk_lines[j]):
                        code = chunk_lines[j]
                        flight_codes.add(code)
                        block_end = min(j + 4, len(chunk_lines))
                        for k in range(i, block_end):
                            flight_lines_idx.add(k)
                        # Derive src/dst from city lines adjacent to times
                        src_city = chunk_lines[i + 1] if i + 1 < len(chunk_lines) else None
                        dst_city = None
                        for k in range(j + 1, block_end):
                            if time_re.match(chunk_lines[k]):
                                if k + 1 < block_end:
                                    dst_city = chunk_lines[k + 1]
                                break
                        if src_city and dst_city:
                            transport.append(f'{code}:{src_city}→{dst_city}')
                        else:
                            transport.append(code)
                        break
            i += 1

        if not transport and len(cities_in_route) >= 2:
            transport.append(f'{cities_in_route[0]}→{cities_in_route[-1]}')

        # Extract activities and accommodation from remaining lines
        activities = []
        accommodation = None
        for idx, ln in enumerate(chunk_lines):
            if idx in flight_lines_idx:
                continue
            if _DISTANCE_RE.match(ln):
                continue
            if time_re.match(ln):
                continue
            if flight_re.match(ln):
                continue
            if re.search(r'机场|铁路$', ln):
                continue
            # Single city name that's just a transit label
            if ln in ('北京', '首尔', '济州岛', '济州市', '西归浦'):
                continue

            if _HOTEL_RE.search(ln):
                m = re.search(r'([\u4e00-\u9fff]{2,12}(?:酒店|宾馆|度假村|客栈|旅馆|民宿))', ln)
                if m:
                    accommodation = m.group(1)
                elif not accommodation:
                    accommodation = ln.strip()
                continue

            name = ln.strip()
            if len(name) < 2:
                continue
            # Skip pure English/Latin lines
            if re.match(r'^[A-Za-z\s\',.\-()]+$', name):
                continue
            m = re.match(
                r"([A-Za-z0-9'\u2018\u2019\u0060·.\- ]*[\u4e00-\u9fff\uac00-\ud7af]"
                r"[\u4e00-\u9fff\uac00-\ud7af·\-'\u2018\u2019（）()]*)",
                name,
            )
            if m:
                clean = m.group(1).rstrip('，,、 ')
                if len(clean) >= 2 and clean not in activities:
                    activities.append(clean)
            elif name not in activities:
                activities.append(name)

        # Build day entry
        if city not in city_legs:
            city_legs[city] = {'days': [], 'start': None, 'end': None}

        day_entry = {
            'day_number': day_num,
            'date': day_date.strftime('%Y-%m-%d') if day_date else None,
            'description': ', '.join(activities[:4]) if activities else f'Day {day_num}',
            'highlights': None,
            'activities': activities,
            'transport': transport,
            'accommodation': accommodation,
        }
        city_legs[city]['days'].append(day_entry)
        if day_date:
            if not city_legs[city]['start'] or day_date < city_legs[city]['start']:
                city_legs[city]['start'] = day_date
            if not city_legs[city]['end'] or day_date > city_legs[city]['end']:
                city_legs[city]['end'] = day_date

    legs = []
    for i, (city, info) in enumerate(city_legs.items()):
        if not info['days']:
            continue
        legs.append({
            'order_index': i,
            'city': city,
            'country': COUNTRY_MAP.get(city, '[待确认]'),
            'start_date': info['start'].strftime('%Y-%m-%d') if info['start'] else None,
            'end_date': info['end'].strftime('%Y-%m-%d') if info['end'] else None,
            'days': info['days'],
        })

    if not title:
        year = start_date.year if start_date else None
        country = legs[0]['country'] if legs else None
        if year and country and country != '[待确认]':
            title = f'soul的{year}年{country}行程'
        elif year:
            title = f'soul的{year}年旅行行程'
        else:
            title = '旅行行程'

    return {
        'type': 'trip',
        'trip': {
            'title': title,
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else None,
            'traveler_count': 1,
            'description': title,
            'status': 'completed',
        },
        'legs': legs,
        'expenses': [],
    }


def _is_short_command(text: str) -> bool:
    if len(text) > 200:
        return False
    if re.search(r'\n\d{2}\n\s*星期[一二三四五六日天]', text):
        return False
    if re.search(r'第\d+天.*总价', text):
        return False
    if text.count('CNY') >= 3:
        return False
    return True


def _try_remove_expense(text: str):
    """Detect '移除/删除费用：X' pattern before NLU classification."""
    m = re.search(r'(?:移除|删除|去掉|取消)\s*(?:费用|花费|支出)[：:\s]*(.+)', text)
    if m:
        desc = m.group(1).strip().rstrip('。，,')
        return {
            'type': 'remove_expense',
            'description': desc,
            'trip': None, 'legs': [], 'expenses': [],
        }
    return None


def _nlu_parse(text: str) -> dict:
    from services.nlu.classifier import classify
    from services.nlu.extractors import extract

    parts = re.split(r'[；;]', text)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) <= 1:
        removal = _try_remove_expense(text)
        if removal:
            return removal
        intent = classify(text)
        return extract(intent, text)

    actions = []
    for part in parts:
        removal = _try_remove_expense(part)
        if removal:
            actions.append(removal)
            continue
        intent = classify(part)
        actions.append(extract(intent, part))
    return {'type': 'compound', 'actions': actions}


def parse_text(text: str) -> dict:
    text = _normalize(text)

    if _is_short_command(text):
        return _nlu_parse(text)

    title, start_date, duration, traveler_count = _extract_trip_header(text)
    _title_is_default = not title

    end_date = None
    if start_date and duration:
        end_date = start_date + timedelta(days=duration - 1)

    expenses = _parse_expenses(text, start_date)
    day_chunks = _split_by_day(text)

    # Extract flight schedule from full text once; build route→code lookup
    flight_schedule = _extract_flight_schedule(text)
    route_to_code = {f'{f["src"]}→{f["dst"]}': f['code'] for f in flight_schedule}
    time_to_flight = {}
    for f in flight_schedule:
        dep = f.get('_dep_time')
        if dep:
            time_to_flight[dep] = f

    # Map overview flight times to day-of-month using marker positions
    # 同 `_split_by_day` 保持一致：不用 `| P\d+` 截断，概览可跨多页。
    cut_pos = len(text)
    for pat in [r'\n第1天[天]?[（(]总价', r'\n预\s*算\s*明\s*细', r'\n费\s*用\s*汇\s*总']:
        m_cut = re.search(pat, text)
        if m_cut and m_cut.start() < cut_pos:
            cut_pos = m_cut.start()
    overview_text = text[:cut_pos]
    day_markers = list(re.finditer(r'\n(\d{2})\s+星期[一二三四五六日天]', overview_text))
    dom_flight_times: dict = {}
    for tm in re.finditer(r'(\d{1,2}:\d{2})\s*-\s*\d{1,2}:\d{2}', overview_text):
        assigned_dom = None
        for dm in day_markers:
            if dm.start() > tm.start():
                assigned_dom = int(dm.group(1))
                break
        if assigned_dom is None and day_markers:
            assigned_dom = int(day_markers[-1].group(1))
        if assigned_dom is not None:
            h, m_str = tm.group(1).split(':')
            dep_key = f'{int(h):02d}:{m_str}'
            dom_flight_times.setdefault(assigned_dom, []).append(dep_key)

    city_legs: 'OrderedDict[str, dict]' = OrderedDict()

    if day_chunks:
        # Pre-compute cities; fix return-to-origin on last day
        day_cities = [_extract_city_from_chunk(c) or '[待确认]' for _, c in day_chunks]
        if len(day_chunks) >= 2:
            first_route = re.search(r'([\u4e00-\u9fff]{2,4})\s*→', day_chunks[0][1])
            last_route = re.search(r'([\u4e00-\u9fff]{2,4})\s*→\s*([\u4e00-\u9fff]{2,4})', day_chunks[-1][1])
            if first_route and last_route and last_route.group(2) == first_route.group(1):
                src = last_route.group(1)
                if src in DEST_CITIES:
                    day_cities[-1] = src

        for seq_idx, ((_dom, chunk), city) in enumerate(zip(day_chunks, day_cities)):

            day_num = seq_idx + 1
            day_date = (start_date + timedelta(days=seq_idx)) if start_date else None

            activities = _extract_activities(chunk)
            raw_routes = _extract_transport(chunk)
            transport = []
            for route in raw_routes:
                code = route_to_code.get(route)
                transport.append(f'{code}:{route}' if code else route)

            if not transport and time_to_flight:
                for dep_key in dom_flight_times.get(_dom, []):
                    if dep_key in time_to_flight:
                        f = time_to_flight[dep_key]
                        entry = f"{f['code']}:{f['src']}→{f['dst']}"
                        if entry not in transport:
                            transport.append(entry)

            if transport:
                rt = re.search(r'([\u4e00-\u9fff]{2,6})→([\u4e00-\u9fff]{2,6})', transport[0])
                if rt:
                    if seq_idx == len(day_chunks) - 1:
                        if rt.group(1) in DEST_CITIES:
                            city = rt.group(1)
                    else:
                        if rt.group(2) in DEST_CITIES:
                            city = rt.group(2)

            if city not in city_legs:
                city_legs[city] = {'days': [], 'start': None, 'end': None}

            accommodation = _extract_accommodation(chunk)

            day_entry = {
                'day_number': day_num,
                'date': day_date.strftime('%Y-%m-%d') if day_date else None,
                'description': ', '.join(activities[:4]) if activities else f'Day {day_num}',
                'highlights': None,
                'activities': activities,
                'transport': transport,
                'accommodation': accommodation,
            }

            city_legs[city]['days'].append(day_entry)
            if day_date:
                if not city_legs[city]['start'] or day_date < city_legs[city]['start']:
                    city_legs[city]['start'] = day_date
                if not city_legs[city]['end'] or day_date > city_legs[city]['end']:
                    city_legs[city]['end'] = day_date

    legs = []
    for i, (city, info) in enumerate(city_legs.items()):
        if not info['days']:
            continue
        legs.append({
            'order_index': i,
            'city': city,
            'country': COUNTRY_MAP.get(city, '[待确认]'),
            'start_date': info['start'].strftime('%Y-%m-%d') if info['start'] else None,
            'end_date': info['end'].strftime('%Y-%m-%d') if info['end'] else None,
            'days': info['days'],
        })

    # Assign expense dates by matching to days: hotels → checkin day, transport → matching route day
    all_days = [day for info in city_legs.values() for day in info['days']]
    for exp in expenses:
        if exp['date']:
            continue
        desc = exp['description'] or ''
        matched_date = None
        if exp['category'] == '住宿':
            # Match hotel name against accommodation field of each day
            for day in all_days:
                hotel = day.get('accommodation') or ''
                if hotel and any(tok in desc or tok in hotel for tok in [hotel[:4], desc[:4]] if len(tok) >= 2):
                    matched_date = day['date']
                    break
        elif exp['category'] == '交通':
            # Match route keywords against transport list of each day
            for day in all_days:
                for t in day.get('transport', []):
                    # t looks like "CODE:A→B" or "A→B"; check if city names appear in desc
                    cities = re.findall(r'[\u4e00-\u9fff]{2,4}', t)
                    if cities and any(c in desc for c in cities):
                        matched_date = day['date']
                        break
                if matched_date:
                    break
        if not matched_date and start_date:
            matched_date = start_date.strftime('%Y-%m-%d')
        exp['date'] = matched_date

    # Backfill accommodation from expenses (expense table is more reliable than
    # regex on the overview page where hotel names use mixed CJK/English formats)
    _ACTIVITY_DESC_RE = re.compile(r'一日游|半日游|游览|跟团|门票|入场')
    _PRICE_SUFFIX_RE = re.compile(r'\s*\([A-Z]{3}\s+[\d,.]+\)')
    date_to_accom = {}
    for exp in expenses:
        if exp['date'] and exp['category'] == '住宿':
            clean = re.sub(r'\s*x\d+$', '', exp['description'])
            clean = _PRICE_SUFFIX_RE.sub('', clean)
            date_to_accom.setdefault(exp['date'], clean)
    for exp in expenses:
        if (exp['date'] and exp['category'] == '其他'
                and exp['date'] not in date_to_accom
                and not _ACTIVITY_DESC_RE.search(exp['description'])):
            clean = re.sub(r'\s*x\d+$', '', exp['description'])
            clean = _PRICE_SUFFIX_RE.sub('', clean)
            date_to_accom.setdefault(exp['date'], clean)
            exp['category'] = '住宿'
    # chunk 抽到的中文酒店名（含「酒店/宾馆/度假村/客栈/旅馆/民宿」后缀且含汉字）
    # 视为高质量——例如概览表中的「竞技场海滩酒店」；不要被 expense 表里同一家酒店
    # 的简写名（如「马尔代夫竞技海滩酒店」）覆盖。仅当 chunk 抽取缺失或明显错误
    # （纯英文拼接、如「National Museum Hotel」）时才采用 expense 回填值。
    _GOOD_ACCOM_RE = re.compile(r'[\u4e00-\u9fff]{2,}.*?(?:酒店|宾馆|度假村|客栈|旅馆|民宿)')
    for day in all_days:
        if day['date'] in date_to_accom:
            cur = day.get('accommodation') or ''
            if not _GOOD_ACCOM_RE.search(cur):
                day['accommodation'] = date_to_accom[day['date']]

    if _title_is_default:
        year = start_date.year if start_date else None
        country = legs[0]['country'] if legs else None
        if year and country and country != '[待确认]':
            title = f'soul的{year}年{country}行程'
        elif year:
            title = f'soul的{year}年旅行行程'
        else:
            title = '旅行行程'

    return {
        'type': 'trip',
        'trip': {
            'title': title,
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else None,
            'traveler_count': traveler_count,
            'description': title,
            'status': 'completed',
        },
        'legs': legs,
        'expenses': expenses,
    }
