"""
Generate finetuned_results_full.csv from finetuned model JSONL prediction files.

Replicates the pipeline from data/finetuned_data_visualization_v3.ipynb:
1. Load JSONL prediction files for each finetuned model variant
2. Parse raw_prediction -> structured_actions -> action_type + coordinates
3. Compute hit_box_accuracy, bbox_center_mse, normalized_mse, giou, ngiou
4. Include baseline (uitars15) rows loaded from JSONL files with stitching
5. Output data/finetuned_results_full.csv with the same schema as baseline_results_full_new.csv

Usage:
    python scripts/generate_finetuned_csv.py \
        --finetuned-dir /path/to/final_model_all_results
"""

import argparse
import ast
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

# ============================================================================
# Constants
# ============================================================================

IMAGE_FACTOR = 28
MIN_PIXELS = 100 * 28 * 28
MAX_PIXELS = 16384 * 28 * 28
MAX_RATIO = 200
IMAGE_HEIGHT = 1080
IMAGE_WIDTH = 1920

# JSONL file -> model name mappings
# Derived from data/finetuned_data_visualization_v3.ipynb cell 8 (notebook used 2026xxxx
# timestamps from a prior run; actual files in GUI-DR use 2025xxxx timestamps).
MODEL_STYLE_FILES = [
    'predictions_uitars15_no_reasoning_direct_query_20260109_033744.jsonl',
    'predictions_uitars15_no_reasoning_relational_query_20260109_033741.jsonl',
    'predictions_uitars15_reasoning_direct_query_20260109_033743.jsonl',
    'predictions_uitars15_reasoning_relational_query_20260109_033734.jsonl'
]
MODEL_ALL_FILES = [
    'predictions_uitars15_no_reasoning_direct_query_20260109_204302.jsonl',
    'predictions_uitars15_no_reasoning_relational_query_20260109_204303.jsonl',
    'predictions_uitars15_reasoning_direct_query_20260109_204302.jsonl',
    'predictions_uitars15_reasoning_relational_query_20260109_204305.jsonl'
]
MODEL_TEXT_SHRINK_FILES = [
    'predictions_uitars15_no_reasoning_direct_query_20260110_005249.jsonl',
    'predictions_uitars15_no_reasoning_relational_query_20260110_005246.jsonl',
    'predictions_uitars15_reasoning_direct_query_20260110_005248.jsonl',
    'predictions_uitars15_reasoning_relational_query_20260110_005244.jsonl'
]
# 25k 3-epoch files not yet available in GUI-DR
MODEL_25K_3_EPOCH_FILES = [
    'predictions_uitars15_no_reasoning_direct_query_20260108_203457.jsonl',
    'predictions_uitars15_no_reasoning_relational_query_20260108_203520.jsonl',
    'predictions_uitars15_reasoning_direct_query_20260108_203518.jsonl',
    'predictions_uitars15_reasoning_relational_query_20260108_203521.jsonl'
]

# ============================================================================
# Coordinate parsing (from notebook cells 16-17)
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


def parse_action(action_str):
    try:
        node = ast.parse(action_str, mode="eval")
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
        return {"function": func_name, "args": kwargs}
    except Exception:
        return None


def _nan_action(reflection, thought, text):
    return {
        "reflection": reflection,
        "thought": thought,
        "action_type": None,
        "action_inputs": {},
        "text": text,
    }


_SMART_H, _SMART_W = smart_resize(IMAGE_HEIGHT, IMAGE_WIDTH)


def parse_action_to_structure_output(text, row_context=None):
    try:
        text = text.strip()
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
                    float_numbers = []
                    for num_idx, num in enumerate(numbers):
                        num = float(num)
                        if (num_idx + 1) % 2 == 0:
                            float_numbers.append(round(num / _SMART_H * IMAGE_HEIGHT))
                        else:
                            float_numbers.append(round(num / _SMART_W * IMAGE_WIDTH))
                    action_inputs[param_name.strip()] = str(float_numbers)
            actions.append({
                "reflection": reflection,
                "thought": thought,
                "action_type": action_type,
                "action_inputs": action_inputs,
                "text": text,
            })
        return actions
    except Exception:
        return [_nan_action(None, None, text)]


def get_action_type_and_coordinates(row):
    structured_actions = row["structured_actions"]
    action_type = structured_actions[0]["action_type"]
    if action_type == "click":
        coordinates = structured_actions[0]["action_inputs"].get("start_box")
        if coordinates:
            coordinates = ast.literal_eval(coordinates)
        return action_type, coordinates
    return action_type, None


# ============================================================================
# Hit box accuracy (from notebook cell 19)
# ============================================================================


