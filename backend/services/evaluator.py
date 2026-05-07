"""
行程评价引擎 — 本地量化指标计算 + 模板文字生成
"""
import json
import os
import math
import re

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_benchmarks_cache = None
_country_defaults_cache = None


def _load_benchmarks():
    global _benchmarks_cache, _country_defaults_cache
    if _benchmarks_cache is None:
        path = os.path.join(DATA_DIR, "city_benchmarks.json")
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _country_defaults_cache = raw.pop("_country_defaults", {})
        _benchmarks_cache = raw
    return _benchmarks_cache


def _get_country_default(country):
    """根据国家名获取回退基准。"""
    if _country_defaults_cache is None:
        _load_benchmarks()
    return _country_defaults_cache.get(country)


def _clamp(v, lo=0, hi=100):
    return max(lo, min(hi, int(round(v))))


# ---------------------------------------------------------------------------
# 0. 消费层级 & 季节基准调整
# ---------------------------------------------------------------------------

_REFERENCE_PER_PERSON_BUDGET = 35000  # 人均年旅行预算基准 (CNY)

# 目的地消费升级锚点 — 两个维度各自独立，避免上调 daily 影响 hotel 参考
_DAILY_COST_ANCHOR = 800   # 中档日均消费水平（住宿+餐饮+本地交通+门票）
_HOTEL_PRICE_ANCHOR = 600  # 中档 4 星均价水平


def _hotel_dest_coefficient(base_hotel_price):
    """住宿维度的「穷地富游/富地穷游」系数 — 较陡，用 hotel anchor。

    用 hotel base 而非 daily base 作为穷富判断 — 否则上调 daily 会让
    城市从「穷地」变「准 anchor 地」，hotel 系数下降，破坏 hotel 修复。

    住宿是离散品（5星 vs 民宿差异巨大），穷地的旅客容易显著升级，
    富地的旅客则更倾向控制住宿等级。所以住宿系数对 anchor 偏离的响应更激进。
    """
    if base_hotel_price <= 0:
        return 1.0
    ratio = base_hotel_price / _HOTEL_PRICE_ANCHOR
    if ratio >= 1.0:
        return max(0.75, 1.0 - (ratio - 1.0) * 0.15)
    return min(1.6, 1.0 + (1.0 - ratio) * 0.8)


def _daily_dest_coefficient(base_daily_cost):
    """日均消费维度的「穷地富游/富地穷游」系数 — 较缓，用 daily anchor。

    日均消费包含本地交通、门票、机场税、签证费等不受目的地穷富影响的项目，
    所以系数应明显比住宿温和，避免被一个粗系数同时放大/压缩所有支出类别。
    """
    if base_daily_cost <= 0:
        return 1.0
    ratio = base_daily_cost / _DAILY_COST_ANCHOR
    if ratio >= 1.0:
        return max(0.92, 1.0 - (ratio - 1.0) * 0.05)
    return min(1.25, 1.0 + (1.0 - ratio) * 0.3)


def _compute_tier_multiplier(profile, traveler_count):
    """根据用户年度旅行预算和出行人数计算消费层级乘数。
    基准: 人均年旅行预算 35,000 → 乘数 1.0 (舒适型)。
    """
    if not profile or not profile.get("annual_travel_budget"):
        return 1.0
    budget = profile["annual_travel_budget"]
    per_person = budget / max(traveler_count, 1)
    ratio = per_person / _REFERENCE_PER_PERSON_BUDGET
    return max(0.5, min(2.5, ratio ** 0.55))


def _extract_household_size(profile):
    """从用户档案 family_description 中提取家庭常规出行人数。

    供消费层级计算使用，避免因单次出行人数变化而误判层级。
    - "夫妻两人" / "夫妻" / "情侣" → 2
    - "两人"、"三人"、"四人" 等数字词 → 对应数字
    - 无法识别时默认 1
    """
    if not profile:
        return 1
    desc = profile.get("family_description") or ""
    _CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}
    m = re.search(r'([一两二三四五六])[人口]', desc)
    if m:
        return _CN_NUM.get(m.group(1), 1)
    if any(kw in desc for kw in ("夫妻", "夫婦", "情侣", "情侶", "伴侣")):
        return 2
    return 1


def _tier_label(multiplier):
    if multiplier < 0.7:
        return "经济型"
    if multiplier < 0.9:
        return "实惠型"
    if multiplier < 1.15:
        return "舒适型"
    if multiplier < 1.5:
        return "品质型"
    if multiplier < 2.0:
        return "高端型"
    return "奢华型"


def _compute_season_multiplier(city_bm, months):
    """根据城市季节数据和实际出行月份返回 (价格乘数, 季节标签)。"""
    seasons = city_bm.get("seasons")
    if not seasons or not months:
        return 1.0, "平季"
    peak_set = set(seasons.get("peak", {}).get("months", []))
    peak_mult = seasons.get("peak", {}).get("multiplier", 1.25)
    off_set = set(seasons.get("off_peak", {}).get("months", []))
    off_mult = seasons.get("off_peak", {}).get("multiplier", 0.80)

    total = len(months)
    peak_n = sum(1 for m in months if m in peak_set)
    off_n = sum(1 for m in months if m in off_set)
    shoulder_n = total - peak_n - off_n

    weighted = (peak_n * peak_mult + off_n * off_mult + shoulder_n * 1.0) / total
    if peak_n > total / 2:
        label = "旺季"
    elif off_n > total / 2:
        label = "淡季"
    else:
        label = "平季"
    return round(weighted, 3), label


def _extract_months_from_leg(leg):
    months = []
    for day in leg.get("days", []):
        date_str = day.get("date", "")
        if date_str:
            try:
                months.append(int(date_str.split("-")[1]))
            except (IndexError, ValueError):
                pass
    return months


def _resolve_city_benchmark(raw_benchmarks, city, country=""):
    """三级查找：城市基准 → 国家回退 → None。"""
    if city in raw_benchmarks:
        return raw_benchmarks[city]
    cd = _get_country_default(country)
    if cd:
        return cd
    return None


def _build_adjusted_benchmarks(raw_benchmarks, tier_mult, legs, traveler_count=1):
    """构建经消费层级 + 季节调整后的基准数据副本。

    日均参考价（avg_daily_cost_cny）拆分为住宿和非住宿两部分，分别用
    hotel_coeff（与住宿参考逻辑一致，更激进）和 daily_coeff（温和）调整，
    使日均参考与住宿参考保持逻辑对齐。

    traveler_count: 行程出行人数，用于将 avg_hotel_price_cny（间价）
    折算为人均住宿基础成本，再合并非住宿部分得到人均日均参考价。
    """
    adjusted = {}
    occupancy = max(traveler_count, 1)
    for leg in legs:
        city = leg.get("city", "")
        if city in adjusted:
            continue
        country = leg.get("country", "")
        bm = _resolve_city_benchmark(raw_benchmarks, city, country)
        if bm is None:
            continue
        months = _extract_months_from_leg(leg)
        season_mult, season_label = _compute_season_multiplier(bm, months)
        base_hotel = bm.get("avg_hotel_price_cny", 500)
        base_daily = bm["avg_daily_cost_cny"]
        hotel_coeff = _hotel_dest_coefficient(base_hotel)
        daily_coeff = _daily_dest_coefficient(base_daily)
        hotel_combined = tier_mult * season_mult * hotel_coeff
        daily_combined = tier_mult * season_mult * daily_coeff

        # 住宿参考（间价/晚），与 _compute_accommodation_metrics 保持一致
        adj_hotel = round(base_hotel * hotel_combined)

        # 日均参考（人均/天）：住宿部分用 hotel_coeff（与住宿参考逻辑对齐），
        # 非住宿部分（餐饮/本地交通/门票）用 daily_coeff（较温和）
        hotel_per_person = base_hotel / occupancy
        non_hotel = max(base_daily - hotel_per_person, 0)
        adj_daily = round(hotel_per_person * hotel_combined + non_hotel * daily_combined)

        adj = dict(bm)
        adj["avg_daily_cost_cny"] = adj_daily
        adj["avg_hotel_price_cny"] = adj_hotel
        adj["_season_label"] = season_label
        adj["_season_multiplier"] = season_mult
        adj["_hotel_dest_coefficient"] = round(hotel_coeff, 3)
        adj["_daily_dest_coefficient"] = round(daily_coeff, 3)
        adj["_original_daily_cost"] = base_daily
        adj["_original_hotel_price"] = base_hotel
        adjusted[city] = adj

    for city, bm in raw_benchmarks.items():
        if city not in adjusted:
            adjusted[city] = bm
    return adjusted


