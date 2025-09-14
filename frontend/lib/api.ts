import { io, Socket } from "socket.io-client";

export interface SkillProcessingUpdate {
  step: string;
  progress: number;
  timestamp: number;
  data?: {
    source_count?: number;
    sources?: Array<{ title: string; url: string; quality: number }>;
    attempted_urls?: string[];
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
  sources: Array<{
    url: string;
    title: string;
    snippet: string;
    weight: number;
    confidence: number;
    source_type: string;
    domain_relevance: number;
  }>;
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

export interface FinalMovementsCommand {
  id: string;
  deg: number;
}

export interface FinalMovementsStep {
  commands: FinalMovementsCommand[];
}

export interface FinalMovementsPayload {
  sequence: FinalMovementsStep[];
}

class SkillLearningAPI {
  private socket: Socket | null = null;
  private baseUrl = "http://localhost:5555";
  private finalMovementsListeners: Array<
    (payload: FinalMovementsPayload) => void
  > = [];

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.socket = io(this.baseUrl, {
        // Prefer long-polling first for compatibility with Flask dev server, then upgrade
        transports: ["polling", "websocket"],
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

      // Forward final_movements events to subscribers
      this.socket.on("final_movements", (payload: FinalMovementsPayload) => {
        console.log("🦾 final_movements received:", payload);
        this.finalMovementsListeners.forEach((cb) => {
          try {
            cb(payload);
          } catch (e) {
            console.error("final_movements listener error", e);
          }
        });
      });
    });
  }

  async calibrateRobot(): Promise<{ ok: boolean; message: string }> {
    const url = `${this.baseUrl}/calibrate`;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `HTTP ${response.status}`);
      }
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const data = (await response.json()) as { message?: string };
        return { ok: true, message: data?.message || "Calibration triggered" };
      }
      const text = await response.text().catch(() => "");
      return { ok: true, message: text || "Calibration triggered" };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      throw new Error(`Calibrate request failed: ${msg}`);
    }
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
      // do not off("final_movements") here to preserve subscribers

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

  onFinalMovements(
    callback: (payload: FinalMovementsPayload) => void
  ): () => void {
    this.finalMovementsListeners.push(callback);
    return () => {
      this.finalMovementsListeners = this.finalMovementsListeners.filter(
        (cb) => cb !== callback
      );
    };
  }
}

export const skillAPI = new SkillLearningAPI();
