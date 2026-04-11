"""
行程评价引擎 — 本地量化指标计算 + 模板文字生成
"""
import json
import os
import math

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_benchmarks_cache = None


def _load_benchmarks():
    global _benchmarks_cache
    if _benchmarks_cache is None:
        path = os.path.join(DATA_DIR, "city_benchmarks.json")
        with open(path, "r", encoding="utf-8") as f:
            _benchmarks_cache = json.load(f)
    return _benchmarks_cache


def _clamp(v, lo=0, hi=100):
    return max(lo, min(hi, int(round(v))))


# ---------------------------------------------------------------------------
# 1. 本地指标计算
# ---------------------------------------------------------------------------

def _compute_cost_metrics(trip, legs, expenses, benchmarks):
    """花费性价比评分"""
    total_expense = sum(e.get("amount", 0) for e in expenses)
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

    per_person_per_day = total_expense / traveler_count / total_days if total_days else 0

    # 用城市基准加权平均作为参考
    market_avg = 0
    city_count = 0
    for leg in legs:
        city = leg.get("city", "")
        bm = benchmarks.get(city)
        if bm:
            market_avg += bm["avg_daily_cost_cny"]
            city_count += 1
    market_avg = market_avg / city_count if city_count else 800

    if market_avg <= 0:
        ratio = 1.0
    else:
        ratio = per_person_per_day / market_avg

    # ratio < 0.7 → 100, ratio == 1.0 → 80, ratio > 1.5 → 50
    if ratio <= 0.7:
        score = 100
    elif ratio <= 1.0:
        score = 100 - (ratio - 0.7) / 0.3 * 20
    elif ratio <= 1.5:
        score = 80 - (ratio - 1.0) / 0.5 * 30
    else:
        score = max(30, 50 - (ratio - 1.5) * 20)

    savings_pct = round((1 - ratio) * 100)

    return {
        "score": _clamp(score),
        "per_person_per_day": round(per_person_per_day),
        "market_avg": round(market_avg),
        "savings_pct": savings_pct,
        "total_expense": round(total_expense),
    }


def _compute_pace_metrics(legs):
    """行程节奏评分"""
    daily_counts = []
    busiest_day = None
    busiest_count = 0

    for leg in legs:
        for day in leg.get("days", []):
            activities = day.get("activities", [])
            count = len(activities)
            daily_counts.append(count)
            if count > busiest_count:
                busiest_count = count
                busiest_day = day.get("day_number")

    if not daily_counts:
        return {"score": 70, "avg_activities": 0, "busiest_day": None, "busiest_count": 0}

    avg = sum(daily_counts) / len(daily_counts)

    # 2-3 activities/day is optimal → 95, <1 or >5 is bad
    if 2 <= avg <= 3:
        base_score = 95
    elif 1.5 <= avg < 2:
        base_score = 85
    elif 3 < avg <= 4:
        base_score = 82
    elif 1 <= avg < 1.5:
        base_score = 75
    elif 4 < avg <= 5:
        base_score = 70
    else:
        base_score = 55

    # 日间方差惩罚: 忽高忽低扣分
    if len(daily_counts) > 1:
        variance = sum((c - avg) ** 2 for c in daily_counts) / len(daily_counts)
        penalty = min(15, variance * 3)
        base_score -= penalty

    return {
        "score": _clamp(base_score),
        "avg_activities": round(avg, 1),
        "busiest_day": busiest_day,
        "busiest_count": busiest_count,
    }


def _compute_accommodation_metrics(legs, expenses, benchmarks):
    """住宿品质评分"""
    has_accommodation = 0
    total_days = 0
    hotel_names = []

    for leg in legs:
        for day in leg.get("days", []):
            total_days += 1
            if day.get("accommodation"):
                has_accommodation += 1
                hotel_names.append(day["accommodation"])

    coverage = has_accommodation / total_days if total_days else 0

    hotel_expense = sum(e["amount"] for e in expenses if e.get("category") == "住宿")
    nights = max(has_accommodation, 1)
    avg_nightly = hotel_expense / nights if hotel_expense else 0

    # 对比基准
    market_hotel_avg = 0
    city_count = 0
    for leg in legs:
        bm = benchmarks.get(leg.get("city", ""))
        if bm:
            market_hotel_avg += bm.get("avg_hotel_price_cny", 300)
            city_count += 1
    market_hotel_avg = market_hotel_avg / city_count if city_count else 300

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


