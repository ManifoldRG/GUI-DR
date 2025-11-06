"""
Utility helper functions for file operations, task discovery, instruction generation, and summaries.
"""

import os
import re
from typing import List, Tuple, Dict, Any


# ============================================================================
# File Utilities
# ============================================================================

def setup_result_dirs(run_dir: str, task_uid: str) -> Tuple[str, str]:
    """Set up directory structure: run_<timestamp>/<task_id>/screenshots/ and trajectory.json
    
    Args:
        run_dir: The run directory name (e.g., "run_20251104_123456")
        task_uid: The task UID to use as the folder name
        
    Returns:
        Tuple of (task_screenshots_dir, trajectory_file)
    """
    # Create structure: run_<timestamp>/<task_id>/
    task_dir = os.path.join(run_dir, task_uid)
    os.makedirs(task_dir, exist_ok=True)
    
    # Create screenshots directory: run_<timestamp>/<task_id>/screenshots/
    task_screenshots_dir = os.path.join(task_dir, "screenshots")
    os.makedirs(task_screenshots_dir, exist_ok=True)
    
    # Create trajectory file path: run_<timestamp>/<task_id>/trajectory.json
    trajectory_file = os.path.join(task_dir, "trajectory.json")
    
    return task_screenshots_dir, trajectory_file


# ============================================================================
# Task Discovery
# ============================================================================

def find_tasks_from_parquet(mm_mind2web_base: str, task_uids: List[str]) -> List[Tuple[str, str, str]]:
    """Find task folders that match the task_uids from parquet data.
    
    Args:
        mm_mind2web_base: Base directory for task folders
        task_uids: List of task UIDs (annotation_ids) from parquet
    
    Returns:
        List of tuples: (task_uid, dom_content_json_path, mhtml_files_dir)
    """
    task_folders = []
    task_dir = os.path.join(mm_mind2web_base, "task")
    
    if not os.path.exists(task_dir):
        raise ValueError(f"Task directory not found: {task_dir}")
    
    task_uids_set = set(task_uids)
    
    # Check each task folder
    for task_uid in task_uids_set:
        item_path = os.path.join(task_dir, task_uid)
        
        if not os.path.isdir(item_path):
            continue
        
        dom_content_path = os.path.join(item_path, "processed", "dom_content.json")
        snapshots_dir = os.path.join(item_path, "processed", "snapshots")
        
        if os.path.exists(dom_content_path) and os.path.exists(snapshots_dir):
            task_folders.append((task_uid, dom_content_path, snapshots_dir))
            print(f"✅ Found task folder: {task_uid}")
    
    missing_tasks = task_uids_set - {t[0] for t in task_folders}
    if missing_tasks:
        print(f"⚠️  Warning: {len(missing_tasks)} tasks from parquet have no corresponding task folders:")
        for task_uid in sorted(missing_tasks)[:5]:
            print(f"      - {task_uid}")
        if len(missing_tasks) > 5:
            print(f"      ... and {len(missing_tasks) - 5} more")
    
    return task_folders


# ============================================================================
# Instruction Generation
# ============================================================================

# Regex pattern for parsing target_action_reprs: [element_type] element_text -> ACTION_TYPE(: action_value)?
TARGET_ACTION_REPRS_PATTERN = r"\[(.*?)\]\s(.*?)\s->\s(CLICK|SELECT|TYPE)(?:\s*:\s*(.*))?"
TARGET_ACTION_REPRS_PATTERN_SIMPLE = r"\[(.*?)\]\s(.*?)\s->.*"


def parse_target_action_reprs(target_action_reprs: str) -> Tuple[str, str]:
    """Parse target_action_reprs to extract element type and text.
    
    Args:
        target_action_reprs: String like "[button] Submit -> CLICK"
    
    Returns:
        Tuple of (target_element_type, target_element_text)
    """
    match = re.match(TARGET_ACTION_REPRS_PATTERN_SIMPLE, target_action_reprs)
    if not match:
        raise ValueError(f"Invalid target action reprs: {target_action_reprs}")
    
    return match.group(1).strip(), match.group(2).strip()


def generate_step_instruction(target_action_reprs: str) -> str:
    """Convert target_action_reprs to natural language step instruction."""
    match = re.match(TARGET_ACTION_REPRS_PATTERN, target_action_reprs)
    if not match:
        raise ValueError(f"Invalid target action reprs: {target_action_reprs}")
    
    element_type, element_text, action_type, action_value = [
        g.strip() if g else g for g in match.groups()
    ]
    
    if action_type == "CLICK":
        if element_type == "heading":
            return f"Click on '{element_text}' in the heading"
        return f"Click on '{element_text}' {element_type}"
    elif action_type == "SELECT":
        return f"Select '{action_value}' in '{element_text}' {element_type}"
    elif action_type == "TYPE":
        return f"Type '{action_value}' in '{element_text}' {element_type}"
    else:
        return f"{action_type} on '{element_text}' {element_type}"


# ============================================================================
# Summary Printing
# ============================================================================

def print_trajectory_summary(stats: Dict[str, Any], split: str) -> None:
    """Print overall summary for all processed trajectories."""
    print(f"\n{'#'*80}")
    print(f"📊 OVERALL SUMMARY - {split.upper()} SPLIT")
    print(f"{'#'*80}\n")
    
    print(f"Split: {split}")
    print(f"Total trajectories processed: {len(stats)}")
    print(f"\nPer-trajectory statistics:")
    print(f"{'='*80}")
    print(f"{'Task UID':<40} {'Total':<8} {'Succeeded':<10} {'Saved':<8}")
    print(f"{'-'*80}")
    
    total_steps_all = 0
    total_succeeded_all = 0
    total_saved_all = 0
    
    for stat in stats:
        task_uid = stat.get('task_uid', 'N/A')
        steps_total = stat.get('steps_total', 0)
        steps_succeeded = stat.get('steps_succeeded', 0)
        steps_saved = stat.get('steps_saved', 0)
        
        if 'error' in stat:
            print(f"{task_uid:<40} {'ERROR':<8} {'-':<10} {'-':<8}")
        else:
            print(f"{task_uid:<40} {steps_total:<8} {steps_succeeded:<10} {steps_saved:<8}")
            total_steps_all += steps_total
            total_succeeded_all += steps_succeeded
            total_saved_all += steps_saved
    
    print(f"{'-'*80}")
    print(f"{'TOTAL':<40} {total_steps_all:<8} {total_succeeded_all:<10} {total_saved_all:<8}")
    print(f"{'='*80}\n")
    
    print(f"✅ All trajectories processed!")
    print(f"📊 Total steps across all trajectories: {total_steps_all}")
    print(f"✅ Total steps succeeded: {total_succeeded_all}")
    print(f"💾 Total steps saved: {total_saved_all}")
    print(f"❌ Total steps failed/skipped: {total_steps_all - total_succeeded_all}")
    if total_steps_all > 0:
        success_rate = (total_succeeded_all / total_steps_all) * 100
        print(f"📈 Success rate: {success_rate:.2f}%")
    print(f"{'#'*80}\n")


