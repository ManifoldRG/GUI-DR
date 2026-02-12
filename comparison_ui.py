import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image, ImageDraw
import ast
import random

st.set_page_config(page_title="AI Agent Comparison", page_icon="🔬", layout="wide")

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

def annotate_image(img, row, cursor_color='white'):
    """Annotate image with GT bbox and mouse cursor at predicted coordinates"""
    annotated_img = img.copy()
    draw = ImageDraw.Draw(annotated_img)

    # Draw GT bbox with dashed lines
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
            pass

    # Draw mouse cursor at predicted coordinates
    coords = parse_coords(row.get('coordinates'))
    if coords:
        cx, cy = int(coords[0]), int(coords[1])

        # Cursor colors based on variant
        if cursor_color == 'white':
            fill_color = (255, 255, 255)
            outline_color = (0, 0, 0)
        elif cursor_color == 'blue':
            fill_color = (100, 150, 255)
            outline_color = (0, 50, 150)
        elif cursor_color == 'red':
            fill_color = (255, 100, 100)
            outline_color = (150, 0, 0)
        else:
            fill_color = (255, 255, 255)
            outline_color = (0, 0, 0)

        # Standard mouse cursor shape: arrow pointing northwest (3x scale)
        cursor_points = [
            (cx, cy),           # Tip (hotspot)
            (cx, cy + 48),      # Bottom of shaft
            (cx + 12, cy + 36), # Inner notch left
            (cx + 21, cy + 54), # Bottom left of tail
            (cx + 27, cy + 51), # Bottom right of tail
            (cx + 18, cy + 33), # Inner notch right
            (cx + 33, cy + 33), # Right edge
        ]
        draw.polygon(cursor_points, fill=fill_color, outline=outline_color, width=2)

    return annotated_img

def display_comparison(original_row, variant_row, variant_name):
    """Display side-by-side comparison with prediction overlays"""
    col1, col2 = st.columns(2)

    with col1:

        # Display image with annotations
        img_path = resolve_image_path(original_row)
        if img_path and img_path.exists():
            img = Image.open(img_path)
            # Add annotations (ground truth bbox + mouse cursor)
            img_annotated = annotate_image(img, original_row, cursor_color='white')
            # Display at full resolution by default
            st.image(img_annotated, use_container_width=False)
        else:
            st.info("Image not available")

        # Display metrics
        success = "✅ SUCCESS" if original_row['success'] else "❌ FAILED"
        if original_row['success']:
            st.success(success)
        else:
            st.error(success)

        col1_1, col1_2, col1_3 = st.columns(3)
        with col1_1:
            st.metric("MSE", f"{original_row['bbox_center_mse']:.1f}", help="Mean Squared Error between predicted click coordinates and target bounding box center. Lower is better.")
        with col1_2:
            if pd.notna(original_row.get('coordinates')):
                try:
                    coords = ast.literal_eval(original_row['coordinates'])
                    st.metric("Coordinates", f"({coords[0]:.0f}, {coords[1]:.0f})")
                except:
                    st.metric("Coordinates", "N/A")
        with col1_3:
            if pd.notna(original_row.get('action_type')):
                st.metric("Action", original_row['action_type'].title())

        # Show raw prediction in expander
        if pd.notna(original_row.get('raw_prediction')):
            formatted_pred = format_raw_prediction(original_row['raw_prediction'])
            if formatted_pred:
                with st.expander("🔍 Raw Prediction"):
                    st.code(formatted_pred, language="text")

    with col2:
        # Display image with annotations
        img_path = resolve_image_path(variant_row)
        if img_path and img_path.exists():
            img = Image.open(img_path)
            # Add annotations (ground truth bbox + mouse cursor)
            img_annotated = annotate_image(img, variant_row, cursor_color='red')
            # Display at full resolution by default
            st.image(img_annotated, use_container_width=False)
        else:
            st.info("Image not available")

        # Display metrics
        success = "✅ SUCCESS" if variant_row['success'] else "❌ FAILED"
        if variant_row['success']:
            st.success(success)
        else:
            st.error(success)

        col2_1, col2_2, col2_3 = st.columns(3)
        with col2_1:
            mse_delta = variant_row['bbox_center_mse'] - original_row['bbox_center_mse']
            # Lower MSE is better, so use "inverse" to make decreases green and increases red
            st.metric("MSE",
                     f"{variant_row['bbox_center_mse']:.1f}",
                     f"{mse_delta:+.1f}",
                     delta_color="inverse",
                     help="Mean Squared Error between predicted click coordinates and target bounding box center. Lower is better. Delta shows change from original.")
        with col2_2:
            if pd.notna(variant_row.get('coordinates')):
                try:
                    coords = ast.literal_eval(variant_row['coordinates'])
                    st.metric("Coordinates", f"({coords[0]:.0f}, {coords[1]:.0f})")
                except:
                    st.metric("Coordinates", "N/A")
        with col2_3:
            if pd.notna(variant_row.get('action_type')):
                st.metric("Action", variant_row['action_type'].title())

        # Show raw prediction in expander
        if pd.notna(variant_row.get('raw_prediction')):
            formatted_pred = format_raw_prediction(variant_row['raw_prediction'])
            if formatted_pred:
                with st.expander("🔍 Raw Prediction"):
                    st.code(formatted_pred, language="text")

