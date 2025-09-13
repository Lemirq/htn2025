"""Enhanced skill compiler service for generating hardware execution plans."""
from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from ..core.models import (
    SkillGuide, ExecutionPlan, ExecutionPhase, PhysicalConstraints, SkillDomain
)
from ..core.config import CompilerConfig
from ..core.exceptions import CompilationError

logger = logging.getLogger(__name__)


class PhaseMapper:
    """Maps skill steps to execution phases with timing and constraints."""
    
    DOMAIN_PHASE_MAPPINGS = {
        SkillDomain.MARTIAL_ARTS: {
            "setup": {"duration": 600, "velocity": "slow", "force": "minimal"},
            "stance": {"duration": 400, "velocity": "slow", "force": "controlled"},
            "preload": {"duration": 300, "velocity": "slow", "force": "building"},
            "preparation": {"duration": 500, "velocity": "slow", "force": "minimal"},
            "strike": {"duration": 120, "velocity": "explosive", "force": "maximum"},
            "punch": {"duration": 150, "velocity": "explosive", "force": "maximum"},
            "kick": {"duration": 200, "velocity": "explosive", "force": "maximum"},
            "block": {"duration": 180, "velocity": "fast", "force": "controlled"},
            "retract": {"duration": 300, "velocity": "fast", "force": "minimal"},
            "recovery": {"duration": 400, "velocity": "slow", "force": "minimal"},
            "reset": {"duration": 350, "velocity": "slow", "force": "minimal"}
        },
        SkillDomain.SPORTS: {
            "setup": {"duration": 800, "velocity": "slow", "force": "minimal"},
            "preparation": {"duration": 600, "velocity": "slow", "force": "controlled"},
            "execution": {"duration": 300, "velocity": "fast", "force": "controlled"},
            "follow_through": {"duration": 400, "velocity": "medium", "force": "controlled"},
            "recovery": {"duration": 500, "velocity": "slow", "force": "minimal"}
        },
        SkillDomain.MUSIC: {
            "preparation": {"duration": 1000, "velocity": "slow", "force": "minimal"},
            "attack": {"duration": 100, "velocity": "precise", "force": "controlled"},
            "sustain": {"duration": 2000, "velocity": "steady", "force": "controlled"},
            "release": {"duration": 200, "velocity": "slow", "force": "minimal"}
        }
    }
    
    def __init__(self, config: CompilerConfig):
        self.config = config
    
    def map_step_to_phase(self, step_name: str, step_data: Dict[str, Any], domain: SkillDomain) -> ExecutionPhase:
        """Map a skill step to an execution phase."""
        step_name_lower = step_name.lower()
        
        # Get domain-specific mappings
        domain_mappings = self.DOMAIN_PHASE_MAPPINGS.get(domain, 
                                                        self.DOMAIN_PHASE_MAPPINGS[SkillDomain.MARTIAL_ARTS])
        
        # Find best matching phase template
        phase_template = None
        for template_name, template_data in domain_mappings.items():
            if template_name in step_name_lower:
                phase_template = template_data
                break
        
        # Default fallback
        if not phase_template:
            phase_template = {"duration": 500, "velocity": "medium", "force": "controlled"}
        
        # Adjust duration based on difficulty
        difficulty = step_data.get("difficulty_level", 1)
        duration_multiplier = 1.0 + (difficulty - 1) * 0.2
        base_duration = phase_template["duration"]
        adjusted_duration = int(base_duration * duration_multiplier)
        
        # Generate cue from step data
        cue = self._generate_cue(step_data, phase_template)
        
        return ExecutionPhase(
            name=step_name_lower.replace(" ", "_"),
            duration_ms=adjusted_duration,
            cue=cue,
            pose_hints=step_data.get("how", ""),
            rationale=step_data.get("why", ""),
            citations=step_data.get("citations", []),
            velocity_profile=phase_template["velocity"],
            force_profile=phase_template["force"]
        )
    
    def _generate_cue(self, step_data: Dict[str, Any], phase_template: Dict[str, Any]) -> str:
        """Generate execution cue from step data."""
        # Use explicit cues if available
        if step_data.get("cues"):
            return step_data["cues"]
        
        # Generate based on velocity and force profiles
        velocity = phase_template["velocity"]
        force = phase_template["force"]
        
        cue_templates = {
            ("slow", "minimal"): "relax and position",
            ("slow", "controlled"): "steady and controlled",
            ("medium", "controlled"): "smooth execution",
            ("fast", "controlled"): "quick but precise",
            ("explosive", "maximum"): "explosive power",
            ("precise", "controlled"): "focus on accuracy"
        }
        
        return cue_templates.get((velocity, force), "execute with control")


