import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import asyncio
import logging
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_stockholm_cases():
    """Test fetching cases from Stockholm län with pagination"""
    collector = LansstyrelsenCollector()
    
    try:
        logger.info("Starting to fetch cases from Stockholm län...")
        cases = await collector.fetch_data(lan="Stockholm")
        
        if not cases or not cases.get("projects"):
            logger.error("No cases returned")
            return
        
        total_cases = len(cases["projects"])
        logger.info(f"Successfully fetched {total_cases} cases from Stockholm län")
        
        # Print some sample cases
        for i, case in enumerate(cases["projects"][:5], 1):
            logger.info(f"\nCase {i}:")
            logger.info(f"ID: {case.get('id')}")
            logger.info(f"Title: {case.get('title')}")
            logger.info(f"Date: {case.get('date')}")
            logger.info(f"Status: {case.get('status')}")
            logger.info(f"Municipality: {case.get('municipality')}")
            logger.info("-" * 50)
        
    except Exception as e:
        logger.error(f"Error testing Stockholm cases: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_stockholm_cases()) 