#!/usr/bin/env python3
"""
Update Multi-Element Instructions Script

Loads a CSV file and allows updating step_instruction and adding multi_element_instruction
for rows where target_correct=True and nearest_correct=False.
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
import argparse
import subprocess
from random import shuffle


# ============================================================================
# Image Viewer Module (simplified from data_review_helper.py)
# ============================================================================

class ImageViewer:
    """Manages image viewer process and window positioning."""
    
    def __init__(self, window_position: str = "left"):
        self.preview_positioned = False
        self.window_position = window_position
    
    def _refocus_to_terminal(self) -> None:
        """Refocus to terminal/IDE."""
        if sys.platform != "darwin":
            return
        script = '''
        set terminalApps to {"Cursor", "Code", "iTerm2", "iTerm", "Terminal", "Hyper"}
        repeat with appName in terminalApps
            try
                tell application appName to activate
                exit repeat
            end try
        end repeat
        '''
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=0.5,
            check=False
        )
    
    def open_image(self, image_path: Path) -> None:
        """Open image in Preview."""
        if sys.platform != "darwin":
            return
        
        print(f"📷 Opening image: file://{image_path.resolve()}")
        
        escaped_path = str(image_path).replace('\\', '\\\\').replace('"', '\\"')
        
        # Close current document if Preview is already open
        if self.preview_positioned:
            close_script = 'tell application "Preview" to try\n    if (count of windows) > 0 then close front document\nend try'
            try:
                subprocess.run(
                    ["osascript", "-e", close_script],
                    capture_output=True,
                    timeout=0.5,
                    check=False
                )
                time.sleep(0.1)
            except subprocess.TimeoutExpired:
                pass
        
        # Determine window bounds based on position setting
        if self.window_position == "left":
            bounds_script = 'set bounds of front window to {0, 0, screenWidth / 2, screenHeight}'
        elif self.window_position == "right":
            bounds_script = 'set bounds of front window to {screenWidth / 2, 0, screenWidth, screenHeight}'
        elif self.window_position == "max":
            bounds_script = 'set bounds of front window to {0, 0, screenWidth, screenHeight}'
        else:
            bounds_script = 'set bounds of front window to {0, 0, screenWidth / 2, screenHeight}'
        
        # Open and position image
        open_script = '''
        tell application "Preview"
            activate
            set imagePath to POSIX file "''' + escaped_path + '''"
            open imagePath
            
            -- Get screen dimensions and position window immediately
            set screenWidth to (do shell script "echo $(/usr/sbin/system_profiler SPDisplaysDataType | grep Resolution | head -1 | awk '{print $2}')") as integer
            set screenHeight to (do shell script "echo $(/usr/sbin/system_profiler SPDisplaysDataType | grep Resolution | head -1 | awk '{print $4}')") as integer
            
            -- Position window based on setting
            if (count of windows) > 0 then
                ''' + bounds_script + '''
            end if
        end tell
        '''
        
        try:
            subprocess.run(
                ["osascript", "-e", open_script],
                capture_output=True,
                timeout=5,
                check=False
            )
        except subprocess.TimeoutExpired:
            # Fallback: just open the image
            fallback_script = f'''
            tell application "Preview"
                activate
                set imagePath to POSIX file "{escaped_path}"
                open imagePath
            end tell
            '''
            try:
                subprocess.run(
                    ["osascript", "-e", fallback_script],
                    capture_output=True,
                    timeout=3,
                    check=False
                )
            except subprocess.TimeoutExpired:
                print("⚠️  Failed to open image in Preview. Continuing...")
        
        self.preview_positioned = True
        time.sleep(0.2)
        self._refocus_to_terminal()
    
    def close_current(self) -> None:
        """Close Preview windows."""
        if sys.platform == "darwin":
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "Preview" to close every window'],
                    capture_output=True,
                    timeout=0.5,
                    check=False
                )
            except Exception:
                pass
            self.preview_positioned = False


# ============================================================================
# Data Loading and Processing
# ============================================================================

def load_csv(csv_path: Path) -> pd.DataFrame:
    """Load CSV file and return DataFrame."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    # Convert string representations of lists back to lists
    for col in ['target_bbox', 'nearest_bbox', 'relative_position']:
        if col in df.columns:
            df[col] = df[col].apply(_safe_eval)
    
    return df


def _safe_eval(val):
    """Evaluate string representation of list."""
    if pd.isna(val) or val == '':
        return None
    if isinstance(val, str):
        try:
            return eval(val)
        except:
            return val
    return val


def find_trajectory_json(project_root: Path, task_id: str) -> Optional[Path]:
    """Find trajectory.json file for a given task_id."""
    # Search in common locations
    search_paths = [
        project_root / "final_data" / "run_*" / task_id / "trajectory.json",
        project_root / "data_experiments" / "run_*" / task_id / "trajectory.json",
        project_root / "outputs" / "run_*" / task_id / "trajectory.json",
    ]
    
    for pattern in search_paths:
        matches = list(project_root.glob(str(pattern).replace(str(project_root) + "/", "")))
        if matches:
            return matches[0]
    
    # Try direct search in all subdirectories
    for run_folder in project_root.glob("**/run_*"):
        trajectory_path = run_folder / task_id / "trajectory.json"
        if trajectory_path.exists():
            return trajectory_path
    
    return None


