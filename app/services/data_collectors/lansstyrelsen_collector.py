from typing import List, Any, Optional, Dict, Tuple, Union
import aiohttp
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging
import time
import random
import asyncio
from app.utils.date_utils import parse_date
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseDataCollector:
    """Base class for data collectors"""
    def __init__(self):
        self.source_name = None
        self.base_url = None

class LansstyrelsenCollector(BaseDataCollector):
    """Collector for Länsstyrelsen data"""
    
    def __init__(self):
        super().__init__()
        self.source_name = "Länsstyrelsen"
        self.base_url = "https://diarium.lansstyrelsen.se"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Mapping of case numbers to caseIDs
        self.case_id_mapping = {
            "13649-2014": "1366003",
            # Add more mappings as we discover them
        }
        # Define län queries
        self.lan_queries = {
            'Blekinge': 'oJ/Yw8gzqEqkNIX1ShhaGWnWcYgyyBdrYHcfG3urKk8/9Zkiokzp0729kvmEyalIedPQBOMNpj63vV+7vy551JfDJvn3xy5BW70PT/+vPLD9uq4jbc+f/NeC1MhP1ZVvWD4FoxnBr5y5sHs3eHq3BdShWRzY+bNQZf9uy0EYRXvjWV6QWSLv2IWfYlZEpRgPzWAtKr01xkSF9Dec196mhA==',
            'Dalarna': 'oJ/Yw8gzqEphSnIcwnpkaNnPA7kL1gRZ4QWHdOX8FhuAyrnC2x2a+OkcbZCs52SC3R3oiAIxQnHMw2sE1D8/a1ub05oRT59giuDlLUaoGEZC3B+Rovcz+AwllaLFRHaa7cURg9aanS3m4UVCSplh7QAfQ+mbp7wV13/W72P//kaBIhUvCHFyN9nkqBTI3OQpRf2Ct8DAi1ejgAeyncHoCQ==',
            'Gotland': 'oJ/Yw8gzqEokeApJVYjRaXoa6k2YElv2emC/oUqyvgFuTr4dDwz3mfBS6ACteyVPmtF/4eeZTE5dKd8ZwzlsI6bTF0fPGHagJLHKWFmWrvkvCGdKm8Ee7x5XPGrwqWxllANj02PO7qZe2IlBrnsMDKAjaDzhzbZ2Ny6lSUxXf32Zlvgvg0/9990pLI6EibjLKXCAhugBI/idniJtuxGOCA==',
            'Gävleborg': 'oJ/Yw8gzqEoPWnqU46hgSukMY6AnxKe5CnlaCg3fZqGGz6dFaKS4eFjafDHa7fD4wZ5571F/ScM5umV8tq+WUGlortEXpF2KBPEIjOhPDH1iyQBpfAC1c6r6+eDRe8DZRqmQa6U03tpKKeJOqtCev3hXnMqY21habRnjBEObNkSL+tjUu60p40fVjhAgvknxzqcJTnqygppmiuYbA/MNWLLiunULSxEp',
            'Halland': 'oJ/Yw8gzqEp0tmHRAAOQK4TwleyAyggOigTHR+8zTcs7T6H8VNzrALRKTlDgyC/8JrzfsaP9lJ/5AkUmxJUtXzCEa0Q+o+JlU1ynIZ5Wl9PGzU+zoaZ/QswWlut5wCFHDR/dcCfMKp89/FRdcS4ZwqVQPTmmvZtOrm0EnegbYh1ULBofjven2/DHeCx6iXvu1odsTa22G1OaTIyE+J7a7Q==',
            'Jämtland': 'oJ/Yw8gzqEruhPyZ6tGyAsh7jq1mAswTLZe5rMuQvSSXn8tE73zBUqA9QTyqiIcvV/3hPBmQIZKVmWFaKNeRRrF46EKA413PTHtvVXobWxbkJjCDGqZTkcUYY75s0cB+BIJIzzHF44mBmMLGY0wT89v0Vp9fu5nWCOSuVqVg84BOYiv1k5xkk/RbejwqeBFF7vXx4LL+Cv2fG7xWodvbkTTZUCZnF7jE',
            'Jönköping': 'oJ/Yw8gzqEo1wANBSKzPj42X2YnLSUN/zPn0ViG28D1ByELJxtyX50hsRz2SuNdQ2g4jZEEHGtEyn8ZJkoH9KX3yact7hXlmPrbv3LTuWyEMQ0OwBT1IwNfpDks+F3oPWpYx/24fMN7pG+Tv6yz8cQwMVyKs+u2p7sT5sYcQ54jbBIhjqLfIf7UgckeZia+/AggowQZ1AvCuWDLpjns+xF/40Ky5qYeO',
            'Kalmar': 'oJ/Yw8gzqErxu6usVA+Wbgz0jxB1z1+K6dFRA8jFjgwlxvjQk/XlaKTQmuAonx3bF3XGDPSQJfFL4fPINvTfj1AIN4Ne0a6MP2/Fz7sx6eacf8w+9ZwnV7CxKIoLUEILa6uehhVpz+QZSdjNc9iSMYmBGcJGaQTLvWHwDc6KQ5qJRUz8MfGIL6O8EUOOwGDTzjOv7znoisG9LWUbQe7SKg==',
            'Kronoberg': 'oJ/Yw8gzqEprB4JJnbIaFEOYgRT/BiIsoFQBzLCuL+mg5YXe73qqHOHcSWAB+cWfABOsDQdgvQOYtNmyk6+ZGvOCTcwkLxBOjjTo+oOqnVRL2brbAKtj7kirkfw4n2qnGbYzamZeVB635r7wJPk32LSwQdMIG/xZhDkQ9vIW5ULPEB2t060UNEevApSr+S1kN/UklwX42UH+MlDWmzwxMw==',
            'Norrbotten': 'oJ/Yw8gzqEoDojViDAag9VYhHZuZYf8FfC/ieZIzAIiR/0cDi+HzRjxMeHChamIg03ba5sFLUAd+V9pfElF/g0CdpB24FQGPDz7oSsCUnbH3btOYvA6ivzWwSEGpIq9/NjPcC3tb7+4X/jHs45mvhKLv1yRStGJMqE1E2Ft+eakgIaT+EVXzmsa9BFoL5CZPI2doBJnJTe4nlrEtJWufNQ==',
            'Skåne': 'oJ/Yw8gzqEoFid3M8oYE6flZFIYGTWPE8O0F7SS0+gy5SjRMjOhf90eJdINMymqX85ZAeW5laMUEBqV3YwWNbTUbcQ0plrcYLwHqR4R407mcJnBglnoKRtIeXkS2e/keLwRRrc3AdDBGwNXP9Np08ooGg2uUt7wk/btrZTsx6PJa7T9r8IbtK5Aqy+prVWH2cwHxkyClGeIiOSeSyDT+MA==',
            'Stockholm': 'oJ/Yw8gzqEr9ngHRvOS/2ldmWTfvgjFlqUZFUYhPZnwUx8MwAuFzFTiAb1/7bMntiEZH+fFgiW5ALWxF1I5vxEiAYmdEdOahK/pYQOCJNpfkyPdhkzSmVM3bVjEX4C8r4yu97P3JRoF/T/hZDj30FP1N9QtHTaYHz9E+PJN/hCP2uicaAXbQuFDAY47PgQSvV3Eauy6DO+MjoDJHiICdtA==',
            'Södermanland': 'oJ/Yw8gzqEoCUywfMvdObIgZuCIP4ndzxv7yLaRyKm7/9b4Tlf7izbW3HWSgpM9J6uu7NC9ibT+AknSBj/V4WS/sPA6VUWqnuBukCeYRB5YnRt4t/z/z4+NzB/KON++A5JU4tjzcNyMGwZA6V0FxoMVs/8VHAr3ez0qIwj+LWTfoRHAJnONnlFfntVqA+yrky5N8ai/RXyYszqyW9841Ay5TWtBuJwnO',
            'Uppsala': 'oJ/Yw8gzqEpUh60GRueUYQxVY2cg7Lez02wrlcXJfaj7GWqwRgRWd5iBM7LLnKOUGRtmB/99nTOTfMwnNH81PYFeAgwNpzvGQR+Rp3UwJWbnXWKHTTqw+6NvdzAhxES3A/g/VtBTYpZHvLnSwl3/g+Z8PyeThnx+xlzqjuxF+I9PHQh68P+Iv8vt8TivfrvF3K8yvl9bliq0FqA8yMhmQw==',
            'Värmland': 'oJ/Yw8gzqErwbiTTCxUh+1TQ2hSHSOXrDc2OfrAMN8rme4hlk2n7Tg2HoNmbUOk8b+nibqv3wruEYA3SSNc1dWiw/3v6SNDBmbPQkhGyWO1BlxSOVMXar95FddPuPlOwKFvimdLsZiq5iFmumW1VYBOKKPOLSJ71JGzGzgoy+Q+DhuBtA2JzECgKmdUuyZZOIpHkRl13q1U6g2HfZItSow764HGDCEYJ',
            'Västerbotten': 'oJ/Yw8gzqEoNb8WjlmUzHPTdaN6YGSpudkuvczkb93cor0JTZvWWFgcMrv+fnSoNHp/NoWsTK175ddLUsJOIU6UKpXeHy6EzUv5hmIRwEVrCwSPUmpbSbsbAurngE9p0ckF7+QOz3YKboMI6EB6wTAIsPWfnLMSJ6kggKhM8aITB15I1JNqjtAq2YmrXP1WNdfcATHfs34UUyx/rBAsnjfLcP6Ot5aIu',
            'Västernorrland': 'oJ/Yw8gzqEpIUyPCD9tP0JFcRoLD05ORL4cXcJEi01y3X79DvS4rdky+B5PEyHw08s6EG2XYAfuEe9S0A6Ngj5glRXgPxJ/oqPYmS1meDqH7ffFegA6uhReTpNVnj54GmA7s8o8jL0m/Y+c1+94zDw9yrLYF/ja6jr41YFTjf4JBZvhBEDAvcx1ubj1IlPIdU1XSdpkkpcPq/82/lDNKY7EKuFgfEaQzw70MfcRYmLM=',
            'Västmanland': 'oJ/Yw8gzqEos5u1jaIdNYYWJXzdf3x/YIlHcT2aAkMnGCrJ2sepoZduei4g3F6IHdi9Fy3cgn8glPPVKkHlXTANxGlJmt7IDzIrrbOL5+Gudl8TwHIlWsT+m2QanGb7CUIQmgFSzQmw+BVyxKgK1wj9Gl3yWCSh+c9cxQ+Y2uByNAjDG3GPayKSrBlTQ70C3w123qKIJA9ZxkCvKMus9LOARurTfJ/nc',
            'Västra Götaland': 'oJ/Yw8gzqEoIEGRc++9S1wFoay2PsOEZfbx/OK6SkZepujV8HZPIdOJBjGbRiTtugpDZlETtNb0nrrNBSmWJ1fO1tA9qVbqXiJtVtlEDuFwNvApN2nx8CO24H8A+In9qMKCB/i7eLrM8ZDKYhFf9UlRhLSK9N3o74+U4bF8ViP6BOc1hcxetFvvSRhgrh8mXMZBcrVs4WxNDPxuafW9YmcdGbjoK//Qy0uKf5N1KBEY=',
            'Örebro': 'oJ/Yw8gzqEriJndjWkYOAIWK/WY55u0KXgzA2XdGRhXpiDqA3r8kQyIEo+eTXxtHzbizl7L2VnH3i0j7IcRPLvcK2NLnk5ITnrn1FCQKLKfah3dv+FsUUZs3tjf3qSxnEYnZJWolKBdggTuCmy5SsidXOLUb7OpKt4rKkBoaCYypi1zW+xf4YsoA82NTlEYyo1SpSKad8fqyVrq/jYG/xw==',
            'Östergötland': 'oJ/Yw8gzqEoK6i/vq38qNznuSDQ9QTCQFWKiBr/AsnRjzxzD7mN2z+Ov5mv4ExfKCgwJkQbTP6pk+P8O0MOOK6Zk80+br+dnPelTwq1d88/CEYXoWEt6bq9SMXyz8idr+zB5i86p2CqE48kfJrofqaThXNIC8Bw8j8MiMNa96cU6XrIA7h13ylgRKJ/s1VVsCVPrga7RJkB2+NTa+PWeWH/r1G84IhZ6Sd6mP9mlmYE='
        }
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime object"""
        return parse_date(date_str)
    
    async def fetch_case_details(self, case_number: str, case_id: str = None) -> Dict[str, Any]:
        """
        Fetch detailed information for a specific case
        Args:
            case_number: The case number (Diarienummer) e.g. "13649-2014"
            case_id: The numeric ID from data-case-id attribute
        """
        max_retries = 3
        base_delay = 2
        
        if not case_id:
            logger.error(f"No case_id provided for case number: {case_number}")
            return None
        
        async with aiohttp.ClientSession() as session:
            for attempt in range(max_retries):
                try:
                    # Calculate delay with exponential backoff and jitter
                    delay = base_delay * (2 ** attempt)
                    jitter = random.uniform(0, delay * 0.1)
                    logger.info(f"Waiting {delay + jitter:.1f}s before attempt {attempt + 1}")
                    await asyncio.sleep(delay + jitter)
                    
                    # Get case details using the case_id
                    case_url = f"{self.base_url}/Case/CaseInfo.aspx?caseID={case_id}"
                    logger.info(f"Getting case details from {case_url}")
                    
                    async with session.get(case_url, headers=self.headers) as case_response:
                        if case_response.status == 200:
                            case_html = await case_response.text()
                            case_soup = BeautifulSoup(case_html, 'html.parser')
                            
                            # Parse details
                            tables = case_soup.find_all('table')
                            if not tables:
                                logger.error("No tables found in case details")
                                continue
                            
                            # Parse overview details
                            details = {}
                            overview_table = tables[0]
                            rows = overview_table.find_all('tr')
                            logger.info(f"Found {len(rows)} rows in overview table")
                            for row in rows:
                                cells = row.find_all('td')
                                if len(cells) == 2:
                                    key = cells[0].get_text(strip=True)
                                    value = cells[1].get_text(strip=True)
                                    details[key] = value
                            
                            # Extract documents from the second table
                            documents = []
                            if len(tables) > 1:
                                documents_table = tables[1]
                                doc_rows = documents_table.find_all('tr')[1:]  # Skip header
                                logger.info(f"Found {len(doc_rows)} document rows")
                                for doc_row in doc_rows:
                                    cells = doc_row.find_all('td')
                                    if len(cells) >= 4:
                                        doc_link = cells[1].find('a')
                                        doc_url = f"{self.base_url}/{doc_link['href']}" if doc_link and 'href' in doc_link.attrs else None
                                        document = {
                                            'id': cells[0].get_text(strip=True),
                                            'title': cells[1].get_text(strip=True),
                                            'date': cells[2].get_text(strip=True),
                                            'sender': cells[3].get_text(strip=True),
                                            'url': doc_url
                                        }
                                        documents.append(document)
                            
                            # Parse dates
                            decision_date = self._parse_date(details.get('Beslutsdatum'))
                            
                            # Create result
                            result = {
                                'id': details.get('Diarienummer', ''),
                                'case_id': case_id,
                                'diarium': details.get('Diarium', ''),
                                'date': self._parse_date(details.get('In/Upp-datum', '')),
                                'title': details.get('Ärenderubrik', ''),
                                'status': details.get('Status', ''),
                                'decision_date': decision_date,
                                'sender': details.get('Avsändare/mottagare', ''),
                                'municipality': details.get('Kommun', ''),
                                'documents': documents,
                                'url': case_url
                            }
                            
                            # Verify we got the right case
                            if result['id'] and case_number in result['id']:
                                logger.info("Successfully parsed case details")
                                return result
                            else:
                                logger.error(f"Found wrong case: {result['id']} (expected {case_number})")
                                continue
                        else:
                            logger.error(f"Failed to get case details: {case_response.status}")
                            continue
                
                except Exception as e:
                    logger.error(f"Error on attempt {attempt + 1}: {str(e)}")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        raise Exception(f"Max retries reached: {str(e)}")
        
        return None

    def _extract_case_details(self, case_details_div):
        """Extract case details from the HTML"""
        details = {}
        
        # Extract basic information
        for field in case_details_div.find_all('div', {'class': 'field'}):
            label = field.find('label')
            value = field.find('span', {'class': 'value'})
            if label and value:
                key = label.get_text(strip=True)
                details[key] = value.get_text(strip=True)
        
        # Extract documents
        documents_table = case_details_div.find('table', {'class': 'documents'})
        if documents_table:
            documents = []
            for row in documents_table.find_all('tr')[1:]:  # Skip header row
                cells = row.find_all('td')
                if len(cells) >= 4:
                    doc = {
                        'id': cells[0].get_text(strip=True),
                        'title': cells[1].get_text(strip=True),
                        'date': cells[2].get_text(strip=True),
                        'sender': cells[3].get_text(strip=True),
                        'url': cells[1].find('a')['href'] if cells[1].find('a') else None
                    }
                    documents.append(doc)
            details['documents'] = documents
        
        return details

    async def _get_next_page_data(self, html_content: str) -> dict:
        """Extract the next page data from the HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the pagination footer
        pagination = soup.find('tfoot')
        if not pagination:
            logger.info("No pagination found")
            return None
            
        # Find the current page number
        current_page_span = pagination.find('span')
        if not current_page_span:
            logger.info("No current page span found")
            return None
            
        current_page = int(current_page_span.text)
        logger.info(f"Current page: {current_page}")
        
        # Find all page links
        page_links = pagination.find_all('a')
        if not page_links:
            logger.info("No page links found")
            return None
        
        # Check if we have a "next" page link or ellipsis link
        next_page_link = None
        for link in page_links:
            # Look for direct next page link
            if link.text.strip() == str(current_page + 1):
                next_page_link = link
                break
            # Look for ellipsis link
            elif link.text.strip() == "..." and 'Page$' in link.get('href', ''):
                next_page_link = link
                break
        
        # If we don't have a next page link, we've reached the end
        if not next_page_link:
            logger.info(f"No link found for page {current_page + 1}")
            return None
        
        # Get the href attribute
        href = next_page_link.get('href', '')
        if 'javascript:__doPostBack' not in href:
            logger.info("No postback found in href")
            return None
        
        logger.info(f"Found next page link: {href}")
        
        # Extract the target and argument
        target = href.split("'")[1]
        argument = href.split("'")[3]
        
        # Get the ASP.NET form fields
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})
        viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
        eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})
        
        if viewstate and viewstategenerator and eventvalidation:
            return {
                '__VIEWSTATE': viewstate['value'],
                '__VIEWSTATEGENERATOR': viewstategenerator['value'],
                '__EVENTVALIDATION': eventvalidation['value'],
                '__EVENTTARGET': target,
                '__EVENTARGUMENT': argument
            }
        
        logger.info("Missing ASP.NET form fields")
        return None

    async def fetch_data(self, lan: Union[str, List[str]], from_date: str = None, to_date: str = None, page: int = 1) -> Dict[str, Any]:
        """
        Fetch data for a specific län
        Args:
            lan: The län to fetch data for
            from_date: Optional start date filter
            to_date: Optional end date filter
            page: The page number to fetch (1-based)
        """
        try:
            # Handle lan parameter being a list
            if isinstance(lan, list):
                lan = lan[0] if lan else None
                
            if lan not in self.lan_queries:
                logger.error(f"Unknown län name: {lan}")
                return {
                    "source": self.source_name,
                    "pagination": {
                        "current_page": page,
                        "total_pages": 0,
                        "total_items": 0,
                        "items_per_page": 50,
                        "has_next": False,
                        "has_previous": page > 1
                    },
                    "projects": []
                }
            
            url = f"{self.base_url}/Case/CaseSearchResult.aspx?query={self.lan_queries[lan]}"
            current_page = 1
            html_content = None
            
            async with aiohttp.ClientSession() as session:
                # Get the initial page
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch initial page: {response.status}")
                        return []
                    
                    html_content = await response.text()
                
                # If we need a page other than the first one, navigate to it
                while current_page < page:
                    next_page_data = await self._get_next_page_data(html_content)
                    if not next_page_data:
                        logger.info(f"No more pages found after page {current_page}")
                        return {
                            "source": self.source_name,
                            "pagination": {
                                "current_page": current_page,
                                "total_pages": current_page,
                                "total_items": current_page * 50,
                                "items_per_page": 50,
                                "has_next": False,
                                "has_previous": current_page > 1
                            },
                            "projects": []
                        }
                    
                    # Add delay between requests
                    await asyncio.sleep(random.uniform(1, 2))
                    
                    # Make the POST request for the next page
                    async with session.post(url, data=next_page_data, headers=self.headers) as post_response:
                        if post_response.status != 200:
                            logger.error(f"Failed to fetch page {current_page + 1}")
                            break
                        
                        html_content = await post_response.text()
                        current_page += 1
                
                # Parse the current page results
                results = await self._parse_search_results(html_content)
                logger.info(f"Found {len(results)} results on page {current_page}")
                
                # Check if there's a next page
                has_next = await self._get_next_page_data(html_content) is not None
                
                # Format results according to spec
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        'id': result['id'],
                        'case_id': result.get('case_id'),
                        'title': result['title'],
                        'date': result['date'].strftime('%Y-%m-%d') if result['date'] else None,
                        'location': result['location'],
                        'municipality': result['municipality'],
                        'status': result['status'],
                        'url': result['url'],
                        'lan': lan,
                        'sender': result.get('sender'),
                        'decision_date': result['decision_date'].strftime('%Y-%m-%d') if result.get('decision_date') else None,
                        'last_updated_from_source': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'details_fetched': False,
                        'details_fetch_attempts': 0
                    })
                
                # Return in the expected format with proper pagination
                return {
                    "source": self.source_name,
                    "pagination": {
                        "current_page": page,
                        "total_pages": page if not has_next else page + 1,  # Minimum known pages
                        "total_items": page * 50,  # Minimum known items
                        "items_per_page": 50,
                        "has_next": has_next,
                        "has_previous": page > 1
                    },
                    "projects": formatted_results
                }
            
        except Exception as e:
            logger.error(f"Error fetching data for {lan}: {str(e)}")
            return {
                "source": self.source_name,
                "pagination": {
                    "current_page": page,
                    "total_pages": 0,
                    "total_items": 0,
                    "items_per_page": 50,
                    "has_next": False,
                    "has_previous": page > 1
                },
                "projects": []
            }

    async def _parse_search_results(self, html: str) -> List[Dict[str, Any]]:
        """Parse search results HTML and extract case information"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # Find the results table
            table = soup.find('table', {'id': 'SearchPlaceHolder_caseGridView'})
            if not table:
                logger.warning("No results table found in HTML")
                logger.debug(f"HTML snippet: {html[:500]}...")
                return []
            
            # Find all rows except header and pagination
            rows = table.find_all('tr')
            data_rows = []
            for row in rows:
                # Skip header rows (contain th) and footer rows (contain colspan)
                if not row.find('th') and not row.find('td', attrs={'colspan': True}):
                    data_rows.append(row)
            
            for row in data_rows:
                try:
                    cells = row.find_all('td')
                    if len(cells) >= 8:  # We expect 8 columns based on the HTML
                        # Extract case ID and URL from first cell
                        case_link = cells[0].find('a', class_='sv-font-brodtext-med-bla-lankning')
                        if not case_link:
                            logger.debug("No case link found in first cell")
                            continue
                        
                        case_id = case_link.get_text(strip=True)
                        case_url = f"{self.base_url}/Case/{case_link['href']}" if case_link.get('href') else None
                        logger.debug(f"Found case: {case_id} with URL: {case_url}")
                        
                        # Extract case_id from href if available
                        case_id_match = None
                        if case_url:
                            case_id_match = re.search(r'caseID=(\d+)', case_url)
                        
                        # Extract cell contents with debug logging
                        status = cells[1].get_text(strip=True)
                        date_str = cells[2].get_text(strip=True)  # In/Upp-datum
                        title = cells[3].get_text(strip=True)  # Ärenderubrik
                        sender = cells[4].get_text(strip=True)  # Avsändare/mottagare
                        location = cells[5].get_text(strip=True)  # Postort
                        municipality = cells[6].get_text(strip=True)  # Kommun
                        decision_date_str = cells[7].get_text(strip=True)  # Beslutsdatum
                        
                        logger.debug(f"Raw date strings: date={date_str}, decision_date={decision_date_str}")
                        
                        # Parse dates
                        date = self._parse_date(date_str)
                        decision_date = self._parse_date(decision_date_str)
                        
                        case = {
                            'id': case_id,
                            'case_id': case_id_match.group(1) if case_id_match else None,
                            'date': date,
                            'decision_date': decision_date,
                            'title': title,
                            'status': status,
                            'sender': sender,
                            'location': location,
                            'municipality': municipality,
                            'url': case_url
                        }
                        
                        results.append(case)
                        logger.debug(f"Successfully parsed case: {case}")
                        
                except Exception as e:
                    logger.error(f"Error parsing search result row: {str(e)}")
                    logger.debug(f"Row HTML: {row}")
                    continue
            
            logger.debug(f"Successfully parsed {len(results)} results from HTML")
            return results
            
        except Exception as e:
            logger.error(f"Error parsing search results: {str(e)}")
            return []