def _compute_transport_metrics(legs):
    """交通规划评分"""
    has_transport = 0
    total_days = 0
    cities_in_order = []

    for leg in legs:
        city = leg.get("city", "")
        if city and (not cities_in_order or cities_in_order[-1] != city):
            cities_in_order.append(city)
        for day in leg.get("days", []):
            total_days += 1
            transport = day.get("transport", [])
            if transport:
                has_transport += 1

    # 回头路检测
    has_backtrack = False
    if len(cities_in_order) >= 3:
        for i in range(2, len(cities_in_order)):
            if cities_in_order[i] == cities_in_order[i - 2]:
                has_backtrack = True
                break

    coverage = has_transport / total_days if total_days else 0
    base_score = 70 + coverage * 25
    if has_backtrack:
        base_score -= 15

    return {
        "score": _clamp(base_score),
        "coverage": round(coverage * 100),
        "has_backtrack": has_backtrack,
        "city_route": " → ".join(cities_in_order) if cities_in_order else "",
    }


def _compute_attractions_metrics(legs, benchmarks):
    """景点覆盖评分"""
    city_results = []

    for leg in legs:
        city = leg.get("city", "")
        bm = benchmarks.get(city)
        must_see = bm["must_see"] if bm else []

        visited = set()
        for day in leg.get("days", []):
            for act in day.get("activities", []):
                visited.add(act)

        # 模糊匹配: 活动名包含景点名或反之
        covered = []
        missed = []
        for spot in must_see:
            found = any(spot in v or v in spot for v in visited)
            if found:
                covered.append(spot)
            else:
                missed.append(spot)

        coverage_pct = len(covered) / len(must_see) * 100 if must_see else 100
        city_results.append({
            "city": city,
            "covered": covered,
            "missed": missed,
            "coverage_pct": round(coverage_pct),
            "total_visited": len(visited),
        })

    if not city_results:
        return {"score": 70, "cities": [], "overall_coverage": 0}

    overall_coverage = sum(c["coverage_pct"] for c in city_results) / len(city_results)
    score = min(100, overall_coverage * 0.9 + 10)

    return {
        "score": _clamp(score),
        "cities": city_results,
        "overall_coverage": round(overall_coverage),
    }


# ---------------------------------------------------------------------------
# 2. 城市维度评价
# ---------------------------------------------------------------------------

def _evaluate_city(leg, expenses, benchmarks):
    """单个城市的综合评价"""
    city = leg.get("city", "")
    bm = benchmarks.get(city, {})
    days = leg.get("days", [])

    leg_expenses = [e for e in expenses if e.get("leg_id") == leg.get("id")]
    total_cost = sum(e["amount"] for e in leg_expenses)
    num_days = max(len(days), 1)
    traveler_count = 1  # leg 级别无人数信息, 后面由外层补正

    activities_count = sum(len(d.get("activities", [])) for d in days)
    avg_activities = activities_count / num_days

    # 花费子分
    market_daily = bm.get("avg_daily_cost_cny", 800)
    daily_cost = total_cost / num_days if num_days else 0
    cost_ratio = daily_cost / market_daily if market_daily else 1
    cost_sub = _clamp(90 - max(0, (cost_ratio - 0.8)) * 40)

    # 景点子分
    must_see = bm.get("must_see", [])
    visited = set()
    for d in days:
        visited.update(d.get("activities", []))
    covered = [s for s in must_see if any(s in v or v in s for v in visited)]
    missed = [s for s in must_see if s not in covered]
    spot_pct = len(covered) / len(must_see) * 100 if must_see else 100
    spot_sub = _clamp(spot_pct * 0.9 + 10)

    # 节奏子分
    if 2 <= avg_activities <= 3:
        pace_sub = 92
    elif avg_activities < 2:
        pace_sub = 78
    else:
        pace_sub = max(60, 92 - (avg_activities - 3) * 10)

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
    elif spot_pct < 50:
        tags.append({"type": "warning", "text": "景点覆盖不足"})
    if avg_activities > 4:
        tags.append({"type": "warning", "text": "节奏偏紧"})
    elif avg_activities < 1.5:
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