# ---------------------------------------------------------------------------
# 1. 本地指标计算
# ---------------------------------------------------------------------------

_MAJOR_TRANSPORT_KW = re.compile(
    r'机票|航班|[Ff]light|高铁|动车|火车票|长途', re.IGNORECASE)

_INTERCITY_ROUTE_RE = re.compile(
    r'[\u4e00-\u9fa5A-Za-z]{2,}(?:[到至]|\u2192|-\s*>)[\u4e00-\u9fa5A-Za-z]{2,}')

# 全程/多日同一辆车跨多城时，用户常只写「包车」而不写「A→B」，不应一律按未记录跨城扣分。
# 仅用于交通规划 coverage 补充，不并入 _is_transit_day（避免市内包车游误判为跨城干扰节奏等维度）。
_CHARTER_RENTAL_SELF_DRIVE_IN_TRANSPORT = re.compile(r'包车|租车|自驾')

_LOCAL_TRANSPORT_PREFIX = re.compile(
    r'^(?:打车|叫车|骑车|坐车|搭车|乘车|出租|的士|地铁|公交|巴士|'
    r'摩的|三轮|渡轮|缆车|索道|滴滴|[Gg]rab|[Uu]ber)')

_LOCAL_PLACE_RE = re.compile(
    r'机场|酒店|旅馆|民宿|市区|市中心|车站|码头|港口|'
    r'景点|景区|餐厅|商场|饭店|宾馆')


# ---------------------------------------------------------------------------
# 活动难度加权：不同活动耗时与体力差异显著，纯数量难以反映真实强度
# ---------------------------------------------------------------------------

# 高强度（1.5×）：半日/全日耗时或体力要求较高的活动
_HIGH_DIFFICULTY_ACTIVITY = re.compile(
    r'山岳|山脉|[\u4e00-\u9fa5]+山$|[\u4e00-\u9fa5]+[岳峰]$|'
    r'徒步|登山|爬山|攀登|[Hh]ik(?:e|ing)|[Tt]rek|'
    r'保护区|国家公园|自然公园|森林公园|'
    r'博物馆|美术馆|科技馆|纪念馆|'
    r'皇宫|城堡|古城|古镇|'
    r'潜水|浮潜|[Ss]nork|[Dd]iving|滑雪|[Ss]ki(?:ing)?\b|'
    r'主题公园|动物园|水族馆|游乐园|迪士尼|环球影城'
)

# 低强度（0.5×）：短时/顺路/轻松参与的活动
_LOW_DIFFICULTY_ACTIVITY = re.compile(
    r'餐厅|餐室|饭店|小吃店|'
    r'夜市|集市|市场|商场|购物中心|百货|'
    r'广场|摩天轮|游轮|码头|'
    r'咖啡馆?|奶茶店|酒吧|夜店|'
    r'[Mm]all\b|[Mm]arket\b|[Cc]af[eé]\b|[Bb]ar\b'
)


def _activity_load_weight(name):
    """按活动名关键词返回难度权重：高强度 1.5，低强度 0.5，其余 1.0。"""
    if not isinstance(name, str):
        return 1.0
    s = name.strip()
    if not s:
        return 1.0
    if _HIGH_DIFFICULTY_ACTIVITY.search(s):
        return 1.5
    if _LOW_DIFFICULTY_ACTIVITY.search(s):
        return 0.5
    return 1.0


def _day_activity_load(day):
    """单日加权活动量（sum of 难度权重）。"""
    return sum(_activity_load_weight(a) for a in day.get("activities", []))


def _is_flight_expense(e):
    """判断是否为城际/国际大交通，应排除出日均花费计算。"""
    if e.get("category") != "交通":
        return False
    desc = (e.get("description") or "").strip()
    if _MAJOR_TRANSPORT_KW.search(desc):
        return True
    if _LOCAL_TRANSPORT_PREFIX.match(desc):
        return False
    if _INTERCITY_ROUTE_RE.search(desc) and not _LOCAL_PLACE_RE.search(desc):
        return True
    return False


def _is_transit_day(day):
    """当天 transport 是否含城际/大交通（跨城日可游览容量低，不计入与纯游览日相同的期望）。"""
    for t in day.get("transport", []):
        if not isinstance(t, str):
            continue
        s = t.strip()
        if _MAJOR_TRANSPORT_KW.search(s) or _INTERCITY_ROUTE_RE.search(s):
            return True
    return False


def _transport_mentions_charter_rental_or_self_drive(day):
    """transport 中是否出现包车/租车/自驾（有记录即算，用于 coverage 缺口填补）。"""
    for t in day.get("transport") or []:
        if not isinstance(t, str):
            continue
        if _CHARTER_RENTAL_SELF_DRIVE_IN_TRANSPORT.search(t.strip()):
            return True
    return False


def _count_transit_days(days):
    return sum(1 for d in days if _is_transit_day(d))


def _is_non_sightseeing_leg(leg):
    """Leg 是否「非游览」：完全没有游览证据的 leg（中转 / 起讫点）。

    判定规则（必须同时满足）：
      1. 所有 days 都没有 activities（无任何安排的景点 / 活动），且
      2. 没有任何 day 是「非中转的实质性停留」——
         即不存在 (该 day 不是 transit_day) 且 (该 day 有 accommodation) 的情况

    第 2 条用于区分「文莱 5 小时中转（transit_day + 临时填了酒店字段）」
    与「胡志明度假 8 晚（无安排景点但每天住酒店休闲）」——前者是非游览，
    后者是度假型 leg 不应被排除。

    用于把「文莱 5 小时中转」「北京返程终点站」这类无任何游览证据的 leg
    从市场基准 / 覆盖率分母 / 城市评价列表中排除，避免拉低真实游览城市的评分。
    """
    days = leg.get("days", [])
    if not days:
        return True
    for day in days:
        if day.get("activities"):
            return False
    for day in days:
        if not _is_transit_day(day) and day.get("accommodation"):
            return False
    return True


_CHINESE_CHAR_RE = re.compile(r'[\u4e00-\u9fa5]')


def _chinese_one_char_typo(spot, activity):
    """中文景点名等长一字之差容错（处理 PDF/OCR 替换错字，如「白金汉宫」vs「白金汉官」）。

    判定条件（必须同时满足）：
      1. 双方长度相等且 >= 3（避免 2 字短词「古城」/「新城」误匹配）
      2. 双方都含中文字符（避免误启用在纯英文景点名上）
      3. 仅有 1 个位置的字符不同
    """
    if not spot or not activity:
        return False
    if len(spot) != len(activity) or len(spot) < 3:
        return False
    if not (_CHINESE_CHAR_RE.search(spot) and _CHINESE_CHAR_RE.search(activity)):
        return False
    diff = sum(1 for a, b in zip(spot, activity) if a != b)
    return diff == 1


