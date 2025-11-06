"""
File and directory utility functions.
"""

import os
from typing import Tuple


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