def main():
    st.title("🔬 Original vs Perturbation Comparison")
    st.markdown("Compare how UI modifications affect AI agent performance")

    df = load_data()
    if df.empty:
        st.error("No data found")
        return

    # Sidebar controls
    st.sidebar.header("🎯 Comparison Settings")

    # Model filter
    models = sorted(df['model'].unique().tolist())
    selected_model = st.sidebar.selectbox(
        "Model",
        models,
        help="Select the AI model to analyze"
    )

    # Query type filter
    query_types = sorted(df['query_type'].unique().tolist())
    selected_query_type = st.sidebar.selectbox(
        "Query Type",
        query_types,
        format_func=lambda x: x.replace('_', ' ').title(),
        help="Filter by query type: Direct Query (simple element targeting) vs Relational Query (spatial/contextual reasoning)"
    )

    # Use reasoning filter
    use_reasoning_options = sorted(df['use_reasoning'].unique().tolist())
    selected_use_reasoning = st.sidebar.selectbox(
        "Use Reasoning",
        use_reasoning_options,
        format_func=lambda x: "Yes" if x else "No",
        help="Filter by whether chain-of-thought reasoning was used"
    )

    # Success filter
    success_filter = st.sidebar.selectbox(
        "Success",
        ['All', 'True', 'False'],
        help="Filter by prediction success (whether click coordinates hit the target bounding box)"
    )

    # Apply base filters BEFORE building task list
    df = df[
        (df['model'] == selected_model) &
        (df['query_type'] == selected_query_type) &
        (df['use_reasoning'] == selected_use_reasoning)
    ]

    # Store success filter value - will be applied to ORIGINAL variant only when building samples
    success_filter_value = None if success_filter == 'All' else (success_filter == 'True')

    # Initialize session state for navigation
    if 'current_sample_index' not in st.session_state:
        st.session_state.current_sample_index = 0

    # Store current task/step to preserve position when switching variants
    if 'current_task_id' not in st.session_state:
        st.session_state.current_task_id = None
    if 'current_step_index' not in st.session_state:
        st.session_state.current_step_index = None

    # Default perturbation for initial filtering
    perturbation_variants = ['precision', 'style', 'text_shrink']

    # Initialize selected_variant in session state if not exists
    if 'selected_variant' not in st.session_state:
        st.session_state.selected_variant = perturbation_variants[0]

    # Track if variant changed (to know when to preserve position)
    if 'previous_variant' not in st.session_state:
        st.session_state.previous_variant = st.session_state.selected_variant

    # Get all samples (task_id, step_index combinations) that have both original and selected perturbation
    available_samples = []
    for task_id in df['task_id'].unique():
        for step_idx in df[df['task_id'] == task_id]['step_index'].unique():
            sample_data = df[(df['task_id'] == task_id) & (df['step_index'] == step_idx)]
            variants = set(sample_data['variant'].values)

            # Check if we have both original and the selected perturbation
            if 'original' in variants and st.session_state.selected_variant in variants:
                # Apply success filter to ORIGINAL only (so switching variants doesn't change the sample list)
                original_row = sample_data[sample_data['variant'] == 'original'].iloc[0]
                if success_filter_value is not None and original_row['success'] != success_filter_value:
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

    # Ensure current index is valid
    if st.session_state.current_sample_index >= len(available_samples):
        st.session_state.current_sample_index = 0

    current_sample = available_samples[st.session_state.current_sample_index]

    # Store current task/step for next rerun
    st.session_state.current_task_id = current_sample['task_id']
    st.session_state.current_step_index = current_sample['step_index']

    # Navigation controls
    st.markdown("### 🔍 Sample Navigation")

    st.markdown(f"<div style='text-align: center; padding: 0.5rem;'><strong>Sample {st.session_state.current_sample_index + 1} of {len(available_samples)}</strong></div>", unsafe_allow_html=True)

    col1, col2 = st.columns([4, 1])

    with col1:
        # Jump to specific sample
        sample_input = st.number_input(
            "Jump to sample:",
            min_value=1,
            max_value=len(available_samples),
            value=st.session_state.current_sample_index + 1,
            key=f"jump_to_sample_{len(available_samples)}",
            label_visibility="collapsed"
        )
        # Update index if changed
        if sample_input - 1 != st.session_state.current_sample_index:
            st.session_state.current_sample_index = sample_input - 1

    with col2:
        # Randomize button - sets a flag that triggers randomization
        def trigger_randomize():
            st.session_state.randomize_requested = True

        st.button("🎲 Randomize", use_container_width=True, on_click=trigger_randomize, key="randomize_btn")

    # Handle randomize request (done after available_samples is built, so length is correct)
    if st.session_state.get('randomize_requested', False):
        st.session_state.current_sample_index = random.randint(0, len(available_samples) - 1)
        st.session_state.randomize_requested = False
        # Update stored task/step for the new random sample
        new_sample = available_samples[st.session_state.current_sample_index]
        st.session_state.current_task_id = new_sample['task_id']
        st.session_state.current_step_index = new_sample['step_index']
        st.rerun()

    st.divider()

    # Sample info
    st.markdown(f"### 📋 Task Instruction")
    st.markdown(f"<div style='text-align: center;'><span style='display: inline-block; padding: 0.5rem 1rem; background-color: rgba(33, 195, 228, 0.1); border-radius: 0.5rem; font-size: 1.25rem;'><strong>{current_sample['instruction']}</strong></span></div>", unsafe_allow_html=True)

    # Layout with headers
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔵 Original")

    with col2:
        # Perturbation selector above the image
        selected_variant = st.selectbox(
            "🔴 Select Perturbation",
            perturbation_variants,
            index=perturbation_variants.index(st.session_state.selected_variant),
            format_func=lambda x: x.replace('_', ' ').title(),
            help="""**Precision**: Viewport zoom (70% scale), tests precision with zoomed interfaces

**Style**: Visual randomization (colors, fonts, borders, shadows)

**Text Shrink**: Font size reduced 20%, tests readability with dense text"""
        )

        # Update session state if changed
        if selected_variant != st.session_state.selected_variant:
            st.session_state.selected_variant = selected_variant
            st.rerun()

    # Get the specific rows for current sample
    sample_data = df[
        (df['task_id'] == current_sample['task_id']) &
        (df['step_index'] == current_sample['step_index'])
    ]

    original_data = sample_data[sample_data['variant'] == 'original']
    variant_data = sample_data[sample_data['variant'] == st.session_state.selected_variant]

    if original_data.empty or variant_data.empty:
        st.error(f"Missing variant data for this sample")
        return

    original_row = original_data.iloc[0]
    variant_row = variant_data.iloc[0]

    # Display comparison
    display_comparison(original_row, variant_row, st.session_state.selected_variant)


if __name__ == "__main__":
    main()