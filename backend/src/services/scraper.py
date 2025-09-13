"""Enhanced web scraping service with better error handling and domain intelligence."""
from __future__ import annotations
import re
import asyncio
import logging
import os
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
import trafilatura
from tavily import TavilyClient

from ..core.models import SourceDoc, SourceType, SkillDomain
from ..core.config import ScrapingConfig
from ..core.exceptions import ScrapingError

logger = logging.getLogger(__name__)


class DomainClassifier:
    """Classifies content domain and relevance."""
    
    DOMAIN_KEYWORDS = {
        SkillDomain.MARTIAL_ARTS: [
            "martial arts", "karate", "kung fu", "taekwondo", "judo", "jujitsu", 
            "boxing", "muay thai", "kickboxing", "mma", "fighting", "combat",
            "punch", "kick", "strike", "block", "stance", "form", "kata"
        ],
        SkillDomain.SPORTS: [
            "sport", "athletic", "training", "exercise", "fitness", "workout",
            "technique", "performance", "competition", "coach", "drill"
        ],
        SkillDomain.MUSIC: [
            "music", "instrument", "piano", "guitar", "violin", "drums",
            "chord", "scale", "rhythm", "melody", "practice", "lesson"
        ],
        SkillDomain.CRAFTS: [
            "craft", "woodworking", "pottery", "knitting", "sewing", "art",
            "handmade", "diy", "tutorial", "project", "skill", "technique"
        ]
    }
    
    def classify_domain(self, text: str, query: str) -> SkillDomain:
        """Classify the domain of the content."""
        combined_text = f"{query} {text}".lower()
        
        domain_scores = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in combined_text)
            domain_scores[domain] = score
        
        if not domain_scores or max(domain_scores.values()) == 0:
            return SkillDomain.GENERAL
        
        return max(domain_scores, key=domain_scores.get)
    
    def calculate_relevance(self, text: str, query: str, domain: SkillDomain) -> float:
        """Calculate domain relevance score."""
        if domain == SkillDomain.GENERAL:
            return 0.5
        
        keywords = self.DOMAIN_KEYWORDS.get(domain, [])
        combined_text = f"{query} {text}".lower()
        
        matches = sum(1 for keyword in keywords if keyword in combined_text)
        return min(1.0, matches / len(keywords) * 2)


class SourceWeighter:
    """Calculates source reliability weights."""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.trust_patterns = [
            (re.compile(pattern), weight) 
            for pattern, weight in config.trust_domains.items()
        ]
    
    def calculate_weight(self, url: str, content_length: int, source_type: SourceType) -> float:
        """Calculate source reliability weight."""
        # Base weight from content length
        if content_length > 2000:
            base_weight = 0.4
        elif content_length > 1000:
            base_weight = 0.3
        else:
            base_weight = 0.2
        
        # Domain trust boost
        for pattern, boost in self.trust_patterns:
            if pattern.search(url):
                base_weight += boost
        
        # Source type modifier
        type_modifiers = {
            SourceType.ACADEMIC: 0.2,
            SourceType.WEB: 0.0,
            SourceType.VIDEO: -0.1,
            SourceType.MANUAL: 0.15
        }
        base_weight += type_modifiers.get(source_type, 0.0)
        
        return max(0.1, min(0.95, base_weight))


class ContentExtractor:
    """Extracts and cleans content from HTML."""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
    
    def extract_text(self, html: str) -> str:
        """Extract clean text from HTML."""
        # Try trafilatura first (better for articles)
        main_content = trafilatura.extract(html)
        if main_content and len(main_content) >= self.config.min_content_length:
            return main_content[:self.config.max_content_length]
        
        # Fallback to BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
            element.decompose()
        
        text = soup.get_text(" ", strip=True)
        return text[:self.config.max_content_length]
    
    def extract_title(self, html: str, url: str) -> str:
        """Extract page title."""
        soup = BeautifulSoup(html, "lxml")
        
        # Try various title sources
        title_candidates = [
            soup.find("title"),
            soup.find("h1"),
            soup.find("meta", property="og:title"),
            soup.find("meta", name="twitter:title")
        ]
        
        for candidate in title_candidates:
            if candidate:
                title = candidate.get("content") if candidate.name == "meta" else candidate.get_text()
                if title and title.strip():
                    return title.strip()[:140]
        
        return urlparse(url).netloc


