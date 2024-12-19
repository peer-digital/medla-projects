from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict
from app.models.database import get_db
from app.services.categorization import CategorizationService
from app.models.models import Case
import os
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
import asyncio
import json
from typing import AsyncGenerator

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file")

router = APIRouter()
categorization_service = CategorizationService(api_key=api_key)

async def progress_generator(db: Session, batch_size: int = 50, min_confidence: float = 0.7) -> AsyncGenerator[str, None]:
    """Generate SSE events for batch categorization progress."""
    try:
        for progress in categorization_service.batch_categorize_with_progress(db, batch_size, min_confidence):
            # Convert the progress dict to a JSON string
            yield f"data: {json.dumps(progress)}\n\n"
            await asyncio.sleep(0.1)  # Small delay to prevent overwhelming the client
    except Exception as e:
        error_data = {
            "status": "error",
            "message": str(e)
        }
        yield f"data: {json.dumps(error_data)}\n\n"

@router.get("/categorize/batch/stream")
async def stream_batch_categorize(
    batch_size: int = 50,
    min_confidence: float = 0.7,
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """Stream batch categorization progress."""
    return StreamingResponse(
        progress_generator(db, batch_size, min_confidence),
        media_type="text/event-stream"
    )

@router.post("/categorize/batch")
def batch_categorize(
    batch_size: int = 50,
    min_confidence: float = 0.7,
    db: Session = Depends(get_db)
) -> Dict:
    """Process a batch of cases for categorization."""
    try:
        results = categorization_service.batch_categorize(
            db=db,
            batch_size=batch_size,
            min_confidence=min_confidence
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during batch categorization: {str(e)}")

@router.post("/categorize/{case_id}")
def categorize_single_case(
    case_id: str,
    db: Session = Depends(get_db)
) -> Dict:
    """Categorize a single case by ID."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    try:
        updated_case = categorization_service.update_case_categorization(db, case)
        return {
            "id": updated_case.id,
            "primary_category": updated_case.primary_category,
            "sub_category": updated_case.sub_category,
            "confidence": updated_case.category_confidence,
            "metadata": updated_case.category_metadata
        }
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error categorizing case: {str(e)}") 