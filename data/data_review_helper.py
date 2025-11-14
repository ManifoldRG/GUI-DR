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
from typing import List, Optional, Tuple, Dict, Any, NamedTuple
import pandas as pd
import argparse
from random import shuffle


# ============================================================================
# Constants
# ============================================================================

INPUT_PROMPT = "Input: [w] both correct | [a] target correct | [d] nearest correct | [s] reject | [q] skip | [z] undo/back"
REVIEW_HISTORY_ENTRY = Tuple[str, int, Path, Dict[str, Any], bool]  # (task_id, step_index, image_path, step_data, was_rejected)
UNKNOWN_SPLIT = "unknown"


# ============================================================================
# Data Models
# ============================================================================

class ReviewResult(NamedTuple):
    """Result of a review action."""
    target_correct: Optional[bool]
    nearest_correct: Optional[bool]
    rejected: bool
    skipped: bool = False
    is_undo: bool = False


class StepInfo(NamedTuple):
    """Information about a step being reviewed."""
    task_id: str
    step_index: int
    image_path: Path
    step_data: Dict[str, Any]
    start_time: float


# ============================================================================
# Scanner Module
# ============================================================================

def scan_run_folder(run_folder_path: Path) -> List[Tuple[str, Path]]:
    """Scan run_folder for task_id subfolders that contain trajectory.json."""
    if not run_folder_path.exists():
        raise FileNotFoundError(f"Run folder does not exist: {run_folder_path}")
    
    valid_tasks = []
    for item in run_folder_path.iterdir():
        if item.is_dir() and (item / "trajectory.json").exists():
            valid_tasks.append((item.name, item))
    
    return valid_tasks


def extract_split_from_run_folder(run_folder_name: str) -> str:
    """
    Extract split from run folder name.
    
    Examples:
        run_20251112_004959_test_domain_original -> test_domain_original
        run_20251112_005144_test_domain_precision -> test_domain_precision
    """
    if not run_folder_name.startswith('run_'):
        return UNKNOWN_SPLIT
    
    parts = run_folder_name[4:].split('_')
    return '_'.join(parts[2:]) if len(parts) >= 3 else UNKNOWN_SPLIT


# ============================================================================
# Trajectory Parser Module
# ============================================================================

def parse_trajectory(trajectory_path: Path) -> List[Dict[str, Any]]:
    """Parse trajectory.json and extract step data."""
    with open(trajectory_path, 'r') as f:
        trajectory_data = json.load(f)
    
    parsed_steps = []
    for idx, entry in enumerate(trajectory_data):
        # Extract step_index from screenshot filename
        step_index = idx
        screenshot_path = entry.get("screenshot", "")
        if screenshot_path:
            match = re.search(r'step_(\d+)_', screenshot_path)
            if match:
                step_index = int(match.group(1))
        
        step_data = {
            'step_index': step_index,
            'step_instruction': entry.get("step_instruction", ""),
            'target_bbox': entry.get("bounding_box", []),
            'nearest_bbox': None,
            'relative_position': None,
        }
        
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
    """Get all visualization images from task folder, sorted by step_index."""
    visualizations_dir = task_folder / "visualizations"
    if not visualizations_dir.exists():
        return []
    
    images = []
    for image_file in visualizations_dir.glob("*_with_bbox.png"):
        match = re.search(r'step_(\d+)_', image_file.name)
        if match:
            images.append((int(match.group(1)), image_file))
    
    images.sort(key=lambda x: x[0])
    return images


# ============================================================================
# Image Viewer Module
# ============================================================================

class ImageViewer:
    """Manages image viewer process and window positioning."""
    
    def __init__(self, window_position: str = "left"):
        self.preview_positioned = False
        self.window_position = window_position  # "left", "right", or "max"
    
    def _refocus_to_terminal(self) -> None:
        """Refocus to terminal/IDE."""
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
        """Open image in Preview, positioning window based on window_position setting."""
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
            # Default to left if invalid
            bounds_script = 'set bounds of front window to {0, 0, screenWidth / 2, screenHeight}'
        
        # Open and position image - calculate screen dimensions inside AppleScript
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
                timeout=5,  # Increased timeout for system_profiler
                check=False
            )
        except subprocess.TimeoutExpired:
            # If timeout, at least try to open the image without positioning
            print("⚠️  Window positioning timed out, opening image without positioning...")
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
        time.sleep(0.2)  # Give Preview time to position window
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