def _spot_match(spot, activity):
    """景点名匹配：双向子串包含 + 中文等长一字差容错。"""
    if not isinstance(spot, str) or not isinstance(activity, str):
        return False
    if not spot or not activity:
        return False
    if spot in activity or activity in spot:
        return True
    return _chinese_one_char_typo(spot, activity)


def _split_must_see_aliases(item):
    """把 must_see 项展开为 [规范名, 别名1, 别名2, ...]。

    must_see 字段允许用 `|` 在单条字符串内声明同一景点的多个常见译名，例如
    "广安里大桥|广安大桥"（同一座桥的两种中文译法）。第一段为规范展示名。

    选择数据层显式声明而非纯字符串相似度算法的原因：长度差 1 的字符插入在
    `广安大桥/广安里大桥` 与 `白金汉宫/白金汉皇宫` 上字符串等价（均为 1 字
    插入），仅靠字符串相似度无法区分"同一物体的不同译名"与"不同物体的相似
    名字"。
    """
    if not isinstance(item, str):
        return []
    parts = [p.strip() for p in item.split("|") if p.strip()]
    return parts


def _spot_match_any(names, activity):
    """任一别名命中即算覆盖（用于 must_see 含 `|` 别名声明的项）。"""
    return any(_spot_match(n, activity) for n in names)


def _is_off_city_day(day, leg_city, must_see):
    """day 是否为「基地式游览的出城日」：未游 leg 城市必去清单且活动名不含 leg 城市。

    判定条件（必须同时满足）：
      1. 不是 transit_day（跨城日已有 0.5 折减，互斥）
      2. activities 非空（空 day 不算 off-city，避免误判休息日）
      3. activities 中没有任何一个：
         a) 匹配 leg 城市必去清单（双向子串或 OCR 容错）
         b) 包含 leg 城市名作为子串（如「爱丁堡王子街」）

    用于「以 X 为基地玩 Y/Z」型多日游识别（如以爱丁堡为基地玩苏格兰高地、
    以京都为基地玩奈良）。这类 day 把 leg city 的覆盖率分母拉大但分子不增，
    需要从 effective_days 中折减以反映用户实际只在 leg city 内消耗了少数日子。
    """
    if _is_transit_day(day):
        return False
    activities = day.get("activities", [])
    if not activities:
        return False
    must_see_list = must_see or []
    for act in activities:
        if not isinstance(act, str):
            continue
        for spot in must_see_list:
            names = _split_must_see_aliases(spot)
            if names and _spot_match_any(names, act):
                return False
        if leg_city and leg_city in act:
            return False
    return True


def _count_off_city_days(days, leg_city, must_see):
    return sum(1 for d in days if _is_off_city_day(d, leg_city, must_see))


def _effective_days(num_days, transit_days, off_city_days=0):
    """有效游览人日：跨城日按 0.5 天计；off-city 日（基地式游览出城）按 0.7 折减。

    每个 off-city day 扣 0.7：保留 0.3 的下限承认用户至少在该城落地睡过，
    但不让分母被外地游览日完全占满。transit_days 与 off_city_days 互斥
    （_is_off_city_day 已优先 transit_day 判定）。
    """
    if num_days <= 0:
        return 0.1
    return max(0.1, num_days - transit_days * 0.5 - off_city_days * 0.7)


def _stay_ratio(effective_days, typical_stay_days):
    typical = max(typical_stay_days or 3, 1)
    return max(0.1, min(1.0, effective_days / typical))


def _pace_day_score(count, low, high):
    """单日活动数相对理想区间 [low, high] 的得分。"""
    if low <= count <= high:
        return 95.0
    if count < low:
        return max(50.0, 95.0 - (low - count) * 12.0)
    return max(45.0, 95.0 - (count - high) * 8.0)


def _ideal_activity_range_for_day(is_transit, must_see, typical_stay_days):
    """游览日按城市景点密度调整理想区间；交通日期望活动较少。"""
    if is_transit:
        return 1.0, 3.0
    typical = max(typical_stay_days or 3, 1)
    if must_see:
        spot_density = len(must_see) / typical
        ideal_center = max(2.0, min(4.5, spot_density + 0.5))
    else:
        ideal_center = 2.5
    return ideal_center - 1.0, ideal_center + 1.5


def _compute_cost_metrics(trip, legs, expenses, benchmarks):
    """花费性价比评分（排除大交通机票）"""
    total_expense = sum(e.get("amount", 0) for e in expenses)
    flight_cost = sum(e.get("amount", 0) for e in expenses if _is_flight_expense(e))
    ground_expense = total_expense - flight_cost
    total_days = max((len(set(e.get("date") for e in expenses)) or 1), 1)
    traveler_count = max(trip.get("traveler_count", 1), 1)

    # 从 legs 推算总天数
    if legs:
        from datetime import date
        all_dates = []
        for leg in legs:
            for day in leg.get("days", []):
                all_dates.append(day.get("date"))
        total_days = max(len(set(all_dates)), total_days, 1)

    per_person_per_day = ground_expense / traveler_count / total_days if total_days else 0

    # 仅游览 leg 按 effective_days 加权计算市场参考
    # （中转 / 起讫点的城市基准不参与，否则会把伦敦+爱丁堡这类高消费目的地的
    #  人均日花费基准被文莱/北京等中转地拉低，错判用户消费偏高）
    weighted_market = 0.0
    total_w = 0.0
    for leg in legs:
        if _is_non_sightseeing_leg(leg):
            continue
        city = leg.get("city", "")
        bm = benchmarks.get(city)
        if not bm:
            continue
        days = leg.get("days", [])
        num_d = max(len(days), 1)
        transit_d = _count_transit_days(days)
        eff_d = _effective_days(num_d, transit_d)
        weighted_market += bm["avg_daily_cost_cny"] * eff_d
        total_w += eff_d
    market_avg = weighted_market / total_w if total_w > 0 else 1000

    if market_avg <= 0:
        ratio = 1.0
    else:
        ratio = per_person_per_day / market_avg

    # 「持平」plateau 与文案档位 (savings_pct ∈ [-10, 10] → "基本持平") 对齐
    # ratio ≤ 0.7   → 100        (节省 30%+，"花费控制出色")
    # 0.7-0.9       → 100→90     (节省 10-30%)
    # 0.9-1.1       → 90 plateau (持平 ±10%，"基本持平、花费合理")
    # 1.1-1.5       → 90→60     (超支 10-50%)
    # 1.5-2.0       → 60→45
    # > 2.0         → 45→30 floor
    if ratio <= 0.7:
        score = 100
    elif ratio <= 0.9:
        score = 100 - (ratio - 0.7) / 0.2 * 10
    elif ratio <= 1.1:
        score = 90
    elif ratio <= 1.5:
        score = 90 - (ratio - 1.1) / 0.4 * 30
    elif ratio <= 2.0:
        score = 60 - (ratio - 1.5) * 30
    else:
        score = max(30, 45 - (ratio - 2.0) * 20)

    savings_pct = round((1 - ratio) * 100)

    return {
        "score": _clamp(score),
        "per_person_per_day": round(per_person_per_day),
        "market_avg": round(market_avg),
        "savings_pct": savings_pct,
        "total_expense": round(total_expense),
        "flight_cost": round(flight_cost),
    }


