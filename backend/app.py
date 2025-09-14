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
import httpx

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
# Track which sessions have already posted a sequence to the robot to prevent duplicates
posted_sequence_sessions = set()

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
        # Include attempted URLs for transparency
        attempted_urls = getattr(pipeline.scraper, 'last_search_urls', []) or []
        processor.emit_progress("Sources found", 30, {
            'source_count': len(sources),
            'sources': [{'title': s.title, 'url': s.url, 'quality': s.quality_score} for s in sources[:3]],
            'attempted_urls': attempted_urls
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
        try:
            print(f"[{session_id}] Compilation finished: phases={len(getattr(plan, 'phases', []) or [])}, warnings={len(warnings or [])}")
        except Exception:
            print(f"[{session_id}] Compilation finished (summary unavailable)")
        try:
            logger.info(
                "Execution plan compiled: phases=%d, warnings=%d",
                len(getattr(plan, 'phases', []) or []),
                len(warnings or []),
            )
            logger.debug(
                "Execution plan details: phase_names=%s, warnings=%s",
                [getattr(p, 'name', None) for p in getattr(plan, 'phases', []) or []],
                warnings,
            )
        except Exception as _log_err:
            logger.debug(f"Plan summary logging failed: {_log_err}")

        print(f"[{session_id}] Finalizing start")
        processor.emit_progress("Finalizing", 90)
        print(f"[{session_id}] Finalizing emit done")
        try:
            logger.info(
                "Finalizing bundle: sources=%d, steps=%d, phases=%d",
                len(sources or []),
                len(getattr(guide, 'steps', []) or []),
                len(getattr(plan, 'phases', []) or []),
            )
            logger.debug(
                "Bundle meta: guide_title=%s, difficulty=%s, domain=%s",
                getattr(guide, 'title', None),
                getattr(guide, 'difficulty_rating', None),
                getattr(getattr(guide, 'domain', None), 'value', None),
            )
        except Exception as _log_err:
            logger.debug(f"Finalizing summary logging failed: {_log_err}")
        
        # Create bundle
        print(f"[{session_id}] Creating bundle object")
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
        print(f"[{session_id}] Bundle object created")
        
        # Save results
        print(f"[{session_id}] Saving bundle to output directory: {pipeline.config.output_dir}")
        saved_files = pipeline.save_bundle(bundle)
        try:
            print(f"[{session_id}] Bundle saved: files_count={len(saved_files or [])}")
        except Exception:
            print(f"[{session_id}] Bundle saved (file count unavailable)")
        try:
            logger.info(
                "Bundle saved: files_count=%d",
                len(saved_files or []),
            )
            logger.debug("Saved files: %s", saved_files)
        except Exception as _log_err:
            logger.debug(f"Saved files logging failed: {_log_err}")

        # Emit final movements if available
        try:
            output_dir = Path(pipeline.config.output_dir)
            servo_file = output_dir / "servo_sequence.json"
            print(f"[{session_id}] Checking for servo sequence at {servo_file}")
            logger.debug("Checking servo sequence at %s", servo_file)
            if servo_file.exists():
                with open(servo_file, 'rb') as f:
                    servo_payload = orjson.loads(f.read())
                try:
                    seq_len = len(servo_payload.get('sequence', []) or [])
                except Exception:
                    seq_len = 0
                socketio.emit('final_movements', servo_payload, room=session_id)
                logger.info(f"Session {session_id}: Emitted final_movements event (sequence_len={seq_len})")
                print(f"[{session_id}] Emitted final_movements (sequence_len={seq_len})")

                # Optionally send servo actions to robot over HTTP one-by-one if configured
                robot_base_url = getattr(pipeline.config, 'robot_base_url', None)
                if robot_base_url:
                    if session_id in posted_sequence_sessions:
                        logger.info(f"Session {session_id}: Robot sequence already posted; skipping duplicate send")
                        print(f"[{session_id}] Robot sequence already posted; skipping duplicate send")
                    else:
                        posted_sequence_sessions.add(session_id)
                        try:
                            base = robot_base_url.rstrip('/')
                            if not (base.startswith('http://') or base.startswith('https://')):
                                base = f"http://{base}"
                            logger.info(
                                "Session %s: Posting %d steps as individual /servo commands",
                                session_id,
                                seq_len,
                            )
                            print(f"[{session_id}] Posting {seq_len} steps as individual /servo commands")

                            steps = servo_payload.get('sequence', []) or []
                            commands_sent = 0
                            errors = 0
                            with httpx.Client(timeout=2.0) as client:
                                for step_index, step in enumerate(steps):
                                    commands = (step or {}).get('commands', []) or []
                                    print(f"[{session_id}] Step {step_index+1}/{len(steps)}: sending {len(commands)} commands")
                                    for cmd in commands:
                                        try:
                                            servo_id = int(cmd.get('id'))
                                            angle = int(cmd.get('deg'))
                                        except Exception:
                                            logger.warning("Invalid command format encountered: %s", cmd)
                                            errors += 1
                                            continue

                                        if angle < 0:
                                            angle = 0
                                        if angle > 180:
                                            angle = 180

                                        url = f"{base}/servo"
                                        resp = client.post(url, json={"id": servo_id, "angle": angle})
                                        if resp.status_code >= 400:
                                            errors += 1
                                            logger.warning(
                                                "Robot /servo error %s: %s (id=%s angle=%s)",
                                                resp.status_code,
                                                resp.text,
                                                servo_id,
                                                angle,
                                            )
                                            print(f"[{session_id}] /servo -> {resp.status_code} (id={servo_id} angle={angle})")
                                        else:
                                            commands_sent += 1
                                        # Small delay to avoid flooding the microcontroller
                                        time.sleep(0.02)

                                    # Slight delay between steps for motion settling
                                    time.sleep(0.1)

                            logger.info(
                                "Session %s: Finished posting servo commands (ok=%d, errors=%d)",
                                session_id,
                                commands_sent,
                                errors,
                            )
                            print(f"[{session_id}] Finished posting servo commands (ok={commands_sent}, errors={errors})")
                        except Exception as e:
                            logger.error(f"Failed to send servo sequence to robot: {e}")
                            print(f"[{session_id}] Failed to send servo sequence: {e}")
                else:
                    logger.info("ROBOT_BASE_URL not set; skipping robot POST")
                    print(f"[{session_id}] ROBOT_BASE_URL not set; skipping robot POST")
            else:
                logger.warning(f"Session {session_id}: servo_sequence.json not found at {servo_file}")
                print(f"[{session_id}] servo_sequence.json not found at {servo_file}")
        except Exception as e:
            logger.error(f"Session {session_id}: Failed to emit final_movements: {e}")
            print(f"[{session_id}] Failed to emit final_movements: {e}")
        
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
        # Remove from posted guard set to avoid stale entries
        if session_id in posted_sequence_sessions:
            try:
                posted_sequence_sessions.remove(session_id)
            except KeyError:
                pass

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'pipeline_initialized': pipeline is not None,
        'active_sessions': len(active_sessions)
    })

