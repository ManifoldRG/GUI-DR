import pandas as pd
from pathlib import Path
from datasets import Dataset, Features, Image, Value, concatenate_datasets
from PIL import Image as PILImage
import json
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc

# Use original CSV for metrics (cleaned CSV has corrupted hit_box_accuracy in some rows)
DATA_DIR = Path('data') if Path('data').exists() else Path('.')
# Filter to a single model and single reasoning type (set to None to keep all)
MODEL_FILTER = 'uitars15'  # one of: 'gta1', 'qwen25vl', 'uitars15'
USE_REASONING_FILTER = False  # True or False
# Resolve project root so /mnt/test_splits -> project test_splits/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_SPLITS_ROOT = PROJECT_ROOT / 'test_splits'

def _find_image_fallback(path_str: str) -> str | None:
    """
    If path doesn't exist, search under test_splits for run_*/<task_id>/screenshots/<filename>.
    Path format: .../test_splits/run_XXX/<uuid>/screenshots/<filename>
    Returns resolved path if found, else None.
    """
    p = Path(path_str)
    if p.exists():
        return path_str
    parts = p.parts
    try:
        idx = parts.index('screenshots')
    except ValueError:
        return None
    if idx < 1 or idx + 1 >= len(parts):
        return None
    task_id, filename = parts[idx - 1], parts[idx + 1]
    # UUID-like folder name (8-4-4-4-12 hex)
    if len(task_id) != 36 or task_id.count('-') != 4:
        return None
    # Prefer same run name if present
    run_name = parts[idx - 2] if idx >= 2 else None
    candidates = list(TEST_SPLITS_ROOT.glob(f"run_*/{task_id}/screenshots/{filename}"))
    if not candidates:
        return None
    if run_name and len(candidates) > 1:
        same_run = [c for c in candidates if c.parts[-4] == run_name]
        if same_run:
            return str(same_run[0].resolve())
    return str(candidates[0].resolve())


def _find_image_by_step_prefix(path_str: str) -> str | None:
    """
    When exact filename is wrong (e.g. df has step_3_click.png but file is step_3_type.png),
    find any screenshot in the same task folder matching step_<N>*.png.
    Path format: .../test_splits/run_XXX/<uuid>/screenshots/step_N_*.png
    Returns resolved path if found, else None.
    """
    p = Path(path_str)
    if p.exists():
        return path_str
    parts = p.parts
    try:
        idx = parts.index('screenshots')
    except ValueError:
        return None
    if idx < 1 or idx + 1 >= len(parts):
        return None
    task_id, filename = parts[idx - 1], parts[idx + 1]
    if len(task_id) != 36 or task_id.count('-') != 4:
        return None
    # step_3_click.png or step_10_click.png -> step prefix "step_3" or "step_10"
    stem = Path(filename).stem  # step_3_click
    if not stem.startswith("step_"):
        return None
    parts_stem = stem.split("_")
    if len(parts_stem) < 2:
        return None
    step_prefix = f"{parts_stem[0]}_{parts_stem[1]}"  # step_3 or step_10
    run_name = parts[idx - 2] if idx >= 2 else None
    # Glob run_*/task_id/screenshots/step_N*.png
    candidates = list(TEST_SPLITS_ROOT.glob(f"run_*/{task_id}/screenshots/{step_prefix}*.png"))
    if not candidates:
        return None
    if run_name and len(candidates) > 1:
        same_run = [c for c in candidates if c.parts[-4] == run_name]
        if same_run:
            return str(same_run[0].resolve())
    return str(candidates[0].resolve())


def resolve_image_path(path_str: str) -> str:
    """Rewrite /mnt/test_splits to project test_splits/; fallback by exact filename then by step_<N>*.png."""
    if pd.isna(path_str) or path_str == '':
        return path_str
    s = str(path_str).strip()
    if s.startswith('/mnt/test_splits'):
        s = str(TEST_SPLITS_ROOT) + s[len('/mnt/test_splits'):]
    if s.startswith('~'):
        s = s.replace('~', str(Path.home()))
    found = _find_image_fallback(s)
    if found is None:
        found = _find_image_by_step_prefix(s)
    return found if found is not None else s

# Use cleaned CSV as single source so interesting_cases is aligned with each row.
# (Using full_new + merge by index had misalignment and gave 3096 instead of 390*8=3120 per model+reasoning.)
df = pd.read_csv(DATA_DIR / 'baseline_results_full_new_cleaned.csv')
n_invalid_rows = (df['interesting_cases'] == 'Invalid').sum()
n_total = len(df)
df = df[df['interesting_cases'] != 'Invalid'].copy()
n_excluded = n_invalid_rows
n_kept = len(df)
print(f"Invalid (rows marked Invalid): {n_invalid_rows:,}")
print(f"Total rows (before exclusion): {n_total:,}")
print(f"Excluded: {n_excluded:,}")
print(f"Kept: {n_kept:,}")
if MODEL_FILTER is not None:
    df = df[df['model'] == MODEL_FILTER].copy()
if USE_REASONING_FILTER is not None:
    df = df[df['use_reasoning'] == USE_REASONING_FILTER].copy()
print(f"Loaded cleaned df with {len(df)} rows"
      + (f" (model={MODEL_FILTER}" if MODEL_FILTER else "")
      + (f", use_reasoning={USE_REASONING_FILTER}" if USE_REASONING_FILTER is not None else "")
      + ").")

print(df.info())

