from fastapi import APIRouter, Query, HTTPException, BackgroundTasks, Depends, Request
from typing import List, Optional, Dict
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector
from app.schemas.project import ProjectResponse
from app.models.database import get_db, engine, Base
from app.models.models import Case, Bookmark
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from fastapi.templating import Jinja2Templates
import logging
import asyncio
import time
from collections import defaultdict
from app.utils.date_utils import parse_date

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Rate limiting setup
RATE_LIMIT_DURATION = 60  # seconds
MAX_REQUESTS = 5  # requests per duration
rate_limit_store = defaultdict(list)  # IP -> list of timestamps

# Task tracking
background_tasks_status: Dict[str, Dict] = {}

async def fetch_case_details_background(case_id: str, db: Session):
    """Background task to fetch case details"""
    collector = LansstyrelsenCollector()
    
    # Get the case
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return
    
    try:
        # Update attempt counter and timestamp
        case.details_fetch_attempts += 1
        case.last_fetch_attempt = datetime.now()
        db.commit()  # Commit the attempt update immediately
        
        # Fetch details
        details = await collector.fetch_case_details(case_id)
        
        if details:
            # Update case with details
            case.sender = details.get('sender')
            if details.get('decision_date'):
                try:
                    case.decision_date = datetime.strptime(details['decision_date'], '%Y-%m-%d')
                except ValueError:
                    case.decision_date = None
            case.decision_summary = details.get('decision_summary')
            case.case_type = details.get('case_type')
            case.documents = details.get('documents', [])
            case.details_fetched = True
            db.commit()
        else:
            # If details fetch failed but didn't raise an exception
            logger.warning(f"No details returned for case {case_id}")
            if case.details_fetch_attempts < 5:
                # Reset the attempt counter to allow future retries
                case.details_fetch_attempts -= 1
                db.commit()
    
    except Exception as e:
        logger.error(f"Error fetching case {case_id} (attempt {case.details_fetch_attempts}/5): {str(e)}")
        if case.details_fetch_attempts < 5:
            # Reset the attempt counter to allow future retries
            case.details_fetch_attempts -= 1
            db.commit()

def check_rate_limit(ip: str):
    now = time.time()
    # Remove old timestamps
    rate_limit_store[ip] = [ts for ts in rate_limit_store[ip] if now - ts < RATE_LIMIT_DURATION]
    
    if len(rate_limit_store[ip]) >= MAX_REQUESTS:
        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {RATE_LIMIT_DURATION} seconds."
        )
    
    rate_limit_store[ip].append(now)

def track_task_progress(task_id: str, total: int = 0):
    background_tasks_status[task_id] = {
        "status": "running",
        "progress": 0,
        "total": total,
        "message": "Task started",
        "errors": [],
        "start_time": datetime.now().isoformat(),
        "end_time": None
    }
    return background_tasks_status[task_id]

def update_task_progress(task_id: str, progress: int, message: str = None, error: str = None):
    if task_id in background_tasks_status:
        background_tasks_status[task_id]["progress"] = progress
        if message:
            background_tasks_status[task_id]["message"] = message
        if error:
            background_tasks_status[task_id]["errors"].append({
                "time": datetime.now().isoformat(),
                "error": error
            })

def complete_task(task_id: str, success: bool = True, message: str = None):
    if task_id in background_tasks_status:
        background_tasks_status[task_id].update({
            "status": "completed" if success else "failed",
            "end_time": datetime.now().isoformat(),
            "message": message or background_tasks_status[task_id]["message"]
        })

@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a background task"""
    if task_id not in background_tasks_status:
        raise HTTPException(status_code=404, detail="Task not found")
    return background_tasks_status[task_id]

@router.post("/admin/reset-database")
async def reset_database(request: Request):
    """Reset the database by dropping all tables and recreating them"""
    check_rate_limit(request.client.host)
    task_id = f"reset_db_{int(time.time())}"
    task_status = track_task_progress(task_id)
    
    try:
        logger.info("Dropping all tables...")
        update_task_progress(task_id, 33, "Dropping tables...")
        Base.metadata.drop_all(bind=engine)
        
        logger.info("Recreating all tables...")
        update_task_progress(task_id, 66, "Recreating tables...")
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database reset completed successfully")
        complete_task(task_id, True, "Database reset completed successfully")
        return {"status": "success", "message": "Database reset completed successfully", "task_id": task_id}
    except Exception as e:
        error_msg = f"Error resetting database: {str(e)}"
        logger.error(error_msg)
        complete_task(task_id, False, error_msg)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )

@router.post("/admin/fetch-all-cases")
async def fetch_all_cases(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Fetch cases from all län in the background"""
    check_rate_limit(request.client.host)
    task_id = f"fetch_cases_{int(time.time())}"
    
    try:
        collector = LansstyrelsenCollector()
        lan_list = list(collector.lan_queries.keys())
        task_status = track_task_progress(task_id, len(lan_list))
        
        async def fetch_cases_background():
            total_cases = 0
            processed_lan = 0
            
            for lan in lan_list:
                try:
                    update_task_progress(
                        task_id,
                        int((processed_lan / len(lan_list)) * 100),
                        f"Fetching cases for {lan}..."
                    )
                    
                    cases = await collector.fetch_data(
                        from_date=(datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"),
                        to_date=datetime.now().strftime("%Y-%m-%d"),
                        lan=[lan]
                    )
                    
                    new_cases = 0
                    for case_data in cases.get("projects", []):
                        if not db.query(Case).filter(Case.id == case_data["id"]).first():
                            # Parse all date fields
                            date_fields = [
                                'date',
                                'decision_date',
                                'last_fetch_attempt',
                                'last_categorized_at',
                                'updated_at'
                            ]
                            
                            for field in date_fields:
                                if field in case_data:
                                    case_data[field] = parse_date(case_data[field])
                            
                            case = Case(**case_data)
                            db.add(case)
                            new_cases += 1
                    
                    db.commit()
                    total_cases += new_cases
                    processed_lan += 1
                    
                    update_task_progress(
                        task_id,
                        int((processed_lan / len(lan_list)) * 100),
                        f"Added {new_cases} new cases from {lan}"
                    )
                    
                except Exception as e:
                    error_msg = f"Error fetching cases for {lan}: {str(e)}"
                    logger.error(error_msg)
                    update_task_progress(task_id, None, error=error_msg)
                    db.rollback()
                    continue
            
            complete_task(
                task_id,
                True,
                f"Completed fetching all cases. Added {total_cases} new cases in total."
            )
        
        background_tasks.add_task(fetch_cases_background)
        return {
            "status": "started",
            "message": "Case fetching started in background",
            "task_id": task_id
        }
    
    except Exception as e:
        error_msg = f"Error starting case fetch: {str(e)}"
        logger.error(error_msg)
        complete_task(task_id, False, error_msg)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )

