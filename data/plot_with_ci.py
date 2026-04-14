"""
Standalone script: loads all data from the same sources as the notebooks,
replicates their preprocessing, and produces all plots with bootstrap CI whiskers.

Usage:
    python data/plot_with_ci.py

Produces:
    data/baseline_hit_rate_with_ci.png       — 3 baseline models
    data/finetuned_plot1_augmentation_ci.png  — baseline vs 6.5k (all/style/text_shrink)
    data/finetuned_plot2_scaling_ci.png       — baseline vs 6.5k vs 25k
    data/finetuned_plot3_real_vs_synth_ci.png — baseline vs salesforce vs perturbed
"""

import os
import re
import ast
import math
import json
import warnings
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore", category=FutureWarning)
np.random.seed(42)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

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
    'original': 'Unperturbed', 'precision': 'Precision',
    'style': 'Style', 'text_shrink': 'Text shrink'
}
METRIC_LABELS = {
    'hit_box_accuracy': 'Target Hit Rate',
    'bbox_center_mse': 'Bbox Center MSE',
    'normalized_mse': 'Normalized MSE (NMSE)',
}
CONFIG_ORDER = [
    ('direct_query', False, 'Direct query\nNo reasoning'),
    ('direct_query', True, 'Direct query\nWith reasoning'),
    ('relational_query', True, 'Relational query\nWith reasoning'),
    ('relational_query', False, 'Relational query\nNo reasoning'),
]


# ============================================================================
# HELPER FUNCTIONS (from notebooks)
# ============================================================================

def escape_single_quotes(text):
    return re.sub(r"(?<!\\)'", r"\\'", text)

def round_by_factor(number, factor):
    return round(number / factor) * factor

def ceil_by_factor(number, factor):
    return math.ceil(number / factor) * factor

def floor_by_factor(number, factor):
    return math.floor(number / factor) * factor

def smart_resize(height, width, factor=IMAGE_FACTOR, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS):
    if max(height, width) / min(height, width) > MAX_RATIO:
        raise ValueError("aspect ratio too large")
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
# PARSING (UI-TARS format — used by finetuned notebook)
# ============================================================================

def parse_action(action_str):
    try:
        node = ast.parse(action_str, mode='eval')
        if not isinstance(node, ast.Expression): raise ValueError
        call = node.body
        if not isinstance(call, ast.Call): raise ValueError
        func_name = call.func.id if isinstance(call.func, ast.Name) else (
            call.func.attr if isinstance(call.func, ast.Attribute) else None)
        kwargs = {}
        for kw in call.keywords:
            if isinstance(kw.value, ast.Constant):
                kwargs[kw.arg] = kw.value.value
            elif isinstance(kw.value, ast.Str):
                kwargs[kw.arg] = kw.value.s
            else:
                kwargs[kw.arg] = None
        return {'function': func_name, 'args': kwargs}
    except Exception:
        return None


def _nan_action(reflection, thought, text):
    return {"reflection": reflection, "thought": thought, "action_type": None,
            "action_inputs": {}, "text": text}