def _generate_summary(overall_score, cost_m, pace_m, attractions_m, legs):
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

    return f"{cost_tag}{quality}{dest}之旅"


def _generate_cost_text(m):
    ppd = m["per_person_per_day"]
    market = m["market_avg"]
    savings = m["savings_pct"]

    if savings > 0:
        return (f"本次行程人均日花费 ¥{ppd}，低于该目的地市场均价 ¥{market} "
                f"约 {savings}%，花费控制出色。总花费 ¥{m['total_expense']:,}。")
    elif savings > -15:
        return (f"本次行程人均日花费 ¥{ppd}，与市场均价 ¥{market} 基本持平，"
                f"花费合理。总花费 ¥{m['total_expense']:,}。")
    else:
        return (f"本次行程人均日花费 ¥{ppd}，高于市场均价 ¥{market} "
                f"约 {abs(savings)}%。总花费 ¥{m['total_expense']:,}，建议下次可优化住宿或交通开支。")


def _generate_cost_tags(m):
    tags = []
    if m["savings_pct"] > 10:
        tags.append({"type": "positive", "text": "低于市场均价"})
    elif m["savings_pct"] < -15:
        tags.append({"type": "warning", "text": "高于市场均价"})
    return tags


def _generate_pace_text(m):
    avg = m["avg_activities"]
    busiest = m["busiest_day"]
    busiest_count = m["busiest_count"]

    parts = [f"平均每天安排 {avg} 个活动"]
    if 2 <= avg <= 3:
        parts.append("节奏适中，松紧得当")
    elif avg > 4:
        parts.append("整体偏紧凑，建议适当留出休息时间")
    elif avg < 1.5:
        parts.append("行程较为宽松，可适当增加体验项目")

    text = "，".join(parts) + "。"

    if busiest and busiest_count > 4:
        text += f"其中 Day{busiest} 安排了 {busiest_count} 个活动，略显密集。"

    return text


def _generate_pace_tags(m):
    tags = []
    if 2 <= m["avg_activities"] <= 3:
        tags.append({"type": "positive", "text": "节奏适中"})
    elif m["avg_activities"] > 4:
        tags.append({"type": "warning", "text": "部分天数偏紧"})
    if m["busiest_day"] and m["busiest_count"] > 4:
        tags.append({"type": "warning", "text": f"Day{m['busiest_day']} 偏满"})
    return tags


def _generate_accommodation_text(m):
    if m["coverage"] >= 90:
        cov_text = "住宿记录完整"
    elif m["coverage"] >= 60:
        cov_text = "大部分天数有住宿记录"
    else:
        cov_text = "部分天数缺少住宿信息"

    if m["avg_nightly"] > 0:
        price_text = f"，平均每晚 ¥{m['avg_nightly']}"
        market = m["market_avg"]
        if m["avg_nightly"] < market * 0.8:
            price_text += f"，低于市场均价 ¥{market}，性价比较高"
        elif m["avg_nightly"] > market * 1.2:
            price_text += f"，高于市场均价 ¥{market}"
        else:
            price_text += f"，与市场均价 ¥{market} 相当"
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
    return "。".join(parts) + "。"


def _generate_transport_tags(m):
    tags = []
    if not m["has_backtrack"]:
        tags.append({"type": "positive", "text": "路线合理"})
    else:
        tags.append({"type": "warning", "text": "存在回头路"})
    return tags


