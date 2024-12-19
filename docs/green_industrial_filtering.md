# Green Industrial Project Filtering

## Project Overview
This document outlines the next phase of development for the Länsstyrelsen data collector: implementing filtering and classification of green industrial projects.

## Current State
- Complete data collection from all 21 län
- Robust pagination and error handling
- Comprehensive case information retrieval
- API endpoints for flexible querying

## Implementation Goals

### 1. Project Classification System

#### Keywords and Categories
Implement a classification system based on:
- Industry sectors (e.g., manufacturing, energy, infrastructure)
- Green technology indicators (e.g., solar, wind, hydrogen)
- Project scale indicators (e.g., investment amounts, facility size)

#### Example Classification Rules
```python
GREEN_INDUSTRY_KEYWORDS = {
    'energy': [
        'solcell', 'vindkraft', 'vätgas', 'energilagring',
        'förnybar', 'biogas', 'energieffektivisering'
    ],
    'manufacturing': [
        'batterifabrik', 'vätgasproduktion', 'industripark',
        'tillverkningsindustri', 'fossilfri produktion'
    ],
    'infrastructure': [
        'laddinfrastruktur', 'elnät', 'industrispår',
        'logistikcentrum', 'hamnutbyggnad'
    ]
}

PROJECT_SCALE_INDICATORS = [
    'miljoner kronor', 'mkr', 'MSEK',
    'hektar', 'kvadratmeter', 'arbetstillfällen'
]
```

### 2. Status Filtering

#### Active Project Criteria
Define criteria for active projects:
- Current status indicators
- Recent activity thresholds
- Progress tracking markers

#### Implementation Example
```python
ACTIVE_STATUS_MARKERS = [
    'Handläggning',
    'Pågående',
    'Under behandling',
    'Ansökan komplett'
]

EXCLUDED_STATUS_MARKERS = [
    'Avslutat',
    'Avslaget',
    'Återkallat'
]
```

### 3. Data Model Extensions

Add new fields to the Project schema:
```python
class GreenIndustrialProject(Project):
    industry_sector: str
    green_category: List[str]
    investment_amount: Optional[float]
    project_scale: Dict[str, Any]
    environmental_impact: Dict[str, Any]
    employment_impact: Optional[int]
    implementation_timeline: Dict[str, datetime]
```

## API Enhancements

### New Endpoint Parameters
```python
@router.get("/api/v1/projects/green-industrial")
async def get_green_industrial_projects(
    sector: Optional[List[str]] = None,
    min_investment: Optional[float] = None,
    green_category: Optional[List[str]] = None,
    status: Optional[List[str]] = None,
    region: Optional[List[str]] = None
)
```

### Response Format
```json
{
    "source": "Länsstyrelsen",
    "pagination": {
        "current_page": 1,
        "total_pages": 10,
        "total_items": 500
    },
    "projects": [
        {
            "id": "case_number",
            "title": "Project Title",
            "industry_sector": "manufacturing",
            "green_categories": ["battery", "renewable-energy"],
            "investment_amount": 1000000000,
            "location": {
                "municipality": "Skellefteå",
                "county": "Västerbotten"
            },
            "status": "in_progress",
            "timeline": {
                "start_date": "2023-01-01",
                "estimated_completion": "2025-12-31"
            }
        }
    ]
}
```

## Implementation Strategy

### Phase 1: Basic Classification
1. Implement keyword-based classification
2. Add basic status filtering
3. Create new API endpoint

### Phase 2: Enhanced Classification
1. Add investment amount extraction
2. Implement project scale analysis
3. Add environmental impact classification

### Phase 3: Advanced Features
1. Add relationship tracking between projects
2. Implement timeline analysis
3. Add export functionality

## Testing Strategy

### Unit Tests
- Keyword matching accuracy
- Status classification
- Investment amount extraction

### Integration Tests
- API endpoint functionality
- Data model validation
- Classification pipeline

### Validation Tests
- Manual verification of classification accuracy
- False positive/negative analysis
- Edge case handling

## Performance Considerations

### Optimization Points
1. Cache frequently accessed classifications
2. Implement batch processing for large datasets
3. Optimize database queries for filtered searches

### Monitoring Needs
1. Classification accuracy metrics
2. Processing time per request
3. Cache hit/miss rates

## Next Steps

1. **Immediate Actions**
   - Set up classification system structure
   - Implement basic keyword matching
   - Create test dataset for validation

2. **Technical Requirements**
   - Update database schema
   - Implement new API endpoints
   - Set up monitoring system

3. **Documentation Needs**
   - API documentation updates
   - Classification rules documentation
   - Monitoring and maintenance guides 