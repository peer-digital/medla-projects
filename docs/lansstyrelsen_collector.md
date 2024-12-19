# Länsstyrelsen Data Collector

## Overview
The Länsstyrelsen collector is responsible for fetching cases from Länsstyrelsen's diarium using their serialized query system. This document outlines the current implementation, known issues, and future improvements.

## Current Status
The collector successfully:
1. Connects to all 21 län using their specific serialized queries
2. Parses HTML responses into structured data
3. Handles pagination with proper total item counts
4. Implements robust session management and error handling
5. Provides detailed case information including IDs, titles, dates, and locations

## Implementation Details

### Features
- **Complete Coverage**: All 21 Swedish län implemented
- **Robust Session Handling**: Automatic session reset between requests
- **Error Recovery**: Retry logic for transient failures
- **Pagination**: Support for browsing large result sets
- **Data Validation**: Comprehensive validation of parsed data

### Län Support
The collector supports all Swedish län:
- Blekinge
- Dalarna
- Gotland
- Gävleborg
- Halland
- Jämtland
- Jönköping
- Kalmar
- Kronoberg
- Norrbotten
- Skåne
- Stockholm
- Södermanland
- Uppsala
- Värmland
- Västerbotten
- Västernorrland
- Västmanland
- Västra Götaland
- Örebro
- Östergötland

## API Usage

### Endpoint Parameters
- `from_date`: Start date in format YYYY-MM-DD (optional)
- `to_date`: End date in format YYYY-MM-DD (optional)
- `lan`: List of län names to search in (optional)
- `page`: Page number for pagination (optional, defaults to 1)

### Example Requests
```bash
# Basic request for a specific län
curl "http://localhost:8000/api/v1/projects/lansstyrelsen?lan=Stockholm"

# Request with pagination
curl "http://localhost:8000/api/v1/projects/lansstyrelsen?lan=Västra%20Götaland&page=2"

# Request with date filtering
curl "http://localhost:8000/api/v1/projects/lansstyrelsen?from_date=2023-01-01&to_date=2023-12-31"
```

### Response Format
```json
{
    "source": "Länsstyrelsen",
    "pagination": {
        "current_page": 1,
        "total_pages": 100,
        "total_items": 5000,
        "items_per_page": 50,
        "has_next": true,
        "has_previous": false
    },
    "projects": [
        {
            "id": "case_number",
            "title": "case_title",
            "date": "case_date",
            "location": "case_location",
            "municipality": "case_municipality",
            "status": "case_status",
            "url": "case_url"
        }
    ]
}
```

## Next Phase: Green Industrial Project Filtering

The next phase of development will focus on identifying and filtering active green industrial projects. This will involve:

1. **Project Classification**
   - Implementing keyword-based filtering
   - Categorizing projects by type (industrial, energy, infrastructure)
   - Identifying green/sustainable initiatives

2. **Status Filtering**
   - Focusing on active and planned projects
   - Excluding completed or rejected cases
   - Tracking project progression

3. **Data Enrichment**
   - Adding industry sector classification
   - Including investment amounts when available
   - Linking related projects

4. **Search Optimization**
   - Creating specialized queries for green industrial projects
   - Implementing advanced filtering options
   - Optimizing response times for filtered queries

## Current Limitations
1. Basic text-based search without semantic understanding
2. No automatic classification of project types
3. Limited metadata for filtering green initiatives

## Future Improvements

### High Priority
1. Implement green industrial project classification
2. Add industry sector categorization
3. Create specialized search queries for green projects

### Medium Priority
4. Implement caching for frequently accessed data
5. Add advanced filtering options
6. Improve search performance

### Low Priority
7. Add project relationship tracking
8. Implement trend analysis
9. Add export functionality for filtered datasets