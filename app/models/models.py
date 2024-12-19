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
    primary_category = Column(String)  # Main category (e.g., "Energy", "Manufacturing", "Infrastructure")
    sub_category = Column(String)  # Sub-category (e.g., "Solar", "Wind", "Battery Production")
    category_confidence = Column(Float)  # Confidence score of the categorization
    category_version = Column(Integer, default=1)  # Version of the categorization model/iteration
    category_metadata = Column(JSON)  # Additional category-related metadata and reasoning
    last_categorized_at = Column(DateTime(timezone=True))  # When the case was last categorized
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    bookmarks = relationship("Bookmark", back_populates="case")

class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("cases.id"))
    notes = Column(Text)
    is_green_industry = Column(Boolean, default=True)
    industry_type = Column(String)  # e.g., 'battery', 'hydrogen', 'steel', etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    case = relationship("Case", back_populates="bookmarks") 