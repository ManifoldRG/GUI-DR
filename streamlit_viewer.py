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
        'pending_variant_navigation': None
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
    csv_path = Path(__file__).parent / "data" / "final_baseline_results.csv"
    return pd.read_csv(csv_path)

def apply_filters(df, model, query_type, reasoning_type, variant=None):
    """Apply filters to dataframe and sort by task_id and step_index"""
    filtered = df[
        (df['model'] == model) &
        (df['query_type'] == query_type) &
        (df['reasoning_type'] == reasoning_type)
    ].copy()
    if variant is not None:
        filtered = filtered[filtered['variant'] == variant]
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
    """Annotate image with GT bbox and corrected_coords_2d_denormalized"""
    img_array = np.array(img)
    width, height = img.width, img.height
    aspect_ratio = width / height
    max_dim = 12
    fig_width = max_dim if width > height else max_dim * aspect_ratio
    fig_height = max_dim / aspect_ratio if width > height else max_dim
    
    fig, ax = plt.subplots(1, 1, figsize=(fig_width, fig_height), dpi=100)
    ax.imshow(img_array)
    ax.axis('off')
    
    # Draw GT bbox
    if pd.notna(row.get('gt_bbox')):
        try:
            gt_bbox = ast.literal_eval(row['gt_bbox'])
            if len(gt_bbox) >= 4:
                x, y, w, h = gt_bbox[0], gt_bbox[1], gt_bbox[2], gt_bbox[3]
                rect = patches.Rectangle((x, y), w, h, linewidth=2, edgecolor='green', 
                                         facecolor='none', linestyle='--', alpha=0.7)
                ax.add_patch(rect)
        except:
            pass
    
    # Draw corrected_coords_2d_denormalized
    coords_2d_denorm = parse_coords(row.get('corrected_coords_2d_denormalized'))
    if coords_2d_denorm:
        ax.plot(coords_2d_denorm[0], coords_2d_denorm[1], 'bo', markersize=12, alpha=0.8)
        ax.plot(coords_2d_denorm[0], coords_2d_denorm[1], 'b+', markersize=20, markeredgewidth=3)
    
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
        # If we have previous task_id and step_index (from variant change), try to find matching row
        if previous_task_id is not None and previous_step_index is not None and len(filtered_df) > 0:
            matching = filtered_df[
                (filtered_df['task_id'] == previous_task_id) &
                (filtered_df['step_index'] == previous_step_index)
            ]
            if len(matching) > 0:
                # Find the position in the new filtered_df (which has reset_index, so index is sequential)
                st.session_state.current_index = matching.index[0]
            else:
                st.session_state.current_index = 0
        else:
            st.session_state.current_index = 0
        st.session_state.filter_hash = current_hash

# ============================================================================
# UI Components
# ============================================================================

def render_filters(df):
    """Render filter selectboxes and return selected values"""
    st.subheader("Filters")
    model = st.selectbox("Model", sorted(df['model'].unique().tolist()))
    query_type = st.selectbox("Query Type", sorted(df['query_type'].unique().tolist()))
    reasoning_type = st.selectbox("Reasoning Type", 
                                   sorted([x for x in df['reasoning_type'].unique().tolist() if pd.notna(x)]))
    
    variants = sorted([x for x in df['variant'].unique().tolist() if pd.notna(x)])
    if st.session_state.selected_variant is None or st.session_state.selected_variant not in variants:
        st.session_state.selected_variant = variants[0] if variants else None
    
    # Variant is controlled by perturb button only - no dropdown shown
    # Just use the session state value directly
    variant = st.session_state.selected_variant
    
    return model, query_type, reasoning_type, variant

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
                    # Store current row info before changing variant
                    if st.session_state.current_index < len(filtered_df):
                        current_row = filtered_df.iloc[st.session_state.current_index]
                        st.session_state.pending_variant_navigation = {
                            'task_id': current_row.get('task_id'),
                            'step_index': current_row.get('step_index')
                        }
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
            # Clear it after use
            st.session_state.pending_variant_navigation = None
        
        # Filters
        model, query_type, reasoning_type, variant = render_filters(df)
        
        # Get variants list for perturb button
        variants = sorted([x for x in df['variant'].unique().tolist() if pd.notna(x)])
        
        # Apply filters
        filtered_df = apply_filters(df, model, query_type, reasoning_type, variant)
        
        # Handle filter changes
        filters = (model, query_type, reasoning_type, variant)
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
        st.metric("Reasoning Type", current_row.get('reasoning_type', 'N/A'))
    with col4:
        st.metric("Variant", current_row.get('variant', 'N/A'))

