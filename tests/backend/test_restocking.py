"""
Tests for restocking API endpoints.
"""
import pytest

from main import restock_orders, RESTOCK_LEAD_TIME_DAYS


@pytest.fixture(autouse=True)
def clear_restock_orders():
    """Reset the in-memory restock order store between tests."""
    restock_orders.clear()
    yield
    restock_orders.clear()


class TestRestockingRecommendations:
    """Test suite for GET /api/restocking/recommendations."""

    def test_get_recommendations_default_budget(self, client):
        """Test getting recommendations with the default budget."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 200

        data = response.json()
        assert "budget" in data
        assert "spent" in data
        assert "remaining" in data
        assert "lead_time_days" in data
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)
        assert data["lead_time_days"] == RESTOCK_LEAD_TIME_DAYS

    def test_recommendation_structure(self, client):
        """Test that each recommendation has the expected fields."""
        response = client.get("/api/restocking/recommendations?budget=500000")
        data = response.json()

        for rec in data["recommendations"]:
            assert "sku" in rec
            assert "name" in rec
            assert "category" in rec
            assert "warehouse" in rec
            assert isinstance(rec["quantity_on_hand"], int)
            assert isinstance(rec["reorder_point"], int)
            assert isinstance(rec["recommended_quantity"], int)
            assert isinstance(rec["unit_cost"], (int, float))
            assert isinstance(rec["line_cost"], (int, float))
            assert isinstance(rec["urgency"], (int, float))

    def test_recommendations_only_below_reorder_point(self, client):
        """Test that only items at or below reorder point are recommended."""
        response = client.get("/api/restocking/recommendations?budget=500000")
        data = response.json()

        for rec in data["recommendations"]:
            assert rec["quantity_on_hand"] <= rec["reorder_point"]

    def test_recommendations_sorted_by_urgency(self, client):
        """Test that recommendations are sorted most-urgent first."""
        response = client.get("/api/restocking/recommendations?budget=500000")
        data = response.json()

        urgencies = [rec["urgency"] for rec in data["recommendations"]]
        assert urgencies == sorted(urgencies, reverse=True)

    def test_recommendations_fit_budget(self, client):
        """Test that total line cost never exceeds the budget."""
        budget = 5000
        response = client.get(f"/api/restocking/recommendations?budget={budget}")
        data = response.json()

        total = sum(rec["line_cost"] for rec in data["recommendations"])
        assert total <= budget
        assert abs(data["spent"] - total) < 0.01
        assert abs(data["remaining"] - (budget - total)) < 0.01

    def test_line_cost_calculation(self, client):
        """Test that line_cost = recommended_quantity * unit_cost."""
        response = client.get("/api/restocking/recommendations?budget=500000")
        data = response.json()

        for rec in data["recommendations"]:
            expected = rec["recommended_quantity"] * rec["unit_cost"]
            assert abs(rec["line_cost"] - expected) < 0.01


class TestRestockingOrders:
    """Test suite for POST/GET /api/restocking/orders."""

    def _sample_line(self):
        return {
            "sku": "PSU-508",
            "name": "Battery Backup Power Supply",
            "category": "Power Supplies",
            "quantity": 25,
            "unit_cost": 185.5,
            "line_cost": 4637.5,
        }

    def test_get_orders_empty(self, client):
        """Test that the order list is empty initially."""
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_order_success(self, client):
        """Test creating a restock order returns 201 with full payload."""
        body = {"budget": 100000, "items": [self._sample_line()]}
        response = client.post("/api/restocking/orders", json=body)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["lead_time_days"] == RESTOCK_LEAD_TIME_DAYS
        assert order["order_number"].startswith("RST-")
        assert abs(order["total_value"] - 4637.5) < 0.01
        assert len(order["items"]) == 1
        assert "expected_delivery" in order
        assert "created_date" in order

    def test_create_order_rejects_empty_items(self, client):
        """Test that an order with no items is rejected."""
        response = client.post(
            "/api/restocking/orders", json={"budget": 100000, "items": []}
        )
        assert response.status_code == 400
        assert "at least one item" in response.json()["detail"].lower()

    def test_create_order_rejects_over_budget(self, client):
        """Test that an order exceeding budget is rejected."""
        line = self._sample_line()
        response = client.post(
            "/api/restocking/orders", json={"budget": 1000, "items": [line]}
        )
        assert response.status_code == 400
        assert "budget" in response.json()["detail"].lower()

    def test_created_order_appears_in_list(self, client):
        """Test that a created order appears in GET /api/restocking/orders."""
        body = {"budget": 100000, "items": [self._sample_line()]}
        created = client.post("/api/restocking/orders", json=body).json()

        listed = client.get("/api/restocking/orders").json()
        assert len(listed) == 1
        assert listed[0]["id"] == created["id"]
        assert listed[0]["order_number"] == created["order_number"]

    def test_orders_listed_newest_first(self, client):
        """Test that the list endpoint returns newest orders first."""
        body = {"budget": 100000, "items": [self._sample_line()]}
        first = client.post("/api/restocking/orders", json=body).json()
        second = client.post("/api/restocking/orders", json=body).json()

        listed = client.get("/api/restocking/orders").json()
        assert [o["id"] for o in listed] == [second["id"], first["id"]]
