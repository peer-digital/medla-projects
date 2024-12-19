from fastapi import FastAPI, Request, Query, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.models.database import engine, get_db
from app.models import Base
from app.routers import projects, categorization
from sqlalchemy.orm import Session
from app.models.models import Case, Bookmark
from typing import Optional
from sqlalchemy import func
from dotenv import load_dotenv
import os
from app.services.categorization import CategorizationService

# Load environment variables
load_dotenv()

# Create database tables
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
        query = query.filter(Case.lan == lan)
    if status:
        query = query.filter(Case.status == status)
    if search:
        query = query.filter(Case.title.ilike(f"%{search}%"))
    if bookmarked:
        query = query.join(Bookmark)
    if category:
        query = query.filter(Case.primary_category == category)
    if subcategory:
        query = query.filter(Case.sub_category == subcategory)
    
    # Apply sorting
    if sort:
        # Define the column to sort by
        sort_column = getattr(Case, {
            'title': 'title',
            'location': 'municipality',  # Using municipality for location sorting
            'category': 'primary_category',
            'date': 'date',
            'status': 'status'
        }.get(sort, 'date'))  # Default to date if invalid sort column
        
        # Apply the sort order
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
    
    # Get unique län and statuses for filters
    lans = db.query(Case.lan).distinct().all()
    statuses = db.query(Case.status).distinct().all()
    
    # Get categories and subcategories
    categories = categorization_service.categories
    
    # Get all subcategories for the selected category
    subcategories = ["N/A"]  # Since we're not using subcategories anymore
    
    # Add is_bookmarked flag to cases
    bookmarked_cases = {b.case_id for b in db.query(Bookmark.case_id).all()}
    for case in cases:
        case.is_bookmarked = case.id in bookmarked_cases
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "cases": cases,
        "lans": [lan[0] for lan in lans],
        "statuses": [status[0] for status in statuses],
        "categories": categories,
        "subcategories": subcategories,
        "category_data": {
            "categories": categories,
            "subcategories": {"N/A": ["N/A"]}  # Simplified subcategory structure
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