def find_image_path(project_root: Path, task_id: str, step_index: int) -> Optional[Path]:
    """Find visualization image path for a given task_id and step_index."""
    # Search for visualization images
    search_paths = [
        project_root / "final_data" / "run_*" / task_id / "visualizations" / f"step_{step_index}_*_with_bbox.png",
        project_root / "data_experiments" / "run_*" / task_id / "visualizations" / f"step_{step_index}_*_with_bbox.png",
        project_root / "outputs" / "run_*" / task_id / "visualizations" / f"step_{step_index}_*_with_bbox.png",
    ]
    
    for pattern in search_paths:
        matches = list(project_root.glob(str(pattern).replace(str(project_root) + "/", "")))
        if matches:
            return matches[0]
    
    # Try direct search
    for run_folder in project_root.glob("**/run_*"):
        vis_dir = run_folder / task_id / "visualizations"
        if vis_dir.exists():
            for img_file in vis_dir.glob(f"step_{step_index}_*_with_bbox.png"):
                return img_file
    
    return None


def load_trajectory_json(trajectory_path: Path) -> List[Dict[str, Any]]:
    """Load trajectory.json file."""
    with open(trajectory_path, 'r') as f:
        return json.load(f)


def save_trajectory_json(trajectory_path: Path, trajectory_data: List[Dict[str, Any]]) -> None:
    """Save trajectory.json file."""
    with open(trajectory_path, 'w') as f:
        json.dump(trajectory_data, f, indent=2)


def update_trajectory_entry(
    trajectory_data: List[Dict[str, Any]],
    step_index: int,
    new_step_instruction: str,
    multi_element_instruction: str
) -> bool:
    """Update trajectory entry with new step_instruction and multi_element_instruction."""
    # Find the entry matching step_index
    for entry in trajectory_data:
        # Try to extract step_index from screenshot path or use index
        entry_step_index = None
        
        screenshot_path = entry.get("screenshot", "")
        if screenshot_path:
            import re
            match = re.search(r'step_(\d+)_', screenshot_path)
            if match:
                entry_step_index = int(match.group(1))
        
        # If no match from screenshot, use array index
        if entry_step_index is None:
            entry_step_index = trajectory_data.index(entry)
        
        if entry_step_index == step_index:
            entry["step_instruction"] = new_step_instruction
            entry["multi_element_instruction"] = multi_element_instruction
            return True
    
    return False


# ============================================================================
# Review Interface
# ============================================================================

def get_user_input(current_step_instruction: str) -> tuple:
    """
    Get user input for updating instructions.
    
    Returns:
        (action, new_step_instruction, multi_element_instruction)
        action: 'update', 'skip', or 'quit'
    """
    print("\n" + "="*80)
    print(f"Current step_instruction: {current_step_instruction}")
    print("="*80)
    print("Options:")
    print("  [Enter] Skip this row")
    print("  [u] Update step_instruction and add multi_element_instruction")
    print("  [q] Quit and save")
    print("="*80)
    
    while True:
        try:
            user_input = input("> ").strip()
            
            if user_input == '':
                return ('skip', None, None)
            elif user_input.lower() == 'q':
                return ('quit', None, None)
            elif user_input.lower() == 'u':
                print("\nEnter new step_instruction (or press Enter to keep current):")
                new_step = input("step_instruction: ").strip()
                if not new_step:
                    new_step = current_step_instruction
                
                print("\nEnter multi_element_instruction:")
                multi_element = input("multi_element_instruction: ").strip()
                if not multi_element:
                    print("⚠️  multi_element_instruction cannot be empty. Skipping update.")
                    return ('skip', None, None)
                
                return ('update', new_step, multi_element)
            else:
                print(f"Invalid input '{user_input}'. Use: Enter (skip), u (update), or q (quit)")
        except EOFError:
            return ('quit', None, None)
        except KeyboardInterrupt:
            print("\n")
            return ('quit', None, None)


# ============================================================================
# Main Processing
# ============================================================================

