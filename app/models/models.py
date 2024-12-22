from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True)
    case_id = Column(String)
    title = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    location = Column(String)
    municipality = Column(String)
    status = Column(String)
    url = Column(String)
    lan = Column(String, nullable=False)
    description = Column(Text)
    
    # New fields for case details
    sender = Column(String)
    decision_date = Column(DateTime)
    decision_summary = Column(Text)
    case_type = Column(String)
    documents = Column(JSON)  # Store related documents as JSON
    details_fetched = Column(Boolean, default=False)  # Track if details have been fetched
    details_fetch_attempts = Column(Integer, default=0)  # Track number of fetch attempts
    last_fetch_attempt = Column(DateTime(timezone=True))  # Track when we last tried to fetch details
    
    # AI Categorization fields
    primary_category = Column(String)  # Main category (e.g., "Wind Power", "Solar Power", "Hydrogen Production")
    sub_category = Column(String)  # Sub-category for future use
    category_confidence = Column(Float)  # Confidence score of the categorization
    category_version = Column(Integer, default=1)  # Version of the categorization model/iteration
    category_metadata = Column(JSON)  # Additional category-related metadata and reasoning
    last_categorized_at = Column(DateTime(timezone=True))  # When the case was last categorized
    
    # Medla-specific fields
    project_phase = Column(String)  # Planning, Construction, Operational, Maintenance, Decommissioning
    is_medla_suitable = Column(Boolean, default=False)  # Whether this case is suitable for Medla
    potential_jobs = Column(JSON)  # List of potential job types for this project as JSON
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_updated_from_source = Column(DateTime(timezone=True))  # Track when the case was last updated from Länsstyrelsen
    
    bookmarks = relationship("Bookmark", back_populates="case")

class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True)
    case_id = Column(String, ForeignKey("cases.id"))
    notes = Column(Text)
    is_green_industry = Column(Boolean, default=True)
    industry_type = Column(String)  # e.g., 'battery', 'hydrogen', 'steel', etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    case = relationship("Case", back_populates="bookmarks")

class FetchStatus(Base):
    __tablename__ = "fetch_status"
    
    lan = Column(String, primary_key=True)
    last_successful_fetch = Column(DateTime(timezone=True))
    last_page_fetched = Column(Integer, default=0)
    total_pages = Column(Integer)
    error_count = Column(Integer, default=0)
    last_error = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 