# Skill Learning System

A comprehensive system that converts natural language queries into structured, executable learning plans with real-time streaming capabilities.

## Features

- **Natural Language Processing**: Convert queries like "learn how to do an uppercut from boxing" into structured guides
- **Web Scraping**: Automatically gather relevant sources from the web
- **LLM Integration**: Uses Cohere AI to generate comprehensive skill guides
- **Execution Planning**: Compiles guides into hardware-agnostic execution plans
- **Real-time Streaming**: Flask API with WebSocket and SSE support for live progress updates
- **Frontend Integration**: CORS-enabled API ready for React/Next.js frontends

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file:

```bash
COHERE_API_KEY=your_cohere_api_key_here
OUTPUT_DIR=outputs
LOG_LEVEL=INFO
```

### 3. Start the API Server

```bash
python start_server.py
```

The server will start on `http://localhost:5000` with streaming capabilities enabled.

## API Endpoints

### REST API

- **GET `/health`** - Health check and server status
- **POST `/api/skill/process`** - Start processing a skill query
  ```json
  {
    "query": "learn how to do an uppercut from boxing",
    "max_sources": 5,
    "session_id": "optional_session_id"
  }
  ```
- **GET `/api/skill/results/<session_id>`** - Get processing results
- **GET `/api/skill/stream/<query>`** - Server-Sent Events streaming

### WebSocket Streaming

Connect to `/socket.io/` for real-time updates:

```javascript
const socket = io("http://localhost:5000");

socket.on("connect", () => {
  console.log("Connected to skill learning server");
});

socket.on("progress_update", (data) => {
  console.log(`${data.step}: ${data.progress}%`);
  if (data.data) {
    console.log("Additional data:", data.data);
  }
});

// Start processing
socket.emit("start_processing", {
  query: "learn how to do an uppercut from boxing",
  max_sources: 5,
});
```

## CLI Usage (Original)

```bash
# Basic usage
python main.py "learn how to do an uppercut from boxing"

# With options
python main.py "tennis serve technique" --max-sources 8 --output-dir tennis_results

# Disable web scraping
python main.py "guitar chords" --no-web
```

## Output Structure

The system generates three main files:

1. **`guide.json`** - Structured learning guide with steps, safety, equipment
2. **`plan.json`** - Hardware-agnostic execution plan with phases and timing
3. **`complete_bundle.json`** - Combined output with metadata

### Example Output Structure

```json
{
  "query": "learn how to do an uppercut from boxing",
  "guide": {
    "title": "Learning Guide: Learn How To Do An Uppercut From Boxing",
    "domain": "general",
    "prerequisites": ["Clear practice area", "Proper stance"],
    "safety": ["Start slowly", "Use protective gear"],
    "steps": [
      {
        "name": "Preparation",
        "how": "Set up your practice area and equipment",
        "why": "Proper preparation ensures safe practice",
        "difficulty_level": 1
      }
    ]
  },
  "plan": {
    "phases": [
      {
        "name": "preparation",
        "duration_ms": 500,
        "cue": "relax and position",
        "velocity_profile": "slow"
      }
    ],
    "total_duration_ms": 2600
  }
}
```

## Streaming Integration

### Frontend Example (React)

```javascript
import { io } from "socket.io-client";

const SkillLearning = () => {
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [results, setResults] = useState(null);

  useEffect(() => {
    const socket = io("http://localhost:5000");

    socket.on("progress_update", (data) => {
      setProgress(data.progress);
      setCurrentStep(data.step);

      if (data.progress === 100 && data.data?.bundle) {
        setResults(data.data.bundle);
      }
    });

    return () => socket.disconnect();
  }, []);

  const startLearning = (query) => {
    socket.emit("start_processing", { query });
  };

  return (
    <div>
      <input
        type="text"
        placeholder="What do you want to learn?"
        onKeyPress={(e) => e.key === "Enter" && startLearning(e.target.value)}
      />

      {progress > 0 && (
        <div>
          <div>Step: {currentStep}</div>
          <div>Progress: {progress}%</div>
          <progress value={progress} max="100" />
        </div>
      )}

      {results && (
        <div>
          <h2>{results.guide.title}</h2>
          <p>Difficulty: {results.guide.difficulty_rating}/5</p>
          <p>Duration: {results.plan.total_duration_ms}ms</p>
        </div>
      )}
    </div>
  );
};
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Flask API      │    │   Pipeline      │
│   (React/Next)  │◄──►│   + WebSocket    │◄──►│   Processing    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                          │
                              ▼                          ▼
                       ┌──────────────┐         ┌─────────────────┐
                       │   Session    │         │   Web Scraper   │
                       │   Management │         │   LLM Agent     │
                       └──────────────┘         │   Compiler      │
                                               └─────────────────┘
```

## Development

### Project Structure

```
backend/
├── src/
│   ├── core/          # Core models and configuration
│   ├── pipeline/      # Main processing pipeline
│   └── services/      # Web scraper, LLM, compiler
├── outputs/           # Generated skill guides and plans
├── app.py            # Flask API server with streaming
├── start_server.py   # Server startup script
├── main.py           # Original CLI interface
└── requirements.txt  # Dependencies
```

### Adding New Features

1. **New Endpoints**: Add routes to `app.py`
2. **Streaming Events**: Extend `StreamingProcessor` class
3. **Pipeline Steps**: Modify `process_skill_with_streaming()`
4. **Data Models**: Update models in `src/core/models.py`

## Troubleshooting

- **Import Errors**: Ensure `PYTHONPATH` includes the `src` directory
- **API Key Issues**: Check your `.env` file has valid `COHERE_API_KEY`
- **Port Conflicts**: Change port in `start_server.py` if 5000 is occupied
- **CORS Issues**: Update allowed origins in `app.py` for your frontend URL

## License

MIT License - see LICENSE file for details.
