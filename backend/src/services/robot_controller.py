"""Robotic arm control instruction generator for upper body movements."""
from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

from ..core.models import ExecutionPlan, ExecutionPhase

logger = logging.getLogger(__name__)


class ServoAxis(Enum):
    """Servo axis types for 3 DOF model."""
    SHOULDER_VERTICAL = "shoulder_vertical"      # up/down
    SHOULDER_HORIZONTAL = "shoulder_horizontal"  # left/right  
    ELBOW_VERTICAL = "elbow_vertical"           # up/down


@dataclass
class ServoCommand:
    """Individual servo command with position and timing."""
    servo_id: str
    axis: ServoAxis
    position_degrees: float  # 0-180 degrees
    duration_ms: int
    velocity_profile: str = "smooth"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "servo_id": self.servo_id,
            "axis": self.axis.value,
            "position_degrees": round(self.position_degrees, 1),
            "duration_ms": self.duration_ms,
            "velocity_profile": self.velocity_profile
        }


@dataclass
class RobotMovementStep:
    """Single movement step with multiple servo commands."""
    step_name: str
    description: str
    servo_commands: List[ServoCommand]
    total_duration_ms: int
    synchronous: bool = True  # Execute all commands simultaneously
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "description": self.description,
            "servo_commands": [cmd.to_dict() for cmd in self.servo_commands],
            "total_duration_ms": self.total_duration_ms,
            "synchronous": self.synchronous
        }


@dataclass
class UnlimitedDOFInstruction:
    """Unlimited DOF movement instruction with full 3D coordinates."""
    step_name: str
    description: str
    left_arm_target: Dict[str, float]   # 3D position and orientation
    right_arm_target: Dict[str, float]  # 3D position and orientation
    duration_ms: int
    velocity_profile: str = "smooth"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "description": self.description,
            "left_arm_target": self.left_arm_target,
            "right_arm_target": self.right_arm_target,
            "duration_ms": self.duration_ms,
            "velocity_profile": self.velocity_profile
        }


@dataclass
class RobotControlInstructions:
    """Complete robot control instructions for both DOF models."""
    skill_name: str
    unlimited_dof_instructions: List[UnlimitedDOFInstruction]
    three_dof_instructions: List[RobotMovementStep]
    total_duration_ms: int
    safety_notes: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "robot_control_formats": {
                "unlimited_dof": {
                    "description": "Full 6DOF control per arm with 3D positioning and orientation",
                    "coordinate_system": "right_handed_cartesian",
                    "units": {
                        "position": "meters",
                        "orientation": "radians",
                        "time": "milliseconds"
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
                "total_duration_ms": self.total_duration_ms,
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
    
    def __init__(self):
        pass
    
    def generate_robot_instructions(self, execution_plan: ExecutionPlan) -> RobotControlInstructions:
        """Generate complete robot control instructions from execution plan."""
        try:
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
                total_duration_ms=execution_plan.total_duration_ms,
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
            
            instruction = UnlimitedDOFInstruction(
                step_name=phase.name,
                description=f"{phase.cue} - {phase.rationale[:100]}",
                left_arm_target=left_target,
                right_arm_target=right_target,
                duration_ms=phase.duration_ms,
                velocity_profile=phase.velocity_profile or "smooth"
            )
            instructions.append(instruction)
        
        return instructions
    
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
        """Generate 3 DOF servo control instructions."""
        instructions = []
        
        for phase in plan.phases:
            # Get movement mapping for this phase
            movement = self.PHASE_MOVEMENT_MAPPINGS.get(
                phase.name, 
                self.PHASE_MOVEMENT_MAPPINGS["basic_uppercut_technique"]  # default
            )
            
            # Create servo commands
            servo_commands = []
            
            # Left arm servos
            servo_commands.extend([
                ServoCommand(
                    servo_id="left_shoulder_vertical",
                    axis=ServoAxis.SHOULDER_VERTICAL,
                    position_degrees=movement["left_arm"]["shoulder_v"],
                    duration_ms=phase.duration_ms,
                    velocity_profile=phase.velocity_profile or "smooth"
                ),
                ServoCommand(
                    servo_id="left_shoulder_horizontal", 
                    axis=ServoAxis.SHOULDER_HORIZONTAL,
                    position_degrees=movement["left_arm"]["shoulder_h"],
                    duration_ms=phase.duration_ms,
                    velocity_profile=phase.velocity_profile or "smooth"
                ),
                ServoCommand(
                    servo_id="left_elbow_vertical",
                    axis=ServoAxis.ELBOW_VERTICAL,
                    position_degrees=movement["left_arm"]["elbow_v"],
                    duration_ms=phase.duration_ms,
                    velocity_profile=phase.velocity_profile or "smooth"
                )
            ])
            
            # Right arm servos
            servo_commands.extend([
                ServoCommand(
                    servo_id="right_shoulder_vertical",
                    axis=ServoAxis.SHOULDER_VERTICAL,
                    position_degrees=movement["right_arm"]["shoulder_v"],
                    duration_ms=phase.duration_ms,
                    velocity_profile=phase.velocity_profile or "smooth"
                ),
                ServoCommand(
                    servo_id="right_shoulder_horizontal",
                    axis=ServoAxis.SHOULDER_HORIZONTAL,
                    position_degrees=movement["right_arm"]["shoulder_h"],
                    duration_ms=phase.duration_ms,
                    velocity_profile=phase.velocity_profile or "smooth"
                ),
                ServoCommand(
                    servo_id="right_elbow_vertical",
                    axis=ServoAxis.ELBOW_VERTICAL,
                    position_degrees=movement["right_arm"]["elbow_v"],
                    duration_ms=phase.duration_ms,
                    velocity_profile=phase.velocity_profile or "smooth"
                )
            ])
            
            step = RobotMovementStep(
                step_name=phase.name,
                description=f"{phase.cue} - Execute {phase.name.replace('_', ' ')}",
                servo_commands=servo_commands,
                total_duration_ms=phase.duration_ms,
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
        
        # Add plan-specific safety notes
        if plan.total_duration_ms < 1000:
            safety_notes.append("High-speed movements detected - verify servo response times")
        
        if any("explosive" in phase.velocity_profile for phase in plan.phases if phase.velocity_profile):
            safety_notes.append("Explosive movements require careful acceleration/deceleration profiles")
        
        return safety_notes
