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
    """Annotate image with GT bbox and coordinates - preserves exact pixel resolution"""
    # Create a copy to draw on, preserving exact pixel dimensions
    annotated_img = img.copy()
    draw = ImageDraw.Draw(annotated_img)
    
    # Draw GT bbox with two lines of different colors
    if pd.notna(row.get('ground_truth_bbox')):
        try:
            gt_bbox = ast.literal_eval(row['ground_truth_bbox'])
            if len(gt_bbox) >= 4:
                x, y, w, h = gt_bbox[0], gt_bbox[1], gt_bbox[2], gt_bbox[3]
                # Draw two rectangles with different colors for better visibility (dashed lines)
                outer_color = (255, 0, 0)  # Red (outer)
                inner_color = (255, 255, 0)  # Yellow (inner)
                outer_width = 5
                inner_width = 3
                offset = 2  # Offset between outer and inner rectangles
                dash_length = 8
                gap_length = 8
                
                # Draw outer rectangle (red) with dashed lines
                # Top edge
                for i in range(0, int(w), dash_length + gap_length):
                    draw.line([(x + i, y), (x + min(i + dash_length, w), y)], 
                             fill=outer_color, width=outer_width)
                # Right edge
                for i in range(0, int(h), dash_length + gap_length):
                    draw.line([(x + w, y + i), (x + w, y + min(i + dash_length, h))], 
                             fill=outer_color, width=outer_width)
                # Bottom edge
                for i in range(0, int(w), dash_length + gap_length):
                    draw.line([(x + w - min(i + dash_length, w), y + h), 
                              (x + w - i, y + h)], 
                             fill=outer_color, width=outer_width)
                # Left edge
                for i in range(0, int(h), dash_length + gap_length):
                    draw.line([(x, y + h - min(i + dash_length, h)), 
                              (x, y + h - i)], 
                             fill=outer_color, width=outer_width)
                
                # Draw inner rectangle (yellow) with dashed lines and offset
                inner_x, inner_y = x + offset, y + offset
                inner_w, inner_h = w - 2 * offset, h - 2 * offset
                # Top edge
                for i in range(0, int(inner_w), dash_length + gap_length):
                    draw.line([(inner_x + i, inner_y), (inner_x + min(i + dash_length, inner_w), inner_y)], 
                             fill=inner_color, width=inner_width)
                # Right edge
                for i in range(0, int(inner_h), dash_length + gap_length):
                    draw.line([(inner_x + inner_w, inner_y + i), (inner_x + inner_w, inner_y + min(i + dash_length, inner_h))], 
                             fill=inner_color, width=inner_width)
                # Bottom edge
                for i in range(0, int(inner_w), dash_length + gap_length):
                    draw.line([(inner_x + inner_w - min(i + dash_length, inner_w), inner_y + inner_h), 
                              (inner_x + inner_w - i, inner_y + inner_h)], 
                             fill=inner_color, width=inner_width)
                # Left edge
                for i in range(0, int(inner_h), dash_length + gap_length):
                    draw.line([(inner_x, inner_y + inner_h - min(i + dash_length, inner_h)), 
                              (inner_x, inner_y + inner_h - i)], 
                             fill=inner_color, width=inner_width)
        except:
            pass
    
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
            (cx + 30, cy + 30), # Right edge (10 * 3)
        ]
        
        # Draw filled white cursor with black outline
        draw.polygon(cursor_points, fill=(255, 255, 255), outline=(0, 0, 0), width=2)
        
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

