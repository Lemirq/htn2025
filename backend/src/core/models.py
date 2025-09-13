"""Core data models for the skill learning system."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import json


class SourceType(Enum):
    """Types of information sources."""
    WEB = "web"
    ACADEMIC = "academic"
    VIDEO = "video"
    MANUAL = "manual"


class SkillDomain(Enum):
    """Domains of skills the system can handle."""
    MARTIAL_ARTS = "martial_arts"
    SPORTS = "sports"
    MUSIC = "music"
    CRAFTS = "crafts"
    GENERAL = "general"


@dataclass
class SourceDoc:
    """Represents a source document with metadata and content."""
    url: str
    title: str
    snippet: str
    text: str
    weight: float  # reliability weight ∈ [0,1]
    confidence: float  # extraction confidence ∈ [0,1]
    source_type: SourceType = SourceType.WEB
    domain_relevance: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "title": self.title[:120],
            "snippet": self.snippet[:320],
            "weight": round(self.weight, 3),
            "confidence": round(self.confidence, 3),
            "source_type": self.source_type.value,
            "domain_relevance": round(self.domain_relevance, 3)
        }
    
    @property
    def quality_score(self) -> float:
        """Combined quality metric."""
        return (self.weight * 0.4 + self.confidence * 0.4 + self.domain_relevance * 0.2)


@dataclass
class SkillStep:
    """Individual step in a skill guide."""
    name: str
    how: str
    why: str
    cues: Optional[str] = None
    common_mistakes: Optional[List[str]] = None
    citations: List[int] = field(default_factory=list)
    difficulty_level: int = 1  # 1-5 scale
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "how": self.how,
            "why": self.why,
            "citations": self.citations,
            "difficulty_level": self.difficulty_level
        }
        if self.cues:
            result["cues"] = self.cues
        if self.common_mistakes:
            result["common_mistakes"] = self.common_mistakes
        return result


@dataclass
class SkillGuide:
    """Complete structured guide for learning a skill."""
    query: str
    title: str
    domain: SkillDomain
    prerequisites: List[str]
    safety: List[str]
    equipment: List[str]
    core_principles: List[str]
    steps: List[SkillStep]
    evaluation: List[str]
    sources: List[Dict[str, Any]]
    estimated_learning_time: Optional[str] = None
    difficulty_rating: int = 1  # 1-5 scale
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "title": self.title,
            "domain": self.domain.value,
            "prerequisites": self.prerequisites,
            "safety": self.safety,
            "equipment": self.equipment,
            "core_principles": self.core_principles,
            "steps": [step.to_dict() for step in self.steps],
            "evaluation": self.evaluation,
            "sources": self.sources,
            "estimated_learning_time": self.estimated_learning_time,
            "difficulty_rating": self.difficulty_rating
        }


@dataclass
class ExecutionPhase:
    """Single phase in a hardware execution plan."""
    name: str
    duration_ms: int
    cue: str
    pose_hints: str
    rationale: str
    citations: List[int] = field(default_factory=list)
    velocity_profile: Optional[str] = None
    force_profile: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "cue": self.cue,
            "pose_hints": self.pose_hints,
            "rationale": self.rationale,
            "citations": self.citations
        }
        if self.velocity_profile:
            result["velocity_profile"] = self.velocity_profile
        if self.force_profile:
            result["force_profile"] = self.force_profile
        return result


@dataclass
class PhysicalConstraints:
    """Physical constraints for execution."""
    max_velocity_hint: float = 0.8
    keep_com_in_base: bool = True
    workspace_hint: str = ""
    joint_limits: Dict[str, float] = field(default_factory=dict)
    safety_margins: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "max_velocity_hint": self.max_velocity_hint,
            "keep_com_in_base": self.keep_com_in_base,
            "workspace_hint": self.workspace_hint,
            "joint_limits": self.joint_limits,
            "safety_margins": self.safety_margins
        }


@dataclass
class ExecutionPlan:
    """Hardware-agnostic execution plan for a skill."""
    skill_name: str
    phases: List[ExecutionPhase]
    constraints: PhysicalConstraints
    provenance: List[Dict[str, Any]]
    total_duration_ms: int = 0
    complexity_score: float = 0.0
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.total_duration_ms = sum(phase.duration_ms for phase in self.phases)
        self.complexity_score = len(self.phases) * 0.2 + (self.total_duration_ms / 1000) * 0.1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "skill": self.skill_name,
            "phases": [phase.to_dict() for phase in self.phases],
            "constraints": self.constraints.to_dict(),
            "provenance": self.provenance,
            "total_duration_ms": self.total_duration_ms,
            "complexity_score": round(self.complexity_score, 3)
        }


@dataclass
class SkillBundle:
    """Complete bundle containing all outputs of the skill learning pipeline."""
    query: str
    sources: List[SourceDoc]
    guide: SkillGuide
    plan: ExecutionPlan
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "sources": [source.to_dict() for source in self.sources],
            "guide": self.guide.to_dict(),
            "plan": self.plan.to_dict(),
            "metadata": self.metadata
        }
