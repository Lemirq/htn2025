"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Send,
  Bot,
  User,
  Loader2,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import { skillAPI, SkillProcessingUpdate, SkillBundle } from "@/lib/api";

// Define specific types for message data
interface ProgressData {
  source_count?: number;
  title?: string;
  step_count?: number;
  difficulty?: number;
  bundle?: SkillBundle;
  error?: string;
}

interface Message {
  id: string;
  content: string;
  sender: "user" | "bot";
  timestamp: Date;
  type?: "text" | "progress" | "result" | "error";
  data?: SkillBundle | ProgressData;
}

interface ProgressState {
  step: string;
  progress: number;
  isActive: boolean;
  data?: ProgressData;
}

export const ChatInterface = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      content:
        "Hello! I'm your robot control assistant. Describe the movements you want the robot to perform, and I'll help translate them into actions.",
      sender: "bot",
      timestamp: new Date(),
      type: "text",
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [progressState, setProgressState] = useState<ProgressState>({
    step: "",
    progress: 0,
    isActive: false,
  });

  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Connect to backend on component mount
  useEffect(() => {
    const connectToBackend = async () => {
      try {
        await skillAPI.connect();
        setIsConnected(true);

        // Add connection success message
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            content:
              "🔗 Connected to skill learning backend! Ready to process movement commands.",
            sender: "bot",
            timestamp: new Date(),
            type: "text",
          },
        ]);
      } catch (error) {
        console.error("Failed to connect to backend:", error);
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            content:
              "❌ Failed to connect to backend. Please make sure the server is running on port 5555.",
            sender: "bot",
            timestamp: new Date(),
            type: "error",
          },
        ]);
      }
    };

    connectToBackend();

    // Cleanup on unmount
    return () => {
      skillAPI.disconnect();
    };
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages, progressState]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || !isConnected) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      sender: "user",
      timestamp: new Date(),
      type: "text",
    };

    setMessages((prev) => [...prev, userMessage]);
    const query = inputValue;
    setInputValue("");
    setIsLoading(true);
    setProgressState({ step: "", progress: 0, isActive: true });

    try {
      // Add processing start message
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          content: `🚀 Processing "${query}"... I'll analyze this movement and create a learning guide for the robot.`,
          sender: "bot",
          timestamp: new Date(),
          type: "text",
        },
      ]);

      await skillAPI.processSkill(query, (update: SkillProcessingUpdate) => {
        setProgressState({
          step: update.step,
          progress: update.progress,
          isActive: update.progress < 100 && update.progress >= 0,
          data: update.data,
        });

        // Add intermediate progress messages for key milestones
        if (update.data && update.progress === 30) {
          setMessages((prev) => [
            ...prev,
            {
              id: `progress_${Date.now()}`,
              content: `📚 Found ${update.data?.source_count} sources for learning this movement.`,
              sender: "bot",
              timestamp: new Date(),
              type: "text",
            },
          ]);
        }

        if (update.data && update.progress === 70) {
          setMessages((prev) => [
            ...prev,
            {
              id: `progress_${Date.now()}`,
              content: `📋 Generated "${update.data?.title}" with ${update.data?.step_count} learning steps (Difficulty: ${update.data?.difficulty}/5).`,
              sender: "bot",
              timestamp: new Date(),
              type: "text",
            },
          ]);
        }

        if (update.progress === 100 && update.data?.bundle) {
          setMessages((prev) => [
            ...prev,
            {
              id: `result_${Date.now()}`,
              content: "Processing complete! Here's your skill learning guide:",
              sender: "bot",
              timestamp: new Date(),
              type: "result",
              data: update.data?.bundle,
            },
          ]);
        }

        if (update.progress === -1) {
          setMessages((prev) => [
            ...prev,
            {
              id: `error_${Date.now()}`,
              content: `❌ Error: ${update.data?.error || "Processing failed"}`,
              sender: "bot",
              timestamp: new Date(),
              type: "error",
            },
          ]);
        }
      });
    } catch (error) {
      console.error("Error processing skill:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: `error_${Date.now()}`,
          content: `❌ Error processing request: ${error instanceof Error ? error.message : "Unknown error"}`,
          sender: "bot",
          timestamp: new Date(),
          type: "error",
        },
      ]);
    } finally {
      setIsLoading(false);
      setProgressState({ step: "", progress: 0, isActive: false });
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const renderMessage = (message: Message) => {
    if (message.type === "result" && message.data) {
      const bundle = message.data as SkillBundle;
      return (
        <div className="space-y-4">
          <p className="text-sm">{message.content}</p>

          {/* Skill Overview */}
          <div className="bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-lg p-4">
            <h3 className="text-lg font-semibold text-neon mb-2">
              {bundle.guide.title}
            </h3>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-muted-foreground">Domain:</span>
                <span className="ml-2 text-foreground">
                  {bundle.guide.domain}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Difficulty:</span>
                <span className="ml-2 text-foreground">
                  {bundle.guide.difficulty_rating}/5
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Duration:</span>
                <span className="ml-2 text-foreground">
                  {bundle.plan.total_duration_ms}ms
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Steps:</span>
                <span className="ml-2 text-foreground">
                  {bundle.guide.steps.length}
                </span>
              </div>
            </div>
          </div>

          {/* Learning Steps */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-neon">Learning Steps:</h4>
            {bundle.guide.steps.slice(0, 3).map((step, index) => (
              <div key={index} className="bg-muted/20 rounded-lg p-3">
                <div className="text-xs font-medium text-foreground">
                  {index + 1}. {step.name}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {step.how}
                </div>
              </div>
            ))}
            {bundle.guide.steps.length > 3 && (
              <div className="text-xs text-muted-foreground">
                +{bundle.guide.steps.length - 3} more steps...
              </div>
            )}
          </div>

          {/* Safety Guidelines */}
          {bundle.guide.safety.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-neon-secondary">
                ⚠️ Safety:
              </h4>
              <div className="text-xs text-muted-foreground space-y-1">
                {bundle.guide.safety.slice(0, 2).map((safety, index) => (
                  <div key={index}>• {safety}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }

    return <p className="text-sm">{message.content}</p>;
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="bg-gradient-glass backdrop-blur-glass border-b border-glass-border p-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/20 rounded-lg">
            <Bot className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              Robot Control AI
            </h2>
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${isConnected ? "bg-neon animate-pulse" : "bg-destructive"}`}
              />
              <p className="text-sm text-muted-foreground">
                {isConnected ? "Connected to backend" : "Disconnected"}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4 overflow-y-auto" ref={scrollAreaRef}>
        <div className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 ${message.sender === "user" ? "justify-end" : "justify-start"}`}
            >
              {message.sender === "bot" && (
                <div className="p-2 bg-primary/20 rounded-lg h-fit">
                  {message.type === "error" ? (
                    <AlertCircle className="w-4 h-4 text-destructive" />
                  ) : message.type === "result" ? (
                    <CheckCircle className="w-4 h-4 text-neon" />
                  ) : (
                    <Bot className="w-4 h-4 text-primary" />
                  )}
                </div>
              )}

              <div
                className={`max-w-[80%] rounded-lg p-3 ${
                  message.sender === "user"
                    ? "bg-primary text-primary-foreground ml-auto"
                    : message.type === "error"
                      ? "bg-destructive/20 border border-destructive/30"
                      : "bg-gradient-glass backdrop-blur-glass border border-glass-border"
                }`}
              >
                {renderMessage(message)}
                <p
                  className={`text-xs mt-2 ${
                    message.sender === "user" ? "" : ""
                  }`}
                >
                  {message.timestamp.toLocaleTimeString()}
                </p>
              </div>

              {message.sender === "user" && (
                <div className="p-2 bg-secondary/20 rounded-lg h-fit">
                  <User className="w-4 h-4 text-secondary" />
                </div>
              )}
            </div>
          ))}

          {/* Progress Indicator */}
          {progressState.isActive && (
            <div className="flex gap-3">
              <div className="p-2 bg-primary/20 rounded-lg h-fit">
                <Loader2 className="w-4 h-4 text-primary animate-spin" />
              </div>
              <div className="bg-gradient-glass backdrop-blur-glass border border-glass-border rounded-lg p-3 flex-1">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">
                    {progressState.step}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {progressState.progress}%
                  </span>
                </div>
                <div className="w-full bg-muted/30 rounded-full h-2">
                  <div
                    className="bg-gradient-primary h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progressState.progress}%` }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="bg-gradient-glass backdrop-blur-glass border-t border-glass-border p-4">
        <div className="flex gap-2">
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              isConnected
                ? "Describe a movement for the robot..."
                : "Connecting to backend..."
            }
            className="flex-1 bg-muted/50 border-glass-border"
            disabled={!isConnected || isLoading}
          />
          <Button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading || !isConnected}
            variant="default"
            size="icon"
            className="bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow-glow transition-all duration-300"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
