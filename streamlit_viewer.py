import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image
import ast
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from io import BytesIO

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
        'is_variant_change': False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================================
# Data Loading & Processing
# ============================================================================

@st.cache_data
def load_data():
    """Load the dataset CSV file"""
    csv_path = Path(__file__).parent / "data" / "baseline_results_full_new.csv"
    return pd.read_csv(csv_path)

def apply_filters(df, model, query_type, use_reasoning, test_split=None, variant=None, hit_box_filter=None):
    """Apply filters to dataframe and sort by task_id and step_index"""
    filtered = df[
        (df['model'] == model) &
        (df['query_type'] == query_type) &
        (df['use_reasoning'] == use_reasoning)
    ].copy()
    if test_split is not None:
        filtered = filtered[filtered['test_split'] == test_split]
    if variant is not None:
        filtered = filtered[filtered['variant'] == variant]
    if hit_box_filter is not None and hit_box_filter != 'All':
        # Filter by hit_box_accuracy (handle both string and bool values)
        # Convert to string and normalize for comparison
        hit_box_str = filtered['hit_box_accuracy'].astype(str).str.strip().str.lower()
        if hit_box_filter == 'False':
            filtered = filtered[hit_box_str == 'false']
        elif hit_box_filter == 'True':
            filtered = filtered[hit_box_str == 'true']
    return filtered.sort_values(['task_id', 'step_index']).reset_index(drop=True)


# ============================================================================
# Image Annotation
# ============================================================================

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
    """Annotate image with GT bbox and coordinates"""
    img_array = np.array(img)
    width, height = img.width, img.height
    
    # Calculate figure size to preserve original resolution
    # Use a higher DPI to maintain pixel accuracy
    dpi = 100
    fig_width = width / dpi
    fig_height = height / dpi
    
    # For very large images, we still need to limit display size for browser performance
    # but we'll use higher DPI to maintain detail
    max_fig_size = 24  # inches (larger limit to preserve more detail)
    if fig_width > max_fig_size or fig_height > max_fig_size:
        scale = max_fig_size / max(fig_width, fig_height)
        fig_width *= scale
        fig_height *= scale
        # Increase DPI proportionally to maintain pixel-level accuracy
        dpi = int(100 / scale)
        # Cap DPI at reasonable maximum to avoid memory issues
        dpi = min(dpi, 300)
    
    fig, ax = plt.subplots(1, 1, figsize=(fig_width, fig_height), dpi=dpi)
    ax.imshow(img_array)
    ax.axis('off')
    
    # Draw GT bbox
    if pd.notna(row.get('ground_truth_bbox')):
        try:
            gt_bbox = ast.literal_eval(row['ground_truth_bbox'])
            if len(gt_bbox) >= 4:
                x, y, w, h = gt_bbox[0], gt_bbox[1], gt_bbox[2], gt_bbox[3]
                rect = patches.Rectangle((x, y), w, h, linewidth=2, edgecolor='green', 
                                         facecolor='none', linestyle='--', alpha=0.7)
                ax.add_patch(rect)
        except:
            pass
    
    # Draw coordinates
    coords = parse_coords(row.get('coordinates'))
    if coords:
        ax.plot(coords[0], coords[1], 'bo', markersize=12, alpha=0.8)
        ax.plot(coords[0], coords[1], 'b+', markersize=20, markeredgewidth=3)
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, dpi=100)
    buf.seek(0)
    annotated_img = Image.open(buf)
    plt.close(fig)
    return annotated_img

# ============================================================================
# Navigation Logic
# ============================================================================

def cycle_variant(variants, current_variant):
    """Cycle to next variant in list, wrapping to first if at last"""
    if not variants or current_variant not in variants:
        return variants[0] if variants else None
    current_idx = variants.index(current_variant)
    next_idx = (current_idx + 1) % len(variants)
    return variants[next_idx]

