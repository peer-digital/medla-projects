import sys
import os
import asyncio
from datetime import datetime, timedelta
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.models.database import get_db
from app.models.models import Case
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector
from app.utils.date_utils import parse_date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def prepare_case_data(raw_data, lan):
    """Prepare case data by converting date fields and setting defaults"""
    case_data = raw_data.copy()
    
    # Define all date fields that need to be parsed
    date_fields = [
        'date',
        'decision_date',
        'last_fetch_attempt',
        'last_categorized_at',
        'updated_at'
    ]
    
    # Log raw date fields for debugging
    for field in date_fields:
        if field in case_data:
            logger.debug(f"Raw {field}: {repr(case_data.get(field))}")
    
    # Parse all date fields first
    parsed_dates = {}
    for field in date_fields:
        value = case_data.get(field)
        parsed = parse_date(value)
        if parsed is not None and isinstance(parsed, datetime):
            parsed_dates[field] = parsed
        else:
            parsed_dates[field] = None
        logger.debug(f"Converted {field}: {parsed_dates[field]} (type: {type(parsed_dates[field]) if parsed_dates[field] else 'None'})")

    prepared_data = {
        'id': case_data.get('id'),
        'case_id': case_data.get('case_id'),
        'title': case_data.get('title'),
        'location': case_data.get('location'),
        'municipality': case_data.get('municipality'),
        'status': case_data.get('status'),
        'url': case_data.get('url'),
        'lan': lan,
        'description': case_data.get('description'),
        'sender': case_data.get('sender'),
        'decision_summary': case_data.get('decision_summary'),
        'case_type': case_data.get('case_type'),
        'details_fetched': case_data.get('details_fetched', False),
        'details_fetch_attempts': case_data.get('details_fetch_attempts', 0),
        'category_confidence': case_data.get('category_confidence'),
        'category_version': case_data.get('category_version', 1),
        'primary_category': case_data.get('primary_category'),
        'sub_category': case_data.get('sub_category'),
        'date': parsed_dates['date'],
        'decision_date': parsed_dates['decision_date'],
        'last_fetch_attempt': parsed_dates.get('last_fetch_attempt') or datetime.now(),
        'last_categorized_at': parsed_dates['last_categorized_at'],
        'updated_at': parsed_dates['updated_at']
    }

    # Validate required fields
    if not prepared_data['id']:
        raise ValueError("Case ID is required")
    if not prepared_data['title']:
        raise ValueError("Case title is required")
    if not prepared_data['date']:
        raise ValueError(f"Invalid required date field: {case_data.get('date')}")

    return prepared_data

async def fetch_all_cases():
    """Fetch all cases from all län"""
    collector = LansstyrelsenCollector()
    db = next(get_db())
    current_batch = []
    total_cases = 0
    
    try:
        # Get list of län
        lan_list = list(collector.lan_queries.keys())
        logger.info(f"Starting to fetch cases from {len(lan_list)} län")
        
        # Set up date range - last 180 days
        to_date = datetime.now()
        from_date = to_date - timedelta(days=180)
        
        # Process each län
        for lan in lan_list:
            try:
                logger.info(f"Fetching cases for {lan}...")
                cases = await collector.fetch_data(
                    from_date=from_date.strftime("%Y-%m-%d"),
                    to_date=to_date.strftime("%Y-%m-%d"),
                    lan=[lan]
                )
                
                # Process cases in batches
                for case_data in cases.get("projects", []):
                    try:
                        # Check if case already exists
                        if db.query(Case).filter(
                            Case.id == case_data["id"]
                        ).first():
                            continue
                        
                        logger.debug(f"Processing case {case_data.get('id')}")
                        logger.debug(f"Raw case data dates: decision_date={repr(case_data.get('decision_date'))}")
                        
                        # Prepare case data
                        prepared_data = prepare_case_data(case_data, lan)
                        
                        # Create case object
                        case = Case(**prepared_data)
                        current_batch.append(case)
                        
                        # Commit in batches of 100
                        if len(current_batch) >= 100:
                            db.bulk_save_objects(current_batch)
                            db.commit()
                            total_cases += len(current_batch)
                            logger.info(f"Committed batch of {len(current_batch)} cases for {lan}. Total cases: {total_cases}")
                            current_batch = []
                    
                    except Exception as e:
                        logger.error(f"Error processing case {case_data.get('id', 'unknown')}: {str(e)}")
                        logger.exception("Full traceback:")
                        continue
                
                # Commit any remaining cases in the batch
                if current_batch:
                    db.bulk_save_objects(current_batch)
                    db.commit()
                    logger.info(f"Committed final batch of {len(current_batch)} cases for {lan}. Total cases: {total_cases}")
                    current_batch = []
                
                logger.info(f"Completed processing {lan}. Added {total_cases} new cases so far.")
                
            except Exception as e:
                logger.error(f"Error fetching cases for {lan}: {str(e)}")
                # Don't rollback the entire transaction, just skip this län
                if current_batch:
                    current_batch = []
                continue
        
        logger.info(f"Completed fetching all cases. Added {total_cases} new cases in total.")
    
    except Exception as e:
        logger.error(f"Error in fetch_all_cases: {str(e)}")
        if current_batch:
            current_batch = []
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(fetch_all_cases()) 