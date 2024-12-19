from abc import ABC, abstractmethod
from typing import List
from app.schemas.project import Project

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
        """Main method to collect and process data"""
        try:
            raw_data = await self.fetch_data()
            return await self.clean_data(raw_data)
        except Exception as e:
            # In a production environment, this should be properly logged
            print(f"Error collecting data from {self.source_name}: {str(e)}")
            return [] 