def process_csv(
    csv_path: Path,
    project_root: Path,
    window_position: str = "left"
) -> None:
    """Process CSV file and update trajectory.json files."""
    # Load CSV
    print(f"Loading CSV: {csv_path}")
    df = load_csv(csv_path)
    print(f"Loaded {len(df)} rows")
    
    # Filter rows: target_correct == True and nearest_correct == False
    mask = (df['target_correct'] == True) & (df['nearest_correct'] == False)
    filtered_df = df[mask].copy()
    
    print(f"Found {len(filtered_df)} rows to review (target_correct=True, nearest_correct=False)")
    
    if len(filtered_df) == 0:
        print("No rows to review. Exiting.")
        return
    
    # Convert to list of (index, row) tuples and shuffle
    rows_to_process = list(filtered_df.iterrows())
    shuffle(rows_to_process)
    print(f"Shuffled {len(rows_to_process)} rows for random review order")
    
    # Track processed (task_id, step_index) combinations to avoid duplicates
    processed_combinations = set()
    
    # Initialize image viewer
    image_viewer = ImageViewer(window_position=window_position)
    
    updated_count = 0
    skipped_count = 0
    
    try:
        for row_num, (idx, row) in enumerate(rows_to_process, 1):
            task_id = row['task_id']
            step_index = int(row['step_index'])
            step_instruction = row['step_instruction']
            
            # Skip if we've already processed this (task_id, step_index) combination
            combination = (task_id, step_index)
            if combination in processed_combinations:
                print(f"\n{'='*80}")
                print(f"Row {row_num}/{len(rows_to_process)} - Already processed, skipping")
                print(f"Task ID: {task_id}, Step Index: {step_index}")
                print("="*80)
                skipped_count += 1
                continue
            
            # Mark as processed
            processed_combinations.add(combination)
            
            print(f"\n{'='*80}")
            print(f"Row {row_num}/{len(rows_to_process)}")
            print(f"Task ID: {task_id}")
            print(f"Step Index: {step_index}")
            print(f"Step Instruction: {step_instruction}")
            print(f"Target BBox: {row['target_bbox']}")
            if row['nearest_bbox']:
                print(f"Nearest BBox: {row['nearest_bbox']}")
                print(f"Relative Position: {row['relative_position']}")
            print("="*80)
            
            # Find image path
            image_path = find_image_path(project_root, task_id, step_index)
            if image_path and image_path.exists():
                image_viewer.open_image(image_path)
            else:
                print(f"⚠️  Image not found for task {task_id}, step {step_index}")
            
            # Get user input
            action, new_step_instruction, multi_element_instruction = get_user_input(step_instruction)
            
            if action == 'quit':
                print("\nQuitting. Saving progress...")
                break
            elif action == 'skip':
                skipped_count += 1
                print("⏭️  Skipped")
                continue
            elif action == 'update':
                # Find trajectory.json
                trajectory_path = find_trajectory_json(project_root, task_id)
                if not trajectory_path:
                    print(f"⚠️  trajectory.json not found for task {task_id}")
                    skipped_count += 1
                    continue
                
                # Load and update trajectory.json
                trajectory_data = load_trajectory_json(trajectory_path)
                if not update_trajectory_entry(trajectory_data, step_index, new_step_instruction, multi_element_instruction):
                    print(f"⚠️  Could not find step_index {step_index} in trajectory.json")
                    skipped_count += 1
                    continue
                
                # Save trajectory.json
                save_trajectory_json(trajectory_path, trajectory_data)
                print(f"✓ Updated trajectory.json: {trajectory_path}")
                
                # Update CSV: set both target_correct and nearest_correct to True
                df.at[idx, 'target_correct'] = True
                df.at[idx, 'nearest_correct'] = True
                updated_count += 1
                print(f"✓ Updated CSV row: set target_correct=True, nearest_correct=True")
                
                # Save CSV after each update
                df.to_csv(csv_path, index=False)
                print(f"✓ Saved CSV: {csv_path}")
    
    except KeyboardInterrupt:
        print("\n\nInterrupted. Saving progress...")
    
    finally:
        image_viewer.close_current()
        
        # Final save
        df.to_csv(csv_path, index=False)
        
        print(f"\n{'='*80}")
        print("Summary:")
        print(f"  Updated: {updated_count}")
        print(f"  Skipped: {skipped_count}")
        print(f"  CSV saved to: {csv_path}")
        print("="*80)


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Update step_instruction and add multi_element_instruction for rows where target_correct=True and nearest_correct=False'
    )
    parser.add_argument(
        '--csv_path',
        type=str,
        required=True,
        help='Path to CSV file (e.g., "data/run_20251112_004959_test_domain_original_reviews.csv")'
    )
    parser.add_argument(
        '--project_root',
        type=str,
        default=None,
        help='Project root directory. Defaults to parent of script directory.'
    )
    parser.add_argument(
        '--window_position',
        type=str,
        choices=['left', 'right', 'max'],
        default='left',
        help='Preview window position: "left" (left half), "right" (right half), or "max" (maximized). Default: left'
    )
    
    args = parser.parse_args()
    
    # Determine project root
    script_dir = Path(__file__).parent
    if args.project_root:
        project_root = Path(args.project_root)
    else:
        project_root = script_dir.parent
    
    # Resolve CSV path
    csv_path = Path(args.csv_path)
    if not csv_path.is_absolute():
        csv_path = project_root / csv_path
    
    process_csv(csv_path, project_root, args.window_position)


if __name__ == "__main__":
    main()