class WebScraper:
    """Enhanced web scraper with domain intelligence."""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.domain_classifier = DomainClassifier()
        self.source_weighter = SourceWeighter(config)
        self.content_extractor = ContentExtractor(config)
        
        # Initialize Tavily client
        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            raise ScrapingError("TAVILY_API_KEY not found in environment variables. Please set this required environment variable.")
        
        self.tavily_client = TavilyClient(api_key=tavily_api_key)
    
    async def search(self, query: str, max_results: int = 10) -> List[str]:
        """Search using Tavily API and return URLs."""
        try:
            # Use Tavily's search API
            response = self.tavily_client.search(
                query=query,
                search_depth="basic",  # Can be "basic" or "advanced"
                max_results=max_results,
                include_domains=None,  # Can specify trusted domains if needed
                exclude_domains=None,
                include_answer=False,  # We don't need the AI-generated answer
                include_raw_content=False,  # We'll fetch content ourselves
                include_images=False
            )
            
            urls = []
            if "results" in response:
                for result in response["results"]:
                    if "url" in result:
                        urls.append(result["url"])
            
            # Prioritize trusted domains
            trusted_urls = [u for u in urls if any(
                pattern.search(u) for pattern, _ in self.source_weighter.trust_patterns
            )]
            other_urls = [u for u in urls if u not in trusted_urls]
            
            return (trusted_urls + other_urls)[:max_results]
            
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            raise ScrapingError(f"Search failed: {e}")
    
    async def fetch_document(self, client: httpx.AsyncClient, url: str, query: str) -> Optional[SourceDoc]:
        """Fetch and process a single document."""
        try:
            response = await client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": self.config.user_agent}
            )
            response.raise_for_status()
            
            html = response.text
            text = self.content_extractor.extract_text(html)
            
            if len(text) < self.config.min_content_length:
                logger.debug(f"Content too short for {url}: {len(text)} chars")
                return None
            
            title = self.content_extractor.extract_title(html, url)
            snippet = text[:400]
            
            # Determine source type
            source_type = SourceType.WEB
            if any(domain in url for domain in [".edu", "arxiv.org", "pubmed"]):
                source_type = SourceType.ACADEMIC
            elif any(domain in url for domain in ["youtube.com", "vimeo.com"]):
                source_type = SourceType.VIDEO
            
            # Calculate metrics
            weight = self.source_weighter.calculate_weight(url, len(text), source_type)
            confidence = min(0.95, weight + (0.05 if len(text) > 2000 else 0))
            
            # Domain classification
            domain = self.domain_classifier.classify_domain(text, query)
            domain_relevance = self.domain_classifier.calculate_relevance(text, query, domain)
            
            return SourceDoc(
                url=url,
                title=title,
                snippet=snippet,
                text=text,
                weight=weight,
                confidence=confidence,
                source_type=source_type,
                domain_relevance=domain_relevance
            )
            
        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            return None
    
    async def scrape_query(self, query: str, max_sources: int = 5) -> List[SourceDoc]:
        """Scrape sources for a query with enhanced processing."""
        if not self.config.allow_web:
            logger.info("Web scraping disabled by configuration")
            return []
        
        try:
            # Search for URLs
            urls = await self.search(query, max_sources * 2)
            if not urls:
                logger.warning(f"No URLs found for query: {query}")
                return []
            
            # Fetch documents concurrently
            documents = []
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                tasks = [self.fetch_document(client, url, query) for url in urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, SourceDoc):
                        documents.append(result)
                    elif isinstance(result, Exception):
                        logger.debug(f"Document fetch failed: {result}")
            
            if not documents:
                logger.warning(f"No documents successfully fetched for query: {query}")
                return []
            
            # Sort by quality score and return top results
            documents.sort(key=lambda d: d.quality_score, reverse=True)
            return documents[:max_sources]
            
        except Exception as e:
            logger.error(f"Scraping failed for query '{query}': {e}")
            raise ScrapingError(f"Scraping failed: {e}")
