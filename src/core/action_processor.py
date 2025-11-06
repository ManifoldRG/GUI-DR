"""
Action processing logic for individual steps in a trajectory.
"""

import os
import json
from typing import Dict, Any, Optional
import pandas as pd

from .mhtml_processor import MHTMLProcessor
from exceptions import ElementLocatorError
from utils.data_loaders import load_dom_content_json, load_action_list_from_mhtml, load_current_page_urls
from utils.helpers import setup_result_dirs, parse_target_action_reprs, generate_step_instruction


def _extract_parquet_data(parquet_row: pd.DataFrame) -> Dict[str, Any]:
    """Extract and validate data from a parquet row."""
    if parquet_row.empty:
        return None
    
    pos_candidate = parquet_row['pos_candidates'].iloc[0]
    if not pos_candidate or len(pos_candidate) == 0:
        return None
    
    return {
        'pos_candidate': pos_candidate[0],
        'confirmed_task': parquet_row['confirmed_task'].iloc[0],
        'action_op': parquet_row['operation'].iloc[0]['op'],
        'target_action_reprs': parquet_row['target_action_reprs'].iloc[0],
        'type_action_value': parquet_row['operation'].iloc[0]['value']
    }




async def process_mhtml_actions(
    dom_content_json_path: str,
    hf_parquet_df: pd.DataFrame,
    mhtml_files_dir: str,
    task_uid: str,
    refresh_ui_params_per_step: bool,
    run_dir: str
) -> Dict[str, Any]:
    """Main processing function for a single trajectory.
    
    Args:
        dom_content_json_path: Path to dom_content.json file
        hf_parquet_df: Combined parquet dataframe (filtered by annotation_id)
        mhtml_files_dir: Directory containing MHTML files
        task_uid: Task UID (annotation_id) to filter parquet data
        refresh_ui_params_per_step: Whether to refresh UI params per step
        run_dir: The run directory name to save all outputs
    
    Returns:
        Dict with keys: 'steps_total', 'steps_succeeded', 'steps_saved', 'task_uid'
    """
    from playwright.async_api import async_playwright
    
    # Use MHTML file names as ground truth for action_uids
    action_uids = load_action_list_from_mhtml(mhtml_files_dir)
    
    if not action_uids:
        raise ValueError(f"No MHTML files found in {mhtml_files_dir}")
    
    print(f"📋 Found {len(action_uids)} MHTML files (action_uids) in snapshots directory")
    
    # Load dom_content.json for page URLs (optional)
    try:
        dom_content_json = load_dom_content_json(dom_content_json_path)
        current_page_urls = load_current_page_urls(dom_content_json, action_uids)
    except Exception as e:
        print(f"⚠️  Warning: Could not load page URLs from dom_content.json: {e}")
        print(f"   Continuing without page URL tracking...")
        current_page_urls = [''] * len(action_uids)
    
    # Filter parquet dataframe by annotation_id (task_uid)
    hf_parquet_file = hf_parquet_df[hf_parquet_df['annotation_id'] == task_uid].copy()
    
    if hf_parquet_file.empty:
        print(f"⚠️  Warning: No data found in parquet files for task_uid: {task_uid}")
        print(f"   Will process MHTML files but skip steps without parquet data")
    else:
        # Check how many action_uids have parquet data
        parquet_action_uids = set(hf_parquet_file['action_uid'].unique())
        mhtml_action_uids = set(action_uids)
        missing_in_parquet = mhtml_action_uids - parquet_action_uids
        if missing_in_parquet:
            print(f"⚠️  Warning: {len(missing_in_parquet)} action_uids from MHTML files not found in parquet:")
            for uid in sorted(missing_in_parquet)[:5]:
                print(f"      - {uid}")
            if len(missing_in_parquet) > 5:
                print(f"      ... and {len(missing_in_parquet) - 5} more")
        print(f"✅ Found parquet data for {len(parquet_action_uids & mhtml_action_uids)}/{len(action_uids)} action_uids")

    task_screenshots_dir, trajectory_file = setup_result_dirs(run_dir, task_uid)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            java_script_enabled=True,
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        processor = MHTMLProcessor(
            page,
            screenshots_base_dir=task_screenshots_dir,
            refresh_ui_params_per_step=refresh_ui_params_per_step
        )

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
                
                if not os.path.exists(mhtml_path):
                    print(f"⏭️  Skipping step {i+1}: MHTML file not found: {mhtml_path}")
                    print(f"{'='*60}")
                    continue
                
                # Try to get data from parquet
                parquet_row = hf_parquet_file[hf_parquet_file['action_uid'] == action_uid]
                parquet_data = _extract_parquet_data(parquet_row)
                
                if parquet_data is None:
                    print(f"⏭️  Skipping step {i+1}: No parquet data found for action UID {action_uid}")
                    print(f"   MHTML file exists but no metadata in parquet files")
                    print(f"{'='*60}")
                    continue
                
                target_element_type, target_element_text = parse_target_action_reprs(
                    parquet_data['target_action_reprs']
                )
                step_instruction = generate_step_instruction(parquet_data['target_action_reprs'])

                print(f"Confirmed Task: {parquet_data['confirmed_task']}")
                print(f"Action Op: {parquet_data['action_op']}")
                print(f"Target Action Reprs: {parquet_data['target_action_reprs']}")
                print(f"Target Element Type: {target_element_type}")
                print(f"Target Element Text: {target_element_text}")
                print(f"Step Instruction: {step_instruction}")
                print(f"Pos Candidate: {parquet_data['pos_candidate']}")
                print(f"Type Action Value: {parquet_data['type_action_value']}")
                print(f"Current Page URL: {current_page_urls[i]}")
                
                # Load MHTML
                await processor.load_mhtml(mhtml_path)

                # Update page pre-actions reset flag if URL changed
                if last_page_url != current_page_urls[i]:
                    should_reset_page_pre_actions = True
                    last_page_url = current_page_urls[i]

                # Process action
                result = await processor.process_action(
                    action_uid,
                    parquet_data['action_op'],
                    parquet_data['type_action_value'],
                    parquet_data['pos_candidate'],
                    target_element_type,
                    target_element_text,
                    step_index=i,
                    should_reset_page_pre_actions=should_reset_page_pre_actions,
                    should_randomize=True
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
                    'confirmed_task': parquet_data['confirmed_task'],
                    'action_uid': result['action_uid'],
                    'op': result['op'],
                    'pos_candidate': parquet_data['pos_candidate'],
                    'target_element_type': target_element_type,
                    'target_element_text': target_element_text,
                    'type_action_value': parquet_data['type_action_value'],
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
                
            except (ElementLocatorError, IndexError, ValueError, KeyError) as e:
                error_type = type(e).__name__
                print(f"⏭️  Skipping step {i+1}: {error_type} - {str(e)}")
                print(f"   Step cannot be processed, skipping to next step")
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

