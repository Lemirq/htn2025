"""Robotic arm control instruction generator for upper body movements."""
from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

from ..core.models import ExecutionPlan, ExecutionPhase
from ..core.config import LLMConfig
from .llm_agent import CohereServoPlanner

logger = logging.getLogger(__name__)


class ServoAxis(Enum):
    """Servo axis types for 3 DOF model."""
    SHOULDER_VERTICAL = "shoulder_vertical"      # up/down
    SHOULDER_HORIZONTAL = "shoulder_horizontal"  # left/right  
    ELBOW_VERTICAL = "elbow_vertical"           # up/down


@dataclass
class ServoCommand:
    """Individual servo command with position only."""
    servo_id: str
    axis: ServoAxis
    position_degrees: float  # 0-180 degrees
    reasoning: str  # LLM-based reasoning for this position
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "servo_id": self.servo_id,
            "axis": self.axis.value,
            "position_degrees": round(self.position_degrees, 1),
            "reasoning": self.reasoning
        }


@dataclass
class RobotMovementStep:
    """Single movement step with multiple servo commands."""
    step_name: str
    description: str
    servo_commands: List[ServoCommand]
    movement_reasoning: str  # LLM reasoning for this movement pattern
    synchronous: bool = True  # Execute all commands simultaneously
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "description": self.description,
            "movement_reasoning": self.movement_reasoning,
            "servo_commands": [cmd.to_dict() for cmd in self.servo_commands],
            "synchronous": self.synchronous
        }


@dataclass
class UnlimitedDOFInstruction:
    """Unlimited DOF movement instruction with full 3D coordinates."""
    step_name: str
    description: str
    left_arm_target: Dict[str, float]   # 3D position and orientation
    right_arm_target: Dict[str, float]  # 3D position and orientation
    spatial_reasoning: str  # LLM reasoning for 3D positioning
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "description": self.description,
            "spatial_reasoning": self.spatial_reasoning,
            "left_arm_target": self.left_arm_target,
            "right_arm_target": self.right_arm_target
        }


@dataclass
class RobotControlInstructions:
    """Complete robot control instructions for both DOF models."""
    skill_name: str
    unlimited_dof_instructions: List[UnlimitedDOFInstruction]
    three_dof_instructions: List[RobotMovementStep]
    overall_strategy: str  # High-level LLM reasoning for the entire skill
    safety_notes: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "overall_strategy": self.overall_strategy,
            "robot_control_formats": {
                "unlimited_dof": {
                    "description": "Full 6DOF control per arm with 3D positioning and orientation",
                    "coordinate_system": "right_handed_cartesian",
                    "units": {
                        "position": "meters",
                        "orientation": "radians"
                    },
                    "instructions": [instr.to_dict() for instr in self.unlimited_dof_instructions]
                },
                "three_dof_per_arm": {
                    "description": "3DOF servo control per arm (shoulder 2-axis + elbow 1-axis)",
                    "servo_specifications": {
                        "range": "0-180 degrees",
                        "axes_per_arm": {
                            "shoulder": ["vertical (up/down)", "horizontal (left/right)"],
                            "elbow": ["vertical (up/down)"]
                        }
                    },
                    "instructions": [step.to_dict() for step in self.three_dof_instructions]
                }
            },
            "execution_metadata": {
                "step_count": len(self.three_dof_instructions),
                "safety_notes": self.safety_notes
            }
        }


