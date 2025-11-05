"""
Main Script - Orchestrates MHTML processing pipeline
"""

import asyncio
import json
import re
import os
from datetime import datetime
from playwright.async_api import async_playwright
from mhtml_processor import MHTMLProcessor
import pandas as pd
import ast
from typing import List, Dict, Any


def load_dom_content_json(dom_content_json_path: str) -> List[str]:
    """Load dom content from JSON file"""
    with open(dom_content_json_path, 'r') as f:
        dom_content_json = json.load(f)

    return dom_content_json

def load_action_list(dom_content_json: List) -> List[str]:
    """Load action list from dom content"""
    action_uids = [item['action_uid'] for item in dom_content_json]

    return action_uids

def load_current_page_urls(dom_content_json: List) -> List[str]:
    """Load current page urls from dom content"""
    current_page_urls = [item['before']['dom']['strings'][1] for item in dom_content_json]

    return current_page_urls

def setup_result_dirs(run_dir: str, task_uid: str):
    """Set up directory structure: run_<timestamp>/<task_id>/screenshots/ and trajectory.json
    
    Args:
        run_dir: The run directory name (e.g., "run_20251104_123456")
        task_uid: The task UID to use as the folder name
        
    Returns:
        tuple: (task_screenshots_dir, trajectory_file)
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

def generate_step_instruction(target_action_reprs: str) -> str:
    """Convert target_action_reprs to natural language step instruction"""
    pattern = r"\[(.*?)\]\s(.*?)\s->\s(CLICK|SELECT|TYPE)(?:\s*:\s*(.*))?"
    match = re.match(pattern, target_action_reprs)
    if not match:
        raise ValueError(f"Invalid target action reprs: {target_action_reprs}")
    
    element_type, element_text, action_type, action_value = [g.strip() if g else g for g in match.groups()]
    
    if action_type == "CLICK":
        if element_type == "heading":
            return f"Click on '{element_text}' in the heading"
        else:
            return f"Click on '{element_text}' {element_type}"
    elif action_type == "SELECT":
        return f"Select '{action_value}' in '{element_text}' {element_type}"
    elif action_type == "TYPE":
        return f"Type '{action_value}' in '{element_text}' {element_type}"
    else:
        return f"{action_type} on '{element_text}' {element_type}"


async def process_mhtml_actions(dom_content_json_path: str, hf_parquet_df: pd.DataFrame, mhtml_files_dir: str, task_uid: str, refresh_ui_params_per_step: bool, run_dir: str):
    """Main processing function
    
    Args:
        dom_content_json_path: Path to dom_content.json file
        hf_parquet_df: Combined parquet dataframe (filtered by annotation_id)
        mhtml_files_dir: Directory containing MHTML files
        task_uid: Task UID (annotation_id) to filter parquet data
        refresh_ui_params_per_step: Whether to refresh UI params per step
        run_dir: The run directory name (e.g., "run_20251104_123456") to save all outputs
    
    Returns:
        dict with keys: 'steps_total', 'steps_succeeded', 'steps_saved', 'task_uid'
    """
    dom_content_json = load_dom_content_json(dom_content_json_path)
    action_uids = load_action_list(dom_content_json)
    current_page_urls = load_current_page_urls(dom_content_json)
    
    # Filter parquet dataframe by annotation_id (task_uid)
    hf_parquet_file = hf_parquet_df[hf_parquet_df['annotation_id'] == task_uid].copy()
    
    if hf_parquet_file.empty:
        raise ValueError(f"No data found in parquet files for task_uid: {task_uid}")

    if not action_uids:
        raise ValueError("No actions to process")

    task_screenshots_dir, trajectory_file = setup_result_dirs(run_dir, task_uid)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        # Set viewport to 1920x1080 to ensure we can crop properly
        context = await browser.new_context(
            java_script_enabled=True,
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        processor = MHTMLProcessor(page, screenshots_base_dir=task_screenshots_dir, refresh_ui_params_per_step=refresh_ui_params_per_step)

        trajectory = []
        last_page_url = None
        should_reset_page_pre_actions = False
        steps_total = len(action_uids)
        steps_succeeded = 0
        steps_saved = 0
        
        for i, action_uid in enumerate(action_uids):
            try:
                print(f"\n{'='*60}")
                print(f"Processing task {task_uid} - action {i+1}/{len(action_uids)}")
                print(f"Action UID: {action_uid}")
                
                mhtml_path = os.path.join(mhtml_files_dir, f"{action_uid}_before.mhtml")
                pos_candidate = hf_parquet_file[hf_parquet_file['action_uid'] == action_uid]['pos_candidates'].iloc[0][0]
                confirmed_task = hf_parquet_file[hf_parquet_file['action_uid'] == action_uid]['confirmed_task'].iloc[0]
                action_op = hf_parquet_file[hf_parquet_file['action_uid'] == action_uid]['operation'].iloc[0]['op']
                target_action_reprs = hf_parquet_file[hf_parquet_file['action_uid'] == action_uid]['target_action_reprs'].iloc[0]
                type_action_value = hf_parquet_file[hf_parquet_file['action_uid'] == action_uid]['operation'].iloc[0]['value']

                pattern = r"\[(.*?)\]\s(.*?)\s->.*"

                match = re.match(pattern, target_action_reprs)
                if match:
                    target_element_type = match.group(1).strip()
                    target_element_text = match.group(2).strip()
                else:
                    raise ValueError(f"Invalid target action reprs: {target_action_reprs}")

                step_instruction = generate_step_instruction(target_action_reprs)

                print(f"Confirmed Task: {confirmed_task}")
                print(f"Action Op: {action_op}")
                print(f"Target Action Reprs: {target_action_reprs}")
                print(f"Target Element Type: {target_element_type}")
                print(f"Target Element Text: {target_element_text}")
                print(f"Step Instruction: {step_instruction}")
                print(f"Pos Candidate: {pos_candidate}")
                print(f"Type Action Value: {type_action_value}")
                print(f"Current Page URL: {current_page_urls[i]}")
                
                # Load MHTML - this will clear page state (close menus) but preserve page_pre_actions
                await processor.load_mhtml(mhtml_path)

                if last_page_url != current_page_urls[i]:
                    should_reset_page_pre_actions = True
                    last_page_url = current_page_urls[i]

                # Try to process action, skip step if element cannot be found with 100% confidence

                result = await processor.process_action(
                    action_uid,
                    action_op,
                    type_action_value,
                    pos_candidate,
                    target_element_type,
                    target_element_text,
                    step_index=i,
                    should_reset_page_pre_actions=should_reset_page_pre_actions
                )
                should_reset_page_pre_actions = False

                # Only add to trajectory if element was found with 100% confidence
                if not result['augmentation_success']:
                    print(f"⏭️  Skipping step {i+1}: Element not found with 100% confidence")
                    print(f"{'='*60}")
                    continue

                steps_succeeded += 1

                coordinates = []
                if result['op'] != 'TYPE' and result['coordinates']:
                    coordinates = list(result['coordinates'])
                
                # Add action data to trajectory list
                action_data = {
                    'confirmed_task': confirmed_task,
                    'action_uid': result['action_uid'],
                    'op': result['op'],
                    'pos_candidate': pos_candidate,
                    'target_element_type': target_element_type,
                    'target_element_text': target_element_text,
                    'type_action_value': type_action_value,
                    'step_instruction': step_instruction,
                    'coordinates': coordinates,
                    'bounding_box': result['bounding_box'],
                    'screenshot': result['screenshot'],
                    'augmentation_success': result['augmentation_success'],
                    'ui_params': result.get('ui_params')
                }
                trajectory.append(action_data)
                print(f"{'='*60}")

                # Save trajectory after successful step
                with open(trajectory_file, 'w') as f:
                    json.dump(trajectory, f, indent=2)
                steps_saved = len(trajectory)
                print(f"💾 Trajectory saved: {trajectory_file} (step {i+1}/{len(action_uids)})")
            except Exception as e:
                # Skip step if element finding fails (ElementNotFoundError, AmbiguousMatchError, etc.)
                error_type = type(e).__name__
                print(f"⏭️  Skipping step {i+1}: {error_type} - {str(e)}")
                print(f"   Element cannot be found with 100% confidence, skipping to next step")
                print(f"{'='*60}")
                should_reset_page_pre_actions = False
                continue

        processor.reset_ui_params_cache()
        await browser.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"✅ Processing complete for trajectory {task_uid}!")
    print(f"📊 Total steps: {steps_total}")
    print(f"✅ Steps succeeded: {steps_succeeded}")
    print(f"💾 Steps saved: {steps_saved}")
    print(f"❌ Steps failed/skipped: {steps_total - steps_succeeded}")
    print(f"{'='*60}")
    
    return {
        'task_uid': task_uid,
        'steps_total': steps_total,
        'steps_succeeded': steps_succeeded,
        'steps_saved': steps_saved
    }


def discover_task_folders(mm_mind2web_base: str) -> List[tuple]:
    """Discover all task folders with processed/dom_content.json
    
    Looks in mm_mind2web_base/task/ directory
    
    Returns:
        List of tuples: (task_uid, dom_content_json_path, mhtml_files_dir)
    """
    task_folders = []
    
    task_dir = os.path.join(mm_mind2web_base, "task")
    
    if not os.path.exists(task_dir):
        raise ValueError(f"Task directory not found: {task_dir}")
    
    for item in os.listdir(task_dir):
        try:
            item_path = os.path.join(task_dir, item)
            
            # Check if it's a directory
            if not os.path.isdir(item_path):
                continue
            
            # Check if it has processed/dom_content.json
            dom_content_path = os.path.join(item_path, "processed", "dom_content.json")
            snapshots_dir = os.path.join(item_path, "processed", "snapshots")
            
            if os.path.exists(dom_content_path) and os.path.exists(snapshots_dir):
                task_folders.append((item, dom_content_path, snapshots_dir))
                print(f"✅ Found task folder: {item}")
        except Exception as e:
            print(f"⚠️  Warning: Failed to process task folder {item}: {e}")
            continue
        
    return task_folders


def load_parquet_files(mm_mind2web_base: str, task_uids: List[str]) -> pd.DataFrame:
    """Load all parquet files from mm_mind2web_base/data/, keeping only needed columns
    
    Columns needed:
    - action_uid
    - pos_candidates
    - confirmed_task
    - operation
    - target_action_reprs
    - annotation_id
    
    Returns:
        Combined and sorted dataframe
    """
    parquet_files = []
    
    data_dir = os.path.join(mm_mind2web_base, "data")
    
    if not os.path.exists(data_dir):
        raise ValueError(f"Data directory not found: {data_dir}")
    
    # Find all parquet files
    for item in os.listdir(data_dir):
        if item.endswith('.parquet'):
            parquet_path = os.path.join(data_dir, item)
            parquet_files.append(parquet_path)
            print(f"✅ Found parquet file: {item}")
    
    if not parquet_files:
        raise ValueError(f"No parquet files found in {data_dir}")
    
    # Columns to load (only what we need)
    columns_to_load = ['action_uid', 'pos_candidates', 'confirmed_task', 'operation', 
                       'target_action_reprs', 'annotation_id']
    
    # Load each parquet file with only needed columns
    dataframes = []
    for parquet_path in parquet_files:
        print(f"📂 Loading columns from {os.path.basename(parquet_path)}...")
        try:
            df = pd.read_parquet(parquet_path, columns=columns_to_load)
            # Parse operation column if it's a string representation of a dict/list
            if 'operation' in df.columns:
                def parse_operation(x):
                    if isinstance(x, str):
                        try:
                            return ast.literal_eval(x)
                        except (ValueError, SyntaxError):
                            return x
                    return x
                df['operation'] = df['operation'].apply(parse_operation)
            dataframes.append(df)
        except Exception as e:
            print(f"⚠️  Warning: Failed to load {parquet_path}: {e}")
            continue
    
    if not dataframes:
        raise ValueError("No parquet files could be loaded")
    
    # Concatenate all dataframes
    print(f"📊 Concatenating {len(dataframes)} parquet files...")
    combined_df = pd.concat(dataframes, ignore_index=True)
    
    # Sort by annotation_id
    print(f"🔢 Sorting by annotation_id...")
    combined_df = combined_df.sort_values('annotation_id').reset_index(drop=True)
    combined_df = combined_df[combined_df['annotation_id'].isin(task_uids)]

    print(f"✅ Loaded {len(combined_df)} rows from {len(dataframes)} parquet file(s) for {len(task_uids)} task(s)")
    
    return combined_df


async def main():
    """Entry point - automatically discovers task folders and parquet files
    
    Data structure:
    - mm_mind2web/task/<task_uid>/processed/dom_content.json
    - mm_mind2web/task/<task_uid>/processed/snapshots/ (MHTML files)
    - mm_mind2web/data/<parquet_file>.parquet
    """
    # Base directory for all source data
    mm_mind2web_base = "mm_mind2web"
    
    refresh_ui_params_per_step = True
    
    # Discover task folders
    print(f"\n{'='*80}")
    print(f"🔍 Discovering task folders in {mm_mind2web_base}/task/...")
    print(f"{'='*80}\n")
    
    task_folders = discover_task_folders(mm_mind2web_base)
    
    if not task_folders:
        raise ValueError(f"No task folders found in {mm_mind2web_base}/task")
    
    print(f"\n✅ Found {len(task_folders)} task folder(s)\n")
    
    # Discover and load parquet files
    print(f"{'='*80}")
    print(f"📦 Loading parquet files from {mm_mind2web_base}/data/...")
    print(f"{'='*80}\n")
    
    # Build lists from discovered folders
    task_uids = [task_uid for task_uid, _, _ in task_folders]
    task_uids = ['277e3468-f8cb-45c6-9e4b-0328066c42d3'] # '000ada18-5007-4fd4-8a12-8987ba543d31' not in parquet files somehow?
    dom_content_json_paths = [dom_path for item, dom_path, _ in task_folders if item in task_uids]
    mhtml_files_dirs = [snapshots_dir for item, _, snapshots_dir in task_folders if item in task_uids]
    hf_parquet_df = load_parquet_files(mm_mind2web_base, task_uids)
    
    # Generate a single run timestamp for this batch
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = f"outputs/run_{run_timestamp}"
    
    # Process each trajectory
    trajectory_stats = []
    total_trajectories = len(task_uids)
    
    print(f"\n{'#'*80}")
    print(f"🚀 Starting batch processing of {total_trajectories} trajectory/trajectories")
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
    print(f"\n{'#'*80}")
    print(f"📊 OVERALL SUMMARY")
    print(f"{'#'*80}\n")
    
    print(f"Total trajectories processed: {len(trajectory_stats)}")
    print(f"\nPer-trajectory statistics:")
    print(f"{'='*80}")
    print(f"{'Task UID':<40} {'Total':<8} {'Succeeded':<10} {'Saved':<8}")
    print(f"{'-'*80}")
    
    total_steps_all = 0
    total_succeeded_all = 0
    total_saved_all = 0
    
    for stats in trajectory_stats:
        task_uid = stats.get('task_uid', 'N/A')
        steps_total = stats.get('steps_total', 0)
        steps_succeeded = stats.get('steps_succeeded', 0)
        steps_saved = stats.get('steps_saved', 0)
        
        if 'error' in stats:
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
    print(f"📁 All outputs saved in: {run_dir}/")
    print(f"   Structure: {run_dir}/<task_id>/screenshots/ and {run_dir}/<task_id>/trajectory.json")
    print(f"📊 Total steps across all trajectories: {total_steps_all}")
    print(f"✅ Total steps succeeded: {total_succeeded_all}")
    print(f"💾 Total steps saved: {total_saved_all}")
    print(f"❌ Total steps failed/skipped: {total_steps_all - total_succeeded_all}")
    if total_steps_all > 0:
        success_rate = (total_succeeded_all / total_steps_all) * 100
        print(f"📈 Success rate: {success_rate:.2f}%")
    print(f"{'#'*80}\n")

if __name__ == "__main__":
    asyncio.run(main())
