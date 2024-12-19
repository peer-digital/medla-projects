import openai
from typing import Dict, Tuple, Optional, List
from datetime import datetime
import json
from sqlalchemy.orm import Session
from app.models.models import Case
import logging
import time
from tenacity import retry, stop_after_attempt, wait_exponential
import os
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError, RateLimitError, APIError
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# Load environment variables from .env file
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class CategorizationService:
    def __init__(self, api_key: str = None):
        # Use provided API key or fall back to environment variable
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file")
        
        self.client = OpenAI(
            api_key=self.api_key,
            timeout=30.0,
            max_retries=3
        )
        self.model = "gpt-4o-mini"
        
        # Define available categories
        self.categories = ['Energy', 'Manufacturing', 'Infrastructure', 'Resource Extraction', 'Other']
        
        # Initialize thread pool for concurrent processing
        self.executor = ThreadPoolExecutor(max_workers=3)  # Limit concurrent requests
        
        # Initialize rate limiting
        self.request_times = []
        self.max_requests_per_minute = 50  # Adjust based on your API limits
    
    def _wait_for_rate_limit(self):
        """Implement rate limiting."""
        now = time.time()
        minute_ago = now - 60
        
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if t > minute_ago]
        
        if len(self.request_times) >= self.max_requests_per_minute:
            sleep_time = self.request_times[0] - minute_ago
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        self.request_times.append(now)

    def _process_case_batch(self, cases: List[Case], db: Session) -> List[Tuple[Case, bool, str]]:
        """Process a batch of cases concurrently."""
        futures = []
        for case in cases:
            future = self.executor.submit(self.update_case_categorization, db, case)
            futures.append((case, future))
        
        results = []
        for case, future in futures:
            try:
                updated_case = future.result()
                success = updated_case.primary_category != "Error"
                error = updated_case.category_metadata.get("error", "") if not success else ""
                results.append((updated_case, success, error))
            except Exception as e:
                results.append((case, False, str(e)))
        
        return results

    def _create_categorization_prompt(self, case: Case) -> str:
        """Create a prompt for the GPT model to categorize a case."""
        # Build a minimal but informative text for categorization
        text = case.title
        if case.description:
            text += f". {case.description}"
        if case.decision_summary:
            text += f". {case.decision_summary}"

        prompt = f"""Categorize as one of: {', '.join(self.categories)}. Return JSON only:
{text}

Format: {{"primary_category": "category", "confidence": 0.0-1.0, "reasoning": "brief"}}"""
        return prompt

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _make_openai_request(self, user_prompt_message: str):
        """Make an OpenAI API request with retry logic."""
        try:
            logger.info("Making OpenAI API request")
            
            # Implement rate limiting
            self._wait_for_rate_limit()
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You categorize industrial projects. Be concise."
                    },
                    {
                        "role": "user",
                        "content": user_prompt_message
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=100,   # Limit response length
                presence_penalty=0,
                frequency_penalty=0
            )
            return completion

        except RateLimitError as e:
            error_msg = str(e)
            if "insufficient_quota" in error_msg or "exceeded your current quota" in error_msg:
                logger.error("API quota exceeded")
                raise APIError("API quota exceeded") from e
            else:
                logger.warning(f"Rate limit hit: {error_msg}")
                raise
        except APIError as e:
            logger.error(f"API error: {str(e)}")
            raise

    def _parse_response(self, content: str) -> dict:
        """Parse the GPT response, handling potential markdown formatting."""
        content = content.strip()
        if content.startswith('```'):
            start = content.find('\n') + 1
            end = content.rfind('```')
            if end == -1:
                end = len(content)
            content = content[start:end].strip()
        
        if content.startswith('json'):
            content = content[4:].strip()
        
        return json.loads(content)

    def categorize_case(self, case: Case) -> Tuple[str, str, float, Dict]:
        """Categorize a single case using gpt-4o-mini."""
        try:
            logger.info(f"Categorizing case: {case.id}")
            
            prompt = self._create_categorization_prompt(case)
            response = self._make_openai_request(prompt)
            content = response.choices[0].message.content
            
            try:
                parsed = self._parse_response(content)
                primary_category = parsed.get("primary_category", "Other")
                confidence = float(parsed.get("confidence", 0.5))
                reasoning = parsed.get("reasoning", "No reasoning provided")

                if primary_category not in self.categories:
                    primary_category = "Other"
                
                logger.info(f"Result: {primary_category} ({confidence:.2f})")
                
                return (
                    primary_category,
                    "N/A",
                    confidence,
                    {"reasoning": reasoning}
                )

            except Exception as e:
                logger.error(f"Failed to parse response: {content}")
                return "Error", "N/A", 0.0, {
                    "error": "Failed to parse response",
                    "raw_response": content
                }
                
        except (RateLimitError, APIError) as e:
            error_msg = str(e)
            if "insufficient_quota" in error_msg or "exceeded your current quota" in error_msg:
                return "Error", "N/A", 0.0, {
                    "error": "API quota exceeded",
                    "recoverable": False
                }
            else:
                return "Error", "N/A", 0.0, {
                    "error": str(e),
                    "recoverable": True
                }
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return "Error", "N/A", 0.0, {"error": str(e)}

    def update_case_categorization(self, db: Session, case: Case) -> Case:
        """Update the categorization for a single case."""
        primary_category, sub_category, confidence, metadata = self.categorize_case(case)
        
        case.primary_category = primary_category
        case.sub_category = sub_category
        case.category_confidence = confidence
        case.category_metadata = metadata
        case.last_categorized_at = datetime.utcnow()
        
        db.commit()
        return case

    def batch_categorize_with_progress(self, db: Session, batch_size: int = 50, min_confidence: float = 0.7):
        """Process a batch of cases with concurrent processing and yield progress updates."""
        logger.info("Starting batch categorization")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"Minimum confidence threshold: {min_confidence}")
        
        cases = db.query(Case).filter(
            (Case.primary_category.is_(None)) |
            (Case.category_confidence < min_confidence)
        ).limit(batch_size).all()
        
        total_cases = len(cases)
        logger.info(f"Found {total_cases} cases to process")
        
        results = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "quota_exceeded": False,
            "categories": {},
            "errors": [],
            "total_cases": total_cases,
            "status": "in_progress",
            "progress_percentage": 0,
            "estimated_time_remaining": None
        }
        
        start_time = time.time()
        
        # Process cases in smaller batches for better concurrency
        batch_size = 3  # Process 3 cases at a time
        for i in range(0, total_cases, batch_size):
            case_batch = cases[i:i + batch_size]
            batch_results = self._process_case_batch(case_batch, db)
            
            for updated_case, success, error in batch_results:
                if error and "quota exceeded" in error.lower():
                    results["quota_exceeded"] = True
                    results["errors"].append(f"Case {updated_case.id}: API quota exceeded")
                    results["status"] = "quota_exceeded"
                    yield results
                    return
                
                if not success:
                    results["failed"] += 1
                    results["errors"].append(f"Case {updated_case.id}: {error}")
                else:
                    results["successful"] += 1
                    category = updated_case.primary_category
                    if category not in results["categories"]:
                        results["categories"][category] = 0
                    results["categories"][category] += 1
                
                results["processed"] += 1
                results["progress_percentage"] = int((results["processed"] / total_cases) * 100)
                
                # Calculate estimated time remaining
                if results["processed"] > 1:
                    elapsed_time = time.time() - start_time
                    avg_time_per_case = elapsed_time / results["processed"]
                    remaining_cases = total_cases - results["processed"]
                    results["estimated_time_remaining"] = int(avg_time_per_case * remaining_cases)
                
                yield results
        
        # Set final status
        if results["quota_exceeded"]:
            results["status"] = "quota_exceeded"
        elif results["failed"] == total_cases:
            results["status"] = "failed"
        elif results["failed"] > 0:
            results["status"] = "completed_with_errors"
        else:
            results["status"] = "completed"
        
        results["total_time"] = int(time.time() - start_time)
        results["estimated_time_remaining"] = None
        
        yield results

    def batch_categorize(self, db: Session, batch_size: int = 50, min_confidence: float = 0.7) -> Dict:
        """Process a batch of cases using the generator and return final results."""
        results = None
        for progress in self.batch_categorize_with_progress(db, batch_size, min_confidence):
            results = progress
        return results or {"status": "failed", "error": "No results generated"}
