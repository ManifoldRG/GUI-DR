"""
Data loading utilities for parquet files, MHTML files, and DOM content.
"""

import json
import os
import ast
from typing import List, Tuple
import pandas as pd


def load_dom_content_json(dom_content_json_path: str) -> List[dict]:
    """Load dom content from JSON file."""
    with open(dom_content_json_path, 'r') as f:
        return json.load(f)


def load_action_list_from_mhtml(mhtml_files_dir: str) -> List[str]:
    """Load action UIDs from MHTML file names (ground truth).
    
    MHTML files are named: {action_uid}_before.mhtml
    Returns sorted list of action_uids found in the snapshots directory.
    """
    if not os.path.exists(mhtml_files_dir):
        raise ValueError(f"MHTML files directory not found: {mhtml_files_dir}")
    
    action_uids = [
        filename.replace('_before.mhtml', '')
        for filename in os.listdir(mhtml_files_dir)
        if filename.endswith('_before.mhtml')
    ]
    
    action_uids.sort()
    return action_uids


def load_current_page_urls(dom_content_json: List[dict], action_uids: List[str]) -> List[str]:
    """Load current page URLs from dom content, matching action_uids order.
    
    Args:
        dom_content_json: The dom content JSON list
        action_uids: List of action_uids to match (from MHTML files)
    
    Returns:
        List of page URLs in the same order as action_uids
    """
    uid_to_url = {}
    for item in dom_content_json:
        uid = item.get('action_uid')
        if (uid and 'before' in item and 'dom' in item['before'] and 
            'strings' in item['before']['dom'] and len(item['before']['dom']['strings']) > 1):
            uid_to_url[uid] = item['before']['dom']['strings'][1]
    
    return [uid_to_url.get(uid, '') for uid in action_uids]


def _parse_operation_column(df: pd.DataFrame) -> pd.DataFrame:
    """Parse operation column if it's a string representation of a dict/list."""
    if 'operation' not in df.columns:
        return df
    
    def parse_operation(x):
        if isinstance(x, str):
            try:
                return ast.literal_eval(x)
            except (ValueError, SyntaxError):
                return x
        return x
    
    df = df.copy()
    df['operation'] = df['operation'].apply(parse_operation)
    return df


def load_parquet_files_by_split(mm_mind2web_base: str, split: str) -> Tuple[pd.DataFrame, List[str]]:
    """Load parquet files for a specific split (train, test_domain, test_task, test_website).
    
    Args:
        mm_mind2web_base: Base directory for data
        split: One of 'train', 'test_domain', 'test_task', 'test_website'
    
    Returns:
        Tuple of (combined dataframe, list of unique task_uids from parquet)
    """
    data_dir = os.path.join(mm_mind2web_base, "data")
    
    if not os.path.exists(data_dir):
        raise ValueError(f"Data directory not found: {data_dir}")
    
    # Find parquet files for the specified split
    parquet_files = [
        os.path.join(data_dir, item)
        for item in os.listdir(data_dir)
        if item.endswith('.parquet') and item.startswith(split)
    ]
    
    if not parquet_files:
        raise ValueError(f"No {split} parquet files found in {data_dir}")
    
    for parquet_path in parquet_files:
        print(f"✅ Found {split} parquet file: {os.path.basename(parquet_path)}")
    
    # Columns to load (only what we need)
    columns_to_load = ['action_uid', 'pos_candidates', 'confirmed_task', 'operation', 
                       'target_action_reprs', 'annotation_id']
    
    # Load each parquet file with only needed columns
    dataframes = []
    for parquet_path in parquet_files:
        print(f"📂 Loading columns from {os.path.basename(parquet_path)}...")
        df = pd.read_parquet(parquet_path, columns=columns_to_load)
        df = _parse_operation_column(df)
        dataframes.append(df)
    
    if not dataframes:
        raise ValueError(f"No {split} parquet files could be loaded")
    
    # Concatenate all dataframes
    print(f"📊 Concatenating {len(dataframes)} {split} parquet files...")
    combined_df = pd.concat(dataframes, ignore_index=True)
    
    # Sort by annotation_id
    print(f"🔢 Sorting by annotation_id...")
    combined_df = combined_df.sort_values('annotation_id').reset_index(drop=True)
    
    # Get unique task_uids from the parquet data
    task_uids = combined_df['annotation_id'].unique().tolist()
    print(f"✅ Loaded {len(combined_df)} rows from {len(dataframes)} {split} parquet file(s)")
    print(f"📋 Found {len(task_uids)} unique tasks (annotation_ids) in {split} split")
    
    return combined_df, task_uids