@router.post("/admin/fetch-bookmarked-details")
async def fetch_bookmarked_details(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Fetch details for all bookmarked cases in the background"""
    check_rate_limit(request.client.host)
    task_id = f"fetch_details_{int(time.time())}"
    
    try:
        bookmarked_cases = db.query(Case).join(Bookmark).filter(
            (Case.details_fetched == False) | 
            (Case.details_fetched == None)
        ).all()
        
        if not bookmarked_cases:
            return {
                "status": "skipped",
                "message": "No bookmarked cases found that need details",
                "task_id": task_id
            }
        
        task_status = track_task_progress(task_id, len(bookmarked_cases))
        
        async def fetch_details_background():
            collector = LansstyrelsenCollector()
            processed_cases = 0
            
            for case in bookmarked_cases:
                try:
                    update_task_progress(
                        task_id,
                        int((processed_cases / len(bookmarked_cases)) * 100),
                        f"Fetching details for case {case.id}..."
                    )
                    
                    details = await collector.fetch_case_details(case.id, case.case_id)
                    
                    if details:
                        case.sender = details.get('sender')
                        if details.get('decision_date'):
                            try:
                                case.decision_date = datetime.strptime(details['decision_date'], '%Y-%m-%d')
                            except ValueError:
                                case.decision_date = None
                        case.decision_summary = details.get('decision_summary')
                        case.case_type = details.get('case_type')
                        case.documents = details.get('documents', [])
                        case.details_fetched = True
                        case.details_fetch_attempts += 1
                        case.last_fetch_attempt = datetime.now()
                        
                        db.commit()
                        processed_cases += 1
                        update_task_progress(
                            task_id,
                            int((processed_cases / len(bookmarked_cases)) * 100),
                            f"Updated details for case {case.id}"
                        )
                    else:
                        error_msg = f"No details found for case {case.id}"
                        logger.warning(error_msg)
                        update_task_progress(task_id, None, error=error_msg)
                        case.details_fetch_attempts += 1
                        case.last_fetch_attempt = datetime.now()
                        db.commit()
                    
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    error_msg = f"Error fetching details for case {case.id}: {str(e)}"
                    logger.error(error_msg)
                    update_task_progress(task_id, None, error=error_msg)
                    case.details_fetch_attempts += 1
                    case.last_fetch_attempt = datetime.now()
                    db.commit()
                    continue
            
            complete_task(
                task_id,
                True,
                f"Completed fetching details for {processed_cases} out of {len(bookmarked_cases)} cases"
            )
        
        background_tasks.add_task(fetch_details_background)
        return {
            "status": "started",
            "message": f"Started fetching details for {len(bookmarked_cases)} bookmarked cases",
            "task_id": task_id
        }
    
    except Exception as e:
        error_msg = f"Error starting bookmarked details fetch: {str(e)}"
        logger.error(error_msg)
        complete_task(task_id, False, error_msg)
        raise HTTPException(
            status_code=500,
            detail=error_msg
        ) 

@router.post("/cases/{case_id}/fetch-details")
async def fetch_case_details(
    case_id: str,
    db: Session = Depends(get_db)
):
    """Fetch additional details for a specific case"""
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        collector = LansstyrelsenCollector()
        details = await collector.fetch_case_details(case.id, case.case_id)
        
        if details:
            case.sender = details.get('sender')
            case.decision_date = parse_date(details.get('decision_date'))
            case.decision_summary = details.get('decision_summary')
            case.case_type = details.get('case_type')
            case.documents = details.get('documents')
            case.details_fetched = True
            case.last_fetch_attempt = datetime.now()
            
            db.commit()
            return {"status": "success", "message": "Case details updated"}
        else:
            case.details_fetch_attempts += 1
            case.last_fetch_attempt = datetime.now()
            db.commit()
            return {"status": "error", "message": "No details found"}
    
    except Exception as e:
        logger.error(f"Error fetching case details: {str(e)}")
        case.details_fetch_attempts += 1
        case.last_fetch_attempt = datetime.now()
        db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching case details: {str(e)}"
        ) 