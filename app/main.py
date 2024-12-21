# app/main.py

from fastapi import FastAPI, Request, Query, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.models.database import engine, get_db
from app.models import Base
from app.routers import projects, categorization
from sqlalchemy.orm import Session
from app.models.models import Case, Bookmark
from typing import Optional
import os
from dotenv import load_dotenv
from app.services.categorization import CategorizationService

# Load environment variables
load_dotenv()

# Create database tables if they don’t exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Green Industrial Projects Tracker")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configure templates
templates = Jinja2Templates(directory="app/templates")

# Initialize categorization service
categorization_service = CategorizationService(api_key=os.getenv("OPENAI_API_KEY"))

# Root route to serve the frontend
@app.get("/")
async def serve_frontend(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    lan: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    bookmarked: bool = False,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    sort: Optional[str] = None,
    order: Optional[str] = None
):
    # Items per page
    per_page = 20
    
    # Base query
    query = db.query(Case)
    
    # Apply filters
    if lan:
        query = query.filter(Case.lan == lan)        # Make sure 'lan' exists in your Case model
    if status:
        query = query.filter(Case.status == status)
    if search:
        query = query.filter(Case.title.ilike(f"%{search}%"))
    if bookmarked:
        # Join with Bookmark to filter only bookmarked cases
        query = query.join(Bookmark).filter(Bookmark.case_id == Case.id)
    if category:
        query = query.filter(Case.primary_category == category)
    if subcategory:
        query = query.filter(Case.sub_category == subcategory)
    
    # Sorting logic
    # Update the dict to match actual model fields if needed
    sort_map = {
        'title': 'title',
        'location': 'municipality',  # or whatever field you actually use for “location”
        'category': 'primary_category',
        'date': 'date',
        'status': 'status'
    }
    
    if sort and sort in sort_map:
        sort_column = getattr(Case, sort_map[sort])
        if order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Default sorting by date descending
        query = query.order_by(Case.date.desc())
    
    # Get total count for pagination
    total_items = query.count()
    total_pages = (total_items + per_page - 1) // per_page
    
    # Get paginated results
    cases = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Distinct values for filters
    lans = db.query(Case.lan).distinct().all()       # if your Case model has a 'lan' column
    statuses = db.query(Case.status).distinct().all()
    
    # Categories from your categorization service
    categories = categorization_service.categories
    
    # If you have subcategories, fetch or define them
    # For now, you said subcategories are not in use, so we set a placeholder
    subcategories_list = ["N/A"]
    
    # Add is_bookmarked flag to cases
    # For large data sets, consider a different approach, but for smaller sets this is fine
    bookmarked_cases = {b.case_id for b in db.query(Bookmark.case_id).all()}
    for case in cases:
        case.is_bookmarked = (case.id in bookmarked_cases)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "cases": cases,
        "lans": [lan[0] for lan in lans],
        "statuses": [status[0] for status in statuses],
        "categories": categories,
        "subcategories": subcategories_list,
        "category_data": {
            "categories": categories,
            "subcategories": {"N/A": ["N/A"]}  # Simplified
        },
        "selected_lan": lan,
        "selected_status": status,
        "selected_category": category,
        "selected_subcategory": subcategory,
        "search_query": search,
        "show_bookmarked": bookmarked,
        "current_sort": sort,
        "current_order": order,
        "pagination": {
            "current_page": page,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages
        }
    })

# Include API routers
app.include_router(projects.router, prefix="/api/v1")
app.include_router(categorization.router, prefix="/api/v1")
