#!/usr/bin/env python3
"""
Load all variant data from variant_reviews.csv into a DataFrame.

For each entry in variant_reviews.csv, extracts:
- Image file paths from all 4 variants
- step_instruction and multi_element_instruction from all 4 variants
- Combines into a single DataFrame
"""

import pandas as pd
from pathlib import Path
import json
import re
from typing import Optional, Tuple, List, Dict

# ROOT GOLDEN SET mapping: base split -> variant
ROOT_GOLDEN_SET = {
    'test_domain': 'original',
    'test_task': 'style',
    'test_website': 'style'
}


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


def find_run_folder_for_images(project_root: Path, base_split: str, variant: str) -> Optional[Path]:
    """Find run folder for images in final_data_filtered."""
    final_data_dir = project_root / "final_data_filtered"
    if not final_data_dir.exists():
        return None
    
    for run_folder in final_data_dir.iterdir():
        if not run_folder.is_dir():
            continue
        
        extracted_base, extracted_variant = extract_split_from_run_folder(run_folder.name)
        if extracted_base == base_split and extracted_variant == variant:
            return run_folder
    
    return None


def find_run_folder_for_trajectory(project_root: Path, base_split: str, variant: str) -> Optional[Path]:
    """Find run folder for trajectory.json in final_data."""
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
    
    # Try other action types
    for action_type in ['select', 'type', 'scroll']:
        image_file = visualizations_dir / f"step_{step_index}_{action_type}_with_bbox.png"
        if image_file.exists():
            return image_file
    
    # Fallback: search for any matching step
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


def get_trajectory_entry_data(trajectory_path: Path, step_index: int) -> Dict:
    """
    Get all data from trajectory entry for a specific step_index.
    
    Returns dict with:
    - step_instruction
    - multi_element_instruction
    - screenshot_path (str or None)
    - target_coordinates (list [x, y] or None)
    - target_bounding_box (list [x, y, width, height] or None)
    - nearest_element_text (str or None)
    - nearest_element_relative_position (list or None)
    - nearest_element_tag (str or None)
    - nearest_element_distance (float or None)
    - nearest_element_bounding_box (list [x, y, width, height] or None)
    """
    default_result = {
        'step_instruction': None,
        'multi_element_instruction': None,
        'screenshot_path': None,
        'target_coordinates': None,
        'target_bounding_box': None,
        'nearest_element_text': None,
        'nearest_element_relative_position': None,
        'nearest_element_tag': None,
        'nearest_element_distance': None,
        'nearest_element_bounding_box': None
    }
    
    if not trajectory_path or not trajectory_path.exists():
        return default_result
    
    try:
        with open(trajectory_path, 'r') as f:
            trajectory_data = json.load(f)
        
        for idx, entry in enumerate(trajectory_data):
            entry_step_index = extract_step_index_from_entry(entry, idx)
            if entry_step_index == step_index:
                # Start with default result to ensure all fields are present
                result = default_result.copy()
                
                # Update with actual values from entry
                # Use .get() which returns None if key doesn't exist
                result['step_instruction'] = entry.get("step_instruction")
                result['multi_element_instruction'] = entry.get("multi_element_instruction")
                result['screenshot_path'] = entry.get("screenshot")
                result['target_coordinates'] = entry.get("coordinates")
                result['target_bounding_box'] = entry.get("bounding_box")
                
                # Extract nearest element data
                nearest_element = entry.get("nearest_element")
                if nearest_element:
                    result['nearest_element_text'] = nearest_element.get("text")
                    result['nearest_element_relative_position'] = nearest_element.get("relative_position")
                    result['nearest_element_tag'] = nearest_element.get("tag")
                    result['nearest_element_distance'] = nearest_element.get("distance")
                    result['nearest_element_bounding_box'] = nearest_element.get("bounding_box")
                # else: already None from default_result
                
                return result
        
        return default_result
    except Exception as e:
        print(f"⚠️  Error reading trajectory.json: {e}")
        return default_result


