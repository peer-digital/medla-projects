# Swedish Green Industrial Projects Tracker

This service collects and presents active green industrial construction projects in Sweden. It aggregates data from multiple sources:

- Länsstyrelserna (County Administrative Boards)
- Trafikverket (Swedish Transport Administration)
- Kommunala översiktsplaner (Municipal comprehensive plans)
- Press releases

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Unix/macOS
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the development server:
```bash
uvicorn app.main:app --reload
```

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models/             # Database models
│   ├── schemas/            # Pydantic models
│   ├── services/           # Business logic
│   │   └── data_collectors/  # Data collection from different sources
│   └── api/                # API endpoints
├── tests/                  # Test files
├── requirements.txt        # Project dependencies
└── README.md              # This file
``` 