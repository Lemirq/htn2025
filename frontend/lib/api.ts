import { io, Socket } from "socket.io-client";

export interface SkillProcessingUpdate {
  step: string;
  progress: number;
  timestamp: number;
  data?: {
    source_count?: number;
    sources?: Array<{ title: string; url: string; quality: number }>;
    title?: string;
    step_count?: number;
    difficulty?: number;
    domain?: string;
    bundle?: SkillBundle;
    files?: Record<string, string>;
    error?: string;
  };
}

export interface SkillBundle {
  query: string;
  guide: {
    title: string;
    domain: string;
    difficulty_rating: number;
    estimated_learning_time: string;
    prerequisites: string[];
    safety: string[];
    equipment: string[];
    core_principles: string[];
    steps: Array<{
      name: string;
      how: string;
      why: string;
      difficulty_level: number;
      citations: number[];
    }>;
    evaluation: string[];
  };
  plan: {
    skill: string;
    phases: Array<{
      name: string;
      duration_ms: number;
      cue: string;
      pose_hints: string;
      rationale: string;
      velocity_profile: string;
      force_profile: string;
    }>;
    total_duration_ms: number;
    complexity_score: number;
  };
  metadata: {
    pipeline_version: string;
    source_count: number;
    step_count: number;
    phase_count: number;
  };
}

class SkillLearningAPI {
  private socket: Socket | null = null;
  private baseUrl = "http://localhost:5555";

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.socket = io(this.baseUrl, {
        transports: ["websocket"],
        timeout: 10000,
      });

      this.socket.on("connect", () => {
        console.log("Connected to skill learning server");
        resolve();
      });

      this.socket.on("connect_error", (error) => {
        console.error("Connection error:", error);
        reject(error);
      });

      this.socket.on("disconnect", () => {
        console.log("Disconnected from server");
      });
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  async processSkill(
    query: string,
    onProgress: (update: SkillProcessingUpdate) => void,
    maxSources: number = 5
  ): Promise<void> {
    if (!this.socket) {
      throw new Error("Not connected to server. Call connect() first.");
    }

    return new Promise((resolve, reject) => {
      const sessionId = `session_${Date.now()}`;
      console.log("🚀 Starting skill processing:", {
        query,
        sessionId,
        maxSources,
      });

      // Avoid duplicate listeners from previous runs
      this.socket!.off("progress_update");
      this.socket!.off("processing_started");
      this.socket!.off("error");

      // Listen for progress updates
      this.socket!.on("progress_update", (update: SkillProcessingUpdate) => {
        console.log("📈 Progress update received:", update);
        onProgress(update);

        // Resolve when complete
        if (update.progress === 100) {
          console.log("✅ Processing completed successfully");
          resolve();
        }

        // Reject on error
        if (update.progress === -1) {
          console.error("❌ Processing failed:", update.data?.error);
          reject(new Error(update.data?.error || "Processing failed"));
        }
      });

      // Listen for processing started confirmation
      this.socket!.on("processing_started", (data) => {
        console.log("🎬 Processing started confirmation:", data);
      });

      // Listen for errors
      this.socket!.on("error", (error) => {
        console.error("🚨 Socket error:", error);
        reject(new Error(error.message || "Unknown error"));
      });

      // Start processing
      console.log("📤 Emitting start_processing event");
      this.socket!.emit("start_processing", {
        query,
        max_sources: maxSources,
        session_id: sessionId,
      });
    });
  }

  async healthCheck(): Promise<{
    status: string;
    pipeline_initialized: boolean;
  }> {
    const response = await fetch(`${this.baseUrl}/health`);
    if (!response.ok) {
      throw new Error("Health check failed");
    }
    return response.json();
  }

  async getResults(sessionId: string): Promise<SkillBundle> {
    const response = await fetch(
      `${this.baseUrl}/api/skill/results/${sessionId}`
    );
    if (!response.ok) {
      throw new Error("Failed to get results");
    }
    return response.json();
  }
}

export const skillAPI = new SkillLearningAPI();