def handle_filter_change(filters, filtered_df, previous_task_id=None, previous_step_index=None):
    """Handle filter changes and update current_index accordingly"""
    current_hash = hash(filters)
    
    if st.session_state.filter_hash != current_hash:
        # Check if this is a variant change using the explicit flag
        is_variant_change = st.session_state.is_variant_change
        
        # Priority: use previous_task_id/step_index if provided (from variant change),
        # otherwise use stored last_task_id/step_index (from previous filter state)
        task_id_to_find = previous_task_id if previous_task_id is not None else st.session_state.last_task_id
        step_index_to_find = previous_step_index if previous_step_index is not None else st.session_state.last_step_index
        
        # Try to find matching row with same task_id and step_index
        if task_id_to_find is not None and step_index_to_find is not None and len(filtered_df) > 0:
            matching = filtered_df[
                (filtered_df['task_id'] == task_id_to_find) &
                (filtered_df['step_index'] == step_index_to_find)
            ]
            if len(matching) > 0:
                # Find the position in the new filtered_df (which has reset_index, so index is sequential)
                st.session_state.current_index = matching.index[0]
            else:
                # If exact match not found
                if is_variant_change:
                    # For variant changes, we MUST have exact match - don't change task_id or step_index
                    # If exact match doesn't exist for the new variant, try to find same task_id with closest step
                    # This handles cases where the step_index might not exist for this variant
                    same_task = filtered_df[filtered_df['task_id'] == task_id_to_find]
                    if len(same_task) > 0:
                        # Find step_index closest to the target within the same task
                        same_task = same_task.copy()
                        same_task['step_diff'] = abs(same_task['step_index'] - step_index_to_find)
                        closest = same_task.nsmallest(1, 'step_diff')
                        st.session_state.current_index = closest.index[0]
                        # Update last_task_id/last_step_index to the closest match we found
                        # This ensures subsequent Perturb clicks use a valid target
                        closest_row = filtered_df.iloc[st.session_state.current_index]
                        st.session_state.last_task_id = closest_row.get('task_id')
                        st.session_state.last_step_index = closest_row.get('step_index')
                    else:
                        # Even the task_id doesn't exist - reset to 0 but preserve target for next attempt
                        if st.session_state.current_index >= len(filtered_df):
                            st.session_state.current_index = 0
                        # Don't update last_task_id/last_step_index - keep the original target
                else:
                    # For other filter changes, try to find same task_id with closest step_index
                    same_task = filtered_df[filtered_df['task_id'] == task_id_to_find]
                    if len(same_task) > 0:
                        # Find step_index closest to the target
                        same_task = same_task.copy()
                        same_task['step_diff'] = abs(same_task['step_index'] - step_index_to_find)
                        closest = same_task.nsmallest(1, 'step_diff')
                        st.session_state.current_index = closest.index[0]
                    else:
                        st.session_state.current_index = 0
        else:
            st.session_state.current_index = 0
        
        # Don't reset variant change flag here - let render_main_content use it
        # It will be reset after render_main_content processes it
        st.session_state.filter_hash = current_hash

# ============================================================================
# UI Components
# ============================================================================

def render_filters(df):
    """Render filter selectboxes and return selected values"""
    st.subheader("Filters")
    model = st.selectbox("Model", sorted(df['model'].unique().tolist()))
    query_type = st.selectbox("Query Type", sorted(df['query_type'].unique().tolist()))
    use_reasoning = st.selectbox("Use Reasoning", sorted(df['use_reasoning'].unique().tolist()))
    
    # Hit box accuracy filter
    hit_box_filter = st.selectbox("Hit Box Accuracy", ['All', 'True', 'False'])
    
    variants = sorted([x for x in df['variant'].unique().tolist() if pd.notna(x)])
    if st.session_state.selected_variant is None or st.session_state.selected_variant not in variants:
        st.session_state.selected_variant = variants[0] if variants else None
    
    # Variant is controlled by perturb button only - no dropdown shown
    # Just use the session state value directly
    variant = st.session_state.selected_variant
    
    return model, query_type, use_reasoning, variant, hit_box_filter

def render_statistics(df, filtered_df):
    """Render statistics metrics"""
    st.subheader("Statistics")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Rows", len(df))
        st.metric("Filtered Rows", len(filtered_df))
    with col2:
        st.metric("Total Columns", len(df.columns))
        if len(df) > 0:
            percentage = (len(filtered_df) / len(df)) * 100
            st.metric("Filter Percentage", f"{percentage:.1f}%")

