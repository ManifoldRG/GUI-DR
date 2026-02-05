import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image, ImageDraw
import ast
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go

# ============================================================================
# Configuration & Initialization
# ============================================================================

st.set_page_config(page_title="Dataset Viewer", page_icon="🖼️", layout="wide")

def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'current_index': 0,
        'filter_hash': None,
        'show_annotations': False,
        'selected_variant': None,
        'pending_variant_navigation': None,
        'last_task_id': None,
        'last_step_index': None,
        'is_variant_change': False,
        'dark_mode': False,
        'debug_mode': False  # Enable debug logging
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================================
# Debug Utilities
# ============================================================================

def debug_log(message, condition=True):
    """Log debug messages if debug mode is enabled"""
    if st.session_state.get('debug_mode', False) and condition:
        st.sidebar.text(f"🔍 {message}")

# ============================================================================
# Theme Management
# ============================================================================

# CSS Theme Constants
DARK_THEME_CSS = """
<style>
.stApp {
    background-color: #0e1117 !important;
    color: #fafafa !important;
}
.main .block-container {
    background-color: #0e1117 !important;
    color: #fafafa !important;
    padding-top: 2rem;
}
h1, h2, h3, h4, h5, h6, p {
    color: #fafafa !important;
}
.stMarkdown, .stMarkdown p {
    color: #fafafa !important;
}
.stMetric {
    background-color: #262730 !important;
    border: 1px solid #3a3b4a;
}
.stMetric label {
    color: #fafafa !important;
}
.stMetric [data-testid="stMetricValue"] {
    color: #fafafa !important;
}
.stSelectbox label, .stNumberInput label, .stCheckbox label {
    color: #fafafa !important;
}
.stSelectbox>div>div {
    background-color: #262730 !important;
    color: #fafafa !important;
}
.stNumberInput {
    background-color: #262730 !important;
}
.stNumberInput>div {
    background-color: #262730 !important;
}
.stNumberInput>div>div {
    background-color: #262730 !important;
}
.stNumberInput>div>div>input {
    background-color: #262730 !important;
    color: #fafafa !important;
}
.stNumberInput>div>div>button {
    background-color: #262730 !important;
    color: #fafafa !important;
    border: 1px solid #3a3b4a;
}
.stNumberInput input[type="number"] {
    background-color: #262730 !important;
    color: #fafafa !important;
}
.stNumberInput label {
    color: #fafafa !important;
}
div[data-baseweb="input"] {
    background-color: #262730 !important;
}
div[data-baseweb="input"] input {
    background-color: #262730 !important;
    color: #fafafa !important;
}
.stButton>button {
    background-color: #262730 !important;
    color: #fafafa !important;
    border: 1px solid #3a3b4a;
    font-weight: bold !important;
    font-size: 1em !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}
.stButton>button:hover {
    background-color: #3a3b4a !important;
}
.navigation-buttons-container .stButton>button {
    background-color: #0e1117 !important;
    color: #fafafa !important;
    border: 1px solid #3a3b4a;
    font-weight: bold !important;
    font-size: 1em !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}
.navigation-buttons-container .stButton>button:hover {
    background-color: #3a3b4a !important;
}
header[data-testid="stHeader"] {
    background-color: #0e1117 !important;
}
header[data-testid="stHeader"] > div {
    background-color: #0e1117 !important;
}
.stDeployButton {
    background-color: #262730 !important;
    color: #fafafa !important;
    border: 1px solid #3a3b4a;
}
.stDeployButton>button {
    background-color: #262730 !important;
    color: #fafafa !important;
    border: 1px solid #3a3b4a;
}
[data-testid="stHeader"] button {
    background-color: #262730 !important;
    color: #fafafa !important;
}
[data-testid="stSidebar"] {
    background-color: #0e1117 !important;
}
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] p {
    color: #fafafa !important;
}
.stExpander {
    background-color: #262730 !important;
    border: 1px solid #3a3b4a;
}
.stExpander label {
    color: #fafafa !important;
}
.stInfo {
    background-color: #1e3a5f !important;
    color: #fafafa !important;
    border: 1px solid #3a5f7f !important;
    border-radius: 4px !important;
}
.stInfo > div {
    background-color: #1e3a5f !important;
    color: #fafafa !important;
}
.stInfo p, .stInfo div {
    color: #fafafa !important;
}
.stWarning {
    background-color: #5a4a00 !important;
    color: #fafafa !important;
}
.stError {
    background-color: #5a1a1a !important;
    color: #fafafa !important;
}
.stSuccess {
    background-color: #1a5a1a !important;
    color: #fafafa !important;
}
code {
    background-color: #262730 !important;
    color: #fafafa !important;
}
</style>
"""

LIGHT_THEME_CSS = """
<style>
.navigation-buttons-container .stButton>button {
    background-color: #f0f2f6 !important;
    color: #1f1f1f !important;
    border: 1px solid #e0e0e0;
    font-weight: bold !important;
    font-size: 1em !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}
.navigation-buttons-container .stButton>button:hover {
    background-color: #e0e0e0 !important;
}
.stButton>button,
.stButton>button>div,
.stButton>button span {
    font-weight: 700 !important;
    font-size: 1em !important;
}
</style>
"""

