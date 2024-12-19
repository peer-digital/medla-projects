import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import time
from app.utils.date_utils import parse_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LansstyrelsenCollector:
    """Collector for Länsstyrelsen data"""
    
    def __init__(self):
        """Initialize the collector"""
        self.source_name = "Länsstyrelsen"
        self.base_url = "https://diarium.lansstyrelsen.se"
        self.items_per_page = 50
        self._setup_session()
        
        # Define län queries
        self.lan_queries = {
            'Värmland': 'oJ/Yw8gzqErwbiTTCxUh+1TQ2hSHSOXrDc2OfrAMN8rme4hlk2n7Tg2HoNmbUOk8b+nibqv3wruEYA3SSNc1dWiw/3v6SNDBmbPQkhGyWO1BlxSOVMXar95FddPuPlOwKFvimdLsZiq5iFmumW1VYBOKKPOLSJ71hHoihcypa1Y0kE9EJdycFSjYfnrV6tHbDuSmI6V2DJm7qpUlcQU1ATw1JdfKoGfs',
            'Stockholm': 'oJ/Yw8gzqEr9ngHRvOS/2ldmWTfvgjFlqUZFUYhPZnwUx8MwAuFzFTiAb1/7bMntiEZH+fFgiW5ALWxF1I5vxEiAYmdEdOahK/pYQOCJNpfkyPdhkzSmVM3bVjEX4C8r4yu97P3JRoF/T/hZDj30FIaOlikOXaBN3SFYGNTVjSQ2DZKFDf6KizEGlCt7sYIS2iKb9Pf1MvKc0TBfdIhlQg=='
        }

        # Default headers for ASP.NET form submission
        self.default_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://diarium.lansstyrelsen.se',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Upgrade-Insecure-Requests': '1'
        }

    def _setup_session(self):
        """Setup a new session with retry logic"""
        retry_strategy = Retry(
            total=3,  # number of retries
            backoff_factor=1,  # wait 1, 2, 4 seconds between retries
            status_forcelist=[500, 502, 503, 504],  # HTTP status codes to retry on
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _reset_session(self):
        """Reset the session to handle timeouts"""
        if self.session:
            self.session.close()
        self._setup_session()

    def collect(self, lan: str = None) -> List[Dict[str, Any]]:
        """Collect basic case information from Länsstyrelsen"""
        try:
            if lan not in self.lan_queries:
                logger.error(f"Unknown län name: {lan}")
                return []
            
            logger.info(f"Searching län: {lan}")
            results, _ = self._collect_data_for_lan(lan)
            return results
            
        except Exception as e:
            logger.error(f"Failed to collect data: {str(e)}")
            return []

    def _collect_data_for_lan(self, lan_name: str) -> Tuple[List[Dict[str, Any]], int]:
        """Collect data for a specific län"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Reset session before each attempt
                self._reset_session()
                
                # Get the serialized query for this län
                query = self.lan_queries[lan_name]
                
                # Get initial page with the query
                logger.info(f"Starting data collection for län {lan_name}... (Attempt {retry_count + 1}/{max_retries})")
                initial_url = f"{self.base_url}/Case/CaseSearchResult.aspx?query={query}"
                
                # Set up headers for initial request
                headers = self.default_headers.copy()
                headers['Referer'] = initial_url
                
                # Make initial request to get form data
                initial_response = self.session.get(initial_url, headers=headers)
                
                if initial_response.status_code == 200:
                    results, total_items = self._parse_search_results(initial_response.text, lan_name)
                    if results is not None:
                        return results, total_items
                    else:
                        logger.warning(f"No valid results found for län {lan_name}")
                        retry_count += 1
                else:
                    error_msg = {
                        'status_code': initial_response.status_code,
                        'headers': dict(initial_response.headers),
                        'content': initial_response.text[:1000]
                    }
                    logger.error(f"Failed to get initial page: {error_msg}")
                    retry_count += 1

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for län {lan_name} (Attempt {retry_count + 1}/{max_retries}): {str(e)}")
                retry_count += 1
                if retry_count >= max_retries:
                    raise Exception(f"Max retries reached for län {lan_name}: {str(e)}")
            
            except Exception as e:
                logger.error(f"Unexpected error for län {lan_name}: {str(e)}")
                raise e

        return [], 0  # Return empty list and 0 total if all retries failed

    def _parse_search_results(self, html_content: str, lan_name: str) -> Tuple[List[Dict[str, Any]], int]:
        """Parse search results from HTML content"""
        try:
            results = []
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Get total items count from the search hit count div
            total_items = 0
            search_hit_count = soup.find('div', {'class': 'large-search__search-hit-count'})
            if search_hit_count:
                h3_text = search_hit_count.find('span', {'id': 'SearchPlaceHolder_lblCaseCount'})
                if h3_text and h3_text.text:
                    # Extract total count from text like "Sökresultat: 1-50 av 7411"
                    match = re.search(r'av\s+(\d+)', h3_text.text)
                    if match:
                        total_items = int(match.group(1))

            # Find the results table
            table = soup.find('table', {'id': 'SearchPlaceHolder_caseGridView'})
            if table:
                rows = table.find_all('tr')[1:]  # Skip header row
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 8:  # We expect 8 columns
                        case_cell = cells[0]
                        case_link = case_cell.find('a', {'class': 'sv-font-brodtext-med-bla-lankning'})
                        
                        # Skip pagination artifacts
                        if not case_link or ('href' in case_link.attrs and 'javascript:' in case_link['href']):
                            continue

                        # Extract case ID directly from the link text
                        case_id = case_link.get_text(strip=True) if case_link else ""
                        
                        # Extract case ID from href
                        case_url = None
                        if case_link and 'href' in case_link.attrs:
                            href = case_link['href']
                            case_id_match = re.search(r'caseID=(\d+)', href)
                            if case_id_match:
                                case_url = f"{self.base_url}/Case/CaseInfo.aspx?caseID={case_id_match.group(1)}"
                        
                        status = cells[1].get_text(strip=True)
                        date_str = cells[2].get_text(strip=True)
                        title = cells[3].get_text(strip=True)
                        sender = cells[4].get_text(strip=True)
                        city = cells[5].get_text(strip=True)
                        municipality = cells[6].get_text(strip=True)
                        
                        # Convert date format
                        try:
                            date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else None
                        except ValueError:
                            logger.warning(f"Invalid date format: {date_str}")
                            date = None
                        
                        # Create result with case ID
                        result = {
                            'id': case_id,
                            'title': title,
                            'date': date,  # Now a datetime object
                            'location': city,
                            'municipality': municipality or lan_name,  # Use län name if municipality is empty
                            'status': status,
                            'url': case_url,
                            'lan': lan_name  # Always use the län name we're searching in
                        }
                        results.append(result)
            
            return results, total_items
            
        except Exception as e:
            logger.error(f"Error parsing search results: {str(e)}")
            return [], 0

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        return parse_date(date_str)
    
    def fetch_case_details(self, case_id: str, delay: float = 1.0) -> Dict[str, Any]:
        """Fetch detailed information for a specific case with rate limiting"""
        try:
            # Add delay for rate limiting
            time.sleep(delay)
            
            # Reset session before request
            self._reset_session()
            
            # Get the case URL
            case_url = f"{self.base_url}/Case/CaseInfo.aspx?caseID={case_id}"
            
            # Set up headers for request
            headers = self.default_headers.copy()
            headers['Referer'] = case_url
            
            # Make request
            response = self.session.get(case_url, headers=headers)
            logger.info(f"GET response status for case {case_id}: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch case details for {case_id}: {response.status_code}")
                return None
            
            # Parse the response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the main content table
            details_table = soup.find('table', {'class': 'sv-table'})
            if not details_table:
                logger.error(f"Could not find details table for case {case_id}")
                return None
            
            # Parse details
            details = {}
            rows = details_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    details[key] = value
            
            # Extract documents
            documents = []
            docs_table = soup.find('table', {'id': 'DocumentsPlaceHolder_documentsGridView'})
            if docs_table:
                doc_rows = docs_table.find_all('tr')[1:]  # Skip header row
                for doc_row in doc_rows:
                    doc_cells = doc_row.find_all('td')
                    if len(doc_cells) >= 4:
                        document = {
                            'id': doc_cells[0].get_text(strip=True),
                            'title': doc_cells[1].get_text(strip=True),
                            'date': doc_cells[2].get_text(strip=True),
                            'type': doc_cells[3].get_text(strip=True)
                        }
                        documents.append(document)
            
            # Extract decision summary from documents or description
            decision_docs = [doc for doc in documents if 'beslut' in doc['title'].lower()]
            decision_summary = details.get('Beslut') or (decision_docs[0]['title'] if decision_docs else None)
            
            # Parse decision date
            decision_date = self._parse_date(details.get('Beslutsdatum'))
            
            # Create result
            result = {
                'case_type': details.get('Ärendetyp'),
                'decision_date': decision_date,
                'decision_summary': decision_summary,
                'sender': details.get('Avsändare/mottagare'),
                'documents': documents
            }
            
            logger.info(f"Parsed details for case {case_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching case details for {case_id}: {str(e)}")
            return None