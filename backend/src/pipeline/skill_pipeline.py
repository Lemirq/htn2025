"""Main skill learning pipeline orchestrating the entire process."""
from __future__ import annotations
import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import orjson

from ..core.models import SkillBundle
from ..core.config import SystemConfig
from ..core.exceptions import SkillLearningError
from ..services.scraper import WebScraper
from ..services.llm_agent import CohereAgent
from ..services.compiler import SkillCompiler
from ..services.robot_controller import RobotControlGenerator

logger = logging.getLogger(__name__)


class SkillLearningPipeline:
    """Main pipeline for converting queries into executable skill plans."""
    
    def __init__(self, config: Optional[SystemConfig] = None):
        self.config = config or SystemConfig.from_env()
        self.config.validate()
        
        # Initialize services
        self.scraper = WebScraper(self.config.scraping)
        self.llm_agent = CohereAgent(self.config.llm)
        self.compiler = SkillCompiler(self.config.compiler)
        # Pass LLM config so servo planning can call Cohere
        self.robot_controller = RobotControlGenerator(self.config.llm)
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    async def process_query(self, query: str, max_sources: Optional[int] = None) -> SkillBundle:
        """Process a learning query through the complete pipeline."""
        max_sources = max_sources or self.config.scraping.max_sources
        
        try:
            logger.info(f"Processing query: '{query}'")
            
            # Step 1: Scrape sources
            logger.info("Step 1: Scraping sources...")
            sources = await self.scraper.scrape_query(query, max_sources)
            logger.info(f"Found {len(sources)} sources")
            
            # Step 2: Generate guide with LLM
            logger.info("Step 2: Generating skill guide...")
            guide = await self.llm_agent.create_skill_guide(query, sources)
            logger.info(f"Generated guide with {len(guide.steps)} steps")
            
            # Step 3: Compile execution plan
            logger.info("Step 3: Compiling execution plan...")
            plan = self.compiler.compile_skill_guide(guide)
            
            # Validate plan and log warnings
            warnings = self.compiler.validate_execution_plan(plan)
            for warning in warnings:
                logger.warning(f"Plan validation: {warning}")
            
            logger.info(f"Compiled plan with {len(plan.phases)} phases, "
                       f"total duration: {plan.total_duration_ms}ms")
            
            # Step 4: Generate robot control instructions
            logger.info("Step 4: Generating robot control instructions...")
            robot_instructions = self.robot_controller.generate_robot_instructions(plan)
            logger.info("Generated robot control instructions for unlimited DOF and 3 DOF models")
            
            # Create bundle
            bundle = SkillBundle(
                query=query,
                sources=sources,
                guide=guide,
                plan=plan,
                robot_instructions=robot_instructions.to_dict(),
                metadata={
                    "pipeline_version": "2.0",
                    "processing_warnings": warnings,
                    "source_count": len(sources),
                    "step_count": len(guide.steps),
                    "phase_count": len(plan.phases)
                }
            )
            
            logger.info("Pipeline processing completed successfully")
            return bundle
            
        except Exception as e:
            logger.error(f"Pipeline processing failed: {e}")
            raise SkillLearningError(f"Failed to process query '{query}': {e}")
    
    def save_bundle(self, bundle: SkillBundle, output_dir: Optional[str] = None) -> Dict[str, str]:
        """Save skill bundle to JSON files."""
        output_dir = Path(output_dir or self.config.output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Define output files
        files = {
            "sources": output_dir / "sources.json",
            "guide": output_dir / "guide.json", 
            "plan": output_dir / "plan.json",
            "robot_instructions": output_dir / "robot_instructions.json",
            "servo_sequence": output_dir / "servo_sequence.json",
            "bundle": output_dir / "complete_bundle.json"
        }
        
        try:
            # Save individual components
            self._save_json(files["sources"], {"sources": [s.to_dict() for s in bundle.sources]})
            self._save_json(files["guide"], bundle.guide.to_dict())
            self._save_json(files["plan"], bundle.plan.to_dict())
            if bundle.robot_instructions:
                self._save_json(files["robot_instructions"], bundle.robot_instructions)
            # Save minimal servo sequence (no textual descriptions)
            minimal_seq = self.robot_controller.generate_minimal_servo_sequence(bundle.plan)
            self._save_json(files["servo_sequence"], minimal_seq)
            self._save_json(files["bundle"], bundle.to_dict())
            
            logger.info(f"Saved bundle to {output_dir}")
            return {key: str(path) for key, path in files.items()}
            
        except Exception as e:
            logger.error(f"Failed to save bundle: {e}")
            raise SkillLearningError(f"Failed to save bundle: {e}")
    
    def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Save data as formatted JSON."""
        with open(path, "wb") as f:
            f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    
    def print_summary(self, bundle: SkillBundle) -> None:
        """Print a formatted summary of the skill bundle."""
        print(f"\n{'='*60}")
        print(f"SKILL LEARNING SUMMARY")
        print(f"{'='*60}")
        print(f"Query: {bundle.query}")
        print(f"Domain: {bundle.guide.domain.value}")
        print(f"Difficulty: {bundle.guide.difficulty_rating}/5")
        print(f"Estimated Learning Time: {bundle.guide.estimated_learning_time or 'Not specified'}")
        
        print(f"\n{'SOURCES':-^60}")
        if bundle.sources:
            for i, source in enumerate(bundle.sources):
                quality = source.quality_score
                print(f"{i+1:2d}. [{quality:.2f}] {source.title}")
                print(f"     {source.url}")
        else:
            print("No sources found (likely using fallback mode)")
        
        print(f"\n{'LEARNING STEPS':-^60}")
        for i, step in enumerate(bundle.guide.steps):
            print(f"{i+1:2d}. {step.name} (Level {step.difficulty_level}/5)")
            print(f"     How: {step.how}")
            print(f"     Why: {step.why}")
            if step.cues:
                print(f"     Cues: {step.cues}")
        
        print(f"\n{'EXECUTION PLAN':-^60}")
        print(f"Total Duration: {bundle.plan.total_duration_ms}ms")
        print(f"Complexity Score: {bundle.plan.complexity_score:.2f}")
        print("\nPhases:")
        for phase in bundle.plan.phases:
            print(f"  • {phase.name.title()}: {phase.duration_ms}ms - {phase.cue}")
        
        print(f"\n{'SAFETY GUIDELINES':-^60}")
        for safety in bundle.guide.safety:
            print(f"  ⚠️  {safety}")
        
        if bundle.metadata.get("processing_warnings"):
            print(f"\n{'WARNINGS':-^60}")
            for warning in bundle.metadata["processing_warnings"]:
                print(f"  ⚠️  {warning}")
        
        print(f"\n{'='*60}")


async def build_skill_async(query: str, config: Optional[SystemConfig] = None, 
                           max_sources: Optional[int] = None) -> SkillBundle:
    """Async convenience function for building a skill."""
    pipeline = SkillLearningPipeline(config)
    return await pipeline.process_query(query, max_sources)


def build_skill(query: str, config: Optional[SystemConfig] = None, 
               max_sources: Optional[int] = None) -> SkillBundle:
    """Sync convenience function for building a skill."""
    return asyncio.run(build_skill_async(query, config, max_sources))