def apply_theme():
    """Apply dark or light theme based on session state"""
    if st.session_state.dark_mode:
        st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)
    else:
        st.markdown(LIGHT_THEME_CSS, unsafe_allow_html=True)

# ============================================================================
# Data Loading & Filtering
# ============================================================================

def get_sorted_variants(df):
    """Get sorted list of variants from dataframe, excluding NaN values"""
    return sorted([x for x in df['variant'].unique().tolist() if pd.notna(x)])

def load_data():
    """Load CSV data"""
    csv_path = Path(__file__).parent / "data" / "baseline_results_full_new.csv"
    if not csv_path.exists():
        st.error(f"CSV file not found: {csv_path}")
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    # Filter out invalid interesting_cases rows (case-insensitive)
    if 'interesting_cases' in df.columns:
        df = df[df['interesting_cases'].astype(str).str.strip().str.lower() != 'invalid']
    debug_log(f"Loaded {len(df)} rows from CSV")
    return df

def apply_filters(df, model=None, query_type=None, use_reasoning=None, 
                  test_split=None, variant=None, hit_box_filter=None, interesting_cases_filter=None):
    """Apply filters to dataframe"""
    filtered = df.copy()
    
    if model:
        filtered = filtered[filtered['model'] == model]
    if query_type:
        filtered = filtered[filtered['query_type'] == query_type]
    if use_reasoning is not None:
        filtered = filtered[filtered['use_reasoning'] == use_reasoning]
    if test_split:
        filtered = filtered[filtered['test_split'] == test_split]
    if variant:
        filtered = filtered[filtered['variant'] == variant]
    
    if hit_box_filter is not None and hit_box_filter != 'All':
        hit_box_str = filtered['hit_box_accuracy'].astype(str).str.strip().str.lower()
        if hit_box_filter == 'False':
            filtered = filtered[hit_box_str == 'false']
        elif hit_box_filter == 'True':
            filtered = filtered[hit_box_str == 'true']
    
    if interesting_cases_filter is not None and interesting_cases_filter != 'All':
        if 'interesting_cases' in filtered.columns:
            # Filter by exact match (case-insensitive comparison)
            filtered = filtered[filtered['interesting_cases'].astype(str).str.strip().str.lower() == 
                               str(interesting_cases_filter).strip().lower()]
    
    result = filtered.sort_values(['task_id', 'step_index']).reset_index(drop=True)
    debug_log(f"Filtered to {len(result)} rows")
    return result

# ============================================================================
# Image Annotation
# ============================================================================

def resolve_image_path(row):
    """
    Resolve image file path from row data.
    Returns Path object if found, None otherwise.
    """
    image_path = row.get('image_path', '')
    if not image_path:
        return None
    
    if image_path.startswith('/mnt/'):
        image_path = image_path[5:]
    
    image_path_obj = Path(image_path)
    if not image_path_obj.is_absolute():
        image_dir = Path(__file__).parent / image_path_obj.parent
        if not image_dir.exists():
            image_dir = Path(image_path_obj.parent)
    else:
        image_dir = image_path_obj.parent
    
    step_idx_str = str(row.get('step_index'))
    matching_files = list(image_dir.glob(f"step_{step_idx_str}_*.png"))
    
    if len(matching_files) == 0:
        return None
    elif len(matching_files) > 1:
        st.warning(f"Multiple image files found for step {step_idx_str} in {image_dir}. Using the first one: {matching_files[0].name}")
    
    image_path_to_load = matching_files[0]
    if not image_path_to_load.exists():
        return None
    
    return image_path_to_load

def parse_coords(coord_str):
    """Parse coordinate string like '[553, 86]' to tuple"""
    if pd.isna(coord_str):
        return None
    try:
        coords = ast.literal_eval(coord_str)
        if isinstance(coords, list) and len(coords) >= 2:
            return (int(coords[0]), int(coords[1]))
    except:
        pass
    return None

