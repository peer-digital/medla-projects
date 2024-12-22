from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict
from app.models.database import get_db
from app.models.models import Case
from app.services.categorization import CategorizationService
import json
import asyncio
from typing import AsyncGenerator

router = APIRouter()
categorization_service = CategorizationService()

async def stream_progress(db: Session) -> AsyncGenerator[str, None]:
    """Stream progress updates as SSE events."""
    try:
        async for progress in categorization_service.batch_categorize_with_progress(db):
            # Ensure all fields are properly initialized
            progress_data = {
                "processed": progress.get("processed", 0),
                "successful": progress.get("successful", 0),
                "failed": progress.get("failed", 0),
                "total_cases": progress.get("total_cases", 0),
                "status": progress.get("status", "in_progress"),
                "progress_percentage": progress.get("progress_percentage", 0),
                "categories": progress.get("categories", {}),
                "errors": progress.get("errors", []),
                "estimated_time_remaining": progress.get("estimated_time_remaining")
            }
            
            yield f"data: {json.dumps(progress_data)}\n\n"
            await asyncio.sleep(0.1)  # Small delay to prevent overwhelming the client
            
    except Exception as e:
        error_data = {
            "status": "failed",
            "error": str(e),
            "progress_percentage": 0
        }
        yield f"data: {json.dumps(error_data)}\n\n"

@router.get("/batch/stream")
async def stream_batch_categorization(
    batch_size: int = 50,
    min_confidence: float = 0.7,
    db: Session = Depends(get_db)
):
    """Stream batch categorization progress as Server-Sent Events."""
    return StreamingResponse(
        stream_progress(db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/{case_id}")
async def categorize_case(case_id: str, db: Session = Depends(get_db)):
    """Categorize a single case."""
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        updated_case = await categorization_service.categorize_case(case)
        db.commit()
        
        return {"status": "success", "case_id": case_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch")
async def batch_categorize(
    batch_size: int = 50,
    min_confidence: float = 0.7,
    db: Session = Depends(get_db)
) -> Dict:
    """Process a batch of cases for categorization."""
    try:
        results = await categorization_service.batch_categorize(
            db=db,
            batch_size=batch_size,
            min_confidence=min_confidence
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during batch categorization: {str(e)}") 