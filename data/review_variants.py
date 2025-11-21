#!/usr/bin/env python3
"""
Review samples across variants for the same task_id and step_index.

For each (task_id, step_index) pair in combined_reviews.csv where
target_correct=True and nearest_correct=True:
- Shows visualization images from all 4 variants (original, precision, style, text_shrink)
- Allows navigation between variants (n/p for next/previous)
- Saves decisions to CSV
- Prints clickable path to trajectory.json in ROOT GOLDEN SET
"""

import pandas as pd
from pathlib import Path
import subprocess
import sys
import time
import re
from typing import Optional, Tuple, List, Dict
import json

# ROOT GOLDEN SET mapping: base split -> variant
ROOT_GOLDEN_SET = {
    'test_domain': 'original',
    'test_task': 'style',
    'test_website': 'style'
}

# Reuse ImageViewer from data_review_helper
def get_screen_dimensions() -> Tuple[int, int]:
    """Get largest screen dimensions. Returns (width, height)."""
    if sys.platform != "darwin":
        return (1920, 1080)
    
    try:
        # Try using AppKit first (most reliable)
        try:
            from AppKit import NSScreen
            # Get all screens and find the largest one
            screens = NSScreen.screens()
            largest_screen = None
            largest_area = 0
            for screen in screens:
                frame = screen.frame()
                area = frame.size.width * frame.size.height
                if area > largest_area:
                    largest_area = area
                    largest_screen = screen
            if largest_screen:
                frame = largest_screen.frame()
                return (int(frame.size.width), int(frame.size.height))
            # Fallback to main screen
            main_screen = NSScreen.mainScreen()
            frame = main_screen.frame()
            return (int(frame.size.width), int(frame.size.height))
        except ImportError:
            # Fallback: Use AppleScript to get largest screen dimensions
            script = '''
            tell application "System Events"
                set largestWidth to 0
                set largestHeight to 0
                repeat with aDesktop in (every desktop)
                    set screenBounds to bounds of aDesktop
                    set screenWidth to item 3 of screenBounds
                    set screenHeight to item 4 of screenBounds
                    set screenArea to screenWidth * screenHeight
                    if screenArea > (largestWidth * largestHeight) then
                        set largestWidth to screenWidth
                        set largestHeight to screenHeight
                    end if
                end repeat
                return largestWidth & "," & largestHeight
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                try:
                    parts = result.stdout.strip().split(',')
                    if len(parts) == 2:
                        return (int(parts[0]), int(parts[1]))
                except (ValueError, IndexError):
                    pass
            
            # Last fallback: use system_profiler to find largest display
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                largest_width = 0
                largest_height = 0
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if 'Resolution' in line:
                        match = re.search(r'Resolution:\s+(\d+)\s+x\s+(\d+)', line)
                        if match:
                            width = int(match.group(1))
                            height = int(match.group(2))
                            if width * height > largest_width * largest_height:
                                largest_width = width
                                largest_height = height
                        else:
                            match = re.search(r'(\d+)\s+(\d+)', line)
                            if match:
                                width = int(match.group(1))
                                height = int(match.group(2))
                                if width * height > largest_width * largest_height:
                                    largest_width = width
                                    largest_height = height
                if largest_width > 0 and largest_height > 0:
                    return (largest_width, largest_height)
            return (1440, 900)
    except Exception:
        return (1440, 900)


class ImageViewer:
    """Manages image viewer process and window positioning."""
    
    def __init__(self, window_position: str = "left"):
        self.preview_positioned = False
        self.window_position = window_position
        self.screen_width, self.screen_height = get_screen_dimensions()
    
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
        """Open image in Preview, positioning window."""
        if sys.platform != "darwin":
            return
        
        # Use absolute path and ensure it exists
        abs_path = image_path.resolve()
        if not abs_path.exists():
            print(f"⚠️  Image file does not exist: {abs_path}")
            return
        
        # Remove quarantine and other problematic extended attributes
        # This helps avoid macOS security blocks
        try:
            # Remove quarantine flag
            subprocess.run(
                ["xattr", "-d", "com.apple.quarantine", str(abs_path)],
                capture_output=True,
                timeout=1,
                check=False
            )
            # Also try to remove provenance which can sometimes cause issues
            subprocess.run(
                ["xattr", "-d", "com.apple.provenance", str(abs_path)],
                capture_output=True,
                timeout=1,
                check=False
            )
        except Exception:
            pass  # Ignore errors if xattr fails
        
        # Ensure file has correct read permissions
        try:
            abs_path.chmod(0o644)  # rw-r--r--
        except Exception:
            pass  # Ignore permission errors
        
        # Close current document if Preview is already open
        # Sometimes fully quitting Preview helps reset permission issues
        if self.preview_positioned:
            # First try to just close the document
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
        else:
            # If Preview hasn't been positioned yet, fully quit it to start fresh
            # This can help avoid permission issues that accumulate
            try:
                quit_script = 'tell application "Preview" to quit'
                subprocess.run(
                    ["osascript", "-e", quit_script],
                    capture_output=True,
                    timeout=1,
                    check=False
                )
                time.sleep(0.2)  # Give Preview time to fully quit
            except Exception:
                pass
        
        # Calculate window bounds using pre-calculated screen dimensions
        screen_width = self.screen_width
        screen_height = self.screen_height
        
        if self.window_position == "left":
            # Use half of screen width for left window
            left, top, right, bottom = 0, 0, screen_width // 2, screen_height
        elif self.window_position == "right":
            left, top, right, bottom = screen_width // 2, 0, screen_width, screen_height
        elif self.window_position == "max":
            left, top, right, bottom = 0, 0, screen_width, screen_height
        else:
            # Default to left with half width
            left, top, right, bottom = 0, 0, screen_width // 2, screen_height
        
        # Try multiple methods to open the file, as macOS can be finicky with permissions
        opened = False
        
        # Method 1: Use AppleScript with file URL (most reliable for permissions)
        try:
            # Escape the path for AppleScript (do this before the f-string)
            escaped_path = str(abs_path).replace('\\', '\\\\').replace('"', '\\"')
            applescript_open = f'''
            tell application "Preview"
                activate
                open POSIX file "{escaped_path}"
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", applescript_open],
                timeout=3,
                check=False,
                capture_output=True
            )
            if result.returncode == 0:
                opened = True
                time.sleep(0.4)
        except Exception:
            pass
        
        # Method 2: If AppleScript failed, try 'open -n' (new instance)
        if not opened:
            try:
                result = subprocess.run(
                    ["open", "-n", "-a", "Preview", str(abs_path)],
                    timeout=3,
                    check=False,
                    capture_output=True
                )
                if result.returncode == 0:
                    opened = True
                    time.sleep(0.4)
            except Exception:
                pass
        
        # Method 3: Try simple 'open' command
        if not opened:
            try:
                subprocess.run(
                    ["open", "-a", "Preview", str(abs_path)],
                    timeout=3,
                    check=False
                )
                time.sleep(0.4)
                opened = True
            except Exception:
                pass
        
        # Method 4: Last resort - use Quick Look (qlmanage) which has different permission handling
        if not opened:
            try:
                subprocess.run(
                    ["qlmanage", "-p", str(abs_path)],
                    timeout=3,
                    check=False,
                    capture_output=True
                )
                # Note: qlmanage opens in a separate window, positioning won't work
                print("⚠️  Opened with Quick Look (positioning unavailable)")
            except Exception as e:
                print(f"⚠️  Error opening image with all methods: {e}")
                print(f"   File path: {abs_path}")
                return
        
        # Then position the window using AppleScript
        position_script = f'''
        tell application "Preview"
            activate
            if (count of windows) > 0 then
                set bounds of front window to {{{left}, {top}, {right}, {bottom}}}
            end if
        end tell
        '''
        
        try:
            subprocess.run(
                ["osascript", "-e", position_script],
                capture_output=True,
                timeout=2,
                check=False
            )
        except subprocess.TimeoutExpired:
            pass
        
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


