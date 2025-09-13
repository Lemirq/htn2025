import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Environment } from '@react-three/drei';
import { Mesh, Group } from 'three';

// Robot component with torso and two arms
function Robot() {
  const groupRef = useRef<Group>(null);
  const leftArmRef = useRef<Mesh>(null);
  const rightArmRef = useRef<Mesh>(null);

  useFrame((state) => {
    if (leftArmRef.current && rightArmRef.current) {
      // Subtle floating animation
      leftArmRef.current.rotation.z = Math.sin(state.clock.elapsedTime) * 0.1;
      rightArmRef.current.rotation.z = -Math.sin(state.clock.elapsedTime) * 0.1;
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
      
      {/* Left Arm */}
      <mesh ref={leftArmRef} position={[-0.8, 0.3, 0]}>
        <boxGeometry args={[0.3, 1.2, 0.3]} />
        <meshPhysicalMaterial 
          color="#00ffff" 
          metalness={0.9}
          roughness={0.1}
          transmission={0.2}
          transparent
          opacity={0.8}
        />
      </mesh>
      
      {/* Right Arm */}
      <mesh ref={rightArmRef} position={[0.8, 0.3, 0]}>
        <boxGeometry args={[0.3, 1.2, 0.3]} />
        <meshPhysicalMaterial 
          color="#00ffff" 
          metalness={0.9}
          roughness={0.1}
          transmission={0.2}
          transparent
          opacity={0.8}
        />
      </mesh>

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
  return (
    <div className="h-full w-full relative overflow-hidden rounded-lg bg-gradient-mesh">
      <div className="absolute inset-0 bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-lg" />
      
      <Canvas
        camera={{ position: [3, 2, 3], fov: 50 }}
        className="relative z-10"
      >
        <ambientLight intensity={0.3} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <pointLight position={[-10, -10, -10]} color="#00bfff" intensity={0.5} />
        
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
      
      <div className="absolute bottom-4 left-4 z-20">
        <div className="bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-lg p-2 text-xs text-foreground/60">
          Click and drag to rotate • Scroll to zoom
        </div>
      </div>
    </div>
  );
};