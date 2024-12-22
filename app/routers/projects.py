from fastapi import APIRouter, Query, HTTPException, BackgroundTasks, Depends, Request
from typing import List, Optional, Dict
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector
from app.schemas.project import ProjectResponse
from app.models.database import get_db, engine, Base
from app.models.models import Case, Bookmark, FetchStatus
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from fastapi.templating import Jinja2Templates
import logging
import asyncio
import time
from collections import defaultdict
from app.utils.date_utils import parse_date
import json
from fastapi.responses import StreamingResponse
import random

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
        "progress_percentage": 0,
        "total": total,
        "total_cases": 0,
        "processed_cases": 0,
        "message": "Task started",
        "errors": [],
        "start_time": datetime.now().isoformat(),
        "end_time": None
    }
    return background_tasks_status[task_id]

def update_task_progress(task_id: str, progress: int, message: str = None, error: str = None, total: int = None, processed: int = None):
    if task_id in background_tasks_status:
        background_tasks_status[task_id]["progress"] = progress
        background_tasks_status[task_id]["progress_percentage"] = progress
        if message:
            background_tasks_status[task_id]["message"] = message
        if error:
            background_tasks_status[task_id]["errors"].append({
                "time": datetime.now().isoformat(),
                "error": error
            })
        if total is not None:
            background_tasks_status[task_id]["total"] = total
            background_tasks_status[task_id]["total_cases"] = total
        if processed is not None:
            background_tasks_status[task_id]["processed"] = processed
            background_tasks_status[task_id]["processed_cases"] = processed

def complete_task(task_id: str, success: bool = True, message: str = None):
    if task_id in background_tasks_status:
        background_tasks_status[task_id].update({
            "status": "completed" if success else "failed",
            "end_time": datetime.now().isoformat(),
            "message": message or background_tasks_status[task_id]["message"]
        })

