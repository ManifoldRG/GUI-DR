"""
Load and inspect eval_dataset_cleaned (HF datasets format).
Verifies structure for use with Hugging Face Data Studio / dataset viewer.
"""
from pathlib import Path
import pandas as pd
from datasets import load_from_disk

DS_PATH = Path(__file__).resolve().parent.parent / "eval_data"
assert DS_PATH.exists(), f"Dataset not found: {DS_PATH}"

print("Loading dataset from disk...")
ds = load_from_disk(str(DS_PATH))

print("\n" + "=" * 60)
print("COLUMNS & FEATURES")
print("=" * 60)
print(ds.features)
print("\nColumn names:", list(ds.column_names))

print("\n" + "=" * 60)
print("SHAPE")
print("=" * 60)
print(f"Number of rows: {len(ds):,}")

print("\n" + "=" * 60)
print("FIRST ROW (sample)")
print("=" * 60)
first = ds[0]
for k, v in first.items():
    if k == "screenshot":
        img = v
        print(f"  {k}: <PIL.Image.Image mode={getattr(img, 'mode', '?')} size={getattr(img, 'size', '?')}>")
    else:
        preview = str(v)[:80] + "..." if len(str(v)) > 80 else str(v)
        print(f"  {k}: {preview}")

print("\n" + "=" * 60)
print("FIRST 3 ROWS (table preview)")
print("=" * 60)
# Show non-image columns for first 3 rows
subset = ds.select_columns([c for c in ds.column_names if c != "screenshot"])
print(pd.DataFrame(subset[:3]).to_string())

print("\n" + "=" * 60)
print("DATA STUDIO / HUB COMPATIBILITY")
print("=" * 60)
# Check if screenshot is path-only (would break on Hub) or has bytes
row0_screenshot = ds[0]["screenshot"]
if hasattr(row0_screenshot, "filename") or (isinstance(row0_screenshot, dict) and row0_screenshot.get("path")):
    path_info = getattr(row0_screenshot, "filename", None) or (row0_screenshot.get("path") if isinstance(row0_screenshot, dict) else None)
    print(f"  Screenshot type: {type(row0_screenshot).__name__}")
    print(f"  Path-like: {path_info is not None}")
# PIL Image means decode worked (from path or bytes)
if hasattr(row0_screenshot, "size"):
    print(f"  Image decodes to PIL: Yes (size={row0_screenshot.size})")
else:
    print(f"  Image decodes to PIL: No (raw: {type(row0_screenshot).__name__})")
print("  For HF Data Studio: Image column will display if dataset is pushed to Hub")
print("  (e.g. ds.push_to_hub('your-org/eval_dataset_cleaned')). Images are read from")
print("  disk when pushing and embedded in the repo so the viewer can render them.")
print("\nDone.")
