"""
Statistical Analysis Protocol for GUI-Perturbed Benchmark
==========================================================
Implements:
  1. 95% bootstrap confidence intervals (10,000 resamples) on all hit rates
  2. McNemar's test for all paired original-to-perturbed comparisons (matched samples)
  3. p-values and effect sizes with CIs for all key claims
  4. Exact binomial (Clopper-Pearson) intervals as secondary check on proportions

Data loading replicates the exact logic from:
  - baseline_data_visualization_v3.ipynb  (baseline: 3 models)
  - finetuned_data_visualization_v3.ipynb (finetuned: UI-TARS variants)
"""

import json
import re
import os
import ast
import math
import warnings
from pathlib import Path
from collections import defaultdict
from typing import Tuple, Optional, List

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore", category=FutureWarning)
np.random.seed(42)

# ============================================================================
# CONSTANTS
# ============================================================================
IMAGE_FACTOR = 28
MIN_PIXELS = 100 * 28 * 28
MAX_PIXELS = 16384 * 28 * 28
MAX_RATIO = 200
IMAGE_HEIGHT = 1080
IMAGE_WIDTH = 1920

VARIANTS = ['original', 'precision', 'style', 'text_shrink']
VARIANT_LABELS = {
    'original': 'Unperturbed',
    'precision': 'Precision',
    'style': 'Style',
    'text_shrink': 'Text shrink'
}

# ============================================================================
# HELPER FUNCTIONS (from notebooks)
# ============================================================================

def escape_single_quotes(text):
    pattern = r"(?<!\\)'"
    return re.sub(pattern, r"\\'", text)

def round_by_factor(number, factor):
    return round(number / factor) * factor

def ceil_by_factor(number, factor):
    return math.ceil(number / factor) * factor

def floor_by_factor(number, factor):
    return math.floor(number / factor) * factor

