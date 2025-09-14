import { useEffect, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Environment } from "@react-three/drei";
import { Group } from "three";
import { skillAPI, FinalMovementsCommand, FinalMovementsStep } from "@/lib/api";
import { Button } from "@/components/ui/button";

// Robot component with torso and two arms
function Robot() {
  const groupRef = useRef<Group>(null);
  // Left arm with two joints
  const leftShoulderRef = useRef<Group>(null);
  const leftElbowRef = useRef<Group>(null);
  // Right arm with two joints
  const rightShoulderRef = useRef<Group>(null);
  const rightElbowRef = useRef<Group>(null);

  // Track current and target angles per servo id
  const currentAnglesRef = useRef<Record<string, number>>({
    left_shoulder_vertical: 90,
    left_shoulder_horizontal: 90,
    left_elbow_vertical: 90,
    right_shoulder_vertical: 90,
    right_shoulder_horizontal: 90,
    right_elbow_vertical: 90,
  });
  const targetAnglesRef = useRef<Record<string, number>>({
    left_shoulder_vertical: 90,
    left_shoulder_horizontal: 90,
    left_elbow_vertical: 90,
    right_shoulder_vertical: 90,
    right_shoulder_horizontal: 90,
    right_elbow_vertical: 90,
  });

  // Subscribe to final_movements and step through the sequence
  useEffect(() => {
    console.log("[RobotViewer] Registering final_movements listener");
    const unsubscribe = skillAPI.onFinalMovements((payload) => {
      try {
        console.log("[RobotViewer] Received final_movements payload:", payload);
        const sequence: FinalMovementsStep[] = Array.isArray(payload?.sequence)
          ? payload.sequence
          : [];
        console.log("[RobotViewer] Parsed sequence length:", sequence.length);
        let stepIndex = 0;
        const stepDelayMs = 200;
        console.log("[RobotViewer] Using stepDelayMs:", stepDelayMs);

        const applyNext = () => {
          console.log("[RobotViewer] applyNext called. stepIndex:", stepIndex);
          if (stepIndex >= sequence.length) {
            console.log(
              "[RobotViewer] Sequence complete. Total steps:",
              sequence.length
            );
            return;
          }
          const step = sequence[stepIndex];
          const cmds: FinalMovementsCommand[] = Array.isArray(step?.commands)
            ? step.commands
            : [];
          console.log(
            `[RobotViewer] Applying step ${stepIndex + 1}/${sequence.length} with commands:`,
            cmds
          );
          cmds.forEach((cmd) => {
            const id = String(cmd?.id || "");
            const deg = Math.max(0, Math.min(180, Number(cmd?.deg ?? 90)));
            if (id in targetAnglesRef.current) {
              console.log(
                `[RobotViewer] Setting target angle for ${id} -> ${deg}°`
              );
              targetAnglesRef.current[id] = deg;
            } else {
              console.warn(
                `[RobotViewer] Unknown servo id '${id}'. Command ignored.`,
                cmd
              );
            }
          });
          stepIndex += 1;
          console.log(
            `[RobotViewer] Scheduling next step (index ${stepIndex}) in ${stepDelayMs}ms`
          );
          setTimeout(applyNext, stepDelayMs);
        };

        applyNext();
      } catch (e) {
        console.error("Failed to apply final_movements to viewer", e);
      }
    });
    return () => {
      console.log("[RobotViewer] Unsubscribing final_movements listener");
      unsubscribe();
    };
  }, []);

  // Lerp current angles toward targets and apply to joint rotations
  useFrame((state, delta) => {
    const lerpFactor = 1 - Math.pow(0.001, delta); // smooth approach
    const ids = Object.keys(currentAnglesRef.current);
    ids.forEach((id) => {
      const cur = currentAnglesRef.current[id];
      const tgt = targetAnglesRef.current[id];
      currentAnglesRef.current[id] = cur + (tgt - cur) * lerpFactor;
    });

    // Helper: degrees -> centered radians (-90..+90 => -PI/2..+PI/2)
    const toRad = (deg: number) => ((deg - 90) * Math.PI) / 180;

    // Apply mapped rotations
    const a = currentAnglesRef.current;
    if (leftShoulderRef.current) {
      // vertical around Z, horizontal around Y
      leftShoulderRef.current.rotation.z = toRad(a.left_shoulder_vertical);
      leftShoulderRef.current.rotation.y = toRad(a.left_shoulder_horizontal);
    }
    if (leftElbowRef.current) {
      leftElbowRef.current.rotation.z = toRad(a.left_elbow_vertical);
    }
    if (rightShoulderRef.current) {
      // mirror horizontal axis for right arm for a natural look
      rightShoulderRef.current.rotation.z = toRad(a.right_shoulder_vertical);
      rightShoulderRef.current.rotation.y = -toRad(a.right_shoulder_horizontal);
    }
    if (rightElbowRef.current) {
      rightElbowRef.current.rotation.z = toRad(a.right_elbow_vertical);
    }
  });

  return (
    <group ref={groupRef}>
      {/* Torso */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[1, 1.5, 0.5]} />
        <meshPhysicalMaterial
          color="#00bfff"
          metalness={0.8}
          roughness={0.2}
          transmission={0.1}
          transparent
          opacity={0.9}
        />
      </mesh>

      {/* Left Arm - two joints (shoulder -> elbow) */}
      <group ref={leftShoulderRef} position={[-0.8, 0.3, 0]}>
        {/* Upper arm pivoted at shoulder; move geometry so pivot is at top */}
        <mesh position={[0, -0.3, 0]}>
          <boxGeometry args={[0.25, 0.6, 0.25]} />
          <meshPhysicalMaterial
            color="#00ffff"
            metalness={0.9}
            roughness={0.1}
            transmission={0.2}
            transparent
            opacity={0.85}
          />
        </mesh>
        {/* Elbow joint */}
        <group ref={leftElbowRef} position={[0, -0.6, 0]}>
          {/* Forearm pivoted at elbow; move geometry so pivot is at top of forearm */}
          <mesh position={[0, -0.35, 0]}>
            <boxGeometry args={[0.22, 0.7, 0.22]} />
            <meshPhysicalMaterial
              color="#8affff"
              metalness={0.9}
              roughness={0.1}
              transmission={0.2}
              transparent
              opacity={0.85}
            />
          </mesh>
        </group>
      </group>

      {/* Right Arm - two joints (shoulder -> elbow) */}
      <group ref={rightShoulderRef} position={[0.8, 0.3, 0]}>
        {/* Upper arm */}
        <mesh position={[0, -0.3, 0]}>
          <boxGeometry args={[0.25, 0.6, 0.25]} />
          <meshPhysicalMaterial
            color="#00ffff"
            metalness={0.9}
            roughness={0.1}
            transmission={0.2}
            transparent
            opacity={0.85}
          />
        </mesh>
        {/* Elbow joint */}
        <group ref={rightElbowRef} position={[0, -0.6, 0]}>
          <mesh position={[0, -0.35, 0]}>
            <boxGeometry args={[0.22, 0.7, 0.22]} />
            <meshPhysicalMaterial
              color="#8affff"
              metalness={0.9}
              roughness={0.1}
              transmission={0.2}
              transparent
              opacity={0.85}
            />
          </mesh>
        </group>
      </group>

      {/* Robot "eyes" - glowing spheres */}
      <mesh position={[-0.2, 0.4, 0.26]}>
        <sphereGeometry args={[0.05]} />
        <meshBasicMaterial color="#00ffff" />
      </mesh>
      <mesh position={[0.2, 0.4, 0.26]}>
        <sphereGeometry args={[0.05]} />
        <meshBasicMaterial color="#00ffff" />
      </mesh>
    </group>
  );
}

