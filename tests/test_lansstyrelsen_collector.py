import pytest
from datetime import datetime
import aiohttp
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector
from app.schemas.project import ProjectType, ProjectStatus

@pytest.fixture
def collector():
    return LansstyrelsenCollector()

@pytest.fixture
def sample_html():
    return """
    <table id="SearchPlaceHolder_caseGridView">
        <tr>
            <th>Diarienummer</th>
            <th>Status</th>
            <th>In/Upp-datum</th>
            <th>Ärenderubrik</th>
            <th>Avsändare/mottagare</th>
            <th>Postort</th>
            <th>Kommun</th>
            <th>Beslutsdatum</th>
        </tr>
        <tr>
            <td><a href="CaseInfo.aspx?caseID=4668238">831-2024</a></td>
            <td>Handläggning</td>
            <td>2024-02-08</td>
            <td>Ansökan om tillstånd för vindkraftparken Cirrus</td>
            <td>Regeringskansliet</td>
            <td>Stockholm</td>
            <td>Karlskrona</td>
            <td>2024-08-01</td>
        </tr>
    </table>
    """

@pytest.fixture
def malformed_html():
    return """
    <table id="SearchPlaceHolder_caseGridView">
        <tr>
            <th>Incomplete Header</th>
        </tr>
        <tr>
            <td>Incomplete Data</td>
        </tr>
    </table>
    """

@pytest.fixture
def empty_html():
    return """
    <table id="SearchPlaceHolder_caseGridView">
        <tr>
            <th>Diarienummer</th>
            <th>Status</th>
            <th>In/Upp-datum</th>
            <th>Ärenderubrik</th>
            <th>Avsändare/mottagare</th>
            <th>Postort</th>
            <th>Kommun</th>
            <th>Beslutsdatum</th>
        </tr>
    </table>
    """

@pytest.mark.asyncio
async def test_clean_data(collector, sample_html):
    projects = await collector.clean_data(sample_html)
    assert len(projects) == 1
    project = projects[0]
    
    assert project.id == "831-2024"
    assert project.status == ProjectStatus.IN_PROGRESS
    assert project.project_type == ProjectType.ENERGY
    assert "vindkraftparken" in project.title.lower()
    assert project.municipality == "Karlskrona"
    assert project.county == "Blekinge"
    assert project.source_url == "https://diarium.lansstyrelsen.se/Case/CaseInfo.aspx?caseID=4668238"

@pytest.mark.asyncio
async def test_clean_data_malformed(collector, malformed_html):
    """Test handling of malformed HTML"""
    projects = await collector.clean_data(malformed_html)
    assert len(projects) == 0

@pytest.mark.asyncio
async def test_clean_data_empty(collector, empty_html):
    """Test handling of empty result set"""
    projects = await collector.clean_data(empty_html)
    assert len(projects) == 0

@pytest.mark.asyncio
async def test_clean_data_invalid_html(collector):
    """Test handling of invalid HTML"""
    projects = await collector.clean_data("Not HTML")
    assert len(projects) == 0

@pytest.mark.asyncio
async def test_fetch_data_success(collector):
    """Test successful API fetch"""
    mock_response = AsyncMock()
    mock_response.text = AsyncMock(return_value="Sample HTML")
    
    with patch('aiohttp.ClientSession.get', return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_response)
    )):
        result = await collector.fetch_data()
        assert result == "Sample HTML"

@pytest.mark.asyncio
async def test_fetch_data_network_error(collector):
    """Test handling of network error"""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = aiohttp.ClientError()
        
        with pytest.raises(aiohttp.ClientError):
            await collector.fetch_data()

def test_determine_project_type(collector):
    assert collector._determine_project_type("Vindkraftpark") == ProjectType.ENERGY
    assert collector._determine_project_type("Batterifabrik") == ProjectType.INDUSTRIAL
    assert collector._determine_project_type("Vägbygge") == ProjectType.INFRASTRUCTURE
    assert collector._determine_project_type("Annat") == ProjectType.OTHER
    
    # Edge cases
    assert collector._determine_project_type("") == ProjectType.OTHER
    assert collector._determine_project_type("VINDKRAFT") == ProjectType.ENERGY  # Case insensitive
    assert collector._determine_project_type("Industri och energi") == ProjectType.INDUSTRIAL  # Multiple keywords

def test_determine_project_status(collector):
    assert collector._determine_project_status("Avslutat") == ProjectStatus.COMPLETED
    assert collector._determine_project_status("Handläggning") == ProjectStatus.IN_PROGRESS
    assert collector._determine_project_status("Annat") == ProjectStatus.PLANNED
    assert collector._determine_project_status("Beslut om avslag") == ProjectStatus.REJECTED
    assert collector._determine_project_status("Ansökan avslagen") == ProjectStatus.REJECTED
    
    # Edge cases
    assert collector._determine_project_status("") == ProjectStatus.PLANNED
    assert collector._determine_project_status("AVSLUTAT") == ProjectStatus.COMPLETED  # Case insensitive
    assert collector._determine_project_status(None) == ProjectStatus.PLANNED  # None handling
    assert collector._determine_project_status("AVSLAG") == ProjectStatus.REJECTED  # Case insensitive

def test_is_relevant_project(collector):
    assert collector._is_relevant_project("Vindkraftpark etablering")
    assert collector._is_relevant_project("Batterifabrik tillstånd")
    assert collector._is_relevant_project("Miljöfarlig verksamhet industri")
    assert not collector._is_relevant_project("Vanlig bygglovsansökan")
    
    # Edge cases
    assert not collector._is_relevant_project("")  # Empty string
    assert not collector._is_relevant_project(None)  # None handling
    assert collector._is_relevant_project("VINDKRAFT")  # Case insensitive
    assert collector._is_relevant_project("Industri-anläggning")  # Hyphenated words

def test_parse_date(collector):
    assert collector._parse_date("2024-02-08") == datetime(2024, 2, 8)
    assert collector._parse_date("&nbsp;") is None
    assert collector._parse_date("") is None
    assert collector._parse_date("invalid-date") is None
    
    # Edge cases
    assert collector._parse_date(None) is None
    assert collector._parse_date("2024-13-01") is None  # Invalid month
    assert collector._parse_date("2024-01-32") is None  # Invalid day