def render_navigation_buttons(filtered_df, variants):
    """Render navigation buttons"""
    if len(filtered_df) == 0:
        return
    
    # Navigation buttons
    has_variants = len(variants) > 1
    cols = st.columns(3 if has_variants else 2)
    
    with cols[0]:
        if st.button("◀ Prev", use_container_width=True, key="prev_sample"):
            st.session_state.current_index = max(0, st.session_state.current_index - 1)
    
    if has_variants:
        with cols[1]:
            if st.button("Perturb", use_container_width=True, key="perturb"):
                new_variant = cycle_variant(variants, st.session_state.selected_variant)
                if new_variant:
                    # Use preserved target values (last_task_id/last_step_index) if available,
                    # otherwise fall back to current row
                    target_task_id = st.session_state.last_task_id
                    target_step_index = st.session_state.last_step_index
                    
                    # If we don't have preserved values, get from current row
                    if target_task_id is None or target_step_index is None:
                        if st.session_state.current_index < len(filtered_df):
                            current_row = filtered_df.iloc[st.session_state.current_index]
                            target_task_id = current_row.get('task_id')
                            target_step_index = current_row.get('step_index')
                    
                    # Store target values for variant navigation
                    if target_task_id is not None and target_step_index is not None:
                        st.session_state.pending_variant_navigation = {
                            'task_id': target_task_id,
                            'step_index': target_step_index
                        }
                        # Preserve these as the target for this and future variant changes
                        st.session_state.last_task_id = target_task_id
                        st.session_state.last_step_index = target_step_index
                    
                    # Mark this as a variant change
                    st.session_state.is_variant_change = True
                    st.session_state.selected_variant = new_variant
                    st.rerun()
        with cols[2]:
            if st.button("Next ▶", use_container_width=True, key="next_sample"):
                st.session_state.current_index = min(len(filtered_df) - 1, st.session_state.current_index + 1)
    else:
        with cols[1]:
            if st.button("Next ▶", use_container_width=True, key="next_sample"):
                st.session_state.current_index = min(len(filtered_df) - 1, st.session_state.current_index + 1)
    
    # Direct index input
    new_index = st.number_input("Go to index:", min_value=0, max_value=len(filtered_df) - 1,
                               value=st.session_state.current_index, step=1)
    if new_index != st.session_state.current_index:
        st.session_state.current_index = int(new_index)
    
    st.session_state.current_index = max(0, min(st.session_state.current_index, len(filtered_df) - 1))

def render_sidebar(df):
    """Render sidebar with filters, stats, and navigation"""
    with st.sidebar:
        st.header("Navigation")
        
        # Get previous row info if available (for variant changes)
        previous_task_id = None
        previous_step_index = None
        if 'pending_variant_navigation' in st.session_state and st.session_state.pending_variant_navigation:
            nav_info = st.session_state.pending_variant_navigation
            previous_task_id = nav_info.get('task_id')
            previous_step_index = nav_info.get('step_index')
            # Preserve these as last_task_id/last_step_index for variant navigation
            # This ensures subsequent Perturb clicks use the correct target
            st.session_state.last_task_id = previous_task_id
            st.session_state.last_step_index = previous_step_index
            # Clear it after use
            st.session_state.pending_variant_navigation = None
        
        # Filters
        model, query_type, use_reasoning, variant, hit_box_filter = render_filters(df)
        
        # Get variants list for perturb button
        variants = sorted([x for x in df['variant'].unique().tolist() if pd.notna(x)])
        
        # For variant changes, temporarily bypass hit_box_accuracy filter to allow cross-variant comparison
        # This lets you see all variants for the same task/step, even if they have different hit_box_accuracy values
        effective_hit_box_filter = hit_box_filter
        if st.session_state.is_variant_change and previous_task_id is not None and previous_step_index is not None:
            # Temporarily remove hit_box_accuracy filter for variant navigation
            effective_hit_box_filter = None
            st.info("ℹ️ **Variant navigation mode**: Showing all variants for this task/step (hit_box_accuracy filter temporarily disabled)")
        
        # Apply filters (test_split=None to include all test splits)
        filtered_df = apply_filters(df, model, query_type, use_reasoning, test_split=None, variant=variant, hit_box_filter=effective_hit_box_filter)
        
        # Handle filter changes
        filters = (model, query_type, use_reasoning, variant, effective_hit_box_filter)
        handle_filter_change(filters, filtered_df, previous_task_id, previous_step_index)
        
        st.divider()
        render_statistics(df, filtered_df)
        st.divider()
        
        # Navigation
        if len(filtered_df) > 0:
            render_navigation_buttons(filtered_df, variants)
        else:
            st.warning("No samples match the filters!")
    
    return filtered_df

