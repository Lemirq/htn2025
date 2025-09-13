#!/usr/bin/env python3
"""Startup script for the Skill Learning API server."""
import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import flask
        import flask_cors
        import flask_socketio
        import orjson
        print("✅ All Flask dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def setup_environment():
    """Setup environment variables if not already set."""
    env_vars = {
        'FLASK_APP': 'app.py',
        'FLASK_ENV': 'development',
        'PYTHONPATH': str(Path(__file__).parent / 'src')
    }
    
    for key, value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = value
            print(f"Set {key}={value}")

def main():
    """Main startup function."""
    print("🚀 Starting Skill Learning API Server...")
    print(f"📁 Working directory: {Path.cwd()}")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Setup environment
    setup_environment()
    
    # Start the server
    try:
        from app import app, socketio, initialize_pipeline
        
        # Initialize pipeline
        print("🔧 Initializing skill learning pipeline...")
        initialize_pipeline()
        
        print("🌐 Starting server on http://localhost:5555")
        print("📡 WebSocket streaming enabled")
        print("🔗 CORS enabled for frontend at http://localhost:3000")
        print("\nAvailable endpoints:")
        print("  GET  /health                    - Health check")
        print("  POST /api/skill/process         - Process skill query")
        print("  GET  /api/skill/results/<id>    - Get results")
        print("  GET  /api/skill/stream/<query>  - Stream processing (SSE)")
        print("  WS   /socket.io/                - WebSocket streaming")
        print("\nPress Ctrl+C to stop the server")
        
        socketio.run(app, host='0.0.0.0', port=5555, debug=True)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
