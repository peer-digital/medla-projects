import sys
import os
import asyncio
from datetime import datetime, timedelta
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.models.database import get_db
from app.models.models import Case, FetchStatus
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector
from app.utils.date_utils import parse_date
import logging
from sqlalchemy import or_

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
        'updated_at': parsed_dates['updated_at'],
        'last_updated_from_source': datetime.now()
    }

    # Validate required fields
    if not prepared_data['id']:
        raise ValueError("Case ID is required")
    if not prepared_data['title']:
        raise ValueError("Case title is required")
    if not prepared_data['date']:
        raise ValueError(f"Invalid required date field: {case_data.get('date')}")

    return prepared_data

async def fetch_all_cases(resume: bool = True):
    """Fetch all cases from all län with support for resuming and tracking updates"""
    collector = LansstyrelsenCollector()
    db = next(get_db())
    current_batch = []
    total_cases = 0
    
    try:
        # Get list of län
        lan_list = list(collector.lan_queries.keys())
        logger.info(f"Starting to fetch cases from {len(lan_list)} län")
        
        # Process each län
        for lan in lan_list:
            try:
                # Get or create fetch status for this län
                fetch_status = db.query(FetchStatus).filter(FetchStatus.lan == lan).first()
                if not fetch_status:
                    fetch_status = FetchStatus(lan=lan)
                    db.add(fetch_status)
                    db.commit()
                
                # If resuming and we have a last successful fetch, only get cases updated since then
                from_date = None
                if resume and fetch_status.last_successful_fetch:
                    from_date = fetch_status.last_successful_fetch.strftime("%Y-%m-%d")
                else:
                    # Default to last 180 days for initial fetch
                    from_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
                
                to_date = datetime.now().strftime("%Y-%m-%d")
                
                logger.info(f"Fetching cases for {lan} from {from_date} to {to_date}...")
                
                try:
                    cases = await collector.fetch_data(lan)
                    
                    # Process cases in batches
                    for case_data in cases:
                        try:
                            # Check if case exists and needs update
                            existing_case = db.query(Case).filter(Case.id == case_data["id"]).first()
                            
                            if existing_case:
                                # Check if case has been updated
                                case_date = parse_date(case_data.get('date'))
                                if not case_date or not existing_case.last_updated_from_source or case_date > existing_case.last_updated_from_source:
                                    # Update existing case
                                    prepared_data = prepare_case_data(case_data, lan)
                                    for key, value in prepared_data.items():
                                        setattr(existing_case, key, value)
                                    db.add(existing_case)
                            else:
                                # Create new case
                                prepared_data = prepare_case_data(case_data, lan)
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
                        total_cases += len(current_batch)
                        logger.info(f"Committed final batch of {len(current_batch)} cases for {lan}. Total cases: {total_cases}")
                        current_batch = []
                    
                    # Update fetch status
                    fetch_status.last_successful_fetch = datetime.now()
                    fetch_status.error_count = 0
                    fetch_status.last_error = None
                    db.commit()
                    
                    logger.info(f"Completed processing {lan}. Added/updated {total_cases} cases so far.")
                
                except Exception as e:
                    error_msg = f"Error fetching cases for {lan}: {str(e)}"
                    logger.error(error_msg)
                    fetch_status.error_count += 1
                    fetch_status.last_error = error_msg
                    db.commit()
                    if current_batch:
                        current_batch = []
                    continue
            
            except Exception as e:
                logger.error(f"Error processing län {lan}: {str(e)}")
                if current_batch:
                    current_batch = []
                continue
        
        logger.info(f"Completed fetching all cases. Added/updated {total_cases} cases in total.")
    
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