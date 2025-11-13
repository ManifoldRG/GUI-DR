"""
Main Script - Orchestrates MHTML processing pipeline
"""

import asyncio
import argparse
import os
from datetime import datetime
from typing import Optional
from utils import load_parquet_files_by_split, find_tasks_from_parquet, print_trajectory_summary
from core import process_mhtml_actions
from ui.config import UIModificationConfig

DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
# DEBUG_TASK_UIDS = ['f4c21e9f-fbd7-4c45-a282-de06ae3b73c5'] # many button
# DEBUG_TASK_UIDS = ['0a2130e7-1108-4281-8772-25c8671fb88e',
#                     'ff173880-e7f5-4b4e-b941-79e9c3504add', # step 4 arrow and bbox are apart, INVESTIGATE coordinates update after scrolling and cropping
#                     '38fe67f7-14af-4259-8309-aa350abdc395', # 3rd star symbol div
#                     'e6643cfb-567e-4e11-8cab-f85483573539', # dense text interface
#                     'f4c21e9f-fbd7-4c45-a282-de06ae3b73c5', # many button
#                     '0cb50efe-4568-4c8d-bf0e-ed106cf99d1d'] # tiny magnifying glass icon top right corner
DEBUG_TASK_UIDS = None
SHOULD_RANDOMIZE = True
HEADLESS = True
# DEBUG_TASK_UIDS = None


async def main(split: str = 'train', ui_config: Optional[UIModificationConfig] = None):
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

    if DEBUG_TASK_UIDS:
        parquet_task_uids = DEBUG_TASK_UIDS
        # parquet_task_uids = parquet_task_uids[:2]
        hf_parquet_df = hf_parquet_df[hf_parquet_df['annotation_id'].isin(parquet_task_uids)]
    
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
                run_dir,
                headless=HEADLESS,
                should_randomize=SHOULD_RANDOMIZE,
                ui_config=ui_config
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


def str_to_bool(v):
    """Convert string to boolean for argparse."""
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError(f'Boolean value expected, got: {v}')


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

    parser.add_argument(
        '--enable_zoom',
        type=str_to_bool,
        default=False,
        help='Enable zoom (default: False)'
    )

    parser.add_argument(
        '--zoom_level',
        type=float,
        default=0.7,
        help='Zoom level (default: 0.7)'
    )

    parser.add_argument(
        '--enable_dense_info',
        type=str_to_bool,
        default=False,
        help='Enable dense info (default: False)'
    )

    parser.add_argument(
        '--enable_style_variants',
        type=str_to_bool,
        default=True,
        help='Enable style variants (default: True)'
    )

    args = parser.parse_args()
    
    print(f"🚀 Processing {args.split} split")
    asyncio.run(
        main(
            split=args.split, 
            ui_config=UIModificationConfig(
                enable_zoom=args.enable_zoom, 
                zoom_level=args.zoom_level, 
                enable_dense_info=args.enable_dense_info, 
                enable_style_variants=args.enable_style_variants
            )
        )
    )
