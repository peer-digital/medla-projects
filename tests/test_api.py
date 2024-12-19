from fastapi.testclient import TestClient
import pytest
from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Swedish Green Industrial Projects API"
    assert data["version"] == "0.1.0"
    assert data["status"] == "operational"

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"} 