def _compute_pace_metrics(legs, benchmarks=None):
    """行程节奏评分：按难度加权的日活动量对照城市理想区间，区分交通日；
    方差仅计非交通日。
    """
    benchmarks = benchmarks or {}
    daily_scores = []
    daily_counts = []
    daily_loads = []
    sightseeing_counts = []
    sightseeing_loads = []
    transit_day_count = 0
    busiest_day = None
    busiest_count = 0
    busiest_load = 0.0

    for leg in legs:
        city = leg.get("city", "")
        bm = benchmarks.get(city) or {}
        must_see = bm.get("must_see", [])
        typical = bm.get("typical_stay_days", 3)

        for day in leg.get("days", []):
            activities = day.get("activities", [])
            count = len(activities)
            load = _day_activity_load(day)
            daily_counts.append(count)
            daily_loads.append(load)
            is_transit = _is_transit_day(day)
            if is_transit:
                transit_day_count += 1
            else:
                sightseeing_counts.append(count)
                sightseeing_loads.append(load)

            lo, hi = _ideal_activity_range_for_day(is_transit, must_see, typical)
            daily_scores.append(_pace_day_score(load, lo, hi))

            # busiest 按加权活动量选，保留原始 count 作为展示
            if load > busiest_load:
                busiest_load = load
                busiest_count = count
                busiest_day = day.get("day_number")

    if not daily_scores:
        return {
            "score": 70,
            "avg_activities": 0,
            "avg_load": 0.0,
            "busiest_day": None,
            "busiest_count": 0,
            "busiest_load": 0.0,
            "transit_day_count": 0,
        }

    base_score = sum(daily_scores) / len(daily_scores)

    # 仅非交通日的加权活动量方差惩罚（避免跨城日拉低均值导致误判）
    if len(sightseeing_loads) > 1:
        mean_sl = sum(sightseeing_loads) / len(sightseeing_loads)
        variance = sum((x - mean_sl) ** 2 for x in sightseeing_loads) / len(sightseeing_loads)
        penalty = min(10, variance * 2)
        base_score -= penalty

    if transit_day_count > 0 and sightseeing_counts:
        avg_count_display = sum(sightseeing_counts) / len(sightseeing_counts)
        avg_load_display = sum(sightseeing_loads) / len(sightseeing_loads)
    else:
        avg_count_display = sum(daily_counts) / len(daily_counts)
        avg_load_display = sum(daily_loads) / len(daily_loads)

    return {
        "score": _clamp(base_score),
        "avg_activities": round(avg_count_display, 1),
        "avg_load": round(avg_load_display, 1),
        "busiest_day": busiest_day,
        "busiest_count": busiest_count,
        "busiest_load": round(busiest_load, 1),
        "transit_day_count": transit_day_count,
    }


def _day_requires_accommodation(day):
    """当日是否需要本地住宿记录（纳入覆盖率分母）。

    交通日 + 未记录住宿 视为合理在途过夜：
      - 返程日（行程最后一日含跨城大交通）
      - 凌晨/通宵航班日（在飞机上过夜）
    其他情形（含交通日但已填住宿，或非交通日）均应计入分母。
    """
    if day.get("accommodation"):
        return True
    return not _is_transit_day(day)


def _compute_accommodation_metrics(legs, expenses, benchmarks, traveler_count=1):
    """住宿品质评分。

    非游览 leg（中转 / 起讫点）整 leg 跳过 coverage 计算——这类 leg 的 days
    不计入「应有住宿」的分母，也不计入「实际有住宿」的分子。例如返程当天到达
    北京就回家了，本就不该住宿，也不该被算成「漏填住宿」拉低评分。

    market_avg 按用户实际住宿夜数加权，避免把没住过的中转 / 终点站城市基准
    计入参考价、误判用户酒店选择是否合理。
    """
    has_accommodation = 0
    required_days = 0
    hotel_names = []
    nights_by_city = {}

    for leg in legs:
        if _is_non_sightseeing_leg(leg):
            continue
        city = leg.get("city", "")
        for day in leg.get("days", []):
            if day.get("accommodation"):
                has_accommodation += 1
                hotel_names.append(day["accommodation"])
                nights_by_city[city] = nights_by_city.get(city, 0) + 1
            if _day_requires_accommodation(day):
                required_days += 1

    coverage = has_accommodation / required_days if required_days else 1.0

    hotel_expense = sum(e["amount"] for e in expenses if e.get("category") == "住宿")
    nights = max(has_accommodation, 1)
    avg_nightly = hotel_expense / nights / max(traveler_count, 1) if hotel_expense else 0

    # 按住宿夜数加权计算市场基准（无住宿城市自动排除，避免拉低参考价）
    weighted_market = 0.0
    total_nights_w = 0
    for city, n in nights_by_city.items():
        bm = benchmarks.get(city)
        if not bm:
            continue
        weighted_market += bm.get("avg_hotel_price_cny", 500) * n
        total_nights_w += n
    if total_nights_w > 0:
        market_hotel_avg = weighted_market / total_nights_w
    else:
        market_hotel_avg = 500

    # 覆盖率分 (有住宿记录) 60分权重 + 价格合理性 40分权重
    coverage_score = min(100, coverage * 100)
    if market_hotel_avg > 0 and avg_nightly > 0:
        price_ratio = avg_nightly / market_hotel_avg
        if 0.6 <= price_ratio <= 1.2:
            price_score = 90
        elif price_ratio < 0.6:
            price_score = 75  # 太便宜可能品质堪忧
        else:
            price_score = max(50, 90 - (price_ratio - 1.2) * 30)
    else:
        price_score = 70

    score = coverage_score * 0.6 + price_score * 0.4

    return {
        "score": _clamp(score),
        "coverage": round(coverage * 100),
        "avg_nightly": round(avg_nightly),
        "market_avg": round(market_hotel_avg),
        "unique_hotels": len(set(hotel_names)),
    }


def _detect_unrecorded_intercity_moves(legs):
    """检测「跨 leg 切换但前后两日均未填跨城交通」的位置。

    将所有 day 按 (date, day_number) 排成全局时间序，找出 leg city 发生变化的相邻
    pair。若该 pair 中任一 day 已被 _is_transit_day 识别（说明用户在前一日或当日的
    transport 字段中记录了跨城交通），就视为已覆盖；否则计入返回列表。

    返回 [{from, to, day_number}, ...]，仅供 text/tag 提示，不进入分母不影响评分——
    避免与「以 X 为基地玩 Y」的日返模式（评分应高）产生冲突。
    """
    timeline = []
    for leg in legs:
        city = leg.get("city", "")
        for day in leg.get("days", []):
            timeline.append((day.get("date") or "", day.get("day_number") or 0, city, day))
    timeline.sort(key=lambda x: (x[0], x[1]))

    moves = []
    for i in range(1, len(timeline)):
        _, _, prev_city, prev_day = timeline[i - 1]
        _, _, curr_city, curr_day = timeline[i]
        if not prev_city or not curr_city or prev_city == curr_city:
            continue
        if _is_transit_day(prev_day) or _is_transit_day(curr_day):
            continue
        moves.append({
            "from": prev_city,
            "to": curr_city,
            "day_number": curr_day.get("day_number"),
        })
    return moves