def render_screenshot(row):
    """Render screenshot with optional annotations"""
    st.subheader("Screenshot")
    
    show_annotations = st.checkbox("Show Annotations", 
                                  value=st.session_state.show_annotations,
                                  key="show_annotations_checkbox")
    st.session_state.show_annotations = show_annotations
    
    screenshot_path = Path(row['screenshot']).expanduser()
    if not screenshot_path.exists():
        st.error(f"Image not found: {screenshot_path}")
        return
    
    try:
        img = Image.open(screenshot_path)
        if show_annotations:
            img = annotate_image(img, row)
        st.image(img, use_container_width=True, caption=screenshot_path.name)
    except Exception as e:
        st.error(f"Error loading image: {e}")

def render_sample_details(row):
    """Render sample details and metrics"""
    st.subheader("Instruction")
    st.info(row['instruction'])
    
    st.subheader("Prediction & Accuracy")
    st.markdown("**Prediction:**")
    st.text(row.get('prediction', 'N/A'))
    
    col_a, col_b = st.columns(2)
    with col_a:
        hit_box = row.get('hit_box_accuracy', 'N/A')
        display_value = f"{hit_box:.2f}" if isinstance(hit_box, (int, float)) and not pd.isna(hit_box) else str(hit_box)
        st.metric("Hit Box Accuracy", display_value)
    with col_b:
        st.metric("Corrected Hit Box", str(row.get('corrected_hit_box_accuracy', 'N/A')))
    
    st.subheader("Corrected Metrics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        action_str_match = row.get('corrected_action_str_em', 'N/A')
        if isinstance(action_str_match, bool):
            action_str_match = "True" if action_str_match else "False"
        elif isinstance(action_str_match, (int, float)) and not pd.isna(action_str_match):
            action_str_match = "True" if action_str_match == 1.0 else "False"
        st.metric("Action Str Match", action_str_match)
    
    with col2:
        mse = row.get('corrected_bbox_center_mse', 'N/A')
        mse_display = f"{mse:.2f}" if isinstance(mse, (int, float)) and not pd.isna(mse) else str(mse)
        st.metric("MSE", mse_display)
    
    with col3:
        normalized_mse = row.get('corrected_normalized_mse', 'N/A')
        nmse_display = f"{normalized_mse:.4f}" if isinstance(normalized_mse, (int, float)) and not pd.isna(normalized_mse) else str(normalized_mse)
        st.metric("Normalized MSE", nmse_display)
    
    st.subheader("Coordinates")
    st.markdown(f"**Coords 2D**: {row.get('corrected_coords_2d', 'N/A')}")
    st.markdown(f"**Coords 2D Denorm**: {row.get('corrected_coords_2d_denormalized', 'N/A')}")
    st.markdown(f"**GT Bbox**: {row.get('gt_bbox', 'N/A')}")
    
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
        st.write(f"**Screenshot Path**: {current_row.get('screenshot', 'N/A')}")
        st.write(f"**Instruction**: {current_row.get('instruction', 'N/A')[:100]}...")
        st.write(f"**GT Bbox**: {current_row.get('gt_bbox', 'N/A')}")
        st.write(f"**Corrected Coords 2D Denorm**: {current_row.get('corrected_coords_2d_denormalized', 'N/A')}")

# ============================================================================
# Main Execution
# ============================================================================

df = load_data()
filtered_df = render_sidebar(df)
render_main_content(filtered_df)
