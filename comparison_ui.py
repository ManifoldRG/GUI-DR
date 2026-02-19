import base64
import io
import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image, ImageDraw
import ast
import random


TECHNICAL_REPORT_1_LINK = "https://fig.inc/"
TECHNICAL_REPORT_2_LINK = "https://fig.inc/"
TECHNICAL_REPORT_3_LINK = "https://fig.inc/"
CODE_LINK = "https://fig.inc/"
DATA_LINK = "https://fig.inc/"
FIG_LINK = "https://fig.inc/"
MANIFOLDRG_LINK = "https://www.manifoldrg.com/"

MEDIA_DIR = Path(__file__).parent / "media"
LOGO_SIZE_PX = 48  # same width and height for both sidebar logos

def _logo_data_uri(filename):
    """Return data URI for a logo under media/ for use in HTML img src."""
    path = MEDIA_DIR / filename
    if not path.exists():
        return None
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    return f"data:image/png;base64,{b64}"

def _pil_image_to_data_uri(img):
    """Return data URI for a PIL Image for HTML embedding with fixed dimensions (no distortion)."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"

st.set_page_config(page_title="GUI Perturbation Evaluation Viewer", page_icon="🔬", layout="wide")

# Font and style consistent with reference page (Geist, Open Sans, Comfortaa; #23283c on #f2f2f2)
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600&family=Comfortaa&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/geist@1.3.0/dist/geist.css">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">
<style>
    /* Base typography and background (match reference page) */
    body, .main, [data-testid="stAppViewContainer"] {
        color: #23283c !important;
        line-height: 1.5em !important;
        font-weight: 400 !important;
        font-size: 1.25rem !important;
        font-family: 'Geist', 'Open Sans', Arial, sans-serif !important;
        background-color: #f2f2f2 !important;
    }
    .block-container {
        padding-top: 3.5rem;
        padding-bottom: 2rem;
        color: #23283c !important;
        font-family: 'Geist', 'Open Sans', Arial, sans-serif !important;
        background-color: #f2f2f2 !important;
    }
    /* Prevent main title from being cut off when scrolled to top */
    [data-testid="stAppViewContainer"] {
        padding-top: 0.5rem;
    }
    .block-container > div:first-child {
        margin-top: 0.5rem;
    }
    /* Constrain comparison images and layout so 100% zoom fits in view */
    div[data-testid="column"] img {
        max-width: 100% !important;
        height: auto !important;
        max-height: min(65vh, 600px) !important;
        object-fit: contain !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #f2f2f2 !important;
        color: #23283c !important;
        font-family: 'Geist', 'Open Sans', Arial, sans-serif !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0.5rem;
    }
    section[data-testid="stSidebar"] hr {
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
    }
    /* Keep header visible so sidebar toggle (keyboard_double_arrow) button is shown */
    header[data-testid="stHeader"] {
        background-color: #f2f2f2 !important;
    }
    /* Expander titles: use normal text font (not icon font) so "GTA1", "Success Filter..." look good */
    [data-testid="stExpander"] summary {
        font-family: 'Open Sans', Arial, sans-serif !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        white-space: normal !important;
        word-break: break-word !important;
        overflow: visible !important;
    }
    /* Only the expander arrow icon uses the icon font */
    [data-testid="stExpander"] summary > span:first-child,
    [data-testid="stExpander"] summary [class*="icon"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', system-ui, sans-serif !important;
    }
    /* Sidebar expander: prevent label cut-off, allow wrap */
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
        font-size: 0.95rem !important;
        min-width: 0 !important;
    }
    /* Header/sidebar toggle: icon font for the button icon only */
    header [role="button"],
    header [role="button"] *,
    header button,
    header button *,
    button[data-testid="baseButton-header"],
    button[data-testid="baseButton-header"] * {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', system-ui, sans-serif !important;
    }
    /* Text content only (exclude icon containers so expander/sidebar icons still render) */
    .block-container > p, .block-container > div .stMarkdown p,
    .stMarkdown p, .stCaption,
    label[data-testid="stWidgetLabel"] {
        color: #23283c !important;
        font-family: 'Geist', 'Open Sans', Arial, sans-serif !important;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    """Load and clean data"""
    csv_path = Path(__file__).parent / "data" / "baseline_results_full_new.csv"
    if not csv_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(csv_path)
    df = df[df['interesting_cases'] != 'Invalid']
    df['success'] = df['hit_box_accuracy'].apply(
        lambda x: True if (isinstance(x, bool) and x) or (isinstance(x, str) and x.lower() == 'true') else False
    )
    return df

def resolve_image_path(row):
    """Get image path for a row - improved to find variant-specific images"""
    image_path = row.get('image_path', '')
    if not image_path or pd.isna(image_path):
        return None

    # Strip /mnt/ prefix if present
    if image_path.startswith('/mnt/'):
        image_path = image_path[5:]

    image_path_obj = Path(image_path)
    if not image_path_obj.is_absolute():
        image_dir = Path(__file__).parent / image_path_obj.parent
    else:
        image_dir = image_path_obj.parent

    step_idx = str(row.get('step_index'))
    variant = row.get('variant', '')

    # Try to find variant-specific image first
    variant_patterns = [
        f"step_{step_idx}_{variant}_*.png",
        f"step_{step_idx}_*{variant}*.png",
        f"*{variant}*step_{step_idx}*.png",
        f"step_{step_idx}_*.png"  # Fallback to any step image
    ]

    for pattern in variant_patterns:
        matching_files = list(image_dir.glob(pattern))
        if matching_files:
            return matching_files[0]

    # If no files found, try the exact path
    exact_path = Path(__file__).parent / image_path
    if exact_path.exists():
        return exact_path

    return None

def format_raw_prediction(raw_pred):
    """Format raw prediction for display - show entire raw prediction as-is"""
    if pd.isna(raw_pred):
        return None

    # Return the raw prediction exactly as it is in the CSV
    return str(raw_pred)

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

# Solid cursor colors: black, white, orange; semi-transparent so overlapping cursors stay visible
CONTRAST_OUTLINE = (50, 50, 50)
CURSOR_ALPHA = 180  # 0–255; lower = more see-through where cursors overlap
MODEL_STYLES = {
    'gta1': {'color': (0, 0, 0), 'label': 'GTA1'},
    'qwen25vl': {'color': (255, 255, 255), 'label': 'Qwen2.5VL'},
    'uitars15': {'color': (255, 165, 0), 'label': 'UI-TARS-1.5'},
}

def _arrow_points(scale):
    """Arrow shape with tip at origin, pointing down-right. Returns list of (dx, dy)."""
    s = scale
    return [
        (0, 0),
        (0, 48 * s),
        (12 * s, 36 * s),
        (21 * s, 54 * s),
        (27 * s, 51 * s),
        (18 * s, 33 * s),
        (33 * s, 33 * s),
    ]

def _draw_cursor_arrow(draw, cx, cy, fill_color, scale=1.0, outline_color=None):
    """Draw arrow cursor with tip at (cx, cy). fill_color/outline_color can be (r,g,b) or (r,g,b,a)."""
    pts_rel = _arrow_points(scale)
    pts_int = [(int(cx + x), int(cy + y)) for x, y in pts_rel]
    outline = outline_color if outline_color is not None else CONTRAST_OUTLINE
    draw.polygon(pts_int, fill=fill_color, outline=outline, width=max(1, int(2 * scale)))

def draw_model_prediction(draw, coords, model, scale=1.0, alpha=255):
    """Draw a model's prediction as solid arrow cursor. Use alpha < 255 for see-through overlap."""
    if not coords:
        return

    cx, cy = int(coords[0]), int(coords[1])
    style = MODEL_STYLES.get(model, {'color': (180, 180, 180), 'label': model})
    color = style.get('color', (180, 180, 180))
    fill_rgba = (*color, alpha)
    outline_rgba = (*CONTRAST_OUTLINE, 255)
    _draw_cursor_arrow(draw, cx, cy, fill_rgba, scale, outline_rgba)

