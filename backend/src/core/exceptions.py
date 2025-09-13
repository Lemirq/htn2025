"""Custom exceptions for the skill learning system."""


class SkillLearningError(Exception):
    """Base exception for skill learning system."""
    pass


class ScrapingError(SkillLearningError):
    """Raised when web scraping fails."""
    pass


class LLMError(SkillLearningError):
    """Raised when LLM processing fails."""
    pass


class CompilationError(SkillLearningError):
    """Raised when guide compilation fails."""
    pass


class ConfigurationError(SkillLearningError):
    """Raised when configuration is invalid."""
    pass


class ValidationError(SkillLearningError):
    """Raised when data validation fails."""
    pass
