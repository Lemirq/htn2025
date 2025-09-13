"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useRef, useState, useEffect } from "react";
import * as THREE from "three";

// Movement presets
export interface MovementPreset {
  name: string;
  description: string;
  leftArmRotation: [number, number, number];
  rightArmRotation: [number, number, number];
  leftForearmRotation: [number, number, number];
  rightForearmRotation: [number, number, number];
  duration: number;
}

export const MOVEMENT_PRESETS: Record<string, MovementPreset> = {
  idle: {
    name: "Idle",
    description: "Default resting position",
    leftArmRotation: [0, 0, 0],
    rightArmRotation: [0, 0, 0],
    leftForearmRotation: [0, 0, 0],
    rightForearmRotation: [0, 0, 0],
    duration: 1000,
  },
  wave: {
    name: "Wave Hello",
    description: "Friendly waving gesture",
    leftArmRotation: [0, 0, 0],
    rightArmRotation: [0, 0, -Math.PI / 3],
    leftForearmRotation: [0, 0, 0],
    rightForearmRotation: [-Math.PI / 4, 0, 0],
    duration: 2000,
  },
  reachUp: {
    name: "Reach Up",
    description: "Both arms reaching upward",
    leftArmRotation: [0, 0, Math.PI / 2],
    rightArmRotation: [0, 0, -Math.PI / 2],
    leftForearmRotation: [0, 0, 0],
    rightForearmRotation: [0, 0, 0],
    duration: 1500,
  },
  crossArms: {
    name: "Cross Arms",
    description: "Arms crossed over chest",
    leftArmRotation: [0, Math.PI / 4, -Math.PI / 6],
    rightArmRotation: [0, -Math.PI / 4, Math.PI / 6],
    leftForearmRotation: [-Math.PI / 3, 0, 0],
    rightForearmRotation: [-Math.PI / 3, 0, 0],
    duration: 1500,
  },
  pointForward: {
    name: "Point Forward",
    description: "Right arm pointing straight ahead",
    leftArmRotation: [0, 0, 0],
    rightArmRotation: [0, -Math.PI / 2, 0],
    leftForearmRotation: [0, 0, 0],
    rightForearmRotation: [0, 0, 0],
    duration: 1200,
  },
  celebrate: {
    name: "Celebrate",
    description: "Victory pose with arms up",
    leftArmRotation: [0, 0, Math.PI / 3],
    rightArmRotation: [0, 0, -Math.PI / 3],
    leftForearmRotation: [-Math.PI / 4, 0, 0],
    rightForearmRotation: [-Math.PI / 4, 0, 0],
    duration: 2000,
  },
};

interface RobotProps {
  currentMovement: string;
  onMovementComplete: () => void;
}