def make_cursor_legend_image(selected_models, width=460, height=64):
    """Create a horizontal legend: cursor + label per model, no overlap or clipping."""
    img = Image.new("RGB", (width, height), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    legend_scale = 0.4 * (height / 64)  # scale down when height is smaller
    cursor_w = int(33 * legend_scale) + 10
    x_start = int(24 * width / 460)
    x_step = max(60, int(width / 3.5))  # fit all models in width
    y_center = height // 2
    cursor_cy = y_center - 10
    for i, model in enumerate(selected_models):
        style = MODEL_STYLES.get(model, {'color': (180, 180, 180), 'label': model})
        color = style.get('color', (180, 180, 180))
        label = style.get('label', model)
        cx = x_start + i * x_step
        cy = cursor_cy
        _draw_cursor_arrow(draw, cx, cy, color, legend_scale)
        # Label to the right of cursor so it doesn't overlap
        text_x = cx + cursor_w
        text_y = y_center - 6
        try:
            from PIL import ImageFont
            font_size = max(8, int(13 * height / 64))
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except Exception:
            font = None
        if font:
            draw.text((text_x, text_y), label, fill=(50, 50, 50), font=font)
        else:
            draw.text((text_x, text_y), label, fill=(50, 50, 50))
    return img

def annotate_image_multi_model(img, rows_by_model, selected_models):
    """Annotate image with GT bbox and predictions from multiple models. Cursors are semi-transparent."""
    annotated_img = img.copy().convert("RGBA")
    draw = ImageDraw.Draw(annotated_img)

    # Draw GT bbox from first available row
    first_row = next(iter(rows_by_model.values()), None)
    if first_row is not None and pd.notna(first_row.get('ground_truth_bbox')):
        try:
            gt_bbox = ast.literal_eval(first_row['ground_truth_bbox'])
            if len(gt_bbox) >= 4:
                x, y, w, h = gt_bbox[0], gt_bbox[1], gt_bbox[2], gt_bbox[3]

                outer_color = (255, 0, 0)  # Red (outer)
                inner_color = (255, 255, 0)  # Yellow (inner)
                outer_width = 5
                inner_width = 3
                offset = 2
                dash_length = 8
                gap_length = 8

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

                draw_dashed_line((x, y), (x + w, y), outer_color, outer_width)
                draw_dashed_line((x + w, y), (x + w, y + h), outer_color, outer_width)
                draw_dashed_line((x + w, y + h), (x, y + h), outer_color, outer_width)
                draw_dashed_line((x, y + h), (x, y), outer_color, outer_width)

                x_inner, y_inner, w_inner, h_inner = x + offset, y + offset, w - 2*offset, h - 2*offset
                if w_inner > 0 and h_inner > 0:
                    draw_dashed_line((x_inner, y_inner), (x_inner + w_inner, y_inner), inner_color, inner_width)
                    draw_dashed_line((x_inner + w_inner, y_inner), (x_inner + w_inner, y_inner + h_inner), inner_color, inner_width)
                    draw_dashed_line((x_inner + w_inner, y_inner + h_inner), (x_inner, y_inner + h_inner), inner_color, inner_width)
                    draw_dashed_line((x_inner, y_inner + h_inner), (x_inner, y_inner), inner_color, inner_width)
        except Exception:
            pass

    # Draw predictions for each selected model
    for model in selected_models:
        if model in rows_by_model:
            row = rows_by_model[model]
            coords = parse_coords(row.get('coordinates'))
            draw_model_prediction(draw, coords, model, alpha=CURSOR_ALPHA)

    return annotated_img

def display_comparison_multi_model(original_rows_by_model, variant_rows_by_model, selected_models, variant_name):
    """Display side-by-side comparison with predictions from multiple models"""
    # Add CSS for visual divider between columns
    st.markdown("""
    <style>
    div[data-testid="column"]:first-child {
        border-right: 3px solid rgba(128, 128, 128, 0.3);
        padding-right: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    first_original = next(iter(original_rows_by_model.values()), None)
    first_variant = next(iter(variant_rows_by_model.values()), None)

    # Row 1: titles and images (same height row so cards below align)
    with col1:
        st.markdown("#### Original")
        if first_original is not None:
            img_path = resolve_image_path(first_original)
            if img_path and img_path.exists():
                img = Image.open(img_path)
                img_annotated = annotate_image_multi_model(img, original_rows_by_model, selected_models)
                st.image(img_annotated, use_container_width=True)
            else:
                st.info("Image not available")
        else:
            st.info("Image not available")

    with col2:
        st.markdown(f"#### Perturbed ({variant_name.replace('_', ' ').title()})")
        if first_variant is not None:
            img_path = resolve_image_path(first_variant)
            if img_path and img_path.exists():
                img = Image.open(img_path)
                img_annotated = annotate_image_multi_model(img, variant_rows_by_model, selected_models)
                st.image(img_annotated, use_container_width=True)
            else:
                st.info("Image not available")
        else:
            st.info("Image not available")

    # One row per model so Original and Perturbed cards align horizontally
    for model in selected_models:
        style = MODEL_STYLES.get(model, {'label': model})
        label = style.get('label', model)
        orig_row = original_rows_by_model.get(model)
        var_row = variant_rows_by_model.get(model)

        left_col, right_col = st.columns(2)
        with left_col:
            with st.expander(f"📊 {label}", expanded=True):
                if orig_row is not None:
                    row = orig_row
                    cols = st.columns(3)
                    with cols[0]:
                        st.metric("MSE", f"{row['bbox_center_mse']:.1f}")
                    with cols[1]:
                        if pd.notna(row.get('coordinates')):
                            try:
                                coords = ast.literal_eval(row['coordinates'])
                                st.metric("Coords", f"({coords[0]:.0f}, {coords[1]:.0f})")
                            except:
                                st.metric("Coords", "N/A")
                    with cols[2]:
                        st.metric("Success", "✅" if row['success'] else "❌")
                    if pd.notna(row.get('raw_prediction')):
                        formatted_pred = format_raw_prediction(row['raw_prediction'])
                        if formatted_pred:
                            st.code(formatted_pred, language="text")
                else:
                    st.caption("No original data for this model")

        with right_col:
            with st.expander(f"📊 {label}", expanded=True):
                if var_row is not None:
                    row = var_row
                    cols = st.columns(3)
                    with cols[0]:
                        mse_val = f"{row['bbox_center_mse']:.1f}"
                        if orig_row is not None:
                            mse_delta = row['bbox_center_mse'] - orig_row['bbox_center_mse']
                            mse_left, mse_right = st.columns([2, 1])
                            with mse_left:
                                st.metric("MSE", mse_val)
                            with mse_right:
                                st.markdown(" ")  # align delta with value row
                                arrow = "↑" if mse_delta > 0 else "↓" if mse_delta < 0 else ""
                                color = "red" if mse_delta > 0 else "green" if mse_delta < 0 else "gray"
                                st.markdown(f"<span style='color: {color}; font-weight: 600;'>{arrow} {mse_delta:+.1f}</span>", unsafe_allow_html=True)
                        else:
                            st.metric("MSE", mse_val)
                    with cols[1]:
                        if pd.notna(row.get('coordinates')):
                            try:
                                coords = ast.literal_eval(row['coordinates'])
                                st.metric("Coords", f"({coords[0]:.0f}, {coords[1]:.0f})")
                            except:
                                st.metric("Coords", "N/A")
                    with cols[2]:
                        st.metric("Success", "✅" if row['success'] else "❌")
                    if pd.notna(row.get('raw_prediction')):
                        formatted_pred = format_raw_prediction(row['raw_prediction'])
                        if formatted_pred:
                            st.code(formatted_pred, language="text")
                else:
                    st.caption("No perturbed data for this model")

def main():
    # Compact header with less vertical space
    st.markdown("## 🔬 GUI Perturbation Evaluation Result Viewer ")
    st.markdown("---")
    df = load_data()
    if df.empty:
        st.error("No data found")
        return

    # Create placeholders for sidebar sections in desired order (logos first = top of sidebar)
    logos_placeholder = st.sidebar.container()
    nav_placeholder = st.sidebar.container()
    models_placeholder = st.sidebar.container()
    perturbation_placeholder = st.sidebar.container()
    filters_placeholder = st.sidebar.container()

    # Render filters section (will appear at bottom due to placeholder order)
    with filters_placeholder:
        # Query type filter
        query_types = sorted(df['query_type'].unique().tolist())
        selected_query_type = st.selectbox(
            "Query Type",
            query_types,
            key="query_type_filter",
            format_func=lambda x: x.replace('_', ' ').title(),
            help="Filter by query type: Direct Query (simple element targeting) vs Relational Query (spatial/contextual reasoning)"
        )

        # Use reasoning filter
        use_reasoning_options = sorted(df['use_reasoning'].unique().tolist())
        selected_use_reasoning = st.selectbox(
            "Use Reasoning",
            use_reasoning_options,
            key="use_reasoning_filter",
            format_func=lambda x: "Yes" if x else "No",
            help="Filter by whether chain-of-thought reasoning was used"
        )

    # Apply base filters (without model filter - we'll show all models)
    df_filtered = df[
        (df['query_type'] == selected_query_type) &
        (df['use_reasoning'] == selected_use_reasoning)
    ]

    # Get available models from data
    all_models = sorted(df_filtered['model'].unique().tolist())

    # Initialize model selection in session state
    if 'selected_models' not in st.session_state:
        st.session_state.selected_models = {model: True for model in all_models}

    # Ensure all models have entries (in case new models appear)
    for model in all_models:
        if model not in st.session_state.selected_models:
            st.session_state.selected_models[model] = True

    # Render models section
    with models_placeholder:
        st.markdown("---")
        st.markdown("**🤖 Models to Display**")

        selected_models = []
        for model in all_models:
            style = MODEL_STYLES.get(model, {'label': model})
            label = style.get('label', model)
            checkbox_label = label

            if st.checkbox(checkbox_label, value=st.session_state.selected_models.get(model, True), key=f"model_{model}"):
                selected_models.append(model)
                st.session_state.selected_models[model] = True
            else:
                st.session_state.selected_models[model] = False

    if not selected_models:
        st.error("Please select at least one model")
        return

    # Per-model success filters - only for selected models
    with filters_placeholder:
        # Initialize per-model success filter in session state
        if 'model_success_filter' not in st.session_state:
            st.session_state.model_success_filter = {model: 'All' for model in all_models}

        # Ensure all models have entries
        for model in all_models:
            if model not in st.session_state.model_success_filter:
                st.session_state.model_success_filter[model] = 'All'

        model_success_filters = {}
        with st.expander("**Success Filter (per model)**", expanded=True):
            for model in selected_models:  # Only show filters for selected models
                style = MODEL_STYLES.get(model, {'label': model})
                label = style.get('label', model)
                model_success_filters[model] = st.selectbox(
                    label,
                    ['All', 'Success', 'Failure'],
                    index=['All', 'Success', 'Failure'].index(st.session_state.model_success_filter.get(model, 'All')),
                    key=f"success_filter_{model}",
                    help=f"Filter by {label}'s prediction success on original"
                )
                st.session_state.model_success_filter[model] = model_success_filters[model]

    # Default perturbation for initial filtering
    perturbation_variants = ['precision', 'style', 'text_shrink']

    # Initialize selected_variant in session state if not exists
    if 'selected_variant' not in st.session_state:
        st.session_state.selected_variant = perturbation_variants[0]

    # Render perturbation section
    with perturbation_placeholder:
        st.markdown("---")
        st.markdown("**Perturbation Type**")
        selected_variant = st.selectbox(
            "Select Perturbation",
            perturbation_variants,
            index=perturbation_variants.index(st.session_state.selected_variant),
            format_func=lambda x: x.replace('_', ' ').title(),
            label_visibility="collapsed",
            help="""**Precision**: Viewport zoom (70% scale), tests precision with zoomed interfaces

**Style**: Visual randomization (colors, fonts, borders, shadows)

**Text Shrink**: Font size reduced 20%, tests readability with dense text"""
        )

    # Update session state if changed
    if selected_variant != st.session_state.selected_variant:
        st.session_state.selected_variant = selected_variant
        st.rerun()

    # Track if variant changed (to know when to preserve position)
    if 'previous_variant' not in st.session_state:
        st.session_state.previous_variant = st.session_state.selected_variant

    # Initialize session state for navigation
    if 'current_sample_index' not in st.session_state:
        st.session_state.current_sample_index = 0

    # Store current task/step to preserve position when switching variants
    if 'current_task_id' not in st.session_state:
        st.session_state.current_task_id = None
    if 'current_step_index' not in st.session_state:
        st.session_state.current_step_index = None

    # Get all samples (task_id, step_index combinations) that have both original and selected perturbation
    # across ALL models (not filtered by model selection)
    available_samples = []
    for task_id in df_filtered['task_id'].unique():
        for step_idx in df_filtered[df_filtered['task_id'] == task_id]['step_index'].unique():
            sample_data = df_filtered[(df_filtered['task_id'] == task_id) & (df_filtered['step_index'] == step_idx)]
            variants = set(sample_data['variant'].values)

            # Check if we have both original and the selected perturbation
            if 'original' in variants and st.session_state.selected_variant in variants:
                original_rows = sample_data[sample_data['variant'] == 'original']
                if original_rows.empty:
                    continue

                # Apply per-model success filters on ORIGINAL variant
                passes_filter = True
                for model in all_models:
                    filter_val = model_success_filters.get(model, 'All')
                    if filter_val == 'All':
                        continue

                    model_original = original_rows[original_rows['model'] == model]
                    if model_original.empty:
                        continue

                    model_success = model_original.iloc[0]['success']
                    if filter_val == 'Success' and not model_success:
                        passes_filter = False
                        break
                    elif filter_val == 'Failure' and model_success:
                        passes_filter = False
                        break

                if not passes_filter:
                    continue

                instruction = sample_data.iloc[0]['instruction']
                available_samples.append({
                    'task_id': task_id,
                    'step_index': step_idx,
                    'instruction': instruction
                })

    if not available_samples:
        st.error(f"No samples found with both original and {st.session_state.selected_variant} perturbation")
        return

    # Try to preserve current task/step position ONLY when variant changes
    variant_changed = st.session_state.previous_variant != st.session_state.selected_variant
    if variant_changed and st.session_state.current_task_id is not None and st.session_state.current_step_index is not None:
        # Find the index of the current task/step in the new available_samples list
        for idx, sample in enumerate(available_samples):
            if (sample['task_id'] == st.session_state.current_task_id and
                sample['step_index'] == st.session_state.current_step_index):
                st.session_state.current_sample_index = idx
                break
        else:
            # If current task/step not found in new list, reset to 0
            st.session_state.current_sample_index = 0
        # Update previous_variant after handling
        st.session_state.previous_variant = st.session_state.selected_variant

    # Store available samples count in session state for callbacks
    st.session_state.num_available_samples = len(available_samples)

    # Ensure current index is valid
    if st.session_state.current_sample_index >= len(available_samples):
        st.session_state.current_sample_index = 0

    current_sample = available_samples[st.session_state.current_sample_index]

    # Store current task/step for next rerun
    st.session_state.current_task_id = current_sample['task_id']
    st.session_state.current_step_index = current_sample['step_index']

    # Initialize sample_nav_input if not exists
    if 'sample_nav_input' not in st.session_state:
        st.session_state.sample_nav_input = st.session_state.current_sample_index + 1

    # Callback for sample input change
    def on_sample_change():
        new_val = st.session_state.sample_nav_input
        if new_val - 1 != st.session_state.current_sample_index:
            st.session_state.current_sample_index = new_val - 1

    # Callback for randomize button
    def on_randomize():
        max_idx = st.session_state.num_available_samples - 1
        new_idx = random.randint(0, max_idx)
        st.session_state.current_sample_index = new_idx
        st.session_state.sample_nav_input = new_idx + 1

    # Callback for reset button
    def on_reset():
        # Reset navigation
        st.session_state.current_sample_index = 0
        st.session_state.sample_nav_input = 1
        st.session_state.current_task_id = None
        st.session_state.current_step_index = None
        # Reset model selections to all checked
        for model in all_models:
            st.session_state.selected_models[model] = True
            # Also reset the checkbox widget state
            if f"model_{model}" in st.session_state:
                st.session_state[f"model_{model}"] = True
        # Reset success filters to 'All'
        for model in all_models:
            st.session_state.model_success_filter[model] = 'All'
            # Also reset the selectbox widget state
            if f"success_filter_{model}" in st.session_state:
                st.session_state[f"success_filter_{model}"] = 'All'
        # Reset perturbation to first option
        st.session_state.selected_variant = 'precision'
        st.session_state.previous_variant = 'precision'
        # Reset query type and use reasoning filters to first option
        if 'query_type_filter' in st.session_state:
            st.session_state.query_type_filter = query_types[0]
        if 'use_reasoning_filter' in st.session_state:
            st.session_state.use_reasoning_filter = use_reasoning_options[0]

    # Logos and links at top of sidebar (above Sample Navigation) — two logos horizontal, text under each
    with logos_placeholder:
        fig_uri = _logo_data_uri("fig-logo.png")
        manifold_uri = _logo_data_uri("manifoldrg-logo.png")
        logo_style = f"width: {LOGO_SIZE_PX}px; height: {LOGO_SIZE_PX}px; object-fit: contain; display: block; margin: 0 auto;"
        wrap_style = "display: flex; flex-direction: column; align-items: center; text-align: center; gap: 0.25rem;"
        logo_col1, logo_col2 = st.columns(2)
        with logo_col1:
            if fig_uri:
                st.markdown(
                    '<div style="' + wrap_style + '"><a href="' + FIG_LINK + '" target="_blank" rel="noopener" title="fig.ai"><img src="' + fig_uri + '" style="' + logo_style + '"/></a><a href="' + FIG_LINK + '" target="_blank" rel="noopener" style="font-size: 0.85rem; color: rgb(128, 128, 128); text-decoration: none;">fig.ai</a></div>',
                    unsafe_allow_html=True,
                )
        with logo_col2:
            if manifold_uri:
                st.markdown(
                    '<div style="' + wrap_style + '"><a href="' + MANIFOLDRG_LINK + '" target="_blank" rel="noopener" title="manifold research"><img src="' + manifold_uri + '" style="' + logo_style + '"/></a><a href="' + MANIFOLDRG_LINK + '" target="_blank" rel="noopener" style="font-size: 0.85rem; color: rgb(128, 128, 128); text-decoration: none;">manifold research</a></div>',
                    unsafe_allow_html=True,
                )
        st.markdown("")
        st.markdown("---")
        # Technical reports in a column (vertical)

        # Code, Data, Technical report in a row
        link_col1, link_col2, link_col3 = st.columns(3)
        with link_col1:
            st.markdown(f"[Technical report 1]({TECHNICAL_REPORT_1_LINK})")
            st.markdown(f"[Code]({CODE_LINK})")
        with link_col2:
            st.markdown(f"[Technical report 2]({TECHNICAL_REPORT_2_LINK})")
            st.markdown(f"[Data]({DATA_LINK})")
        with link_col3:
            st.markdown(f"[Technical report 3]({TECHNICAL_REPORT_3_LINK})")
        st.markdown("---")

    # Now fill in the navigation placeholder
    with nav_placeholder:
        st.markdown("**🔍 Sample Navigation**")
        st.markdown(f"Sample **{st.session_state.current_sample_index + 1}** of **{len(available_samples)}**")

        # Jump to specific sample (no value param - uses session state key)
        st.number_input(
            "Jump to sample:",
            min_value=1,
            max_value=len(available_samples),
            key="sample_nav_input",
            label_visibility="collapsed",
            on_change=on_sample_change
        )

        # Randomize button
        st.button("🎲 Random sample", use_container_width=True, key="randomize_btn", on_click=on_randomize)

    # Reset button at the bottom of sidebar
    st.sidebar.markdown("---")
    st.sidebar.button("🔄 Reset All", use_container_width=True, key="reset_btn", on_click=on_reset)

    # Task instruction (full width)
    
    instr_col, legend_col = st.columns([2, 1])
    with instr_col:
        st.markdown(f"<div style='text-align: left;'><span style='font-size: 1.5rem;'>📋 Task Instruction:</span> <span style='display: inline-block; padding: 0.5rem 1rem; background-color: rgba(33, 195, 228, 0.1); border-radius: 0.5rem; font-size: 1.5rem;'><strong>{current_sample['instruction']}</strong></span></div>", unsafe_allow_html=True)
    with legend_col:
        # Model prediction cursor legend — right-aligned, fixed dimensions so image is never distorted
        legend_w, legend_h = 460, 64
        legend_img = make_cursor_legend_image(selected_models, width=legend_w, height=legend_h)
        legend_uri = _pil_image_to_data_uri(legend_img)
        st.markdown(
            f"<div style='text-align: right; margin-top: 0.5rem;'>"
            f"<p style='font-size: 1.4rem; color: rgb(128, 128, 128); margin-bottom: 0.5rem;'>Model predictions</p>"
            f"<img src='{legend_uri}' width='{legend_w}' height='{legend_h}' style='display: block; margin-left: auto;' />"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Get the specific rows for current sample across all selected models
    sample_data = df_filtered[
        (df_filtered['task_id'] == current_sample['task_id']) &
        (df_filtered['step_index'] == current_sample['step_index'])
    ]

    # Build rows by model for original and variant
    original_rows_by_model = {}
    variant_rows_by_model = {}

    for model in selected_models:
        model_data = sample_data[sample_data['model'] == model]
        original_data = model_data[model_data['variant'] == 'original']
        variant_data = model_data[model_data['variant'] == st.session_state.selected_variant]

        if not original_data.empty:
            original_rows_by_model[model] = original_data.iloc[0]
        if not variant_data.empty:
            variant_rows_by_model[model] = variant_data.iloc[0]

    if not original_rows_by_model and not variant_rows_by_model:
        st.error(f"No data for selected models on this sample")
        return

    # Display comparison with multi-model support
    display_comparison_multi_model(original_rows_by_model, variant_rows_by_model, selected_models, st.session_state.selected_variant)


if __name__ == "__main__":
    main()