def is_coords_in_bbox(coords, bbox):
    if coords is None:
        return 0
    tolerance = 4
    x1, y1, w, h = ast.literal_eval(bbox) if isinstance(bbox, str) else bbox
    try:
        x, y = coords
    except Exception:
        return 0
    return int(x1 - tolerance / 2 <= x <= x1 + w + tolerance / 2 and
               y1 - tolerance / 2 <= y <= y1 + h + tolerance / 2)


def is_bbox_hit(row):
    action_type = row.get("action_type")
    pred = row.get("coordinates")
    gt_bbox = row.get("ground_truth_bbox")
    if action_type in ("click", "scroll", "type", "select"):
        return is_coords_in_bbox(pred, gt_bbox)
    if action_type in ("wait", "finished", "call_user", "hotkey"):
        return 0
    if action_type is None:
        try:
            return is_coords_in_bbox(pred, gt_bbox)
        except Exception:
            return 0
    return 0


# ============================================================================
# Metrics: MSE, NMSE, GIoU, NGIoU (from baseline notebooks)
# ============================================================================


def get_bbox_mse_and_normalized_mse(pred, gt_bbox_str):
    if pred is None:
        return np.nan, np.nan
    gt = ast.literal_eval(gt_bbox_str) if isinstance(gt_bbox_str, str) else gt_bbox_str
    x1, y1, w, h = gt
    gt_center = (x1 + w / 2, y1 + h / 2)
    try:
        x, y = pred
    except Exception:
        return np.nan, np.nan
    mse = (x - gt_center[0]) ** 2 + (y - gt_center[1]) ** 2
    diagonal_squared = w ** 2 + h ** 2
    nmse = mse / diagonal_squared if diagonal_squared > 0 else np.nan
    return mse, nmse


def giou_point_to_bbox(coords, gt_bbox_str):
    gt = ast.literal_eval(gt_bbox_str) if isinstance(gt_bbox_str, str) else gt_bbox_str
    x_gt, y_gt, w_gt, h_gt = gt

    if coords is None:
        return np.nan, np.nan
    if isinstance(coords, str):
        try:
            coords = ast.literal_eval(coords)
        except Exception:
            return np.nan, np.nan
    try:
        px, py = coords
    except (TypeError, ValueError):
        return np.nan, np.nan
    if px < 0 or px > IMAGE_WIDTH or py < 0 or py > IMAGE_HEIGHT:
        return np.nan, np.nan

    gt_box = np.array([x_gt, y_gt, x_gt + w_gt, y_gt + h_gt])
    pb = np.array([px - w_gt / 2, py - h_gt / 2, px + w_gt / 2, py + h_gt / 2])

    ix1, iy1 = np.maximum(gt_box[:2], pb[:2])
    ix2, iy2 = np.minimum(gt_box[2:], pb[2:])
    iw = np.maximum(ix2 - ix1, 0.0)
    ih = np.maximum(iy2 - iy1, 0.0)
    inter = iw * ih

    area_gt = w_gt * h_gt
    area_pb = w_gt * h_gt
    union = area_gt + area_pb - inter
    iou = inter / union if union > 0 else 0.0

    cx1, cy1 = np.minimum(gt_box[:2], pb[:2])
    cx2, cy2 = np.maximum(gt_box[2:], pb[2:])
    area_c = (cx2 - cx1) * (cy2 - cy1)

    giou = iou - (area_c - union) / area_c if area_c > 0 else 0.0
    ngiou = (giou + 1.0) / 2.0
    return giou, ngiou


# ============================================================================
# Data loading
# ============================================================================


def load_jsonl_dir(directory):
    """Load all JSONL files from a directory into a dict of {filename: DataFrame}."""
    path = Path(directory)
    if not path.exists():
        print(f"WARNING: directory does not exist: {path}", file=sys.stderr)
        return {}
    dataframes = {}
    for jsonl_file in sorted(path.glob("*.jsonl")):
        print(f"  Loading {jsonl_file.name}", file=sys.stderr)
        dataframes[jsonl_file.name] = pd.read_json(jsonl_file, lines=True)
    return dataframes


def build_model_df(dataframes, file_list, model_name):
    """Concat specific files from dataframes dict and assign model name."""
    dfs = []
    for f in file_list:
        if f in dataframes:
            dfs.append(dataframes[f])
        else:
            print(f"  WARNING: missing file {f}", file=sys.stderr)
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    df["model"] = model_name
    return df