# Prepare data from cleaned df (keep source df column names for rows)
eval_data_df = df[['variant', 'query_type', 'task_id', 'step_index', 'instruction', 'ground_truth_bbox', 'image_path']].copy()
# Rewrite /mnt/test_splits to local test_splits/ folder
eval_data_df['image_path'] = eval_data_df['image_path'].apply(resolve_image_path)

# Convert ground_truth_bbox to JSON string upfront (for HF gt_bbox)
eval_data_df['ground_truth_bbox'] = eval_data_df['ground_truth_bbox'].apply(
    lambda x: json.dumps(x) if isinstance(x, (list, tuple)) else str(x) if x is not None else ''
)

def load_image(path):
    """Load image from file path and return PIL Image"""
    if pd.isna(path) or path == '':
        raise ValueError(f"Empty or NaN path encountered")
    path_str = str(path)
    if path_str.startswith('~'):
        path_str = path_str.replace('~', str(Path.home()))
    path_obj = Path(path_str)
    if not path_obj.exists():
        raise FileNotFoundError(f"Image file does not exist: {path_str}")
    try:
        return PILImage.open(path_obj).convert('RGB')
    except Exception as e:
        raise RuntimeError(f"Could not load image from {path_str}: {e}")

def process_row(original_idx, row):
    """Process a single row: resolve image path, return dict with HF feature names (screenshot = path for Image feature)."""
    try:
        path_str = str(row['image_path']).strip()
        if path_str.startswith('~'):
            path_str = path_str.replace('~', str(Path.home()))
        if pd.isna(row['image_path']) or not path_str or not Path(path_str).exists():
            raise FileNotFoundError(f"Image file does not exist: {path_str}")
        return {
            'visual_variant': row['variant'],
            'instruction_type': row['query_type'],
            'task_id': row['task_id'],
            'step_index': int(row['step_index']),
            'instruction': row['instruction'],
            'gt_bbox': row['ground_truth_bbox'],
            'screenshot': path_str,
            '_original_idx': original_idx,
        }, None
    except Exception as e:
        return None, (original_idx, row['image_path'], str(e))

BATCH_SIZE = 500
MAX_WORKERS = 4

features = Features({
    'visual_variant': Value('string'),
    'instruction_type': Value('string'),
    'task_id': Value('string'),
    'step_index': Value('int32'),
    'instruction': Value('string'),
    'gt_bbox': Value('string'),
    'screenshot': Image(),
})

print(f"Processing {len(eval_data_df)} examples in batches of {BATCH_SIZE}...")
datasets = []
failed_paths = []

for batch_start in range(0, len(eval_data_df), BATCH_SIZE):
    batch_end = min(batch_start + BATCH_SIZE, len(eval_data_df))
    batch_df = eval_data_df.iloc[batch_start:batch_end]

    print(f"Processing batch {batch_start//BATCH_SIZE + 1}/{(len(eval_data_df)-1)//BATCH_SIZE + 1} (rows {batch_start}-{batch_end-1})...")

    data_list = []

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_row, original_idx, row): original_idx
                for original_idx, row in batch_df.iterrows()
            }

            for future in tqdm(as_completed(futures), total=len(futures), desc=f"Batch {batch_start//BATCH_SIZE + 1}", leave=False):
                result, error = future.result()
                if error:
                    failed_paths.append(error)
                else:
                    data_list.append(result)

        if failed_paths and len([f for f in failed_paths if batch_start <= f[0] < batch_end]) > 0:
            batch_failures = [f for f in failed_paths if batch_start <= f[0] < batch_end]
            print(f"  Warning: {len(batch_failures)} failures in this batch")

        data_list = sorted(data_list, key=lambda x: x['_original_idx'])
        for item in data_list:
            del item['_original_idx']

        if not data_list:
            print(f"  Skipping batch {batch_start//BATCH_SIZE + 1}: no successful rows")
            continue

        # Build mapping with exact feature keys so Arrow schema matches Features
        mapping = {k: [row[k] for row in data_list] for k in features}
        batch_dataset = Dataset.from_dict(mapping, features=features)
        datasets.append(batch_dataset)

        del data_list
        gc.collect()

    except MemoryError:
        print(f"\nERROR: Out of memory processing batch {batch_start//BATCH_SIZE + 1}")
        print("Try reducing BATCH_SIZE or MAX_WORKERS")
        raise
    except Exception as e:
        print(f"\nERROR: Failed to process batch {batch_start//BATCH_SIZE + 1}: {e}")
        raise

if failed_paths:
    print(f"\nWarning: {len(failed_paths)} rows skipped (image not found):")
    for idx, path, error in failed_paths[:10]:
        print(f"  Row {idx}: {path} - {error}")
    if len(failed_paths) > 10:
        print(f"  ... and {len(failed_paths) - 10} more")
    if not datasets:
        raise RuntimeError(
            f"No images could be loaded ({len(failed_paths)} failures). Check that test_splits/ exists and paths are correct."
        )
    print(f"Proceeding with {sum(len(d) for d in datasets)} examples (skipped {len(failed_paths)} missing images).")

print("Combining batches...")
if not datasets:
    raise RuntimeError("No data to save. All rows failed or no batches produced.")
eval_dataset = concatenate_datasets(datasets)
print(f"✓ Dataset created with {len(eval_dataset)} examples")

del datasets
gc.collect()

print("Saving dataset to disk...")
try:
    eval_dataset.save_to_disk("eval_dataset_cleaned")
    print("✓ Dataset saved to eval_dataset_cleaned/ directory")
except Exception as e:
    print(f"ERROR saving dataset: {e}")
    raise