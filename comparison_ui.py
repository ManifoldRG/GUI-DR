import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image, ImageDraw
import ast

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

def add_prediction_overlay(img, coordinates, color, label):
    """Add prediction overlay to image"""
    if not coordinates or pd.isna(coordinates):
        return img

    try:
        if isinstance(coordinates, str):
            coords = ast.literal_eval(coordinates)
        else:
            coords = coordinates

        # Create a copy to draw on
        img_with_overlay = img.copy()
        draw = ImageDraw.Draw(img_with_overlay)

        x, y = int(coords[0]), int(coords[1])

        # Convert color names to RGB tuples for better visibility
        color_rgb = {
            'blue': (0, 100, 255),
            'red': (255, 50, 50)
        }.get(color, color)

        # Draw crosshair with thicker lines
        size = 30
        # Horizontal line
        draw.line([(x-size, y), (x+size, y)], fill=color_rgb, width=4)
        # Vertical line
        draw.line([(x, y-size), (x, y+size)], fill=color_rgb, width=4)

        # Draw circle around prediction
        radius = 12
        draw.ellipse([(x-radius, y-radius), (x+radius, y+radius)], outline=color_rgb, width=4)

        # Add label with background for visibility
        # Draw a small rectangle behind the text
        label_text = f"{label}"
        # Estimate text size (rough approximation)
        text_bg_box = [(x+25, y-15), (x+25+len(label_text)*7, y+5)]
        draw.rectangle(text_bg_box, fill=(255, 255, 255, 200))
        draw.text((x+28, y-12), label_text, fill=color_rgb)

        return img_with_overlay

    except Exception as e:
        st.warning(f"Could not overlay prediction: {e}")
        return img

def display_comparison(original_row, variant_row, variant_name, debug_mode=False):
    """Display side-by-side comparison with prediction overlays"""
    col1, col2 = st.columns(2)

    # Debug info
    if debug_mode:
        st.caption(f"🔍 Original variant: {original_row.get('variant', 'unknown')}, Perturbation: {variant_row.get('variant', 'unknown')}")
        st.caption(f"📁 Image paths - Original: {original_row.get('image_path', 'N/A')[:50]}... | Perturbation: {variant_row.get('image_path', 'N/A')[:50]}...")

    with col1:

        # Display image with prediction overlay
        img_path = resolve_image_path(original_row, debug_mode)
        if img_path and img_path.exists():
            img = Image.open(img_path)
            # Add prediction overlay
            img_with_prediction = add_prediction_overlay(
                img,
                original_row.get('coordinates'),
                'blue',
                'Original'
            )
            # Display at full resolution by default
            st.image(img_with_prediction, use_container_width=False)
        else:
            st.info("Image not available")
            st.caption(f"❌ Path: {img_path}")

        # Display metrics
        success = "✅ SUCCESS" if original_row['success'] else "❌ FAILED"
        if original_row['success']:
            st.success(success)
        else:
            st.error(success)

        col1_1, col1_2 = st.columns(2)
        with col1_1:
            st.metric("Prediction Error", f"{original_row['bbox_center_mse']:.1f}", help="Mean Squared Error (MSE) between predicted click coordinates and target bounding box center. Lower is better.")
        with col1_2:
            if pd.notna(original_row.get('coordinates')):
                try:
                    coords = ast.literal_eval(original_row['coordinates'])
                    st.metric("Coordinates", f"({coords[0]:.0f}, {coords[1]:.0f})")
                except:
                    st.metric("Coordinates", "N/A")

    with col2:
        # Display image with prediction overlay
        img_path = resolve_image_path(variant_row, debug_mode)
        if img_path and img_path.exists():
            img = Image.open(img_path)
            # Add prediction overlay
            img_with_prediction = add_prediction_overlay(
                img,
                variant_row.get('coordinates'),
                'red',
                variant_name.title()
            )
            # Display at full resolution by default
            st.image(img_with_prediction, use_container_width=False)
        else:
            st.info("Image not available")
            st.caption(f"❌ Path: {img_path}")

        # Display metrics
        success = "✅ SUCCESS" if variant_row['success'] else "❌ FAILED"
        if variant_row['success']:
            st.success(success)
        else:
            st.error(success)

        col2_1, col2_2 = st.columns(2)
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

def main():
    st.title("🔬 Original vs Perturbation Comparison")
    st.markdown("Compare how UI modifications affect AI agent performance")

    df = load_data()
    if df.empty:
        st.error("No data found")
        return

    # Sidebar controls
    st.sidebar.header("🎯 Comparison Settings")

    # Debug mode toggle
    debug_mode = st.sidebar.checkbox("🔍 Debug Mode", value=False, help="Show technical debug information")

    # Default perturbation for initial filtering
    perturbation_variants = ['precision', 'style', 'text_shrink']
    default_variant = 'precision'

    # Get tasks that have both original and any perturbation variant
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