def _generate_attractions_text(m):
    cov = m["overall_coverage"]
    if cov >= 85:
        return f"整体景点覆盖率 {cov}%，必去景点基本全面覆盖，行程安排充实。"
    elif cov >= 60:
        return f"整体景点覆盖率 {cov}%，大部分核心景点已包含，部分值得一去的地方有所遗漏。"
    else:
        return f"整体景点覆盖率 {cov}%，较多必去景点未覆盖，建议下次重点补充。"


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
    parts = []
    parts.append(f"{city}停留 {num_days} 天")

    if daily_cost > 0 and market_daily > 0:
        ratio = daily_cost / market_daily
        if ratio < 0.85:
            parts.append(f"日均花费 ¥{round(daily_cost)}，显著低于市场均价")
        elif ratio > 1.15:
            parts.append(f"日均花费 ¥{round(daily_cost)}，略高于市场水平")
        else:
            parts.append(f"日均花费 ¥{round(daily_cost)}，与市场水平持平")

    if covered:
        parts.append(f"已覆盖{', '.join(covered[:4])}等{'核心' if len(covered) >= 3 else ''}景点")
    if missed:
        parts.append(f"遗憾未能前往{', '.join(missed[:3])}")

    typical = bm.get("typical_stay_days", 3)
    if num_days < typical - 1:
        parts.append(f"建议下次至少停留 {typical} 天以获得更完整的体验")

    return "，".join(parts[:3]) + "。" + ("，".join(parts[3:]) + "。" if len(parts) > 3 else "")


def _generate_suggestions(trip, legs, cost_m, pace_m, attractions_m, benchmarks):
    """后续行程建议"""
    suggestions = []
    visited_cities = {leg.get("city", "") for leg in legs}

    # 基于景点遗漏的建议
    for city_data in attractions_m.get("cities", []):
        missed = city_data.get("missed", [])
        city = city_data.get("city", "")
        if len(missed) >= 2:
            suggestions.append(
                f"下次{city}之行可重点补充{', '.join(missed[:3])}等景点"
            )

    # 基于节奏的建议
    if pace_m["avg_activities"] > 4:
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
        "东京": [("箱根", "温泉和富士山景观"), ("�的仓", "经典的古都一日游")],
        "大阪": [("奈良", "可爱的小鹿和古寺"), ("神户", "牛排和港口夜景")],
        "京都": [("奈良", "搭配京都的经典路线"), ("宇治", "抹茶之乡")],
        "首尔": [("釜山", "韩国第二大城市，海景和美食"), ("济州岛", "韩国度假胜地")],
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

def generate_evaluation(trip_dict):
    """
    生成行程评价。
    trip_dict: Trip.to_dict(include_legs=True, include_expenses=True) 的结果
    返回: {"overall_score": int, "evaluation_data": dict}
    """
    benchmarks = _load_benchmarks()
    legs = trip_dict.get("legs", [])
    expenses = trip_dict.get("expenses", [])

    cost_m = _compute_cost_metrics(trip_dict, legs, expenses, benchmarks)
    pace_m = _compute_pace_metrics(legs)
    accom_m = _compute_accommodation_metrics(legs, expenses, benchmarks)
    transport_m = _compute_transport_metrics(legs)
    attractions_m = _compute_attractions_metrics(legs, benchmarks)

    # 加权总分
    overall = _clamp(
        cost_m["score"] * 0.20 +
        pace_m["score"] * 0.20 +
        accom_m["score"] * 0.15 +
        transport_m["score"] * 0.15 +
        attractions_m["score"] * 0.30
    )

    summary = _generate_summary(overall, cost_m, pace_m, attractions_m, legs)

    # 城市维度评价
    cities = []
    for leg in legs:
        city_eval = _evaluate_city(leg, expenses, benchmarks)
        cities.append(city_eval)

    suggestions = _generate_suggestions(trip_dict, legs, cost_m, pace_m, attractions_m, benchmarks)

    evaluation_data = {
        "summary": summary,
        "dimensions": {
            "cost": {
                "score": cost_m["score"],
                "label": "花费性价比",
                "text": _generate_cost_text(cost_m),
                "tags": _generate_cost_tags(cost_m),
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
                "text": _generate_accommodation_text(accom_m),
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