def render_header(filtered_df, current_row):
    """Render header with episode/step info and metrics"""
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        episode_id = current_row.get('task_id', 'N/A')
        step_idx = current_row.get('step_index', 'N/A')
        
        # Episode position
        unique_episodes = sorted(filtered_df['task_id'].unique().tolist())
        episode_pos = unique_episodes.index(episode_id) + 1 if episode_id in unique_episodes else 1
        
        # Step position within episode
        episode_steps = filtered_df[filtered_df['task_id'] == episode_id]
        step_pos_in_episode = None
        for pos, idx in enumerate(episode_steps.index):
            if idx == st.session_state.current_index:
                step_pos_in_episode = pos + 1
                break
        if step_pos_in_episode is None:
            step_pos_in_episode = step_idx + 1
        
        st.markdown("**Episode:**")
        st.markdown(f"<span style='font-size: 1.5em;'>{episode_id}</span>", unsafe_allow_html=True)
        st.markdown(f"<span style='font-size: 1em; color: #666;'>{episode_pos} / {len(unique_episodes)}</span>", unsafe_allow_html=True)
        st.markdown("**Step:**")
        st.markdown(f"<span style='font-size: 1.5em;'>{step_idx}</span>", unsafe_allow_html=True)
        st.markdown(f"<span style='font-size: 1em; color: #666;'>Episode: {step_pos_in_episode} / {len(episode_steps)} | All: {st.session_state.current_index + 1} / {len(filtered_df)}</span>", unsafe_allow_html=True)
    
    with col2:
        st.metric("Model", current_row['model'])
    with col3:
        use_reasoning = current_row.get('use_reasoning', 'N/A')
        st.metric("Use Reasoning", "Yes" if use_reasoning == True else "No" if use_reasoning == False else str(use_reasoning))
    with col4:
        st.metric("Variant", current_row.get('variant', 'N/A'))

def render_screenshot(row):
    """Render screenshot with optional annotations"""
    st.subheader("Screenshot")
    
    show_annotations = st.checkbox("Show Annotations", 
                                  value=st.session_state.show_annotations,
                                  key="show_annotations_checkbox")
    st.session_state.show_annotations = show_annotations
    
    image_path = row.get('image_path', '')
    if not image_path:
        st.error("Image path not found in data")
        return
    
    # Strip /mnt/ prefix if present and convert to relative path
    if image_path.startswith('/mnt/'):
        image_path = image_path[5:]  # Remove '/mnt/' prefix
    
    # Handle both absolute and relative paths
    image_path_obj = Path(image_path)
    if not image_path_obj.is_absolute():
        # Try relative to project root first
        image_path_obj = Path(__file__).parent / image_path
        # If not found, try relative to current directory
        if not image_path_obj.exists():
            image_path_obj = Path(image_path)
    
    if not image_path_obj.exists():
        st.error(f"Image not found: {image_path_obj}")
        return
    
    try:
        img = Image.open(image_path_obj)
        if show_annotations:
            img = annotate_image(img, row)
        # Display image at original resolution
        st.image(img, use_container_width=False, caption=image_path_obj.name)
    except Exception as e:
        st.error(f"Error loading image: {e}")

def render_sample_details(row):
    """Render sample details and metrics"""
    st.subheader("Instruction")
    st.info(row['instruction'])
    
    st.subheader("Prediction & Accuracy")
    st.markdown("**Raw Prediction:**")
    st.text(row.get('raw_prediction', 'N/A'))
    
    hit_box = row.get('hit_box_accuracy', 'N/A')
    if isinstance(hit_box, bool):
        display_value = "True" if hit_box else "False"
    elif isinstance(hit_box, (int, float)) and not pd.isna(hit_box):
        display_value = f"{hit_box:.2f}"
    else:
        display_value = str(hit_box)
    st.metric("Hit Box Accuracy", display_value)
    
    # Debug: Log metric column access
    metric_cols = {
        'Bbox Center MSE': 'bbox_center_mse',
        'Normalized MSE': 'normalized_mse',
        'GIoU': 'giou',
        'NGIoU': 'ngiou'
    }
    
    for metric_name, col_name in metric_cols.items():
        value = row.get(col_name)
        exists = col_name in row.index
        # Only show metric if it exists and has a valid value
        if exists and value is not None and not pd.isna(value):
            if isinstance(value, (int, float)):
                display_val = f"{value:.4f}" if abs(value) < 1 else f"{value:.2f}"
            else:
                display_val = str(value)
            st.metric(metric_name, display_val)
        else:
            # Show as N/A - debug info available in Debug section below
            st.metric(metric_name, "N/A")
    
    st.subheader("Coordinates")
    st.markdown(f"**Coordinates**: {row.get('coordinates')}")
    st.markdown(f"**Ground Truth Bbox**: {row.get('ground_truth_bbox')}")
    
    with st.expander("View All Data Fields"):
        st.json(row.to_dict())

