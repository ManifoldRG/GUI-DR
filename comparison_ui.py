import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image, ImageDraw
import ast
import json
import re

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

def resolve_image_path(row, debug_mode=False):
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
            # Debug: print what we found
            if debug_mode:
                st.caption(f"🔍 Found {len(matching_files)} files for pattern '{pattern}': {[f.name for f in matching_files[:3]]}")
            return matching_files[0]

    # If no files found, try the exact path
    exact_path = Path(__file__).parent / image_path
    if exact_path.exists():
        return exact_path

    return None

def format_raw_prediction(raw_pred):
    """Format raw prediction for display"""
    if pd.isna(raw_pred):
        return None
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

def display_comparison(original_row, variant_row, variant_name, debug_mode=False):
    """Display side-by-side comparison with prediction overlays"""
    col1, col2 = st.columns(2)

    # Debug info
    if debug_mode:
        st.caption(f"🔍 Original variant: {original_row.get('variant', 'unknown')}, Perturbation: {variant_row.get('variant', 'unknown')}")
        st.caption(f"📁 Image paths - Original: {original_row.get('image_path', 'N/A')[:50]}... | Perturbation: {variant_row.get('image_path', 'N/A')[:50]}...")

    with col1:

        # Display image with annotations
        img_path = resolve_image_path(original_row, debug_mode)
        if img_path and img_path.exists():
            img = Image.open(img_path)
            # Add annotations (ground truth bbox + mouse cursor)
            img_annotated = annotate_image(img, original_row, cursor_color='white')
            # Display at full resolution by default
            st.image(img_annotated, use_container_width=False)
        else:
            st.info("Image not available")
            st.caption(f"❌ Path: {img_path}")

        # Display metrics
        success = "✅ SUCCESS" if original_row['success'] else "❌ FAILED"
        if original_row['success']:
            st.success(success)
        else:
            st.error(success)

        col1_1, col1_2, col1_3 = st.columns(3)
        with col1_1:
            st.metric("Prediction Error", f"{original_row['bbox_center_mse']:.1f}", help="Mean Squared Error (MSE) between predicted click coordinates and target bounding box center. Lower is better.")
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

        # Show raw prediction in debug mode
        if debug_mode and pd.notna(original_row.get('raw_prediction')):
            formatted_pred = format_raw_prediction(original_row['raw_prediction'])
            if formatted_pred:
                with st.expander("🔍 Raw Prediction"):
                    st.code(formatted_pred, language="text")

    with col2:
        # Display image with annotations
        img_path = resolve_image_path(variant_row, debug_mode)
        if img_path and img_path.exists():
            img = Image.open(img_path)
            # Add annotations (ground truth bbox + mouse cursor)
            img_annotated = annotate_image(img, variant_row, cursor_color='red')
            # Display at full resolution by default
            st.image(img_annotated, use_container_width=False)
        else:
            st.info("Image not available")
            st.caption(f"❌ Path: {img_path}")

        # Display metrics
        success = "✅ SUCCESS" if variant_row['success'] else "❌ FAILED"
        if variant_row['success']:
            st.success(success)
        else:
            st.error(success)

        col2_1, col2_2, col2_3 = st.columns(3)
        with col2_1:
            mse_delta = variant_row['bbox_center_mse'] - original_row['bbox_center_mse']
            # Higher MSE is worse, so positive delta should be red (bad)
            delta_color = "inverse" if mse_delta > 0 else "normal"
            st.metric("Prediction Error",
                     f"{variant_row['bbox_center_mse']:.1f}",
                     f"{mse_delta:+.1f}",
                     delta_color=delta_color,
                     help="Mean Squared Error (MSE) between predicted click coordinates and target bounding box center. Lower is better. Delta shows change from original.")
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

        # Show raw prediction in debug mode
        if debug_mode and pd.notna(variant_row.get('raw_prediction')):
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

    # Test split filter
    test_splits = sorted(df['test_split'].unique().tolist())
    selected_test_split = st.sidebar.selectbox(
        "Test Split",
        test_splits,
        format_func=lambda x: x.replace('_', ' ').title(),
        help="Select the test split: domain-based vs task-based vs website-based test sets"
    )

    # Success filter
    success_filter = st.sidebar.selectbox(
        "Success",
        ['All', 'True', 'False'],
        help="Filter by prediction success (whether click coordinates hit the target bounding box)"
    )

    # Debug mode toggle
    debug_mode = st.sidebar.checkbox("🔍 Debug Mode", value=False, help="Show technical debug information")

    # Apply filters BEFORE building task list
    df = df[
        (df['model'] == selected_model) &
        (df['query_type'] == selected_query_type) &
        (df['use_reasoning'] == selected_use_reasoning) &
        (df['test_split'] == selected_test_split)
    ]

    # Apply success filter if not 'All'
    if success_filter != 'All':
        df = df[df['success'] == (success_filter == 'True')]

    # Default perturbation for initial filtering
    perturbation_variants = ['precision', 'style', 'text_shrink']
    default_variant = 'precision'

    # Get tasks that have both original and any perturbation variant (from filtered data)
    available_tasks = []
    for task_id in df['task_id'].unique():
        for step_idx in df[df['task_id'] == task_id]['step_index'].unique():
            task_data = df[(df['task_id'] == task_id) & (df['step_index'] == step_idx)]
            variants = set(task_data['variant'].values)

            # Check if we have original and at least one perturbation variant
            if 'original' in variants and any(v in variants for v in perturbation_variants):
                instruction = task_data.iloc[0]['instruction']
                available_tasks.append({
                    'task_id': task_id,
                    'step_index': step_idx,
                    'instruction': instruction,
                    'display': f"Task {len(available_tasks)+1}: {instruction[:50]}...",
                    'available_variants': list(variants)
                })

    if not available_tasks:
        st.error("No tasks found with both original and selected perturbation")
        return

    # Task selector
    task_options = [task['display'] for task in available_tasks]
    selected_task_idx = st.sidebar.selectbox(
        "Select Task",
        range(len(task_options)),
        format_func=lambda i: task_options[i]
    )

    selected_task = available_tasks[selected_task_idx]

    # Show comparison
    st.divider()

    # Task info
    st.markdown(f"### 📋 Task Instruction")
    st.info(f"**{selected_task['instruction']}**")
    st.caption("Note: Each step represents a different stage in executing this task. Steps may share the same instruction but have different UI states.")

    # Step selector - show all available steps for this task that have both original and perturbation data
    task_id = selected_task['task_id']

    # Get steps that have both original and at least one perturbation variant
    available_steps = []
    for step in df[df['task_id'] == task_id]['step_index'].unique():
        step_data = df[(df['task_id'] == task_id) & (df['step_index'] == step)]
        variants = set(step_data['variant'].values)
        if 'original' in variants and any(v in variants for v in perturbation_variants):
            available_steps.append(step)

    available_steps = sorted(available_steps)

    # Debug info about step availability
    if debug_mode:
        all_steps = sorted(df[df['task_id'] == task_id]['step_index'].unique())
        st.caption(f"🔍 Debug: All steps for this task: {all_steps}")
        st.caption(f"🔍 Debug: Steps with both original + perturbation: {available_steps}")

    # Timeline Navigation Bar - Draggable Slider
    st.markdown("### 📊 Step Timeline")

    if len(available_steps) > 1:
        # Default to the task's original step if available, otherwise first available step
        default_step = available_steps[0]
        if selected_task['step_index'] in available_steps:
            default_step = selected_task['step_index']

        # Track current task to detect task changes
        if 'current_task_id' not in st.session_state or st.session_state.current_task_id != task_id:
            st.session_state.current_task_id = task_id
            default_step = available_steps[0]

        # Create a draggable slider for step navigation with actual step numbers
        selected_step = st.select_slider(
            "Drag to navigate through steps",
            options=available_steps,
            value=default_step,
            key=f"step_slider_{task_id}",
            label_visibility="collapsed",
            help="Each step represents a different stage in the task execution. Drag to navigate through the available steps for this task."
        )

        # Show step info below slider
        selected_index = available_steps.index(selected_step)
        step_labels = " → ".join([f"**Step {s}**" if i == selected_index else f"Step {s}"
                                   for i, s in enumerate(available_steps)])
        st.markdown(step_labels)
        st.caption(f"Task ID: {task_id[:8]}... | Currently viewing: Step {selected_step} ({selected_index + 1} of {len(available_steps)} available steps)")
    else:
        selected_step = available_steps[0] if available_steps else selected_task['step_index']
        st.caption(f"Task ID: {task_id[:8]}... | Step: {selected_step} (only available step)")

    # Layout with perturbation selector above right image
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔵 Original")

    with col2:
        # Perturbation selector directly above the perturbed image
        available_variants_for_task = [v for v in perturbation_variants if v in selected_task['available_variants']]

        if not available_variants_for_task:
            st.error("No perturbation variants available for this task")
            return

        selected_variant = st.selectbox(
            "🔴 Select Perturbation",
            available_variants_for_task,
            format_func=lambda x: x.replace('_', ' ').title()
        )

    # Get the specific rows for selected step
    task_data = df[
        (df['task_id'] == selected_task['task_id']) &
        (df['step_index'] == selected_step)
    ]

    if task_data.empty:
        st.error(f"No data found for Task {selected_task['task_id'][:8]}... Step {selected_step}")
        return

    original_data = task_data[task_data['variant'] == 'original']
    variant_data = task_data[task_data['variant'] == selected_variant]

    if original_data.empty or variant_data.empty:
        st.error(f"Missing variant data for this step. Available variants: {list(task_data['variant'].unique())}")
        return

    original_row = original_data.iloc[0]
    variant_row = variant_data.iloc[0]

    # Display comparison
    display_comparison(original_row, variant_row, selected_variant, debug_mode)

    # Add legend below the images
    st.divider()
    st.markdown("### 📖 Perturbation Legend")

    legend_col1, legend_col2, legend_col3 = st.columns(3)

    with legend_col1:
        st.markdown("""
        **🎯 Precision (Type 1 - Viewport Zoom)**
        - Fixed viewport zoom (default 0.7 = 70% scale)
        - CSS transform scale from top-left origin
        - Body enlarged to maintain layout proportions
        - Tests AI precision with zoomed-out interfaces
        """)

    with legend_col2:
        st.markdown("""
        **🎨 Style (Type 3 - Visual Randomization)**
        - Random design style (neobrutalism, glassmorphism, etc.)
        - Random colors from palette (WCAG compliant)
        - Random typography (fonts, sizes, weights, spacing)
        - Random styling (borders, shadows, padding)
        - Optional element reordering
        """)

    with legend_col3:
        st.markdown("""
        **📏 Text Shrink (Type 2 - Dense Info)**
        - Font size reduced by 20% (×0.8, min 11px)
        - Removes overflow/ellipsis restrictions
        - Unwraps text from nowrap constraints
        - Removes small fixed width limits
        - Tests readability with compressed text
        """)

    # Primary Research Findings
    st.divider()
    st.markdown("### 🔬 Primary Research Findings")

    findings_col1, findings_col2 = st.columns(2)

    with findings_col1:
        st.markdown("""
        **🎯 Key Observations:**
        - **Spatial reasoning gaps**: Models lack GUI spatial relation understanding and reasoning
        - **Static visual heuristics**: Models rely on inaccurate heuristics that fail after interface updates
        - **Reasoning trade-offs**: CoT reasoning hurts performance on simple tasks but helps on complex/unfamiliar tasks
        """)

    with findings_col2:
        st.markdown("""
        **⚠️ Training Insights:**
        - **SFT limitations**: LoRA fine-tuning on noisy synthetic data can hurt performance on direct GUI grounding
        - **Overfitting sensitivity**: Models show high sensitivity to domain-randomized perturbations
        - **Robustness needs**: General software control requires robustness to version changes and fine-grained visual understanding
        """)


if __name__ == "__main__":
    main()