def _compute_transport_metrics(legs):
    """交通规划评分。

    coverage 只考察「跨城日是否记录了交通方式」——城内日的地铁、打车记录习惯
    与「交通规划质量」无关，把它们计入分母会要求用户每天都填一条 transport，
    令评分被记录习惯而非规划本身决定。

    `unrecorded_intercity_moves` 是一份纯提示性的副指标：当 leg 发生切换但前后
    两日的 transport 都不含跨城内容时，列出这些位置。它仅用于 text/tag 文案，
    **不进入 score 计算**——避免与「以基地城市玩日返」的合理玩法冲突。
    """
    has_transport_transit = 0
    transit_total = 0
    cities_in_order = []

    for leg in legs:
        city = leg.get("city", "")
        if city and (not cities_in_order or cities_in_order[-1] != city):
            cities_in_order.append(city)
        for day in leg.get("days", []):
            if _is_transit_day(day):
                transit_total += 1
                if day.get("transport"):
                    has_transport_transit += 1

    # 回头路检测
    has_backtrack = False
    if len(cities_in_order) >= 3:
        for i in range(2, len(cities_in_order)):
            if cities_in_order[i] == cities_in_order[i - 2]:
                has_backtrack = True
                break

    # leg 间至少有 (城市数 - 1) 次跨城；若用户根本没填 transport 而被识别为 0,
    # 用 leg 数兜底，让"两城但未记录任何交通"仍能得到合理的 0% 提示。
    inferred_transit = max(len(cities_in_order) - 1, 0)
    transit_total = max(transit_total, inferred_transit)

    # 非「航班/高铁/城A→城B」类词条、但已写明包车/租车/自驾的日期：按条数补足未覆盖的跨城记录缺口（封顶分母）
    charter_supp = 0
    if transit_total > 0:
        for leg in legs:
            for day in leg.get("days", []):
                if not day.get("transport"):
                    continue
                if _is_transit_day(day):
                    continue
                if _transport_mentions_charter_rental_or_self_drive(day):
                    charter_supp += 1

    gap = max(0, transit_total - has_transport_transit)
    effective_has = has_transport_transit + min(charter_supp, gap)

    coverage = effective_has / transit_total if transit_total > 0 else 1.0
    base_score = 70 + coverage * 25
    if has_backtrack:
        base_score -= 15

    return {
        "score": _clamp(base_score),
        "coverage": round(coverage * 100),
        "has_backtrack": has_backtrack,
        "city_route": " → ".join(cities_in_order) if cities_in_order else "",
        "transit_total": transit_total,
        "unrecorded_intercity_moves": _detect_unrecorded_intercity_moves(legs),
    }


def _compute_attractions_metrics(legs, benchmarks, past_visited=None):
    """景点覆盖评分：按停留人日相对典型停留调整期望，跨城日折减有效天；城市间按有效天加权。

    非游览 leg（中转 / 起讫点，无任何 activity 且无历史去过）不参与加权计算，
    避免把一个本来就不打算游玩的城市的 0% 覆盖率拉低整体得分。
    这类 leg 仍出现在 cities 列表中（带 non_sightseeing=True 标记）。

    past_visited: {city: [activity, ...]} — 历史行程已去景点，合并入 visited 集合，
                  使历史去过的必去点不再计入 missed。
    """
    past_visited = past_visited or {}
    city_results = []
    weighted_cov = 0.0
    weighted_raw = 0.0
    total_weight = 0.0

    for leg in legs:
        city = leg.get("city", "")
        bm = benchmarks.get(city)
        must_see = bm.get("must_see", []) if bm else []
        days = leg.get("days", [])
        num_days = max(len(days), 1)
        typical = bm.get("typical_stay_days", 3) if bm else 3
        transit_days = _count_transit_days(days)
        off_city_days = _count_off_city_days(days, city, must_see)
        effective_days = _effective_days(num_days, transit_days, off_city_days)
        ratio = _stay_ratio(effective_days, typical)

        is_non_sightseeing = (
            _is_non_sightseeing_leg(leg) and not past_visited.get(city)
        )

        visited = set()
        for day in days:
            for act in day.get("activities", []):
                visited.add(act)
        visited.update(past_visited.get(city, []))

        covered = []
        missed = []
        for spot in must_see:
            names = _split_must_see_aliases(spot)
            if not names:
                continue
            canonical = names[0]
            found = any(_spot_match_any(names, v) for v in visited)
            if found:
                covered.append(canonical)
            else:
                missed.append(canonical)

        if must_see:
            raw_ratio = len(covered) / len(must_see)
            raw_pct = raw_ratio * 100
            adjusted_ratio = min(1.0, raw_ratio / ratio) if ratio > 0 else 0.0
            adj_pct = adjusted_ratio * 100
        else:
            raw_pct = 100.0
            adj_pct = 100.0

        # 非游览 leg 不参与加权（仍保留在 city_results 中作展示）
        w = 0.0 if is_non_sightseeing else effective_days
        weighted_cov += adj_pct * w
        weighted_raw += raw_pct * w
        total_weight += w

        city_results.append({
            "city": city,
            "covered": covered,
            "missed": [] if is_non_sightseeing else missed,
            "coverage_pct": round(adj_pct),
            "raw_coverage_pct": round(raw_pct),
            "total_visited": len(visited),
            "effective_days": round(effective_days, 1),
            "typical_stay": typical,
            "stay_ratio": round(ratio, 2),
            "transit_days": transit_days,
            "non_sightseeing": is_non_sightseeing,
        })

    if not city_results:
        return {"score": 70, "cities": [], "overall_coverage": 0, "raw_overall_coverage": 0}

    if total_weight <= 0:
        overall_coverage = 0
        raw_overall = 0
    else:
        overall_coverage = weighted_cov / total_weight
        raw_overall = weighted_raw / total_weight

    score = min(100, overall_coverage * 0.9 + 10)

    return {
        "score": _clamp(score),
        "cities": city_results,
        "overall_coverage": round(overall_coverage),
        "raw_overall_coverage": round(raw_overall),
    }


# ---------------------------------------------------------------------------
# 2. 城市维度评价
# ---------------------------------------------------------------------------