class ConstraintGenerator:
    """Generates physical constraints based on skill domain and complexity."""
    
    DOMAIN_CONSTRAINTS = {
        SkillDomain.MARTIAL_ARTS: {
            "max_velocity_hint": 0.9,
            "keep_com_in_base": True,
            "workspace_hint": "short to medium range combat movements",
            "joint_limits": {
                "shoulder_flexion": 180.0,
                "elbow_extension": 170.0,
                "hip_flexion": 120.0,
                "knee_flexion": 135.0
            },
            "safety_margins": {
                "impact_force": 0.8,
                "joint_stress": 0.7,
                "balance_threshold": 0.9
            }
        },
        SkillDomain.SPORTS: {
            "max_velocity_hint": 0.85,
            "keep_com_in_base": True,
            "workspace_hint": "sport-specific movement patterns",
            "joint_limits": {
                "shoulder_flexion": 170.0,
                "elbow_extension": 160.0,
                "hip_flexion": 110.0,
                "knee_flexion": 130.0
            },
            "safety_margins": {
                "impact_force": 0.75,
                "joint_stress": 0.8,
                "balance_threshold": 0.85
            }
        },
        SkillDomain.MUSIC: {
            "max_velocity_hint": 0.6,
            "keep_com_in_base": True,
            "workspace_hint": "fine motor control and precision",
            "joint_limits": {
                "wrist_flexion": 80.0,
                "finger_flexion": 90.0,
                "shoulder_flexion": 45.0
            },
            "safety_margins": {
                "repetitive_strain": 0.6,
                "joint_stress": 0.9,
                "fatigue_threshold": 0.7
            }
        }
    }
    
    def generate_constraints(self, domain: SkillDomain, complexity_score: float) -> PhysicalConstraints:
        """Generate physical constraints for the skill."""
        base_constraints = self.DOMAIN_CONSTRAINTS.get(domain, 
                                                      self.DOMAIN_CONSTRAINTS[SkillDomain.MARTIAL_ARTS])
        
        # Adjust constraints based on complexity
        complexity_factor = min(1.0, complexity_score / 10.0)
        
        # Reduce velocity limits for complex skills
        max_velocity = base_constraints["max_velocity_hint"] * (1.0 - complexity_factor * 0.2)
        
        # Increase safety margins for complex skills
        safety_margins = base_constraints["safety_margins"].copy()
        for key, value in safety_margins.items():
            safety_margins[key] = max(0.5, value - complexity_factor * 0.1)
        
        return PhysicalConstraints(
            max_velocity_hint=max_velocity,
            keep_com_in_base=base_constraints["keep_com_in_base"],
            workspace_hint=base_constraints["workspace_hint"],
            joint_limits=base_constraints["joint_limits"].copy(),
            safety_margins=safety_margins
        )