@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a background task using Server-Sent Events"""
    if task_id not in background_tasks_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    async def event_generator():
        while True:
            if task_id not in background_tasks_status:
                break
            
            data = background_tasks_status[task_id]
            # Ensure we have all required fields for the frontend
            if "progress_percentage" not in data:
                data["progress_percentage"] = data.get("progress", 0)
            if "total_cases" not in data:
                data["total_cases"] = data.get("total", 0)
            if "processed_cases" not in data:
                data["processed_cases"] = data.get("processed", 0)
            
            yield f"data: {json.dumps(data)}\n\n"
            
            # If task is completed or failed, stop sending events
            if data.get("status") in ["completed", "failed"]:
                break
            
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

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

@router.post("/admin/fetch-cases")
async def fetch_cases(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Fetch cases, continuing from where we left off or checking for updates"""
    check_rate_limit(request.client.host)
    task_id = f"fetch_cases_{int(time.time())}"
    
    try:
        collector = LansstyrelsenCollector()
        lan_list = list(collector.lan_queries.keys())
        task_status = track_task_progress(task_id)
        
        async def fetch_cases_background():
            total_processed = 0
            current_batch = []
            
            # Get fetch status for all län
            fetch_statuses = {status.lan: status for status in db.query(FetchStatus).all()}
            
            # First, handle län that haven't completed their initial fetch
            incomplete_lan = []
            lan_page_info = {}  # Cache for län page information
            
            for lan in lan_list:
                status = fetch_statuses.get(lan)
                try:
                    # Check if län is incomplete (never fetched or has more pages)
                    if not status or status.last_successful_fetch is None:
                        incomplete_lan.append((lan, status))
                        # Fetch page info for estimation
                        result = await collector.fetch_data(lan, page=1)
                        if result and result.get('pagination'):
                            lan_page_info[lan] = result['pagination']
                        continue
                    
                    # Check if we have more pages to fetch for this län
                    result = await collector.fetch_data(lan, page=1)
                    if result and result.get('pagination'):
                        lan_page_info[lan] = result['pagination']
                        total_pages = result['pagination'].get('total_pages', 1)
                        if status.last_page_fetched < total_pages:
                            incomplete_lan.append((lan, status))
                except Exception as e:
                    logger.error(f"Error checking status for {lan}: {str(e)}")
                    if not status or status.last_successful_fetch is None:
                        incomplete_lan.append((lan, status))
            
            # Sort incomplete län to prioritize those that were interrupted mid-fetch
            incomplete_lan.sort(key=lambda x: (
                0 if x[1] and x[1].last_page_fetched else 1,  # Prioritize län that were interrupted
                x[1].last_page_fetched if x[1] else 0,  # Then by how many pages were already fetched
                x[0]  # Then alphabetically by län name
            ))
            
            # Estimate total cases using cached page info
            total_cases = 0
            for lan, status in incomplete_lan:
                if lan in lan_page_info:
                    total_pages = lan_page_info[lan].get('total_pages', 1)
                    fetched_pages = status.last_page_fetched if status else 0
                    remaining_pages = total_pages - fetched_pages
                    total_cases += remaining_pages * 50
            
            # Update task with estimated total
            update_task_progress(
                task_id,
                0,
                "Starting fetch...",
                total=total_cases,
                processed=0
            )
            
            if incomplete_lan:
                # Continue fetching incomplete län
                for lan, status in incomplete_lan:
                    try:
                        start_page = (status.last_page_fetched + 1) if status else 1
                        current_page = start_page
                        
                        logger.info(f"Continuing fetch for {lan} from page {start_page}")
                        
                        while True:
                            # Update progress
                            update_task_progress(
                                task_id,
                                (total_processed * 100) // total_cases if total_cases > 0 else 0,
                                f"Fetching page {current_page} for {lan}",
                                processed=total_processed,
                                total=total_cases
                            )
                            
                            # Fetch current page
                            result = await collector.fetch_data(lan, page=current_page)
                            if not result or not result.get('projects'):
                                break
                            
                            # Process cases
                            for case_data in result['projects']:
                                try:
                                    # Parse dates before database operations
                                    if case_data.get('date'):
                                        case_data['date'] = parse_date(case_data['date'])
                                    if case_data.get('decision_date'):
                                        case_data['decision_date'] = parse_date(case_data['decision_date'])
                                    if case_data.get('last_updated_from_source'):
                                        case_data['last_updated_from_source'] = parse_date(case_data['last_updated_from_source'])
                                    
                                    # Check if case exists
                                    existing_case = db.query(Case).filter(Case.id == case_data["id"]).first()
                                    
                                    if existing_case:
                                        # Update if newer
                                        if not existing_case.last_updated_from_source or (
                                            case_data.get('last_updated_from_source') and 
                                            case_data['last_updated_from_source'] > existing_case.last_updated_from_source
                                        ):
                                            for key, value in case_data.items():
                                                if key in case_data:
                                                    setattr(existing_case, key, value)
                                            db.add(existing_case)
                                            if len(current_batch) >= 50:
                                                db.commit()
                                                current_batch = []
                                    else:
                                        # Create new case
                                        case = Case(**case_data)
                                        db.add(case)
                                        current_batch.append(case)
                                        if len(current_batch) >= 50:
                                            db.commit()
                                            current_batch = []
                                    
                                    total_processed += 1
                                
                                except Exception as e:
                                    logger.error(f"Error processing case {case_data.get('id')}: {str(e)}")
                                    db.rollback()  # Roll back on error
                                    continue
                            
                            # Update fetch status without committing yet
                            if not status:
                                status = FetchStatus(
                                    lan=lan,
                                    last_page_fetched=current_page,
                                    last_successful_fetch=datetime.now(),
                                    error_count=0
                                )
                                db.add(status)
                            else:
                                status.last_page_fetched = current_page
                                status.last_successful_fetch = datetime.now()
                            
                            # Check if we have more pages
                            if not result['pagination']['has_next']:
                                db.commit()  # Commit only at the end of a län's pages
                                break
                            
                            current_page += 1
                            await asyncio.sleep(random.uniform(0.5, 1))  # Reduced sleep time
                    
                    except Exception as e:
                        logger.error(f"Error fetching {lan}: {str(e)}")
                        if not status:
                            status = FetchStatus(
                                lan=lan,
                                error_count=1,
                                last_error=str(e)
                            )
                            db.add(status)
                        else:
                            status.error_count = (status.error_count or 0) + 1
                            status.last_error = str(e)
                        db.commit()
            else:
                # All län have been fetched at least once, check for updates
                logger.info("All län have been fetched, checking for updates...")
                
                # Estimate total cases for updates
                total_cases = 0
                for lan in lan_list:
                    status = fetch_statuses.get(lan)
                    if not status:
                        continue
                    try:
                        from_date = status.last_successful_fetch.strftime('%Y-%m-%d') if status.last_successful_fetch else None
                        if from_date:
                            result = await collector.fetch_data(lan, from_date=from_date, page=1)
                            if result and result.get('pagination'):
                                total_pages = result['pagination'].get('total_pages', 1)
                                total_cases += total_pages * 50
                    except Exception as e:
                        logger.error(f"Error estimating updates for {lan}: {str(e)}")
                        continue
                
                # Update task with estimated total
                update_task_progress(
                    task_id,
                    0,
                    "Starting update check...",
                    total=total_cases,
                    processed=0
                )
                
                for lan in lan_list:
                    status = fetch_statuses.get(lan)
                    if not status:
                        continue
                    
                    try:
                        # Get cases updated since last fetch
                        from_date = status.last_successful_fetch.strftime('%Y-%m-%d') if status.last_successful_fetch else None
                        if from_date:
                            update_task_progress(
                                task_id,
                                (total_processed * 100) // total_cases if total_cases > 0 else 0,
                                f"Checking updates for {lan} since {from_date}",
                                processed=total_processed,
                                total=total_cases
                            )
                            
                            current_page = 1
                            while True:
                                result = await collector.fetch_data(lan, from_date=from_date, page=current_page)
                                if not result or not result.get('projects'):
                                    break
                                
                                # Process updated cases
                                for case_data in result['projects']:
                                    try:
                                        # Parse dates before database operations
                                        if case_data.get('date'):
                                            case_data['date'] = parse_date(case_data['date'])
                                        if case_data.get('decision_date'):
                                            case_data['decision_date'] = parse_date(case_data['decision_date'])
                                        if case_data.get('last_updated_from_source'):
                                            case_data['last_updated_from_source'] = parse_date(case_data['last_updated_from_source'])
                                        
                                        existing_case = db.query(Case).filter(Case.id == case_data["id"]).first()
                                        if existing_case:
                                            # Update case
                                            for key, value in case_data.items():
                                                if key in case_data:
                                                    setattr(existing_case, key, value)
                                            db.add(existing_case)
                                            total_processed += 1
                                    except Exception as e:
                                        logger.error(f"Error updating case {case_data.get('id')}: {str(e)}")
                                        db.rollback()  # Roll back on error
                                        continue
                                
                                # Commit changes
                                db.commit()
                                
                                # Check if we have more pages
                                if not result['pagination']['has_next']:
                                    break
                                
                                current_page += 1
                                await asyncio.sleep(random.uniform(1, 2))  # Rate limiting
                        
                        # Update fetch status
                        status.last_successful_fetch = datetime.now()
                        status.error_count = 0
                        status.last_error = None
                        db.commit()
                    
                    except Exception as e:
                        logger.error(f"Error checking updates for {lan}: {str(e)}")
                        status.error_count = (status.error_count or 0) + 1
                        status.last_error = str(e)
                        db.commit()
                
            # Final commit for any remaining cases
            if current_batch:
                db.commit()
            
            complete_task(task_id, True, f"Processed {total_processed} cases")
        
        # Start background task
        background_tasks.add_task(fetch_cases_background)
        return {"status": "started", "message": "Case fetching started in background", "task_id": task_id}
    
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