def _evaluate_city(leg, expenses, benchmarks, past_visited=None):
    """单个城市的综合评价

    past_visited: {city: [activity, ...]} — 历史行程已去景点，合并入 visited 集合。
    """
    past_visited = past_visited or {}
    city = leg.get("city", "")
    bm = benchmarks.get(city, {})
    days = leg.get("days", [])
    num_days = max(len(days), 1)

    # 非游览 leg（中转 / 起讫点）走简化路径：不评景点维度，仅作信息展示
    if _is_non_sightseeing_leg(leg) and not past_visited.get(city):
        return {
            "city": city,
            "country": bm.get("country", leg.get("country", "")),
            "days": num_days,
            "score": 75,
            "text": f"{city}本次为过境/中转，未安排游览。",
            "tags": [{"type": "info", "text": "过境/中转"}],
            "missed_spots": [],
            "metrics": {
                "daily_cost": 0,
                "market_daily": bm.get("avg_daily_cost_cny", 1000),
                "spot_coverage": None,
                "spot_coverage_raw": None,
                "avg_activities": 0,
            },
            "non_sightseeing": True,
        }

    leg_expenses = [e for e in expenses if e.get("leg_id") == leg.get("id")]
    total_cost = sum(e["amount"] for e in leg_expenses)
    traveler_count = 1  # leg 级别无人数信息, 后面由外层补正

    activities_count = sum(len(d.get("activities", [])) for d in days)

    # 花费子分
    market_daily = bm.get("avg_daily_cost_cny", 1000)
    daily_cost = total_cost / num_days if num_days else 0
    cost_ratio = daily_cost / market_daily if market_daily else 1
    cost_sub = _clamp(90 - max(0, (cost_ratio - 0.8)) * 40)

    # 景点子分（按停留人日相对典型停留调整期望）
    must_see = bm.get("must_see", [])
    typical_stay = bm.get("typical_stay_days", 3)
    transit_days = _count_transit_days(days)
    off_city_days = _count_off_city_days(days, city, must_see)
    effective_days = _effective_days(num_days, transit_days, off_city_days)
    stay_ratio_val = _stay_ratio(effective_days, typical_stay)

    visited = set()
    for d in days:
        visited.update(d.get("activities", []))
    visited.update(past_visited.get(city, []))
    covered = []
    missed = []
    for s in must_see:
        names = _split_must_see_aliases(s)
        if not names:
            continue
        canonical = names[0]
        if any(_spot_match_any(names, v) for v in visited):
            covered.append(canonical)
        else:
            missed.append(canonical)
    if must_see:
        raw_ratio = len(covered) / len(must_see)
        spot_pct_raw = raw_ratio * 100
        adjusted_ratio = min(1.0, raw_ratio / stay_ratio_val) if stay_ratio_val > 0 else 0.0
        spot_pct = adjusted_ratio * 100
    else:
        spot_pct_raw = 100.0
        spot_pct = 100.0
    spot_sub = _clamp(min(100, spot_pct * 0.9 + 10))

    # 节奏子分（与整体维度一致的按难度加权日模型）
    sightseeing_counts = []
    sightseeing_loads = []
    if days:
        daily_scores = []
        for d in days:
            c = len(d.get("activities", []))
            load = _day_activity_load(d)
            is_t = _is_transit_day(d)
            lo, hi = _ideal_activity_range_for_day(is_t, must_see, typical_stay)
            daily_scores.append(_pace_day_score(load, lo, hi))
            if not is_t:
                sightseeing_counts.append(c)
                sightseeing_loads.append(load)
        pace_mean = sum(daily_scores) / len(daily_scores)
        if len(sightseeing_loads) > 1:
            msl = sum(sightseeing_loads) / len(sightseeing_loads)
            var = sum((x - msl) ** 2 for x in sightseeing_loads) / len(sightseeing_loads)
            pace_mean -= min(10, var * 2)
        pace_sub = _clamp(pace_mean)
    else:
        pace_sub = 92

    if sightseeing_counts:
        avg_activities = sum(sightseeing_counts) / len(sightseeing_counts)
    else:
        avg_activities = activities_count / num_days if num_days else 0
    avg_load = (
        sum(sightseeing_loads) / len(sightseeing_loads) if sightseeing_loads else 0.0
    )

    # 停留天数子分
    typical = bm.get("typical_stay_days", 3)
    if num_days >= typical:
        stay_sub = 90
    elif num_days >= typical - 1:
        stay_sub = 78
    else:
        stay_sub = 65

    score = _clamp(cost_sub * 0.25 + spot_sub * 0.30 + pace_sub * 0.25 + stay_sub * 0.20)

    # 生成标签
    tags = []
    if cost_ratio < 0.85:
        tags.append({"type": "positive", "text": "花费优秀"})
    elif cost_ratio > 1.2:
        tags.append({"type": "warning", "text": "花费偏高"})
    if spot_pct >= 80:
        tags.append({"type": "positive", "text": "景点全面"})
    elif spot_pct < 80:
        tags.append({"type": "warning", "text": "景点覆盖不足"})
    if avg_load > 4.0:
        tags.append({"type": "warning", "text": "节奏偏紧"})
    elif avg_load and avg_load < 1.5:
        tags.append({"type": "warning", "text": "行程较松散"})
    if num_days < typical - 1:
        tags.append({"type": "warning", "text": "停留偏短"})

    # 生成文字
    text = _generate_city_text(city, num_days, daily_cost, market_daily,
                               covered, missed, avg_activities, bm)

    return {
        "city": city,
        "country": bm.get("country", leg.get("country", "")),
        "days": num_days,
        "score": score,
        "text": text,
        "tags": tags,
        "missed_spots": missed[:5],
        "metrics": {
            "daily_cost": round(daily_cost),
            "market_daily": market_daily,
            "spot_coverage": round(spot_pct),
            "spot_coverage_raw": round(spot_pct_raw),
            "avg_activities": round(avg_activities, 1),
        },
    }


# ---------------------------------------------------------------------------
# 3. 模板文字生成
# ---------------------------------------------------------------------------

def _score_label(score):
    if score >= 90:
        return "优秀"
    elif score >= 80:
        return "良好"
    elif score >= 70:
        return "中等"
    elif score >= 60:
        return "一般"
    return "较差"


def _generate_summary(overall_score, cost_m, pace_m, attractions_m, legs,
                      profile=None, tier_label=""):
    """一句话总评"""
    cities = [leg.get("city", "") for leg in legs if leg.get("city")]
    dest = "、".join(cities[:3])
    if len(cities) > 3:
        dest += f"等{len(cities)}城"

    if cost_m["savings_pct"] > 10:
        cost_tag = "性价比出色的"
    elif cost_m["savings_pct"] > 0:
        cost_tag = "花费合理的"
    else:
        cost_tag = ""

    if overall_score >= 90:
        quality = "精彩纷呈的"
    elif overall_score >= 80:
        quality = "规划良好的"
    elif overall_score >= 70:
        quality = "中规中矩的"
    else:
        quality = "有提升空间的"

    prefix = ""
    if tier_label:
        prefix = f"以{tier_label}消费水平衡量，这是一次"
    visited = profile.get("visited_countries_cities") if profile else None
    if visited and isinstance(visited, dict) and visited:
        n_countries = len(visited)
        n_cities = sum(
            len(trip.get("cities", []))
            for trips in visited.values() if isinstance(trips, list)
            for trip in trips if isinstance(trip, dict)
        )
        if n_countries > 0 and n_cities > 0:
            prefix = f"作为已探访 {n_countries} 国 {n_cities} 城的{tier_label}旅行者，这是一次"

    if prefix:
        return f"{prefix}{cost_tag}{quality}{dest}之旅"
    return f"{cost_tag}{quality}{dest}之旅"


def _generate_cost_text(m, tier_label=""):
    ppd = m["per_person_per_day"]
    market = m["market_avg"]
    savings = m["savings_pct"]
    flight_cost = m.get("flight_cost", 0)
    ref = f"{tier_label}参考水准" if tier_label else "市场参考水准"

    flight_note = f"（不含大交通 ¥{flight_cost:,}）" if flight_cost > 0 else ""

    if savings > 0:
        return (f"本次行程人均日花费 ¥{ppd}{flight_note}，低于{ref} ¥{market} "
                f"约 {savings}%，花费控制出色。总花费 ¥{m['total_expense']:,}。")
    elif savings > -15:
        return (f"本次行程人均日花费 ¥{ppd}{flight_note}，与{ref} ¥{market} 基本持平，"
                f"花费合理。总花费 ¥{m['total_expense']:,}。")
    else:
        return (f"本次行程人均日花费 ¥{ppd}{flight_note}，高于{ref} ¥{market} "
                f"约 {abs(savings)}%。总花费 ¥{m['total_expense']:,}，建议下次可优化住宿或交通开支。")


def _generate_cost_tags(m):
    tags = []
    if m["savings_pct"] > 10:
        tags.append({"type": "positive", "text": "低于参考水准"})
    elif m["savings_pct"] < -15:
        tags.append({"type": "warning", "text": "高于参考水准"})
    return tags


def _generate_pace_text(m):
    avg_count = m["avg_activities"]
    avg_load = m.get("avg_load", avg_count)
    busiest = m["busiest_day"]
    busiest_count = m["busiest_count"]
    busiest_load = m.get("busiest_load", busiest_count)
    transit_n = m.get("transit_day_count", 0)

    if transit_n > 0:
        parts = [
            f"含 {transit_n} 个跨城交通日",
            f"非交通日平均每天 {avg_count} 个活动（按难度加权活动量 {avg_load}）",
        ]
    else:
        parts = [f"平均每天 {avg_count} 个活动（按难度加权活动量 {avg_load}）"]

    # 以加权活动量为主要判据：2.0-3.5 为适中区间
    if 2.0 <= avg_load <= 3.5:
        parts.append("节奏适中，松紧得当")
    elif avg_load > 4.0:
        parts.append("整体偏紧凑，建议适当留出休息时间")
    elif avg_load < 1.5:
        parts.append("行程较为宽松，可适当增加体验项目")

    text = "，".join(parts) + "。"

    if busiest and busiest_load > 5.0:
        text += (
            f"其中 Day{busiest} 安排了 {busiest_count} 个活动（活动量 {busiest_load}），"
            f"略显密集。"
        )

    return text


