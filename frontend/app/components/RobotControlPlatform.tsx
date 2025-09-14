import { RobotViewer } from "./RobotViewer";
import { ChatInterface } from "./ChatInterface";

export const RobotControlPlatform = () => {
  return (
    <div className="min-h-screen bg-background bg-gradient-mesh relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 bg-gradient-mesh opacity-50" />

      {/* Main content */}
      <div className="relative z-10 h-screen flex">
        {/* Left Panel - 3D Robot Viewer */}
        <div className="flex-1 p-4">
          <div className="h-full bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-xl shadow-glass overflow-hidden">
            <RobotViewer />
          </div>
        </div>

        {/* Right Panel - Chat Interface */}
        <div className="w-[400px] py-4 pr-2">
          <div className="h-full bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-xl shadow-glass overflow-hidden">
            <ChatInterface />
          </div>
        </div>
      </div>
    </div>
  );
};
