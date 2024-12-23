from sqlalchemy import Column, String, DateTime, Integer, Text
from app.database import Base

class FetchStatus(Base):
    __tablename__ = "fetch_status"

    lan = Column(String, primary_key=True)
    last_successful_fetch = Column(DateTime, nullable=True)
    last_page_fetched = Column(Integer, nullable=True)
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    total_cases_checked = Column(Integer, default=0)  # Track all cases we've checked
    total_medla_cases = Column(Integer, default=0)    # Track only Medla-suitable cases 