def render_main_content(filtered_df):
    """Render main content area"""
    if len(filtered_df) == 0:
        st.warning("No samples available. Please adjust your filters.")
        return
    
    # Ensure current_index is within bounds
    st.session_state.current_index = max(0, min(st.session_state.current_index, len(filtered_df) - 1))
    
    # Get the current row - using iloc ensures we get by position, not by index label
    # Since apply_filters resets index with drop=True, iloc position matches the sequential index
    current_row = filtered_df.iloc[st.session_state.current_index].copy()
    
    # Store current task_id and step_index for filter change preservation
    # BUT: If we just did a variant change, only update if the current row matches the target
    current_task_id = current_row.get('task_id')
    current_step_index = current_row.get('step_index')
    
    # Only update last_task_id/last_step_index if:
    # 1. Not a variant change, OR
    # 2. It's a variant change AND the current row matches what we were looking for
    if not st.session_state.is_variant_change:
        # Normal case: update with current row
        st.session_state.last_task_id = current_task_id
        st.session_state.last_step_index = current_step_index
    else:
        # Variant change case: check if current row matches the target
        # The target is stored in last_task_id/last_step_index (set in render_sidebar)
        target_task_id = st.session_state.last_task_id
        target_step_index = st.session_state.last_step_index
        
        if target_task_id is not None and target_step_index is not None:
            if current_task_id == target_task_id and current_step_index == target_step_index:
                # Current row matches target - this is correct, values already set in render_sidebar
                pass
            else:
                # Current row doesn't match target - preserve the target values
                # Don't update last_task_id/last_step_index, keep the original target
                pass
        else:
            # No target set, use current row
            st.session_state.last_task_id = current_task_id
            st.session_state.last_step_index = current_step_index
    
    # Reset variant change flag after processing in render_main_content
    st.session_state.is_variant_change = False
    
    # Verify we're using the same row for all components
    # Store row identifier for debugging
    row_id = f"{current_row.get('task_id', 'N/A')}_step_{current_row.get('step_index', 'N/A')}_variant_{current_row.get('variant', 'N/A')}"
    
    render_header(filtered_df, current_row)
    st.divider()
    
    col1, col2 = st.columns([1.5, 1])
    with col1:
        render_screenshot(current_row)
    with col2:
        render_sample_details(current_row)
    
    # Debug: Show row identifier to verify consistency
    with st.expander("🔍 Debug: Row Verification", expanded=False):
        st.write(f"**Current Index**: {st.session_state.current_index}")
        st.write(f"**Row Identifier**: {row_id}")
        st.write(f"**Image Path**: {current_row.get('image_path', 'N/A')}")
        st.write(f"**Instruction**: {current_row.get('instruction', 'N/A')[:100]}...")
        st.write(f"**Ground Truth Bbox**: {current_row.get('ground_truth_bbox', 'N/A')}")
        st.write(f"**Coordinates**: {current_row.get('coordinates', 'N/A')}")
        
        st.divider()
        st.subheader("All Columns in Row")
        st.write(f"**Total Columns**: {len(current_row)}")
        st.write("**Column Names:**")
        st.code(', '.join(current_row.index.tolist()))
        
        st.divider()
        st.subheader("Column Values")
        for col in current_row.index:
            value = current_row[col]
            # Truncate long values for display
            if isinstance(value, str) and len(value) > 100:
                display_value = value[:100] + "..."
            else:
                display_value = value
            st.write(f"**{col}**: `{display_value}` (type: {type(value).__name__})")
        
        st.divider()
        st.subheader("Missing Metric Columns Check")
        metric_cols = ['bbox_center_mse', 'normalized_mse', 'giou', 'ngiou']
        for col in metric_cols:
            exists = col in current_row.index
            value = current_row.get(col, 'NOT FOUND')
            st.write(f"**{col}**: {'✅ EXISTS' if exists else '❌ NOT FOUND'} - Value: `{value}`")

# ============================================================================
# Main Execution
# ============================================================================

df = load_data()
filtered_df = render_sidebar(df)
render_main_content(filtered_df)