def smart_resize(height, width, factor=IMAGE_FACTOR, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS):
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError(f"absolute aspect ratio must be smaller than {MAX_RATIO}")
    h_bar = max(factor, round_by_factor(height, factor))
    w_bar = max(factor, round_by_factor(width, factor))
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = floor_by_factor(height / beta, factor)
        w_bar = floor_by_factor(width / beta, factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = ceil_by_factor(height * beta, factor)
        w_bar = ceil_by_factor(width * beta, factor)
    return h_bar, w_bar


# ============================================================================
# PARSING FUNCTIONS (from baseline notebook)
# ============================================================================

# --- Qwen2.5VL parser (Cell 12 of baseline notebook) ---
def parse_qwen_prediction(raw_prediction: str, debug: bool = False) -> Tuple[Optional[str], Optional[List[int]]]:
    tool_call_pattern = r'<tool_call>[\s\\n]*(\{.*?\})[\s\\n]*</tool_call>'
    tool_calls = re.findall(tool_call_pattern, raw_prediction, re.DOTALL)

    if not tool_calls:
        code_block_pattern = r'```(?:json)?[\s\\n]*(\{.*?\})[\s\\n]*```'
        code_blocks = re.findall(code_block_pattern, raw_prediction, re.DOTALL)
        if code_blocks:
            tool_calls = code_blocks
        else:
            if '"computer_use"' in raw_prediction and '"arguments"' in raw_prediction:
                json_pattern = r'\{[^{}]*"name"\s*:\s*"computer_use"[^{}]*"arguments"\s*:\s*\{[^}]*\}[^}]*\}'
                standalone_json = re.findall(json_pattern, raw_prediction, re.DOTALL)
                if standalone_json:
                    tool_calls = standalone_json

    if not tool_calls:
        return None, None

    actions = []
    for tool_call_str in tool_calls:
        try:
            tool_call_str = tool_call_str.strip().replace('\\n', '')
            tool_call_json = json.loads(tool_call_str)
            if 'arguments' in tool_call_json:
                actions.append(tool_call_json['arguments'])
            elif 'action' in tool_call_json:
                actions.append(tool_call_json)
        except json.JSONDecodeError:
            continue

    if not actions:
        return None, None

    coordinates = None
    for action in actions:
        if 'coordinate' in action and action['coordinate']:
            coordinates = action['coordinate']
            break

    click_actions = {'left_click', 'right_click', 'middle_click', 'double_click',
                     'mouse_move', 'left_click_drag'}
    action_type = None
    non_click_action = None
    for action in actions:
        action_name = action.get('action', '')
        if action_type is None:
            action_type = 'click'
        if action_name not in click_actions:
            non_click_action = action_name
            break
    if non_click_action:
        action_type = non_click_action

    if action_type == 'terminate' and actions:
        for action in actions:
            if action.get('action') == 'terminate' and 'status' in action:
                status = action.get('status', '')
                if status:
                    action_type = f"terminate_{status}"
                break
    if action_type == 'browser_select_option':
        action_type = 'select'

    return action_type, coordinates


# --- UI-TARS1.5 parser (Cells 16-17 of baseline notebook) ---
def parse_action(action_str):
    try:
        node = ast.parse(action_str, mode='eval')
        if not isinstance(node, ast.Expression):
            raise ValueError("Not an expression")
        call = node.body
        if not isinstance(call, ast.Call):
            raise ValueError("Not a function call")
        if isinstance(call.func, ast.Name):
            func_name = call.func.id
        elif isinstance(call.func, ast.Attribute):
            func_name = call.func.attr
        else:
            func_name = None
        kwargs = {}
        for kw in call.keywords:
            key = kw.arg
            if isinstance(kw.value, ast.Constant):
                value = kw.value.value
            elif isinstance(kw.value, ast.Str):
                value = kw.value.s
            else:
                value = None
            kwargs[key] = value
        return {'function': func_name, 'args': kwargs}
    except Exception:
        return None


def _nan_action(reflection, thought, text):
    return {"reflection": reflection, "thought": thought, "action_type": None, "action_inputs": {}, "text": text}


def parse_action_to_structure_output_baseline(text, factor=IMAGE_FACTOR, origin_resized_height=1080,
                                               origin_resized_width=1920, model_type="qwen25vl",
                                               max_pixels=16384*28*28, min_pixels=100*28*28):
    """Baseline notebook version (Cell 16) - raises on unparseable actions."""
    text = text.strip()
    if model_type == "qwen25vl":
        smart_resize_height, smart_resize_width = smart_resize(
            origin_resized_height, origin_resized_width, factor=IMAGE_FACTOR,
            min_pixels=min_pixels, max_pixels=max_pixels)

    if text.startswith("Thought:"):
        thought_pattern = r"Thought: (.+?)(?=\s*Action:|$)"
    elif text.startswith("Reflection:"):
        thought_pattern = r"Reflection: (.+?)Action_Summary: (.+?)(?=\s*Action:|$)"
    elif text.startswith("Action_Summary:"):
        thought_pattern = r"Action_Summary: (.+?)(?=\s*Action:|$)"
    else:
        thought_pattern = r"Thought: (.+?)(?=\s*Action:|$)"

    reflection, thought = None, None
    thought_match = re.search(thought_pattern, text, re.DOTALL)
    if thought_match:
        if len(thought_match.groups()) == 1:
            thought = thought_match.group(1).strip()
        elif len(thought_match.groups()) == 2:
            thought = thought_match.group(2).strip()
            reflection = thought_match.group(1).strip()

    if "Action:" not in text:
        return [_nan_action(reflection, thought, text)]

    action_str = text.split("Action:")[-1]
    tmp_all_action = action_str.split("\n\n")
    all_action = []
    for action_str in tmp_all_action:
        if "type(content" in action_str:
            def escape_quotes(match):
                return match.group(1)
            pattern = r"type\(content='(.*?)'\)"
            content = re.sub(pattern, escape_quotes, action_str)
            action_str = escape_single_quotes(content)
            action_str = "type(content='" + action_str + "')"
        all_action.append(action_str)

    parsed_actions = [parse_action(action.replace("\n", "\\n").lstrip()) for action in all_action]
    actions = []
    for action_instance, raw_str in zip(parsed_actions, all_action):
        if action_instance is None:
            actions.append(_nan_action(reflection, thought, text))
            continue
        action_type = action_instance["function"]
        params = action_instance["args"]
        action_inputs = {}
        for param_name, param in params.items():
            if param == "":
                continue
            param = param.lstrip()
            action_inputs[param_name.strip()] = param
            if "start_box" in param_name or "end_box" in param_name:
                ori_box = param
                numbers = ori_box.replace("(", "").replace(")", "").replace("[", "").replace("]", "").split(",")
                if model_type == "qwen25vl":
                    float_numbers = []
                    for num_idx, num in enumerate(numbers):
                        num = float(num)
                        if (num_idx + 1) % 2 == 0:
                            float_numbers.append(round(float(num / smart_resize_height * IMAGE_HEIGHT)))
                        else:
                            float_numbers.append(round(float(num / smart_resize_width * IMAGE_WIDTH)))
                else:
                    raise ValueError(f"Unknown model type: {model_type}")
                action_inputs[param_name.strip()] = str(float_numbers)
        actions.append({
            "reflection": reflection, "thought": thought,
            "action_type": action_type, "action_inputs": action_inputs, "text": text
        })
    return actions


def parse_action_to_structure_output_finetuned(text, factor=IMAGE_FACTOR, origin_resized_height=1080,
                                                origin_resized_width=1920, model_type="qwen25vl",
                                                max_pixels=16384*28*28, min_pixels=100*28*28, row_context=None):
    """Finetuned notebook version (Cell 16) - returns _nan_action on failures instead of raising."""
    try:
        text = text.strip()
        if model_type == "qwen25vl":
            smart_resize_height, smart_resize_width = smart_resize(
                origin_resized_height, origin_resized_width, factor=IMAGE_FACTOR,
                min_pixels=min_pixels, max_pixels=max_pixels)

        if text.startswith("Thought:"):
            thought_pattern = r"Thought: (.+?)(?=\s*Action:|$)"
        elif text.startswith("Reflection:"):
            thought_pattern = r"Reflection: (.+?)Action_Summary: (.+?)(?=\s*Action:|$)"
        elif text.startswith("Action_Summary:"):
            thought_pattern = r"Action_Summary: (.+?)(?=\s*Action:|$)"
        else:
            thought_pattern = r"Thought: (.+?)(?=\s*Action:|$)"

        reflection, thought = None, None
        thought_match = re.search(thought_pattern, text, re.DOTALL)
        if thought_match:
            if len(thought_match.groups()) == 1:
                thought = thought_match.group(1).strip()
            elif len(thought_match.groups()) == 2:
                thought = thought_match.group(2).strip()
                reflection = thought_match.group(1).strip()

        if "Action:" not in text:
            return [_nan_action(reflection, thought, text)]

        action_str = text.split("Action:")[-1]
        tmp_all_action = action_str.split("\n\n")
        all_action = []
        for action_str in tmp_all_action:
            if "type(content" in action_str:
                def escape_quotes(match):
                    return match.group(1)
                pattern = r"type\(content='(.*?)'\)"
                content = re.sub(pattern, escape_quotes, action_str)
                action_str = escape_single_quotes(content)
                action_str = "type(content='" + action_str + "')"
            all_action.append(action_str)

        parsed_actions = [parse_action(action.replace("\n", "\\n").lstrip()) for action in all_action]
        actions = []
        for action_instance, raw_str in zip(parsed_actions, all_action):
            if action_instance is None:
                actions.append(_nan_action(reflection, thought, text))
                continue
            action_type = action_instance["function"]
            params = action_instance["args"]
            action_inputs = {}
            for param_name, param in params.items():
                if param == "":
                    continue
                param = param.lstrip()
                action_inputs[param_name.strip()] = param
                if "start_box" in param_name or "end_box" in param_name:
                    ori_box = param
                    numbers = ori_box.replace("(", "").replace(")", "").replace("[", "").replace("]", "").split(",")
                    if model_type == "qwen25vl":
                        float_numbers = []
                        for num_idx, num in enumerate(numbers):
                            num = float(num)
                            if (num_idx + 1) % 2 == 0:
                                float_numbers.append(round(float(num / smart_resize_height * IMAGE_HEIGHT)))
                            else:
                                float_numbers.append(round(float(num / smart_resize_width * IMAGE_WIDTH)))
                    else:
                        raise ValueError(f"Unknown model type: {model_type}")
                    action_inputs[param_name.strip()] = str(float_numbers)
            actions.append({
                "reflection": reflection, "thought": thought,
                "action_type": action_type, "action_inputs": action_inputs, "text": text
            })
        return actions
    except Exception:
        return [_nan_action(None, None, text)]


# --- GTA1 parser (Cells 20-21 of baseline notebook) ---
def extract_coordinates(raw_string):
    try:
        matches = re.findall(r"\((-?\d*\.?\d+),\s*(-?\d*\.?\d+)\)", raw_string)
        if matches:
            return [int(matches[0][0]), int(matches[0][1])]
        matches = re.findall(r"(-?\d+\.?\d*),\s*(-?\d+\.?\d*)", raw_string)
        if matches:
            return list(map(int, matches[0]))
        return [0, 0]
    except:
        return [0, 0]


def get_action_type_and_coordinates_uitars15(row):
    structured_actions = row['structured_actions']
    action_type = structured_actions[0]['action_type']
    if action_type == 'click':
        coordinates = structured_actions[0]['action_inputs']['start_box']
        coordinates = ast.literal_eval(coordinates)
        return action_type, coordinates
    else:
        coordinates = None
    return action_type, coordinates


# ============================================================================
# HIT BOX ACCURACY (from notebooks)
# ============================================================================

def is_coords_in_bbox_baseline(coords, bbox, tolerance=20):
    """Baseline notebook: tolerance=20."""
    if coords is None:
        return 0
    x1, y1, w, h = ast.literal_eval(bbox) if isinstance(bbox, str) else bbox
    try:
        if isinstance(coords, (list, tuple)) and len(coords) == 4:
            # 4-element coords: take center of box
            x = (coords[0] + coords[2]) / 2
            y = (coords[1] + coords[3]) / 2
        elif isinstance(coords, (list, tuple)) and len(coords) == 2:
            x, y = coords
        else:
            x, y = coords
    except (TypeError, ValueError):
        return 0
    return int(x1 - tolerance / 2 <= x <= x1 + w + tolerance / 2 and
               y1 - tolerance / 2 <= y <= y1 + h + tolerance / 2)


def is_coords_in_bbox_finetuned(coords, bbox, tolerance=4):
    """Finetuned notebook cell 19: tolerance=4."""
    if coords is None:
        return 0
    x1, y1, w, h = ast.literal_eval(bbox) if isinstance(bbox, str) else bbox
    try:
        x, y = coords
    except:
        return 0
    return int(x1 - tolerance / 2 <= x <= x1 + w + tolerance / 2 and
               y1 - tolerance / 2 <= y <= y1 + h + tolerance / 2)


def is_coords_in_bbox_strict(coords, bbox):
    """Finetuned notebook cell 23 (_is_coords_in_bbox): tolerance=0, used for combined plots."""
    if coords is None or bbox is None:
        return 0
    try:
        x, y = coords[0], coords[1]
    except (TypeError, IndexError):
        return 0
    if isinstance(bbox, str):
        bbox = ast.literal_eval(bbox)
    x1, y1, w, h = bbox
    return 1 if (x1 <= x <= x1 + w and y1 <= y <= y1 + h) else 0


def is_bbox_hit(row, tolerance=20):
    """Generic hit calculator matching both notebooks' is_bbox_hit logic."""
    action_type = row.get('action_type', None)
    pred = row.get('coordinates')
    gt_bbox = row.get('ground_truth_bbox')

    if action_type in ('click', 'scroll', 'type', 'select'):
        return is_coords_in_bbox_baseline(pred, gt_bbox, tolerance=tolerance)
    elif action_type in ('wait', 'finished', 'call_user', 'hotkey'):
        return 0
    elif action_type is None:
        try:
            return is_coords_in_bbox_baseline(pred, gt_bbox, tolerance=tolerance)
        except:
            return 0
    else:
        # Unknown action type — try coords, fall back to 0
        try:
            return is_coords_in_bbox_baseline(pred, gt_bbox, tolerance=tolerance)
        except:
            return 0


# ============================================================================
# DATA LOADING — BASELINE (replicates baseline_data_visualization_v3.ipynb)
# ============================================================================

def load_baseline_from_csv():
    """
    Cell 41 path: load from cleaned CSV + Invalid filtering.
    Returns per-sample df with precomputed hit_box_accuracy (tolerance=20).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'baseline_results_full_new_cleaned.csv')

    print(f"Loading baseline CSV from {csv_path}")
    df = pd.read_csv(csv_path)
    n_before = len(df)
    df = df[df['interesting_cases'] != 'Invalid'].copy()
    print(f"  Filtered Invalid: {n_before} -> {len(df)} rows")

    # Coerce hit_box_accuracy to numeric (Cell 48 logic)
    if df['hit_box_accuracy'].dtype == object:
        df['hit_box_accuracy'] = df['hit_box_accuracy'].replace(
            {'TRUE': 1, 'True': 1, True: 1, 'FALSE': 0, 'False': 0, False: 0}
        ).infer_objects(copy=False)
    df['hit_box_accuracy'] = pd.to_numeric(df['hit_box_accuracy'], errors='coerce')

    # Add level column
    df['level'] = df['query_type'].map({'direct_query': 'L1', 'relational_query': 'L2'})

    print(f"  Models: {sorted(df['model'].unique())}")
    print(f"  Variants: {sorted(df['variant'].unique())}")
    print(f"  Samples per (model, variant, use_reasoning, query_type):")
    print(f"    {df.groupby(['model', 'variant', 'use_reasoning', 'query_type']).size().describe()}")
    return df


# ============================================================================
# DATA LOADING — BASELINE FROM JSONL (replicates baseline notebook cells 2-3)
# ============================================================================

def load_baseline_from_jsonl():
    """
    Cells 2-3 + parsing + hit_box_accuracy computation.
    Used when we need to recompute hit_box_accuracy from raw predictions.
    """
    RESULT_FOLDER_PATH = "/Users/lockewang/FIG/GUI-DR/baseline_results_full_new/baseline_results"

    jsonl_files = sorted(list(Path(RESULT_FOLDER_PATH).glob("*.jsonl")))
    print(f"Found {len(jsonl_files)} .jsonl files in baseline results")

    dataframes = {}
    for jsonl_file in jsonl_files:
        df = pd.read_json(jsonl_file, lines=True)
        dataframes[jsonl_file.name] = df

    # GTA1: simple concat
    gta1_dfs = [df for fn, df in dataframes.items() if fn.startswith("predictions_gta1")]
    df_all = pd.concat(gta1_dfs, ignore_index=True)

    # Qwen + UI-TARS: stitch re-runs (Cell 3)
    configs = [
        ("predictions_qwen25vl_no_reasoning_direct_query_20251214_022358", "predictions_qwen25vl_no_reasoning_direct_query_20251215_021838", "replace"),
        ("predictions_qwen25vl_no_reasoning_relational_query_20251214_022351", "predictions_qwen25vl_no_reasoning_relational_query_20251215_021833", "concat"),
        ("predictions_qwen25vl_reasoning_direct_query_20251214_022355", "predictions_qwen25vl_reasoning_direct_query_20251215_021836", "replace"),
        ("predictions_qwen25vl_reasoning_relational_query_20251214_022344", "predictions_qwen25vl_reasoning_relational_query_20251215_021829", "concat"),
        ("predictions_uitars15_no_reasoning_direct_query_20251213_223027", "predictions_uitars15_no_reasoning_direct_query_20251215_024416", "replace"),
        ("predictions_uitars15_no_reasoning_relational_query_20251213_222956", "predictions_uitars15_no_reasoning_relational_query_20251215_024414", "replace"),
        ("predictions_uitars15_reasoning_direct_query_20251213_223013", "predictions_uitars15_reasoning_direct_query_20251215_024415", "replace"),
        ("predictions_uitars15_reasoning_relational_query_20251213_222938", "predictions_uitars15_reasoning_relational_query_20251215_024412", "replace"),
    ]

    for config in configs:
        big_df = dataframes[config[0] + ".jsonl"].copy()
        small_df = dataframes[config[1] + ".jsonl"].copy()
        if config[2] == "replace":
            big_df.iloc[-92:] = small_df.values
        elif config[2] == "concat":
            big_df = pd.concat([big_df, small_df], ignore_index=True)
        df_all = pd.concat([df_all, big_df], ignore_index=True)

    print(f"  Loaded {len(df_all)} baseline rows from JSONL")
    return df_all


# ============================================================================
# DATA LOADING — FINETUNED (replicates finetuned_data_visualization_v3.ipynb)
# ============================================================================

def load_finetuned_from_jsonl():
    """
    Cells 6, 8, 10, 12 of finetuned notebook.
    Returns combined df with model labels.
    """
    # --- Baseline UI-TARS from JSONL (Cell 6) ---
    RESULT_FOLDER_PATH = "/Users/lockewang/FIG/GUI-DR/baseline_results_full_new/baseline_results"
    jsonl_files = sorted(list(Path(RESULT_FOLDER_PATH).glob("*.jsonl")))
    dataframes = {}
    for jsonl_file in jsonl_files:
        df = pd.read_json(jsonl_file, lines=True)
        dataframes[jsonl_file.name] = df

    # Stitch UI-TARS re-runs only (Cell 6 of finetuned notebook)
    configs = [
        ("predictions_uitars15_no_reasoning_direct_query_20251213_223027", "predictions_uitars15_no_reasoning_direct_query_20251215_024416", "replace"),
        ("predictions_uitars15_no_reasoning_relational_query_20251213_222956", "predictions_uitars15_no_reasoning_relational_query_20251215_024414", "replace"),
        ("predictions_uitars15_reasoning_direct_query_20251213_223013", "predictions_uitars15_reasoning_direct_query_20251215_024415", "replace"),
        ("predictions_uitars15_reasoning_relational_query_20251213_222938", "predictions_uitars15_reasoning_relational_query_20251215_024412", "replace"),
    ]
    # The finetuned notebook uses df_baseline for the last loaded file, then stitches
    # It iterates, so df_baseline ends up as the last stitched config's big_df
    df_baseline = None
    for config in configs:
        big_df = dataframes[config[0] + ".jsonl"].copy()
        small_df = dataframes[config[1] + ".jsonl"].copy()
        if config[2] == "replace":
            big_df.iloc[-92:] = small_df.values
        elif config[2] == "concat":
            big_df = pd.concat([big_df, small_df], ignore_index=True)
        if df_baseline is None:
            df_baseline = big_df.copy()
        else:
            df_baseline = pd.concat([df_baseline, big_df], ignore_index=True)
    df_baseline['model'] = 'baseline'

    # --- Finetuned models (Cell 8) ---
    FINETUNED_RESULT_FOLDER_PATH = "/Users/lockewang/FIG/sca-sprint0-archive/results/final_model_all_results"
    ft_jsonl_files = sorted(list(Path(FINETUNED_RESULT_FOLDER_PATH).glob("*.jsonl")))
    ft_dataframes = {}
    for jsonl_file in ft_jsonl_files:
        df = pd.read_json(jsonl_file, lines=True)
        ft_dataframes[jsonl_file.name] = df

    model_style_files = [
        'predictions_uitars15_no_reasoning_direct_query_20260109_033744.jsonl',
        'predictions_uitars15_no_reasoning_relational_query_20260109_033741.jsonl',
        'predictions_uitars15_reasoning_direct_query_20260109_033743.jsonl',
        'predictions_uitars15_reasoning_relational_query_20260109_033734.jsonl'
    ]
    model_all_files = [
        'predictions_uitars15_no_reasoning_direct_query_20260109_204302.jsonl',
        'predictions_uitars15_no_reasoning_relational_query_20260109_204303.jsonl',
        'predictions_uitars15_reasoning_direct_query_20260109_204302.jsonl',
        'predictions_uitars15_reasoning_relational_query_20260109_204305.jsonl'
    ]
    model_text_shrink_files = [
        'predictions_uitars15_no_reasoning_direct_query_20260110_005249.jsonl',
        'predictions_uitars15_no_reasoning_relational_query_20260110_005246.jsonl',
        'predictions_uitars15_reasoning_direct_query_20260110_005248.jsonl',
        'predictions_uitars15_reasoning_relational_query_20260110_005244.jsonl'
    ]
    model_25k_3_epoch_files = [
        'predictions_uitars15_no_reasoning_direct_query_20260108_203457.jsonl',
        'predictions_uitars15_no_reasoning_relational_query_20260108_203520.jsonl',
        'predictions_uitars15_reasoning_direct_query_20260108_203518.jsonl',
        'predictions_uitars15_reasoning_relational_query_20260108_203521.jsonl'
    ]

    model_all_df = pd.concat([ft_dataframes[f] for f in model_all_files], ignore_index=True)
    model_style_df = pd.concat([ft_dataframes[f] for f in model_style_files], ignore_index=True)
    model_text_shrink_df = pd.concat([ft_dataframes[f] for f in model_text_shrink_files], ignore_index=True)
    model_all_high_rank_df = pd.concat([ft_dataframes[f] for f in model_25k_3_epoch_files], ignore_index=True)

    model_all_df['model'] = 'all'
    model_style_df['model'] = 'style'
    model_text_shrink_df['model'] = 'text_shrink_zoom'
    model_all_high_rank_df['model'] = 'all_25k_3_epoch'

    df_all = pd.concat([model_all_df, model_style_df, model_text_shrink_df, model_all_high_rank_df], ignore_index=True)

    # --- 25k Salesforce 1 epoch (Cell 10) ---
    SALESFORCE_RESULTS_DIR = Path("/Users/lockewang/FIG/sca-sprint0-archive/results/exp_2_salesforce_1_epoch_results")
    salesforce_dfs = []
    for jsonl_file in sorted(list(SALESFORCE_RESULTS_DIR.glob("*.jsonl"))):
        salesforce_dfs.append(pd.read_json(jsonl_file, lines=True))
    df_25k_salesforce = pd.concat(salesforce_dfs, ignore_index=True)
    df_25k_salesforce['model'] = '25k_salesforce_1_epoch'
    df_all = pd.concat([df_all, df_25k_salesforce], ignore_index=True)

    # --- 25k Perturbed 1 epoch (Cell 12) ---
    perturbed_dir = Path("/Users/lockewang/FIG/sca-sprint0-archive/results/exp_2_checkpoint_1_epoch_results/")
    perturbed_dfs = []
    for jsonl_file in sorted(list(perturbed_dir.glob("*.jsonl"))):
        perturbed_dfs.append(pd.read_json(jsonl_file, lines=True))
    df_25k_perturbed = pd.concat(perturbed_dfs, ignore_index=True)
    df_25k_perturbed['model'] = '25k_perturbed_1_epoch'
    df_all = pd.concat([df_all, df_25k_perturbed], ignore_index=True)

    print(f"  Loaded finetuned df_all: {len(df_all)} rows, models: {sorted(df_all['model'].unique())}")
    print(f"  Loaded baseline (uitars15): {len(df_baseline)} rows")
    return df_baseline, df_all


def parse_and_compute_hit_finetuned(df_all, tolerance=4):
    """
    Cells 16-19 of finetuned notebook: parse actions and compute hit_box_accuracy.
    All models in finetuned notebook are UI-TARS format.
    """
    print("  Parsing structured actions for finetuned data...")

    df_all['structured_actions'] = df_all['raw_prediction'].apply(
        lambda text: parse_action_to_structure_output_finetuned(text)
    )

    df_all['action_type'], df_all['coordinates'] = zip(
        *df_all.apply(get_action_type_and_coordinates_uitars15, axis=1)
    )

    # Hit box accuracy (Cell 19, tolerance=4)
    df_all['hit_box_accuracy'] = df_all.apply(lambda row: is_bbox_hit(row, tolerance=tolerance), axis=1)

    # Add level
    df_all['level'] = df_all['query_type'].map({'direct_query': 'L1', 'relational_query': 'L2'})

    print(f"  Hit rate overall: {df_all['hit_box_accuracy'].mean():.4f}")
    return df_all


# ============================================================================
# STATISTICAL ANALYSIS FUNCTIONS
# ============================================================================

def bootstrap_ci(data, n_bootstrap=10000, ci=0.95, stat_func=np.mean):
    """
    Compute bootstrap confidence interval for a statistic.
    Returns (point_estimate, ci_lower, ci_upper).
    """
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)
    if n == 0:
        return np.nan, np.nan, np.nan

    point_est = stat_func(data)
    boot_stats = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        sample = np.random.choice(data, size=n, replace=True)
        boot_stats[i] = stat_func(sample)

    alpha = 1 - ci
    ci_lower = np.percentile(boot_stats, 100 * alpha / 2)
    ci_upper = np.percentile(boot_stats, 100 * (1 - alpha / 2))
    return point_est, ci_lower, ci_upper


def clopper_pearson(k, n, alpha=0.05):
    """
    Exact binomial (Clopper-Pearson) confidence interval.
    k: number of successes, n: number of trials
    Returns (lower, upper) at (1-alpha) confidence level.
    """
    if n == 0:
        return np.nan, np.nan
    lower = stats.beta.ppf(alpha / 2, k, n - k + 1) if k > 0 else 0.0
    upper = stats.beta.ppf(1 - alpha / 2, k + 1, n - k) if k < n else 1.0
    return lower, upper


def mcnemar_test(y_orig, y_pert):
    """
    McNemar's test for paired binary outcomes.
    y_orig, y_pert: arrays of 0/1 for matched samples.
    Returns dict with test statistic, p-value, odds_ratio, and 2x2 table counts.
    """
    y_orig = np.asarray(y_orig, dtype=int)
    y_pert = np.asarray(y_pert, dtype=int)
    assert len(y_orig) == len(y_pert), "Mismatched lengths"

    # 2x2 contingency table
    # b = orig correct, pert wrong (discordant: degradation)
    # c = orig wrong, pert correct (discordant: improvement)
    a = np.sum((y_orig == 1) & (y_pert == 1))  # both correct
    b = np.sum((y_orig == 1) & (y_pert == 0))  # orig correct, pert wrong
    c = np.sum((y_orig == 0) & (y_pert == 1))  # orig wrong, pert correct
    d = np.sum((y_orig == 0) & (y_pert == 0))  # both wrong

    n_discordant = b + c

    # McNemar's test with continuity correction
    if n_discordant == 0:
        chi2 = 0.0
        p_value = 1.0
    else:
        # Standard McNemar's with continuity correction
        chi2 = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) > 0 else 0.0
        p_value = 1 - stats.chi2.cdf(chi2, df=1)

    # Exact McNemar's (binomial test) for small samples
    if n_discordant < 25:
        p_value_exact = stats.binomtest(b, n_discordant, 0.5).pvalue if n_discordant > 0 else 1.0
    else:
        p_value_exact = p_value

    # Odds ratio (b/c) with handling for zero cells
    if c > 0:
        odds_ratio = b / c
    else:
        odds_ratio = np.inf if b > 0 else 1.0

    # Cohen's g: effect size for McNemar's test
    if n_discordant > 0:
        cohens_g = b / n_discordant - 0.5
    else:
        cohens_g = 0.0

    return {
        'a': int(a), 'b': int(b), 'c': int(c), 'd': int(d),
        'n_discordant': int(n_discordant),
        'chi2': chi2,
        'p_value': p_value,
        'p_value_exact': p_value_exact,
        'odds_ratio': odds_ratio,
        'cohens_g': cohens_g,
    }


def bootstrap_effect_size_ci(y_orig, y_pert, n_bootstrap=10000, ci=0.95):
    """
    Bootstrap CI on the hit rate difference (orig - pert).
    Returns (diff, ci_lower, ci_upper).
    """
    y_orig = np.asarray(y_orig, dtype=float)
    y_pert = np.asarray(y_pert, dtype=float)
    n = len(y_orig)
    diff = np.mean(y_orig) - np.mean(y_pert)

    boot_diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        boot_diffs[i] = np.mean(y_orig[idx]) - np.mean(y_pert[idx])

    alpha = 1 - ci
    ci_lower = np.percentile(boot_diffs, 100 * alpha / 2)
    ci_upper = np.percentile(boot_diffs, 100 * (1 - alpha / 2))
    return diff, ci_lower, ci_upper


# ============================================================================
# MATCHING SAMPLES ACROSS VARIANTS
# ============================================================================

def match_samples_across_variants(df, group_cols=['model', 'use_reasoning', 'query_type']):
    """
    For each group (model x reasoning x query_type), match samples across variants
    using task_id + step_index as the key.

    Returns a dict: (model, reasoning, query_type) -> DataFrame with columns:
        task_id, step_index, hit_original, hit_precision, hit_style, hit_text_shrink
    """
    matched = {}

    for group_key, group_df in df.groupby(group_cols):
        # Pivot: rows = (task_id, step_index), columns = variant, values = hit_box_accuracy
        variant_dfs = {}
        for variant in VARIANTS:
            vdf = group_df[group_df['variant'] == variant][['task_id', 'step_index', 'hit_box_accuracy']].copy()
            vdf = vdf.rename(columns={'hit_box_accuracy': f'hit_{variant}'})
            variant_dfs[variant] = vdf

        # Inner join to get matched samples present in all variants
        merged = variant_dfs['original']
        for variant in VARIANTS[1:]:
            merged = merged.merge(variant_dfs[variant], on=['task_id', 'step_index'], how='inner')

        if isinstance(group_key, tuple):
            matched[group_key] = merged
        else:
            matched[(group_key,)] = merged

    return matched


# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def run_analysis_on_df(df, dataset_label, group_cols=['model', 'use_reasoning', 'query_type']):
    """
    Run all statistical analyses on a given dataframe.
    Returns results dict with all tables.
    """
    print(f"\n{'='*80}")
    print(f"STATISTICAL ANALYSIS: {dataset_label}")
    print(f"{'='*80}")

    results = {
        'bootstrap_ci': [],
        'clopper_pearson': [],
        'mcnemar': [],
        'effect_size': [],
    }

    # ---------------------------------------------------------------
    # 1. Bootstrap CIs + Clopper-Pearson for ALL hit rates
    # ---------------------------------------------------------------
    print(f"\n--- 1. Hit Rate Confidence Intervals ---")
    groups = df.groupby(group_cols + ['variant'])

    for group_key, group_df in groups:
        hits = group_df['hit_box_accuracy'].values
        n = len(hits)
        k = int(np.nansum(hits))

        # Bootstrap CI
        point_est, boot_lo, boot_hi = bootstrap_ci(hits, n_bootstrap=10000)

        # Clopper-Pearson
        cp_lo, cp_hi = clopper_pearson(k, n)

        row = {
            **dict(zip(group_cols + ['variant'], group_key)),
            'n': n,
            'k': k,
            'hit_rate': point_est,
            'boot_ci_lo': boot_lo,
            'boot_ci_hi': boot_hi,
            'cp_ci_lo': cp_lo,
            'cp_ci_hi': cp_hi,
        }
        results['bootstrap_ci'].append(row)
        results['clopper_pearson'].append(row)

    ci_df = pd.DataFrame(results['bootstrap_ci'])
    print(f"\nHit rates with 95% CIs ({len(ci_df)} groups):")
    print(ci_df.to_string(index=False, float_format='{:.4f}'.format))

    # ---------------------------------------------------------------
    # 2. McNemar's test + Effect Sizes for paired comparisons
    # ---------------------------------------------------------------
    print(f"\n--- 2. McNemar's Test: Original vs Perturbed ---")

    # Check if matching columns exist
    if 'task_id' not in df.columns or 'step_index' not in df.columns:
        print("  WARNING: task_id or step_index not found. Attempting index-based matching.")
        print("  (Samples within each group are assumed to be in the same order across variants)")
        # Fallback: match by position within each group
        matched = _match_by_position(df, group_cols)
    else:
        matched = match_samples_across_variants(df, group_cols)

    perturbations = ['precision', 'style', 'text_shrink']

    for group_key, merged_df in matched.items():
        n_matched = len(merged_df)
        group_label = dict(zip(group_cols, group_key))

        for pert in perturbations:
            y_orig = merged_df['hit_original'].values
            y_pert = merged_df[f'hit_{pert}'].values

            # McNemar's test
            mc = mcnemar_test(y_orig, y_pert)

            # Bootstrap CI on effect size (hit rate difference)
            diff, diff_lo, diff_hi = bootstrap_effect_size_ci(y_orig, y_pert)

            row = {
                **group_label,
                'perturbation': pert,
                'n_matched': n_matched,
                'orig_hit_rate': np.mean(y_orig),
                'pert_hit_rate': np.mean(y_pert),
                'diff': diff,
                'diff_ci_lo': diff_lo,
                'diff_ci_hi': diff_hi,
                'mcnemar_chi2': mc['chi2'],
                'mcnemar_p': mc['p_value'],
                'mcnemar_p_exact': mc['p_value_exact'],
                'odds_ratio': mc['odds_ratio'],
                'cohens_g': mc['cohens_g'],
                'a_both_correct': mc['a'],
                'b_orig_only': mc['b'],
                'c_pert_only': mc['c'],
                'd_both_wrong': mc['d'],
                'n_discordant': mc['n_discordant'],
            }
            results['mcnemar'].append(row)
            results['effect_size'].append(row)

    mcnemar_df = pd.DataFrame(results['mcnemar'])
    if len(mcnemar_df) > 0:
        print(f"\nMcNemar's test results ({len(mcnemar_df)} comparisons):")
        display_cols = list(group_cols) + [
            'perturbation', 'n_matched', 'orig_hit_rate', 'pert_hit_rate',
            'diff', 'diff_ci_lo', 'diff_ci_hi',
            'mcnemar_p', 'odds_ratio', 'cohens_g',
            'b_orig_only', 'c_pert_only', 'n_discordant'
        ]
        print(mcnemar_df[display_cols].to_string(index=False, float_format='{:.4f}'.format))

        # Significance summary
        sig = mcnemar_df[mcnemar_df['mcnemar_p'] < 0.05]
        print(f"\n  Significant at p<0.05: {len(sig)} / {len(mcnemar_df)} comparisons")
        if len(sig) > 0:
            print(sig[display_cols].to_string(index=False, float_format='{:.4f}'.format))
    else:
        print("  No matched comparisons could be computed.")

    return results


def _match_by_position(df, group_cols):
    """Fallback: match samples by position within each (model, reasoning, query_type) group."""
    matched = {}
    for group_key, group_df in df.groupby(group_cols):
        variant_arrays = {}
        min_len = float('inf')
        for variant in VARIANTS:
            vdf = group_df[group_df['variant'] == variant].sort_index()
            variant_arrays[variant] = vdf['hit_box_accuracy'].values
            min_len = min(min_len, len(vdf))

        if min_len == 0:
            continue

        merged = pd.DataFrame({
            'task_id': range(min_len),
            'step_index': range(min_len),
        })
        for variant in VARIANTS:
            merged[f'hit_{variant}'] = variant_arrays[variant][:min_len]

        if isinstance(group_key, tuple):
            matched[group_key] = merged
        else:
            matched[(group_key,)] = merged

    return matched


# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def save_results(results, dataset_label, output_dir=None):
    """Save results to CSV files."""
    if output_dir is None:
        output_dir = os.path.dirname(__file__)

    prefix = dataset_label.lower().replace(' ', '_').replace('/', '_')

    ci_df = pd.DataFrame(results['bootstrap_ci'])
    if len(ci_df) > 0:
        path = os.path.join(output_dir, f'{prefix}_confidence_intervals.csv')
        ci_df.to_csv(path, index=False)
        print(f"  Saved: {path}")

    mcnemar_df = pd.DataFrame(results['mcnemar'])
    if len(mcnemar_df) > 0:
        path = os.path.join(output_dir, f'{prefix}_mcnemar_tests.csv')
        mcnemar_df.to_csv(path, index=False)
        print(f"  Saved: {path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("GUI-PERTURBED BENCHMARK — STATISTICAL ANALYSIS PROTOCOL")
    print("=" * 80)

    # ------------------------------------------------------------------
    # PART A: BASELINE (3 models: gta1, qwen25vl, uitars15)
    # ------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PART A: BASELINE MODELS (from cleaned CSV, tolerance=20)")
    print("=" * 80)

    df_baseline_csv = load_baseline_from_csv()
    baseline_results = run_analysis_on_df(
        df_baseline_csv,
        dataset_label='Baseline',
        group_cols=['model', 'use_reasoning', 'query_type']
    )
    save_results(baseline_results, 'baseline')

    # ------------------------------------------------------------------
    # PART B: FINETUNED (UI-TARS variants, tolerance=4)
    # ------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PART B: FINETUNED MODELS (from JSONL, tolerance=4)")
    print("=" * 80)

    df_ft_baseline, df_ft_all = load_finetuned_from_jsonl()

    # Parse and compute hit_box_accuracy for finetuned models
    df_ft_all = parse_and_compute_hit_finetuned(df_ft_all, tolerance=4)

    # Parse baseline (UI-TARS) with same tolerance for fair comparison
    print("  Parsing baseline (UI-TARS) for finetuned comparison...")
    df_ft_baseline = parse_and_compute_hit_finetuned(df_ft_baseline, tolerance=4)

    # Combine baseline + finetuned
    df_ft_combined = pd.concat([df_ft_baseline, df_ft_all], ignore_index=True)
    print(f"  Combined finetuned dataset: {len(df_ft_combined)} rows")
    print(f"  Models: {sorted(df_ft_combined['model'].unique())}")

    finetuned_results = run_analysis_on_df(
        df_ft_combined,
        dataset_label='Finetuned',
        group_cols=['model', 'use_reasoning', 'query_type']
    )
    save_results(finetuned_results, 'finetuned')

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nOutput files saved to:", os.path.dirname(__file__) or '.')
    print("  - baseline_confidence_intervals.csv")
    print("  - baseline_mcnemar_tests.csv")
    print("  - finetuned_confidence_intervals.csv")
    print("  - finetuned_mcnemar_tests.csv")


if __name__ == "__main__":
    main()
