"""
Standalone evaluation script.

Loads evaluation data from HuggingFace (figai/GUI-Perturbed), runs model inference, and saves raw predictions.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from anthropic import Anthropic
from datasets import load_dataset
from dotenv import load_dotenv

load_dotenv()
from openai import OpenAI
from PIL import Image
from loguru import logger

# Add eval directory to path for imports
eval_dir = Path(__file__).parent
sys.path.insert(0, str(eval_dir))

from prompts import (
    build_claude_messages,
    build_gta1_messages,
    build_uitars15_messages,
    build_qwen25vl_messages,
    resize_image,
)


# ============================================================================
# Constants
# ============================================================================

EXPECTED_IMAGE_WIDTH = 1920
EXPECTED_IMAGE_HEIGHT = 1080

IMAGE_FACTOR = 28
MIN_PIXELS = 100 * 28 * 28
MAX_PIXELS = 16384 * 28 * 28
MAX_RATIO = 200

VALID_MODEL_TYPES = {"gta1", "qwen25vl", "uitars15", "claude"}

# Model-specific default max_tokens
# GTA1 only needs ~32 tokens for coordinate output (x,y), but we use 64 to be safe
DEFAULT_MAX_TOKENS = {
    ("gta1", False): 64,
    ("gta1", True): 1000,
    ("qwen25vl", False): 1000,
    ("qwen25vl", True): 1000,
    ("uitars15", False): 1000,
    ("uitars15", True): 1000,
    ("claude", False): 1024,
    ("claude", True): 4096,
}

# ============================================================================
# Coordinate Extraction and Hit Detection
# ============================================================================

def extract_coordinates(raw_prediction: str, model_type: str) -> Optional[Tuple[float, float]]:
    """Extract (x, y) coordinates from a model's raw prediction.

    Each model type has a different output format:
    - gta1: "(x,y)" or "Thought: ... Action: (x,y)" or "Thought: ... (x,y)"
    - uitars15: "Action: click(start_box='(x,y)')" or with Thought prefix
    - qwen25vl: '<tool_call>{"name":"computer_use","arguments":{"coordinate":[x,y]}}</tool_call>'
    - claude: JSON array with tool_use blocks containing {"input":{"coordinate":[x,y]}}

    Returns (x, y) in the model's native coordinate space, or None if parsing fails.
    """
    if not raw_prediction or not raw_prediction.strip():
        return None

    try:
        if model_type == "claude":
            return _extract_claude_coordinates(raw_prediction)
        elif model_type == "gta1":
            return _extract_gta1_coordinates(raw_prediction)
        elif model_type == "uitars15":
            return _extract_uitars15_coordinates(raw_prediction)
        elif model_type == "qwen25vl":
            return _extract_qwen25vl_coordinates(raw_prediction)
    except Exception:
        return None
    return None


def _extract_claude_coordinates(raw_prediction: str) -> Optional[Tuple[float, float]]:
    """Claude: JSON array of content blocks. Coordinates are already scaled to 1920x1080."""
    blocks = json.loads(raw_prediction)
    for block in blocks:
        if block.get("type") == "tool_use" and "input" in block:
            coord = block["input"].get("coordinate")
            if coord and len(coord) == 2:
                return (float(coord[0]), float(coord[1]))
    return None


def _extract_gta1_coordinates(raw_prediction: str) -> Optional[Tuple[float, float]]:
    """GTA1: '(x,y)' or 'Thought: ... Action: (x,y)' or 'Thought: ... (x,y)'."""
    # Find last (x,y) pattern — in reasoning mode the coordinate comes after the thought
    matches = re.findall(r'\((\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\)', raw_prediction)
    if matches:
        x, y = matches[-1]
        return (float(x), float(y))
    return None


def _extract_uitars15_coordinates(raw_prediction: str) -> Optional[Tuple[float, float]]:
    """UITARS: "click(start_box='(x,y)')" or similar action format."""
    # Match click(start_box='(x,y)') or similar patterns with box coordinates
    match = re.search(r"start_box='(?:<\|box_start\|>)?\((\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\)", raw_prediction)
    if match:
        return (float(match.group(1)), float(match.group(2)))
    # Fallback: any (x,y) pattern
    matches = re.findall(r'\((\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\)', raw_prediction)
    if matches:
        return (float(matches[-1][0]), float(matches[-1][1]))
    return None


def _extract_qwen25vl_coordinates(raw_prediction: str) -> Optional[Tuple[float, float]]:
    """Qwen2.5VL: '<tool_call>{"name":"computer_use","arguments":{"coordinate":[x,y]}}</tool_call>'."""
    match = re.search(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', raw_prediction, re.DOTALL)
    if match:
        tool_call = json.loads(match.group(1))
        coord = tool_call.get("arguments", {}).get("coordinate")
        if coord and len(coord) == 2:
            return (float(coord[0]), float(coord[1]))
    # Fallback: find "coordinate": [x, y] anywhere
    match = re.search(r'"coordinate"\s*:\s*\[(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\]', raw_prediction)
    if match:
        return (float(match.group(1)), float(match.group(2)))
    return None


def renormalize_to_original(
    coord: Tuple[float, float],
    model_type: str,
    original_width: int = EXPECTED_IMAGE_WIDTH,
    original_height: int = EXPECTED_IMAGE_HEIGHT,
) -> Tuple[float, float]:
    """Map predicted coordinates back to the original image dimensions.

    - gta1, uitars15, qwen25vl: coordinates are in the smart_resize'd space.
      Renormalize by multiplying by (original / resized) per axis.
    - claude: coordinates are already in 1920x1080 space (scaled back in
      _parse_claude_response), so no further transformation is needed.
    """
    if model_type == "claude":
        # Already scaled back to original dimensions during response parsing
        return coord

    # Compute the resized dimensions that the VLM models used
    resized_image = resize_image(Image.new("RGB", (original_width, original_height)))
    resized_w, resized_h = resized_image.size

    x = coord[0] * (original_width / resized_w)
    y = coord[1] * (original_height / resized_h)
    return (x, y)


def is_hit(coord: Tuple[float, float], gt_bbox) -> bool:
    """Check whether the predicted coordinate falls inside the ground truth bbox.

    gt_bbox format: [x, y, width, height] where (x, y) is the top-left corner.
    Accepts either a list of floats or a JSON string representation.
    """
    if isinstance(gt_bbox, str):
        gt_bbox = json.loads(gt_bbox)
    bx, by, bw, bh = [float(v) for v in gt_bbox]
    return bx <= coord[0] <= bx + bw and by <= coord[1] <= by + bh


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class ModelConfig:
    """Model inference configuration."""
    name: str  # Model identifier
    model_type: str  # gta1, qwen25vl, uitars15
    use_reasoning: bool  # Whether to use reasoning prompt template
    temperature: float = 0.0
    max_tokens: int = 1000
    top_p: float = 0.9
    seed: Optional[int] = None
    language: str = "English"
    image_factor: int = 28  # Image resize factor (patch_size * merge_size)
    image_min_pixels: int = MIN_PIXELS
    image_max_pixels: int = MAX_PIXELS  # Maximum image pixels

class DatasetVariantType(Enum):
    STYLE = "style"
    PRECISION = "precision"
    TEXT_ZOOM = "text_zoom"
    ORIGINAL = "original"

class InstructionType(Enum):
    DIRECT_QUERY = "direct_query"
    RELATIONAL_QUERY = "relational_query"

@dataclass
class DatasetConfig:
    """Dataset variant configuration."""
    instruction_type: InstructionType
    dataset_variant: Optional[DatasetVariantType] = None

@dataclass
class EvaluationConfig:
    """Overall evaluation configuration."""
    output_dir: Path
    model_config: ModelConfig
    dataset_config: DatasetConfig
    api_url: str
    api_key: str
    config_id: str = ""
    save_interval: int = 10  # Save predictions every N steps


# ============================================================================
# Helper Functions
# ============================================================================

def format_metadata_string(task_id: Optional[str] = None, 
                           step_index: Optional[int] = None, 
                           variant: Optional[str] = None) -> str:
    """Format metadata for logging."""
    if task_id is None and step_index is None and variant is None:
        return ""
    parts = []
    if task_id is not None:
        parts.append(f"task_id={task_id}")
    if step_index is not None:
        parts.append(f"step_index={step_index}")
    if variant is not None:
        parts.append(f"variant={variant}")
    return f" [{', '.join(parts)}]"


def setup_logging(output_dir: Path) -> Path:
    """Set up logging to both console and file. Returns log file path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"evaluation_{timestamp}.log"
    log_path = output_dir / log_filename
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Remove default handler
    logger.remove()
    
    # Add console handler (INFO level)
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
        colorize=True,
    )
    
    # Add file handler (DEBUG level)
    logger.add(
        str(log_path),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        encoding="utf-8",
    )
    
    return log_path