def parse_action_to_structure_output(text, row_context=None):
    """Finetuned notebook cell 16 parser (graceful failures)."""
    try:
        text = text.strip()
        smart_resize_height, smart_resize_width = smart_resize(
            IMAGE_HEIGHT, IMAGE_WIDTH, factor=IMAGE_FACTOR,
            min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)

        if text.startswith("Thought:"):
            thought_pattern = r"Thought: (.+?)(?=\s*Action:|$)"
        elif text.startswith("Reflection:"):
            thought_pattern = r"Reflection: (.+?)Action_Summary: (.+?)(?=\s*Action:|$)"
        elif text.startswith("Action_Summary:"):
            thought_pattern = r"Action_Summary: (.+?)(?=\s*Action:|$)"
        else:
            thought_pattern = r"Thought: (.+?)(?=\s*Action:|$)"

        reflection, thought = None, None
        m = re.search(thought_pattern, text, re.DOTALL)
        if m:
            if len(m.groups()) == 1:
                thought = m.group(1).strip()
            elif len(m.groups()) == 2:
                thought = m.group(2).strip()
                reflection = m.group(1).strip()

        if "Action:" not in text:
            return [_nan_action(reflection, thought, text)]

        action_str = text.split("Action:")[-1]
        tmp_all_action = action_str.split("\n\n")
        all_action = []
        for a in tmp_all_action:
            if "type(content" in a:
                pattern = r"type\(content='(.*?)'\)"
                content = re.sub(pattern, lambda m: m.group(1), a)
                a = "type(content='" + escape_single_quotes(content) + "')"
            all_action.append(a)

        parsed = [parse_action(a.replace("\n", "\\n").lstrip()) for a in all_action]
        actions = []
        for inst, raw in zip(parsed, all_action):
            if inst is None:
                actions.append(_nan_action(reflection, thought, text))
                continue
            action_type = inst["function"]
            params = inst["args"]
            action_inputs = {}
            for pname, pval in params.items():
                if pval == "": continue
                pval = pval.lstrip()
                action_inputs[pname.strip()] = pval
                if "start_box" in pname or "end_box" in pname:
                    nums = pval.replace("(","").replace(")","").replace("[","").replace("]","").split(",")
                    float_nums = []
                    for ni, n in enumerate(nums):
                        n = float(n)
                        if (ni + 1) % 2 == 0:
                            float_nums.append(round(n / smart_resize_height * IMAGE_HEIGHT))
                        else:
                            float_nums.append(round(n / smart_resize_width * IMAGE_WIDTH))
                    action_inputs[pname.strip()] = str(float_nums)
            actions.append({"reflection": reflection, "thought": thought,
                           "action_type": action_type, "action_inputs": action_inputs, "text": text})
        return actions
    except Exception:
        return [_nan_action(None, None, text)]


def get_action_type_and_coords(row):
    sa = row['structured_actions']
    atype = sa[0]['action_type']
    if atype == 'click':
        coords = ast.literal_eval(sa[0]['action_inputs']['start_box'])
        return atype, coords
    return atype, None


# ============================================================================
# HIT BOX ACCURACY — tolerance=0 (matches finetuned notebook cell 23 plots)
# ============================================================================

def _parse_bbox(bbox):
    if bbox is None or (isinstance(bbox, float) and pd.isna(bbox)):
        return None
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    if isinstance(bbox, str):
        try:
            out = ast.literal_eval(bbox)
            return (float(out[0]), float(out[1]), float(out[2]), float(out[3]))
        except Exception:
            return None
    return None


def _is_coords_in_bbox_strict(coords, bbox):
    """Tolerance=0 — matches finetuned notebook cell 23."""
    if coords is None or bbox is None:
        return 0
    try:
        x, y = float(coords[0]), float(coords[1])
    except (TypeError, IndexError, ValueError):
        return 0
    x1, y1, w, h = bbox
    return 1 if (x1 <= x <= x1 + w and y1 <= y <= y1 + h) else 0


def compute_hit_strict(row):
    """Recompute hit_box_accuracy with tolerance=0."""
    bbox = _parse_bbox(row.get('ground_truth_bbox'))
    coords = row.get('coordinates')
    return _is_coords_in_bbox_strict(coords, bbox)


def is_bbox_hit_baseline(row, tolerance=20):
    """Baseline notebook cell 31: tolerance=20."""
    action_type = row.get('action_type', None)
    pred = row.get('coordinates')
    gt_bbox = row.get('ground_truth_bbox')
    if pred is None:
        return 0
    try:
        if isinstance(gt_bbox, str):
            x1, y1, w, h = ast.literal_eval(gt_bbox)
        else:
            x1, y1, w, h = gt_bbox
        if isinstance(pred, (list, tuple)) and len(pred) == 4:
            x = (pred[0] + pred[2]) / 2
            y = (pred[1] + pred[3]) / 2
        else:
            x, y = pred
    except:
        return 0
    if action_type in ('wait', 'finished', 'call_user', 'hotkey'):
        return 0
    return int(x1 - tolerance/2 <= x <= x1 + w + tolerance/2 and
               y1 - tolerance/2 <= y <= y1 + h + tolerance/2)


# ============================================================================
# DATA LOADING — BASELINE (from cleaned CSV, replicates notebook cell 41+48)
# ============================================================================