class RobotControlGenerator:
    """Generates robotic control instructions from execution plans."""
    
    # Default servo positions (neutral stance)
    NEUTRAL_POSITIONS = {
        "left_shoulder_vertical": 90,    # neutral up/down
        "left_shoulder_horizontal": 45,  # slightly inward
        "left_elbow_vertical": 90,       # 90-degree bend
        "right_shoulder_vertical": 90,   # neutral up/down  
        "right_shoulder_horizontal": 135, # slightly inward (mirrored)
        "right_elbow_vertical": 90       # 90-degree bend
    }
    
    # Movement mappings for different phase types
    PHASE_MOVEMENT_MAPPINGS = {
        "basic_uppercut_technique": {
            "left_arm": {"shoulder_v": 75, "shoulder_h": 60, "elbow_v": 45},
            "right_arm": {"shoulder_v": 60, "shoulder_h": 120, "elbow_v": 30}
        },
        "advanced_footwork_and_combinations": {
            "left_arm": {"shoulder_v": 85, "shoulder_h": 50, "elbow_v": 70},
            "right_arm": {"shoulder_v": 70, "shoulder_h": 130, "elbow_v": 50}
        },
        "timing_and_defense": {
            "left_arm": {"shoulder_v": 95, "shoulder_h": 40, "elbow_v": 80},
            "right_arm": {"shoulder_v": 80, "shoulder_h": 140, "elbow_v": 60}
        }
    }
    
    def __init__(self, llm_config: Optional[LLMConfig] = None):
        # Initialize Cohere servo planner (falls back to heuristics if not available)
        self.servo_planner = CohereServoPlanner(llm_config or LLMConfig())
    
    def generate_robot_instructions(self, execution_plan: ExecutionPlan) -> RobotControlInstructions:
        """Generate complete robot control instructions from execution plan."""
        try:
            # Generate overall strategy reasoning
            overall_strategy = self._generate_overall_strategy(execution_plan)
            
            # Generate unlimited DOF instructions
            unlimited_dof = self._generate_unlimited_dof_instructions(execution_plan)
            
            # Generate 3 DOF instructions
            three_dof = self._generate_three_dof_instructions(execution_plan)
            
            # Generate safety notes
            safety_notes = self._generate_safety_notes(execution_plan)
            
            return RobotControlInstructions(
                skill_name=execution_plan.skill_name,
                unlimited_dof_instructions=unlimited_dof,
                three_dof_instructions=three_dof,
                overall_strategy=overall_strategy,
                safety_notes=safety_notes
            )
            
        except Exception as e:
            logger.error(f"Failed to generate robot instructions: {e}")
            raise
    
    def _generate_unlimited_dof_instructions(self, plan: ExecutionPlan) -> List[UnlimitedDOFInstruction]:
        """Generate unlimited DOF instructions with full 3D positioning."""
        instructions = []
        
        for phase in plan.phases:
            # Generate 3D targets based on phase characteristics
            left_target, right_target = self._calculate_3d_targets(phase)
            
            # Generate spatial reasoning for this movement
            spatial_reasoning = self._generate_spatial_reasoning(phase, left_target, right_target)
            
            instruction = UnlimitedDOFInstruction(
                step_name=phase.name,
                description=f"{phase.cue} - {phase.rationale[:100]}",
                left_arm_target=left_target,
                right_arm_target=right_target,
                spatial_reasoning=spatial_reasoning
            )
            instructions.append(instruction)
        
        return instructions

    def generate_minimal_servo_sequence(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Generate a minimal, actuator-ready servo sequence JSON for the whole skill.

        Structure:
        {
          "skill": str,
          "sequence": [
            { "commands": [ {"id": str, "deg": int}, ... ] },
            ...
          ]
        }

        No textual descriptions or reasoning. Strictly ordered steps only.
        """
        sequence: List[Dict[str, Any]] = []
        # Determine max allowed change per step per joint (degrees)
        # Map max_velocity_hint ∈ (0,1] to a delta between 10° and 45°
        mv = getattr(plan.constraints, "max_velocity_hint", 0.8) or 0.8
        max_delta = int(10 + (max(0.0, min(1.0, mv)) * 35))

        # Maintain last angles to smooth transitions; start from neutral
        last_angles: Dict[str, int] = {
            "left_shoulder_vertical": 90,
            "left_shoulder_horizontal": 90,
            "left_elbow_vertical": 90,
            "right_shoulder_vertical": 90,
            "right_shoulder_horizontal": 90,
            "right_elbow_vertical": 90,
        }

        def clamp_int(v: float) -> int:
            try:
                iv = int(round(float(v)))
            except Exception:
                iv = 90
            return max(0, min(180, iv))

        def smooth(target: int, prev: int) -> int:
            # Limit per-step change to +/- max_delta
            if target > prev + max_delta:
                return prev + max_delta
            if target < prev - max_delta:
                return prev - max_delta
            return target

        seq_counter = 1
        for phase in plan.phases:
            left_target, right_target = self._calculate_3d_targets(phase)
            # Ask for multi-waypoint trajectory to enable richer sequences
            waypoints = self.servo_planner.plan_servo_trajectory(
                skill_name=plan.skill_name,
                phase=phase,
                constraints=plan.constraints,
                left_target=left_target,
                right_target=right_target,
            )

            for wp in waypoints:
                la = wp.get("left_arm", {})
                ra = wp.get("right_arm", {})

                raw = {
                    "left_shoulder_vertical": clamp_int(la.get("shoulder_vertical", 90)),
                    "left_shoulder_horizontal": clamp_int(la.get("shoulder_horizontal", 90)),
                    "left_elbow_vertical": clamp_int(la.get("elbow_vertical", 90)),
                    "right_shoulder_vertical": clamp_int(ra.get("shoulder_vertical", 90)),
                    "right_shoulder_horizontal": clamp_int(ra.get("shoulder_horizontal", 90)),
                    "right_elbow_vertical": clamp_int(ra.get("elbow_vertical", 90)),
                }

                smoothed = {k: smooth(v, last_angles[k]) for k, v in raw.items()}
                last_angles.update(smoothed)

                commands = [
                    {"id": "left_shoulder_vertical", "deg": smoothed["left_shoulder_vertical"]},
                    {"id": "left_shoulder_horizontal", "deg": smoothed["left_shoulder_horizontal"]},
                    {"id": "left_elbow_vertical", "deg": smoothed["left_elbow_vertical"]},
                    {"id": "right_shoulder_vertical", "deg": smoothed["right_shoulder_vertical"]},
                    {"id": "right_shoulder_horizontal", "deg": smoothed["right_shoulder_horizontal"]},
                    {"id": "right_elbow_vertical", "deg": smoothed["right_elbow_vertical"]},
                ]
                sequence.append({"seq_num": seq_counter, "commands": commands})
                seq_counter += 1

        return {"skill": plan.skill_name, "sequence": sequence}
    
    def _calculate_3d_targets(self, phase: ExecutionPhase) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Calculate 3D target positions for unlimited DOF model."""
        # Base positions (neutral stance)
        left_base = {"x": 0.3, "y": 0.2, "z": 1.2, "roll": 0, "pitch": 0, "yaw": 0}
        right_base = {"x": 0.3, "y": -0.2, "z": 1.2, "roll": 0, "pitch": 0, "yaw": 0}
        
        # Modify based on phase name and characteristics
        if "uppercut" in phase.name.lower():
            # Uppercut motion - arms move upward and forward
            left_target = {
                "x": left_base["x"] + 0.2,  # forward
                "y": left_base["y"],
                "z": left_base["z"] + 0.3,  # upward
                "roll": 0.2, "pitch": -0.3, "yaw": 0.1
            }
            right_target = {
                "x": right_base["x"] + 0.4,  # more forward for dominant hand
                "y": right_base["y"],
                "z": right_base["z"] + 0.4,  # higher for power
                "roll": -0.2, "pitch": -0.4, "yaw": -0.1
            }
        elif "footwork" in phase.name.lower():
            # Defensive positioning
            left_target = {
                "x": left_base["x"] - 0.1,
                "y": left_base["y"] + 0.1,
                "z": left_base["z"] + 0.1,
                "roll": 0.1, "pitch": 0.1, "yaw": 0.2
            }
            right_target = {
                "x": right_base["x"],
                "y": right_base["y"] - 0.1,
                "z": right_base["z"] + 0.1,
                "roll": -0.1, "pitch": 0.1, "yaw": -0.2
            }
        else:
            # Default/neutral positioning
            left_target = left_base.copy()
            right_target = right_base.copy()
        
        return left_target, right_target
    
    def _generate_three_dof_instructions(self, plan: ExecutionPlan) -> List[RobotMovementStep]:
        """Generate 3 DOF servo control instructions powered by LLM servo planning."""
        instructions = []
        
        for phase in plan.phases:
            # Compute 3D targets for this phase to guide the reduction to 3DOF
            left_target, right_target = self._calculate_3d_targets(phase)
            
            # Ask LLM (with fallback) to plan explicit servo angles and reasoning
            plan_data = self.servo_planner.plan_servo_positions(
                skill_name=plan.skill_name,
                phase=phase,
                constraints=plan.constraints,
                left_target=left_target,
                right_target=right_target,
            )
            
            # Extract angles and reasoning
            la = plan_data.get("left_arm", {})
            ra = plan_data.get("right_arm", {})
            reason = plan_data.get("reasoning", {})
            
            servo_commands = [
                ServoCommand(
                    servo_id="left_shoulder_vertical",
                    axis=ServoAxis.SHOULDER_VERTICAL,
                    position_degrees=float(la.get("shoulder_vertical", 90)),
                    reasoning=reason.get("left_shoulder_vertical") or self._generate_servo_reasoning("left_shoulder_vertical", float(la.get("shoulder_vertical", 90)), phase)
                ),
                ServoCommand(
                    servo_id="left_shoulder_horizontal", 
                    axis=ServoAxis.SHOULDER_HORIZONTAL,
                    position_degrees=float(la.get("shoulder_horizontal", 90)),
                    reasoning=reason.get("left_shoulder_horizontal") or self._generate_servo_reasoning("left_shoulder_horizontal", float(la.get("shoulder_horizontal", 90)), phase)
                ),
                ServoCommand(
                    servo_id="left_elbow_vertical",
                    axis=ServoAxis.ELBOW_VERTICAL,
                    position_degrees=float(la.get("elbow_vertical", 90)),
                    reasoning=reason.get("left_elbow_vertical") or self._generate_servo_reasoning("left_elbow_vertical", float(la.get("elbow_vertical", 90)), phase)
                ),
                ServoCommand(
                    servo_id="right_shoulder_vertical",
                    axis=ServoAxis.SHOULDER_VERTICAL,
                    position_degrees=float(ra.get("shoulder_vertical", 90)),
                    reasoning=reason.get("right_shoulder_vertical") or self._generate_servo_reasoning("right_shoulder_vertical", float(ra.get("shoulder_vertical", 90)), phase)
                ),
                ServoCommand(
                    servo_id="right_shoulder_horizontal",
                    axis=ServoAxis.SHOULDER_HORIZONTAL,
                    position_degrees=float(ra.get("shoulder_horizontal", 90)),
                    reasoning=reason.get("right_shoulder_horizontal") or self._generate_servo_reasoning("right_shoulder_horizontal", float(ra.get("shoulder_horizontal", 90)), phase)
                ),
                ServoCommand(
                    servo_id="right_elbow_vertical",
                    axis=ServoAxis.ELBOW_VERTICAL,
                    position_degrees=float(ra.get("elbow_vertical", 90)),
                    reasoning=reason.get("right_elbow_vertical") or self._generate_servo_reasoning("right_elbow_vertical", float(ra.get("elbow_vertical", 90)), phase)
                ),
            ]
            
            movement_reasoning = reason.get("movement") or self._generate_movement_reasoning(phase, {})
            
            step = RobotMovementStep(
                step_name=phase.name,
                description=f"{phase.cue} - Execute {phase.name.replace('_', ' ')}",
                servo_commands=servo_commands,
                movement_reasoning=movement_reasoning,
                synchronous=True
            )
            instructions.append(step)
        
        return instructions
    
    def _generate_safety_notes(self, plan: ExecutionPlan) -> List[str]:
        """Generate safety notes for robot operation."""
        safety_notes = [
            "Ensure robot workspace is clear of obstacles and personnel",
            "Verify servo position limits (0-180°) before execution",
            "Monitor servo temperatures during extended operation",
            "Emergency stop must be accessible at all times",
            "Test movements at reduced speed before full execution"
        ]
        
        # Add plan-specific safety notes based on movement complexity
        if len(plan.phases) > 3:
            safety_notes.append("Complex multi-phase movement - verify each step individually")
        
        if any("explosive" in phase.force_profile for phase in plan.phases if phase.force_profile):
            safety_notes.append("High-force movements detected - ensure proper mechanical limits")
        
        return safety_notes
    
    def _generate_overall_strategy(self, plan: ExecutionPlan) -> str:
        """Generate high-level LLM reasoning for the entire skill execution."""
        strategy_parts = [
            f"Executing {plan.skill_name} through {len(plan.phases)} coordinated phases.",
            "The robot will demonstrate proper form and technique by:"
        ]
        
        for i, phase in enumerate(plan.phases, 1):
            strategy_parts.append(f"{i}. {phase.name.replace('_', ' ').title()}: {phase.rationale}")
        
        strategy_parts.append(
            "Each movement is designed to build upon the previous phase, "
            "creating a fluid demonstration of the complete skill while "
            "maintaining safety and proper biomechanical principles."
        )
        
        return " ".join(strategy_parts)
    
    def _generate_spatial_reasoning(self, phase, left_target: Dict[str, float], right_target: Dict[str, float]) -> str:
        """Generate LLM reasoning for 3D spatial positioning."""
        reasoning_parts = []
        
        # Analyze the movement based on phase characteristics
        if "uppercut" in phase.name.lower():
            reasoning_parts.append(
                f"Positioning arms for {phase.name.replace('_', ' ')}: "
                f"Left arm moves to ({left_target['x']:.2f}, {left_target['y']:.2f}, {left_target['z']:.2f}) "
                f"to provide defensive coverage while right arm extends to "
                f"({right_target['x']:.2f}, {right_target['y']:.2f}, {right_target['z']:.2f}) "
                f"for the primary striking motion. The upward trajectory maximizes power transfer."
            )
        elif "footwork" in phase.name.lower():
            reasoning_parts.append(
                f"Defensive positioning for {phase.name.replace('_', ' ')}: "
                f"Arms positioned to maintain guard while allowing mobility. "
                f"Slight inward positioning creates protective stance."
            )
        else:
            reasoning_parts.append(
                f"Neutral positioning for {phase.name.replace('_', ' ')}: "
                f"Balanced arm placement maintains readiness for subsequent movements."
            )
        
        return " ".join(reasoning_parts)
    
    def _generate_servo_reasoning(self, servo_id: str, position: float, phase) -> str:
        """Generate LLM reasoning for individual servo positions."""
        servo_type = servo_id.split('_')[-1]  # vertical or horizontal
        arm_side = servo_id.split('_')[0]     # left or right
        joint = servo_id.split('_')[1]        # shoulder or elbow
        
        reasoning_map = {
            "shoulder_vertical": {
                "low": f"{arm_side.title()} shoulder lowered ({position}°) for defensive positioning",
                "mid": f"{arm_side.title()} shoulder at neutral ({position}°) for balanced stance", 
                "high": f"{arm_side.title()} shoulder raised ({position}°) for striking preparation"
            },
            "shoulder_horizontal": {
                "inward": f"{arm_side.title()} shoulder positioned inward ({position}°) for guard protection",
                "neutral": f"{arm_side.title()} shoulder at neutral width ({position}°) for mobility",
                "outward": f"{arm_side.title()} shoulder extended outward ({position}°) for reach"
            },
            "elbow_vertical": {
                "bent": f"{arm_side.title()} elbow bent ({position}°) for power generation",
                "neutral": f"{arm_side.title()} elbow at neutral ({position}°) for balance",
                "extended": f"{arm_side.title()} elbow extended ({position}°) for reach"
            }
        }
        
        # Determine position category
        if position < 60:
            category = "low" if servo_type == "vertical" else ("inward" if position < 90 else "bent")
        elif position > 120:
            category = "high" if servo_type == "vertical" else ("outward" if position > 90 else "extended")
        else:
            category = "mid" if servo_type == "vertical" else "neutral"
        
        servo_key = f"{joint}_{servo_type}"
        return reasoning_map.get(servo_key, {}).get(category, f"{servo_id} positioned at {position}° for {phase.name}")
    
    def _generate_movement_reasoning(self, phase, movement: Dict) -> str:
        """Generate LLM reasoning for overall movement pattern."""
        reasoning_parts = [
            f"Movement pattern for {phase.name.replace('_', ' ')}: {phase.rationale}",
            f"Cue: '{phase.cue}'",
            "Servo coordination creates biomechanically sound movement that demonstrates proper technique while maintaining safety."
        ]
        
        return " ".join(reasoning_parts)
