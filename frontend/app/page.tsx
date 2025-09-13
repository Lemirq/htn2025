"use client";

import RobotViewer from "./components/RobotViewer";
import ChatInterface from "./components/ChatInterface";

export default function Home() {
  return (
    <div className="h-screen flex bg-gray-900">
      {/* Left Pane - 3D Robot Viewer */}
      <div className="w-2/3 bg-gray-800 border-r border-gray-700">
        <RobotViewer />
      </div>

      {/* Right Pane - AI Chat Interface */}
      <div className="w-1/3 bg-gray-900">
        <ChatInterface />
      </div>
    </div>
  );
}