// Robot component that creates the 3D model with animations
function Robot({ currentMovement, onMovementComplete }: RobotProps) {
  const robotRef = useRef<THREE.Group>(null);
  const leftArmRef = useRef<THREE.Group>(null);
  const rightArmRef = useRef<THREE.Group>(null);
  const leftForearmRef = useRef<THREE.Group>(null);
  const rightForearmRef = useRef<THREE.Group>(null);

  const [animationProgress, setAnimationProgress] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [startTime, setStartTime] = useState(0);
  const [targetMovement, setTargetMovement] = useState<MovementPreset>(
    MOVEMENT_PRESETS.idle
  );
  const [initialRotations, setInitialRotations] = useState({
    leftArm: [0, 0, 0] as [number, number, number],
    rightArm: [0, 0, 0] as [number, number, number],
    leftForearm: [0, 0, 0] as [number, number, number],
    rightForearm: [0, 0, 0] as [number, number, number],
  });

  // Start animation when movement changes
  useEffect(() => {
    if (currentMovement && MOVEMENT_PRESETS[currentMovement]) {
      const movement = MOVEMENT_PRESETS[currentMovement];

      // Store current rotations as initial state
      setInitialRotations({
        leftArm: leftArmRef.current
          ? [
              leftArmRef.current.rotation.x,
              leftArmRef.current.rotation.y,
              leftArmRef.current.rotation.z,
            ]
          : [0, 0, 0],
        rightArm: rightArmRef.current
          ? [
              rightArmRef.current.rotation.x,
              rightArmRef.current.rotation.y,
              rightArmRef.current.rotation.z,
            ]
          : [0, 0, 0],
        leftForearm: leftForearmRef.current
          ? [
              leftForearmRef.current.rotation.x,
              leftForearmRef.current.rotation.y,
              leftForearmRef.current.rotation.z,
            ]
          : [0, 0, 0],
        rightForearm: rightForearmRef.current
          ? [
              rightForearmRef.current.rotation.x,
              rightForearmRef.current.rotation.y,
              rightForearmRef.current.rotation.z,
            ]
          : [0, 0, 0],
      });

      setTargetMovement(movement);
      setIsAnimating(true);
      setAnimationProgress(0);
      setStartTime(Date.now());
    }
  }, [currentMovement]);

  // Animation frame
  useFrame(() => {
    if (!isAnimating) return;

    const elapsed = Date.now() - startTime;
    const progress = Math.min(elapsed / targetMovement.duration, 1);

    // Smooth easing function
    const easeInOutCubic = (t: number) =>
      t < 0.5 ? 4 * t * t * t : (t - 1) * (2 * t - 2) * (2 * t - 2) + 1;
    const easedProgress = easeInOutCubic(progress);

    // Interpolate rotations
    if (leftArmRef.current) {
      leftArmRef.current.rotation.x = THREE.MathUtils.lerp(
        initialRotations.leftArm[0],
        targetMovement.leftArmRotation[0],
        easedProgress
      );
      leftArmRef.current.rotation.y = THREE.MathUtils.lerp(
        initialRotations.leftArm[1],
        targetMovement.leftArmRotation[1],
        easedProgress
      );
      leftArmRef.current.rotation.z = THREE.MathUtils.lerp(
        initialRotations.leftArm[2],
        targetMovement.leftArmRotation[2],
        easedProgress
      );
    }

    if (rightArmRef.current) {
      rightArmRef.current.rotation.x = THREE.MathUtils.lerp(
        initialRotations.rightArm[0],
        targetMovement.rightArmRotation[0],
        easedProgress
      );
      rightArmRef.current.rotation.y = THREE.MathUtils.lerp(
        initialRotations.rightArm[1],
        targetMovement.rightArmRotation[1],
        easedProgress
      );
      rightArmRef.current.rotation.z = THREE.MathUtils.lerp(
        initialRotations.rightArm[2],
        targetMovement.rightArmRotation[2],
        easedProgress
      );
    }

    if (leftForearmRef.current) {
      leftForearmRef.current.rotation.x = THREE.MathUtils.lerp(
        initialRotations.leftForearm[0],
        targetMovement.leftForearmRotation[0],
        easedProgress
      );
      leftForearmRef.current.rotation.y = THREE.MathUtils.lerp(
        initialRotations.leftForearm[1],
        targetMovement.leftForearmRotation[1],
        easedProgress
      );
      leftForearmRef.current.rotation.z = THREE.MathUtils.lerp(
        initialRotations.leftForearm[2],
        targetMovement.leftForearmRotation[2],
        easedProgress
      );
    }

    if (rightForearmRef.current) {
      rightForearmRef.current.rotation.x = THREE.MathUtils.lerp(
        initialRotations.rightForearm[0],
        targetMovement.rightForearmRotation[0],
        easedProgress
      );
      rightForearmRef.current.rotation.y = THREE.MathUtils.lerp(
        initialRotations.rightForearm[1],
        targetMovement.rightForearmRotation[1],
        easedProgress
      );
      rightForearmRef.current.rotation.z = THREE.MathUtils.lerp(
        initialRotations.rightForearm[2],
        targetMovement.rightForearmRotation[2],
        easedProgress
      );
    }

    setAnimationProgress(progress);

    // Animation complete
    if (progress >= 1) {
      setIsAnimating(false);
      onMovementComplete();
    }
  });

  return (
    <group ref={robotRef}>
      {/* Torso */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[1, 2, 0.5]} />
        <meshStandardMaterial color="#4a90e2" />
      </mesh>

      {/* Left Arm */}
      <group ref={leftArmRef} position={[-0.75, 0.5, 0]}>
        {/* Upper arm */}
        <mesh position={[-0.5, 0, 0]}>
          <boxGeometry args={[1, 0.3, 0.3]} />
          <meshStandardMaterial color="#357abd" />
        </mesh>
        {/* Lower arm group */}
        <group ref={leftForearmRef} position={[-1, 0, 0]}>
          <mesh position={[-0.2, -0.5, 0]}>
            <boxGeometry args={[0.8, 0.25, 0.25]} />
            <meshStandardMaterial color="#2c5aa0" />
          </mesh>
          {/* Hand */}
          <mesh position={[-0.7, -0.5, 0]}>
            <sphereGeometry args={[0.15]} />
            <meshStandardMaterial color="#1e3a8a" />
          </mesh>
        </group>
      </group>

      {/* Right Arm */}
      <group ref={rightArmRef} position={[0.75, 0.5, 0]}>
        {/* Upper arm */}
        <mesh position={[0.5, 0, 0]}>
          <boxGeometry args={[1, 0.3, 0.3]} />
          <meshStandardMaterial color="#357abd" />
        </mesh>
        {/* Lower arm group */}
        <group ref={rightForearmRef} position={[1, 0, 0]}>
          <mesh position={[0.2, -0.5, 0]}>
            <boxGeometry args={[0.8, 0.25, 0.25]} />
            <meshStandardMaterial color="#2c5aa0" />
          </mesh>
          {/* Hand */}
          <mesh position={[0.7, -0.5, 0]}>
            <sphereGeometry args={[0.15]} />
            <meshStandardMaterial color="#1e3a8a" />
          </mesh>
        </group>
      </group>
    </group>
  );
}

export default function RobotViewer() {
  return (
    <div className="w-full h-full relative">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 bg-gray-800 bg-opacity-90 p-4 border-b border-gray-700">
        <h2 className="text-white text-xl font-semibold">
          Robot Control Panel
        </h2>
        <p className="text-gray-300 text-sm">
          Click and drag to orbit around the robot
        </p>
      </div>

      {/* 3D Canvas */}
      <Canvas
        camera={{ position: [5, 2, 5], fov: 50 }}
        className="w-full h-full"
      >
        {/* Lighting */}
        <ambientLight intensity={0.4} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <pointLight position={[-10, -10, -5]} intensity={0.5} />

        {/* Robot Model */}
        <Robot currentMovement="idle" onMovementComplete={() => {}} />

        {/* Orbit Controls */}
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          minDistance={3}
          maxDistance={15}
          target={[0, 0, 0]}
        />

        {/* Grid Helper */}
        <gridHelper args={[10, 10]} />
      </Canvas>

      {/* Controls Info */}
      <div className="absolute bottom-4 left-4 bg-gray-800 bg-opacity-90 p-3 rounded-lg border border-gray-700">
        <div className="text-white text-sm space-y-1">
          <div>
            <strong>Left Click + Drag:</strong> Rotate
          </div>
          <div>
            <strong>Right Click + Drag:</strong> Pan
          </div>
          <div>
            <strong>Scroll:</strong> Zoom
          </div>
        </div>
      </div>
    </div>
  );
}