_image_viewer: Optional[ImageViewer] = None


def init_image_viewer(window_position: str = "left") -> None:
    """Initialize the global image viewer with window position setting."""
    global _image_viewer
    _image_viewer = ImageViewer(window_position=window_position)


def open_image(image_path: Path) -> None:
    """Open image in system default viewer."""
    if _image_viewer is None:
        init_image_viewer()  # Default to left if not initialized
    _image_viewer.open_image(image_path)


def close_image() -> None:
    """Close the current image viewer window."""
    if _image_viewer is not None:
        _image_viewer.close_current()


# ============================================================================
# Review Interface Module
# ============================================================================

class QuitReview(Exception):
    """Exception to signal user wants to quit the review."""
    pass


def get_user_input(step_data: Dict[str, Any]) -> ReviewResult:
    """Display step info and get user input."""
    print("\n" + "="*80)
    print(f"Step {step_data['step_index']}: {step_data['step_instruction']}")
    print(f"Target BBox: {step_data['target_bbox']}")
    if step_data['nearest_bbox']:
        print(f"Nearest BBox: {step_data['nearest_bbox']}")
        print(f"Relative Position: {step_data['relative_position']}")
    else:
        print("Nearest Element: None")
    print("="*80)
    print(INPUT_PROMPT)
    
    while True:
        try:
            user_input = input("> ").strip().lower()
            
            if user_input == 'w':
                return ReviewResult(True, True, False, False)
            elif user_input == 'a':
                return ReviewResult(True, False, False, False)
            elif user_input == 'd':
                return ReviewResult(False, True, False, False)
            elif user_input == 's':
                return ReviewResult(None, None, True, False)  # rejected
            elif user_input == 'q':
                return ReviewResult(None, None, False, True)  # skipped
            elif user_input == 'z':
                return ReviewResult(None, None, False, False, is_undo=True)
            
            print(f"Invalid input '{user_input}'. Use: w, a, d, s (reject), q (skip), or z (undo)")
        except EOFError:
            raise QuitReview("EOF received, quitting")
        except KeyboardInterrupt:
            print("\n")
            raise


# ============================================================================
# Data Manager Module
# ============================================================================

class DataManager:
    """Manages DataFrame and CSV persistence."""
    
    COLUMNS = [
        'split', 'task_id', 'step_index', 'step_instruction',
        'target_bbox', 'nearest_bbox', 'relative_position',
        'target_correct', 'nearest_correct', 'rejected'
    ]
    
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.df = self._load_existing()
    
    def _load_existing(self) -> pd.DataFrame:
        """Load existing CSV if it exists."""
        if not self.csv_path.exists():
            return pd.DataFrame(columns=self.COLUMNS)
        
        df = pd.read_csv(self.csv_path)
        for col in ['target_bbox', 'nearest_bbox', 'relative_position']:
            df[col] = df[col].apply(self._safe_eval)
        return df
    
    @staticmethod
    def _safe_eval(val):
        """Evaluate string representation of list."""
        if pd.isna(val) or val == '':
            return None
        if isinstance(val, str):
            return eval(val)
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
        rejected: bool
    ) -> None:
        """Add or update a review record."""
        new_row = {
            'split': split,
            'task_id': task_id,
            'step_index': step_index,
            'step_instruction': step_instruction,
            'target_bbox': str(target_bbox) if target_bbox else None,
            'nearest_bbox': str(nearest_bbox) if nearest_bbox else None,
            'relative_position': str(relative_position) if relative_position else None,
            'target_correct': target_correct,
            'nearest_correct': nearest_correct,
            'rejected': rejected
        }
        
        mask = (self.df['task_id'] == task_id) & (self.df['step_index'] == step_index)
        if mask.any():
            self.df.loc[mask, list(new_row.keys())] = list(new_row.values())
        else:
            self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
    
    def save(self) -> None:
        """Save DataFrame to CSV."""
        self.df.to_csv(self.csv_path, index=False)
    
    def count_both_correct(self) -> int:
        """Count samples where both target and nearest are correct."""
        if self.df.empty:
            return 0
        mask = (
            (self.df['target_correct'] == True) &
            (self.df['nearest_correct'] == True) &
            (self.df['rejected'] == False)
        )
        return mask.sum()
    
    def count_target_correct(self) -> int:
        """Count samples where target is correct."""
        if self.df.empty:
            return 0
        mask = (
            (self.df['target_correct'] == True) &
            (self.df['rejected'] == False)
        )
        return mask.sum()
    
    def count_reviewed(self) -> int:
        """Count all reviews (including rejected items)."""
        if self.df.empty:
            return 0
        return len(self.df)


