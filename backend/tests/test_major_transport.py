"""测试大交通（国际/城际交通）检测与花费计算排除逻辑"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.evaluator import _is_flight_expense, _compute_cost_metrics


class TestMajorTransportDetection:
    """_is_flight_expense 应识别所有大交通，不仅限于机票关键词"""

    def test_flight_keyword_detected(self):
        assert _is_flight_expense({"category": "交通", "description": "北京到东京机票"}) is True

    def test_airline_keyword_detected(self):
        assert _is_flight_expense({"category": "交通", "description": "南航航班"}) is True

    def test_flight_english_detected(self):
        assert _is_flight_expense({"category": "交通", "description": "AirAsia Flight"}) is True

    def test_intercity_route_with_budget(self):
        """'XX到YY的交通预算' 应被识别为大交通"""
        e = {"category": "交通", "description": "北京到吉隆坡的交通预算 x2", "amount": 7102}
        assert _is_flight_expense(e) is True

    def test_intercity_route_between_cities(self):
        """城际交通 '吉隆坡到兰卡威的交通预算' 应被识别"""
        e = {"category": "交通", "description": "吉隆坡到兰卡威的交通预算 x2", "amount": 2457.6}
        assert _is_flight_expense(e) is True

    def test_local_taxi_not_detected(self):
        """打车应保留为日常交通，不排除"""
        assert _is_flight_expense({"category": "交通", "description": "打车"}) is False

    def test_local_taxi_to_place_not_detected(self):
        """打车到酒店应保留为日常交通"""
        assert _is_flight_expense({"category": "交通", "description": "打车到酒店"}) is False

    def test_grab_not_detected(self):
        assert _is_flight_expense({"category": "交通", "description": "Grab 到机场"}) is False

    def test_metro_not_detected(self):
        assert _is_flight_expense({"category": "交通", "description": "地铁"}) is False

    def test_non_transport_not_detected(self):
        assert _is_flight_expense({"category": "住宿", "description": "北京到上海的酒店"}) is False

    def test_rail_keyword_detected(self):
        """高铁/动车应被识别为城际交通"""
        assert _is_flight_expense({"category": "交通", "description": "京沪高铁"}) is True

    def test_train_ticket_detected(self):
        assert _is_flight_expense({"category": "交通", "description": "火车票"}) is True

    def test_intercity_route_with_transport(self):
        """'A到B交通费' 格式"""
        e = {"category": "交通", "description": "曼谷到清迈交通费"}
        assert _is_flight_expense(e) is True

    def test_intercity_route_with_zhì(self):
        """'A至B' 格式"""
        e = {"category": "交通", "description": "上海至东京"}
        assert _is_flight_expense(e) is True

    def test_airport_to_hotel_not_detected(self):
        """机场到酒店是本地交通"""
        assert _is_flight_expense({"category": "交通", "description": "从机场到酒店"}) is False

    def test_airport_to_downtown_not_detected(self):
        """机场到市区是本地交通"""
        assert _is_flight_expense({"category": "交通", "description": "机场到市区出租车"}) is False

    def test_station_to_hotel_not_detected(self):
        """车站到酒店是本地交通"""
        assert _is_flight_expense({"category": "交通", "description": "车站到酒店"}) is False


class TestCostMetricsExcludesMajorTransport:
    """_compute_cost_metrics 应从日均花费中排除所有大交通"""

    TRIP = {"traveler_count": 1}
    LEGS = [
        {"city": "吉隆坡", "country": "马来西亚",
         "days": [{"date": "2024-02-12"}, {"date": "2024-02-13"}]},
        {"city": "兰卡威", "country": "马来西亚",
         "days": [{"date": "2024-02-14"}, {"date": "2024-02-15"}]},
        {"city": "槟城", "country": "马来西亚",
         "days": [{"date": "2024-02-16"}, {"date": "2024-02-17"}, {"date": "2024-02-18"}]},
    ]
    BENCHMARKS = {
        "吉隆坡": {"avg_daily_cost_cny": 600},
        "兰卡威": {"avg_daily_cost_cny": 600},
        "槟城": {"avg_daily_cost_cny": 550},
    }
    EXPENSES = [
        {"category": "交通", "description": "北京到吉隆坡的交通预算 x2", "amount": 7102.0, "date": "2024-02-12"},
        {"category": "购物", "description": "购物", "amount": 1630.43, "date": "2024-02-12"},
        {"category": "交通", "description": "打车", "amount": 1758.0, "date": "2024-02-12"},
        {"category": "餐饮", "description": "餐饮", "amount": 979.0, "date": "2024-02-12"},
        {"category": "门票", "description": "门票", "amount": 397.0, "date": "2024-02-12"},
        {"category": "住宿", "description": "吉隆坡w酒店", "amount": 1838.51, "date": "2024-02-13"},
        {"category": "交通", "description": "吉隆坡到兰卡威的交通预算 x2", "amount": 2457.6, "date": "2024-02-14"},
        {"category": "住宿", "description": "兰卡威雅乐轩酒店", "amount": 1653.73, "date": "2024-02-14"},
        {"category": "门票", "description": "兰卡威红树林一日游", "amount": 2216.0, "date": "2024-02-15"},
        {"category": "住宿", "description": "槟城万怡酒店", "amount": 834.22, "date": "2024-02-16"},
        {"category": "住宿", "description": "槟城东方大酒店", "amount": 1182.73, "date": "2024-02-17"},
    ]

    def test_major_transport_excluded_from_daily(self):
        """国际+城际交通(¥9559.6)应从日均花费中排除"""
        m = _compute_cost_metrics(self.TRIP, self.LEGS, self.EXPENSES, self.BENCHMARKS)
        expected_ground = 22049.22 - 7102.0 - 2457.6  # 12489.62
        expected_ppd = round(expected_ground / 7)      # 1784
        assert m["per_person_per_day"] == expected_ppd

    def test_flight_cost_includes_all_major_transport(self):
        """flight_cost 应包含国际交通和城际交通的总额"""
        m = _compute_cost_metrics(self.TRIP, self.LEGS, self.EXPENSES, self.BENCHMARKS)
        assert m["flight_cost"] == round(7102.0 + 2457.6)

    def test_total_expense_unchanged(self):
        """总花费不受大交通排除影响"""
        m = _compute_cost_metrics(self.TRIP, self.LEGS, self.EXPENSES, self.BENCHMARKS)
        assert m["total_expense"] == round(22049.22)
