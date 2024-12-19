import pytest
from typing import List
from app.services.data_collectors.base_collector import BaseDataCollector
from app.schemas.project import Project

class TestCollector(BaseDataCollector):
    """Test implementation of BaseDataCollector"""
    
    def __init__(self, should_fail: bool = False):
        super().__init__()
        self.should_fail = should_fail
    
    async def fetch_data(self) -> List[Project]:
        if self.should_fail:
            raise Exception("Test fetch error")
        return ["test data"]
    
    async def clean_data(self, raw_data: any) -> List[Project]:
        if self.should_fail:
            raise Exception("Test clean error")
        return [
            Project(
                id="test-1",
                title="Test Project",
                description="Test Description",
                status="planned",
                project_type="industrial",
                location="Test Location",
                municipality="Test Municipality",
                county="Test County",
                source="Test Source",
                source_url="https://example.com"
            )
        ]

@pytest.fixture
def collector():
    return TestCollector()

@pytest.fixture
def failing_collector():
    return TestCollector(should_fail=True)

@pytest.mark.asyncio
async def test_collect_success(collector):
    """Test successful data collection"""
    projects = await collector.collect()
    assert len(projects) == 1
    assert projects[0].id == "test-1"
    assert projects[0].title == "Test Project"

@pytest.mark.asyncio
async def test_collect_fetch_error(failing_collector):
    """Test handling of fetch error"""
    projects = await failing_collector.collect()
    assert len(projects) == 0

@pytest.mark.asyncio
async def test_collect_clean_error(failing_collector):
    """Test handling of clean error"""
    projects = await failing_collector.collect()
    assert len(projects) == 0

def test_source_name(collector):
    """Test source name generation"""
    assert collector.source_name == "TestCollector" 