# ============================================================================
# Review Session Module
# ============================================================================

class ReviewSession:
    """Manages review session state and operations."""
    
    def __init__(
        self,
        data_manager: DataManager,
        split: str,
        total_images_in_run: int,
        total_reviewed_all_runs: int,
        num_samples: Optional[int] = None,
        num_target_samples: Optional[int] = None,
        run_folder_path: Optional[Path] = None
    ):
        self.data_manager = data_manager
        self.split = split
        self.total_images_in_run = total_images_in_run
        self.total_reviewed_all_runs = total_reviewed_all_runs
        self.num_samples = num_samples
        self.num_target_samples = num_target_samples
        self.run_folder_path = run_folder_path
        
        self.total_reviewed = 0
        self.total_skipped_existing = 0  # Items skipped because they already exist in CSV
        self.session_start_time = time.time()
        self.review_history: List[REVIEW_HISTORY_ENTRY] = []
        self.undone_from_csv: set = set()  # Track (task_id, step_index) already undone from CSV
        self.pending_return_step: Optional[StepInfo] = None  # Step to return to after undoing
    
    def _print_progress(self, step_elapsed: float) -> None:
        """Print progress information."""
        session_elapsed = time.time() - self.session_start_time
        avg_time = session_elapsed / self.total_reviewed if self.total_reviewed > 0 else 0
        
        print(f"✓ Saved review | Step: {step_elapsed:.2f}s | Session: {session_elapsed:.1f}s | Avg: {avg_time:.2f}s\n\n")
        print(f"  Progress: {self.total_reviewed}/{self.total_images_in_run} this run | {self.total_reviewed_all_runs + self.total_reviewed} total (all runs)")
        
        if self.num_samples is not None:
            current_both_correct = self.data_manager.count_both_correct()
            print(f"  'Both correct' samples: {current_both_correct}/{self.num_samples}")
        
        if self.num_target_samples is not None:
            current_target_correct = self.data_manager.count_target_correct()
            print(f"  'Target correct' samples: {current_target_correct}/{self.num_target_samples}")
        
        print(f"\n{'='*80}\n")
    
    def _check_target_reached(self) -> bool:
        """Check if target number of samples is reached (both correct and/or target correct)."""
        both_reached = False
        target_reached = False
        
        if self.num_samples is not None:
            current_both_correct = self.data_manager.count_both_correct()
            if current_both_correct >= self.num_samples:
                both_reached = True
        
        if self.num_target_samples is not None:
            current_target_correct = self.data_manager.count_target_correct()
            if current_target_correct >= self.num_target_samples:
                target_reached = True
        
        if both_reached or target_reached:
            self._print_session_summary()
            messages = []
            if both_reached:
                messages.append(f"'both correct': {self.data_manager.count_both_correct()}/{self.num_samples}")
            if target_reached:
                messages.append(f"'target correct': {self.data_manager.count_target_correct()}/{self.num_target_samples}")
            print(f"🎉 Target reached! Collected {', '.join(messages)}")
            return True
        return False
    
    def _print_undo_progress(self, current_step: StepInfo, was_rejected: bool) -> None:
        """Print progress after undo operation."""
        step_elapsed, session_elapsed = self._get_timing(current_step)
        if was_rejected:
            print(f"⏱️  Re-rejected | Step: {step_elapsed:.2f}s | Session: {session_elapsed:.1f}s")
        else:
            self._print_progress(step_elapsed)
        print(f"\n{'='*80}\nReturning to step you were reviewing:\n{'='*80}")
    
    def _print_session_summary(self) -> None:
        """Print session summary."""
        session_elapsed = time.time() - self.session_start_time
        current_both_correct = self.data_manager.count_both_correct()
        
        print(f"\n{'='*80}")
        print("Session Summary:")
        print(f"  Reviewed this run: {self.total_reviewed} / {self.total_images_in_run}")
        print(f"  Total reviewed (all runs): {self.total_reviewed_all_runs + self.total_reviewed}")
        if self.num_samples is not None:
            print(f"  'Both correct' samples: {current_both_correct}/{self.num_samples}")
        
        current_target_correct = self.data_manager.count_target_correct()
        if self.num_target_samples is not None:
            print(f"  'Target correct' samples: {current_target_correct}/{self.num_target_samples}")
        
        print(f"  Skipped (already in CSV): {self.total_skipped_existing}")
        print(f"  Session time: {session_elapsed:.1f}s ({session_elapsed/60:.1f} min)")
        if self.total_reviewed > 0:
            print(f"  Avg time per step: {session_elapsed/self.total_reviewed:.2f}s")
    
    def save_review(
        self,
        task_id: str,
        step_index: int,
        step_data: Dict[str, Any],
        result: ReviewResult,
        adjust_counter: bool = True
    ) -> None:
        """
        Save a review to the data manager.
        
        Args:
            adjust_counter: If True, increment total_reviewed (including rejected items)
        """
        self.data_manager.add_review(
            split=self.split,
            task_id=task_id,
            step_index=step_index,
            step_instruction=step_data['step_instruction'],
            target_bbox=step_data['target_bbox'],
            nearest_bbox=step_data['nearest_bbox'],
            relative_position=step_data['relative_position'],
            target_correct=result.target_correct,
            nearest_correct=result.nearest_correct,
            rejected=result.rejected
        )
        self.data_manager.save()
        
        if adjust_counter:
            # Count all reviews, including rejected items
            self.total_reviewed += 1
    
    def handle_undo(self, current_step: StepInfo) -> Optional[StepInfo]:
        """
        Handle undo operation.
        First checks review_history (current session), then checks CSV/DF for previously reviewed items.
        
        Returns:
            StepInfo to re-review if undo successful, None otherwise
        """
        # First try review_history (current session)
        if self.review_history:
            last_entry = self.review_history.pop()
            last_task_id, last_step_index, last_image_path, last_step_data, last_was_rejected = last_entry
            
            # Create StepInfo for the undone step
            undone_step = StepInfo(
                task_id=last_task_id,
                step_index=last_step_index,
                image_path=last_image_path,
                step_data=last_step_data,
                start_time=time.time()
            )
            
            action_type = "rejection" if last_was_rejected else "review"
            print(f"↩️  Undoing previous {action_type}: Task {last_task_id}, Step {last_step_index}")
            
            # Return the undone step to re-review (don't process here, let _review_step handle it)
            return undone_step
        
        # If no review_history, try to get last reviewed item from CSV/DF
        if self.run_folder_path is None:
            print("⚠️  No previous step to undo. Continuing with current step...")
            return None
        
        # Get last reviewed item from CSV that hasn't been undone yet
        last_reviewed = None
        for idx in range(len(self.data_manager.df) - 1, -1, -1):
            row = self.data_manager.df.iloc[idx]
            task_id = row['task_id']
            step_index = int(row['step_index'])
            if (task_id, step_index) not in self.undone_from_csv:
                last_reviewed = {
                    'task_id': task_id,
                    'step_index': step_index,
                    'step_instruction': row['step_instruction'],
                    'target_bbox': row['target_bbox'],
                    'nearest_bbox': row['nearest_bbox'],
                    'relative_position': row['relative_position'],
                    'rejected': bool(row['rejected'])
                }
                break
        
        if last_reviewed is None:
            print("⚠️  No previous step to undo. Continuing with current step...")
            return None
        
        # Reconstruct step info from CSV
        task_id = last_reviewed['task_id']
        step_index = last_reviewed['step_index']
        task_folder = self.run_folder_path / task_id
        
        # Find the image path
        images = get_visualization_images(task_folder)
        image_path = None
        for img_step_idx, img_path in images:
            if img_step_idx == step_index:
                image_path = img_path
                break
        
        if image_path is None or not image_path.exists():
            raise FileNotFoundError(f"Image not found for Task {task_id}, Step {step_index}")
        
        # Reconstruct step_data
        step_data = {
            'step_index': step_index,
            'step_instruction': last_reviewed['step_instruction'],
            'target_bbox': last_reviewed['target_bbox'],
            'nearest_bbox': last_reviewed['nearest_bbox'],
            'relative_position': last_reviewed['relative_position']
        }
        
        # Mark as undone from CSV (before returning, so we don't undo it again)
        self.undone_from_csv.add((task_id, step_index))
        
        # Store current_step to return to after re-reviewing
        self.pending_return_step = current_step
        
        # Create StepInfo for the undone step
        undone_step = StepInfo(
            task_id=task_id,
            step_index=step_index,
            image_path=image_path,
            step_data=step_data,
            start_time=time.time()
        )
        
        action_type = "rejection" if last_reviewed['rejected'] else "review"
        print(f"↩️  Undoing previous {action_type} from CSV: Task {task_id}, Step {step_index}")
        
        # Return the undone step to re-review (don't process here, let _review_step handle it)
        return undone_step
    
    def _add_to_history(self, step_info: StepInfo, was_rejected: bool) -> None:
        """Add step to review history."""
        self.review_history.append((
            step_info.task_id,
            step_info.step_index,
            step_info.image_path,
            step_info.step_data,
            was_rejected
        ))
    
    def _get_timing(self, step_info: StepInfo) -> Tuple[float, float]:
        """Get step and session elapsed times."""
        step_elapsed = time.time() - step_info.start_time
        session_elapsed = time.time() - self.session_start_time
        return step_elapsed, session_elapsed
    
    def process_review(
        self,
        step_info: StepInfo,
        result: ReviewResult
    ) -> bool:
        """
        Process a review result.
        
        Returns:
            True if should continue, False if should exit
        """
        # Skip: don't save, can be sampled again next time
        if result.skipped:
            step_elapsed, session_elapsed = self._get_timing(step_info)
            print(f"⏱️  Skipped | Step: {step_elapsed:.2f}s | Session: {session_elapsed:.1f}s")
            return True
        
        # Rejected: save as rejected
        if result.rejected:
            self.save_review(
                step_info.task_id,
                step_info.step_index,
                step_info.step_data,
                result,
                adjust_counter=True
            )
            self._add_to_history(step_info, True)
            step_elapsed, session_elapsed = self._get_timing(step_info)
            print(f"⏱️  Rejected | Step: {step_elapsed:.2f}s | Session: {session_elapsed:.1f}s")
            return True
        
        # Regular review: save and track progress
        self.save_review(
            step_info.task_id,
            step_info.step_index,
            step_info.step_data,
            result
        )
        # Only add to history if this step wasn't undone from CSV (to prevent loops)
        # Items undone from CSV are already in undone_from_csv set, so we skip adding to history
        if (step_info.task_id, step_info.step_index) not in self.undone_from_csv:
            self._add_to_history(step_info, False)
        
        step_elapsed, session_elapsed = self._get_timing(step_info)
        self._print_progress(step_elapsed)
        
        return not self._check_target_reached()


