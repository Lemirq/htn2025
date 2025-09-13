"""Enhanced LLM agent service with better error handling and structured processing."""
from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import asdict
import asyncio

from ..core.models import SourceDoc, SkillGuide, SkillStep, SkillDomain
from ..core.config import LLMConfig
from ..core.exceptions import LLMError, ValidationError

logger = logging.getLogger(__name__)

try:
    import cohere
except ImportError:
    cohere = None
    logger.warning("Cohere package not available, using fallback mode")


class GuideValidator:
    """Validates and sanitizes LLM-generated guides."""
    
    REQUIRED_FIELDS = [
        "title", "prerequisites", "safety", "equipment", 
        "core_principles", "steps", "evaluation"
    ]
    
    def validate_guide_structure(self, data: Dict[str, Any]) -> None:
        """Validate that guide has required structure."""
        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in data]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {missing_fields}")
        
        if not isinstance(data["steps"], list) or len(data["steps"]) == 0:
            raise ValidationError("Guide must have at least one step")
        
        for i, step in enumerate(data["steps"]):
            required_step_fields = ["name", "how", "why"]
            missing_step_fields = [field for field in required_step_fields if field not in step]
            if missing_step_fields:
                raise ValidationError(f"Step {i} missing fields: {missing_step_fields}")
    
    def sanitize_guide(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and sanitize guide data."""
        # Ensure lists are actually lists
        list_fields = ["prerequisites", "safety", "equipment", "core_principles", "evaluation"]
        for field in list_fields:
            if field in data and not isinstance(data[field], list):
                data[field] = [str(data[field])] if data[field] else []
        
        # Clean steps
        if "steps" in data:
            cleaned_steps = []
            for step in data["steps"]:
                if isinstance(step, dict) and "name" in step:
                    # Ensure citations is a list of integers
                    if "citations" in step:
                        try:
                            step["citations"] = [int(c) for c in step["citations"] if str(c).isdigit()]
                        except (ValueError, TypeError):
                            step["citations"] = []
                    else:
                        step["citations"] = []
                    
                    # Set default difficulty level
                    if "difficulty_level" not in step:
                        step["difficulty_level"] = 1
                    
                    cleaned_steps.append(step)
            data["steps"] = cleaned_steps
        
        return data


class FallbackGuideGenerator:
    """Generates deterministic fallback guides when LLM is unavailable."""
    
    def __init__(self):
        self.domain_templates = {
            SkillDomain.MARTIAL_ARTS: {
                "prerequisites": ["Clear practice area", "Proper stance", "Basic warm-up"],
                "safety": ["Start slowly", "Respect joint limits", "Use protective gear", "Practice with supervision"],
                "equipment": ["Training mat", "Protective gear (optional)"],
                "core_principles": ["Whole-body coordination", "Proper form over speed", "Progressive training"],
                "evaluation": ["Maintain balance", "Execute with control", "Demonstrate understanding"]
            },
            SkillDomain.SPORTS: {
                "prerequisites": ["Physical fitness check", "Proper equipment", "Understanding of rules"],
                "safety": ["Proper warm-up", "Use safety equipment", "Know your limits"],
                "equipment": ["Sport-specific gear", "Protective equipment"],
                "core_principles": ["Technique first", "Consistent practice", "Mental focus"],
                "evaluation": ["Technical proficiency", "Safety awareness", "Performance consistency"]
            },
            SkillDomain.MUSIC: {
                "prerequisites": ["Instrument access", "Basic music theory", "Practice space"],
                "safety": ["Proper posture", "Regular breaks", "Hearing protection"],
                "equipment": ["Musical instrument", "Music stand", "Metronome"],
                "core_principles": ["Regular practice", "Proper technique", "Patience and persistence"],
                "evaluation": ["Rhythm accuracy", "Tone quality", "Musical expression"]
            }
        }
    
    def generate_fallback_guide(self, query: str, sources: List[Dict[str, Any]], domain: SkillDomain) -> Dict[str, Any]:
        """Generate a structured fallback guide."""
        template = self.domain_templates.get(domain, self.domain_templates[SkillDomain.MARTIAL_ARTS])
        
        # Generate basic steps based on common learning patterns
        steps = [
            {
                "name": "Preparation",
                "how": "Set up your practice area and equipment. Review safety guidelines.",
                "why": "Proper preparation ensures safe and effective practice.",
                "citations": list(range(min(2, len(sources)))),
                "difficulty_level": 1
            },
            {
                "name": "Basic Technique",
                "how": "Learn the fundamental movements slowly and with control.",
                "why": "Building proper form is essential before adding speed or power.",
                "citations": list(range(min(3, len(sources)))),
                "difficulty_level": 2
            },
            {
                "name": "Practice",
                "how": "Repeat the movements with focus on accuracy and consistency.",
                "why": "Repetition builds muscle memory and confidence.",
                "citations": list(range(min(2, len(sources)))),
                "difficulty_level": 3
            },
            {
                "name": "Application",
                "how": "Apply the skill in realistic scenarios or with variations.",
                "why": "Real-world application tests understanding and adaptability.",
                "citations": [],
                "difficulty_level": 4
            }
        ]
        
        return {
            "query": query,
            "title": f"Learning Guide: {query.title()}",
            "domain": domain.value,
            "prerequisites": template["prerequisites"],
            "safety": template["safety"],
            "equipment": template["equipment"],
            "core_principles": template["core_principles"],
            "steps": steps,
            "evaluation": template["evaluation"],
            "sources": sources,
            "estimated_learning_time": "2-4 weeks with regular practice",
            "difficulty_rating": 3
        }


class CohereAgent:
    """Enhanced Cohere LLM agent with better prompting and error handling."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.validator = GuideValidator()
        self.fallback_generator = FallbackGuideGenerator()
        
        if not (config.api_key and cohere):
            logger.warning("Cohere not available, will use fallback mode")
            self.client = None
        else:
            self.client = cohere.Client(config.api_key)
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for guide generation."""
        return """You are an expert skill learning instructor that converts research sources into structured, practical learning guides.

Your task is to analyze multiple sources and create a comprehensive, safety-focused learning guide.

CRITICAL REQUIREMENTS:
1. Output ONLY valid JSON with this exact structure:
{
  "title": "Clear, descriptive title",
  "domain": "martial_arts|sports|music|crafts|general",
  "prerequisites": ["requirement1", "requirement2"],
  "safety": ["safety rule1", "safety rule2"],
  "equipment": ["item1", "item2"],
  "core_principles": ["principle1", "principle2"],
  "steps": [
    {
      "name": "Step Name",
      "how": "Detailed instructions on how to perform this step",
      "why": "Explanation of why this step is important",
      "cues": "Optional: coaching cues or tips",
      "common_mistakes": ["mistake1", "mistake2"],
      "citations": [0, 1],
      "difficulty_level": 1-5
    }
  ],
  "evaluation": ["success criteria1", "criteria2"],
  "estimated_learning_time": "realistic timeframe",
  "difficulty_rating": 1-5
}

2. Use concrete, actionable language
3. Include safety considerations prominently
4. Reference sources using citation numbers [0, 1, 2, etc.]
5. Order steps logically from basic to advanced
6. Be specific about techniques and avoid vague descriptions"""
    
    def _build_user_prompt(self, query: str, sources: List[Dict[str, Any]]) -> str:
        """Build user prompt with source information."""
        source_text = []
        for i, source in enumerate(sources):
            source_info = f"[{i}] {source.get('title', 'Unknown')} - {source.get('url', '')}"
            snippet = source.get('snippet', '')[:800]
            source_text.append(f"{source_info}\n{snippet}")
        
        return f"""LEARNING QUERY: {query}

RESEARCH SOURCES:
{chr(10).join(source_text)}

Create a comprehensive learning guide based on these sources. Focus on practical, step-by-step instructions that a beginner could follow safely. Include specific techniques, common mistakes to avoid, and clear success criteria.

Return ONLY the JSON structure - no additional text or formatting."""
    
    async def generate_guide_with_retry(self, query: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate guide with retry logic."""
        if not self.client:
            logger.info("Using fallback guide generation")
            domain = SkillDomain.GENERAL  # Could be enhanced with domain detection
            return self.fallback_generator.generate_fallback_guide(query, sources, domain)
        
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(query, sources)
        
        for attempt in range(self.config.retry_attempts):
            try:
                logger.debug(f"LLM attempt {attempt + 1}/{self.config.retry_attempts}")
                
                response = await asyncio.to_thread(
                    self.client.chat,
                    model=self.config.model,
                    message=user_prompt,
                    preamble=system_prompt,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
                
                # Parse and validate response
                text = response.text.strip()
                
                # Clean up common JSON formatting issues
                if text.startswith("```json"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                
                data = json.loads(text)
                self.validator.validate_guide_structure(data)
                data = self.validator.sanitize_guide(data)
                
                logger.info("Successfully generated guide with LLM")
                return data
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed on attempt {attempt + 1}: {e}")
                if attempt == self.config.retry_attempts - 1:
                    logger.error("All LLM attempts failed, using fallback")
                    break
            except ValidationError as e:
                logger.warning(f"Validation failed on attempt {attempt + 1}: {e}")
                if attempt == self.config.retry_attempts - 1:
                    logger.error("All LLM attempts failed validation, using fallback")
                    break
            except Exception as e:
                logger.error(f"LLM request failed on attempt {attempt + 1}: {e}")
                if attempt == self.config.retry_attempts - 1:
                    break
        
        # Fallback to deterministic generation
        logger.info("Using fallback guide generation after LLM failure")
        domain = SkillDomain.GENERAL
        return self.fallback_generator.generate_fallback_guide(query, sources, domain)
    
    async def create_skill_guide(self, query: str, sources: List[SourceDoc]) -> SkillGuide:
        """Create a structured skill guide from sources."""
        try:
            # Convert sources to dict format for LLM processing
            source_dicts = [source.to_dict() for source in sources]
            
            # Generate guide data
            guide_data = await self.generate_guide_with_retry(query, source_dicts)
            
            # Convert to structured objects
            steps = []
            for step_data in guide_data.get("steps", []):
                step = SkillStep(
                    name=step_data["name"],
                    how=step_data["how"],
                    why=step_data["why"],
                    cues=step_data.get("cues"),
                    common_mistakes=step_data.get("common_mistakes"),
                    citations=step_data.get("citations", []),
                    difficulty_level=step_data.get("difficulty_level", 1)
                )
                steps.append(step)
            
            # Determine domain
            domain_str = guide_data.get("domain", "general")
            try:
                domain = SkillDomain(domain_str)
            except ValueError:
                domain = SkillDomain.GENERAL
            
            # Create guide object
            guide = SkillGuide(
                query=query,
                title=guide_data["title"],
                domain=domain,
                prerequisites=guide_data.get("prerequisites", []),
                safety=guide_data.get("safety", []),
                equipment=guide_data.get("equipment", []),
                core_principles=guide_data.get("core_principles", []),
                steps=steps,
                evaluation=guide_data.get("evaluation", []),
                sources=source_dicts,
                estimated_learning_time=guide_data.get("estimated_learning_time"),
                difficulty_rating=guide_data.get("difficulty_rating", 1)
            )
            
            return guide
            
        except Exception as e:
            logger.error(f"Guide creation failed: {e}")
            raise LLMError(f"Failed to create skill guide: {e}")
