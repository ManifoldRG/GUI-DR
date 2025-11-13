import json
import os
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import PIL.Image
import argparse

def main(run_folder: str):
    ##### VISUALIZE BOUNDING BOXES #####
    # Visualize bounding boxes for all images in a trajectory
    # Get the project root directory (parent of mhtml-processor)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    task_folders = [f for f in os.listdir(project_root / run_folder)]

    for task_folder in task_folders:
        # Construct paths
        json_path = project_root / run_folder / task_folder / "trajectory.json"
        output_base_dir = project_root / run_folder / task_folder / "visualizations"
        output_base_dir.mkdir(parents=True, exist_ok=True)
        if not os.path.exists(json_path):
            print(f"Skipping task {task_folder}: trajectory.json not found at {json_path}")
            continue
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
            image_path = project_root / run_folder / task_folder / "screenshots" / screenshot_rel_path.split("/")[-1]
            
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
            
            # Draw target element bounding box rectangle (red)
            rect = patches.Rectangle((x, y), width, height, linewidth=3, edgecolor='red', facecolor='none', label='Target Element')
            ax.add_patch(rect)
            
            # Draw nearest element bounding box if available
            nearest_element = entry.get("nearest_element")
            has_nearest_bbox = False
            nx, ny, nwidth, nheight = 0, 0, 0, 0  # Initialize variables
            if nearest_element and nearest_element.get("bounding_box"):
                nearest_bbox = nearest_element.get("bounding_box")
                if len(nearest_bbox) == 4:
                    nx, ny, nwidth, nheight = nearest_bbox
                    nearest_rect = patches.Rectangle((nx, ny), nwidth, nheight, linewidth=3, edgecolor='blue', facecolor='none', linestyle='--', label='Nearest Element')
                    ax.add_patch(nearest_rect)
                    has_nearest_bbox = True
            
            # Build title with step instruction, nearest element info, and target bbox
            step_instruction = entry.get("step_instruction", "No instruction")
            title = f"Step: {step_instruction}"
            
            # Add target element bounding box
            title += f"\nTarget BBox: [{x:.1f}, {y:.1f}, {width:.1f}, {height:.1f}]"
            
            # Add nearest element info to title if available
            if has_nearest_bbox:
                nearest_text = nearest_element.get("text", "")
                relative_position = nearest_element.get("relative_position", "")
                # Handle both string and list formats
                if isinstance(relative_position, list):
                    if len(relative_position) > 0:
                        relative_pos_str = relative_position[0] if isinstance(relative_position[0], str) else str(relative_position)
                    else:
                        relative_pos_str = "N/A"
                else:
                    relative_pos_str = str(relative_position) if relative_position else "N/A"
                title += f"\nNearest: '{nearest_text}' | Relative Position: {relative_pos_str}"
            
            ax.set_title(title, fontsize=10, pad=10)
            
            # Add compact legend in bottom-left corner (less obstructing)
            # Include text density region if it was drawn
            ax.legend(loc='lower left', fontsize=9, framealpha=0.9, edgecolor='black', fancybox=True)
            
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Visualize bounding boxes for all images in a trajectory')
    parser.add_argument('--run_folder', type=str, required=True, help='The run folder to visualize')
    args = parser.parse_args()
    main(args.run_folder)