"""
Push eval_dataset_cleaned to Hugging Face Hub (figai/GUI-Perturbed) for Data Studio.
Run from repo root. Requires: pip install huggingface_hub and being logged in (huggingface-cli login).
"""
from pathlib import Path
from datasets import load_from_disk

# Dataset saved by save_eval_data_to_hf_format.py — check repo root or data/
ROOT = Path(__file__).resolve().parent.parent
DS_PATH = ROOT / "eval_data"
REPO_ID = "figai/GUI-Perturbed"

if not DS_PATH.exists():
    raise FileNotFoundError(f"Dataset not found: {DS_PATH}")

print(f"Loading dataset from {DS_PATH}...")
ds = load_from_disk(str(DS_PATH))
print(ds)
print(f"\nPushing to https://huggingface.co/datasets/{REPO_ID} ...")
ds.push_to_hub(REPO_ID, private=False)
print(f"✓ Pushed to https://huggingface.co/datasets/{REPO_ID} (Data Studio should work)")