def load_baseline():
    """Load baseline per-sample data with precomputed hit_box_accuracy (tolerance=20)."""
    csv_path = os.path.join(SCRIPT_DIR, 'baseline_results_full_new_cleaned.csv')
    print(f"[Baseline] Loading {csv_path}")
    df = pd.read_csv(csv_path)
    df = df[df['interesting_cases'] != 'Invalid'].copy()
    if df['hit_box_accuracy'].dtype == object:
        df['hit_box_accuracy'] = df['hit_box_accuracy'].replace(
            {'TRUE': 1, 'True': 1, True: 1, 'FALSE': 0, 'False': 0, False: 0}
        ).infer_objects(copy=False)
    df['hit_box_accuracy'] = pd.to_numeric(df['hit_box_accuracy'], errors='coerce')
    df['level'] = df['query_type'].map({'direct_query': 'L1', 'relational_query': 'L2'})
    print(f"  {len(df)} rows, models: {sorted(df['model'].unique())}")
    return df


# ============================================================================
# DATA LOADING — FINETUNED (from JSONL, replicates finetuned notebook cells 4-19)
# ============================================================================

def _load_jsonl_dir(folder):
    """Load all .jsonl files in a folder into a dict keyed by filename."""
    folder = Path(folder)
    dfs = {}
    for f in sorted(folder.glob("*.jsonl")):
        dfs[f.name] = pd.read_json(f, lines=True)
    return dfs