def load_variant_data(variant_reviews_csv: Path, project_root: Path) -> pd.DataFrame:
    """
    Load all variant data into a DataFrame.
    
    Returns DataFrame with columns:
    - task_id
    - step_index
    - split (from variant_reviews.csv)
    - decision (from variant_reviews.csv)
    - variant (original/precision/style/text_shrink)
    - image_path
    - screenshot_path (from trajectory.json)
    - step_instruction
    - multi_element_instruction
    - target_coordinates
    - target_bounding_box
    - nearest_element_text
    - nearest_element_relative_position
    - nearest_element_tag
    - nearest_element_distance
    - nearest_element_bounding_box
    """
    # Load variant_reviews.csv
    print(f"Loading {variant_reviews_csv}...")
    reviews_df = pd.read_csv(variant_reviews_csv)
    print(f"Found {len(reviews_df)} entries")
    
    # Filter to only keep entries with decision == 'keep'
    reviews_df = reviews_df[reviews_df['decision'] == 'keep'].copy()
    print(f"Filtered to {len(reviews_df)} entries with decision='keep'")
    
    rows = []
    
    for idx, row in reviews_df.iterrows():
        task_id = str(row['task_id'])
        step_index = int(row['step_index'])
        golden_split = str(row['split'])
        decision = str(row['decision'])

        # Get base split from golden split
        base_split = get_base_split_from_golden_split(golden_split)
        if not base_split:
            print(f"⚠️  Could not determine base split from '{golden_split}' for task {task_id}, step {step_index}. Skipping...")
            continue
        
        # Process all 4 variants
        for variant_name in ['original', 'precision', 'style', 'text_shrink']:
            # Find run folders - images from final_data_filtered, trajectory from final_data
            image_run_folder = find_run_folder_for_images(project_root, base_split, variant_name)
            trajectory_run_folder = find_run_folder_for_trajectory(project_root, base_split, variant_name)
            
            # Get image path from final_data_filtered
            image_path = None
            image_path_str = None
            if image_run_folder:
                image_task_folder = image_run_folder / task_id
                if image_task_folder.exists():
                    image_path = get_visualization_image(image_task_folder, step_index)
                    image_path_str = str(image_path) if image_path and image_path.exists() else None
            
            # Get all trajectory data from trajectory.json in final_data
            trajectory_path = None
            if trajectory_run_folder:
                trajectory_task_folder = trajectory_run_folder / task_id
                trajectory_path = trajectory_task_folder / "trajectory.json"
            
            trajectory_data = get_trajectory_entry_data(trajectory_path, step_index)
            
            rows.append({
                'task_id': task_id,
                'step_index': step_index,
                'split': golden_split,
                'decision': decision,
                'variant': variant_name,
                'image_path': image_path_str,
                'screenshot_path': trajectory_data['screenshot_path'],
                'step_instruction': trajectory_data['step_instruction'],
                'multi_element_instruction': trajectory_data['multi_element_instruction'],
                'target_coordinates': json.dumps(trajectory_data['target_coordinates']) if trajectory_data['target_coordinates'] else None,
                'target_bounding_box': json.dumps(trajectory_data['target_bounding_box']) if trajectory_data['target_bounding_box'] else None,
                'nearest_element_text': trajectory_data['nearest_element_text'],
                'nearest_element_relative_position': json.dumps(trajectory_data['nearest_element_relative_position']) if trajectory_data['nearest_element_relative_position'] else None,
                'nearest_element_tag': trajectory_data['nearest_element_tag'],
                'nearest_element_distance': trajectory_data['nearest_element_distance'],
                'nearest_element_bounding_box': json.dumps(trajectory_data['nearest_element_bounding_box']) if trajectory_data['nearest_element_bounding_box'] else None
            })
        
        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx + 1}/{len(reviews_df)} entries...")
    
    df = pd.DataFrame(rows)
    print(f"\n✓ Created DataFrame with {len(df)} rows")
    print(f"  Columns: {', '.join(df.columns)}")
    print(f"  Unique task_id/step_index pairs: {len(reviews_df)}")
    print(f"  Variants per pair: {len(df) // len(reviews_df) if len(reviews_df) > 0 else 0}")
    
    return df


def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    variant_reviews_csv = script_dir / "variant_reviews.csv"
    output_csv = script_dir / "final_variant_data.csv"
    
    if not variant_reviews_csv.exists():
        print(f"Error: {variant_reviews_csv} not found")
        return
    
    # Load all variant data
    df = load_variant_data(variant_reviews_csv, project_root)
    
    # Save to CSV
    print(f"\nSaving to {output_csv}...")
    df.to_csv(output_csv, index=False)
    print(f"✓ Saved {len(df)} rows to {output_csv}")
    
    # Print summary statistics
    print("\n" + "="*80)
    print("Summary Statistics:")
    print("="*80)
    print(f"Total rows: {len(df)}")
    print(f"Unique (task_id, step_index) pairs: {df[['task_id', 'step_index']].drop_duplicates().shape[0]}")
    print(f"\nBy variant:")
    print(df['variant'].value_counts())
    print(f"\nBy decision:")
    print(df['decision'].value_counts())
    print(f"\nMissing data:")
    print(f"  image_path: {df['image_path'].isna().sum()}")
    print(f"  screenshot_path: {df['screenshot_path'].isna().sum()}")
    print(f"  step_instruction: {df['step_instruction'].isna().sum()}")
    print(f"  multi_element_instruction: {df['multi_element_instruction'].isna().sum()}")
    print(f"  target_coordinates: {df['target_coordinates'].isna().sum()}")
    print(f"  target_bounding_box: {df['target_bounding_box'].isna().sum()}")
    print(f"  nearest_element_text: {df['nearest_element_text'].isna().sum()}")
    print(f"  nearest_element_relative_position: {df['nearest_element_relative_position'].isna().sum()}")
    print(f"  nearest_element_tag: {df['nearest_element_tag'].isna().sum()}")
    print(f"  nearest_element_distance: {df['nearest_element_distance'].isna().sum()}")
    print(f"  nearest_element_bounding_box: {df['nearest_element_bounding_box'].isna().sum()}")
    print("="*80)


if __name__ == "__main__":
    main()