# ============================================================================
# Data Loader
# ============================================================================

class DataLoader:
    """Loads and filters evaluation data from HuggingFace (figai/GUI-Perturbed)."""

    def __init__(self, dataset_config: DatasetConfig):
        self.dataset_config = dataset_config
        self.rows = self._load_and_filter()

    def _load_and_filter(self) -> List[Dict]:
        """Load dataset from HuggingFace and filter by dataset variant configuration."""
        logger.info("Loading dataset from figai/GUI-Perturbed...")
        ds = load_dataset("figai/GUI-Perturbed", split="eval")

        # Filter by dataset variant type
        if self.dataset_config.dataset_variant is not None:
            variant_value = self.dataset_config.dataset_variant.value
            ds = ds.filter(lambda row: row["visual_variant"] == variant_value)

        # Filter by instruction type
        instruction_type_value = self.dataset_config.instruction_type.value
        ds = ds.filter(lambda row: row["instruction_type"] == instruction_type_value)

        # Sort by task_id and step_index
        ds = ds.sort(["task_id", "step_index"])

        logger.info(f"Loaded {len(ds)} rows after filtering")
        return [ds[i] for i in range(len(ds))]

    def get_rows(self) -> List[Dict]:
        """Get all filtered rows."""
        return self.rows


# ============================================================================
# Model Client
# ============================================================================

