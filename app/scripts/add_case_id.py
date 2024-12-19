import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.models.database import engine, get_db
from app.models.models import Case
from sqlalchemy import Column, String, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_case_id_column():
    """Add case_id column to cases table"""
    try:
        # Add the column - SQLite syntax
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(text("PRAGMA table_info(cases);"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'case_id' not in columns:
                conn.execute(text('ALTER TABLE cases ADD COLUMN case_id VARCHAR;'))
                conn.commit()
                logger.info("Added case_id column to cases table")
            else:
                logger.info("case_id column already exists")
            
        # Extract case_ids from data-case-id attributes in existing data
        db = next(get_db())
        cases = db.query(Case).all()
        updated = 0
        
        for case in cases:
            if case.case_id is None and case.url:
                # Extract case_id from URL
                import re
                case_id_match = re.search(r'caseID=(\d+)', case.url)
                if case_id_match:
                    case.case_id = case_id_match.group(1)
                    updated += 1
        
        if updated > 0:
            db.commit()
            logger.info(f"Updated {updated} cases with case_id from URLs")
        
        logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Error in migration: {str(e)}")
        raise

if __name__ == "__main__":
    add_case_id_column() 