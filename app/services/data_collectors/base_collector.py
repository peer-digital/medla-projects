from abc import ABC, abstractmethod
from typing import List
from app.schemas.project import Project
import logging

logger = logging.getLogger(__name__)

class BaseDataCollector(ABC):
    """Base class for all data collectors"""
    
    def __init__(self):
        self.source_name: str = self.__class__.__name__
    
    @abstractmethod
    async def fetch_data(self) -> List[Project]:
        """Fetch data from the source and return a list of projects"""
        pass
    
    @abstractmethod
    async def clean_data(self, raw_data: any) -> List[Project]:
        """Clean and transform raw data into Project objects"""
        pass
    
    async def collect(self) -> List[Project]:
        """Collect data from the source and return a list of standardized cases."""
        logger.info(f"Collecting from {self.source_name}")
        try:
            raw_data = await self.fetch_data()
            cases = self.transform_data(raw_data)
            return cases
        except Exception as e:
            logger.error(f"Error collecting data from {self.source_name}: {str(e)}")
            return [] 