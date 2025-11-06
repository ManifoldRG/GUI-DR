"""
Main Script - Orchestrates MHTML processing pipeline
"""

import asyncio
import argparse
from datetime import datetime

from data_loaders import load_parquet_files_by_split
from task_discovery import find_tasks_from_parquet
from action_processor import process_mhtml_actions
from summary import print_trajectory_summary


async def main(split: str = 'train'):
    """Entry point - loads parquet files for specified split and processes corresponding tasks.
    
    Args:
        split: One of 'train', 'test_domain', 'test_task', 'test_website'
    
    Data structure:
    - mm_mind2web/task/<task_uid>/processed/dom_content.json
    - mm_mind2web/task/<task_uid>/processed/snapshots/ (MHTML files)
    - mm_mind2web/data/<split>-*.parquet
    """
    mm_mind2web_base = "mm_mind2web"
    valid_splits = ['train', 'test_domain', 'test_task', 'test_website']
    
    if split not in valid_splits:
        raise ValueError(f"Invalid split: {split}. Must be one of {valid_splits}")
    
    refresh_ui_params_per_step = True
    
    # Load parquet files for the specified split
    print(f"\n{'='*80}")
    print(f"📦 Loading {split} parquet files from {mm_mind2web_base}/data/...")
    print(f"{'='*80}\n")
    
    hf_parquet_df, parquet_task_uids = load_parquet_files_by_split(mm_mind2web_base, split)
    
    if len(parquet_task_uids) == 0:
        raise ValueError(f"No tasks found in {split} parquet files")
    
    # Find corresponding task folders
    print(f"\n{'='*80}")
    print(f"🔍 Finding task folders for {len(parquet_task_uids)} tasks from {split} split...")
    print(f"{'='*80}\n")
    
    task_folders = find_tasks_from_parquet(mm_mind2web_base, parquet_task_uids)
    
    if not task_folders:
        raise ValueError(f"No task folders found for tasks in {split} split")
    
    print(f"\n✅ Found {len(task_folders)} task folder(s) with MHTML files\n")
    
    # Build lists from found folders
    task_uids = [task_uid for task_uid, _, _ in task_folders]
    dom_content_json_paths = [dom_path for _, dom_path, _ in task_folders]
    mhtml_files_dirs = [snapshots_dir for _, _, snapshots_dir in task_folders]
    
    # Generate run directory with timestamp and split
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = f"outputs/run_{run_timestamp}_{split}"
    
    # Process each trajectory
    trajectory_stats = []
    total_trajectories = len(task_uids)
    
    print(f"\n{'#'*80}")
    print(f"🚀 Starting batch processing of {total_trajectories} trajectory/trajectories from {split} split")
    print(f"📁 All outputs will be saved in: {run_dir}/")
    print(f"{'#'*80}\n")
    
    for idx, (dom_content_json_path, mhtml_files_dir, task_uid) in enumerate(
        zip(dom_content_json_paths, mhtml_files_dirs, task_uids), 1
    ):
        print(f"\n{'#'*80}")
        print(f"📋 Processing trajectory {idx}/{total_trajectories}: {task_uid}")
        print(f"{'#'*80}\n")
        
        try:
            stats = await process_mhtml_actions(
                dom_content_json_path,
                hf_parquet_df,
                mhtml_files_dir,
                task_uid,
                refresh_ui_params_per_step,
                run_dir
            )
            trajectory_stats.append(stats)
        except Exception as e:
            print(f"\n❌ Error processing trajectory {task_uid}: {str(e)}")
            trajectory_stats.append({
                'task_uid': task_uid,
                'steps_total': 0,
                'steps_succeeded': 0,
                'steps_saved': 0,
                'error': str(e)
            })
    
    # Print overall summary
    print_trajectory_summary(trajectory_stats, split)
    print(f"📁 All outputs saved in: {run_dir}/")
    print(f"   Structure: {run_dir}/<task_id>/screenshots/ and {run_dir}/<task_id>/trajectory.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Process MHTML files with UI randomization based on parquet data splits',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py                    # Process train split (default)
  python src/main.py --split test_domain
  python src/main.py -s test_task
  python src/main.py --split test_website
        """
    )
    
    parser.add_argument(
        '--split', '-s',
        type=str,
        default='train',
        choices=['train', 'test_domain', 'test_task', 'test_website'],
        help='Data split to process (default: train)'
    )
    
    args = parser.parse_args()
    
    print(f"🚀 Processing {args.split} split")
    asyncio.run(main(split=args.split))