def annotate_image(img, row):
    """Annotate image with GT bbox and coordinates - preserves exact pixel resolution"""
    annotated_img = img.copy()
    draw = ImageDraw.Draw(annotated_img)
    
    # Draw GT bbox with two dashed lines of different colors
    if pd.notna(row.get('ground_truth_bbox')):
        try:
            gt_bbox = ast.literal_eval(row['ground_truth_bbox'])
            if len(gt_bbox) >= 4:
                x, y, w, h = gt_bbox[0], gt_bbox[1], gt_bbox[2], gt_bbox[3]
                
                outer_color = (255, 0, 0)  # Red (outer)
                inner_color = (255, 255, 0)  # Yellow (inner)
                outer_width = 5
                inner_width = 3
                offset = 2
                dash_length = 8
                gap_length = 8
                
                # Helper to draw dashed line
                def draw_dashed_line(p1, p2, color, width):
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    dist = (dx**2 + dy**2)**0.5
                    if dist == 0: return
                    
                    num_dashes = int(dist / (dash_length + gap_length))
                    
                    for i in range(num_dashes + 1):
                        start_factor = i * (dash_length + gap_length) / dist
                        end_factor = min(1.0, (i * (dash_length + gap_length) + dash_length) / dist)
                        
                        start_point = (p1[0] + dx * start_factor, p1[1] + dy * start_factor)
                        end_point = (p1[0] + dx * end_factor, p1[1] + dy * end_factor)
                        draw.line([start_point, end_point], fill=color, width=width)

                # Draw outer dashed rectangle
                draw_dashed_line((x, y), (x + w, y), outer_color, outer_width)
                draw_dashed_line((x + w, y), (x + w, y + h), outer_color, outer_width)
                draw_dashed_line((x + w, y + h), (x, y + h), outer_color, outer_width)
                draw_dashed_line((x, y + h), (x, y), outer_color, outer_width)

                # Draw inner dashed rectangle
                x_inner, y_inner, w_inner, h_inner = x + offset, y + offset, w - 2*offset, h - 2*offset
                if w_inner > 0 and h_inner > 0:
                    draw_dashed_line((x_inner, y_inner), (x_inner + w_inner, y_inner), inner_color, inner_width)
                    draw_dashed_line((x_inner + w_inner, y_inner), (x_inner + w_inner, y_inner + h_inner), inner_color, inner_width)
                    draw_dashed_line((x_inner + w_inner, y_inner + h_inner), (x_inner, y_inner + h_inner), inner_color, inner_width)
                    draw_dashed_line((x_inner, y_inner + h_inner), (x_inner, y_inner), inner_color, inner_width)
        except Exception as e:
            debug_log(f"Error drawing bounding box: {e}")
    
    # Draw coordinates as mouse cursor icon
    coords = parse_coords(row.get('coordinates'))
    if coords:
        cx, cy = int(coords[0]), int(coords[1])
        # Draw standard mouse cursor icon (white with black outline, pointing up-left)
        # The tip of the cursor (hotspot) is at (cx, cy)
        
        # Standard mouse cursor shape: arrow pointing northwest (3x bigger)
        cursor_points = [
            (cx, cy),           # Tip (hotspot - top point)
            (cx, cy + 48),      # Bottom of shaft (16 * 3)
            (cx + 12, cy + 36), # Inner notch left (4 * 3, 12 * 3)
            (cx + 21, cy + 54), # Bottom left of tail (7 * 3, 18 * 3)
            (cx + 27, cy + 51), # Bottom right of tail (9 * 3, 17 * 3)
            (cx + 18, cy + 33), # Inner notch right (6 * 3, 11 * 3)
            (cx + 33, cy + 33), # Right edge (10 * 3)
        ]
        draw.polygon(cursor_points, fill=(255, 255, 255), outline=(0, 0, 0), width=2)
        
    return annotated_img

# ============================================================================
# Navigation Logic - Refactored
# ============================================================================

def cycle_variant(variants, current_variant):
    """Cycle to next variant in list"""
    if not variants or current_variant not in variants:
        return variants[0] if variants else None
    current_idx = variants.index(current_variant)
    next_idx = (current_idx + 1) % len(variants)
    return variants[next_idx]

def find_row_by_task_and_step(filtered_df, task_id, step_index):
    """
    Find row index in filtered_df matching task_id and step_index.
    Returns (index, row) if found, (None, None) otherwise.
    """
    if task_id is None or step_index is None or len(filtered_df) == 0:
        return None, None
    
    task_id_str = str(task_id)
    step_index_val = int(step_index) if pd.notna(step_index) else step_index
    
    matching = filtered_df[
        (filtered_df['task_id'].astype(str) == task_id_str) &
        (filtered_df['step_index'] == step_index_val)
    ]
    
    if len(matching) > 0:
        idx = matching.index[0]
        return idx, filtered_df.iloc[idx]
    return None, None

def update_current_row_state(filtered_df, index):
    """Update all current row state variables from filtered_df at index"""
    if len(filtered_df) == 0:
        return
    
    index = max(0, min(index, len(filtered_df) - 1))
    st.session_state.current_index = index
    
    if index < len(filtered_df):
        current_row = filtered_df.iloc[index]
        st.session_state.last_task_id = current_row.get('task_id')
        st.session_state.last_step_index = current_row.get('step_index')
        if 'variant' in current_row:
            st.session_state.selected_variant = current_row.get('variant')
        
        debug_log(f"State updated: task_id={st.session_state.last_task_id}, step_index={st.session_state.last_step_index}, variant={st.session_state.selected_variant}")

def handle_variant_navigation(filtered_df, target_task_id, target_step_index):
    """
    Handle variant navigation: find exact match for target task_id/step_index.
    Returns (index, found_exact_match).
    If exact match not found, returns (None, False) - DO NOT update target.
    """
    debug_log(f"Variant nav: looking for task_id={target_task_id}, step_index={target_step_index}")
    
    idx, row = find_row_by_task_and_step(filtered_df, target_task_id, target_step_index)
    
    if idx is not None:
        debug_log(f"Variant nav: Found exact match at index {idx}")
        return idx, True
    else:
        debug_log(f"Variant nav: No exact match found - keeping original target")
        return None, False

