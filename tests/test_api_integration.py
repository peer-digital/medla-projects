import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.schemas.project import Project, ProjectStatus, ProjectType
from datetime import datetime

client = TestClient(app)

@pytest.fixture
def test_project():
    return Project(
        id="test-1",
        title="Test Vindkraftpark",
        description="Test description",
        status=ProjectStatus.IN_PROGRESS,
        project_type=ProjectType.ENERGY,
        location="Test Location",
        municipality="Test Municipality",
        county="Test County",
        start_date=datetime(2024, 1, 1),
        source="Länsstyrelsen",
        source_url="https://example.com"
    )

@pytest.mark.asyncio
async def test_get_lansstyrelsen_projects_success(test_project):
    """Test successful retrieval of projects"""
    mock_collector = AsyncMock()
    mock_collector.collect.return_value = [test_project]
    
    with patch('app.main.LansstyrelsenCollector', return_value=mock_collector):
        response = client.get("/projects/lansstyrelsen")
        assert response.status_code == 200
        
        data = response.json()
        assert data["source"] == "Länsstyrelsen"
        assert data["total_projects"] == 1
        
        project = data["projects"][0]
        assert project["id"] == "test-1"
        assert project["title"] == "Test Vindkraftpark"
        assert project["project_type"] == "energy"
        assert project["status"] == "in_progress"

@pytest.mark.asyncio
async def test_get_lansstyrelsen_projects_empty():
    """Test handling of empty result set"""
    mock_collector = AsyncMock()
    mock_collector.collect.return_value = []
    
    with patch('app.main.LansstyrelsenCollector', return_value=mock_collector):
        response = client.get("/projects/lansstyrelsen")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_projects"] == 0
        assert data["projects"] == []

@pytest.mark.asyncio
async def test_get_lansstyrelsen_projects_error():
    """Test handling of collector error"""
    mock_collector = AsyncMock()
    mock_collector.collect.side_effect = Exception("Test error")
    
    with patch('app.main.LansstyrelsenCollector', return_value=mock_collector):
        response = client.get("/projects/lansstyrelsen")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to fetch projects from Länsstyrelsen"