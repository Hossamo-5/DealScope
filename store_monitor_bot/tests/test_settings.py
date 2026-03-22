"""
Tests for Configuration Settings
===============================
Tests config/settings.py constants and structures
"""

from config.settings import (
    PLAN_LIMITS, SCORE_WEIGHTS, SCAN_INTERVALS, SCORE_LEVELS
)


class TestPlanLimits:
    """Test PLAN_LIMITS structure."""

    def test_plan_limits_has_all_required_keys(self):
        """Test PLAN_LIMITS structure has all required keys."""
        required_plans = ["free", "basic", "professional"]
        required_keys = ["max_products", "max_categories", "max_stores", "price", "scan_interval"]

        for plan in required_plans:
            assert plan in PLAN_LIMITS, f"Plan {plan} missing from PLAN_LIMITS"

            plan_config = PLAN_LIMITS[plan]
            for key in required_keys:
                assert key in plan_config, f"Key {key} missing from plan {plan}"

    def test_plan_limits_free_plan_values(self):
        """Test free plan has expected values."""
        free_plan = PLAN_LIMITS["free"]

        assert free_plan["max_products"] == 3
        assert free_plan["max_categories"] == 0
        assert free_plan["max_stores"] == 0
        assert free_plan["price"] == 0
        assert free_plan["scan_interval"] == 60

    def test_plan_limits_basic_plan_values(self):
        """Test basic plan has expected values."""
        basic_plan = PLAN_LIMITS["basic"]

        assert basic_plan["max_products"] == 50
        assert basic_plan["max_categories"] == 10
        assert basic_plan["max_stores"] == 0
        assert basic_plan["price"] == 10
        assert basic_plan["scan_interval"] == 30

    def test_plan_limits_professional_plan_values(self):
        """Test professional plan has expected values."""
        pro_plan = PLAN_LIMITS["professional"]

        assert pro_plan["max_products"] == 300
        assert pro_plan["max_categories"] == 50
        assert pro_plan["max_stores"] == 20
        assert pro_plan["price"] == 49
        assert pro_plan["scan_interval"] == 15


class TestScoreWeights:
    """Test SCORE_WEIGHTS configuration."""

    def test_score_weights_sum_equals_100(self):
        """Test SCORE_WEIGHTS sum equals 100."""
        total = sum(SCORE_WEIGHTS.values())
        assert total == 100, f"SCORE_WEIGHTS sum is {total}, should be 100"

    def test_score_weights_has_required_keys(self):
        """Test SCORE_WEIGHTS has all required keys."""
        required_keys = [
            "discount_percent", "product_rating", "review_count",
            "stock_availability", "price_history_low"
        ]

        for key in required_keys:
            assert key in SCORE_WEIGHTS, f"Key {key} missing from SCORE_WEIGHTS"

    def test_score_weights_discount_percent(self):
        """Test discount_percent weight."""
        assert SCORE_WEIGHTS["discount_percent"] == 40

    def test_score_weights_product_rating(self):
        """Test product_rating weight."""
        assert SCORE_WEIGHTS["product_rating"] == 20

    def test_score_weights_review_count(self):
        """Test review_count weight."""
        assert SCORE_WEIGHTS["review_count"] == 15

    def test_score_weights_stock_availability(self):
        """Test stock_availability weight."""
        assert SCORE_WEIGHTS["stock_availability"] == 10

    def test_score_weights_price_history_low(self):
        """Test price_history_low weight."""
        assert SCORE_WEIGHTS["price_history_low"] == 15


class TestScanIntervals:
    """Test SCAN_INTERVALS configuration."""

    def test_scan_intervals_ascending_order(self):
        """Test SCAN_INTERVALS are in ascending order (free > basic > professional)."""
        intervals = SCAN_INTERVALS

        assert intervals["free"] >= intervals["basic"], "Free interval should be >= basic"
        assert intervals["basic"] >= intervals["professional"], "Basic interval should be >= professional"

    def test_scan_intervals_values(self):
        """Test SCAN_INTERVALS have expected values."""
        assert SCAN_INTERVALS["free"] == 60
        assert SCAN_INTERVALS["basic"] == 30
        assert SCAN_INTERVALS["professional"] == 15


class TestScoreLevels:
    """Test SCORE_LEVELS configuration."""

    def test_score_levels_has_required_keys(self):
        """Test SCORE_LEVELS has all required keys."""
        required_keys = ["excellent", "good", "normal"]

        for key in required_keys:
            assert key in SCORE_LEVELS, f"Key {key} missing from SCORE_LEVELS"

    def test_score_levels_values(self):
        """Test SCORE_LEVELS have expected values."""
        assert SCORE_LEVELS["excellent"] == 90
        assert SCORE_LEVELS["good"] == 70
        assert SCORE_LEVELS["normal"] == 0

    def test_score_levels_order(self):
        """Test SCORE_LEVELS are in descending order."""
        assert SCORE_LEVELS["excellent"] > SCORE_LEVELS["good"] > SCORE_LEVELS["normal"]