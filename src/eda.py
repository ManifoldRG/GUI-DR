import pandas as pd
import io
import PIL.Image
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

# df = pd.read_parquet("test_domain-00000-of-00011-26c55c12cbbcdc8e.parquet")
df = pd.read_parquet("mm_mind2web/data/test_domain-00002-of-00011-f4d93275c87bbd81.parquet")

print(df.info())
print(df.head(1)['action_uid'])
print(df.head(1)['confirmed_task'])
print(df.head(1)['annotation_id'])
print(df['screenshot'].isnull().sum())

# print(df[df['action_uid']=='8121d266-e16a-4265-ac02-a2e6fd7fca16'].head())

# print(df[df['annotation_id']=='277e3468-f8cb-45c6-9e4b-0328066c42d3']['action_uid'].tolist())

image_size_set = set()
for i in range(len(df)):
    try:
        image = PIL.Image.open(io.BytesIO(df['screenshot'][i]['bytes']))
        # image.show()
        image_size_set.add(image.size)
        # print(df['target_action_reprs'][i])
    except Exception as e:
        print(f"Error opening image {i}: {e}")
        continue

print(image_size_set)
min_width = float('inf')
min_height = float('inf')
max_width = 0
max_height = 0
height_set = set()
width_set = set()
for size in image_size_set:
    min_width = min(min_width, size[0])
    min_height = min(min_height, size[1])
    max_width = max(max_width, size[0])
    max_height = max(max_height, size[1])
    height_set.add(size[1])
    width_set.add(size[0])

print(f"Min width: {min_width}, Min height: {min_height}, Max width: {max_width}, Max height: {max_height}")
print(f"Height set: {height_set}, Width set: {width_set}")

# round height set to the nearest 1000
height_set = set(round(height, -3) for height in height_set)
print(f"Height set: {height_set}")
# round width set to the nearest 10
width_set = set(round(width, -1) for width in width_set)
print(f"Width set: {width_set}")

# Visualize bounding boxes for all images in a trajectory
# Get the project root directory (parent of mhtml-processor)
script_dir = Path(__file__).parent
project_root = script_dir.parent


##### VISUALIZE BOUNDING BOXES #####
# Configuration: specify the run folder and JSON filename
import os

run_folder = "run_20251104_225607"
task_folders = [f for f in os.listdir(project_root / run_folder)]

for task_folder in task_folders:
    # Construct paths
    json_path = project_root / run_folder / task_folder / "trajectory.json"
    output_base_dir = project_root / run_folder / task_folder / "visualizations"
    output_base_dir.mkdir(parents=True, exist_ok=True)

    # Load JSON file
    print(f"Loading JSON from: {json_path}")
    with open(json_path, 'r') as f:
        trajectory_data = json.load(f)

    print(f"Found {len(trajectory_data)} entries in trajectory")

    # Loop through each entry in the JSON
    for idx, entry in enumerate(trajectory_data):
        # Get screenshot path from the entry
        screenshot_rel_path = entry.get("screenshot", "")
        if not screenshot_rel_path:
            print(f"Skipping entry {idx}: no screenshot path")
            continue
        
        # Construct full image path (screenshot path is relative to project root)
        image_path = project_root / screenshot_rel_path
        
        if not image_path.exists():
            print(f"Skipping entry {idx}: image not found at {image_path}")
            continue
        
        # Extract bounding box
        bounding_box = entry.get("bounding_box")
        if not bounding_box:
            print(f"Skipping entry {idx}: no bounding box")
            continue
        
        # Format: [x, y, width, height]
        x, y, width, height = bounding_box
        
        # Load image
        image = PIL.Image.open(image_path)
        
        # Create figure and axis
        fig, ax = plt.subplots(1, figsize=(12, 8))
        ax.imshow(image)
        
        # Draw bounding box rectangle
        rect = patches.Rectangle((x, y), width, height, linewidth=3, edgecolor='red', facecolor='none')
        ax.add_patch(rect)
        
        # Add information text
        op = entry.get("op", "UNKNOWN")
        target_text = entry.get("target_element_text", "")
        title = f"{op}: {target_text}\nBounding Box: [{x:.1f}, {y:.1f}, {width:.1f}, {height:.1f}]"
        ax.set_title(title, fontsize=10, pad=10)
        
        # Remove axes
        ax.axis('off')
        
        # Generate output filename from screenshot path
        screenshot_filename = Path(screenshot_rel_path).name
        output_filename = screenshot_filename.replace('.png', '_with_bbox.png')
        output_path = output_base_dir / output_filename
        
        # Save the visualization
        plt.savefig(output_path, bbox_inches='tight', dpi=150)
        print(f"Saved visualization {idx+1}/{len(trajectory_data)}: {output_path}")
        
        # Close the figure to free memory
        plt.close(fig)

print(f"\nAll visualizations saved to: {output_base_dir}")

