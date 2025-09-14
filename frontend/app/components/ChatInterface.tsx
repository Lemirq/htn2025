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
import Image from "next/image";

// Define specific types for message data
interface ProgressData {
  source_count?: number;
  title?: string;
  step_count?: number;
  difficulty?: number;
  bundle?: SkillBundle;
  error?: string;
  attempted_urls?: string[];
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

  // Keep a running list of scraped sources from progress updates
  const [scrapedSources, setScrapedSources] = useState<
    Array<{ title: string; url: string; quality: number }>
  >([]);
  const [attemptedUrls, setAttemptedUrls] = useState<string[]>([]);

  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Timer state
  const [elapsedMs, setElapsedMs] = useState(0);
  const timerStartRef = useRef<number | null>(null);
  const timerIntervalRef = useRef<number | null>(null);

  const startTimer = () => {
    // Stop any existing timer first
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    timerStartRef.current = Date.now();
    setElapsedMs(0);
    timerIntervalRef.current = window.setInterval(() => {
      if (timerStartRef.current !== null) {
        setElapsedMs(Date.now() - timerStartRef.current);
      }
    }, 100);
  };

  const stopTimer = (): number => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    const total = timerStartRef.current
      ? Date.now() - timerStartRef.current
      : elapsedMs;
    timerStartRef.current = null;
    return total;
  };

  const formatDuration = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    const seconds = ms / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const tenths = Math.floor((seconds - Math.floor(seconds)) * 10);
    return `${m}:${s.toString().padStart(2, "0")}${tenths ? "." + tenths : ""}`;
  };

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
              "🔗 Connected to skill learning backend. Ready to process movement commands.",
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
      // Ensure any running timer is cleared on unmount
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
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
    startTimer();

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
        console.log("📈 Progress update received:", update);
        setProgressState({
          step: update.step,
          progress: update.progress,
          isActive: update.progress < 100 && update.progress >= 0,
          data: update.data,
        });

        // Collect sources as they arrive (step ~30%)
        if (update?.data?.sources && update.data.sources.length > 0) {
          setScrapedSources((prev) => {
            const byUrl = new Map(prev.map((s) => [s.url, s]));
            for (const s of update.data!.sources!) {
              if (!byUrl.has(s.url)) byUrl.set(s.url, s);
            }
            return Array.from(byUrl.values());
          });
        }

        // Collect attempted URLs for transparency even if none pass filters
        if (
          update?.data?.attempted_urls &&
          update.data.attempted_urls.length > 0
        ) {
          setAttemptedUrls((prev) => {
            const set = new Set(prev);
            update.data!.attempted_urls!.forEach((u: string) => set.add(u));
            return Array.from(set);
          });
        }

        // Add intermediate progress messages for key milestones
        // if (update.data && update.progress === 30) {
        //   setMessages((prev) => [
        //     ...prev,
        //     {
        //       id: `progress_${Date.now()}`,
        //       content: `📚 Found ${update.data?.source_count} sources for learning this movement.`,
        //       sender: "bot",
        //       timestamp: new Date(),
        //       type: "text",
        //     },
        //   ]);
        // }

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
          const totalMs = stopTimer();
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
            {
              id: `timer_${Date.now()}`,
              content: `⏱ Completed in ${formatDuration(totalMs)}`,
              sender: "bot",
              timestamp: new Date(),
              type: "text",
            },
          ]);
          // Reset progress sources after completion
          setScrapedSources([]);
          setAttemptedUrls([]);
        }

        if (update.progress === -1) {
          const totalMs = stopTimer();
          setMessages((prev) => [
            ...prev,
            {
              id: `error_${Date.now()}`,
              content: `❌ Error: ${update.data?.error || "Processing failed"}`,
              sender: "bot",
              timestamp: new Date(),
              type: "error",
            },
            {
              id: `timer_${Date.now()}`,
              content: `⏱ Ended after ${formatDuration(totalMs)}`,
              sender: "bot",
              timestamp: new Date(),
              type: "text",
            },
          ]);
        }
      });
    } catch (error) {
      console.error("Error processing skill:", error);
      const totalMs = stopTimer();
      setMessages((prev) => [
        ...prev,
        {
          id: `error_${Date.now()}`,
          content: `❌ Error processing request: ${error instanceof Error ? error.message : "Unknown error"}`,
          sender: "bot",
          timestamp: new Date(),
          type: "error",
        },
        {
          id: `timer_${Date.now()}`,
          content: `⏱ Ended after ${formatDuration(totalMs)}`,
          sender: "bot",
          timestamp: new Date(),
          type: "text",
        },
      ]);
    } finally {
      setIsLoading(false);
      setProgressState({ step: "", progress: 0, isActive: false });
      // Safety: ensure timer is stopped
      stopTimer();
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
        <div className="space-y-4 w-full">
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

          {/* Sources */}
          {bundle.sources && bundle.sources.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-neon-secondary">
                📚 Sources ({bundle.sources.length}):
              </h4>
              <div className="space-y-2">
                {bundle.sources.slice(0, 5).map((source, index) => (
                  <div key={index} className="bg-muted/20 rounded-lg p-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs font-medium text-neon hover:underline"
                        >
                          {source.title || new URL(source.url).hostname}
                        </a>
                        <div className="text-xs text-muted-foreground mt-1">
                          {source.snippet?.substring(0, 120)}...
                        </div>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground ml-2">
                        <span
                          className={`px-1.5 py-0.5 rounded text-xs ${
                            source.source_type === "academic"
                              ? "bg-blue-500/20 text-blue-300"
                              : source.source_type === "video"
                                ? "bg-red-500/20 text-red-300"
                                : "bg-gray-500/20 text-gray-300"
                          }`}
                        >
                          {source.source_type}
                        </span>
                        <span>⭐{(source.weight * 5).toFixed(1)}</span>
                      </div>
                    </div>
                  </div>
                ))}
                {bundle.sources.length > 5 && (
                  <div className="text-xs text-muted-foreground">
                    +{bundle.sources.length - 5} more sources...
                  </div>
                )}
              </div>
            </div>
          )}

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
            {/* <Bot className="w-6 h-6 text-primary" /> */}
            <Image src="/monkey.png" alt="Monkey" width={40} height={40} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">
              Monkey See Monkey Do
            </h2>
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500 animate-pulse" : "bg-destructive"}`}
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
              className={`flex gap-3 w-full ${message.sender === "user" ? "justify-end" : "justify-start"}`}
            >
              {message.sender === "bot" && (
                <div className="p-2 bg-primary/0 rounded-lg h-fit">
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
            <div className="flex gap-3 w-full">
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

                {/* Show scraped websites if available */}
                {scrapedSources.length > 0 && (
                  <div className="mt-3">
                    <div className="text-xs font-medium text-neon-secondary mb-1">
                      Websites scraped ({scrapedSources.length}):
                    </div>
                    <ul className="space-y-1">
                      {scrapedSources.slice(0, 6).map((s) => (
                        <li
                          key={s.url}
                          className="text-xs text-muted-foreground truncate"
                        >
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline"
                            title={s.title || s.url}
                          >
                            {s.title || s.url}
                          </a>
                        </li>
                      ))}
                      {scrapedSources.length > 6 && (
                        <li className="text-xs text-muted-foreground">
                          +{scrapedSources.length - 6} more…
                        </li>
                      )}
                    </ul>
                  </div>
                )}

                {/* Fallback: attempted URLs if no accepted sources */}
                {scrapedSources.length === 0 && attemptedUrls.length > 0 && (
                  <div className="mt-3">
                    <div className="text-xs font-medium text-neon-secondary mb-1">
                      Websites scraped ({attemptedUrls.length}):
                    </div>
                    <ul className="space-y-1">
                      {attemptedUrls.slice(0, 6).map((u) => (
                        <li
                          key={u}
                          className="text-xs text-muted-foreground truncate"
                        >
                          <a
                            href={u}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline"
                          >
                            {u.split("/")}
                          </a>
                        </li>
                      ))}
                      {attemptedUrls.length > 6 && (
                        <li className="text-xs text-muted-foreground">
                          +{attemptedUrls.length - 6} more…
                        </li>
                      )}
                    </ul>
                  </div>
                )}
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
