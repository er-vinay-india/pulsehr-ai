import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.report_generator import generate_pptx_presentation

client = TestClient(app)

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["database"]["employees"] >= 100
    assert data["database"]["hr_alerts"] >= 1

def test_analytics_overview():
    response = client.get("/api/analytics/overview")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    assert data["stats"]["total_employees"] >= 100
    assert "departments" in data
    assert len(data["departments"]) >= 5
    assert "alerts" in data
    assert len(data["alerts"]) >= 1

def test_employees_list_and_filter():
    response = client.get("/api/employees?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 100
    assert len(data["employees"]) == 10

    # Filter by department
    response_dept = client.get("/api/employees?department=Engineering")
    assert response_dept.status_code == 200
    dept_data = response_dept.json()
    assert all(e["department"] == "Engineering" for e in dept_data["employees"])

def test_employee_detail():
    response = client.get("/api/employees/0")
    assert response.status_code == 200
    data = response.json()
    assert "employee" in data
    assert data["employee"]["id"] == 0
    assert "recent_punches" in data

def test_copilot_suggestions():
    response = client.get("/api/copilot/suggestions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["suggestions"]) >= 3

def test_generate_presentation():
    path = generate_pptx_presentation()
    assert path.exists()
    assert path.stat().st_size > 10000

def test_executive_html_report():
    response = client.get("/api/reports/executive-html")
    assert response.status_code == 200
    assert "PulseHR AI" in response.text
    assert "Workforce" in response.text

def test_copilot_exact_entity_citations():
    from app.services.ai_copilot import find_exact_employee_matches, query_copilot
    matches = find_exact_employee_matches("How many days was Sofia Sharma absent?")
    assert len(matches) >= 1
    assert matches[0]["employee"]["name"] == "Sofia Sharma"
    assert matches[0]["employee"]["employee_code"] == "EMP-002"

def test_unrelated_query_no_citation_flood():
    from app.services.ai_copilot import query_copilot
    res = query_copilot("What is 2 + 2?")
    # An unrelated query should not flood 7 citations
    assert len(res["citations"]) == 0
