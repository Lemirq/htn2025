# Skill Learning System

A sophisticated AI-powered system that converts natural language queries into structured learning guides and executable hardware plans. This system uses web scraping, LLM reasoning, and domain-specific compilation to create comprehensive skill learning resources.

## 🎯 What It Does

The system takes queries like "learn the one inch punch by bruce lee" and produces:

1. **Curated Sources**: Web-scraped content with reliability scoring
2. **Structured Learning Guide**: Step-by-step instructions with safety guidelines
3. **Hardware Execution Plan**: Timing-based phases for robotic or training systems

## 🧠 AI Agent Architecture

### Core Components

- **Web Intelligence Agent** (`scraper.py`): Domain-aware web scraping with source reliability weighting
- **LLM Reasoning Agent** (`llm_agent.py`): Uses Cohere's `command-r-plus` model for knowledge synthesis
- **Compilation Agent** (`compiler.py`): Converts guides into hardware-agnostic execution plans
- **Pipeline Orchestrator** (`skill_pipeline.py`): Manages the complete workflow

### How It Uses Cohere

- **Model**: `command-r-plus` for advanced reasoning and structured output
- **Temperature**: 0.2 for consistent, factual responses
- **System Prompting**: Enforces strict JSON schema with safety focus
- **Fallback System**: Deterministic templates when LLM unavailable
- **Retry Logic**: Multiple attempts with validation

## 📊 Output Explanation

### Sources (`sources.json`)
```json
{
  "sources": [
    {
      "url": "https://example.com",
      "title": "Article Title",
      "weight": 0.85,           // Reliability score (0-1)
      "confidence": 0.92,       // Extraction confidence (0-1)
      "domain_relevance": 0.78  // Topic relevance (0-1)
    }
  ]
}
```

### Guide (`guide.json`)
```json
{
  "title": "Learning Guide Title",
  "domain": "martial_arts",
  "difficulty_rating": 3,
  "steps": [
    {
      "name": "Setup",
      "how": "Detailed instructions",
      "why": "Rationale and principles",
      "difficulty_level": 2,
      "citations": [0, 1]       // References to sources
    }
  ],
  "safety": ["Safety guidelines"],
  "evaluation": ["Success criteria"]
}
```

### Plan (`plan.json`)
```json
{
  "skill": "Skill Name",
  "phases": [
    {
      "name": "setup",
      "duration_ms": 600,       // Precise timing
      "cue": "establish base",   // Execution cue
      "pose_hints": "Physical instructions",
      "velocity_profile": "slow",
      "force_profile": "minimal"
    }
  ],
  "constraints": {
    "max_velocity_hint": 0.8,
    "joint_limits": {...},
    "safety_margins": {...}
  },
  "total_duration_ms": 1320,
  "complexity_score": 4.2
}
```

## 🚀 Installation & Usage

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Cohere API key
```

### Basic Usage
```bash
# Basic usage
python main.py "learn the one inch punch by bruce lee"

# With options
python main.py "tennis serve technique" --max-sources 8 --output-dir tennis_results

# Fallback mode (no web scraping)
python main.py "guitar chords" --no-web

# Test the system
python test.py
```

### Programmatic Usage
```python
from src.pipeline.skill_pipeline import build_skill
from src.core.config import SystemConfig

# Simple usage
bundle = build_skill("learn piano scales")

# With custom configuration
config = SystemConfig.from_env()
config.scraping.max_sources = 10
bundle = build_skill("martial arts kata", config)

# Access results
print(f"Found {len(bundle.sources)} sources")
print(f"Generated {len(bundle.guide.steps)} learning steps")
print(f"Execution time: {bundle.plan.total_duration_ms}ms")
```

## 🏗️ Architecture

### Key Improvements

1. **Structured Data Models**: Type-safe dataclasses with validation
2. **Domain Intelligence**: Skill domain classification and relevance scoring
3. **Error Handling**: Comprehensive exception hierarchy with graceful fallbacks
4. **Configuration Management**: Environment-based config with validation
5. **Logging & Monitoring**: Structured logging with performance metrics
6. **Modular Services**: Clean separation of concerns with dependency injection
7. **Async Processing**: Concurrent web scraping and LLM requests
8. **Validation Pipeline**: Multi-stage validation with warnings
9. **Enhanced CLI**: Rich command-line interface with progress indicators
10. **Extensible Design**: Plugin architecture for new domains and compilers

### Key Sophistications

- **Source Reliability Weighting**: Domain trust scoring based on URL patterns
- **Content Quality Assessment**: Length, structure, and relevance analysis  
- **Domain-Aware Processing**: Martial arts, sports, music, crafts specialization
- **Timing Optimization**: Phase duration adjustment based on complexity
- **Safety Integration**: Domain-specific safety constraints and warnings
- **Citation Tracking**: Maintains source traceability throughout pipeline
- **Fallback Robustness**: Multiple fallback layers for reliability

## 🔧 Configuration

Key environment variables:
```bash
COHERE_API_KEY=your_api_key_here
ALLOW_WEB=true
MAX_SOURCES=10
OUTPUT_DIR=outputs
LOG_LEVEL=INFO
ENABLE_CACHING=true
```

## 📈 Performance & Scaling

- **Concurrent Processing**: Async web scraping and LLM requests
- **Caching Support**: Built-in caching for repeated queries
- **Rate Limiting**: Respectful web scraping with delays
- **Memory Efficient**: Streaming JSON processing with orjson
- **Error Recovery**: Graceful degradation with fallback modes

## 🎯 Use Cases

- **Robotics Training**: Generate precise movement sequences for robot learning
- **Educational Platforms**: Create structured learning curricula
- **Sports Coaching**: Develop technique breakdown and timing analysis  
- **Skill Assessment**: Automated evaluation criteria generation
- **Training Simulations**: Hardware-agnostic execution plans for VR/AR

This system provides a sophisticated, production-ready skill learning platform with enterprise-grade error handling, monitoring, and extensibility.
