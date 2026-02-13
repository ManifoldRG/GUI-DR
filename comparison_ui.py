import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image, ImageDraw
import ast
import random

st.set_page_config(page_title="UI Perturbations Demo", page_icon="🔬", layout="wide")

# Reduce top padding
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    header[data-testid="stHeader"] {
        display: none;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0.5rem;
    }
    section[data-testid="stSidebar"] hr {
        margin-top: 0.5rem;
        margin-bottom: 0.5rem;
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

# Model colors and symbols for multi-model display
MODEL_STYLES = {
    'gta1': {'color': (0, 150, 255), 'outline': (0, 50, 150), 'symbol': 'cursor', 'label': 'GTA1'},
    'qwen25vl': {'color': (50, 205, 50), 'outline': (0, 100, 0), 'symbol': 'diamond', 'label': 'Qwen2.5VL'},
    'uitars15': {'color': (255, 165, 0), 'outline': (200, 100, 0), 'symbol': 'triangle', 'label': 'UI-TARS-1.5'},
}

def draw_model_prediction(draw, coords, model, scale=1.0):
    """Draw a model's prediction with its unique symbol"""
    if not coords:
        return

    cx, cy = int(coords[0]), int(coords[1])
    style = MODEL_STYLES.get(model, {'color': (255, 255, 255), 'outline': (0, 0, 0), 'symbol': 'cursor'})
    fill_color = style['color']
    outline_color = style['outline']
    symbol = style['symbol']

    if symbol == 'cursor':
        # Mouse cursor shape
        cursor_points = [
            (cx, cy),
            (cx, cy + 48),
            (cx + 12, cy + 36),
            (cx + 21, cy + 54),
            (cx + 27, cy + 51),
            (cx + 18, cy + 33),
            (cx + 33, cy + 33),
        ]
        draw.polygon(cursor_points, fill=fill_color, outline=outline_color, width=2)
    elif symbol == 'diamond':
        # Diamond shape
        size = 20
        diamond_points = [
            (cx, cy - size),      # Top
            (cx + size, cy),      # Right
            (cx, cy + size),      # Bottom
            (cx - size, cy),      # Left
        ]
        draw.polygon(diamond_points, fill=fill_color, outline=outline_color, width=3)
        # Draw crosshair inside
        draw.line([(cx - size//2, cy), (cx + size//2, cy)], fill=outline_color, width=2)
        draw.line([(cx, cy - size//2), (cx, cy + size//2)], fill=outline_color, width=2)
    elif symbol == 'triangle':
        # Triangle pointing down
        size = 22
        triangle_points = [
            (cx, cy + size),      # Bottom point
            (cx - size, cy - size//2),  # Top left
            (cx + size, cy - size//2),  # Top right
        ]
        draw.polygon(triangle_points, fill=fill_color, outline=outline_color, width=3)

def annotate_image_multi_model(img, rows_by_model, selected_models):
    """Annotate image with GT bbox and predictions from multiple models"""
    annotated_img = img.copy()
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
            draw_model_prediction(draw, coords, model)

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

    # Get first available row for image path
    first_original = next(iter(original_rows_by_model.values()), None)
    first_variant = next(iter(variant_rows_by_model.values()), None)

    with col1:
        st.markdown("#### 🔵 Original")

        # Display image with multi-model annotations
        if first_original is not None:
            img_path = resolve_image_path(first_original)
            if img_path and img_path.exists():
                img = Image.open(img_path)
                img_annotated = annotate_image_multi_model(img, original_rows_by_model, selected_models)
                st.image(img_annotated, use_container_width=False)
            else:
                st.info("Image not available")

        # Show metrics and raw predictions for each selected model
        for model in selected_models:
            if model in original_rows_by_model:
                row = original_rows_by_model[model]
                style = MODEL_STYLES.get(model, {})
                label = style.get('label', model)

                with st.expander(f"📊 {label}", expanded=True):
                    success = "✅ SUCCESS" if row['success'] else "❌ FAILED"
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
                        st.metric("Status", "✅" if row['success'] else "❌")

                    if pd.notna(row.get('raw_prediction')):
                        formatted_pred = format_raw_prediction(row['raw_prediction'])
                        if formatted_pred:
                            st.code(formatted_pred, language="text")

    with col2:
        st.markdown(f"#### 🔴 Perturbed ({variant_name.replace('_', ' ').title()})")

        # Display image with multi-model annotations
        if first_variant is not None:
            img_path = resolve_image_path(first_variant)
            if img_path and img_path.exists():
                img = Image.open(img_path)
                img_annotated = annotate_image_multi_model(img, variant_rows_by_model, selected_models)
                st.image(img_annotated, use_container_width=False)
            else:
                st.info("Image not available")

        # Show metrics and raw predictions for each selected model
        for model in selected_models:
            if model in variant_rows_by_model:
                row = variant_rows_by_model[model]
                orig_row = original_rows_by_model.get(model)
                style = MODEL_STYLES.get(model, {})
                label = style.get('label', model)

                with st.expander(f"📊 {label}", expanded=True):
                    cols = st.columns(3)
                    with cols[0]:
                        if orig_row is not None:
                            mse_delta = row['bbox_center_mse'] - orig_row['bbox_center_mse']
                            st.metric("MSE", f"{row['bbox_center_mse']:.1f}", f"{mse_delta:+.1f}", delta_color="inverse")
                        else:
                            st.metric("MSE", f"{row['bbox_center_mse']:.1f}")
                    with cols[1]:
                        if pd.notna(row.get('coordinates')):
                            try:
                                coords = ast.literal_eval(row['coordinates'])
                                st.metric("Coords", f"({coords[0]:.0f}, {coords[1]:.0f})")
                            except:
                                st.metric("Coords", "N/A")
                    with cols[2]:
                        st.metric("Status", "✅" if row['success'] else "❌")

                    if pd.notna(row.get('raw_prediction')):
                        formatted_pred = format_raw_prediction(row['raw_prediction'])
                        if formatted_pred:
                            st.code(formatted_pred, language="text")

def main():
    # Compact header with less vertical space
    st.markdown("### 🔬 Original vs Perturbation Comparison")

    df = load_data()
    if df.empty:
        st.error("No data found")
        return

    # Create placeholders for sidebar sections in desired order
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

    # Symbol legend for models
    model_symbols = {
        'gta1': '🔵',
        'qwen25vl': '🟢',
        'uitars15': '🟠',
    }

    # Render models section
    with models_placeholder:
        st.markdown("---")
        st.markdown("**🤖 Models to Display**")

        selected_models = []
        for model in all_models:
            style = MODEL_STYLES.get(model, {'label': model})
            label = style.get('label', model)
            symbol = model_symbols.get(model, '⚪')
            checkbox_label = f"{symbol} {label}"

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
                symbol = model_symbols.get(model, '⚪')
                model_success_filters[model] = st.selectbox(
                    f"{symbol} {label}",
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
        st.markdown("**🔴 Perturbation Type**")
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

    # Now fill in the navigation placeholder at the top of sidebar
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
        st.button("🎲 Randomize", use_container_width=True, key="randomize_btn", on_click=on_randomize)

    # Reset button at the bottom of sidebar
    st.sidebar.markdown("---")
    st.sidebar.button("🔄 Reset All", use_container_width=True, key="reset_btn", on_click=on_reset)

    # Sample info
    st.markdown(f"<div style='text-align: left;'><span style='font-size: 1.5rem;'>📋 Task Instruction:</span> <span style='display: inline-block; padding: 0.5rem 1rem; background-color: rgba(33, 195, 228, 0.1); border-radius: 0.5rem; font-size: 1.5rem;'><strong>{current_sample['instruction']}</strong></span></div>", unsafe_allow_html=True)

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