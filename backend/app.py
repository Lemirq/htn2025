"""Flask API server for the skill learning system with streaming capabilities."""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import orjson
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
import threading
import time

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.config import SystemConfig
from src.core.exceptions import SkillLearningError
from src.pipeline.skill_pipeline import SkillLearningPipeline
from src.core.models import SkillBundle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'skill-learning-secret-key'
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"])

# Global pipeline instance
pipeline = None
active_sessions = {}

def initialize_pipeline():
    """Initialize the skill learning pipeline."""
    global pipeline
    try:
        config = SystemConfig.from_env()
        pipeline = SkillLearningPipeline(config)
        logger.info("Skill learning pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        raise

class StreamingProcessor:
    """Handles streaming updates during skill processing."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.progress = 0
        self.current_step = ""
        self.results = {}
    
    def emit_progress(self, step: str, progress: int, data: Optional[Dict] = None):
        """Emit progress update to the client."""
        self.current_step = step
        self.progress = progress
        
        update = {
            'step': step,
            'progress': progress,
            'timestamp': time.time()
        }
        
        if data:
            update['data'] = data
            
        socketio.emit('progress_update', update, room=self.session_id)
        logger.info(f"Session {self.session_id}: {step} - {progress}%")

async def process_skill_with_streaming(query: str, session_id: str, max_sources: Optional[int] = None):
    """Process skill query with streaming updates."""
    processor = StreamingProcessor(session_id)
    active_sessions[session_id] = processor
    
    try:
        processor.emit_progress("Initializing", 0)
        
        # Step 1: Scraping
        processor.emit_progress("Scraping sources", 10)
        sources = await pipeline.scraper.scrape_query(query, max_sources or 5)
        processor.emit_progress("Sources found", 30, {
            'source_count': len(sources),
            'sources': [{'title': s.title, 'url': s.url, 'quality': s.quality_score} for s in sources[:3]]
        })
        
        # Step 2: Guide generation
        processor.emit_progress("Generating skill guide", 40)
        guide = await pipeline.llm_agent.create_skill_guide(query, sources)
        processor.emit_progress("Guide generated", 70, {
            'title': guide.title,
            'step_count': len(guide.steps),
            'difficulty': guide.difficulty_rating,
            'domain': guide.domain.value
        })
        
        # Step 3: Compilation
        processor.emit_progress("Compiling execution plan", 80)
        plan = pipeline.compiler.compile_skill_guide(guide)
        warnings = pipeline.compiler.validate_execution_plan(plan)
        
        processor.emit_progress("Finalizing", 90)
        
        # Create bundle
        bundle = SkillBundle(
            query=query,
            sources=sources,
            guide=guide,
            plan=plan,
            metadata={
                "pipeline_version": "2.0",
                "processing_warnings": warnings,
                "source_count": len(sources),
                "step_count": len(guide.steps),
                "phase_count": len(plan.phases)
            }
        )
        
        # Save results
        saved_files = pipeline.save_bundle(bundle)
        
        processor.emit_progress("Complete", 100, {
            'bundle': bundle.to_dict(),
            'files': saved_files
        })
        
        return bundle
        
    except Exception as e:
        logger.error(f"Error processing skill: {e}")
        processor.emit_progress("Error", -1, {'error': str(e)})
        raise
    finally:
        # Clean up session
        if session_id in active_sessions:
            del active_sessions[session_id]

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'pipeline_initialized': pipeline is not None,
        'active_sessions': len(active_sessions)
    })

@app.route('/api/skill/process', methods=['POST'])
def process_skill():
    """Process a skill learning query."""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': 'Query is required'}), 400
        
        query = data['query']
        max_sources = data.get('max_sources', 5)
        session_id = data.get('session_id', f"session_{int(time.time())}")
        
        # Start async processing in background
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                bundle = loop.run_until_complete(
                    process_skill_with_streaming(query, session_id, max_sources)
                )
                return bundle
            finally:
                loop.close()
        
        # Run in thread to avoid blocking
        thread = threading.Thread(target=run_async)
        thread.start()
        
        return jsonify({
            'message': 'Processing started',
            'session_id': session_id,
            'query': query
        })
        
    except Exception as e:
        logger.error(f"Error in process_skill: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/skill/results/<session_id>', methods=['GET'])
def get_results(session_id: str):
    """Get results for a specific session."""
    try:
        # Try to load from saved files
        output_dir = Path(pipeline.config.output_dir)
        bundle_file = output_dir / "complete_bundle.json"
        
        if bundle_file.exists():
            with open(bundle_file, 'rb') as f:
                data = orjson.loads(f.read())
            return jsonify(data)
        else:
            return jsonify({'error': 'Results not found'}), 404
            
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/skill/stream/<query>', methods=['GET'])
def stream_skill_processing(query: str):
    """Stream skill processing with Server-Sent Events."""
    def generate():
        session_id = f"stream_{int(time.time())}"
        
        def event_stream():
            try:
                # This is a simplified streaming approach
                yield f"data: {orjson.dumps({'step': 'Starting', 'progress': 0}).decode()}\n\n"
                
                # Run the async processing
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    bundle = loop.run_until_complete(
                        pipeline.process_query(query, 5)
                    )
                    
                    # Stream the final result
                    yield f"data: {orjson.dumps({'step': 'Complete', 'progress': 100, 'data': bundle.to_dict()}).decode()}\n\n"
                    
                finally:
                    loop.close()
                    
            except Exception as e:
                yield f"data: {orjson.dumps({'step': 'Error', 'progress': -1, 'error': str(e)}).decode()}\n\n"
        
        return event_stream()
    
    return Response(generate(), mimetype='text/plain')

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to skill learning server'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {request.sid}")
    # Clean up any active sessions for this client
    sessions_to_remove = [sid for sid, processor in active_sessions.items() 
                         if hasattr(processor, 'client_id') and processor.client_id == request.sid]
    for sid in sessions_to_remove:
        del active_sessions[sid]

@socketio.on('start_processing')
def handle_start_processing(data):
    """Handle skill processing request via WebSocket."""
    try:
        query = data.get('query')
        max_sources = data.get('max_sources', 5)
        session_id = data.get('session_id', f"ws_{request.sid}_{int(time.time())}")
        
        if not query:
            emit('error', {'message': 'Query is required'})
            return
        
        # Ensure the requesting client joins the session room so it receives updates
        try:
            join_room(session_id)
        except Exception as e:
            logger.error(f"Failed to join room {session_id}: {e}")
        
        # Start processing in background thread
        def process_in_background():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    process_skill_with_streaming(query, session_id, max_sources)
                )
            except Exception as e:
                logger.error(f"Background processing error: {e}")
            finally:
                loop.close()
        
        thread = threading.Thread(target=process_in_background)
        thread.start()
        
        emit('processing_started', {
            'session_id': session_id,
            'query': query
        })
        
    except Exception as e:
        logger.error(f"Error in start_processing: {e}")
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    try:
        initialize_pipeline()
        logger.info("Starting Flask server with SocketIO...")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