def process_dataframe(df):
    """Apply parsing, hit_box_accuracy, and metrics to a DataFrame."""
    print(f"  Parsing structured_actions for {len(df)} rows...", file=sys.stderr)
    exception_counts = defaultdict(int)

    def parse_with_context(row):
        return parse_action_to_structure_output(
            row["raw_prediction"],
            row_context={"model": row.get("model", "unknown"), "exception_counts": exception_counts},
        )

    df["structured_actions"] = df.apply(parse_with_context, axis=1)

    print("  Extracting action_type and coordinates...", file=sys.stderr)
    df["action_type"], df["coordinates"] = zip(*df.apply(get_action_type_and_coordinates, axis=1))

    print("  Computing hit_box_accuracy...", file=sys.stderr)
    df["hit_box_accuracy"] = df.apply(is_bbox_hit, axis=1)

    print("  Computing MSE, NMSE...", file=sys.stderr)
    mse_results = df.apply(
        lambda x: get_bbox_mse_and_normalized_mse(x["coordinates"], x["ground_truth_bbox"]),
        axis=1, result_type="expand",
    )
    df["bbox_center_mse"] = mse_results[0]
    df["normalized_mse"] = mse_results[1]

    # Fill NaN MSE with 95th percentile penalty
    valid_mse = df["bbox_center_mse"].dropna()
    valid_nmse = df["normalized_mse"].dropna()
    mse_penalty = valid_mse.quantile(0.95) if len(valid_mse) > 0 else 0
    nmse_penalty = valid_nmse.quantile(0.95) if len(valid_nmse) > 0 else 0
    df["bbox_center_mse"] = df["bbox_center_mse"].fillna(mse_penalty)
    df["normalized_mse"] = df["normalized_mse"].fillna(nmse_penalty)

    print("  Computing GIoU, NGIoU...", file=sys.stderr)
    giou_results = df.apply(
        lambda x: giou_point_to_bbox(x["coordinates"], x["ground_truth_bbox"]),
        axis=1, result_type="expand",
    )
    df["giou"] = giou_results[0]
    df["ngiou"] = giou_results[1]

    # Convert structured_actions to string for CSV storage
    df["structured_actions"] = df["structured_actions"].apply(str)
    # Convert coordinates to string for CSV storage
    df["coordinates"] = df["coordinates"].apply(lambda x: str(list(x)) if isinstance(x, (list, tuple)) else x)

    return df


# ============================================================================
# Main
# ============================================================================

OUTPUT_COLUMNS = [
    "model", "use_reasoning", "query_type", "test_split", "variant",
    "task_id", "step_index", "instruction", "raw_prediction", "ground_truth_bbox",
    "image_path", "step_time_seconds", "coordinates", "hit_box_accuracy",
    "action_type", "structured_actions", "bbox_center_mse", "normalized_mse",
    "giou", "ngiou",
]


