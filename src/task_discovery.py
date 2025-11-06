"""
Task discovery utilities for finding task folders and matching with parquet data.
"""

import os
from typing import List, Tuple


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