class SkillCompiler:
    """Enhanced skill compiler with domain-aware execution planning."""
    
    def __init__(self, config: CompilerConfig):
        self.config = config
        self.phase_mapper = PhaseMapper(config)
        self.constraint_generator = ConstraintGenerator()
    
    def _calculate_complexity_score(self, guide: SkillGuide) -> float:
        """Calculate skill complexity score."""
        base_score = len(guide.steps) * 0.5
        
        # Add difficulty-based complexity
        avg_difficulty = sum(step.difficulty_level for step in guide.steps) / len(guide.steps)
        difficulty_score = avg_difficulty * 0.8
        
        # Add domain-based complexity
        domain_complexity = {
            SkillDomain.MARTIAL_ARTS: 1.2,
            SkillDomain.SPORTS: 1.0,
            SkillDomain.MUSIC: 0.8,
            SkillDomain.CRAFTS: 0.6,
            SkillDomain.GENERAL: 0.5
        }
        domain_score = domain_complexity.get(guide.domain, 0.5)
        
        return base_score + difficulty_score + domain_score
    
    def _optimize_phase_timing(self, phases: List[ExecutionPhase]) -> List[ExecutionPhase]:
        """Optimize phase timing for smooth execution."""
        if len(phases) < 2:
            return phases
        
        optimized_phases = []
        
        for i, phase in enumerate(phases):
            optimized_phase = ExecutionPhase(
                name=phase.name,
                duration_ms=phase.duration_ms,
                cue=phase.cue,
                pose_hints=phase.pose_hints,
                rationale=phase.rationale,
                citations=phase.citations,
                velocity_profile=phase.velocity_profile,
                force_profile=phase.force_profile
            )
            
            # Adjust timing based on adjacent phases
            if i > 0:
                prev_phase = phases[i-1]
                # Smooth transitions between phases
                if (prev_phase.velocity_profile == "explosive" and 
                    phase.velocity_profile == "slow"):
                    # Add transition time for deceleration
                    optimized_phase.duration_ms = int(phase.duration_ms * 1.2)
            
            if i < len(phases) - 1:
                next_phase = phases[i+1]
                # Prepare for next phase
                if (phase.velocity_profile == "slow" and 
                    next_phase.velocity_profile == "explosive"):
                    # Reduce duration to allow for acceleration
                    optimized_phase.duration_ms = int(phase.duration_ms * 0.9)
            
            optimized_phases.append(optimized_phase)
        
        return optimized_phases
    
    def compile_skill_guide(self, guide: SkillGuide) -> ExecutionPlan:
        """Compile a skill guide into a hardware execution plan."""
        try:
            if not guide.steps:
                raise CompilationError("Cannot compile guide with no steps")
            
            # Calculate complexity
            complexity_score = self._calculate_complexity_score(guide)
            
            # Map steps to phases
            phases = []
            for step in guide.steps:
                step_dict = asdict(step)
                phase = self.phase_mapper.map_step_to_phase(step.name, step_dict, guide.domain)
                phases.append(phase)
            
            # Optimize phase timing
            phases = self._optimize_phase_timing(phases)
            
            # Generate constraints
            constraints = self.constraint_generator.generate_constraints(guide.domain, complexity_score)
            
            # Create execution plan
            plan = ExecutionPlan(
                skill_name=guide.title,
                phases=phases,
                constraints=constraints,
                provenance=[source for source in guide.sources],
                complexity_score=complexity_score
            )
            
            logger.info(f"Compiled execution plan with {len(phases)} phases, "
                       f"total duration: {plan.total_duration_ms}ms, "
                       f"complexity: {complexity_score:.2f}")
            
            return plan
            
        except Exception as e:
            logger.error(f"Skill compilation failed: {e}")
            raise CompilationError(f"Failed to compile skill guide: {e}")
    
    def validate_execution_plan(self, plan: ExecutionPlan) -> List[str]:
        """Validate execution plan and return warnings/suggestions."""
        warnings = []
        
        # Check total duration
        if plan.total_duration_ms > 10000:  # 10 seconds
            warnings.append("Execution time is quite long - consider breaking into sub-skills")
        
        if plan.total_duration_ms < 500:  # 0.5 seconds
            warnings.append("Execution time is very short - may be too fast for learning")
        
        # Check phase transitions
        for i in range(len(plan.phases) - 1):
            current = plan.phases[i]
            next_phase = plan.phases[i + 1]
            
            if (current.velocity_profile == "explosive" and 
                next_phase.velocity_profile == "explosive" and
                current.duration_ms < 200):
                warnings.append(f"Rapid transition from {current.name} to {next_phase.name} may be difficult")
        
        # Check complexity
        if plan.complexity_score > self.config.complexity_threshold:
            warnings.append("High complexity skill - consider progressive learning approach")
        
        return warnings
