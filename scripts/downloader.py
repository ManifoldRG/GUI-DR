# Download parquet from hf
from huggingface_hub import snapshot_download

snapshot_download(repo_id="osunlp/Multimodal-Mind2Web", repo_type="dataset", local_dir="mm_mind2web")