def load_finetuned():
    """
    Load all finetuned data + baseline (UI-TARS) from JSONL.
    Parse actions and compute hit_box_accuracy with tolerance=4 (cell 19).
    Returns (df_baseline_uitars, df_finetuned_all).
    """
    # --- Baseline UI-TARS from JSONL (cell 6) ---
    baseline_dir = "/Users/lockewang/FIG/GUI-DR/baseline_results_full_new/baseline_results"
    print(f"[Finetuned] Loading baseline JSONL from {baseline_dir}")
    baseline_dfs = _load_jsonl_dir(baseline_dir)

    # Stitch UI-TARS re-runs (cell 6)
    uitars_configs = [
        ("predictions_uitars15_no_reasoning_direct_query_20251213_223027",
         "predictions_uitars15_no_reasoning_direct_query_20251215_024416", "replace"),
        ("predictions_uitars15_no_reasoning_relational_query_20251213_222956",
         "predictions_uitars15_no_reasoning_relational_query_20251215_024414", "replace"),
        ("predictions_uitars15_reasoning_direct_query_20251213_223013",
         "predictions_uitars15_reasoning_direct_query_20251215_024415", "replace"),
        ("predictions_uitars15_reasoning_relational_query_20251213_222938",
         "predictions_uitars15_reasoning_relational_query_20251215_024412", "replace"),
    ]
    df_baseline_uitars = None
    for big_name, small_name, mode in uitars_configs:
        big = baseline_dfs[big_name + ".jsonl"].copy()
        small = baseline_dfs[small_name + ".jsonl"].copy()
        if mode == "replace":
            big.iloc[-92:] = small.values
        elif mode == "concat":
            big = pd.concat([big, small], ignore_index=True)
        if df_baseline_uitars is None:
            df_baseline_uitars = big.copy()
        else:
            df_baseline_uitars = pd.concat([df_baseline_uitars, big], ignore_index=True)
    df_baseline_uitars['model'] = 'baseline'
    print(f"  baseline (uitars15): {len(df_baseline_uitars)} rows")

    # --- Finetuned models (cell 8) ---
    ft_dir = "/Users/lockewang/FIG/sca-sprint0-archive/results/final_model_all_results"
    print(f"[Finetuned] Loading finetuned JSONL from {ft_dir}")
    ft_dfs = _load_jsonl_dir(ft_dir)

    file_groups = {
        'all': [
            'predictions_uitars15_no_reasoning_direct_query_20260109_204302.jsonl',
            'predictions_uitars15_no_reasoning_relational_query_20260109_204303.jsonl',
            'predictions_uitars15_reasoning_direct_query_20260109_204302.jsonl',
            'predictions_uitars15_reasoning_relational_query_20260109_204305.jsonl',
        ],
        'style': [
            'predictions_uitars15_no_reasoning_direct_query_20260109_033744.jsonl',
            'predictions_uitars15_no_reasoning_relational_query_20260109_033741.jsonl',
            'predictions_uitars15_reasoning_direct_query_20260109_033743.jsonl',
            'predictions_uitars15_reasoning_relational_query_20260109_033734.jsonl',
        ],
        'text_shrink_zoom': [
            'predictions_uitars15_no_reasoning_direct_query_20260110_005249.jsonl',
            'predictions_uitars15_no_reasoning_relational_query_20260110_005246.jsonl',
            'predictions_uitars15_reasoning_direct_query_20260110_005248.jsonl',
            'predictions_uitars15_reasoning_relational_query_20260110_005244.jsonl',
        ],
        'all_25k_3_epoch': [
            'predictions_uitars15_no_reasoning_direct_query_20260108_203457.jsonl',
            'predictions_uitars15_no_reasoning_relational_query_20260108_203520.jsonl',
            'predictions_uitars15_reasoning_direct_query_20260108_203518.jsonl',
            'predictions_uitars15_reasoning_relational_query_20260108_203521.jsonl',
        ],
    }
    model_dfs = []
    for model_name, files in file_groups.items():
        mdf = pd.concat([ft_dfs[f] for f in files], ignore_index=True)
        mdf['model'] = model_name
        model_dfs.append(mdf)

    # --- 25k Salesforce (cell 10) ---
    sf_dir = "/Users/lockewang/FIG/sca-sprint0-archive/results/exp_2_salesforce_1_epoch_results"
    print(f"[Finetuned] Loading Salesforce JSONL from {sf_dir}")
    sf_dfs = _load_jsonl_dir(sf_dir)
    df_sf = pd.concat(sf_dfs.values(), ignore_index=True)
    df_sf['model'] = '25k_salesforce_1_epoch'
    model_dfs.append(df_sf)

    # --- 25k Perturbed (cell 12) ---
    pt_dir = "/Users/lockewang/FIG/sca-sprint0-archive/results/exp_2_checkpoint_1_epoch_results/"
    print(f"[Finetuned] Loading Perturbed JSONL from {pt_dir}")
    pt_dfs = _load_jsonl_dir(pt_dir)
    df_pt = pd.concat(pt_dfs.values(), ignore_index=True)
    df_pt['model'] = '25k_perturbed_1_epoch'
    model_dfs.append(df_pt)

    df_all = pd.concat(model_dfs, ignore_index=True)
    print(f"  finetuned total: {len(df_all)} rows, models: {sorted(df_all['model'].unique())}")

    # --- Filter Invalid samples (same task-level labels as baseline) ---
    csv_path = os.path.join(SCRIPT_DIR, 'baseline_results_full_new_cleaned.csv')
    csv_df = pd.read_csv(csv_path)
    invalid_keys = csv_df[csv_df['interesting_cases'] == 'Invalid'][
        ['task_id', 'step_index', 'variant']].drop_duplicates()
    invalid_set = set(zip(invalid_keys['task_id'], invalid_keys['step_index'], invalid_keys['variant']))

    n_bl = len(df_baseline_uitars)
    n_ft = len(df_all)
    df_baseline_uitars = df_baseline_uitars[~df_baseline_uitars.apply(
        lambda r: (r['task_id'], r['step_index'], r['variant']) in invalid_set, axis=1)].copy()
    df_all = df_all[~df_all.apply(
        lambda r: (r['task_id'], r['step_index'], r['variant']) in invalid_set, axis=1)].copy()
    print(f"  Filtered Invalid: baseline {n_bl} -> {len(df_baseline_uitars)}, finetuned {n_ft} -> {len(df_all)}")

    # --- Parse actions + compute hit_box_accuracy (cells 16-19) ---
    print("[Finetuned] Parsing actions for all finetuned models...")
    df_all['structured_actions'] = df_all['raw_prediction'].apply(parse_action_to_structure_output)
    df_all['action_type'], df_all['coordinates'] = zip(*df_all.apply(get_action_type_and_coords, axis=1))
    df_all['hit_box_accuracy'] = df_all.apply(lambda r: is_bbox_hit_baseline(r, tolerance=4), axis=1)
    df_all['level'] = df_all['query_type'].map({'direct_query': 'L1', 'relational_query': 'L2'})

    print("[Finetuned] Parsing actions for baseline (uitars15)...")
    df_baseline_uitars['structured_actions'] = df_baseline_uitars['raw_prediction'].apply(
        parse_action_to_structure_output)
    df_baseline_uitars['action_type'], df_baseline_uitars['coordinates'] = zip(
        *df_baseline_uitars.apply(get_action_type_and_coords, axis=1))
    df_baseline_uitars['hit_box_accuracy'] = df_baseline_uitars.apply(
        lambda r: is_bbox_hit_baseline(r, tolerance=4), axis=1)
    df_baseline_uitars['level'] = df_baseline_uitars['query_type'].map(
        {'direct_query': 'L1', 'relational_query': 'L2'})

    return df_baseline_uitars, df_all


