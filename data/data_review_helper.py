#!/usr/bin/env python3
"""
Data Review Helper Script

Manually review visualization images and log correctness of target/nearest element labels.
Designed for fast review: ~1s per image inspection, ~0.5s for logging.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import pandas as pd
import argparse
from random import shuffle


# ============================================================================
# Scanner Module
# ============================================================================

def scan_run_folder(run_folder_path: Path) -> List[Tuple[str, Path]]:
    """
    Scan run_folder for task_id subfolders that contain trajectory.json.
    
    Returns:
        List of (task_id, task_folder_path) tuples
    """
    valid_tasks = []
    
    if not run_folder_path.exists():
        print(f"Error: Run folder does not exist: {run_folder_path}")
        return valid_tasks
    
    for item in run_folder_path.iterdir():
        if item.is_dir():
            trajectory_path = item / "trajectory.json"
            if trajectory_path.exists():
                valid_tasks.append((item.name, item))
    
    return valid_tasks


def extract_split_from_run_folder(run_folder_name: str) -> str:
    """
    Extract split from run folder name.
    
    Examples:
        run_20251112_004959_test_domain_original -> test_domain_original
        run_20251112_005144_test_domain_precision -> test_domain_precision
        run_20251112_005559_train_precision -> train_precision
    
    Pattern: run_<timestamp>_<split>
    """
    # Remove 'run_' prefix
    if not run_folder_name.startswith('run_'):
        return "unknown"
    
    # Remove 'run_' and split by '_'
    parts = run_folder_name[4:].split('_')
    
    # First two parts are timestamp (YYYYMMDD_HHMMSS)
    # Everything after is the split
    if len(parts) >= 3:
        return '_'.join(parts[2:])
    else:
        return "unknown"


# ============================================================================
# Trajectory Parser Module
# ============================================================================

def parse_trajectory(trajectory_path: Path) -> List[Dict[str, Any]]:
    """
    Parse trajectory.json and extract step data.
    
    Returns:
        List of step dictionaries with:
        - step_index (inferred from array index or screenshot filename)
        - step_instruction
        - target_bbox
        - nearest_bbox
        - relative_position
    """
    with open(trajectory_path, 'r') as f:
        trajectory_data = json.load(f)
    
    parsed_steps = []
    
    for idx, entry in enumerate(trajectory_data):
        # Try to extract step_index from screenshot filename
        screenshot_path = entry.get("screenshot", "")
        step_index = None
        
        if screenshot_path:
            # Extract step number from filename like "step_4_type.png"
            match = re.search(r'step_(\d+)_', screenshot_path)
            if match:
                step_index = int(match.group(1))
        
        # Fallback to array index if not found
        if step_index is None:
            step_index = idx
        
        step_data = {
            'step_index': step_index,
            'step_instruction': entry.get("step_instruction", ""),
            'target_bbox': entry.get("bounding_box", []),
            'nearest_bbox': None,
            'relative_position': None,
        }
        
        # Extract nearest element data
        nearest_element = entry.get("nearest_element")
        if nearest_element:
            step_data['nearest_bbox'] = nearest_element.get("bounding_box")
            step_data['relative_position'] = nearest_element.get("relative_position", [])
        
        parsed_steps.append(step_data)
    
    return parsed_steps


# ============================================================================
# Image Manager Module
# ============================================================================

def get_visualization_images(task_folder: Path) -> List[Tuple[int, Path]]:
    """
    Get all visualization images from task folder, sorted by step_index.
    
    Returns:
        List of (step_index, image_path) tuples, sorted by step_index
    """
    visualizations_dir = task_folder / "visualizations"
    
    if not visualizations_dir.exists():
        return []
    
    images = []
    
    for image_file in visualizations_dir.glob("*_with_bbox.png"):
        # Extract step_index from filename like "step_4_type_with_bbox.png"
        match = re.search(r'step_(\d+)_', image_file.name)
        if match:
            step_index = int(match.group(1))
            images.append((step_index, image_file))
    
    # Sort by step_index
    images.sort(key=lambda x: x[0])
    
    return images


# ============================================================================
# Review Interface Module
# ============================================================================

class ImageViewer:
    """Manages image viewer process to prevent multiple windows."""
    
    def __init__(self):
        self.current_process = None
        self.preview_positioned = False  # Track if Preview is already positioned
    
    def _position_preview(self) -> None:
        """Position Preview window on left half of screen."""
        position_script = '''
        tell application "Preview"
            if (count of windows) > 0 then
                activate
                -- Get screen dimensions from shell
                set screenWidth to (do shell script "echo $(/usr/sbin/system_profiler SPDisplaysDataType | grep Resolution | head -1 | awk '{print $2}')") as integer
                set screenHeight to (do shell script "echo $(/usr/sbin/system_profiler SPDisplaysDataType | grep Resolution | head -1 | awk '{print $4}')") as integer
                -- Position window on left half
                set bounds of front window to {0, 0, screenWidth / 2, screenHeight}
            end if
        end tell
        '''
        
        subprocess.run(
            ["osascript", "-e", position_script],
            capture_output=True,
            timeout=1
        )
        self.preview_positioned = True
    
    def _refocus_to_terminal(self) -> None:
        """Refocus to terminal/IDE."""
        refocus_script = '''
        -- Refocus to terminal/IDE
        try
            tell application "Cursor" to activate
        on error
            try
                tell application "Visual Studio Code" to activate
            on error
                try
                    tell application "iTerm" to activate
                on error
                    try
                        tell application "Terminal" to activate
                    on error
                        -- Try to find terminal via System Events
                        tell application "System Events"
                            set terminalApps to {"Cursor", "Code", "iTerm2", "Terminal", "Hyper"}
                            repeat with appName in terminalApps
                                try
                                    tell application appName to activate
                                    exit repeat
                                end try
                            end repeat
                        end tell
                    end try
                end try
            end try
        end try
        '''
        
        subprocess.run(
            ["osascript", "-e", refocus_script],
            capture_output=True,
            timeout=0.5
        )
    
    def open_image(self, image_path: Path) -> None:
        """Open image in Preview, reusing existing window if possible."""
        if sys.platform == "darwin":  # macOS
            # Log the image path for debugging (absolute path for clickability)
            abs_path = image_path.resolve()
            print(f"📷 Opening image: file://{abs_path}")
            
            # Escape the path properly for AppleScript
            escaped_path = str(image_path).replace('\\', '\\\\').replace('"', '\\"')
            
            # Strategy: Close current document first (with timeout), then open new one
            if self.preview_positioned:
                # Preview is already open - close current doc first
                close_script = '''
                tell application "Preview"
                    try
                        if (count of windows) > 0 then
                            close front document
                        end if
                    end try
                end tell
                '''
                
                # Run close with a short timeout to ensure it completes
                try:
                    subprocess.run(
                        ["osascript", "-e", close_script],
                        capture_output=True,
                        timeout=0.5,
                        check=False
                    )
                except subprocess.TimeoutExpired:
                    pass  # Continue even if close times out
                
                # Small delay to ensure close completes before opening new image
                time.sleep(0.1)
            
            # Open the new image and position it immediately in one AppleScript call
            # Use string concatenation to avoid f-string issues with curly braces
            open_and_position_script = '''
            tell application "Preview"
                activate
                set imagePath to POSIX file "''' + escaped_path + '''"
                open imagePath
                
                -- Get screen dimensions and position window immediately
                set screenWidth to (do shell script "echo $(/usr/sbin/system_profiler SPDisplaysDataType | grep Resolution | head -1 | awk '{print $2}')") as integer
                set screenHeight to (do shell script "echo $(/usr/sbin/system_profiler SPDisplaysDataType | grep Resolution | head -1 | awk '{print $4}')") as integer
                
                -- Position window on left half immediately after opening
                if (count of windows) > 0 then
                    set bounds of front window to {0, 0, screenWidth / 2, screenHeight}
                end if
            end tell
            '''
            
            try:
                subprocess.run(
                    ["osascript", "-e", open_and_position_script],
                    capture_output=True,
                    timeout=2,
                    check=False
                )
            except subprocess.TimeoutExpired:
                # Fallback: open and position separately
                subprocess.run(
                    ["open", "-a", "Preview", str(image_path)],
                    check=False
                )
                time.sleep(0.1)  # Delay for window to appear
                self._position_preview()
            
            # Mark as positioned
            self.preview_positioned = True
            
            # Small delay to ensure image is loaded before refocusing
            time.sleep(0.05)
            
            # Refocus to terminal immediately
            self._refocus_to_terminal()
            
        elif sys.platform == "win32":  # Windows
            self.current_process = subprocess.Popen(["start", str(image_path)], shell=True)
        else:  # Linux
            self.current_process = subprocess.Popen(["xdg-open", str(image_path)])
    
    def close_current(self) -> None:
        """Close the current image viewer window (only called on quit)."""
        if sys.platform == "darwin":  # macOS
            # Close Preview windows using AppleScript
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "Preview" to close every window'],
                    capture_output=True,
                    timeout=0.5
                )
            except Exception:
                pass
            self.preview_positioned = False
        elif sys.platform == "win32":  # Windows
            if self.current_process:
                try:
                    self.current_process.terminate()
                except Exception:
                    pass
                self.current_process = None
        else:  # Linux
            if self.current_process:
                try:
                    self.current_process.terminate()
                except Exception:
                    pass
                self.current_process = None


# Global image viewer instance
_image_viewer = ImageViewer()


def open_image(image_path: Path) -> None:
    """Open image in system default viewer, closing previous one if exists."""
    _image_viewer.open_image(image_path)


def close_image() -> None:
    """Close the current image viewer window."""
    _image_viewer.close_current()


class QuitReview(Exception):
    """Custom exception to signal user wants to quit the review."""
    pass


def get_user_input(step_data: Dict[str, Any]) -> Tuple[Optional[bool], Optional[bool], bool]:
    """
    Display step info and get user input.
    
    Returns:
        (target_correct, nearest_correct, skipped) tuple
    
    Raises:
        QuitReview: If user wants to quit (q or Ctrl+C)
        KeyboardInterrupt: If Ctrl+C is pressed (re-raised)
    """
    print("\n" + "="*80)
    print(f"Step {step_data['step_index']}: {step_data['step_instruction']}")
    print(f"Target BBox: {step_data['target_bbox']}")
    if step_data['nearest_bbox']:
        print(f"Nearest BBox: {step_data['nearest_bbox']}")
        print(f"Relative Position: {step_data['relative_position']}")
    else:
        print("Nearest Element: None")
    print("="*80)
    print("Input: [w] both correct | [a] target correct | [d] nearest correct | [e] both wrong | [s] skip | [q] quit")
    
    while True:
        try:
            user_input = input("> ").strip().lower()
            
            if user_input == 'w':
                return (True, True, False)
            elif user_input == 'a':
                return (True, False, False)
            elif user_input == 'd':
                return (False, True, False)
            elif user_input == 'e':
                return (False, False, False)
            elif user_input == 's':
                return (None, None, True)
            elif user_input == 'q':
                raise QuitReview("User requested to quit")
            else:
                print("Invalid input. Use: w, a, d, e, s, or q")
        except EOFError:
            # EOF (Ctrl+D) - treat as quit
            raise QuitReview("EOF received, quitting")
        except KeyboardInterrupt:
            # Ctrl+C - re-raise to be caught by outer handler
            print("\n")
            raise


# ============================================================================
# Data Manager Module
# ============================================================================

class DataManager:
    """Manages DataFrame and CSV persistence."""
    
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.df = self._load_existing()
    
    def _load_existing(self) -> pd.DataFrame:
        """Load existing CSV if it exists."""
        if self.csv_path.exists():
            df = pd.read_csv(self.csv_path)
            # Convert list columns back from string
            for col in ['target_bbox', 'nearest_bbox', 'relative_position']:
                if col in df.columns:
                    df[col] = df[col].apply(self._safe_eval)
            return df
        else:
            return pd.DataFrame(columns=[
                'split',
                'task_id',
                'step_index',
                'step_instruction',
                'target_bbox',
                'nearest_bbox',
                'relative_position',
                'target_correct',
                'nearest_correct',
                'skipped'
            ])
    
    def _safe_eval(self, val):
        """Safely evaluate string representation of list."""
        if pd.isna(val) or val == '':
            return None
        if isinstance(val, str):
            try:
                return eval(val)  # Safe for our use case (JSON-like lists)
            except:
                return val
        return val
    
    def is_reviewed(self, task_id: str, step_index: int) -> bool:
        """Check if a task/step combination has already been reviewed."""
        if self.df.empty:
            return False
        
        mask = (self.df['task_id'] == task_id) & (self.df['step_index'] == step_index)
        return mask.any()
    
    def add_review(
        self,
        split: str,
        task_id: str,
        step_index: int,
        step_instruction: str,
        target_bbox: List,
        nearest_bbox: Optional[List],
        relative_position: Optional[List],
        target_correct: Optional[bool],
        nearest_correct: Optional[bool],
        skipped: bool
    ) -> None:
        """Add or update a review record."""
        # Convert lists to strings for CSV storage
        target_bbox_str = str(target_bbox) if target_bbox else None
        nearest_bbox_str = str(nearest_bbox) if nearest_bbox else None
        relative_position_str = str(relative_position) if relative_position else None
        
        # Check if record exists
        mask = (self.df['task_id'] == task_id) & (self.df['step_index'] == step_index)
        
        new_row = {
            'split': split,
            'task_id': task_id,
            'step_index': step_index,
            'step_instruction': step_instruction,
            'target_bbox': target_bbox_str,
            'nearest_bbox': nearest_bbox_str,
            'relative_position': relative_position_str,
            'target_correct': target_correct,
            'nearest_correct': nearest_correct,
            'skipped': skipped
        }
        
        if mask.any():
            # Update existing row
            self.df.loc[mask, list(new_row.keys())] = list(new_row.values())
        else:
            # Add new row
            self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
    
    def save(self) -> None:
        """Save DataFrame to CSV."""
        self.df.to_csv(self.csv_path, index=False)


# ============================================================================
# Review Controller (Main)
# ============================================================================

def review_run_folder(run_folder: str, output_csv: Optional[str] = None):
    """
    Main review function.
    
    Args:
        run_folder: Path to run folder (e.g., "final_data/run_20251112_004959_test_domain_original")
        output_csv: Optional path to output CSV file. Defaults to <run_folder>_reviews.csv
    """
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    run_folder_path = project_root / run_folder
    
    if not run_folder_path.exists():
        print(f"Error: Run folder does not exist: {run_folder_path}")
        return
    
    # Extract split from run folder name
    run_folder_name = run_folder_path.name
    split = extract_split_from_run_folder(run_folder_name)
    print(f"Detected split: {split}")
    
    # Determine output CSV path
    if output_csv is None:
        csv_filename = f"{run_folder_name}_reviews.csv"
        csv_path = project_root / "scripts" / csv_filename
    else:
        csv_path = Path(output_csv)
        if not csv_path.is_absolute():
            csv_path = project_root / csv_path
    
    print(f"Output CSV: {csv_path}")
    
    # Initialize Data Manager
    data_manager = DataManager(csv_path)
    total_reviewed_all_runs = len(data_manager.df) if not data_manager.df.empty else 0
    print(f"Loaded {total_reviewed_all_runs} existing reviews from CSV")
    
    # Scan for valid tasks
    print(f"\nScanning {run_folder_path}...")
    valid_tasks = scan_run_folder(run_folder_path)
    print(f"Found {len(valid_tasks)} tasks with trajectory.json")
    
    if not valid_tasks:
        print("No valid tasks found. Exiting.")
        return
    
    # Count total images in this run folder
    total_images_in_run = 0
    for task_id, task_folder in valid_tasks:
        images = get_visualization_images(task_folder)
        total_images_in_run += len(images)
    
    print(f"Total images in this run: {total_images_in_run}")
    
    # Shuffle for random sampling
    shuffle(valid_tasks)
    
    # Start session timing
    session_start_time = time.time()
    
    # Review each task
    total_reviewed = 0
    total_skipped_existing = 0
    
    try:
        for task_id, task_folder in valid_tasks:
            print(f"\n{'='*80}")
            print(f"Task: {task_id}")
            print(f"{'='*80}")
            
            # Parse trajectory
            trajectory_path = task_folder / "trajectory.json"
            steps = parse_trajectory(trajectory_path)
            
            # Get visualization images
            images = get_visualization_images(task_folder)
            
            if not images:
                print(f"No visualization images found for task {task_id}")
                continue
            
            # Create step lookup by step_index
            step_lookup = {step['step_index']: step for step in steps}
            
            # Review each image
            for step_index, image_path in images:
                # Check if already reviewed
                if data_manager.is_reviewed(task_id, step_index):
                    total_skipped_existing += 1
                    continue
                
                # Get step data
                step_data = step_lookup.get(step_index)
                if not step_data:
                    print(f"Warning: No step data found for step_index {step_index}")
                    continue
                
                # Start timing for this step
                step_start_time = time.time()
                
                # Open image (reuses existing Preview window)
                open_image(image_path)
                
                try:
                    # Get user input
                    target_correct, nearest_correct, skipped = get_user_input(step_data)
                except QuitReview:
                    # User wants to quit
                    close_image()  # Close image before quitting
                    session_elapsed = time.time() - session_start_time
                    print("\nQuitting review. Saving progress...")
                    data_manager.save()
                    print(f"Progress saved to {csv_path}")
                    print(f"\nSession Summary:")
                    print(f"  Reviewed this run: {total_reviewed} / {total_images_in_run}")
                    print(f"  Total reviewed (all runs): {total_reviewed_all_runs + total_reviewed}")
                    print(f"  Skipped (existing): {total_skipped_existing}")
                    print(f"  Session time: {session_elapsed:.1f}s ({session_elapsed/60:.1f} min)")
                    if total_reviewed > 0:
                        print(f"  Avg time per step: {session_elapsed/total_reviewed:.2f}s")
                    return
                
                # Don't close image - keep Preview open for next image
                
                if skipped:
                    # User wants to skip this image
                    data_manager.add_review(
                        split=split,
                        task_id=task_id,
                        step_index=step_index,
                        step_instruction=step_data['step_instruction'],
                        target_bbox=step_data['target_bbox'],
                        nearest_bbox=step_data['nearest_bbox'],
                        relative_position=step_data['relative_position'],
                        target_correct=None,
                        nearest_correct=None,
                        skipped=True
                    )
                    data_manager.save()
                    step_elapsed = time.time() - step_start_time
                    session_elapsed = time.time() - session_start_time
                    print(f"⏱️  Step time: {step_elapsed:.2f}s | Session: {session_elapsed:.1f}s")
                    continue
                
                # Record review
                data_manager.add_review(
                    split=split,
                    task_id=task_id,
                    step_index=step_index,
                    step_instruction=step_data['step_instruction'],
                    target_bbox=step_data['target_bbox'],
                    nearest_bbox=step_data['nearest_bbox'],
                    relative_position=step_data['relative_position'],
                    target_correct=target_correct,
                    nearest_correct=nearest_correct,
                    skipped=False
                )
                
                # Save immediately
                data_manager.save()
                total_reviewed += 1
                
                # Calculate timing
                step_elapsed = time.time() - step_start_time
                session_elapsed = time.time() - session_start_time
                avg_time = session_elapsed / total_reviewed if total_reviewed > 0 else 0
                
                print(f"✓ Saved review | Step: {step_elapsed:.2f}s | Session: {session_elapsed:.1f}s | Avg: {avg_time:.2f}s\n\n")
                print(f"  Progress: {total_reviewed}/{total_images_in_run} this run | {total_reviewed_all_runs + total_reviewed} total (all runs)")
                print(f"\n{'='*80}\n")

    except KeyboardInterrupt:
        close_image()  # Close image before quitting
        session_elapsed = time.time() - session_start_time
        print("\n\nReview interrupted (Ctrl+C). Saving progress...")
        data_manager.save()
        print(f"Progress saved to {csv_path}")
        print(f"\nSession Summary:")
        print(f"  Reviewed this run: {total_reviewed} / {total_images_in_run}")
        print(f"  Total reviewed (all runs): {total_reviewed_all_runs + total_reviewed}")
        print(f"  Skipped (existing): {total_skipped_existing}")
        print(f"  Session time: {session_elapsed:.1f}s ({session_elapsed/60:.1f} min)")
        if total_reviewed > 0:
            print(f"  Avg time per step: {session_elapsed/total_reviewed:.2f}s")
        return
    
    session_elapsed = time.time() - session_start_time
    print(f"\n{'='*80}")
    print("Review complete!")
    print(f"\nSession Summary:")
    print(f"  Reviewed this run: {total_reviewed} / {total_images_in_run}")
    print(f"  Total reviewed (all runs): {total_reviewed_all_runs + total_reviewed}")
    print(f"  Skipped (existing): {total_skipped_existing}")
    print(f"  Session time: {session_elapsed:.1f}s ({session_elapsed/60:.1f} min)")
    if total_reviewed > 0:
        print(f"  Avg time per step: {session_elapsed/total_reviewed:.2f}s")
    print(f"\nResults saved to: {csv_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Manually review visualization images and log correctness of labels'
    )
    parser.add_argument(
        '--run_folder',
        type=str,
        default="final_data/run_20251112_004959_test_domain_original",
        help='Path to run folder (e.g., "final_data/run_20251112_004959_test_domain_original")'
    )
    parser.add_argument(
        '--output_csv',
        type=str,
        default="data/run_20251112_004959_test_domain_original_reviews.csv",
        help='Optional path to output CSV file. Defaults to <run_folder>_reviews.csv in scripts/'
    )
    
    args = parser.parse_args()
    review_run_folder(args.run_folder, args.output_csv)


if __name__ == "__main__":
    main()

