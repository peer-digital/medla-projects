from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ProjectStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class ProjectType(str, Enum):
    INDUSTRIAL = "industrial"
    INFRASTRUCTURE = "infrastructure"
    ENERGY = "energy"
    OTHER = "other"

class Project(BaseModel):
    id: Optional[str] = None
    title: str
    description: str
    status: ProjectStatus
    project_type: ProjectType
    location: str
    municipality: str
    county: str
    start_date: Optional[datetime] = None
    estimated_completion_date: Optional[datetime] = None
    investment_amount: Optional[float] = None
    source: str
    source_url: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Green Battery Factory",
                "description": "Construction of a new battery factory with focus on sustainable production",
                "status": "planned",
                "project_type": "industrial",
                "location": "Skellefteå",
                "municipality": "Skellefteå",
                "county": "Västerbotten",
                "source": "Länsstyrelsen Västerbotten",
                "source_url": "https://example.com/project"
            }
        }

class PaginationInfo(BaseModel):
    """Pagination information"""
    current_page: int
    total_pages: int
    total_items: int
    items_per_page: int
    has_next: bool
    has_previous: bool

class ProjectResponse(BaseModel):
    """API response model for projects"""
    source: str
    pagination: PaginationInfo
    projects: List[Dict[str, Any]] 