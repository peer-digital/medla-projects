import asyncio
import logging
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_case_details():
    """Test fetching case details with proper session handling"""
    case_id = "8384-2023"  # Using a more recent case ID
    logger.info(f"Testing case {case_id}")
    
    collector = LansstyrelsenCollector()
    try:
        details = await collector.fetch_case_details(case_id)
        if details:
            logger.info("Successfully fetched case details:")
            for key, value in details.items():
                if key != 'documents':
                    logger.info(f"{key}: {value}")
                else:
                    logger.info(f"Documents: {len(value)} found")
                    for doc in value:
                        logger.info(f"  - {doc['title']} ({doc['date']})")
        else:
            logger.error("No details returned")
    except Exception as e:
        logger.error(f"Error fetching case details: {str(e)}")

async def main():
    await test_case_details()

if __name__ == "__main__":
    asyncio.run(main()) 