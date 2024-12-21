import asyncio
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base
from app.models.models import Case, FetchStatus
from app.services.data_collectors.lansstyrelsen_collector import LansstyrelsenCollector
from app.utils.date_utils import parse_date

# Create a test database
TEST_DB_URL = "sqlite:///test_fetch.db"
engine = create_engine(TEST_DB_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def setup_test_db():
    """Create test database and tables"""
    Base.metadata.create_all(bind=engine)

def cleanup_test_db():
    """Remove test database"""
    if os.path.exists("test_fetch.db"):
        os.remove("test_fetch.db")

async def test_resumable_fetch():
    print("\nTesting resumable fetch functionality...")
    
    # Setup
    cleanup_test_db()
    setup_test_db()
    collector = LansstyrelsenCollector()
    db = TestingSessionLocal()
    
    try:
        # Test scenario 1: Initial fetch
        print("\nScenario 1: Initial fetch")
        test_lan = "Stockholm"
        
        # Fetch first page
        print("\nFetching page 1...")
        result = await collector.fetch_data(test_lan, page=1)
        
        if result and result.get('projects'):
            # Save cases to database
            print(f"Saving {len(result['projects'])} cases...")
            for case_data in result['projects']:
                if case_data.get('date'):
                    case_data['date'] = parse_date(case_data['date'])
                if case_data.get('decision_date'):
                    case_data['decision_date'] = parse_date(case_data['decision_date'])
                if case_data.get('last_updated_from_source'):
                    case_data['last_updated_from_source'] = parse_date(case_data['last_updated_from_source'])
                
                case = Case(**case_data)
                db.add(case)
            
            # Create fetch status
            fetch_status = FetchStatus(
                lan=test_lan,
                last_successful_fetch=datetime.now(),
                last_page_fetched=1,
                error_count=0
            )
            db.add(fetch_status)
            db.commit()
            
            print("Initial fetch completed")
            
            # Verify saved data
            cases = db.query(Case).all()
            status = db.query(FetchStatus).filter(FetchStatus.lan == test_lan).first()
            print(f"\nVerification:")
            print(f"Cases saved: {len(cases)}")
            print(f"Last page fetched: {status.last_page_fetched}")
            print(f"Last fetch time: {status.last_successful_fetch}")
        
        # Test scenario 2: Resume fetch
        print("\nScenario 2: Resume fetch")
        if result['pagination']['has_next']:
            print("\nFetching page 2...")
            result = await collector.fetch_data(test_lan, page=2)
            
            if result and result.get('projects'):
                # Save new cases
                print(f"Saving {len(result['projects'])} cases...")
                for case_data in result['projects']:
                    if case_data.get('date'):
                        case_data['date'] = parse_date(case_data['date'])
                    if case_data.get('decision_date'):
                        case_data['decision_date'] = parse_date(case_data['decision_date'])
                    if case_data.get('last_updated_from_source'):
                        case_data['last_updated_from_source'] = parse_date(case_data['last_updated_from_source'])
                    
                    case = Case(**case_data)
                    db.add(case)
                
                # Update fetch status
                status = db.query(FetchStatus).filter(FetchStatus.lan == test_lan).first()
                status.last_page_fetched = 2
                status.last_successful_fetch = datetime.now()
                db.commit()
                
                print("Resume fetch completed")
                
                # Verify updated data
                cases = db.query(Case).all()
                status = db.query(FetchStatus).filter(FetchStatus.lan == test_lan).first()
                print(f"\nVerification:")
                print(f"Total cases saved: {len(cases)}")
                print(f"Last page fetched: {status.last_page_fetched}")
                print(f"Last fetch time: {status.last_successful_fetch}")
        
        # Test scenario 3: Update check
        print("\nScenario 3: Update check")
        # Set last fetch time to yesterday to simulate checking for updates
        status = db.query(FetchStatus).filter(FetchStatus.lan == test_lan).first()
        status.last_successful_fetch = datetime.now() - timedelta(days=1)
        db.commit()
        
        print("\nChecking for updates...")
        from_date = status.last_successful_fetch.strftime('%Y-%m-%d')
        result = await collector.fetch_data(test_lan, from_date=from_date, page=1)
        
        if result and result.get('projects'):
            print(f"Found {len(result['projects'])} updates")
            
            # Process updates
            for case_data in result['projects']:
                existing_case = db.query(Case).filter(Case.id == case_data["id"]).first()
                if existing_case:
                    print(f"Updating case: {existing_case.id}")
                    if case_data.get('date'):
                        case_data['date'] = parse_date(case_data['date'])
                    if case_data.get('decision_date'):
                        case_data['decision_date'] = parse_date(case_data['decision_date'])
                    if case_data.get('last_updated_from_source'):
                        case_data['last_updated_from_source'] = parse_date(case_data['last_updated_from_source'])
                    
                    for key, value in case_data.items():
                        if key in case_data:
                            setattr(existing_case, key, value)
                    db.add(existing_case)
            
            # Update fetch status
            status.last_successful_fetch = datetime.now()
            db.commit()
            
            print("Update check completed")
            
            # Verify final state
            cases = db.query(Case).all()
            status = db.query(FetchStatus).filter(FetchStatus.lan == test_lan).first()
            print(f"\nFinal verification:")
            print(f"Total cases in database: {len(cases)}")
            print(f"Last successful fetch: {status.last_successful_fetch}")
        
    except Exception as e:
        print(f"Error during test: {str(e)}")
    finally:
        db.close()
        cleanup_test_db()

if __name__ == "__main__":
    asyncio.run(test_resumable_fetch()) 