def handle_filter_change(filters, filtered_df, previous_task_id=None, previous_step_index=None):
    """
    Handle filter changes and update current_index accordingly.
    For variant changes, preserves target task_id/step_index.
    """
    current_hash = hash(filters)
    
    if st.session_state.filter_hash != current_hash:
        is_variant_change = st.session_state.is_variant_change
        
        # Determine target task_id/step_index
        task_id_to_find = previous_task_id if previous_task_id is not None else st.session_state.last_task_id
        step_index_to_find = previous_step_index if previous_step_index is not None else st.session_state.last_step_index
        
        debug_log(f"Filter change: is_variant={is_variant_change}, target=({task_id_to_find}, {step_index_to_find})")
        
        if task_id_to_find is not None and step_index_to_find is not None and len(filtered_df) > 0:
            if is_variant_change:
                # For variant changes: MUST find exact match, NEVER update target
                # The target (task_id/step_index) must remain constant across all variant changes
                idx, found = handle_variant_navigation(filtered_df, task_id_to_find, step_index_to_find)
                if found:
                    st.session_state.current_index = idx
                    # DO NOT update last_task_id/last_step_index - preserve the original target!
                    # The matched row should have the same task_id/step_index as target anyway,
                    # but we don't want to risk any drift by updating from the matched row
                    debug_log(f"Variant change: Set index to {idx}, preserving target=({task_id_to_find}, {step_index_to_find})")
                else:
                    # No exact match - keep current index if valid, but DO NOT update target
                    # This preserves the original target for next variant attempt
                    if st.session_state.current_index >= len(filtered_df):
                        st.session_state.current_index = 0
                    debug_log(f"Variant change: No exact match, keeping index {st.session_state.current_index}, preserving target=({task_id_to_find}, {step_index_to_find})")
            else:
                # For other filter changes: try to find exact match, fallback to closest
                idx, row = find_row_by_task_and_step(filtered_df, task_id_to_find, step_index_to_find)
                if idx is not None:
                    st.session_state.current_index = idx
                    update_current_row_state(filtered_df, idx)
                else:
                    # Find closest step_index within same task_id
                    same_task = filtered_df[filtered_df['task_id'].astype(str) == str(task_id_to_find)]
                    if len(same_task) > 0:
                        same_task = same_task.copy()
                        same_task['step_diff'] = abs(same_task['step_index'] - step_index_to_find)
                        closest = same_task.nsmallest(1, 'step_diff')
                        st.session_state.current_index = closest.index[0]
                        update_current_row_state(filtered_df, st.session_state.current_index)
                    else:
                        st.session_state.current_index = 0
        else:
            st.session_state.current_index = 0
        
        st.session_state.filter_hash = current_hash

# ============================================================================
# UI Components
# ============================================================================

def format_metric_value(row, col_name):
    """Format a metric value from a row for display"""
    value = row.get(col_name)
    exists = col_name in row.index
    if exists and value is not None and not pd.isna(value):
        if isinstance(value, (int, float)):
            return f"{value:.4f}" if abs(value) < 1 else f"{value:.2f}"
        else:
            return str(value)
    return "N/A"

def format_hit_box_accuracy(hit_box):
    """Format hit_box_accuracy value for display"""
    if isinstance(hit_box, bool):
        return "True" if hit_box else "False"
    elif isinstance(hit_box, (int, float)) and not pd.isna(hit_box):
        return f"{hit_box:.2f}"
    else:
        return str(hit_box)

def render_filters(df):
    """Render filter selectboxes and return selected values"""
    model = st.selectbox("Model", sorted(df['model'].unique().tolist()))
    query_type = st.selectbox("Query Type", sorted(df['query_type'].unique().tolist()))
    use_reasoning = st.selectbox("Use Reasoning", sorted(df['use_reasoning'].unique().tolist()))
    
    hit_box_filter = st.selectbox("Success", ['All', 'True', 'False'])
    
    interesting_cases_filter = 'All'
    if 'interesting_cases' in df.columns:
        unique_cases = sorted([str(x) for x in df['interesting_cases'].unique().tolist() if pd.notna(x)])
        filter_options = ['All'] + unique_cases
        interesting_cases_filter = st.selectbox("Interesting Cases", filter_options)
    
    variants = get_sorted_variants(df)
    if st.session_state.selected_variant is None or st.session_state.selected_variant not in variants:
        st.session_state.selected_variant = variants[0] if variants else None
    
    variant = st.session_state.selected_variant
    
    return model, query_type, use_reasoning, variant, hit_box_filter, interesting_cases_filter

