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
from openai import AsyncOpenAI

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
        
        # Initialize both sync and async clients
        self.client = OpenAI(
            api_key=self.api_key,
            timeout=30.0,
            max_retries=3
        )
        self.async_client = AsyncOpenAI(
            api_key=self.api_key,
            timeout=30.0,
            max_retries=3
        )
        self.model = "gpt-4o-mini" # gpt-4o-mini is the best model for this task
        
        # Define available categories for green industrial projects
        self.categories = [
            'Wind Power',
            'Solar Power',
            'Hydrogen Production',
            'Battery Manufacturing',
            'Green Steel',
            'Other Green Industry',
            'Not Relevant'
        ]
        
        # Project phases
        self.phases = [
            'Planning',
            'Construction',
            'Operational',
            'Maintenance',
            'Decommissioning'
        ]
        
        # Initialize rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests

    def _wait_for_rate_limit(self):
        """Simple rate limiting."""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()

    async def _make_openai_request(self, prompt: str) -> str:
        """Make a request to OpenAI API with rate limiting."""
        self._wait_for_rate_limit()
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You analyze if cases are green industrial projects. Respond only with the requested JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise

    async def _categorize_case(self, case: Case) -> Tuple[Case, bool, str]:
        """Categorize a single case using OpenAI API."""
        try:
            logger.info(f"Categorizing case: {case.id}")
            prompt = self._create_categorization_prompt(case.title, case.description or "")
            response = await self._make_openai_request(prompt)
            
            try:
                result = json.loads(response)
                
                if not result.get("is_relevant", False):
                    case.primary_category = "Not Relevant"
                    case.category_confidence = 0.9
                    case.is_medla_suitable = False
                    return case, True, ""

                details = result.get("details", {})
                case.primary_category = details.get("primary_category")
                case.project_phase = details.get("project_phase")
                case.is_medla_suitable = details.get("is_medla_suitable", False)
                case.category_confidence = details.get("confidence", 0.0)
                case.potential_jobs = details.get("potential_jobs", [])
                case.last_categorized_at = datetime.utcnow()
                
                return case, True, ""
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse response: {response}")
                case.primary_category = "Error"
                case.category_confidence = 0.0
                case.is_medla_suitable = False
                return case, False, f"Failed to parse response: {str(e)}"
                
        except Exception as e:
            logger.error(f"Error categorizing case {case.id}: {str(e)}")
            case.primary_category = "Error"
            case.category_confidence = 0.0
            case.is_medla_suitable = False
            return case, False, str(e)

    async def batch_categorize_with_progress(self, db: Session, batch_size: int = 50, min_confidence: float = 0.7):
        """Process a batch of cases and yield progress updates."""
        logger.info("Starting batch categorization")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"Minimum confidence threshold: {min_confidence}")
        
        cases = db.query(Case).filter(
            (Case.primary_category.is_(None)) |
            (Case.category_confidence < min_confidence)
        ).limit(batch_size).all()
        
        total_cases = len(cases)
        logger.info(f"Found {total_cases} cases to process")
        
        if total_cases == 0:
            yield {
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "total_cases": 0,
                "status": "completed",
                "progress_percentage": 100,
                "categories": {},
                "errors": []
            }
            return

        results = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "total_cases": total_cases,
            "status": "in_progress",
            "progress_percentage": 0,
            "categories": {},
            "errors": []
        }
        
        start_time = time.time()
        
        # Process in smaller batches
        batch_size = 3
        for i in range(0, total_cases, batch_size):
            batch = cases[i:i + batch_size]
            tasks = [self._categorize_case(case) for case in batch]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for case, success, error in batch_results:
                if isinstance(case, Exception):
                    results["failed"] += 1
                    results["errors"].append(f"Unexpected error: {str(case)}")
                    continue

                if success:
                    results["successful"] += 1
                    category = case.primary_category
                    results["categories"][category] = results["categories"].get(category, 0) + 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Case {case.id}: {error}")
                
                results["processed"] += 1
                results["progress_percentage"] = int((results["processed"] / total_cases) * 100)
                
                # Calculate time remaining
                elapsed_time = time.time() - start_time
                if results["processed"] > 0:
                    avg_time_per_case = elapsed_time / results["processed"]
                    remaining_cases = total_cases - results["processed"]
                    results["estimated_time_remaining"] = int(avg_time_per_case * remaining_cases)
                
                # Commit changes for this batch
                try:
                    db.commit()
                except Exception as e:
                    logger.error(f"Database error: {str(e)}")
                    results["errors"].append(f"Database error: {str(e)}")
                
                yield results
            
            # Small delay between batches
            await asyncio.sleep(0.5)
        
        # Set final status
        if results["failed"] == total_cases:
            results["status"] = "failed"
        elif results["failed"] > 0:
            results["status"] = "completed_with_errors"
        else:
            results["status"] = "completed"
        
        results["total_time"] = int(time.time() - start_time)
        results["estimated_time_remaining"] = None
        
        yield results

    async def batch_categorize(self, db: Session, batch_size: int = 50, min_confidence: float = 0.7):
        """Process a batch of cases and return final results."""
        async for progress in self.batch_categorize_with_progress(db, batch_size, min_confidence):
            if progress["status"] in ["completed", "failed", "completed_with_errors"]:
                return progress
        return {"status": "failed", "error": "No results generated"}

    def _create_categorization_prompt(self, case_title: str, case_description: str) -> str:
        return f"""Analyze if this case is a green industrial project suitable for Medla's local job matching service.
Title: {case_title}
Description: {case_description}

Respond with a JSON object containing:
{{
    "is_relevant": boolean,  // True if this is a green industrial project
    "details": {{  // Only include if is_relevant is True
        "primary_category": string,  // One of: Wind Power, Solar Power, Hydrogen Production, Battery Manufacturing, Green Steel, Other Green Industry
        "project_phase": string,  // One of: Planning, Construction, Operational, Maintenance, Decommissioning
        "is_medla_suitable": boolean,
        "confidence": float,  // 0.0-1.0
        "potential_jobs": string[]  // Max 3 job types
    }}
}}"""

    def categorize_case(self, case: Case) -> Tuple[str, str, float, Dict]:
        """Categorize a single case using gpt-4o-mini."""
        try:
            logger.info(f"Categorizing case: {case.id}")
            
            prompt = self._create_categorization_prompt(case.title, case.description or "")
            response = self._make_openai_request(prompt)
            content = response.choices[0].message.content
            
            try:
                parsed = self._parse_response(content)
                primary_category = parsed.get("primary_category", "Not Relevant")
                confidence = float(parsed.get("confidence", 0.5))
                project_phase = parsed.get("project_phase", "Unknown")
                is_medla_suitable = parsed.get("is_medla_suitable", False)
                reasoning = parsed.get("reasoning", "No reasoning provided")
                potential_jobs = parsed.get("potential_job_opportunities", [])

                if primary_category not in self.categories:
                    primary_category = "Not Relevant"
                
                if project_phase not in self.phases:
                    project_phase = "Unknown"
                
                logger.info(f"Result: {primary_category} ({confidence:.2f}) - Medla suitable: {is_medla_suitable}")
                
                return (
                    primary_category,
                    project_phase,
                    confidence,
                    {
                        "reasoning": reasoning,
                        "is_medla_suitable": is_medla_suitable,
                        "potential_jobs": potential_jobs
                    }
                )

            except Exception as e:
                logger.error(f"Failed to parse response: {content}")
                return "Error", "Unknown", 0.0, {
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