# ============================================================================
# Review Controller (Main)
# ============================================================================

def load_reference_steps(reference_csv_path: Path, project_root: Path) -> set:
    """
    Load reference steps from CSV (target_correct=True, nearest_correct=True).
    
    Returns:
        Set of (task_id, step_index) tuples
    """
    if not reference_csv_path.exists():
        raise FileNotFoundError(f"Reference CSV not found: {reference_csv_path}")
    
    ref_df = pd.read_csv(reference_csv_path)
    
    # Filter for target_correct=True and nearest_correct=True
    mask = (ref_df['target_correct'] == True) & (ref_df['nearest_correct'] == True)
    filtered_df = ref_df[mask]
    
    # Create set of (task_id, step_index) tuples
    reference_steps = set()
    for _, row in filtered_df.iterrows():
        task_id = str(row['task_id'])
        step_index = int(row['step_index'])
        reference_steps.add((task_id, step_index))
    
    return reference_steps


def review_run_folder(run_folder: str, output_csv: Optional[str] = None, num_samples: Optional[int] = None, num_target_samples: Optional[int] = None, window_position: str = "left", reference_csv: Optional[str] = None):
    """Main review function."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    run_folder_path = project_root / run_folder
    
    # Extract split
    split = extract_split_from_run_folder(run_folder_path.name)
    print(f"Detected split: {split}")
    
    # Determine CSV path
    if output_csv is None:
        csv_filename = f"{run_folder_path.name}_reviews.csv"
        csv_path = project_root / "data" / csv_filename
    else:
        csv_path = Path(output_csv)
        if not csv_path.is_absolute():
            csv_path = project_root / csv_path
    
    print(f"Output CSV: {csv_path}")
    
    # Load reference steps if provided
    reference_steps = set()
    if reference_csv:
        reference_csv_path = Path(reference_csv)
        if not reference_csv_path.is_absolute():
            reference_csv_path = project_root / reference_csv_path
        
        print(f"\nLoading reference CSV: {reference_csv_path}")
        reference_steps = load_reference_steps(reference_csv_path, project_root)
        print(f"Found {len(reference_steps)} reference steps (target_correct=True, nearest_correct=True)")
    
    # Initialize image viewer with window position
    init_image_viewer(window_position)
    
    # Initialize data manager
    data_manager = DataManager(csv_path)
    total_reviewed_all_runs = data_manager.count_reviewed()
    print(f"Loaded {total_reviewed_all_runs} existing reviews from CSV")
    
    # Check existing samples
    existing_both_correct = data_manager.count_both_correct()
    existing_target_correct = data_manager.count_target_correct()
    
    if num_samples is not None:
        print(f"Target: {num_samples} 'both correct' samples")
        print(f"Existing 'both correct' samples: {existing_both_correct}")
        if existing_both_correct >= num_samples:
            print(f"✓ Already have {existing_both_correct} 'both correct' samples (target: {num_samples}). Exiting.")
            return
    
    if num_target_samples is not None:
        print(f"Target: {num_target_samples} 'target correct' samples")
        print(f"Existing 'target correct' samples: {existing_target_correct}")
        if existing_target_correct >= num_target_samples:
            print(f"✓ Already have {existing_target_correct} 'target correct' samples (target: {num_target_samples}). Exiting.")
            return
    
    # Scan for valid tasks
    print(f"\nScanning {run_folder_path}...")
    valid_tasks = scan_run_folder(run_folder_path)
    if not valid_tasks:
        raise ValueError(f"No valid tasks found in {run_folder_path}")
    print(f"Found {len(valid_tasks)} tasks with trajectory.json")
    
    # Collect all steps from all tasks, separating reference matches
    all_steps = []
    reference_matches = []
    reference_match_count = 0
    
    for task_id, task_folder in valid_tasks:
        # Parse trajectory
        trajectory_path = task_folder / "trajectory.json"
        if not trajectory_path.exists():
            raise FileNotFoundError(f"trajectory.json not found in {task_folder}")
        
        steps = parse_trajectory(trajectory_path)
        images = get_visualization_images(task_folder)
        
        if not images:
            continue  # Skip tasks with no visualization images
        
        step_lookup = {step['step_index']: step for step in steps}
        
        # Collect all steps for this task
        for step_index, image_path in images:
            # Skip if already reviewed (exists in CSV)
            if data_manager.is_reviewed(task_id, step_index):
                continue
            
            # Get step data - error if missing
            step_data = step_lookup.get(step_index)
            if step_data is None:
                raise ValueError(f"No step data found for task {task_id}, step_index {step_index}")
            
            step_tuple = (task_id, step_index, image_path, step_data)
            
            # Check if this matches a reference step
            if (task_id, step_index) in reference_steps:
                reference_matches.append(step_tuple)
                reference_match_count += 1
            else:
                all_steps.append(step_tuple)
    
    # Log reference matches
    if reference_csv:
        print(f"\nFound {reference_match_count} matching steps in current run_folder")
        print(f"  Reference matches: {len(reference_matches)}")
        print(f"  Other steps: {len(all_steps)}")
    
    # Count total images (including already reviewed ones for accurate count)
    total_images_all = sum(
        len(get_visualization_images(task_folder))
        for _, task_folder in valid_tasks
    )
    total_images_in_run = len(reference_matches) + len(all_steps)  # Only unreviewed steps
    total_skipped_existing = total_images_all - total_images_in_run
    
    print(f"Total images in this run: {total_images_in_run} (skipped {total_skipped_existing} already reviewed)")
    
    # Shuffle reference matches and regular steps separately
    shuffle(reference_matches)
    shuffle(all_steps)
    
    # Combine: reference matches first, then regular steps
    all_steps = reference_matches + all_steps
    
    # Initialize session
    session = ReviewSession(
        data_manager=data_manager,
        split=split,
        total_images_in_run=total_images_in_run,
        total_reviewed_all_runs=total_reviewed_all_runs,
        num_samples=num_samples,
        num_target_samples=num_target_samples,
        run_folder_path=run_folder_path
    )
    session.total_skipped_existing = total_skipped_existing
    
    try:
        # Review all steps in shuffled order
        for task_id, step_index, image_path, step_data in all_steps:
            # Review step
            step_info = StepInfo(
                task_id=task_id,
                step_index=step_index,
                image_path=image_path,
                step_data=step_data,
                start_time=time.time()
            )
            
            if not _review_step(session, step_info):
                return  # Target reached or quit
    
    except KeyboardInterrupt:
        close_image()
        session._print_session_summary()
        print("\n\nReview interrupted (Ctrl+C). Saving progress...")
        data_manager.save()
        print(f"Progress saved to {csv_path}")
        return
    
    # Final summary
    session._print_session_summary()
    print("Review complete!")
    print(f"\nResults saved to: {csv_path}")


def _review_step(session: ReviewSession, step_info: StepInfo) -> bool:
    """
    Review a single step.
    
    Returns:
        True to continue, False to exit
    """
    open_image(step_info.image_path)
    
    try:
        result = get_user_input(step_info.step_data)
        
        # Handle undo
        if result.is_undo:
            undone_step = session.handle_undo(step_info)
            if undone_step is None:
                return True  # No undo possible, continue
            
            # Re-review the undone step
            continue_review = _review_step(session, undone_step)
            if not continue_review:
                return False
            
            # After re-reviewing undone step, return to the step we were at (if any)
            if session.pending_return_step is not None:
                return_step = session.pending_return_step
                session.pending_return_step = None
                print(f"\n{'='*80}\nReturning to step you were reviewing:\n{'='*80}")
                return _review_step(session, return_step)
            
            # No pending return step, continue normally
            return True
        
        # Process the review
        return session.process_review(step_info, result)
    
    except QuitReview:
        close_image()
        session._print_session_summary()
        print("\nQuitting review. Saving progress...")
        session.data_manager.save()
        print(f"Progress saved to {session.data_manager.csv_path}")
        return False


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Manually review visualization images and log correctness of labels'
    )
    parser.add_argument(
        '--run_folder',
        type=str,
        # default="final_data/run_20251112_004959_test_domain_original",
        default="final_data/run_20251112_005144_test_domain_precision",
        help='Path to run folder (e.g., "final_data/run_20251112_004959_test_domain_original")'
    )
    parser.add_argument(
        '--output_csv',
        type=str,
        # default="data/run_20251112_004959_test_domain_original_reviews.csv",
        default="data/run_20251112_005144_test_domain_precision_reviews.csv",
        help='Optional path to output CSV file. Defaults to <run_folder>_reviews.csv in data/'
    )
    parser.add_argument(
        '--num_samples',
        type=int,
        default=200,
        help='Number of "both correct" samples to collect. Script exits when reached. (e.g., 500)'
    )
    parser.add_argument(
        '--num_target_samples',
        type=int,
        default=None,
        help='Number of "target correct" samples to collect. Script exits when reached. (e.g., 1000)'
    )
    parser.add_argument(
        '--window_position',
        type=str,
        choices=['left', 'right', 'max'],
        default='max',
        help='Preview window position: "left" (left half), "right" (right half), or "max" (maximized). Default: left'
    )
    parser.add_argument(
        '--reference_csv',
        type=str,
        default=None,
        help='Optional path to reference CSV file. Steps matching (task_id, step_index) from reference CSV rows with target_correct=True and nearest_correct=True will be shown first.'
    )
    
    args = parser.parse_args()
    review_run_folder(args.run_folder, args.output_csv, args.num_samples, args.num_target_samples, args.window_position, args.reference_csv)


if __name__ == "__main__":
    main()