def _generate_pace_tags(m):
    tags = []
    transit_n = m.get("transit_day_count", 0)
    if transit_n >= 2:
        tags.append({"type": "info", "text": f"含 {transit_n} 个交通日"})

    avg_load = m.get("avg_load", m["avg_activities"])
    busiest_load = m.get("busiest_load", m["busiest_count"])
    if 2.0 <= avg_load <= 3.5:
        tags.append({"type": "positive", "text": "节奏适中"})
    elif avg_load > 4.0:
        tags.append({"type": "warning", "text": "部分天数偏紧"})
    if m["busiest_day"] and busiest_load > 5.0:
        tags.append({"type": "warning", "text": f"Day{m['busiest_day']} 偏满"})
    return tags


def _generate_accommodation_text(m, tier_label=""):
    if m["coverage"] >= 90:
        cov_text = "住宿记录完整"
    elif m["coverage"] >= 60:
        cov_text = "大部分天数有住宿记录"
    else:
        cov_text = "部分天数缺少住宿信息"

    ref = f"{tier_label}参考价" if tier_label else "参考均价"
    if m["avg_nightly"] > 0:
        price_text = f"，平均每晚 ¥{m['avg_nightly']}"
        market = m["market_avg"]
        if m["avg_nightly"] < market * 0.8:
            price_text += f"，低于{ref} ¥{market}，性价比较高"
        elif m["avg_nightly"] > market * 1.2:
            price_text += f"，高于{ref} ¥{market}"
        else:
            price_text += f"，与{ref} ¥{market} 相当"
    else:
        price_text = ""

    return f"{cov_text}{price_text}。共入住 {m['unique_hotels']} 家不同酒店。"


def _generate_accommodation_tags(m):
    tags = []
    if m["avg_nightly"] > 0 and m["market_avg"] > 0:
        ratio = m["avg_nightly"] / m["market_avg"]
        if ratio < 0.8:
            tags.append({"type": "positive", "text": "住宿性价比高"})
        elif ratio > 1.3:
            tags.append({"type": "warning", "text": "住宿花费偏高"})
    if m["coverage"] >= 90:
        tags.append({"type": "positive", "text": "记录完整"})
    return tags


def _generate_transport_text(m):
    route = m.get("city_route", "")
    parts = []
    if route:
        parts.append(f"行程路线: {route}")
    if m["has_backtrack"]:
        parts.append("存在回头路，建议优化路线顺序以节省交通时间和费用")
    else:
        parts.append("路线规划合理，无回头路")

    coverage = m.get("coverage", 0)
    if coverage == 0:
        parts.append("行程中暂无出行方式记录，补充后评分可进一步提升")
    elif coverage < 50:
        parts.append(f"目前仅 {coverage}% 的天数有出行方式记录，建议补充完整以获得更准确的评分")

    base = "，".join(parts) + "。"

    moves = m.get("unrecorded_intercity_moves") or []
    if moves:
        sample = "、".join(
            f"Day{mv['day_number']} {mv['from']}→{mv['to']}" for mv in moves[:3]
        )
        base += f"提示: {sample} 等跨城切换暂未记录交通方式，可补充以让行程档案更完整（不影响评分）。"
    return base


def _generate_transport_tags(m):
    tags = []
    if not m["has_backtrack"]:
        tags.append({"type": "positive", "text": "路线合理"})
    else:
        tags.append({"type": "warning", "text": "存在回头路"})

    coverage = m.get("coverage", 0)
    if coverage == 0:
        tags.append({"type": "info", "text": "暂无交通记录"})
    elif coverage < 50:
        tags.append({"type": "warning", "text": f"交通覆盖 {coverage}%"})

    moves = m.get("unrecorded_intercity_moves") or []
    if moves:
        tags.append({"type": "info", "text": f"{len(moves)} 处跨城未记录"})

    return tags


def _generate_attractions_text(m):
    cov = m["overall_coverage"]
    raw = m.get("raw_overall_coverage")
    if cov >= 85:
        base = f"整体景点覆盖率 {cov}%（按停留天数调整），必去景点基本全面覆盖，行程安排充实。"
        if raw is not None and raw < cov - 5:
            base += f" 未调整前约 {raw}%。"
        return base
    elif cov >= 60:
        return (
            f"整体景点覆盖率 {cov}%（按停留天数调整），大部分核心景点已包含；"
            f"部分城市停留较短时覆盖有限，建议下次适当延长或聚焦必去清单。"
        )
    else:
        return (
            f"整体景点覆盖率 {cov}%（按停留天数调整），相对典型停留仍有不少必去点未覆盖，"
            f"建议下次重点补充或增加停留日。"
        )


def _generate_attractions_tags(m):
    tags = []
    cov = m["overall_coverage"]
    if cov >= 85:
        tags.append({"type": "positive", "text": "覆盖全面"})
    elif cov < 50:
        tags.append({"type": "warning", "text": "覆盖不足"})
    return tags


def _generate_city_text(city, num_days, daily_cost, market_daily,
                        covered, missed, avg_activities, bm):
    """单城市评价文字"""
    season = bm.get("_season_label", "")
    season_tag = f"（{season}）" if season and season != "平季" else ""

    parts = []
    parts.append(f"{city}停留 {num_days} 天")

    if daily_cost > 0 and market_daily > 0:
        ratio = daily_cost / market_daily
        if ratio < 0.85:
            parts.append(f"日均花费 ¥{round(daily_cost)}，低于参考水准 ¥{round(market_daily)}{season_tag}")
        elif ratio > 1.15:
            parts.append(f"日均花费 ¥{round(daily_cost)}，高于参考水准 ¥{round(market_daily)}{season_tag}")
        else:
            parts.append(f"日均花费 ¥{round(daily_cost)}，与参考水准 ¥{round(market_daily)} 持平{season_tag}")

    if covered:
        parts.append(f"已覆盖{', '.join(covered[:4])}等{'核心' if len(covered) >= 3 else ''}景点")
    if missed:
        parts.append(f"遗憾未能前往{', '.join(missed[:3])}")

    typical = bm.get("typical_stay_days", 3)
    if num_days < typical - 1:
        parts.append(f"建议下次至少停留 {typical} 天以获得更完整的体验")

    return "，".join(parts[:3]) + "。" + ("，".join(parts[3:]) + "。" if len(parts) > 3 else "")


