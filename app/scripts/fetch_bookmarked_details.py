import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.models.database import get_db
from app.models.models import Case
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector
from app.utils.date_utils import parse_date
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_bookmarked_details():
    """Fetch details for all bookmarked cases"""
    db = next(get_db())
    collector = LansstyrelsenCollector()
    
    try:
        # Get all bookmarked cases that haven't had details fetched
        cases = db.query(Case).filter(
            Case.bookmarks.any(),
            Case.details_fetched == False
        ).all()
        
        logger.info(f"Found {len(cases)} bookmarked cases without details")
        
        for case in cases:
            try:
                logger.info(f"Fetching details for case {case.id}")
                details = await collector.fetch_case_details(case.id, case.case_id)
                
                if details:
                    # Update case with fetched details
                    case.sender = details.get('sender')
                    case.decision_date = parse_date(details.get('decision_date'))
                    case.decision_summary = details.get('decision_summary')
                    case.case_type = details.get('case_type')
                    case.documents = details.get('documents')
                    case.details_fetched = True
                    case.last_fetch_attempt = datetime.now()
                    
                    db.commit()
                    logger.info(f"Successfully updated case {case.id} with details")
                else:
                    # Update fetch attempt count and timestamp
                    case.details_fetch_attempts += 1
                    case.last_fetch_attempt = datetime.now()
                    db.commit()
                    logger.warning(f"No details found for case {case.id}")
            
            except Exception as e:
                logger.error(f"Error fetching details for case {case.id}: {str(e)}")
                case.details_fetch_attempts += 1
                case.last_fetch_attempt = datetime.now()
                db.commit()
                continue
        
        logger.info("Completed fetching details for all bookmarked cases")
    
    except Exception as e:
        logger.error(f"Error in fetch_bookmarked_details: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(fetch_bookmarked_details()) 