@app.route('/calibrate', methods=['POST'])
def calibrate_robot():
    """Trigger robot calibration (reset) via robot controller.

    Forwards a POST to ROBOT_BASE_URL/calibrate when configured.
    If ROBOT_BASE_URL is not set, returns a simulated success response.
    """
    try:
        # Ensure pipeline/config is available
        if pipeline is None:
            initialize_pipeline()

        robot_base_url = getattr(pipeline.config, 'robot_base_url', None)
        if not robot_base_url:
            logger.info("ROBOT_BASE_URL not set; simulating calibration success")
            return jsonify({
                'ok': True,
                'message': 'Calibration simulated (ROBOT_BASE_URL not set)'
            })

        base = robot_base_url.rstrip('/')
        if not (base.startswith('http://') or base.startswith('https://')):
            base = f"http://{base}"
        url = f"{base}/calibrate"

        logger.info(f"Forwarding calibration request to robot: {url}")
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(url, json={'action': 'calibrate'})
                content_type = resp.headers.get('content-type', '')
                body: Any
                try:
                    if 'application/json' in content_type:
                        body = resp.json()
                    else:
                        body = {'message': resp.text}
                except Exception:
                    body = {'message': resp.text}

                if resp.status_code >= 400:
                    logger.warning(f"Robot calibration returned {resp.status_code}: {resp.text}")
                    raise RuntimeError(f"calibrate endpoint returned {resp.status_code}")

                return jsonify({
                    'ok': True,
                    'message': body.get('message') if isinstance(body, dict) else 'Calibration triggered',
                    'robot_response': body
                })
        except Exception as primary_err:
            # Fallback: if /calibrate not supported, send neutral angles via /servos
            try:
                base = robot_base_url.rstrip('/')
                if not (base.startswith('http://') or base.startswith('https://')):
                    base = f"http://{base}"
                servos_url = f"{base}/servos"
                neutral = {'angles': [90, 90, 90, 90, 90, 90]}
                logger.info(f"Calibration fallback: POST neutral pose to {servos_url}")
                with httpx.Client(timeout=5.0) as client:
                    resp2 = client.post(servos_url, json=neutral)
                    if resp2.status_code >= 400:
                        logger.warning(f"Calibration fallback failed {resp2.status_code}: {resp2.text}")
                        return jsonify({'ok': False, 'message': 'Calibration failed', 'status': resp2.status_code}), 502
                return jsonify({'ok': True, 'message': 'Calibration fallback applied (neutral pose sent)'})
            except Exception as fallback_err:
                logger.error(f"Calibration endpoint error: {primary_err}; fallback error: {fallback_err}")
                return jsonify({'ok': False, 'error': 'Calibration failed and fallback failed'}), 500

    except Exception as e:
        logger.error(f"Calibration endpoint error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

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
