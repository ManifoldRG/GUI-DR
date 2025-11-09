import json
import os
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import PIL.Image


##### VISUALIZE BOUNDING BOXES #####
# Visualize bounding boxes for all images in a trajectory
# Get the project root directory (parent of mhtml-processor)
script_dir = Path(__file__).parent
project_root = script_dir.parent

# Configuration: specify the run folder and JSON filename
run_folder = "run_20251107_124217_train"
task_folders = [f for f in os.listdir(project_root / "outputs" / run_folder)]

for task_folder in task_folders:
    # Construct paths
    json_path = project_root / "outputs" / run_folder / task_folder / "trajectory.json"
    output_base_dir = project_root / "outputs" / run_folder / task_folder / "visualizations"
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
