import sys
import os
import asyncio
from datetime import datetime, timedelta
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.models.database import get_db
from app.models.models import Case, FetchStatus
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector
from app.services.categorization import CategorizationService
from app.utils.date_utils import parse_date
import logging
from sqlalchemy import or_

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set debug level for other loggers
logging.getLogger('app.services.data_collectors.lansstyrelsen_collector').setLevel(logging.DEBUG)
logging.getLogger('app.utils.date_utils').setLevel(logging.WARNING)  # Keep this at WARNING to avoid noise

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
        if isinstance(value, datetime):
            parsed_dates[field] = value
        elif value:  # Only try to parse if we have a value
            try:
                parsed = parse_date(value)
                parsed_dates[field] = parsed
                logger.debug(f"Successfully parsed {field}: {parsed}")
            except Exception as e:
                logger.warning(f"Failed to parse {field} ({value}): {str(e)}")
                parsed_dates[field] = None
        else:
            parsed_dates[field] = None
        logger.debug(f"Final {field}: {parsed_dates[field]} (type: {type(parsed_dates[field]) if parsed_dates[field] else 'None'})")

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
        logger.warning(f"Case {prepared_data['id']} is missing date field")

    return prepared_data

async def fetch_all_cases(resume: bool = True):
    """
    Fetch all cases from Länsstyrelsen, classify them, and save only Medla-suitable cases.
    """
    db = next(get_db())
    collector = LansstyrelsenCollector()
    categorization_service = CategorizationService()
    current_batch = []
    total_cases_checked = 0  # Track all cases we check
    total_medla_cases = 0    # Track only Medla cases
    
    try:
        for lan in collector.lan_queries.keys():
            try:
                fetch_status = db.query(FetchStatus).filter(FetchStatus.lan == lan).first()
                
                if not fetch_status:
                    fetch_status = FetchStatus(lan=lan)
                    db.add(fetch_status)
                    db.commit()
                
                if resume and fetch_status.last_successful_fetch:
                    # Only fetch cases newer than last successful fetch minus 1 day for safety
                    start_date = fetch_status.last_successful_fetch - timedelta(days=1)
                else:
                    start_date = None
                
                try:
                    logger.info(f"Fetching cases for {lan}")
                    result = await collector.fetch_cases(lan)
                    cases = result.get('projects', [])
                    
                    # Process cases in batches
                    for case_data in cases:
                        total_cases_checked += 1  # Increment total cases checked
                        
                        try:
                            case_id = case_data.get("id")
                            if not case_id:
                                logger.warning(f"Skipping case due to missing ID in {lan}")
                                continue
                                
                            case_date = parse_date(case_data.get('date'))
                            if not case_date:
                                logger.warning(f"Skipping case {case_id} due to invalid date in {lan}")
                                continue
                            
                            # Check if case exists
                            existing_case = db.query(Case).filter(Case.id == case_id).first()
                            
                            # Determine if case needs updating based on multiple factors
                            needs_update = False
                            if not existing_case:
                                needs_update = True
                                logger.debug(f"New case found: {case_id}")
                            else:
                                # Check date-based updates
                                if case_date and (
                                    not existing_case.last_updated_from_source or 
                                    case_date > existing_case.last_updated_from_source
                                ):
                                    needs_update = True
                                    logger.debug(f"Case {case_id} needs update due to newer date")
                                
                                # Check content-based updates (status, decision date, etc.)
                                elif (
                                    case_data.get('status') != existing_case.status or
                                    case_data.get('decision_date') != existing_case.decision_date or
                                    case_data.get('title') != existing_case.title or
                                    case_data.get('description') != existing_case.description
                                ):
                                    needs_update = True
                                    logger.debug(f"Case {case_id} needs update due to content changes")
                            
                            if needs_update:
                                # Prepare case data
                                prepared_data = prepare_case_data(case_data, lan)
                                
                                # Classify the case
                                if existing_case:
                                    case = existing_case
                                    for key, value in prepared_data.items():
                                        setattr(case, key, value)
                                else:
                                    case = Case(**prepared_data)
                                
                                # Perform classification
                                case, success, error = await categorization_service._categorize_case(case)
                                
                                # Only save if it's a Medla-suitable case
                                if case.is_medla_suitable:
                                    total_medla_cases += 1  # Increment Medla cases counter
                                    if existing_case:
                                        db.add(case)
                                    else:
                                        current_batch.append(case)
                                    
                                    # Commit in batches of 100
                                    if len(current_batch) >= 100:
                                        db.bulk_save_objects(current_batch)
                                        db.commit()
                                        logger.info(f"Committed batch of {len(current_batch)} Medla-suitable cases for {lan}. Total Medla cases: {total_medla_cases}, Total checked: {total_cases_checked}")
                                        current_batch = []
                            
                        except Exception as e:
                            logger.error(f"Error processing case {case_data.get('id', 'unknown')}: {str(e)}")
                            logger.exception("Full traceback:")
                            continue
                    
                    # Commit any remaining cases in the batch
                    if current_batch:
                        db.bulk_save_objects(current_batch)
                        db.commit()
                        logger.info(f"Committed final batch of {len(current_batch)} Medla-suitable cases for {lan}. Total Medla cases: {total_medla_cases}, Total checked: {total_cases_checked}")
                        current_batch = []
                    
                    # Update fetch status with counters
                    fetch_status.last_successful_fetch = datetime.now()
                    fetch_status.error_count = 0
                    fetch_status.last_error = None
                    fetch_status.total_cases_checked = total_cases_checked
                    fetch_status.total_medla_cases = total_medla_cases
                    db.commit()
                    
                    logger.info(f"Completed processing {lan}. Total Medla cases: {total_medla_cases}, Total checked: {total_cases_checked}")
                
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
        
        logger.info(f"Completed fetching all cases. Total Medla cases: {total_medla_cases}, Total checked: {total_cases_checked}")
    
    except Exception as e:
        logger.error(f"Error in fetch_all_cases: {str(e)}")
        if current_batch:
            current_batch = []
        db.rollback()
        raise
    finally:
        db.close()
        
    return {
        "total_cases_checked": total_cases_checked,
        "total_medla_cases": total_medla_cases
    }

if __name__ == "__main__":
    asyncio.run(fetch_all_cases()) 