def _generate_suggestions(trip, legs, cost_m, pace_m, attractions_m, benchmarks, profile=None):
    """后续行程建议"""
    suggestions = []
    visited_cities = {leg.get("city", "") for leg in legs}

    # 合并 profile 中历史访问过的城市
    visited = profile.get("visited_countries_cities") if profile else None
    if visited and isinstance(visited, dict):
        for trips in visited.values():
            if isinstance(trips, list):
                for trip in trips:
                    if isinstance(trip, dict):
                        visited_cities.update(trip.get("cities", []))

    # 基于景点遗漏的建议
    for city_data in attractions_m.get("cities", []):
        missed = city_data.get("missed", [])
        city = city_data.get("city", "")
        if len(missed) >= 2:
            suggestions.append(
                f"下次{city}之行可重点补充{', '.join(missed[:3])}等景点"
            )

    # 基于节奏的建议
    if pace_m.get("avg_load", pace_m["avg_activities"]) > 4.0:
        suggestions.append(
            "整体行程偏紧凑，建议每天安排 2-3 个核心景点并预留休息和自由探索时间"
        )

    # 基于花费的建议
    if cost_m["savings_pct"] < -15:
        suggestions.append(
            "花费略高于市场水平，可考虑提前预订住宿和交通以获得更好价格"
        )

    # 推荐邻近目的地
    NEARBY_RECS = {
        "曼谷": [("芭提雅", "距离曼谷仅 2 小时车程，适合海滩度假"), ("华欣", "皇室度假胜地，距曼谷 3 小时")],
        "清迈": [("拜县", "清迈周边的文艺小城"), ("清莱", "白庙和蓝庙值得一游")],
        "吉隆坡": [("槟城", "美食之都，世界遗产古城"), ("马六甲", "历史文化名城，距吉隆坡 2 小时")],
        "河内": [("下龙湾", "世界自然遗产，距河内约 4 小时"), ("会安", "古镇灯笼和美食")],
        "胡志明市": [("会安", "千年古镇值得一游"), ("富国岛", "越南度假天堂")],
        "东京": [("箱根", "温泉和富士山景观"), ("镰仓", "经典的古都一日游")],
        "大阪": [("奈良", "可爱的小鹿和古寺"), ("神户", "牛排和港口夜景")],
        "京都": [("奈良", "搭配京都的经典路线"), ("宇治", "抹茶之乡")],
        "首尔": [("釜山", "韩国第二大城市，海景和美食"), ("济州岛", "韩国度假胜地")],
        "伦敦": [("爱丁堡", "苏格兰首府，古堡风情"), ("牛津", "学术圣地，距伦敦 1 小时")],
        "维也纳": [("萨尔茨堡", "莫扎特故乡，音乐之城"), ("哈尔施塔特", "童话小镇，绝美湖景")],
        "慕尼黑": [("新天鹅堡", "童话城堡，巴伐利亚经典"), ("海德堡", "古老大学城，浪漫莱茵河畔")],
        "柏林": [("波茨坦", "无忧宫和普鲁士历史"), ("德累斯顿", "易北河上的佛罗伦萨")],
        "哥本哈根": [("奥胡斯", "丹麦第二大城，现代艺术"), ("欧登塞", "安徒生故乡")],
        "斯德哥尔摩": [("哥德堡", "西海岸美食之城"), ("基律纳", "极光和冰酒店")],
        "赫尔辛基": [("罗瓦涅米", "圣诞老人村，追极光胜地"), ("坦佩雷", "芬兰工业文化名城")],
        "奥斯陆": [("卑尔根", "峡湾门户，彩色木屋"), ("特罗姆瑟", "极光之城，北极圈体验")],
        "开罗": [("卢克索", "神庙和帝王谷"), ("阿斯旺", "努比亚文化和阿布辛贝神庙")],
        "内罗毕": [("马赛马拉", "非洲最壮观的野生动物迁徙"), ("蒙巴萨", "印度洋海滨度假")],
        "巴黎": [("凡尔赛", "宏伟的皇家宫殿"), ("卢瓦尔河谷", "城堡之旅")],
        "北京": [("天津", "高铁 30 分钟直达"), ("承德", "避暑山庄值得一游")],
        "上海": [("苏州", "园林之城，高铁 25 分钟"), ("杭州", "西湖美景，高铁 1 小时")],
        "成都": [("乐山", "大佛和美食"), ("九寨沟", "世界自然遗产")],
    }
    for city in visited_cities:
        recs = NEARBY_RECS.get(city, [])
        for nearby_city, desc in recs:
            if nearby_city not in visited_cities:
                suggestions.append(f"推荐下一站: {nearby_city}——{desc}")
                break
        if len(suggestions) >= 5:
            break

    return suggestions[:5]


# ---------------------------------------------------------------------------
# 4. 主入口
# ---------------------------------------------------------------------------

def generate_evaluation(trip_dict, profile=None, past_visited=None):
    """
    生成行程评价。
    trip_dict: Trip.to_dict(include_legs=True, include_expenses=True) 的结果
    profile: UserProfile.to_dict() 或 None
    past_visited: {city: [activity, ...]} — 历史行程中该城市已去景点，
                  供景点覆盖评估时扣除，避免将历史已访景点列为"遗漏"
    返回: {"overall_score": int, "evaluation_data": dict}
    """
    raw_benchmarks = _load_benchmarks()
    legs = trip_dict.get("legs", [])
    expenses = trip_dict.get("expenses", [])
    traveler_count = max(trip_dict.get("traveler_count", 1), 1)

    # 消费层级 & 季节调整（用家庭人数，不受单次行程出行人数影响）
    household_size = _extract_household_size(profile)
    tier_mult = _compute_tier_multiplier(profile, household_size)
    tier_lbl = _tier_label(tier_mult)
    benchmarks = _build_adjusted_benchmarks(raw_benchmarks, tier_mult, legs, traveler_count)

    cost_m = _compute_cost_metrics(trip_dict, legs, expenses, benchmarks)
    pace_m = _compute_pace_metrics(legs, benchmarks)
    accom_m = _compute_accommodation_metrics(legs, expenses, benchmarks, traveler_count)
    transport_m = _compute_transport_metrics(legs)
    attractions_m = _compute_attractions_metrics(legs, benchmarks, past_visited=past_visited)

    overall = _clamp(
        cost_m["score"] * 0.20 +
        pace_m["score"] * 0.20 +
        accom_m["score"] * 0.15 +
        transport_m["score"] * 0.15 +
        attractions_m["score"] * 0.30
    )

    summary = _generate_summary(overall, cost_m, pace_m, attractions_m, legs,
                                profile, tier_label=tier_lbl)

    cities = []
    for leg in legs:
        if _is_non_sightseeing_leg(leg):
            continue
        city_eval = _evaluate_city(leg, expenses, benchmarks, past_visited=past_visited)
        cities.append(city_eval)

    suggestions = _generate_suggestions(trip_dict, legs, cost_m, pace_m,
                                        attractions_m, benchmarks, profile)

    cost_text = _generate_cost_text(cost_m, tier_label=tier_lbl)
    cost_tags = _generate_cost_tags(cost_m)

    if profile and profile.get("annual_travel_budget", 0) > 0:
        budget = profile["annual_travel_budget"]
        budget_pct = round(cost_m["total_expense"] / budget * 100)
        if budget_pct > 50:
            cost_tags.append({"type": "warning", "text": f"占年度预算 {budget_pct}%"})
        cost_text += f"本次行程占年度旅游预算的 {budget_pct}%。"

    evaluation_data = {
        "summary": summary,
        "profile_context": {
            "tier_label": tier_lbl,
            "tier_multiplier": round(tier_mult, 2),
        },
        "dimensions": {
            "cost": {
                "score": cost_m["score"],
                "label": "花费性价比",
                "text": cost_text,
                "tags": cost_tags,
                "metrics": cost_m,
            },
            "pace": {
                "score": pace_m["score"],
                "label": "行程节奏",
                "text": _generate_pace_text(pace_m),
                "tags": _generate_pace_tags(pace_m),
                "metrics": pace_m,
            },
            "accommodation": {
                "score": accom_m["score"],
                "label": "住宿品质",
                "text": _generate_accommodation_text(accom_m, tier_label=tier_lbl),
                "tags": _generate_accommodation_tags(accom_m),
                "metrics": accom_m,
            },
            "transport": {
                "score": transport_m["score"],
                "label": "交通规划",
                "text": _generate_transport_text(transport_m),
                "tags": _generate_transport_tags(transport_m),
                "metrics": transport_m,
            },
            "attractions": {
                "score": attractions_m["score"],
                "label": "景点覆盖",
                "text": _generate_attractions_text(attractions_m),
                "tags": _generate_attractions_tags(attractions_m),
                "metrics": attractions_m,
            },
        },
        "cities": cities,
        "suggestions": suggestions,
    }

    return {
        "overall_score": overall,
        "evaluation_data": evaluation_data,
    }