def render_statistics(df, filtered_df, model=None):
    """Render aggregated statistics by variant and overall"""
    
    if len(filtered_df) == 0:
        st.warning("No data available for statistics.")
        return
    
    # Check which metrics are available
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
    
    # Convert hit_box_accuracy to numeric for aggregation (True/False -> 1/0)
    filtered_df_agg = filtered_df.copy()
    if 'hit_box_accuracy' in filtered_df_agg.columns:
        # Convert boolean/string to numeric
        filtered_df_agg['hit_box_accuracy_numeric'] = filtered_df_agg['hit_box_accuracy'].apply(
            lambda x: 1 if (isinstance(x, bool) and x) or (isinstance(x, str) and x.lower() == 'true') else 0
        )
    
    # Failure distribution visualization - Show this first
    if 'hit_box_accuracy' in filtered_df_agg.columns and model is not None:
        st.markdown(f"**{model} - Failure Distribution**")
        
        # Get all data for the selected model, regardless of other filters
        # This shows all configurations for the model
        model_df = df[df['model'] == model].copy()
        
        # Prepare data for visualization
        viz_df = model_df.copy()
        if 'hit_box_accuracy' in viz_df.columns:
            # Convert hit_box_accuracy to numeric for this visualization
            viz_df['hit_box_accuracy_numeric'] = viz_df['hit_box_accuracy'].apply(
                lambda x: 1 if (isinstance(x, bool) and x) or (isinstance(x, str) and x.lower() == 'true') else 0
            )
        viz_df['is_failure'] = ~(viz_df['hit_box_accuracy_numeric'].astype(bool))
        
        # Create a comprehensive view of all combinations
        if all(col in viz_df.columns for col in ['query_type', 'use_reasoning', 'variant']):
            # Group by all three dimensions
            failure_stats = viz_df.groupby(['query_type', 'use_reasoning', 'variant']).agg({
                'is_failure': ['sum', 'count']
            }).reset_index()
            failure_stats.columns = ['query_type', 'use_reasoning', 'variant', 'failures', 'total']
            failure_stats['failure_rate'] = failure_stats['failures'] / failure_stats['total']
            failure_stats['success_rate'] = 1 - failure_stats['failure_rate']
            
            # Create a multi-bar chart grouped by variant
            # x-axis: query_type/use_reasoning combinations
            # bars: variants
            fig = go.Figure()
            
            # Get unique values for grouping
            variants = sorted(failure_stats['variant'].unique())
            query_types = sorted(failure_stats['query_type'].unique())
            reasoning_types = sorted(failure_stats['use_reasoning'].unique())
            
            # Create x-axis labels (query_type/use_reasoning combinations)
            # Use shorter, more readable labels
            x_labels = []
            label_mapping = {}  # Store mapping for hover tooltips
            for query_type in query_types:
                for use_reasoning in reasoning_types:
                    # Create short label: abbreviate query_type and use R/NR for reasoning
                    reasoning_abbr = "R" if use_reasoning else "NR"
                    # Shorten query_type if needed (take first few chars or use abbreviation)
                    query_abbr = query_type[:8] if len(query_type) > 8 else query_type
                    short_label = f"{query_abbr}\n{reasoning_abbr}"
                    x_labels.append(short_label)
                    # Store full info for reference
                    label_mapping[short_label] = (query_type, use_reasoning)
            
            # Color palette for variants
            colors = px.colors.qualitative.Set3
            
            # Create bars for each variant
            for variant_idx, variant in enumerate(variants):
                # Create y values for each query_type/use_reasoning combination
                y_values = []
                custom_data_list = []
                for query_type in query_types:
                    for use_reasoning in reasoning_types:
                        # Filter data for this combination and variant
                        variant_data = failure_stats[
                            (failure_stats['query_type'] == query_type) &
                            (failure_stats['use_reasoning'] == use_reasoning) &
                            (failure_stats['variant'] == variant)
                        ]
                        if len(variant_data) > 0:
                            y_values.append(variant_data['failure_rate'].iloc[0])
                            custom_data_list.append([
                                variant_data['failures'].iloc[0],
                                variant_data['total'].iloc[0],
                                query_type,
                                use_reasoning
                            ])
                        else:
                            y_values.append(None)
                            custom_data_list.append([None, None, query_type, use_reasoning])
                
                fig.add_trace(go.Bar(
                    name=variant,
                    x=x_labels,
                    y=y_values,
                    marker=dict(
                        color=colors[variant_idx % len(colors)],
                        opacity=0.8
                    ),
                    hovertemplate='<b>Variant:</b> ' + variant + '<br>' +
                                '<b>Query Type:</b> %{customdata[2]}<br>' +
                                '<b>Use Reasoning:</b> %{customdata[3]}<br>' +
                                '<b>Failure Rate:</b> %{y:.2%}<br>' +
                                '<b>Failures:</b> %{customdata[0]}/%{customdata[1]}<extra></extra>',
                    customdata=custom_data_list,
                    showlegend=False  # Hide from legend
                ))
            
            fig.update_layout(
                xaxis=dict(
                    title='',
                    tickangle=0,  # Horizontal labels
                    tickfont=dict(size=8),
                    tickmode='linear'
                ),
                yaxis=dict(
                    title='',
                    range=[0, 1],
                    tickformat='.0%'
                ),
                barmode='group',  # Grouped bars
                height=280,  # Increased height for better bar visibility
                hovermode='closest',  # Show only the bar being hovered
                showlegend=False,  # Hide overall legend
                margin=dict(t=10, b=80, l=0, r=10)  # Minimal left margin, reduced right margin
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Overall Statistics - Show this after Failure Distribution
    st.markdown("**Overall Statistics**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if 'hit_box_accuracy' in metrics:
            hit_box_mean = filtered_df_agg['hit_box_accuracy_numeric'].mean() if 'hit_box_accuracy_numeric' in filtered_df_agg.columns else 0
            st.markdown(f"**Accuracy**")
            st.markdown(f"<span style='font-size: 1.1em;'>{hit_box_mean:.4f}</span>", unsafe_allow_html=True)
            hit_box_count = filtered_df_agg['hit_box_accuracy_numeric'].sum() if 'hit_box_accuracy_numeric' in filtered_df_agg.columns else 0
            st.caption(f"{int(hit_box_count)}/{len(filtered_df_agg)}")
    
    with col2:
        if 'normalized_mse' in metrics:
            mse_mean = filtered_df_agg['normalized_mse'].mean() if pd.notna(filtered_df_agg['normalized_mse']).any() else None
            if mse_mean is not None:
                st.markdown(f"**NMSE**")
                st.markdown(f"<span style='font-size: 1.1em;'>{mse_mean:.4f}</span>", unsafe_allow_html=True)
                mse_std = filtered_df_agg['normalized_mse'].std()
                st.caption(f"σ: {mse_std:.4f}")
            else:
                st.markdown(f"**NMSE**")
                st.markdown(f"<span style='font-size: 1.1em;'>N/A</span>", unsafe_allow_html=True)
    
    with col3:
        if 'ngiou' in metrics:
            ngiou_mean = filtered_df_agg['ngiou'].mean() if pd.notna(filtered_df_agg['ngiou']).any() else None
            if ngiou_mean is not None:
                st.markdown(f"**NGIoU**")
                st.markdown(f"<span style='font-size: 1.1em;'>{ngiou_mean:.4f}</span>", unsafe_allow_html=True)
                ngiou_std = filtered_df_agg['ngiou'].std()
                st.caption(f"σ: {ngiou_std:.4f}")
            else:
                st.markdown(f"**NGIoU**")
                st.markdown(f"<span style='font-size: 1.1em;'>N/A</span>", unsafe_allow_html=True)


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
        st.header("Evaluation Config")
        
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
            # st.info("ℹ️ **Variant navigation mode**: Showing all variants for this task/step (hit_box_accuracy filter temporarily disabled)")
        
        # Apply filters (test_split=None to include all test splits)
        filtered_df = apply_filters(df, model, query_type, use_reasoning, test_split=None, variant=variant, hit_box_filter=effective_hit_box_filter)
        
        # Handle filter changes
        filters = (model, query_type, use_reasoning, variant, effective_hit_box_filter)
        handle_filter_change(filters, filtered_df, previous_task_id, previous_step_index)
        
        st.divider()
        render_statistics(df, filtered_df, model=model)
        st.divider()
        
        # Navigation
        if len(filtered_df) > 0:
            render_navigation_buttons(filtered_df, variants)
        else:
            st.warning("No samples match the filters!")
    
    return filtered_df

def render_header(filtered_df, current_row):
    """Render header with model/reasoning/variant info"""
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.metric("Model", current_row['model'])
    with col2:
        use_reasoning = current_row.get('use_reasoning', 'N/A')
        st.metric("Use Reasoning", "Yes" if use_reasoning == True else "No" if use_reasoning == False else str(use_reasoning))
    with col3:
        st.metric("Variant", current_row.get('variant', 'N/A'))

def render_screenshot(row, filtered_df):
    """Render screenshot with optional annotations"""
    # Episode and Step information
    episode_id = row.get('task_id', 'N/A')
    step_idx = row.get('step_index', 'N/A')
    
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
    
    # Compact Episode/Step info on one line
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

def render_sample_details(row, filtered_df):
    """Render sample details and metrics"""
    st.subheader("Instruction")
    st.info(row['instruction'])
    
    st.subheader("Prediction & Step Metrics")
    
    # Raw Prediction and Hit Box Accuracy in the same row
    pred_col1, pred_col2 = st.columns(2)
    with pred_col1:
        st.markdown("**Raw Prediction**")
        st.markdown(f"<span style='font-size: 0.9em;'>{row.get('raw_prediction', 'N/A')}</span>", unsafe_allow_html=True)
    
    with pred_col2:
        hit_box = row.get('hit_box_accuracy', 'N/A')
        if isinstance(hit_box, bool):
            display_value = "True" if hit_box else "False"
        elif isinstance(hit_box, (int, float)) and not pd.isna(hit_box):
            display_value = f"{hit_box:.2f}"
        else:
            display_value = str(hit_box)
        st.markdown("**Success**")
        st.markdown(f"<span style='font-size: 0.9em;'>{display_value}</span>", unsafe_allow_html=True)
    
    # Helper function to get metric value
    def get_metric_value(col_name, metric_name):
        value = row.get(col_name)
        exists = col_name in row.index
        if exists and value is not None and not pd.isna(value):
            if isinstance(value, (int, float)):
                return f"{value:.4f}" if abs(value) < 1 else f"{value:.2f}"
            else:
                return str(value)
        return "N/A"
    
    # MSEs in one row
    mse_col1, mse_col2 = st.columns(2)
    with mse_col1:
        st.markdown("**Bbox Center MSE**")
        mse_val = get_metric_value('bbox_center_mse', 'Bbox Center MSE')
        st.markdown(f"<span style='font-size: 0.9em;'>{mse_val}</span>", unsafe_allow_html=True)
    with mse_col2:
        st.markdown("**Normalized MSE**")
        nmse_val = get_metric_value('normalized_mse', 'Normalized MSE')
        st.markdown(f"<span style='font-size: 0.9em;'>{nmse_val}</span>", unsafe_allow_html=True)
    
    # GIoUs in one row
    giou_col1, giou_col2 = st.columns(2)
    with giou_col1:
        st.markdown("**GIoU**")
        giou_val = get_metric_value('giou', 'GIoU')
        st.markdown(f"<span style='font-size: 0.9em;'>{giou_val}</span>", unsafe_allow_html=True)
    with giou_col2:
        st.markdown("**NGIoU**")
        ngiou_val = get_metric_value('ngiou', 'NGIoU')
        st.markdown(f"<span style='font-size: 0.9em;'>{ngiou_val}</span>", unsafe_allow_html=True)
    
    st.subheader("Coordinates")
    st.markdown(f"**Prediction**: {[round(i) for i in ast.literal_eval(row.get('coordinates'))]}")
    st.markdown(f"**Ground Truth Bbox**: {[round(i) for i in ast.literal_eval(row.get('ground_truth_bbox'))]}")
    
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
    
    col1, col2 = st.columns([3, 1])
    with col1:
        render_screenshot(current_row, filtered_df)
    with col2:
        render_sample_details(current_row, filtered_df)
    
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