export const RobotViewer = () => {
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrateMsg, setCalibrateMsg] = useState<string | null>(null);

  const handleCalibrate = async () => {
    setIsCalibrating(true);
    setCalibrateMsg(null);
    try {
      const res = await skillAPI.calibrateRobot();
      setCalibrateMsg(res.message || "Calibration triggered");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Calibration failed";
      setCalibrateMsg(`❌ ${msg}`);
    } finally {
      setIsCalibrating(false);
    }
  };

  return (
    <div className="h-full w-full relative overflow-hidden rounded-lg bg-gradient-mesh">
      <div className="absolute inset-0 bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-lg" />

      <Canvas
        camera={{ position: [3, 2, 3], fov: 50 }}
        className="relative z-10"
      >
        <ambientLight intensity={0.3} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <pointLight
          position={[-10, -10, -10]}
          color="#00bfff"
          intensity={0.5}
        />

        <Robot />

        <OrbitControls
          enablePan={false}
          minDistance={2}
          maxDistance={8}
          maxPolarAngle={Math.PI / 2}
        />

        <Environment preset="city" />
      </Canvas>

      {/* UI Overlay */}
      <div className="absolute top-4 left-4 z-20">
        <div className="bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-lg p-3">
          <div className="text-neon text-sm font-medium">Robot Status</div>
          <div className="text-foreground/80 text-xs">Online • Ready</div>
        </div>
      </div>

      {/* Reset/Calibrate Button */}
      <div className="absolute top-4 right-4 z-20 flex flex-col items-end gap-2">
        <Button
          onClick={handleCalibrate}
          disabled={isCalibrating}
          className="bg-primary text-primary-foreground hover:bg-primary/90"
          size="sm"
        >
          {isCalibrating ? "Resetting..." : "Reset Robot"}
        </Button>
        {calibrateMsg && (
          <div className="text-xs bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-md px-2 py-1 text-foreground/80 max-w-[240px]">
            {calibrateMsg}
          </div>
        )}
      </div>

      <div className="absolute bottom-4 left-4 z-20">
        <div className="bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-lg p-2 text-xs text-foreground/60">
          Click and drag to rotate • Scroll to zoom
        </div>
      </div>
    </div>
  );
};
