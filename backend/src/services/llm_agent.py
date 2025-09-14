"""Enhanced LLM agent service with better error handling and structured processing."""
from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional
import re
from dataclasses import asdict
import asyncio

from ..core.models import SourceDoc, SkillGuide, SkillStep, SkillDomain
from ..core.models import ExecutionPhase, PhysicalConstraints
from ..core.config import LLMConfig
from ..core.exceptions import LLMError, ValidationError

logger = logging.getLogger(__name__)

try:
    import cohere
except ImportError:
    cohere = None
    logger.warning("Cohere package not available, using fallback mode")


def _strip_code_fences(text: str) -> str:
    """Remove common code fences around JSON blocks."""
    t = text.strip()
    if t.startswith("```json"):
        t = t[7:]
    if t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def _replace_smart_quotes(text: str) -> str:
    """Normalize smart quotes to standard quotes."""
    return (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def _remove_json_comments(text: str) -> str:
    """Remove // and /* */ comments from text."""
    # Remove // comments
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    # Remove /* */ comments
    text = re.sub(r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/", "", text, flags=re.DOTALL)
    return text


def _extract_first_braced_block(text: str) -> Optional[str]:
    """Extract the first top-level {...} block using brace balance."""
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_lenient_json(text: str) -> Dict[str, Any]:
    """Attempt to parse potentially messy LLM JSON outputs robustly.

    Steps:
    - Strip code fences
    - Extract first {...} block
    - Remove comments and smart quotes
    - Try strict JSON
    - Then remove trailing commas
    - Then convert single-quoted keys/values to double quotes
    """
    raw = _strip_code_fences(text)
    candidate = _extract_first_braced_block(raw) or raw
    candidate = _remove_json_comments(candidate)
    candidate = _replace_smart_quotes(candidate)

    # First attempt
    try:
        return json.loads(candidate)
    except Exception:
        pass

    # Remove trailing commas before } or ]
    without_trailing_commas = re.sub(r",\s*([}\]])", r"\1", candidate)
    try:
        return json.loads(without_trailing_commas)
    except Exception:
        pass

    # Convert single-quoted keys and values to double-quoted
    fixed_keys = re.sub(r"([,{]\s*)'([^'\n]+)'\s*:", r'\1"\2":', without_trailing_commas)
    fixed_both = re.sub(r":\s*'([^'\\]*(?:\\.[^'\\]*)*)'", r': "\1"', fixed_keys)
    return json.loads(fixed_both)


class GuideValidator:
    """Validates and sanitizes LLM-generated guides."""
    
    REQUIRED_FIELDS = [
        "title", "prerequisites", "safety", "equipment", 
        "core_principles", "steps", "evaluation"
    ]
    
    def validate_guide_structure(self, data: Dict[str, Any]) -> None:
        """Validate that guide has required structure."""
        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in data]
        if missing_fields:
            raise ValidationError(f"Missing required fields: {missing_fields}")
        
        if not isinstance(data["steps"], list) or len(data["steps"]) == 0:
            raise ValidationError("Guide must have at least one step")
        
        for i, step in enumerate(data["steps"]):
            required_step_fields = ["name", "how", "why"]
            missing_step_fields = [field for field in required_step_fields if field not in step]
            if missing_step_fields:
                raise ValidationError(f"Step {i} missing fields: {missing_step_fields}")
    
    def sanitize_guide(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and sanitize guide data."""
        # Ensure lists are actually lists
        list_fields = ["prerequisites", "safety", "equipment", "core_principles", "evaluation"]
        for field in list_fields:
            if field in data and not isinstance(data[field], list):
                data[field] = [str(data[field])] if data[field] else []
        
        # Clean steps
        if "steps" in data:
            cleaned_steps = []
            for step in data["steps"]:
                if isinstance(step, dict) and "name" in step:
                    # Ensure citations is a list of integers
                    if "citations" in step:
                        try:
                            step["citations"] = [int(c) for c in step["citations"] if str(c).isdigit()]
                        except (ValueError, TypeError):
                            step["citations"] = []
                    else:
                        step["citations"] = []
                    
                    # Set default difficulty level
                    if "difficulty_level" not in step:
                        step["difficulty_level"] = 1
                    
                    cleaned_steps.append(step)
            data["steps"] = cleaned_steps
        
        return data

    


class FallbackGuideGenerator:
    """Generates deterministic fallback guides when LLM is unavailable."""
    
    def __init__(self):
        self.domain_templates = {
            SkillDomain.MARTIAL_ARTS: {
                "prerequisites": ["Clear practice area", "Proper stance", "Basic warm-up"],
                "safety": ["Start slowly", "Respect joint limits", "Use protective gear", "Practice with supervision"],
                "equipment": ["Training mat", "Protective gear (optional)"],
                "core_principles": ["Whole-body coordination", "Proper form over speed", "Progressive training"],
                "evaluation": ["Maintain balance", "Execute with control", "Demonstrate understanding"]
            },
            SkillDomain.SPORTS: {
                "prerequisites": ["Physical fitness check", "Proper equipment", "Understanding of rules"],
                "safety": ["Proper warm-up", "Use safety equipment", "Know your limits"],
                "equipment": ["Sport-specific gear", "Protective equipment"],
                "core_principles": ["Technique first", "Consistent practice", "Mental focus"],
                "evaluation": ["Technical proficiency", "Safety awareness", "Performance consistency"]
            },
            SkillDomain.MUSIC: {
                "prerequisites": ["Instrument access", "Basic music theory", "Practice space"],
                "safety": ["Proper posture", "Regular breaks", "Hearing protection"],
                "equipment": ["Musical instrument", "Music stand", "Metronome"],
                "core_principles": ["Regular practice", "Proper technique", "Patience and persistence"],
                "evaluation": ["Rhythm accuracy", "Tone quality", "Musical expression"]
            }
        }
    
    def generate_fallback_guide(self, query: str, sources: List[Dict[str, Any]], domain: SkillDomain) -> Dict[str, Any]:
        """Generate a structured fallback guide."""
        template = self.domain_templates.get(domain, self.domain_templates[SkillDomain.MARTIAL_ARTS])
        
        # Generate basic steps based on common learning patterns
        steps = [
            {
                "name": "Preparation",
                "how": "Set up your practice area and equipment. Review safety guidelines.",
                "why": "Proper preparation ensures safe and effective practice.",
                "citations": list(range(min(2, len(sources)))),
                "difficulty_level": 1
            },
            {
                "name": "Basic Technique",
                "how": "Learn the fundamental movements slowly and with control.",
                "why": "Building proper form is essential before adding speed or power.",
                "citations": list(range(min(3, len(sources)))),
                "difficulty_level": 2
            },
            {
                "name": "Practice",
                "how": "Repeat the movements with focus on accuracy and consistency.",
                "why": "Repetition builds muscle memory and confidence.",
                "citations": list(range(min(2, len(sources)))),
                "difficulty_level": 3
            },
            {
                "name": "Application",
                "how": "Apply the skill in realistic scenarios or with variations.",
                "why": "Real-world application tests understanding and adaptability.",
                "citations": [],
                "difficulty_level": 4
            }
        ]
        
        return {
            "query": query,
            "title": f"Learning Guide: {query.title()}",
            "domain": domain.value,
            "prerequisites": template["prerequisites"],
            "safety": template["safety"],
            "equipment": template["equipment"],
            "core_principles": template["core_principles"],
            "steps": steps,
            "evaluation": template["evaluation"],
            "sources": sources,
            "estimated_learning_time": "2-4 weeks with regular practice",
            "difficulty_rating": 3
        }


class CohereAgent:
    """Enhanced Cohere LLM agent with better prompting and error handling."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.validator = GuideValidator()
        self.fallback_generator = FallbackGuideGenerator()
        
        if not (config.api_key and cohere):
            logger.warning("Cohere not available, will use fallback mode")
            self.client = None
        else:
            self.client = cohere.Client(config.api_key)
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for guide generation."""
        return """You are an expert skill learning instructor that converts research sources into structured, practical learning guides.

Your task is to analyze multiple sources and create a comprehensive, safety-focused learning guide.

CRITICAL REQUIREMENTS:
1. Output ONLY valid JSON with this exact structure:
{
  "title": "Clear, descriptive title",
  "domain": "martial_arts|sports|music|crafts|general",
  "prerequisites": ["requirement1", "requirement2"],
  "safety": ["safety rule1", "safety rule2"],
  "equipment": ["item1", "item2"],
  "core_principles": ["principle1", "principle2"],
  "steps": [
    {
      "name": "Step Name",
      "how": "Detailed instructions on how to perform this step",
      "why": "Explanation of why this step is important",
      "cues": "Optional: coaching cues or tips",
      "common_mistakes": ["mistake1", "mistake2"],
      "citations": [0, 1],
      "difficulty_level": 1-5
    }
  ],
  "evaluation": ["success criteria1", "criteria2"],
  "estimated_learning_time": "realistic timeframe",
  "difficulty_rating": 1-5
}

2. Use concrete, actionable language
3. Include safety considerations prominently
4. Reference sources using citation numbers [0, 1, 2, etc.]
5. Order steps logically from basic to advanced
6. Be specific about techniques and avoid vague descriptions"""
    
    def _build_user_prompt(self, query: str, sources: List[Dict[str, Any]]) -> str:
        """Build user prompt with source information."""
        source_text = []
        for i, source in enumerate(sources):
            source_info = f"[{i}] {source.get('title', 'Unknown')} - {source.get('url', '')}"
            snippet = source.get('snippet', '')[:800]
            source_text.append(f"{source_info}\n{snippet}")
        
        return f"""LEARNING QUERY: {query}

RESEARCH SOURCES:
{chr(10).join(source_text)}

Create a comprehensive learning guide based on these sources. Focus on practical, step-by-step instructions that a beginner could follow safely. Include specific techniques, common mistakes to avoid, and clear success criteria.

Return ONLY the JSON structure - no additional text or formatting."""
    
    async def generate_guide(self, query: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate guide with a single LLM call (no retries)."""
        if not self.client:
            logger.info("Using fallback guide generation")
            domain = SkillDomain.GENERAL  # Could be enhanced with domain detection
            return self.fallback_generator.generate_fallback_guide(query, sources, domain)

        system_prompt = self._build_system_prompt() 
        print(f"System prompt: {system_prompt}")
        user_prompt = self._build_user_prompt(query, sources)
        print(f"User prompt: {user_prompt}")
        try:
            logger.debug(
                "Guide generation request prepared: query='%s', sources=%d, model='%s', temp=%s, max_tokens=%s, system_len=%d, user_len=%d",
                query,
                len(sources),
                getattr(self.config, "model", "command-a-03-2025"),
                getattr(self.config, "temperature", 0.2),
                getattr(self.config, "max_tokens", 1200),
                len(system_prompt or ""),
                len(user_prompt or ""),
            )
        except Exception:
            pass
        try:
            logger.debug(
                "Guide generation request prepared: query='%s', sources=%d, model='%s', temp=%s, max_tokens=%s, system_len=%d, user_len=%d",
                user_prompt,
                len(sources),
                getattr(self.config, "model", "command-a-03-2025"),
                getattr(self.config, "temperature", 0.2),
                getattr(self.config, "max_tokens", 1200),
                len(system_prompt or ""),
                len(user_prompt or ""),
            )
            print("Sending guide generation request")
            response = self.client.chat(
                model=getattr(self.config, "model", "command-a-03-2025"),
                message=user_prompt,
                response_format={"type": "json_object"},
                preamble=system_prompt,
                temperature=float(getattr(self.config, "temperature", 0.2) or 0.2),
                max_tokens=int(getattr(self.config, "max_tokens", 1200) or 1200),
            )
            print(f"Guide generation response: {response}")
            text = response.text.strip()
            try:
                logger.debug(
                    "Guide generation raw response: length=%d, preview=%s",
                    len(text),
                    text[:400].replace("\n", " ") if text else "",
                )
            except Exception:
                pass
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]

            data = json.loads(text)
            # Validate and sanitize
            self.validator.validate_guide_structure(data)
            data = self.validator.sanitize_guide(data)
            try:
                logger.debug(
                    "Guide generation parsed successfully: keys=%s, step_count=%d",
                    list(data.keys()),
                    len(data.get("steps", []) or []),
                )
            except Exception:
                pass
            return data
        except Exception as e:
            try:
                preview = text[:200].replace("\n", " ") if 'text' in locals() and isinstance(text, str) else ""
                logger.error("Guide generation failed without retry: %s; response preview=%s", e, preview)
            except Exception:
                logger.error(f"Guide generation failed without retry: {e}")
            raise

    async def create_skill_guide(self, query: str, sources: List[SourceDoc]) -> SkillGuide:
        """Create a structured skill guide from sources."""
        try:
            print(f"Creating skill guide for query: {query}")
            # Convert sources to dict format for LLM processing
            source_dicts = [source.to_dict() for source in sources]
            
            # Generate guide data
            guide_data = await self.generate_guide(query, source_dicts)
            print(f"Guide data: {guide_data}")
            # Convert to structured objects
            steps = []
            for step_data in guide_data.get("steps", []):
                step = SkillStep(
                    name=step_data["name"],
                    how=step_data["how"],
                    why=step_data["why"],
                    cues=step_data.get("cues"),
                    common_mistakes=step_data.get("common_mistakes"),
                    citations=step_data.get("citations", []),
                    difficulty_level=step_data.get("difficulty_level", 1)
                )
                steps.append(step)
            print(f"Steps: {steps}")
            # Determine domain
            domain_str = guide_data.get("domain", "general")
            try:
                domain = SkillDomain(domain_str)
            except ValueError:
                domain = SkillDomain.GENERAL
            print(f"Domain: {domain}")
            # Create guide object
            guide = SkillGuide(
                query=query,
                title=guide_data["title"],
                domain=domain,
                prerequisites=guide_data.get("prerequisites", []),
                safety=guide_data.get("safety", []),
                equipment=guide_data.get("equipment", []),
                core_principles=guide_data.get("core_principles", []),
                steps=steps,
                evaluation=guide_data.get("evaluation", []),
                sources=source_dicts,
                estimated_learning_time=guide_data.get("estimated_learning_time"),
                difficulty_rating=guide_data.get("difficulty_rating", 1)
            )
            print(f"Guide: {guide}")
            return guide
            
        except Exception as e:
            print(f"Guide creation failed: {e}")
            logger.error(f"Guide creation failed: {e}")
            raise LLMError(f"Failed to create skill guide: {e}")


class CohereServoPlanner:
    """Cohere-driven servo planner that reduces movements to 3 DOF with reasoning.

    Produces explicit servo angles in [0, 180] for:
      - left_shoulder_vertical, left_shoulder_horizontal, left_elbow_vertical
      - right_shoulder_vertical, right_shoulder_horizontal, right_elbow_vertical

    Returns a JSON-like dict with angles and detailed reasoning.
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        if not (config.api_key and cohere):
            logger.warning("Cohere not available for servo planning, will use fallback")
            self.client = None
        else:
            self.client = cohere.Client(config.api_key)

    def _build_system_prompt(self) -> str:
        return (
            "You are a robotics kinematics planner for a humanoid UPPER-BODY only with 3 DOF per arm. "
            "Your job: convert each movement phase (plus optional 3D targets and constraints) into EXPLICIT servo angles suitable for direct actuator control.\n\n"
            "Hardware per arm: shoulder_vertical (up/down), shoulder_horizontal (left/right), elbow_vertical (up/down).\n"
            "Angle domain: integers in [0, 180]. Neutral posture is ~90°. Do NOT output any floats.\n"
            "Safety & constraints: obey provided joint limits, keep COM in base if requested, respect workspace hints, and prefer guard posture for the non-active arm.\n"
            "Planning rules:\n"
            "- If the phase implies a single-handed action, infer an ACTIVE ARM and keep the other arm in protective guard (shoulder_horizontal inward, shoulder_vertical moderate, elbow flexed).\n"
            "- Use 3D targets as directional hints (z -> shoulder_vertical, y -> shoulder_horizontal, x -> elbow extension).\n"
            "- Map velocity/force profiles to posture intent (explosive -> more extension on active arm; slow/controlled -> conservative angles).\n"
            "- Ensure biomechanical plausibility and keep all angles within [0,180].\n"
            "- UPPER BODY ARMS ONLY. No legs or torso outputs.\n\n"
            "Output ONLY valid JSON with this exact schema and keys (integers only):\n"
            "{\n"
            "  \"left_arm\": {\n"
            "    \"shoulder_vertical\": 0-180,\n"
            "    \"shoulder_horizontal\": 0-180,\n"
            "    \"elbow_vertical\": 0-180\n"
            "  },\n"
            "  \"right_arm\": {\n"
            "    \"shoulder_vertical\": 0-180,\n"
            "    \"shoulder_horizontal\": 0-180,\n"
            "    \"elbow_vertical\": 0-180\n"
            "  },\n"
            "  \"reasoning\": {\n"
            "    \"movement\": \"high-level explanation\",\n"
            "    \"left_shoulder_vertical\": \"why this angle\",\n"
            "    \"left_shoulder_horizontal\": \"why this angle\",\n"
            "    \"left_elbow_vertical\": \"why this angle\",\n"
            "    \"right_shoulder_vertical\": \"why this angle\",\n"
            "    \"right_shoulder_horizontal\": \"why this angle\",\n"
            "    \"right_elbow_vertical\": \"why this angle\"\n"
            "  }\n"
            "}\n\n"
            "Return only the JSON."
        )

    def _build_system_prompt_trajectory(self) -> str:
        return (
            "You are a robotics trajectory planner for a humanoid UPPER-BODY with 3 DOF per arm. "
            "Given a skill phase and constraints, generate a SHORT sequence of intermediate waypoints "
            "that smoothly moves from neutral posture (all 90°) to the target posture.\n\n"
            "Hardware per arm: shoulder_vertical (up/down), shoulder_horizontal (left/right), elbow_vertical (up/down).\n"
            "Angles: integers in [0, 180]. Neutral posture is 90°.\n"
            "Output ONLY valid JSON with this schema:\n"
            "{\n"
            "  \"waypoints\": [\n"
            "    {\n"
            "      \"left_arm\": {\"shoulder_vertical\": int, \"shoulder_horizontal\": int, \"elbow_vertical\": int},\n"
            "      \"right_arm\": {\"shoulder_vertical\": int, \"shoulder_horizontal\": int, \"elbow_vertical\": int}\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Keep 3-7 waypoints depending on duration/velocity. Ensure all values are integers within [0,180]."
        )

    def _build_user_prompt_trajectory(
        self,
        skill_name: str,
        phase: ExecutionPhase,
        constraints: PhysicalConstraints,
        left_target: dict,
        right_target: dict,
    ) -> str:
        dur = getattr(phase, "duration_ms", 500) or 500
        return (
            f"SKILL: {skill_name}\n"
            f"PHASE: {phase.name}\n"
            f"CUE: {phase.cue}\n"
            f"RATIONALE: {phase.rationale}\n"
            f"POSE_HINTS: {phase.pose_hints}\n"
            f"VELOCITY_PROFILE: {phase.velocity_profile}\n"
            f"FORCE_PROFILE: {phase.force_profile}\n"
            f"DURATION_MS: {dur}\n"
            f"CONSTRAINTS: {constraints.to_dict()}\n"
            f"LEFT_TARGET: {left_target}\n"
            f"RIGHT_TARGET: {right_target}\n"
            "Return only JSON with 'waypoints' as described in the system prompt."
        )

    def _build_user_prompt(
        self,
        skill_name: str,
        phase: ExecutionPhase,
        constraints: PhysicalConstraints,
        left_target: dict,
        right_target: dict,
    ) -> str:
        # Lightweight role inference hints from phase naming/cues
        name = (phase.name or "").lower()
        cue = (phase.cue or "").lower()
        role_hint = "unknown"
        if any(k in name or k in cue for k in ["left", "jab (left)"]):
            role_hint = "left_active"
        elif any(k in name or k in cue for k in ["right", "cross", "jab (right)"]):
            role_hint = "right_active"
        elif any(k in name or k in cue for k in ["uppercut", "hook", "punch"]):
            # default to right-dominant for generic strikes unless specified
            role_hint = "right_active"

        return (
            f"SKILL: {skill_name}\n"
            f"PHASE: {phase.name}\n"
            f"CUE: {phase.cue}\n"
            f"RATIONALE: {phase.rationale}\n"
            f"POSE_HINTS: {phase.pose_hints}\n"
            f"VELOCITY_PROFILE: {phase.velocity_profile}\n"
            f"FORCE_PROFILE: {phase.force_profile}\n"
            f"ROLE_HINT: {role_hint}  # if unknown, infer from context\n"
            f"CONSTRAINTS: {constraints.to_dict()}\n"
            f"LEFT_3D_TARGET: {left_target}\n"
            f"RIGHT_3D_TARGET: {right_target}\n"
            "Reduce to 3 DOF servo angles per arm with integer 0-180° values. Provide concise reasoning per servo and overall."
        )

    def _clamp(self, v: float) -> int:
        try:
            iv = int(round(float(v)))
        except Exception:
            iv = 90
        return max(0, min(180, iv))

    def _validate_plan(self, data: dict) -> dict:
        # Ensure structure and clamp angles
        for arm in ["left_arm", "right_arm"]:
            if arm not in data:
                data[arm] = {}
            for joint in ["shoulder_vertical", "shoulder_horizontal", "elbow_vertical"]:
                data[arm][joint] = self._clamp(data.get(arm, {}).get(joint, 90))
        if "reasoning" not in data:
            data["reasoning"] = {"movement": "Deterministic fallback reasoning."}
        # Ensure per-servo reasoning keys exist
        for key in [
            "left_shoulder_vertical", "left_shoulder_horizontal", "left_elbow_vertical",
            "right_shoulder_vertical", "right_shoulder_horizontal", "right_elbow_vertical",
        ]:
            data["reasoning"].setdefault(key, "")
        data["reasoning"].setdefault("movement", "")
        return data

    def _validate_trajectory(self, data: dict) -> list:
        """Validate and sanitize a trajectory response into a list of waypoints.

        Ensures each waypoint contains integer angles within [0,180] for
        left and right arms with keys: shoulder_vertical, shoulder_horizontal, elbow_vertical.
        """
        waypoints = data.get("waypoints")
        if not isinstance(waypoints, list) or len(waypoints) == 0:
            raise ValueError("Invalid trajectory: missing or empty 'waypoints'")

        def sanitize_arm(arm: dict) -> dict:
            return {
                "shoulder_vertical": self._clamp(arm.get("shoulder_vertical", 90)),
                "shoulder_horizontal": self._clamp(arm.get("shoulder_horizontal", 90)),
                "elbow_vertical": self._clamp(arm.get("elbow_vertical", 90)),
            }

        cleaned: list = []
        for wp in waypoints:
            if not isinstance(wp, dict):
                continue
            left = sanitize_arm(wp.get("left_arm", {}))
            right = sanitize_arm(wp.get("right_arm", {}))
            cleaned.append({"left_arm": left, "right_arm": right})

        if not cleaned:
            raise ValueError("Invalid trajectory: no valid waypoints after sanitization")

        return cleaned

    def _fallback_plan(
        self,
        phase: ExecutionPhase,
        left_target: dict,
        right_target: dict,
    ) -> dict:
        """Deterministic heuristic mapping from 3D targets to 3DOF servo angles with role and profile awareness."""
        # Infer active arm
        name = (phase.name or "").lower()
        cue = (phase.cue or "").lower()
        right_active = False
        left_active = False
        if any(k in name or k in cue for k in ["left", "jab (left)"]):
            left_active = True
        elif any(k in name or k in cue for k in ["right", "cross", "jab (right)"]):
            right_active = True
        elif any(k in name or k in cue for k in ["uppercut", "hook", "punch"]):
            right_active = True

        # Velocity/force scaling
        vel = (phase.velocity_profile or "medium").lower()
        force = (phase.force_profile or "controlled").lower()
        power_scale = 1.0
        if vel in ["explosive", "fast"] or force in ["maximum"]:
            power_scale = 1.2
        elif vel in ["slow"] and force in ["minimal"]:
            power_scale = 0.9

        def map_arm(tgt: dict, side: str, active: bool) -> dict:
            # Start neutral
            shoulder_v = 90
            shoulder_h = 90
            elbow_v = 90

            # Heuristics: z controls shoulder vertical, y controls shoulder horizontal, x controls elbow extension
            z = tgt.get("z", 1.2)
            y = tgt.get("y", 0.0)
            x = tgt.get("x", 0.3)

            # Shoulder vertical: up if higher z
            shoulder_v = self._clamp(90 + (z - 1.2) * 200 * (1.1 if active else 0.9))

            # Shoulder horizontal: inward/outward based on lateral offset (mirror right side)
            if side == "left":
                shoulder_h = self._clamp(90 - y * 300)
            else:
                shoulder_h = self._clamp(90 + (-y) * 300)

            # Elbow vertical: more forward x -> more extension (smaller angle), keep within 30-150
            elbow_v = self._clamp(120 - (x - 0.3) * 300 * (1.2 if active else 0.8))

            # Apply power scaling for active arm only
            if active:
                # Move shoulder_v slightly higher and elbow more extended for strikes
                shoulder_v = self._clamp(shoulder_v * power_scale)
                elbow_v = self._clamp(elbow_v - int(round((power_scale - 1.0) * 10)))
            else:
                # Guard posture for non-active arm
                shoulder_h = self._clamp((shoulder_h + (60 if side == "left" else 120)) // 2)
                elbow_v = self._clamp((elbow_v + 110) // 2)

            return {
                "shoulder_vertical": shoulder_v,
                "shoulder_horizontal": shoulder_h,
                "elbow_vertical": elbow_v,
            }

        left = map_arm(left_target, "left", left_active and not right_active)
        right = map_arm(right_target, "right", right_active and not left_active)

        reasoning = {
            "movement": (
                f"Mapped 3D targets to servo angles: z -> shoulder_vertical, y -> shoulder_horizontal, x -> elbow_vertical. "
                f"Phase '{phase.name}' translated to balanced, safe positions."
            ),
            "left_shoulder_vertical": f"Higher z leads to raised left shoulder ({left['shoulder_vertical']}°)",
            "left_shoulder_horizontal": f"Positive y pulls left shoulder inward ({left['shoulder_horizontal']}°)",
            "left_elbow_vertical": f"Forward x extends left elbow ({left['elbow_vertical']}°)",
            "right_shoulder_vertical": f"Higher z leads to raised right shoulder ({right['shoulder_vertical']}°)",
            "right_shoulder_horizontal": f"Negative y pulls right shoulder inward ({right['shoulder_horizontal']}°)",
            "right_elbow_vertical": f"Forward x extends right elbow ({right['elbow_vertical']}°)",
        }

        return {
            "left_arm": left,
            "right_arm": right,
            "reasoning": reasoning,
        }

    def _fallback_trajectory(
        self,
        phase: ExecutionPhase,
        left_target: dict,
        right_target: dict,
    ) -> list:
        """Heuristic multi-waypoint trajectory from neutral to phase target."""
        single = self._fallback_plan(phase, left_target, right_target)
        la_t = single["left_arm"]
        ra_t = single["right_arm"]
        # Determine number of waypoints by duration and velocity profile
        dur = getattr(phase, "duration_ms", 500) or 500
        vel = (phase.velocity_profile or "medium").lower()
        n = max(3, min(7, int(round(dur / 200))))
        if vel in ["explosive"]:
            n = max(3, min(n, 4))
        elif vel in ["slow"]:
            n = min(7, max(n, 5))
        def interp(a0: int, a1: int, t: float) -> int:
            return self._clamp(int(round(a0 + (a1 - a0) * t)))
        neutral = {"shoulder_vertical": 90, "shoulder_horizontal": 90, "elbow_vertical": 90}
        waypoints = []
        for i in range(1, n + 1):
            t = i / n
            la = {k: interp(neutral[k], la_t[k], t) for k in neutral}
            ra = {k: interp(neutral[k], ra_t[k], t) for k in neutral}
            waypoints.append({"left_arm": la, "right_arm": ra})
        return waypoints

    def plan_servo_positions(
        self,
        skill_name: str,
        phase: ExecutionPhase,
        constraints: PhysicalConstraints,
        left_target: dict,
        right_target: dict,
    ) -> dict:
        """Call Cohere to plan servo angles and reasoning. Falls back to heuristics if unavailable."""
        if not self.client:
            return self._fallback_plan(phase, left_target, right_target)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(skill_name, phase, constraints, left_target, right_target)

        try:
            # Use deterministic settings for actuator commands
            response = self.client.chat(
                model=self.config.model,
                message=user_prompt,
                preamble=system_prompt,
                response_format={"type": "json_object"},
                temperature=min(getattr(self.config, "temperature", 0.2), 0.1),
                max_tokens=min(getattr(self.config, "max_tokens", 4000), 600),
            )

            text = response.text or ""
            data = parse_lenient_json(text)
            data = self._validate_plan(data)
            return data
        except Exception as e:
            logger.warning(f"Cohere servo planning failed, using fallback: {e}")
            return self._fallback_plan(phase, left_target, right_target)

    def plan_servo_trajectory(
        self,
        skill_name: str,
        phase: ExecutionPhase,
        constraints: PhysicalConstraints,
        left_target: dict,
        right_target: dict,
    ) -> list:
        """Ask Cohere for multiple waypoints; fallback to heuristic interpolation."""
        if not self.client:
            return self._fallback_trajectory(phase, left_target, right_target)

        system_prompt = self._build_system_prompt_trajectory()
        user_prompt = self._build_user_prompt_trajectory(skill_name, phase, constraints, left_target, right_target)

        try:
            response = self.client.chat(
                model=getattr(self.config, "model", "command-a-03-2025"),
                message=user_prompt,
                preamble=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=700,
            )
            text = response.text or ""
            data = parse_lenient_json(text)
            waypoints = self._validate_trajectory(data)
            return waypoints
        except Exception as e:
            logger.warning(f"Cohere servo trajectory failed, using fallback: {e}")
            return self._fallback_trajectory(phase, left_target, right_target)
    