def convert_hit_box_to_numeric(df):
    """Convert hit_box_accuracy column to numeric (0/1)"""
    df_copy = df.copy()
    if 'hit_box_accuracy' in df_copy.columns:
        df_copy['hit_box_accuracy_numeric'] = df_copy['hit_box_accuracy'].apply(
            lambda x: 1 if (isinstance(x, bool) and x) or (isinstance(x, str) and x.lower() == 'true') else 0
        )
    return df_copy

def get_plot_colors():
    """Get plot colors based on theme"""
    if st.session_state.dark_mode:
        return {
            'plot_bgcolor': '#0e1117',
            'paper_bgcolor': '#0e1117',
            'gridcolor': '#3a3b4a',
            'tickfont_color': '#fafafa'
        }
    else:
        return {
            'plot_bgcolor': '#f0f2f6',
            'paper_bgcolor': '#f0f2f6',
            'gridcolor': '#e0e0e0',
            'tickfont_color': '#1f1f1f'
        }

def render_success_rate_chart(df, model):
    """Render success rate distribution chart"""
    if 'hit_box_accuracy' not in df.columns:
        return
    
    model_df = df[df['model'] == model].copy()
    viz_df = convert_hit_box_to_numeric(model_df)
    viz_df['is_success'] = viz_df['hit_box_accuracy_numeric'].astype(bool)
    
    if not all(col in viz_df.columns for col in ['query_type', 'use_reasoning', 'variant']):
        return
    
    success_stats = viz_df.groupby(['query_type', 'use_reasoning', 'variant']).agg({
        'is_success': ['sum', 'count']
    }).reset_index()
    success_stats.columns = ['query_type', 'use_reasoning', 'variant', 'successes', 'total']
    success_stats['success_rate'] = success_stats['successes'] / success_stats['total']
    
    fig = go.Figure()
    
    variants = sorted(success_stats['variant'].unique())
    query_types = sorted(success_stats['query_type'].unique())
    reasoning_types = sorted(success_stats['use_reasoning'].unique())
    
    x_labels = []
    for query_type_val in query_types:
        for use_reasoning_val in reasoning_types:
            reasoning_abbr = "R" if use_reasoning_val else "NR"
            query_abbr = query_type_val[:8] if len(query_type_val) > 8 else query_type_val
            short_label = f"{query_abbr}\n{reasoning_abbr}"
            x_labels.append(short_label)
    
    colors = px.colors.qualitative.Set3
    colors_dict = get_plot_colors()
    
    for variant_idx, variant_val in enumerate(variants):
        y_values = []
        custom_data_list = []
        for query_type_val in query_types:
            for use_reasoning_val in reasoning_types:
                variant_data = success_stats[
                    (success_stats['query_type'] == query_type_val) &
                    (success_stats['use_reasoning'] == use_reasoning_val) &
                    (success_stats['variant'] == variant_val)
                ]
                if len(variant_data) > 0:
                    y_values.append(variant_data['success_rate'].iloc[0])
                    custom_data_list.append([
                        variant_data['successes'].iloc[0],
                        variant_data['total'].iloc[0],
                        query_type_val,
                        use_reasoning_val
                    ])
                else:
                    y_values.append(None)
                    custom_data_list.append([None, None, query_type_val, use_reasoning_val])
        
        fig.add_trace(go.Bar(
            name=variant_val,
            x=x_labels,
            y=y_values,
            marker=dict(
                color=colors[variant_idx % len(colors)],
                opacity=0.8
            ),
            hovertemplate='<b>Variant:</b> ' + variant_val + '<br>' +
                        '<b>Query Type:</b> %{customdata[2]}<br>' +
                        '<b>Use Reasoning:</b> %{customdata[3]}<br>' +
                        '<b>Success Rate:</b> %{y:.2%}<br>' +
                        '<b>Successes:</b> %{customdata[0]}/%{customdata[1]}<extra></extra>',
            customdata=custom_data_list,
            showlegend=False
        ))
    
    fig.update_layout(
        xaxis=dict(
            title='',
            tickangle=0,
            tickfont=dict(size=12, color=colors_dict['tickfont_color']),
            tickmode='linear',
            gridcolor=colors_dict['gridcolor'],
            linecolor=colors_dict['gridcolor']
        ),
        yaxis=dict(
            title='',
            range=[0, 1],
            tickformat='.0%',
            tickfont=dict(size=12, color=colors_dict['tickfont_color']),
            gridcolor=colors_dict['gridcolor'],
            linecolor=colors_dict['gridcolor']
        ),
        barmode='group',
        height=280,
        hovermode='closest',
        showlegend=False,
        margin=dict(t=10, b=80, l=0, r=10),
        plot_bgcolor=colors_dict['plot_bgcolor'],
        paper_bgcolor=colors_dict['paper_bgcolor']
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_overall_statistics(filtered_df_agg, metrics, model, query_type_flag, use_reasoning_flag, variant_flag):
    """Render overall statistics metrics"""
    st.subheader(f"**Statistics**")
    display_model = model if model is not None else 'N/A'
    display_query_type = query_type_flag if query_type_flag is not None else 'N/A'
    display_use_reasoning = use_reasoning_flag if use_reasoning_flag is not None else 'N/A'
    display_variant = variant_flag if variant_flag is not None else 'N/A'
    
    if isinstance(display_use_reasoning, bool):
        reasoning_text = "with reasoning" if display_use_reasoning else "no reasoning"
    elif isinstance(display_use_reasoning, str):
        reasoning_text = "with reasoning" if display_use_reasoning.lower() == 'true' else "no reasoning"
    else:
        reasoning_text = "no reasoning"
    
    st.markdown(f"{display_model} | {display_query_type} | {reasoning_text} | {display_variant}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if 'hit_box_accuracy' in metrics:
            hit_box_mean = filtered_df_agg['hit_box_accuracy_numeric'].mean() if 'hit_box_accuracy_numeric' in filtered_df_agg.columns else 0
            st.markdown(f"**Accuracy**")
            st.info(f"{hit_box_mean:.4f}")
            hit_box_count = filtered_df_agg['hit_box_accuracy_numeric'].sum() if 'hit_box_accuracy_numeric' in filtered_df_agg.columns else 0
            st.caption(f"({int(hit_box_count)}/{len(filtered_df_agg)})")
    
    with col2:
        if 'normalized_mse' in metrics:
            mse_mean = filtered_df_agg['normalized_mse'].mean() if pd.notna(filtered_df_agg['normalized_mse']).any() else None
            if mse_mean is not None:
                st.markdown(f"**NMSE**")
                st.info(f"{mse_mean:.4f}")
                mse_std = filtered_df_agg['normalized_mse'].std()
                st.caption(f"(σ: {mse_std:.4f})")
            else:
                st.markdown(f"**NMSE**")
                st.info("N/A")
    
    with col3:
        if 'ngiou' in metrics:
            ngiou_mean = filtered_df_agg['ngiou'].mean() if pd.notna(filtered_df_agg['ngiou']).any() else None
            if ngiou_mean is not None:
                st.markdown(f"**NGIoU**")
                st.info(f"{ngiou_mean:.4f}")
                ngiou_std = filtered_df_agg['ngiou'].std()
                st.caption(f"(σ: {ngiou_std:.4f})")
            else:
                st.markdown(f"**NGIoU**")
                st.info("N/A")

def render_statistics(df, filtered_df, model=None, query_type_flag=None, use_reasoning_flag=None, variant_flag=None):
    """Render aggregated statistics by variant and overall"""
    
    if len(filtered_df) == 0:
        st.warning("No data available for statistics.")
        return
    
    metrics = {}
    if 'hit_box_accuracy' in filtered_df.columns:
        metrics['hit_box_accuracy'] = 'Accuracy'
    if 'normalized_mse' in filtered_df.columns:
        metrics['normalized_mse'] = 'NMSE'
    if 'ngiou' in filtered_df.columns:
        metrics['ngiou'] = 'NGIoU'
    
    if not metrics:
        st.info("No metrics available for display.")
        return
    
    filtered_df_agg = convert_hit_box_to_numeric(filtered_df)
    
    # Success rate distribution visualization
    if 'hit_box_accuracy' in filtered_df_agg.columns and model is not None:
        st.markdown(f"**{model} - Success Rate Distribution**")
        render_success_rate_chart(df, model)
    
    render_overall_statistics(filtered_df_agg, metrics, model, query_type_flag, use_reasoning_flag, variant_flag)

def render_navigation_buttons(filtered_df, variants, current_row=None):
    """Render navigation buttons"""
    if len(filtered_df) == 0:
        return
    
    has_variants = len(variants) > 1
    cols = st.columns(3 if has_variants else 2)
    
    with cols[0]:
        if st.button("Prev", icon=":material/arrow_back:", width='stretch', key="prev_sample"):
            new_index = max(0, st.session_state.current_index - 1)
            update_current_row_state(filtered_df, new_index)
            # Clear variant navigation state on normal navigation
            st.session_state.is_variant_change = False
            st.rerun()
    
    if has_variants:
        with cols[1]:
            if st.button("Perturb", icon=":material/shuffle:", width='stretch', key="perturb"):
                new_variant = cycle_variant(variants, st.session_state.selected_variant)
                if new_variant:
                    # Strategy: If we have a preserved target AND we're in variant navigation mode,
                    # use the preserved target. Otherwise, use current row to set a new target.
                    # This ensures target stays constant during variant navigation sequence.
                    if (st.session_state.is_variant_change and 
                        st.session_state.last_task_id is not None and 
                        st.session_state.last_step_index is not None):
                        # Continuing variant navigation - use preserved target
                        target_task_id = st.session_state.last_task_id
                        target_step_index = st.session_state.last_step_index
                        debug_log(f"Perturb: Continuing variant nav, using preserved target=({target_task_id}, {target_step_index})")
                    else:
                        # New variant navigation - set target from current row
                        if current_row is not None:
                            target_task_id = current_row.get('task_id')
                            target_step_index = current_row.get('step_index')
                        else:
                            target_task_id = st.session_state.last_task_id
                            target_step_index = st.session_state.last_step_index
                            
                            if target_task_id is None or target_step_index is None:
                                if st.session_state.current_index < len(filtered_df):
                                    current_row_fallback = filtered_df.iloc[st.session_state.current_index]
                                    target_task_id = current_row_fallback.get('task_id')
                                    target_step_index = current_row_fallback.get('step_index')
                        debug_log(f"Perturb: New variant nav, setting target from current_row=({target_task_id}, {target_step_index})")
                    
                    debug_log(f"Perturb: final target=({target_task_id}, {target_step_index}), new_variant={new_variant}")
                    
                    if target_task_id is not None and target_step_index is not None:
                        st.session_state.pending_variant_navigation = {
                            'task_id': target_task_id,
                            'step_index': target_step_index
                        }
                        st.session_state.last_task_id = target_task_id
                        st.session_state.last_step_index = target_step_index
                        st.session_state.is_variant_change = True
                        st.session_state.selected_variant = new_variant
                        st.rerun()
        with cols[2]:
            if st.button("Next", icon=":material/arrow_forward:", width='stretch', key="next_sample"):
                new_index = min(len(filtered_df) - 1, st.session_state.current_index + 1)
                update_current_row_state(filtered_df, new_index)
                # Clear variant navigation state on normal navigation
                st.session_state.is_variant_change = False
                st.rerun()
    else:
        with cols[1]:
            if st.button("Next", icon=":material/arrow_forward:", width='stretch', key="next_sample"):
                new_index = min(len(filtered_df) - 1, st.session_state.current_index + 1)
                update_current_row_state(filtered_df, new_index)
                st.rerun()
    
    new_index = st.number_input("Go to index:", min_value=0, max_value=len(filtered_df) - 1,
                               value=st.session_state.current_index, step=1)
    if new_index != st.session_state.current_index:
        update_current_row_state(filtered_df, int(new_index))
        st.rerun()

def render_sidebar(df):
    """Render sidebar with filters, stats, and navigation"""
    with st.sidebar:
        dark_mode = st.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, key="dark_mode_toggle")
        if dark_mode != st.session_state.dark_mode:
            st.session_state.dark_mode = dark_mode
            st.rerun()
        
        st.session_state.debug_mode = st.toggle("🐛 Debug Mode", value=st.session_state.get('debug_mode', False), key="debug_toggle")
        
        st.divider()
        st.header("Evaluation Config")
        
        # Get pending variant navigation info
        previous_task_id = None
        previous_step_index = None
        has_pending_navigation = ('pending_variant_navigation' in st.session_state and 
                                  st.session_state.pending_variant_navigation is not None)
        
        if has_pending_navigation:
            nav_info = st.session_state.pending_variant_navigation
            previous_task_id = nav_info.get('task_id')
            previous_step_index = nav_info.get('step_index')
            st.session_state.last_task_id = previous_task_id
            st.session_state.last_step_index = previous_step_index
        
        model, query_type, use_reasoning, variant, hit_box_filter, interesting_cases_filter = render_filters(df)
        variants = get_sorted_variants(df)
        
        # Determine if we're in variant navigation mode
        is_variant_navigation = (st.session_state.is_variant_change or has_pending_navigation)
        
        # Clear pending navigation AFTER we've used it
        if has_pending_navigation:
            st.session_state.pending_variant_navigation = None
        
        # Bypass hit_box_accuracy filter during variant navigation
        effective_hit_box_filter = None if is_variant_navigation else hit_box_filter
        
        debug_log(f"Filtering: variant_nav={is_variant_navigation}, effective_hit_box={effective_hit_box_filter}")
        
        filtered_df = apply_filters(df, model, query_type, use_reasoning, test_split=None, 
                                   variant=variant, hit_box_filter=effective_hit_box_filter,
                                   interesting_cases_filter=interesting_cases_filter)
        
        filters = (model, query_type, use_reasoning, variant, hit_box_filter, interesting_cases_filter)
        handle_filter_change(filters, filtered_df, previous_task_id, previous_step_index)
        
        if not st.session_state.is_variant_change and len(filtered_df) > 0:
            if (st.session_state.last_task_id is None or 
                st.session_state.last_step_index is None or
                st.session_state.current_index < len(filtered_df)):
                update_current_row_state(filtered_df, st.session_state.current_index)
        
        st.divider()
        render_statistics(df, filtered_df, model=model, query_type_flag=query_type, 
                         use_reasoning_flag=use_reasoning, variant_flag=variant)
        st.divider()
        
        if len(filtered_df) == 0:
            st.warning("No samples match the filters!")
    
    return filtered_df

def render_screenshot(row, filtered_df, variants=None):
    """Render screenshot with optional annotations"""
    episode_id = row.get('task_id', 'N/A')
    step_idx = row.get('step_index', 'N/A')
    
    unique_episodes = sorted(filtered_df['task_id'].unique().tolist())
    episode_pos = unique_episodes.index(episode_id) + 1 if episode_id in unique_episodes else 1
    
    episode_steps = filtered_df[filtered_df['task_id'] == episode_id]
    step_pos_in_episode = None
    for pos, idx in enumerate(episode_steps.index):
        if idx == st.session_state.current_index:
            step_pos_in_episode = pos + 1
            break
    if step_pos_in_episode is None:
        step_pos_in_episode = step_idx + 1
    
    st.markdown(
        f"<span style='font-size: 0.9em;'>"
        f"<strong>Episode:</strong> {episode_id} ({episode_pos}/{len(unique_episodes)}) | "
        f"<strong>Step:</strong> {step_idx} (Episode: {step_pos_in_episode}/{len(episode_steps)}, All: {st.session_state.current_index + 1}/{len(filtered_df)})"
        f"</span>",
        unsafe_allow_html=True
    )
    
    st.subheader("Screenshot")
    
    show_annotations = st.checkbox("Show Prediction", 
                                  value=st.session_state.show_annotations,
                                  key="show_annotations_checkbox")
    st.session_state.show_annotations = show_annotations
    
    image_path_to_load = resolve_image_path(row)
    if image_path_to_load is None:
        st.error(f"Image not found for step {row.get('step_index')}")
        return
    
    try:
        img = Image.open(image_path_to_load)
        if show_annotations:
            img = annotate_image(img, row)
        original_width, original_height = img.size
        scaled_width = int(original_width * 1.2)
        scaled_height = int(original_height * 1.2)
        img_scaled = img.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
        st.image(img_scaled, use_container_width=False)
        
        if variants is not None:
            st.markdown('<div class="navigation-buttons-container">', unsafe_allow_html=True)
            render_navigation_buttons(filtered_df, variants, current_row=row)
            st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading image: {e}")

def render_sample_details(row, filtered_df):
    """Render sample details and metrics"""
    
    st.subheader("Variant")
    st.info(row.get('variant'))
    
    st.subheader("Instruction")
    st.info(row['instruction'])
    
    st.subheader("Raw Prediction")
    st.info(row.get('raw_prediction', 'N/A'))
    
    st.subheader("Step Metrics")
    
    pred_col1, pred_col2 = st.columns(2)
    
    with pred_col1:
        hit_box = row.get('hit_box_accuracy', 'N/A')
        display_value = format_hit_box_accuracy(hit_box)
        st.markdown("**Success**")
        st.info(display_value)
    
    mse_col1, mse_col2 = st.columns(2)
    with mse_col1:
        st.markdown("**Bbox Center MSE**")
        mse_val = format_metric_value(row, 'bbox_center_mse')
        st.info(mse_val)
    with mse_col2:
        st.markdown("**Normalized MSE**")
        nmse_val = format_metric_value(row, 'normalized_mse')
        st.info(nmse_val)
    
    giou_col1, giou_col2 = st.columns(2)
    with giou_col1:
        st.markdown("**GIoU**")
        giou_val = format_metric_value(row, 'giou')
        st.info(giou_val)
    with giou_col2:
        st.markdown("**NGIoU**")
        ngiou_val = format_metric_value(row, 'ngiou')
        st.info(ngiou_val)
    
    st.subheader("Coordinates")
    st.markdown(f"**Prediction**:")
    st.info([round(i) for i in ast.literal_eval(row.get('coordinates'))])
    st.markdown(f"**Ground Truth Bbox**:")
    st.info([round(i) for i in ast.literal_eval(row.get('ground_truth_bbox'))])
    
    with st.expander("View All Data Fields"):
        st.json(row.to_dict())

def render_main_content(filtered_df, df=None):
    """Render main content area"""
    if len(filtered_df) == 0:
        st.warning("No samples available. Please adjust your filters.")
        return
    
    if not st.session_state.is_variant_change:
        update_current_row_state(filtered_df, st.session_state.current_index)
    else:
        st.session_state.current_index = max(0, min(st.session_state.current_index, len(filtered_df) - 1))
    
    current_row = filtered_df.iloc[st.session_state.current_index].copy()
    
    if st.session_state.is_variant_change:
        current_task_id = current_row.get('task_id')
        current_step_index = current_row.get('step_index')
        target_task_id = st.session_state.last_task_id
        target_step_index = st.session_state.last_step_index
        
        debug_log(f"Main content: current=({current_task_id}, {current_step_index}), target=({target_task_id}, {target_step_index})")
        
        if current_task_id != target_task_id or current_step_index != target_step_index:
            debug_log(f"⚠️ MISMATCH: Current row doesn't match target!")
    
    st.session_state.is_variant_change = False
    
    if df is not None:
        variants = get_sorted_variants(df)
    else:
        variants = get_sorted_variants(filtered_df)
    
    col1, col2 = st.columns([4, 0.8], gap="large")
    with col1:
        render_screenshot(current_row, filtered_df, variants=variants)
    with col2:
        render_sample_details(current_row, filtered_df)

# ============================================================================
# Main Execution
# ============================================================================

apply_theme()

df = load_data()
filtered_df = render_sidebar(df)
render_main_content(filtered_df, df=df)