@router.get("/")
def get_cases(
    request: Request,
    lan: str = None,
    status: str = None,
    category: str = None,
    phase: str = None,
    search: str = None,
    bookmarked: bool = False,
    medla_suitable: str = Query(None, description="Filter for Medla suitable projects"),
    page: int = 1,
    db: Session = Depends(get_db)
):
    """Get all cases with optional filters"""
    try:
        # Base query
        query = db.query(Case)
        
        # Apply filters
        if lan:
            query = query.filter(Case.lan == lan)
        if status:
            query = query.filter(Case.status == status)
        if category:
            query = query.filter(Case.primary_category == category)
        if phase:
            query = query.filter(Case.project_phase == phase)
        if search:
            search_term = f"%{search}%"
            query = query.filter(Case.title.ilike(search_term))
        if bookmarked:
            query = query.join(Bookmark).filter(Bookmark.case_id == Case.id)
        if medla_suitable in ['true', 'True', 'on', True]:
            query = query.filter(Case.is_medla_suitable == True)
        
        # Get distinct values for filters
        lans = db.query(Case.lan).distinct().all()
        statuses = db.query(Case.status).distinct().all()
        categories = db.query(Case.primary_category).distinct().all()
        phases = db.query(Case.project_phase).distinct().all()
        
        # Calculate pagination
        page_size = 50
        total_cases = query.count()
        total_pages = (total_cases + page_size - 1) // page_size
        
        # Get paginated results
        offset = (page - 1) * page_size
        cases = query.order_by(Case.date.desc()).offset(offset).limit(page_size).all()
        
        # Create pagination info
        pagination = {
            "current_page": page,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages
        }
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "cases": cases,
                "lans": [lan[0] for lan in lans if lan[0]],
                "statuses": [status[0] for status in statuses if status[0]],
                "categories": [cat[0] for cat in categories if cat[0]],
                "phases": [phase[0] for phase in phases if phase[0]],
                "selected_lan": lan,
                "selected_status": status,
                "selected_category": category,
                "selected_phase": phase,
                "search_query": search,
                "show_bookmarked": bookmarked,
                "show_medla_suitable": medla_suitable in ['true', 'True', 'on', True],
                "pagination": pagination
            }
        )
    except Exception as e:
        logger.error(f"Error getting cases: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting cases: {str(e)}"
        ) 