def extract_split_from_run_folder(run_folder_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract base split and variant from run folder name."""
    if not run_folder_name.startswith('run_'):
        return None, None
    
    parts = run_folder_name[4:].split('_')
    if len(parts) < 3:
        return None, None
    
    rest = '_'.join(parts[2:])
    
    for variant_name in ['text_shrink', 'precision', 'original', 'style']:
        if rest.endswith(f'_{variant_name}'):
            base_split = rest[:-len(f'_{variant_name}')]
            return base_split, variant_name
    
    return None, None


def get_base_split_from_golden_split(split: str) -> Optional[str]:
    """Extract base split from ROOT GOLDEN SET split name."""
    for base, variant in ROOT_GOLDEN_SET.items():
        if split == f'{base}_{variant}':
            return base
    return None


def find_run_folder(project_root: Path, base_split: str, variant: str) -> Optional[Path]:
    """Find run folder for a given base split and variant."""
    final_data_dir = project_root / "final_data"
    if not final_data_dir.exists():
        return None
    
    for run_folder in final_data_dir.iterdir():
        if not run_folder.is_dir():
            continue
        
        extracted_base, extracted_variant = extract_split_from_run_folder(run_folder.name)
        if extracted_base == base_split and extracted_variant == variant:
            return run_folder
    
    return None


def get_visualization_image(task_folder: Path, step_index: int) -> Optional[Path]:
    """Get visualization image for a specific step_index."""
    visualizations_dir = task_folder / "visualizations"
    if not visualizations_dir.exists():
        return None
    
    image_file = visualizations_dir / f"step_{step_index}_click_with_bbox.png"
    if image_file.exists():
        return image_file
    
    for image_file in visualizations_dir.glob("*_with_bbox.png"):
        match = re.search(r'step_(\d+)_', image_file.name)
        if match and int(match.group(1)) == step_index:
            return image_file
    
    return None


def extract_step_index_from_entry(entry: Dict, default_index: int) -> int:
    """Extract step_index from trajectory entry, using screenshot path or default index."""
    screenshot_path = entry.get("screenshot", "")
    if screenshot_path:
        match = re.search(r'step_(\d+)_', screenshot_path)
        if match:
            return int(match.group(1))
    return default_index


def update_trajectory_entry(
    trajectory_data: List[Dict],
    step_index: int,
    new_step_instruction: str,
    multi_element_instruction: str
) -> bool:
    """Update trajectory entry with new step_instruction and multi_element_instruction."""
    for idx, entry in enumerate(trajectory_data):
        entry_step_index = extract_step_index_from_entry(entry, idx)
        if entry_step_index == step_index:
            entry["step_instruction"] = new_step_instruction
            entry["multi_element_instruction"] = multi_element_instruction
            return True
    return False


def save_trajectory_json(trajectory_path: Path, trajectory_data: List[Dict]) -> None:
    """Save trajectory.json file."""
    with open(trajectory_path, 'w') as f:
        json.dump(trajectory_data, f, indent=2)


def get_current_instructions(trajectory_path: Path, step_index: int) -> Tuple[Optional[str], Optional[str]]:
    """Get current step_instruction and multi_element_instruction from trajectory.json."""
    if not trajectory_path or not trajectory_path.exists():
        return None, None
    
    try:
        with open(trajectory_path, 'r') as f:
            trajectory_data = json.load(f)
        
        for idx, entry in enumerate(trajectory_data):
            entry_step_index = extract_step_index_from_entry(entry, idx)
            if entry_step_index == step_index:
                step_instruction = entry.get("step_instruction")
                multi_element_instruction = entry.get("multi_element_instruction")
                return step_instruction, multi_element_instruction
        
        return None, None
    except Exception as e:
        print(f"⚠️  Error reading trajectory.json: {e}")
        return None, None


class VariantReviewSession:
    """Manages variant review session."""
    
    def __init__(self, output_csv: Path):
        self.output_csv = output_csv
        self.decisions = []
        self.load_existing()
    
    def load_existing(self):
        """Load existing decisions from CSV."""
        if self.output_csv.exists():
            df = pd.read_csv(self.output_csv)
            for _, row in df.iterrows():
                self.decisions.append({
                    'task_id': str(row['task_id']),
                    'step_index': int(row['step_index']),
                    'split': str(row['split']),
                    'decision': str(row['decision'])
                })
    
    def is_reviewed(self, task_id: str, step_index: int) -> bool:
        """Check if already reviewed."""
        for d in self.decisions:
            if d['task_id'] == task_id and d['step_index'] == step_index:
                return True
        return False
    
    def add_decision(self, task_id: str, step_index: int, split: str, decision: str):
        """Add a decision."""
        # Remove existing decision for this pair
        self.decisions = [d for d in self.decisions 
                         if not (d['task_id'] == task_id and d['step_index'] == step_index)]
        
        self.decisions.append({
            'task_id': task_id,
            'step_index': step_index,
            'split': split,
            'decision': decision
        })
        self.save()
        
        # Print current count
        summary = self.get_summary()
        print(f"  📊 Total reviews: {summary['total']} (Keep: {summary['keep']}, Not Keep: {summary['not_keep']})")
    
    def save(self):
        """Save decisions to CSV."""
        if not self.decisions:
            return
        
        df = pd.DataFrame(self.decisions)
        df.to_csv(self.output_csv, index=False)
    
    def get_summary(self) -> Dict[str, int]:
        """Get summary statistics."""
        keep_count = sum(1 for d in self.decisions if d['decision'] == 'keep')
        not_keep_count = sum(1 for d in self.decisions if d['decision'] == 'not_keep')
        return {
            'total': len(self.decisions),
            'keep': keep_count,
            'not_keep': not_keep_count
        }


def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    csv_path = script_dir / "combined_reviews.csv"
    # output_csv = script_dir / "final_variant_reviews.csv"
    output_csv = script_dir / "variant_reviews.csv"

    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        return
    
    # Load CSV
    print(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path)
    # ref_df = pd.read_csv(script_dir / "variant_data.csv")
    # get df and ref_df intersect on task_id and step_index
    # merged = df.merge(ref_df[['task_id', 'step_index']], on=['task_id', 'step_index'], how='inner')
    # filtered_df = merged

    # filtered_df.sort_values(by=['task_id', 'step_index'], inplace=True)
    
    # Filter for target_correct=True and nearest_correct=True
    mask = (df['target_correct'] == True) & (df['nearest_correct'] == True)
    filtered_df = df[mask]
    
    print(f"Found {len(filtered_df)} rows with target_correct=True and nearest_correct=True")
    
    # Initialize session
    session = VariantReviewSession(output_csv)
    existing_count = len([r for r in filtered_df.itertuples() 
                         if session.is_reviewed(str(r.task_id), int(r.step_index))])
    print(f"Already reviewed: {existing_count} | Remaining: {len(filtered_df) - existing_count}")
    
    # Initialize image viewer
    image_viewer = ImageViewer(window_position="left")
    
    # Process each row
    samples = list(filtered_df.itertuples())
    current_idx = 0
    
    while current_idx < len(samples):
        row = samples[current_idx]
        task_id = str(row.task_id)
        step_index = int(row.step_index)
        golden_split = str(row.split)
        
        # Skip if already reviewed
        if session.is_reviewed(task_id, step_index):
            current_idx += 1
            continue
        
        # Get base split from golden split
        base_split = get_base_split_from_golden_split(golden_split)
        if not base_split:
            print(f"\n⚠️  Could not determine base split from '{golden_split}'. Skipping...")
            current_idx += 1
            continue
        
        golden_variant = ROOT_GOLDEN_SET[base_split]
        
        # Collect variant images
        variant_images = []
        for variant_name in ['original', 'precision', 'style', 'text_shrink']:
            run_folder = find_run_folder(project_root, base_split, variant_name)
            if not run_folder:
                continue
            
            task_folder = run_folder / task_id
            if not task_folder.exists():
                continue
            
            image_path = get_visualization_image(task_folder, step_index)
            if image_path and image_path.exists():
                variant_images.append((variant_name, image_path))
        
        if not variant_images:
            print(f"\n⚠️  No images found for Task {task_id}, Step {step_index}. Skipping...")
            current_idx += 1
            continue
        
        # Get trajectory.json path from ROOT GOLDEN SET
        golden_run_folder = find_run_folder(project_root, base_split, golden_variant)
        trajectory_path = None
        if golden_run_folder:
            trajectory_path = golden_run_folder / task_id / "trajectory.json"
        
        # Review loop for this sample
        variant_idx = 0
        reviewing = True
        
        while reviewing:
            variant_name, image_path = variant_images[variant_idx]
            
            print(f"\n{'='*80}")
            print(f"Sample {current_idx + 1}/{len(samples)}: Task {task_id}, Step {step_index}")
            print(f"Base Split: {base_split} | Variant: {variant_name} ({variant_idx + 1}/{len(variant_images)})")
            if trajectory_path and trajectory_path.exists():
                print(f"📄 trajectory.json: file://{trajectory_path.resolve()}")
            
            # Display step_instruction and multi_element_instruction
            if trajectory_path and trajectory_path.exists():
                step_instr, multi_instr = get_current_instructions(trajectory_path, step_index)
                print(f"\n  Instructions:")
                if step_instr:
                    print(f"    step_instruction: {step_instr}")
                else:
                    print(f"    step_instruction: (not found)")
                if multi_instr:
                    print(f"    multi_element_instruction: {multi_instr}")
                else:
                    print(f"    multi_element_instruction: (not found)")
            
            print(f"{'='*80}")
            
            # Open image
            print(f"📷 Opening: {image_path.name}")
            print(f"📷 Image path: file://{image_path.resolve()}")
            image_viewer.open_image(image_path)
            
            # Show navigation prompt
            prompt = "Navigation: [n] next variant | [p] previous variant | [u] update instructions | [k] keep | [r] not keep | [s] skip | [z] back | [q] quit"
            print(prompt)
            
            try:
                user_input = input("> ").strip().lower()
                
                if user_input == 'q':
                    print("\nExiting...")
                    reviewing = False
                    current_idx = len(samples)  # Exit outer loop
                elif user_input == 's':
                    print("  → Skipped")
                    reviewing = False
                    current_idx += 1
                elif user_input == 'k':
                    session.add_decision(task_id, step_index, golden_split, 'keep')
                    print("  → Marked as KEEP")
                    reviewing = False
                    current_idx += 1
                elif user_input == 'r':
                    session.add_decision(task_id, step_index, golden_split, 'not_keep')
                    print("  → Marked as NOT KEEP")
                    reviewing = False
                    current_idx += 1
                elif user_input == 'u':
                    # Check instructions across all variants first
                    print("\n  Checking instructions across variants...")
                    variant_instructions = {}
                    for var_name_check in ['original', 'precision', 'style', 'text_shrink']:
                        run_folder = find_run_folder(project_root, base_split, var_name_check)
                        if run_folder:
                            var_trajectory = run_folder / task_id / "trajectory.json"
                            if var_trajectory.exists():
                                step_instr, multi_instr = get_current_instructions(var_trajectory, step_index)
                                variant_instructions[var_name_check] = (step_instr, multi_instr)
                    
                    # Show differences
                    if len(variant_instructions) > 1:
                        print("  Instructions across variants:")
                        for var_name, (step_instr, multi_instr) in variant_instructions.items():
                            marker = " (GOLDEN)" if var_name == golden_variant else ""
                            print(f"    {var_name:12s}{marker}: step='{step_instr or '(none)'}' multi='{multi_instr or '(none)'}'")
                        
                        # Check if all are the same
                        all_same = True
                        if variant_instructions:
                            first_step, first_multi = list(variant_instructions.values())[0]
                            for step_instr, multi_instr in variant_instructions.values():
                                if step_instr != first_step or multi_instr != first_multi:
                                    all_same = False
                                    break
                        
                        if all_same:
                            print("  ✓ All variants have the same instructions")
                        else:
                            print("  ⚠️  Instructions differ across variants")
                    
                    # Get current instructions from the variant being shown
                    current_variant_run_folder = find_run_folder(project_root, base_split, variant_name)
                    if not current_variant_run_folder:
                        print("  ⚠️  Cannot find run folder for current variant. Cannot update.")
                        continue
                    
                    current_variant_trajectory = current_variant_run_folder / task_id / "trajectory.json"
                    if not current_variant_trajectory.exists():
                        print("  ⚠️  trajectory.json not found for current variant. Cannot update.")
                        continue
                    
                    current_step_instruction, current_multi_element = get_current_instructions(
                        current_variant_trajectory, step_index
                    )
                    
                    print("\n  Update instructions:")
                    print(f"  Current variant: {variant_name}")
                    if current_step_instruction:
                        print(f"  Current step_instruction: {current_step_instruction}")
                    else:
                        print("  Current step_instruction: (not found)")
                    
                    print("\n  Enter new step_instruction (or press Enter to keep current):")
                    new_step = input("  step_instruction: ").strip()
                    if not new_step:
                        new_step = current_step_instruction if current_step_instruction else ""
                    
                    print("\n  Enter multi_element_instruction:")
                    if current_multi_element:
                        print(f"  Current: {current_multi_element}")
                    multi_element = input("  multi_element_instruction: ").strip()
                    if not multi_element:
                        print("  ⚠️  multi_element_instruction cannot be empty. Skipping update.")
                        continue
                    
                    # Ask if update all variants or just current variant
                    print(f"\n  Update: [c] current variant ({variant_name}) only | [a] all variants")
                    update_choice = input("  > ").strip().lower()
                    update_all = (update_choice == 'a')
                    
                    # Update trajectory.json files
                    variants_to_update = ['original', 'precision', 'style', 'text_shrink'] if update_all else [variant_name]
                    updated_count = 0
                    updated_paths = []
                    
                    for var_name in variants_to_update:
                        run_folder = find_run_folder(project_root, base_split, var_name)
                        if not run_folder:
                            continue
                        
                        var_trajectory = run_folder / task_id / "trajectory.json"
                        if not var_trajectory.exists():
                            print(f"  ⚠️  trajectory.json not found for {var_name}")
                            continue
                        
                        try:
                            with open(var_trajectory, 'r') as f:
                                trajectory_data = json.load(f)
                            
                            if update_trajectory_entry(trajectory_data, step_index, new_step, multi_element):
                                save_trajectory_json(var_trajectory, trajectory_data)
                                marker = " (GOLDEN)" if var_name == golden_variant else ""
                                print(f"  ✓ Updated {var_name}{marker}")
                                updated_paths.append((var_name, var_trajectory, marker))
                                updated_count += 1
                            else:
                                print(f"  ⚠️  Could not find step_index {step_index} in {var_name} trajectory.json")
                        except Exception as e:
                            print(f"  ⚠️  Error updating {var_name} trajectory.json: {e}")
                    
                    if updated_count > 0:
                        print(f"\n  ✓ Updated {updated_count} variant(s). Clickable paths:")
                        for var_name, var_trajectory, marker in updated_paths:
                            print(f"    {var_name:12s}{marker}: file://{var_trajectory.resolve()}")
                elif user_input == 'n':
                    variant_idx = (variant_idx + 1) % len(variant_images)
                elif user_input == 'p':
                    variant_idx = (variant_idx - 1) % len(variant_images)
                elif user_input == 'z':
                    if current_idx > 0:
                        current_idx -= 1
                        reviewing = False
                    else:
                        print("  → Already at first sample")
                else:
                    print("  → Invalid input")
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                reviewing = False
                current_idx = len(samples)
    
    # Close image viewer
    image_viewer.close_current()
    
    # Print summary
    summary = session.get_summary()
    print(f"\n{'='*80}")
    print("Summary:")
    print(f"  Total reviewed: {summary['total']}")
    print(f"  Keep: {summary['keep']}")
    print(f"  Not Keep: {summary['not_keep']}")
    print(f"  Saved to: {output_csv}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