def build_finetuned_plot_datasets(df_baseline_uitars, df_all):
    """
    Build the 3 plot datasets matching finetuned notebook cell 23.
    Recomputes hit_box_accuracy with tolerance=0 for combined plots
    (matching the notebook's _metrics_row_finetuned).
    """
    cols = ['model', 'variant', 'use_reasoning', 'query_type',
            'hit_box_accuracy', 'ground_truth_bbox', 'coordinates',
            'task_id', 'step_index']

    def _ensure_cols(d):
        for c in cols:
            if c not in d.columns:
                d[c] = np.nan
        return d

    def _recompute_hit(d):
        """Recompute hit_box_accuracy with tolerance=0 (notebook cell 23 style)."""
        d = d.copy()
        d['hit_box_accuracy'] = d.apply(compute_hit_strict, axis=1)
        return d

    def _make_summary(d):
        s = d.groupby(['model', 'variant', 'use_reasoning', 'query_type']).agg(
            {'hit_box_accuracy': 'mean'}).reset_index()
        return s

    # Baseline series (recompute hit with tolerance=0)
    bl = _recompute_hit(_ensure_cols(df_baseline_uitars.copy()))
    bl_cols = [c for c in cols if c in bl.columns]

    # Plot 1: baseline vs all vs style vs text_shrink_zoom
    ft1 = _recompute_hit(_ensure_cols(
        df_all[df_all['model'].isin(['all', 'style', 'text_shrink_zoom'])].copy()))
    df_p1 = pd.concat([bl[bl_cols], ft1[bl_cols]], ignore_index=True)
    models_p1 = ['baseline', 'all', 'style', 'text_shrink_zoom']

    # Plot 2: baseline vs all vs all_25k_3_epoch
    ft2 = _recompute_hit(_ensure_cols(
        df_all[df_all['model'].isin(['all', 'all_25k_3_epoch'])].copy()))
    df_p2 = pd.concat([bl[bl_cols], ft2[bl_cols]], ignore_index=True)
    models_p2 = ['baseline', 'all', 'all_25k_3_epoch']

    # Plot 3: baseline vs 25k_salesforce vs 25k_perturbed
    ft3 = _recompute_hit(_ensure_cols(
        df_all[df_all['model'].isin(['25k_perturbed_1_epoch', '25k_salesforce_1_epoch'])].copy()))
    df_p3 = pd.concat([bl[bl_cols], ft3[bl_cols]], ignore_index=True)
    models_p3 = ['baseline', '25k_perturbed_1_epoch', '25k_salesforce_1_epoch']

    datasets = {
        'plot1': (df_p1, _make_summary(df_p1), models_p1,
                  'Hit accuracy: baseline vs 6.5k (all / style / text shrink)'),
        'plot2': (df_p2, _make_summary(df_p2), models_p2,
                  'Hit accuracy: baseline vs 6.5k vs 25k (3 epoch)'),
        'plot3': (df_p3, _make_summary(df_p3), models_p3,
                  'Hit accuracy: baseline vs 25k perturbed vs Salesforce (1 epoch)'),
    }

    for name, (per_sample, summary, models, title) in datasets.items():
        print(f"  {name}: {len(per_sample)} rows, {len(models)} models, "
              f"summary shape {summary.shape}")

    return datasets


# ============================================================================
# BOOTSTRAP CI
# ============================================================================

def _bootstrap_ci(data, n_bootstrap=10000, ci=0.95):
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)
    if n == 0:
        return 0, 0, 0
    mean = np.mean(data)
    boot = np.array([np.mean(np.random.choice(data, size=n, replace=True))
                     for _ in range(n_bootstrap)])
    alpha = 1 - ci
    return mean, np.percentile(boot, 100 * alpha / 2), np.percentile(boot, 100 * (1 - alpha / 2))


def _get_ci_for_bar(per_sample_df, model, variant, query_type, reasoning,
                    metric='hit_box_accuracy'):
    mask = ((per_sample_df['model'] == model) &
            (per_sample_df['variant'] == variant) &
            (per_sample_df['query_type'] == query_type) &
            (per_sample_df['use_reasoning'] == reasoning))
    data = per_sample_df.loc[mask, metric].values
    if len(data) == 0:
        return 0, 0, 0
    return _bootstrap_ci(data)


# ============================================================================
# PLOTTING
# ============================================================================

