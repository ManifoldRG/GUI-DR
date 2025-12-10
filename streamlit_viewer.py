import streamlit as st
import pandas as pd
from pathlib import Path
from PIL import Image
import ast

# Page configuration
st.set_page_config(
    page_title="Dataset Viewer",
    page_icon="🖼️",
    layout="wide"
)

# Load data
@st.cache_data
def load_data():
    """Load the dataset CSV file"""
    csv_path = Path(__file__).parent / "data" / "final_baseline_results.csv"
    df = pd.read_csv(csv_path)
    return df

# Initialize session state
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'filter_hash' not in st.session_state:
    st.session_state.filter_hash = None

# Load dataframe
df = load_data()

# Sidebar for navigation and filters
with st.sidebar:
    st.header("Navigation")
    
    # Filters
    st.subheader("Filters")
    
    # Model filter
    models = ['All'] + sorted(df['model'].unique().tolist())
    selected_model = st.selectbox("Model", models)
    
    # Test split filter
    test_splits = ['All'] + sorted(df['test_split'].unique().tolist())
    selected_split = st.selectbox("Test Split", test_splits)
    
    # Query type filter
    query_types = ['All'] + sorted(df['query_type'].unique().tolist())
    selected_query = st.selectbox("Query Type", query_types)
    
    # Apply filters
    filtered_df = df.copy()
    if selected_model != 'All':
        filtered_df = filtered_df[filtered_df['model'] == selected_model]
    if selected_split != 'All':
        filtered_df = filtered_df[filtered_df['test_split'] == selected_split]
    if selected_query != 'All':
        filtered_df = filtered_df[filtered_df['query_type'] == selected_query]
    
    # Reset index when filters change
    current_filter_hash = hash((selected_model, selected_split, selected_query))
    if st.session_state.filter_hash != current_filter_hash:
        st.session_state.current_index = 0
        st.session_state.filter_hash = current_filter_hash
    
    st.divider()
    
    # Navigation controls
    st.subheader("Navigation")
    
    total_samples = len(filtered_df)
    st.write(f"**Total samples**: {len(df)}")
    st.write(f"**Filtered samples**: {total_samples}")
    
    if total_samples > 0:
        # Navigation buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("◀ Previous", use_container_width=True):
                st.session_state.current_index = max(0, st.session_state.current_index - 1)
        with col2:
            if st.button("Next ▶", use_container_width=True):
                st.session_state.current_index = min(total_samples - 1, st.session_state.current_index + 1)
        
        # Direct index input
        new_index = st.number_input(
            "Go to index:",
            min_value=0,
            max_value=total_samples - 1,
            value=st.session_state.current_index,
            step=1
        )
        if new_index != st.session_state.current_index:
            st.session_state.current_index = int(new_index)
        
        # Update index if out of bounds
        if st.session_state.current_index >= total_samples:
            st.session_state.current_index = 0
    else:
        st.warning("No samples match the filters!")

# Main content area
if len(filtered_df) > 0:
    # Get current row
    current_row = filtered_df.iloc[st.session_state.current_index]
    
    # Header with sample info
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title(f"Sample {st.session_state.current_index + 1} / {len(filtered_df)}")
    with col2:
        st.metric("Model", current_row['model'])
    with col3:
        st.metric("Test Split", current_row['test_split'])
    
    # Two columns: Image and Details
    col1, col2 = st.columns([1.5, 1])
    
    with col1:
        st.subheader("Screenshot")
        
        # Load and display image
        screenshot_path = Path(current_row['screenshot']).expanduser()
        
        if screenshot_path.exists():
            try:
                img = Image.open(screenshot_path)
                st.image(img, use_container_width=True, caption=screenshot_path.name)
            except Exception as e:
                st.error(f"Error loading image: {e}")
                st.text(f"Path: {screenshot_path}")
        else:
            st.error(f"Image not found: {screenshot_path}")
            st.text(f"Path: {screenshot_path}")
    
    with col2:
        st.subheader("Instruction")
        st.info(current_row['instruction'])
        
        st.subheader("Metadata")
        
        # Key information
        metadata = {
            "Task ID": current_row.get('task_id', 'N/A'),
            "Step Index": current_row.get('step_index', 'N/A'),
            "Query Type": current_row.get('query_type', 'N/A'),
            "Reasoning Type": current_row.get('reasoning_type', 'N/A'),
            "Variant": current_row.get('variant', 'N/A'),
        }
        
        for key, value in metadata.items():
            st.text(f"**{key}**: {value}")
        
        st.divider()
        
        # Prediction and accuracy
        st.subheader("Prediction & Accuracy")
        
        prediction = current_row.get('prediction', 'N/A')
        st.text_area("Prediction", prediction, height=100, disabled=True)
        
        col_a, col_b = st.columns(2)
        with col_a:
            hit_box = current_row.get('hit_box_accuracy', 'N/A')
            st.metric("Hit Box Accuracy", f"{hit_box:.2f}" if isinstance(hit_box, (int, float)) and not pd.isna(hit_box) else str(hit_box))
        with col_b:
            corrected_hit_box = current_row.get('corrected_hit_box_accuracy', 'N/A')
            st.metric("Corrected Hit Box", str(corrected_hit_box))
        
        # Coordinates
        st.subheader("Coordinates")
        
        coords_2d = current_row.get('corrected_coords_2d', 'N/A')
        coords_2d_denorm = current_row.get('corrected_coords_2d_denormalized', 'N/A')
        
        st.text(f"**Coords 2D**: {coords_2d}")
        st.text(f"**Coords 2D Denorm**: {coords_2d_denorm}")
        
        # GT Bbox
        gt_bbox = current_row.get('gt_bbox', 'N/A')
        st.text(f"**GT Bbox**: {gt_bbox}")
    
    # Expandable section for all data
    with st.expander("View All Data Fields"):
        st.json(current_row.to_dict())
        
else:
    st.warning("No samples available. Please adjust your filters.")

