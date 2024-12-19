from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def parse_date(date_str):
    """Parse date string to datetime object, return None if invalid."""
    if not date_str:
        return None

    if isinstance(date_str, datetime):
        return date_str

    try:
        date_str = str(date_str).strip()
        logger.debug(f"Parsing date string: {repr(date_str)}")
        
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # If all attempts fail, try to extract just the date part
        if '-' in date_str:
            date_part = date_str.split()[0]  # Take first part before any space
            try:
                return datetime.strptime(date_part, "%Y-%m-%d")
            except ValueError:
                logger.warning(f"Failed to parse date part: {date_part}")
                return None

        logger.warning(f"Could not parse date with any format: {repr(date_str)}")
        return None

    except Exception as e:
        logger.warning(f"Failed to parse date: {repr(date_str)}, error: {str(e)}")
        return None 