def plot_grouped_bars_with_ci(per_sample_df, summary_df, models, model_color_dict,
                              suptitle_text, metric='hit_box_accuracy', save_path=None):
    """
    Grouped bar plot with bootstrap CI whiskers.
    2×2 grid (one subplot per variant) × 4 config groups × N model bars.
    White background for LaTeX preprint.
    """
    np.random.seed(42)
    use_pct = (metric == 'hit_box_accuracy')

    sns.set_style("whitegrid")
    plt.rcParams.update({
        'figure.dpi': 100, 'savefig.dpi': 150, 'font.size': 18,
        'text.color': 'black', 'axes.labelcolor': 'black',
        'axes.edgecolor': 'black', 'xtick.color': 'black',
        'ytick.color': 'black', 'axes.facecolor': 'white',
        'figure.facecolor': 'white',
    })

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    # --- Font size constants (all relative to subplot title = 18) ---
    TITLE_SIZE = 24       # main plot title
    SUBTITLE_SIZE = 20    # subplot titles
    TEXT_SIZE = 18         # x-tick labels, y-tick labels
    BAR_LABEL_SIZE = 14   # bar value labels (slightly smaller to avoid overlap)
    AXIS_LABEL_SIZE = 20  # "Accuracy (%)" y-axis label
    LEGEND_SIZE = 17       # legend entries

    # Global y range
    all_vals = []
    for variant in VARIANTS:
        vdata = summary_df[summary_df['variant'] == variant]
        for _, row in vdata.iterrows():
            val = row[metric]
            if not pd.isna(val):
                all_vals.append(val * 100 if use_pct else val)
    y_min_global = 0.0
    if use_pct and all_vals:
        y_min_global = max(15, min(all_vals) - 8)
        y_min_global = (y_min_global // 5) * 5

    fig.suptitle(suptitle_text, fontsize=TITLE_SIZE, fontweight='bold', y=1.02)

    n_models = len(models)
    total_bar_span = 0.78
    width = total_bar_span / n_models
    x_pos = np.arange(len(CONFIG_ORDER))
    bar_positions = [x_pos - (n_models - 1) / 2 * width + i * width for i in range(n_models)]

    short_labels = ['Direct\nNo reas.', 'Direct\nWith reas.',
                    'Relational\nWith reas.', 'Relational\nNo reas.']

    legend_handles, legend_labels = None, None

    for variant_idx, variant in enumerate(VARIANTS):
        ax = axes[variant_idx]
        ax.set_title(VARIANT_LABELS[variant], fontsize=SUBTITLE_SIZE, fontweight='bold', pad=10)
        variant_data = summary_df[summary_df['variant'] == variant].copy()

        for model_idx, model in enumerate(models):
            vals = []
            ci_lo_list = []
            ci_hi_list = []

            for query_type, reasoning, _ in CONFIG_ORDER:
                md = variant_data[
                    (variant_data['model'] == model) &
                    (variant_data['query_type'] == query_type) &
                    (variant_data['use_reasoning'] == reasoning)]
                mean_val = md[metric].iloc[0] if len(md) > 0 and not pd.isna(md[metric].iloc[0]) else 0

                _, ci_lo, ci_hi = _get_ci_for_bar(
                    per_sample_df, model, variant, query_type, reasoning, metric)

                if use_pct:
                    vals.append(mean_val * 100)
                    ci_lo_list.append(mean_val * 100 - ci_lo * 100)
                    ci_hi_list.append(ci_hi * 100 - mean_val * 100)
                else:
                    vals.append(mean_val)
                    ci_lo_list.append(mean_val - ci_lo)
                    ci_hi_list.append(ci_hi - mean_val)

            # Reference line
            ax.axhline(y=vals[0], color=model_color_dict[model],
                       linestyle='--', alpha=0.5, linewidth=1.0, zorder=0)

            # Bars + error bars
            b = ax.bar(
                bar_positions[model_idx], vals, width,
                yerr=[ci_lo_list, ci_hi_list],
                capsize=3, error_kw={'linewidth': 1.2, 'capthick': 1.2, 'ecolor': '#555555'},
                label=model.replace('_', ' ').title(),
                color=model_color_dict[model], alpha=0.85, edgecolor='none', zorder=1)

            # Labels — stagger: even-indexed models above, odd-indexed below
            for bar, val, ci_lo_err, ci_hi_err in zip(b, vals, ci_lo_list, ci_hi_list):
                if val > 0:
                    lbl = f'{val:.1f}' if use_pct else f'{val:.3f}'
                    if model_idx % 2 == 0:
                        # Above the CI whisker
                        y_pos_lbl = val + ci_hi_err + 0.5
                        va = 'bottom'
                    else:
                        # Below the CI whisker
                        y_pos_lbl = val - ci_lo_err - 0.5
                        va = 'top'
                    ax.text(bar.get_x() + bar.get_width() / 2., y_pos_lbl,
                            lbl, ha='center', va=va,
                            fontsize=BAR_LABEL_SIZE, fontweight='bold', zorder=2)

        ax.set_xticks(x_pos)
        ax.set_xticklabels(short_labels, fontsize=TEXT_SIZE)
        ax.tick_params(axis='both', labelsize=TEXT_SIZE)
        ax.set_xlim(x_pos[0] - 0.55, x_pos[-1] + 0.55)
        ax.grid(True, alpha=0.3, linestyle='--', axis='y', zorder=0)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        if use_pct:
            ax.set_ylim(bottom=y_min_global, top=115)  # generous headroom for large labels
        else:
            ax.set_ylim(bottom=0)

        # Y-axis label only on left column
        if variant_idx % 2 == 0:
            ax.set_ylabel('Accuracy (%)' if use_pct else METRIC_LABELS.get(metric, metric),
                          fontsize=AXIS_LABEL_SIZE)

        if variant_idx == 0:
            legend_handles, legend_labels = ax.get_legend_handles_labels()

    fig.legend(legend_handles, legend_labels, ncol=n_models, fontsize=LEGEND_SIZE,
               loc='upper center', bbox_to_anchor=(0.5, 0.96), framealpha=0.95,
               edgecolor='#cccccc')
    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.90])
    plt.subplots_adjust(hspace=0.55, wspace=0.25)

    if save_path:
        plt.savefig(save_path, bbox_inches='tight', dpi=300, facecolor='white')
        print(f"  Saved: {save_path}")
    plt.close(fig)


