"""Test script for robot controller functionality."""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.services.robot_controller import RobotControlGenerator
from src.core.models import ExecutionPlan, ExecutionPhase, PhysicalConstraints

def test_robot_controller():
    """Test the robot control generator with sample data."""
    
    # Create sample execution phases (similar to boxing uppercut)
    phases = [
        ExecutionPhase(
            name="basic_uppercut_technique",
            duration_ms=600,
            cue="Focus on rotating your body and driving the punch upward",
            pose_hints="Start from orthodox stance, rotate body, drive dominant hand up",
            rationale="Foundation for all uppercut variations",
            velocity_profile="medium",
            force_profile="controlled"
        ),
        ExecutionPhase(
            name="advanced_footwork_and_combinations", 
            duration_ms=700,
            cue="Focus on smooth, controlled footwork",
            pose_hints="Practice stepping forward, pivot on front foot",
            rationale="Improves distance closing and angle changes",
            velocity_profile="medium",
            force_profile="controlled"
        ),
        ExecutionPhase(
            name="timing_and_defense",
            duration_ms=800,
            cue="Visualize opponent's guard dropping",
            pose_hints="Practice at different speeds, work on defensive movements",
            rationale="Crucial for landing effective uppercuts",
            velocity_profile="medium", 
            force_profile="controlled"
        )
    ]
    
    # Create sample constraints
    constraints = PhysicalConstraints(
        max_velocity_hint=0.7667,
        keep_com_in_base=True,
        workspace_hint="sport-specific movement patterns",
        joint_limits={
            "shoulder_flexion": 170.0,
            "elbow_extension": 160.0
        },
        safety_margins={
            "impact_force": 0.701,
            "joint_stress": 0.751
        }
    )
    
    # Create execution plan
    plan = ExecutionPlan(
        skill_name="How to Throw an Effective Uppercut in Boxing",
        phases=phases,
        constraints=constraints,
        provenance=[],
        complexity_score=0.81
    )
    
    # Generate robot instructions
    generator = RobotControlGenerator()
    robot_instructions = generator.generate_robot_instructions(plan)
    
    # Print results
    print("=== ROBOT CONTROL INSTRUCTIONS TEST ===")
    print(f"Skill: {robot_instructions.skill_name}")
    print(f"Total Duration: {robot_instructions.total_duration_ms}ms")
    print(f"Safety Notes: {len(robot_instructions.safety_notes)} items")
    print()
    
    print("=== UNLIMITED DOF INSTRUCTIONS ===")
    for i, instr in enumerate(robot_instructions.unlimited_dof_instructions):
        print(f"{i+1}. {instr.step_name}")
        print(f"   Left arm: x={instr.left_arm_target['x']}, y={instr.left_arm_target['y']}, z={instr.left_arm_target['z']}")
        print(f"   Right arm: x={instr.right_arm_target['x']}, y={instr.right_arm_target['y']}, z={instr.right_arm_target['z']}")
        print(f"   Duration: {instr.duration_ms}ms")
        print()
    
    print("=== 3 DOF INSTRUCTIONS ===")
    for i, step in enumerate(robot_instructions.three_dof_instructions):
        print(f"{i+1}. {step.step_name}")
        print(f"   Description: {step.description}")
        print(f"   Servo commands: {len(step.servo_commands)}")
        for cmd in step.servo_commands:
            print(f"     - {cmd.servo_id}: {cmd.position_degrees}° ({cmd.axis.value})")
        print(f"   Duration: {step.total_duration_ms}ms")
        print()
    
    print("=== SAFETY NOTES ===")
    for note in robot_instructions.safety_notes:
        print(f"  • {note}")
    
    return robot_instructions

if __name__ == "__main__":
    test_robot_controller()
