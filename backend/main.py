"""Main entry point for the skill learning system."""
import asyncio
import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.config import SystemConfig
from src.core.exceptions import SkillLearningError
from src.pipeline.skill_pipeline import SkillLearningPipeline


def main():
    """Main entry point with CLI interface."""
    parser = argparse.ArgumentParser(
        description="Skill Learning System - Convert queries into executable learning plans",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "learn the one inch punch by bruce lee"
  python main.py "how to play guitar chords" --max-sources 8
  python main.py "tennis serve technique" --output-dir tennis_results
        """
    )
    
    parser.add_argument(
        "query", 
        help="Learning query (e.g., 'learn the one inch punch by bruce lee')"
    )
    parser.add_argument(
        "--max-sources", 
        type=int, 
        default=None,
        help="Maximum number of sources to scrape (default: from config)"
    )
    parser.add_argument(
        "--output-dir", 
        default=None,
        help="Output directory for results (default: from config)"
    )
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    parser.add_argument(
        "--no-web", 
        action="store_true",
        help="Disable web scraping (use fallback mode only)"
    )
    parser.add_argument(
        "--quiet", 
        action="store_true",
        help="Suppress detailed output, only show summary"
    )
    
    args = parser.parse_args()
    
    try:
        # Create configuration
        config = SystemConfig.from_env()
        config.log_level = args.log_level
        
        if args.output_dir:
            config.output_dir = args.output_dir
        
        if args.no_web:
            config.scraping.allow_web = False
        
        # Run pipeline
        pipeline = SkillLearningPipeline(config)
        
        if not args.quiet:
            print(f"🎯 Processing query: '{args.query}'")
            print(f"📁 Output directory: {config.output_dir}")
            print(f"🌐 Web scraping: {'enabled' if config.scraping.allow_web else 'disabled'}")
            print()
        
        # Process the query
        bundle = asyncio.run(pipeline.process_query(args.query, args.max_sources))
        
        # Save results
        saved_files = pipeline.save_bundle(bundle)
        
        # Print summary
        if not args.quiet:
            pipeline.print_summary(bundle)
        else:
            print(f"✅ Successfully processed '{args.query}'")
            print(f"📊 Generated {len(bundle.guide.steps)} learning steps")
            print(f"⏱️  Execution plan: {bundle.plan.total_duration_ms}ms")
        
        print(f"\n📄 Results saved to:")
        for file_type, file_path in saved_files.items():
            print(f"   {file_type}: {file_path}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n❌ Process interrupted by user")
        return 1
    except SkillLearningError as e:
        print(f"❌ Skill learning error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.log_level == "DEBUG":
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