# ============================================================================
# MAIN — run all plots
# ============================================================================

def main():
    print("=" * 70)
    print("GENERATING ALL PLOTS WITH BOOTSTRAP CI WHISKERS")
    print("=" * 70)

    # ---- PLOT 0: Baseline (3 models) ----
    print("\n--- Baseline plot ---")
    df_baseline = load_baseline()
    summary_baseline = df_baseline.groupby(
        ['model', 'variant', 'use_reasoning', 'query_type']
    ).agg({'hit_box_accuracy': 'mean'}).reset_index()
    models_bl = ['qwen25vl', 'uitars15', 'gta1']
    colors_bl = {m: sns.color_palette("pastel", n_colors=len(models_bl))[i]
                 for i, m in enumerate(models_bl)}

    plot_grouped_bars_with_ci(
        df_baseline, summary_baseline, models_bl, colors_bl,
        'Cross-Model Target Element Hit Accuracy',
        save_path=os.path.join(SCRIPT_DIR, 'baseline_hit_rate_with_ci.png'))

    # ---- PLOTS 1-3: Finetuned ----
    print("\n--- Finetuned data loading ---")
    df_ft_baseline, df_ft_all = load_finetuned()

    print("\n--- Building plot datasets (recomputing hit with tolerance=0) ---")
    datasets = build_finetuned_plot_datasets(df_ft_baseline, df_ft_all)

    filenames = {
        'plot1': 'finetuned_plot1_augmentation_ci.png',
        'plot2': 'finetuned_plot2_scaling_ci.png',
        'plot3': 'finetuned_plot3_real_vs_synth_ci.png',
    }

    for name, (per_sample, summary, models, title) in datasets.items():
        print(f"\n--- {name}: {title} ---")
        colors = {m: sns.color_palette("pastel", n_colors=len(models))[i]
                  for i, m in enumerate(models)}
        plot_grouped_bars_with_ci(
            per_sample, summary, models, colors, title,
            save_path=os.path.join(SCRIPT_DIR, filenames[name]))

    print("\n" + "=" * 70)
    print("ALL PLOTS GENERATED")
    print("=" * 70)
    print(f"Output directory: {SCRIPT_DIR}")
    for f in sorted(filenames.values()):
        print(f"  {f}")
    print(f"  baseline_hit_rate_with_ci.png")


if __name__ == '__main__':
    main()