def main():
    parser = argparse.ArgumentParser(description="Generate finetuned_results_full.csv")
    parser.add_argument("--finetuned-dir",
                        default="/Users/lockewang/FIG/sca-sprint0-archive/results/final_model_all_results",
                        help="Path to directory with finetuned JSONL files (style, all, text_shrink, 25k_3_epoch)")
    parser.add_argument("--salesforce-dir",
                        default="/Users/lockewang/FIG/sca-sprint0-archive/results/exp_2_salesforce_1_epoch_results",
                        help="Path to exp_2_salesforce_1_epoch_results directory")
    parser.add_argument("--perturbed-1epoch-dir",
                        default="/Users/lockewang/FIG/sca-sprint0-archive/results/exp_2_checkpoint_1_epoch_results",
                        help="Path to exp_2_checkpoint_1_epoch_results directory")
    parser.add_argument("--baseline-dir", default=None,
                        help="Path to baseline JSONL directory (default: repo/baseline_results_full_new/baseline_results)")
    parser.add_argument("--output", default=None,
                        help="Output CSV path (default: data/finetuned_results_full.csv)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent

    # Determine output path
    output_path = Path(args.output) if args.output else repo_root / "data" / "finetuned_results_full.csv"

    # --- Load baseline uitars15 rows from JONLs with stitching ---
    baseline_dir = args.baseline_dir
    if baseline_dir is None:
        baseline_dir = str(repo_root / "baseline_results_full_new" / "baseline_results")

    all_dfs = []
    if Path(baseline_dir).exists():
        print(f"Loading baseline JONLs from: {baseline_dir}", file=sys.stderr)
        baseline_dfs = load_jsonl_dir(baseline_dir)

        # Stitching logic from notebook cell 6: replace last 92 rows of 4 uitars15 configs
        # with re-run files to fix nan relational query error at row 1625
        BASELINE_STITCH_CONFIGS = [
            ("predictions_uitars15_no_reasoning_direct_query_20251213_223027.jsonl",
             "predictions_uitars15_no_reasoning_direct_query_20251215_024416.jsonl", "replace"),
            ("predictions_uitars15_no_reasoning_relational_query_20251213_222956.jsonl",
             "predictions_uitars15_no_reasoning_relational_query_20251215_024414.jsonl", "replace"),
            ("predictions_uitars15_reasoning_direct_query_20251213_223013.jsonl",
             "predictions_uitars15_reasoning_direct_query_20251215_024415.jsonl", "replace"),
            ("predictions_uitars15_reasoning_relational_query_20251213_222938.jsonl",
             "predictions_uitars15_reasoning_relational_query_20251215_024412.jsonl", "replace"),
        ]

        df_baseline = pd.DataFrame()
        for big_name, small_name, mode in BASELINE_STITCH_CONFIGS:
            if big_name not in baseline_dfs:
                print(f"  WARNING: missing baseline file {big_name}", file=sys.stderr)
                continue
            big_df = baseline_dfs[big_name].copy()
            if small_name in baseline_dfs and mode == "replace":
                small_df = baseline_dfs[small_name].copy()
                big_df.iloc[-92:] = small_df.values
                print(f"  Stitched {big_name}: replaced last 92 rows from {small_name}", file=sys.stderr)
            df_baseline = pd.concat([df_baseline, big_df], ignore_index=True)

        df_baseline["model"] = "baseline"
        print(f"  Processing baseline ({len(df_baseline)} rows)...", file=sys.stderr)
        df_baseline = process_dataframe(df_baseline)
        all_dfs.append(df_baseline)
        print(f"  Baseline rows: {len(df_baseline)}", file=sys.stderr)
    else:
        print(f"WARNING: baseline directory not found: {baseline_dir}, skipping baseline model", file=sys.stderr)

    # --- Load finetuned JSONL files ---
    print(f"\nLoading finetuned JSONLs from: {args.finetuned_dir}", file=sys.stderr)
    finetuned_dfs = load_jsonl_dir(args.finetuned_dir)

    for file_list, model_name in [
        (MODEL_ALL_FILES, "all"),
        (MODEL_STYLE_FILES, "style"),
        (MODEL_TEXT_SHRINK_FILES, "text_shrink_zoom"),
        (MODEL_25K_3_EPOCH_FILES, "all_25k_3_epoch"),
    ]:
        print(f"\nBuilding model '{model_name}'...", file=sys.stderr)
        df = build_model_df(finetuned_dfs, file_list, model_name)
        if not df.empty:
            df = process_dataframe(df)
            all_dfs.append(df)
            print(f"  {model_name}: {len(df)} rows", file=sys.stderr)

    # --- Load salesforce 1-epoch ---
    sf_dfs = {}
    if args.salesforce_dir:
        print(f"\nLoading Salesforce 1-epoch JSONLs from: {args.salesforce_dir}", file=sys.stderr)
        sf_dfs = load_jsonl_dir(args.salesforce_dir)
    if sf_dfs:
        df_sf = pd.concat(sf_dfs.values(), ignore_index=True)
        df_sf["model"] = "25k_salesforce_1_epoch"
        print(f"  Processing 25k_salesforce_1_epoch ({len(df_sf)} rows)...", file=sys.stderr)
        df_sf = process_dataframe(df_sf)
        all_dfs.append(df_sf)

    # --- Load perturbed 1-epoch ---
    p1_dfs = {}
    if args.perturbed_1epoch_dir:
        print(f"\nLoading perturbed 1-epoch JSONLs from: {args.perturbed_1epoch_dir}", file=sys.stderr)
        p1_dfs = load_jsonl_dir(args.perturbed_1epoch_dir)
    if p1_dfs:
        df_p1 = pd.concat(p1_dfs.values(), ignore_index=True)
        df_p1["model"] = "25k_perturbed_1_epoch"
        print(f"  Processing 25k_perturbed_1_epoch ({len(df_p1)} rows)...", file=sys.stderr)
        df_p1 = process_dataframe(df_p1)
        all_dfs.append(df_p1)

    if not all_dfs:
        print("ERROR: no data loaded", file=sys.stderr)
        sys.exit(1)

    # --- Combine and output ---
    df_all = pd.concat(all_dfs, ignore_index=True)

    # Ensure all output columns exist
    for col in OUTPUT_COLUMNS:
        if col not in df_all.columns:
            df_all[col] = np.nan

    df_all = df_all[OUTPUT_COLUMNS]

    print(f"\nFinal dataset: {len(df_all)} rows, {df_all['model'].nunique()} models", file=sys.stderr)
    print(f"Models: {sorted(df_all['model'].unique())}", file=sys.stderr)
    print(f"Model counts:\n{df_all['model'].value_counts()}", file=sys.stderr)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_all.to_csv(output_path, index=False)
    print(f"\nSaved to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