class ModelClient:
    """Client for vLLM API inference."""
    
    def __init__(self, config: ModelConfig, api_url: str, api_key: str):
        self.config = config
        if config.model_type == "claude":
            self.anthropic_client = Anthropic(api_key=api_key, max_retries=5)
            self.client = None
        else:
            self.client = OpenAI(base_url=api_url, api_key=api_key)
            self.anthropic_client = None
    
    def predict(self, instruction: str, image: Image.Image,
               metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Run model inference on instruction and image.

        Args:
            instruction: Text instruction
            image: PIL Image for inference
            metadata: Optional dict with task_id, step_index, variant for logging

        Returns raw prediction text from model.
        """
        # Validate image
        metadata = metadata or {}
        image = self._validate_image(image, **metadata)

        # Claude uses a separate API path
        if self.config.model_type == "claude":
            return self._predict_claude(instruction, image)

        # Build messages
        messages = self.build_messages(instruction, image, self.config.model_type, self.config.use_reasoning)

        # Make API request
        request_kwargs = {
            "model": self.config.name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }
        if self.config.seed is not None:
            request_kwargs["seed"] = self.config.seed

        response = self.client.chat.completions.create(**request_kwargs)
        return response.choices[0].message.content.strip()

    def _predict_claude(self, instruction: str, image: Image.Image) -> str:
        """Run Claude computer use inference via the beta API.

        Implements a mini agent loop matching the official Computer Use pattern:
        1. Send instruction → Claude requests a screenshot via the tool
        2. Return the screenshot as a tool_result → Claude responds with a click
        The loop runs for at most MAX_TURNS to avoid runaway costs.
        """
        MAX_TURNS = 3
        msg_data = build_claude_messages(instruction, image, self.config.use_reasoning)
        encoded_image = msg_data["encoded_image"]
        scale_factor = msg_data["scale_factor"]

        base_kwargs = {
            "model": self.config.name,
            "max_tokens": self.config.max_tokens,
            "tools": msg_data["tools"],
        }
        if self.config.use_reasoning:
            base_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": 2048,
            }
        else:
            base_kwargs["temperature"] = self.config.temperature

        messages = list(msg_data["messages"])

        for turn in range(MAX_TURNS):
            response = self.anthropic_client.beta.messages.create(
                betas=["computer-use-2025-01-24"],
                messages=messages,
                **base_kwargs,
            )

            # Check if any tool_use block has an action with coordinates (i.e. a click)
            for block in response.content:
                if block.type == "tool_use" and hasattr(block, "input"):
                    action = block.input.get("action", "")
                    if action != "screenshot":
                        # Got a click or other action with coordinates — done
                        return self._parse_claude_response(response, scale_factor)

            # Claude requested a screenshot — return the image as tool_result
            # Build the assistant message and tool_result for the next turn
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": encoded_image,
                                },
                            }
                        ],
                    })
            messages.append({"role": "user", "content": tool_results})

        # Fallback: return whatever the last response was
        return self._parse_claude_response(response, scale_factor)

    def _parse_claude_response(self, response, scale_factor: float) -> str:
        """Parse Claude response into a JSON string of content blocks.

        Coordinates are scaled back to the original 1920x1080 space using
        scale_factor, since the image was downscaled before sending to Claude.
        """
        blocks = []
        for block in response.content:
            if block.type == "thinking":
                blocks.append({"type": "thinking", "thinking": block.thinking})
            elif block.type == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                input_data = dict(block.input)
                # Scale coordinates back to original image dimensions
                if "coordinate" in input_data and scale_factor < 1.0:
                    x, y = input_data["coordinate"]
                    input_data["coordinate"] = [
                        round(x / scale_factor),
                        round(y / scale_factor),
                    ]
                blocks.append({
                    "type": "tool_use",
                    "name": block.name,
                    "input": input_data,
                })
        return json.dumps(blocks)

    def build_messages(self, instruction: str, image: Image.Image, model_type: str, use_reasoning: bool) -> List[Dict[str, Any]]:
        """Build messages for model inference.""" 
        if model_type == "gta1":
            return build_gta1_messages(instruction, image, use_reasoning)
        elif model_type == "uitars15":
            return build_uitars15_messages(instruction, image, use_reasoning)
        elif model_type == "qwen25vl":
            return build_qwen25vl_messages(instruction, image, use_reasoning)
        elif model_type == "claude":
            return build_claude_messages(instruction, image, use_reasoning)
        else:
            raise ValueError(f"Invalid model type: {model_type}")
    
    def _validate_image(self, image: Image.Image,
                        task_id: Optional[str] = None,
                        step_index: Optional[int] = None,
                        variant: Optional[str] = None) -> Image.Image:
        """
        Validate and prepare image for inference.

        Args:
            image: PIL Image from dataset
            task_id: Optional task ID for logging
            step_index: Optional step index for logging
            variant: Optional variant for logging

        Returns:
            Image ready for inference
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        original_width, original_height = image.size

        if original_width != EXPECTED_IMAGE_WIDTH or original_height != EXPECTED_IMAGE_HEIGHT:
            metadata_str = format_metadata_string(task_id, step_index, variant)
            logger.warning(
                f"[Image Dimension Check] Image is not {EXPECTED_IMAGE_WIDTH}x{EXPECTED_IMAGE_HEIGHT}: "
                f"actual={original_width}x{original_height}{metadata_str}"
            )

        return image



# ============================================================================
# Evaluation Runner
# ============================================================================

class Evaluator:
    """Main evaluation orchestrator."""
    
    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.data_loader = DataLoader(
            config.dataset_config,
        )
        self.model_client = ModelClient(
            config.model_config,
            config.api_url,
            config.api_key
        )
        self.output_path = self._get_output_path()
        self.save_interval = config.save_interval
    
    def _get_output_path(self) -> Path:
        """Generate output file path based on configuration."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"predictions_{self.config.config_id}_{timestamp}.jsonl"
        )
        return self.config.output_dir / filename
    
    def run(self):
        """Run evaluation on all dataset rows."""
        rows = self.data_loader.get_rows()
        total_rows = len(rows)
        hits = 0
        parsed = 0

        logger.info(f"Starting evaluation on {total_rows} rows")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.output_path, "w", encoding="utf-8") as f:
                for idx, row in enumerate(rows, 1):
                    prediction = self._process_row(row, step_num=idx, total_rows=total_rows)
                    json.dump(prediction, f, ensure_ascii=False)
                    f.write("\n")

                    if prediction["predicted_coordinate"] is not None:
                        parsed += 1
                    if prediction["is_hit"]:
                        hits += 1

                    if idx % self.save_interval == 0:
                        f.flush()

                    if idx % 100 == 0:
                        acc = hits / idx * 100
                        logger.info(
                            f"Processed {idx}/{total_rows} ({idx/total_rows*100:.1f}%) | "
                            f"Running accuracy: {acc:.1f}% ({hits}/{idx}) | "
                            f"Parse rate: {parsed}/{idx}"
                        )
        except Exception as e:
            logger.error(f"Error processing row {idx}: {e}")
            raise e

        # Final accuracy summary
        acc = hits / total_rows * 100 if total_rows > 0 else 0
        logger.info("=" * 80)
        logger.info(f"Evaluation completed. Processed {total_rows} rows")
        logger.info(f"Hit accuracy: {acc:.2f}% ({hits}/{total_rows})")
        logger.info(f"Parse rate: {parsed}/{total_rows} ({parsed/total_rows*100:.1f}%)")
        logger.info(f"Results saved to: {self.output_path}")
        logger.info("=" * 80)
    
    def _process_row(self, row: Dict, step_num: int, total_rows: int) -> Dict:
        """Process a single dataset row and return prediction with hit detection."""
        logger.info("=" * 80)
        logger.info(f"Step {step_num}/{total_rows} ({step_num/total_rows*100:.1f}%)")
        logger.info("=" * 80)

        model_type = self.config.model_config.model_type
        instruction = row["instruction"]
        image = row["screenshot"]

        # Prepare metadata for logging
        metadata = {
            "task_id": row.get("task_id"),
            "step_index": row.get("step_index"),
            "variant": row.get("visual_variant"),
        }

        raw_prediction = self.model_client.predict(instruction, image, metadata=metadata)
        logger.info(f"Instruction: {instruction}")

        # Truncate very long predictions in logs (likely model hallucination)
        if len(raw_prediction) > 500:
            logger.warning(f"Raw prediction is unusually long ({len(raw_prediction)} chars), truncating log output")
            logger.info(f"Raw prediction (first 500 chars): \n{raw_prediction[:500]}...")
        else:
            logger.info(f"Raw prediction: \n{raw_prediction}")

        # Extract and renormalize coordinates, then check hit
        gt_bbox = row["gt_bbox"]
        raw_coord = extract_coordinates(raw_prediction, model_type)
        predicted_coord = None
        hit = False

        if raw_coord is not None:
            predicted_coord = renormalize_to_original(raw_coord, model_type)
            hit = is_hit(predicted_coord, gt_bbox)

        logger.info(f"Ground truth bbox: {gt_bbox}")
        logger.info(f"Predicted coordinate: {predicted_coord}")
        logger.info(f"Is hit: {hit}")
        logger.info("=" * 80)

        return {
            "config_id": self.config.config_id,
            "model": model_type,
            "use_reasoning": self.config.model_config.use_reasoning,
            "query_type": self.config.dataset_config.instruction_type.value,
            "variant": metadata["variant"],
            "task_id": row["task_id"],
            "step_index": row["step_index"],
            "instruction": instruction,
            "raw_prediction": raw_prediction,
            "ground_truth_bbox": gt_bbox,
            "predicted_coordinate": list(predicted_coord) if predicted_coord else None,
            "is_hit": hit,
        }


# ============================================================================
# Predefined Configurations
# ============================================================================

@dataclass
class EvaluationPreset:
    """Predefined evaluation configuration preset."""
    config_id: str
    model_type: str
    model_name: str  # for vLLM server
    use_reasoning: bool
    instruction_type: InstructionType


def _create_preset(
    model_name: str,
    model_type: str,
    use_reasoning: bool,
    instruction_type: InstructionType,
) -> EvaluationPreset:
    """Create a single preset with explicit config_id."""
    reasoning_str = "reasoning" if use_reasoning else "no_reasoning"
    config_id = f"{model_type}_{reasoning_str}_{instruction_type.value}"
    
    return EvaluationPreset(
        config_id=config_id,
        model_name=model_name,
        model_type=model_type,
        use_reasoning=use_reasoning,
        instruction_type=instruction_type,
    )


def _generate_all_presets() -> Dict[str, EvaluationPreset]:
    """Generate all possible evaluation configuration presets.
    
    Generates 12 total combinations:
    - 4 models (gta1, qwen25vl, uitars15, claude)
    - 2 reasoning modes (with/without)
    - 2 instruction types (direct_query, relational_query)
    
    Note: dataset_variant is specified separately via CLI argument.
    This explicit structure makes it easy to verify correctness and debug.
    """
    presets = {}
    
    # Define all model types explicitly
    MODEL_TYPES = ["gta1", "qwen25vl", "uitars15", "claude"]

    # Define all other dimensions explicitly
    REASONING_MODES = [False, True]
    MODEL_NAMES = {
        "gta1": "HelloKKMe/GTA1-7B",
        "qwen25vl": "Qwen/Qwen2.5-VL-7B-Instruct",
        "uitars15": "ByteDance-Seed/UI-TARS-1.5-7B",
        "claude": "claude-sonnet-4-20250514",
    }
    INSTRUCTION_TYPES = [
        InstructionType.DIRECT_QUERY,
        InstructionType.RELATIONAL_QUERY,
    ]
    
    # Generate all combinations (without dataset_variant)
    for model_type in MODEL_TYPES:
        for use_reasoning in REASONING_MODES:
            for instruction_type in INSTRUCTION_TYPES:
                preset = _create_preset(
                    model_name=MODEL_NAMES[model_type],
                    model_type=model_type,
                    use_reasoning=use_reasoning,
                    instruction_type=instruction_type,
                )
                presets[preset.config_id] = preset
    
    return presets


EVALUATION_PRESETS = _generate_all_presets()


def list_presets() -> List[str]:
    """List all available preset configuration IDs."""
    return sorted(EVALUATION_PRESETS.keys())


def get_preset(config_id: str) -> EvaluationPreset:
    """Get a preset configuration by ID."""
    if config_id not in EVALUATION_PRESETS:
        available = ", ".join(list_presets()[:10])
        raise ValueError(
            f"Unknown config_id: {config_id}. "
            f"Available presets (showing first 10): {available}... "
            f"Use --list_presets to see all."
        )
    return EVALUATION_PRESETS[config_id]


# ============================================================================
# CLI Interface
# ============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="evaluation script")
    
    # Output
    parser.add_argument("--output_dir", type=Path, required=True, help="Output directory")
    
    # Configuration selection
    parser.add_argument("--config_id", type=str, default=None, help="Preset configuration ID (e.g., 'gta1_no_reasoning_direct_query')")
    parser.add_argument("--list_presets", action="store_true", help="List all available preset configuration IDs and exit")
    parser.add_argument("--dataset_variant", default=None, type=str, choices=["style", "precision", "text_zoom", "original"], help="Dataset variant to evaluate")
    
    # Model configuration (optional overrides)
    parser.add_argument("--model_name", type=str, default=None, help="Override model name for vLLM (e.g., path to local checkpoint)")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max_tokens", type=int, default=1000)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--language", type=str, default="English")
    
    # API configuration
    parser.add_argument("--api_url", type=str, default=None, help="API URL (or use VLLM_API_URL env)")
    parser.add_argument("--api_key", type=str, default=None, help="API key (or use VLLM_API_KEY env)")
    
    # Other
    parser.add_argument("--save_interval", type=int, default=10, help="Save every N predictions")
    
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> EvaluationConfig:
    """Build evaluation configuration from arguments."""
    if args.list_presets:
        print("Available preset configurations:")
        for preset_id in list_presets():
            preset = EVALUATION_PRESETS[preset_id]
            print(f"  {preset_id}")
            print(f"    Model: {preset.model_type}, Reasoning: {preset.use_reasoning}, "
                  f"Instruction: {preset.instruction_type.value}")
        exit(0)
    
    if args.config_id is None:
        raise ValueError("--config_id is required. Use --list_presets to see available options.")
    
    preset = get_preset(args.config_id)

    # Validate preset model_type
    if preset.model_type not in VALID_MODEL_TYPES:
        raise ValueError(
            f"Invalid model_type '{preset.model_type}' in preset '{args.config_id}'. "
            f"Valid types: {VALID_MODEL_TYPES}"
        )
    
    # Parse dataset variant from CLI argument
    try:
        if args.dataset_variant is not None:
            dataset_variant = DatasetVariantType(args.dataset_variant)
        else:
            dataset_variant = None
    except ValueError:
        raise ValueError(
            f"Invalid dataset_variant: {args.dataset_variant}. "
            f"Must be one of: {[v.value for v in DatasetVariantType]}"
        )
    
    # Log preset details for debugging
    logger.info(f"Using preset: {args.config_id}")
    logger.info(f"  model_type: {preset.model_type}")
    logger.info(f"  use_reasoning: {preset.use_reasoning}")
    logger.info(f"  dataset_variant: {dataset_variant.value if dataset_variant is not None else 'None'}")
    logger.info(f"  instruction_type: {preset.instruction_type.value}")
    
    # Set model-specific default max_tokens if using default value
    # GTA1 only needs ~32 tokens for coordinate output (x,y), but we use 64 to be safe
    if args.max_tokens == 1000:  # Using default value
        max_tokens = DEFAULT_MAX_TOKENS.get((preset.model_type, preset.use_reasoning), args.max_tokens)
    else:
        max_tokens = args.max_tokens  # User explicitly set a value
    
    logger.info(f"  max_tokens: {max_tokens}")
    
    model_config = ModelConfig(
        name=args.model_name if args.model_name is not None else preset.model_name,
        model_type=preset.model_type,
        use_reasoning=preset.use_reasoning,
        temperature=args.temperature,
        max_tokens=max_tokens,
        top_p=args.top_p,
        seed=args.seed,
        language=args.language,
    )
    
    # Verify model_type was set correctly
    if model_config.model_type != preset.model_type:
        raise ValueError(
            f"ModelConfig model_type mismatch: expected '{preset.model_type}', "
            f"got '{model_config.model_type}'"
        )
    
    dataset_config = DatasetConfig(
        dataset_variant=dataset_variant,
        instruction_type=preset.instruction_type,
    )
    
    api_url = args.api_url or os.environ.get("VLLM_API_URL", "http://localhost:8000/v1")
    if preset.model_type == "claude":
        api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    else:
        api_key = args.api_key or os.environ.get("VLLM_API_KEY", "EMPTY")
    
    return EvaluationConfig(
        output_dir=args.output_dir,
        model_config=model_config,
        dataset_config=dataset_config,
        api_url=api_url,
        api_key=api_key,
        config_id=args.config_id,
        save_interval=args.save_interval,
    )


def main():
    """Main entry point."""
    args = parse_args()
    config = build_config(args)
    
    # Set up logging
    log_path = setup_logging(config.output_dir)
    logger.info(f"Logging to file: {log_path}")
    logger.info(f"Starting evaluation with config_id: {args.config_id}")
    
    evaluator = Evaluator(config)
    evaluator.run()
    
    logger.info(f"Evaluation completed. Logs saved to: {log_path}")


"""
uv run scripts/gui_perturbed_evaluator.py \
    --output_dir data/gui_perturbed_eval/predictions \
    --seed 42 \
    --config_id gta1_no_reasoning_direct_query
"""


if __name__ == "__main__":
    main()
