"""Configuration management for the skill learning system."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from .exceptions import ConfigurationError

load_dotenv()


@dataclass
class ScrapingConfig:
    """Configuration for web scraping."""
    allow_web: bool = True
    max_sources: int = 10
    timeout_seconds: int = 20
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    trust_domains: Dict[str, float] = field(default_factory=lambda: {
        r"\.edu($|/)": 0.25,
        r"\.org($|/)": 0.10,
        r"wikipedia\.org": 0.20,
        r"blackbeltmag\.com|scientificamerican\.com|nih\.gov": 0.15,
        r"youtube\.com|youtu\.be": 0.05,
        r"reddit\.com": 0.05
    })
    min_content_length: int = 200
    max_content_length: int = 15000


@dataclass
class LLMConfig:
    """Configuration for LLM processing."""
    api_key: Optional[str] = None
    model: str = "command-r-plus"
    temperature: float = 0.2
    max_tokens: int = 4000
    timeout_seconds: int = 30
    fallback_enabled: bool = True
    retry_attempts: int = 3
    
    def __post_init__(self):
        """Load API key from environment if not provided."""
        if not self.api_key:
            self.api_key = os.getenv("COHERE_API_KEY")


@dataclass
class CompilerConfig:
    """Configuration for guide compilation."""
    default_phase_durations: Dict[str, int] = field(default_factory=lambda: {
        "setup": 600,
        "preload": 300,
        "execution": 120,
        "retract": 300,
        "recovery": 200
    })
    max_velocity: float = 0.8
    safety_margin: float = 0.2
    complexity_threshold: float = 5.0


@dataclass
class SystemConfig:
    """Main system configuration."""
    scraping: ScrapingConfig = field(default_factory=ScrapingConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    compiler: CompilerConfig = field(default_factory=CompilerConfig)
    output_dir: str = "outputs"
    log_level: str = "INFO"
    enable_caching: bool = True
    cache_ttl_hours: int = 24
    robot_base_url: Optional[str] = None  # e.g., "http://192.168.1.50"
    
    @classmethod
    def from_env(cls) -> SystemConfig:
        """Create configuration from environment variables."""
        config = cls()
        
        # Override with environment variables
        config.scraping.allow_web = os.getenv("ALLOW_WEB", "true").lower() == "true"
        config.scraping.max_sources = int(os.getenv("MAX_SOURCES", "10"))
        config.output_dir = os.getenv("OUTPUT_DIR", "outputs")
        config.log_level = os.getenv("LOG_LEVEL", "INFO")
        config.enable_caching = os.getenv("ENABLE_CACHING", "true").lower() == "true"
        config.robot_base_url = os.getenv("ROBOT_BASE_URL")
        
        return config
    
    def validate(self) -> None:
        """Validate configuration settings."""
        if self.scraping.max_sources <= 0:
            raise ConfigurationError("max_sources must be positive")
        
        if self.scraping.timeout_seconds <= 0:
            raise ConfigurationError("timeout_seconds must be positive")
        
        if not (0.0 <= self.llm.temperature <= 2.0):
            raise ConfigurationError("temperature must be between 0.0 and 2.0")
        
        if self.llm.max_tokens <= 0:
            raise ConfigurationError("max_tokens must be positive")
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
